from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from review_agent import core, github, storage


@pytest.mark.parametrize("approach", ["plain", "context", "tool"])
def test_worker_posts_once_and_records_results(tmp_path, monkeypatch, approach):
    engine = create_engine(f"sqlite:///{tmp_path / 'runs.db'}")
    storage.Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(storage, "session_factory", lambda: sessions)
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    with sessions() as db:
        run = storage.ReviewRun(delivery_id="delivery", installation_id=17,
            repository="owner/repo", pr_number=1, head_sha="sha", approach=approach)
        db.add(run)
        db.commit()
        run_id = run.id

    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n"
    posted = []

    async def token(installation):
        assert installation == 17
        return "token"

    async def request(token, method, path, **kwargs):
        if method == "POST":
            posted.append(kwargs["json"])
            return SimpleNamespace(json=lambda: {})
        if path.endswith("/reviews"):
            return SimpleNamespace(json=lambda: [])
        if kwargs.get("accept") == "application/vnd.github.diff":
            return SimpleNamespace(text=diff)
        return SimpleNamespace(json=lambda: {"head": {"sha": "sha"}})

    async def context(*args, **kwargs):
        return "FILE a.py\nnew", "[]"

    async def fake_review(diff_arg, approach_arg, **kwargs):
        assert diff_arg == diff and approach_arg == approach
        assert kwargs["context"] == ("" if approach == "plain" else "FILE a.py\nnew")
        kwargs["metadata"]["model"] = "mock"
        return [core.Finding(file_path="a.py", line_start=1, line_end=1, title="Issue",
            severity="medium", category="correctness", explanation="Bad", evidence="new")]

    monkeypatch.setattr(github, "installation_token", token)
    monkeypatch.setattr(github, "github_request", request)
    monkeypatch.setattr(github, "repository_context", context)
    monkeypatch.setattr(core, "review", fake_review)
    github.process_pull_request(run_id)
    github.process_pull_request(run_id)
    assert len(posted) == 1
    assert posted[0]["comments"][0]["line"] == 1
    with sessions() as db:
        run = db.get(storage.ReviewRun, run_id)
        assert run.status == "completed"
        assert run.model_metadata["model"] == "mock"
        assert len(run.findings) == 1

