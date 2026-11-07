import hashlib
import hmac
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from .dashboard import router as dashboard_router
from .jobs import connection, schedule
from .storage import ReviewRun, session_factory

app = FastAPI(title="AI Code Review Agent")


class RepositoryPayload(BaseModel):
    full_name: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", max_length=300)


class InstallationPayload(BaseModel):
    id: int = Field(gt=0)


class HeadPayload(BaseModel):
    sha: str = Field(pattern=r"^[a-fA-F0-9]{40}$")


class PullPayload(BaseModel):
    head: HeadPayload


class WebhookPayload(BaseModel):
    repository: RepositoryPayload
    installation: InstallationPayload
    number: int = Field(gt=0)
    pull_request: PullPayload


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    try:
        with session_factory()() as db:
            db.execute(text("SELECT 1"))
        connection().ping()
    except Exception:
        raise HTTPException(503, "Database or queue unavailable") from None
    return {"status": "ready"}


@app.post("/webhooks/github", status_code=202)
async def webhook(request: Request):
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(503, "Webhook secret missing")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 1_000_000:
            raise HTTPException(413, "Webhook body too large")
    supplied = request.headers.get("x-hub-signature-256", "")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, "Invalid signature")
    if request.headers.get("x-github-event") != "pull_request":
        return {"status": "ignored"}
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(400, "Invalid JSON object") from None
    if payload.get("action") not in {"opened", "synchronize", "reopened"}:
        return {"status": "ignored"}
    delivery = request.headers.get("x-github-delivery", "")
    if not delivery or len(delivery) > 100:
        raise HTTPException(400, "Missing or invalid delivery ID")
    try:
        event = WebhookPayload.model_validate(payload)
    except ValidationError:
        raise HTTPException(422, "Malformed pull request event") from None
    approach = os.getenv("REVIEW_APPROACH", "plain")
    if approach not in {"plain", "context", "tool"}:
        raise HTTPException(503, "Invalid REVIEW_APPROACH configuration")
    with session_factory()() as db:
        run = ReviewRun(delivery_id=delivery, repository=event.repository.full_name,
                        installation_id=event.installation.id, pr_number=event.number,
                        head_sha=event.pull_request.head.sha, approach=approach)
        db.add(run)
        try:
            db.flush()
            schedule(db, "github", run.id)
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(select(ReviewRun).where(
                ReviewRun.repository == event.repository.full_name,
                ReviewRun.pr_number == event.number,
                ReviewRun.head_sha == event.pull_request.head.sha,
                ReviewRun.approach == approach))
            return {"status": "duplicate", "run_id": existing.id if existing else None}
        return {"status": "queued", "run_id": run.id}


app.include_router(dashboard_router)
static_dir = Path(__file__).parent / "static"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")
