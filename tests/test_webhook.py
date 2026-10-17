import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from review_agent.api import app


def test_rejects_unsigned_webhook(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "secret")
    response = TestClient(app).post("/webhooks/github", json={})
    assert response.status_code == 401


def test_ignores_verified_irrelevant_event(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "secret")
    body = json.dumps({"action": "created"}).encode()
    signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    response = TestClient(app).post("/webhooks/github", content=body,
        headers={"x-hub-signature-256": signature, "x-github-event": "issue_comment"})
    assert response.status_code == 202
    assert response.json()["status"] == "ignored"
