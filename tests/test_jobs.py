import hashlib
import hmac
import json

import fakeredis
import pytest
from fastapi.testclient import TestClient
from rq import Queue, SimpleWorker
from sqlalchemy import select

from review_agent import github, jobs
from review_agent.api import app
from review_agent.storage import ReviewOutbox, ReviewRun, session_factory


@pytest.fixture
def environment(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'jobs.db'}")
    monkeypatch.setenv("DASHBOARD_TOKEN", "test")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "webhook-test")
    monkeypatch.setenv("REVIEW_MODE", "demo")
    redis = fakeredis.FakeRedis()
    monkeypatch.setattr(jobs, "connection", lambda: redis)
    return TestClient(app), redis


def event(client, payload=None, delivery="delivery-one"):
    payload = payload or {"action": "opened", "repository": {"full_name": "owner/repo"},
                          "installation": {"id": 3}, "number": 1,
                          "pull_request": {"head": {"sha": "a" * 40}}}
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"webhook-test", body, hashlib.sha256).hexdigest()
    return client.post("/webhooks/github", content=body, headers={"x-hub-signature-256": signature,
                       "x-github-event": "pull_request", "x-github-delivery": delivery})


def test_webhook_outbox_deduplicates_delivery_and_commit(environment):
    client, _ = environment
    assert event(client).json()["status"] == "queued"
    assert event(client).json()["status"] == "duplicate"
    assert event(client, delivery="delivery-two").json()["status"] == "duplicate"
    with session_factory()() as db:
        assert len(db.scalars(select(ReviewRun)).all()) == 1
        assert len(db.scalars(select(ReviewOutbox)).all()) == 1


def test_signed_malformed_event_rejected(environment):
    client, _ = environment
    assert event(client, {"action": "opened"}).status_code == 422
    assert event(client, delivery="").status_code == 400
    assert event(client, {"action": "closed"}).json()["status"] == "ignored"


def test_queue_outage_preserves_outbox_for_recovery(environment, monkeypatch):
    client, redis = environment
    event(client)
    original_queue = jobs.Queue

    def unavailable(*args, **kwargs):
        raise ConnectionError("offline")

    monkeypatch.setattr(jobs, "Queue", unavailable)
    with pytest.raises(ConnectionError):
        jobs.dispatch_once()
    with session_factory()() as db:
        assert db.scalars(select(ReviewOutbox)).one().delivered_at is None
    monkeypatch.setattr(jobs, "Queue", original_queue)
    assert jobs.dispatch_once() == 1
    assert jobs.dispatch_once() == 0
    assert Queue("reviews", connection=redis).count == 1


def test_dispatch_recovers_crash_after_enqueue(environment):
    client, redis = environment
    event(client)
    jobs.dispatch_once()
    with session_factory()() as db:
        item = db.scalars(select(ReviewOutbox)).one()
        item.delivered_at = None  # simulate lost SQL acknowledgement after successful enqueue
        db.commit()
    jobs.dispatch_once()
    assert Queue("reviews", connection=redis).count == 1


def test_webhook_to_queue_worker_comment_and_dashboard(environment, monkeypatch):
    client, redis = environment
    diff = ('diff --git a/access.py b/access.py\n--- a/access.py\n+++ b/access.py\n'
            '@@ -1,2 +1,2 @@\n def can_delete(actor, owner):\n'
            '-    return actor.id == owner.id\n+    return True\n')
    posted = []

    class Response:
        text = diff

        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    async def token(_):
        return "mock-installation-token"

    async def request(token, method, path, **kwargs):
        if method == "POST":
            posted.append(kwargs["json"])
        if path.endswith("/reviews"):
            return Response([])
        return Response({"head": {"sha": "a" * 40}, "state": "open"})

    monkeypatch.setattr(github, "installation_token", token)
    monkeypatch.setattr(github, "github_request", request)
    response = event(client)
    jobs.dispatch_once()
    queue = Queue("reviews", connection=redis)
    SimpleWorker([queue], connection=redis).work(burst=True, with_scheduler=False)
    detail = client.get(f'/api/dashboard/runs/github-{response.json()["run_id"]}',
                        headers={"Authorization": "Bearer test"}).json()
    assert detail["status"] == "completed"
    assert detail["findings"][0]["line_start"] == 2
    assert detail["diff"] == diff
    assert len(posted) == 1 and posted[0]["comments"][0]["line"] == 2
    assert event(client).json()["status"] == "duplicate"
    assert len(posted) == 1


def test_retry_uses_new_outbox_and_old_failure_does_not_override_it(environment):
    client, redis = environment
    response = event(client)
    jobs.dispatch_once()
    with session_factory()() as db:
        run = db.get(ReviewRun, response.json()["run_id"])
        run.status = "failed"
        db.commit()
    result = client.post(f'/api/dashboard/runs/github-{response.json()["run_id"]}/retry',
                         headers={"Authorization": "Bearer test"})
    assert result.status_code == 202
    jobs.reconcile_interrupted()
    with session_factory()() as db:
        assert db.get(ReviewRun, response.json()["run_id"]).status == "queued"
        assert len(db.scalars(select(ReviewOutbox)).all()) == 2
    assert client.post(f'/api/dashboard/runs/github-{response.json()["run_id"]}/retry',
                       headers={"Authorization": "Bearer test"}).status_code == 409
