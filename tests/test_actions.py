import json
from types import SimpleNamespace

import pytest

from review_agent import actions
from review_agent.core import Finding


@pytest.mark.asyncio
async def test_actions_posts_one_review_and_skips_duplicate(monkeypatch, tmp_path):
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps({"pull_request": {"number": 7, "head": {"sha": "abc"}}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    posts = []
    async def request(token, method, path, **kwargs):
        assert token == "test-token"
        if method == "POST":
            posts.append(kwargs["json"])
            return SimpleNamespace()
        if "accept" in kwargs:
            return SimpleNamespace(text="diff --git a/file.py b/file.py\n+++ b/file.py\n@@ -0,0 +1 @@\n+bad()")
        return SimpleNamespace(json=lambda: {"head": {"sha": "abc"}, "state": "open"})
    async def fake_review(diff, approach, metadata):
        assert approach == "plain"
        return [Finding(file_path="file.py", line_start=1, line_end=1, title="Bug",
                        severity="high", category="correctness", explanation="Broken call",
                        evidence="bad()")]
    async def exists(token, path, marker):
        return bool(posts)
    monkeypatch.setattr(actions, "github_request", request)
    monkeypatch.setattr(actions, "review", fake_review)
    monkeypatch.setattr(actions, "review_exists", exists)
    assert "1 findings" in await actions.run()
    assert posts[0]["comments"][0]["line"] == 1
    assert "already posted" in await actions.run()
    assert len(posts) == 1


@pytest.mark.asyncio
async def test_actions_skips_stale_pr(monkeypatch, tmp_path):
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps({"pull_request": {"number": 7, "head": {"sha": "old"}}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    async def request(*args, **kwargs):
        return SimpleNamespace(json=lambda: {"head": {"sha": "new"}, "state": "open"})
    monkeypatch.setattr(actions, "github_request", request)
    assert "stale" in await actions.run()
