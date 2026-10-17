import hashlib
import hmac
import json
import os

from fastapi import FastAPI, HTTPException, Request
from redis import Redis
from rq import Queue, Retry
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .storage import ReviewRun, session_factory

app = FastAPI(title="AI Code Review Agent")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhooks/github", status_code=202)
async def webhook(request: Request):
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(503, "Webhook secret missing")
    body = await request.body()
    supplied = request.headers.get("x-hub-signature-256", "")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(401, "Invalid signature")
    if request.headers.get("x-github-event") != "pull_request":
        return {"status": "ignored"}
    payload = json.loads(body)
    if payload.get("action") not in {"opened", "synchronize", "reopened"}:
        return {"status": "ignored"}
    delivery = request.headers.get("x-github-delivery")
    if not delivery:
        raise HTTPException(400, "Missing delivery ID")
    installation = payload.get("installation", {}).get("id")
    if not installation:
        raise HTTPException(400, "Missing installation")
    sessions = session_factory()
    with sessions() as db:
        run = ReviewRun(delivery_id=delivery, repository=payload["repository"]["full_name"],
            installation_id=installation, pr_number=payload["number"],
            head_sha=payload["pull_request"]["head"]["sha"],
            approach=os.getenv("REVIEW_APPROACH", "plain"))
        db.add(run)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(select(ReviewRun).where(
                ReviewRun.repository == run.repository,
                ReviewRun.pr_number == run.pr_number,
                ReviewRun.head_sha == run.head_sha,
                ReviewRun.approach == run.approach))
            if existing is None or existing.status != "failed":
                return {"status": "duplicate"}
            run = existing
            run.status = "queued"
            run.error = None
            db.commit()
        try:
            Queue("reviews", connection=Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0")))\
                .enqueue("review_agent.github.process_pull_request", run.id, job_timeout=180,
                         retry=Retry(max=2, interval=[30, 120]))
        except Exception:
            run.status = "failed"
            run.error = "Queue unavailable"
            db.commit()
            raise HTTPException(503, "Queue unavailable")
        return {"status": "queued", "run_id": run.id}
