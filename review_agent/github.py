"""GitHub App authentication, diff retrieval, and review publication."""
import asyncio
import base64
import os
import time
from urllib.parse import quote

import httpx
import jwt


async def installation_token(installation_id: int) -> str:
    private_key = os.environ["GITHUB_PRIVATE_KEY"].replace("\\n", "\n")
    now = int(time.time())
    bearer = jwt.encode({"iat": now - 60, "exp": now + 540, "iss": os.environ["GITHUB_APP_ID"]},
                        private_key, algorithm="RS256")
    async with httpx.AsyncClient(timeout=25, base_url="https://api.github.com") as client:
        response = await client.post(f"/app/installations/{installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {bearer}", "Accept": "application/vnd.github+json"})
        response.raise_for_status()
        return response.json()["token"]


async def github_request(token: str, method: str, path: str, **kwargs):
    async with httpx.AsyncClient(timeout=30, base_url="https://api.github.com") as client:
        response = await client.request(method, path, headers={"Authorization": f"Bearer {token}",
            "Accept": kwargs.pop("accept", "application/vnd.github+json")}, **kwargs)
        response.raise_for_status()
        return response


async def repository_context(token: str, repository: str, sha: str, diff: str) -> tuple[str, str]:
    """Fetch bounded changed files and related tests/modules pinned to the PR SHA."""
    from .core import changed_lines

    snippets = []
    diagnostics = []
    changed = [name for name in changed_lines(diff) if name.endswith((".py", ".js", ".ts"))][:12]
    related = []
    if changed:
        tree = (await github_request(token, "GET", f"/repos/{repository}/git/trees/{sha}",
            params={"recursive": "1"})).json()
        stems = {name.rsplit("/", 1)[-1].rsplit(".", 1)[0].removeprefix("test_") for name in changed}
        for entry in tree.get("tree", []):
            name = entry.get("path", "")
            if (entry.get("type") == "blob" and name not in changed and entry.get("size", 999999) <= 16000
                and name.endswith((".py", ".js", ".ts"))
                and any(stem in name.rsplit("/", 1)[-1] for stem in stems if len(stem) >= 3)):
                related.append(name)
            if len(related) >= 6:
                break
    for name in changed + related:
        if not name.endswith((".py", ".js", ".ts")):
            continue
        path = f"/repos/{repository}/contents/{quote(name, safe='/')}"
        response = await github_request(token, "GET", path, params={"ref": sha})
        item = response.json()
        if item.get("type") != "file" or item.get("size", 0) > 16000:
            continue
        content = base64.b64decode(item["content"]).decode("utf-8", errors="replace")
        snippets.append(f"FILE {name}\n{content[:3000]}")
        if name in changed and name.endswith(".py"):
            try:
                proc = await asyncio.create_subprocess_exec("ruff", "check", "--output-format", "json",
                    "--stdin-filename", name, "-", stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, _ = await asyncio.wait_for(proc.communicate(content.encode()), timeout=15)
                diagnostics.append(stdout.decode(errors="replace")[:1500])
            except (TimeoutError, FileNotFoundError):
                diagnostics.append("Analyzer unavailable")
    return "\n".join(snippets)[:12000], "\n".join(diagnostics)[:4000]


async def review_exists(token: str, path: str, marker: str) -> bool:
    for page in range(1, 6):
        reviews = (await github_request(token, "GET", f"{path}/reviews",
            params={"per_page": 100, "page": page})).json()
        if any(marker in (item.get("body") or "") for item in reviews):
            return True
        if len(reviews) < 100:
            break
    return False


def process_pull_request(run_id: int):
    """Worker entry point. Rechecks the SHA before posting to avoid stale reviews."""
    from .core import review
    from .storage import ReviewRun, StoredFinding, session_factory

    sessions = session_factory()
    with sessions() as db:
        run = db.get(ReviewRun, run_id)
        if not run or run.status == "completed":
            return
        run.status = "running"
        db.commit()
        started = time.monotonic()
        try:
            token = asyncio.run(installation_token(run.installation_id))
            pr_path = f"/repos/{run.repository}/pulls/{run.pr_number}"
            pr = asyncio.run(github_request(token, "GET", pr_path)).json()
            if pr["head"]["sha"] != run.head_sha:
                run.status = "stale"
                db.commit()
                return
            diff = asyncio.run(github_request(token, "GET", pr_path,
                accept="application/vnd.github.diff")).text
            context, diagnostics = "", ""
            if run.approach != "plain":
                context, diagnostics = asyncio.run(repository_context(token, run.repository,
                    run.head_sha, diff))
            metadata = {}
            findings = asyncio.run(review(diff, run.approach, context=context,
                diagnostics=diagnostics, metadata=metadata))
            run.model_metadata = metadata
            marker = f"<!-- review-agent:{run.repository}:{run.pr_number}:{run.head_sha}:{run.approach} -->"
            if findings:
                current = asyncio.run(github_request(token, "GET", pr_path)).json()
                if current["head"]["sha"] != run.head_sha:
                    run.status = "stale"
                    db.commit()
                    return
                if not asyncio.run(review_exists(token, pr_path, marker)):
                    comments = [{"path": f.file_path, "line": f.line_start, "side": "RIGHT",
                        "body": f"**{f.title}** ({f.severity})\n\n{f.explanation}\n\nEvidence: {f.evidence}"}
                        for f in findings]
                    asyncio.run(github_request(token, "POST", f"{pr_path}/reviews", json={
                        "commit_id": run.head_sha, "event": "COMMENT", "body": marker,
                        "comments": comments}))
            for finding in findings:
                db.add(StoredFinding(run_id=run.id, data=finding.model_dump()))
            run.status = "completed"
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)[:500]
            raise
        finally:
            run.duration_ms = int((time.monotonic() - started) * 1000)
            db.commit()
