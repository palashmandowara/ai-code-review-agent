from fastapi.testclient import TestClient

from review_agent.api import app
from review_agent.storage import ReviewRun, StoredFinding, session_factory

DIFF = ('diff --git a/access.py b/access.py\n--- a/access.py\n+++ b/access.py\n'
        '@@ -1,2 +1,2 @@\n def can_delete(actor, owner):\n'
        '-    return actor.id == owner.id\n+    return True\n')
AUTH = {"Authorization": "Bearer dashboard-test"}


def setup(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'dashboard.db'}")
    monkeypatch.setenv("DASHBOARD_TOKEN", "dashboard-test")
    monkeypatch.setenv("REVIEW_MODE", "demo")
    return TestClient(app)


def test_dashboard_requires_token(monkeypatch, tmp_path):
    client = setup(monkeypatch, tmp_path)
    for route in ["/api/dashboard/runs", "/api/dashboard/runs/manual-1"]:
        assert client.get(route).status_code == 401
    assert client.post("/api/dashboard/reviews", json={"diff": DIFF}).status_code == 401
    monkeypatch.delenv("DASHBOARD_TOKEN")
    assert client.get("/api/dashboard/runs", headers=AUTH).status_code == 503


def test_manual_review_persists_and_lists_without_diff(monkeypatch, tmp_path):
    client = setup(monkeypatch, tmp_path)
    response = client.post("/api/dashboard/reviews", headers=AUTH, json={"diff": DIFF, "title": "Auth check"})
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "completed"
    assert run["findings"][0]["line_start"] == 2
    assert run["metadata"]["model"] == "offline-demo-rule"
    assert client.get(f'/api/dashboard/runs/{run["id"]}', headers=AUTH).json()["diff"] == DIFF
    listing = client.get("/api/dashboard/runs", headers=AUTH).json()
    assert listing[0]["finding_count"] == 1
    assert "diff" not in listing[0]
    assert "findings" not in listing[0]


def test_bad_diff_context_and_missing_run(monkeypatch, tmp_path):
    client = setup(monkeypatch, tmp_path)
    for payload in [{"diff": "hello"}, {"diff": DIFF, "approach": "context"},
                    {"diff": DIFF, "approach": "tool"}, {"diff": "a" * 30001}]:
        assert client.post("/api/dashboard/reviews", headers=AUTH, json=payload).status_code == 422
    for identifier in ["nonsense", "manual-999", "github-abc", "unknown-1"]:
        assert client.get(f"/api/dashboard/runs/{identifier}", headers=AUTH).status_code == 404


def test_provider_failure_is_saved_without_secret(monkeypatch, tmp_path):
    client = setup(monkeypatch, tmp_path)

    async def fail(*args, **kwargs):
        raise RuntimeError("secret-provider-token")

    monkeypatch.setattr("review_agent.dashboard.review", fail)
    response = client.post("/api/dashboard/reviews", headers=AUTH, json={"diff": DIFF})
    assert response.json()["status"] == "failed"
    assert "secret-provider-token" not in response.text
    assert client.get("/api/dashboard/runs", headers=AUTH).json()[0]["status"] == "failed"


def test_github_history_and_finding_details(monkeypatch, tmp_path):
    client = setup(monkeypatch, tmp_path)
    with session_factory()() as db:
        run = ReviewRun(delivery_id="one", repository="owner/repo", installation_id=1,
                        pr_number=3, head_sha="abc", approach="tool", status="completed")
        db.add(run)
        db.flush()
        db.add(StoredFinding(run_id=run.id, data={"title": "Existing finding"}))
        db.commit()
        identifier = run.id
    result = client.get(f"/api/dashboard/runs/github-{identifier}", headers=AUTH).json()
    assert result["url"] == "https://github.com/owner/repo/pull/3"
    assert result["findings"][0]["title"] == "Existing finding"
    assert result["diff"] is None
