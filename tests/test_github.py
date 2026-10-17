import base64

import pytest

from review_agent import github


class Response:
    def __init__(self, value):
        self.value = value

    def json(self):
        return self.value


@pytest.mark.asyncio
async def test_repository_context_is_pinned_and_bounded(monkeypatch):
    calls = []

    async def fake_request(token, method, path, **kwargs):
        calls.append((path, kwargs))
        if "/git/trees/" in path:
            return Response({"tree": []})
        return Response({"type": "file", "size": 6,
                         "content": base64.b64encode(b"let x;").decode()})

    monkeypatch.setattr(github, "github_request", fake_request)
    diff = "diff --git a/src/app.js b/src/app.js\n--- a/src/app.js\n+++ b/src/app.js\n@@ -0,0 +1 @@\n+let x;\n"
    context, diagnostics = await github.repository_context("token", "owner/repo", "abc123", diff)
    assert "let x;" in context
    assert diagnostics == ""
    assert calls == [
        ("/repos/owner/repo/git/trees/abc123", {"params": {"recursive": "1"}}),
        ("/repos/owner/repo/contents/src/app.js", {"params": {"ref": "abc123"}}),
    ]


@pytest.mark.asyncio
async def test_existing_review_marker(monkeypatch):
    async def fake_request(*args, **kwargs):
        return Response([{"body": "<!-- review-agent:owner/repo:1:sha:plain -->"}])

    monkeypatch.setattr(github, "github_request", fake_request)
    assert await github.review_exists("token", "/repos/owner/repo/pulls/1",
                                      "<!-- review-agent:owner/repo:1:sha:plain -->")


@pytest.mark.asyncio
async def test_repository_context_includes_matching_test(monkeypatch):
    async def fake_request(token, method, path, **kwargs):
        if "/git/trees/" in path:
            return Response({"tree": [{"path": "tests/test_widget.js", "type": "blob", "size": 20}]})
        data = b"test('widget', () => {})" if "test_widget" in path else b"let widget = 1;"
        return Response({"type": "file", "size": len(data),
                         "content": base64.b64encode(data).decode()})

    monkeypatch.setattr(github, "github_request", fake_request)
    diff = ("diff --git a/src/widget.js b/src/widget.js\n--- a/src/widget.js\n"
            "+++ b/src/widget.js\n@@ -0,0 +1 @@\n+let widget = 1;\n")
    context, _ = await github.repository_context("token", "owner/repo", "sha", diff)
    assert "FILE src/widget.js" in context
    assert "FILE tests/test_widget.js" in context
