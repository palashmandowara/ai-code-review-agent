"""Run the existing reviewer in GitHub Actions without a local webhook server."""
import asyncio
import json
import os

from .core import review
from .github import github_request, review_exists


async def run() -> str:
    token = os.environ["GITHUB_TOKEN"]
    repository = os.environ["GITHUB_REPOSITORY"]
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as event_file:
        event = json.load(event_file)
    number = event["pull_request"]["number"]
    expected_sha = event["pull_request"]["head"]["sha"]
    path = f"/repos/{repository}/pulls/{number}"
    marker = f"<!-- review-agent:{repository}:{number}:{expected_sha}:plain -->"

    current = (await github_request(token, "GET", path)).json()
    if current["head"]["sha"] != expected_sha or current["state"] != "open":
        return "Skipped stale or closed pull request"
    if await review_exists(token, path, marker):
        return "Review already posted for this commit"

    diff = (await github_request(token, "GET", path, accept="application/vnd.github.diff")).text
    if len(diff) > 30000:
        return "Skipped pull request: diff exceeds 30000 characters"
    metadata = {}
    findings = await review(diff, "plain", metadata=metadata)
    current = (await github_request(token, "GET", path)).json()
    if current["head"]["sha"] != expected_sha or current["state"] != "open":
        return "Skipped pull request updated during review"
    if await review_exists(token, path, marker):
        return "Review already posted for this commit"
    comments = [{"path": f.file_path, "line": f.line_start, "side": "RIGHT",
                 "body": f"**{f.title}** ({f.severity})\n\n{f.explanation}\n\nEvidence: {f.evidence}"}
                for f in findings]
    await github_request(token, "POST", f"{path}/reviews", json={
        "commit_id": expected_sha, "event": "COMMENT", "body": marker, "comments": comments})
    return f"Posted review with {len(comments)} findings; model={metadata.get('model', 'unknown')}"


def main() -> None:
    print(asyncio.run(run()))


if __name__ == "__main__":
    main()
