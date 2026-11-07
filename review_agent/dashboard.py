"""Authenticated dashboard API. Manual reviews never publish to GitHub."""
import hmac
import os
from datetime import timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .core import changed_lines
from .jobs import schedule
from .storage import ManualRun, ReviewRun, session_factory


def authorize(authorization: str = Header(default="")):
    token = os.getenv("DASHBOARD_TOKEN", "")
    if not token:
        raise HTTPException(503, "Set DASHBOARD_TOKEN on the server to enable the dashboard.")
    if not hmac.compare_digest(authorization.encode(), f"Bearer {token}".encode()):
        raise HTTPException(401, "Invalid dashboard token.")


router = APIRouter(prefix="/api/dashboard", dependencies=[Depends(authorize)])


class ManualRequest(BaseModel):
    title: str = Field(default="Manual review", min_length=1, max_length=120)
    diff: str = Field(min_length=1, max_length=30000)
    approach: Literal["plain", "context"] = "plain"
    context: str = Field(default="", max_length=12000)


def serialize(run):
    manual = isinstance(run, ManualRun)
    data = run.data if manual else {}
    findings = data.get("findings", []) if manual else [f.data for f in run.findings]
    return {"id": f"{'manual' if manual else 'github'}-{run.id}",
            "title": run.title if manual else f"{run.repository} #{run.pr_number}",
            "source": "manual" if manual else "github", "status": run.status,
            "approach": run.approach, "created_at": run.created_at.replace(tzinfo=timezone.utc).isoformat(),
            "duration_ms": data.get("duration_ms") if manual else run.duration_ms,
            "metadata": (data.get("metadata", {}) if manual else
                         {k: v for k, v in (run.model_metadata or {}).items() if k != "diff"}),
            "findings": findings, "diff": data.get("diff") if manual else (run.model_metadata or {}).get("diff"),
            "error": ("Review failed. Check the provider configuration."
                      if run.status == "failed" else None),
            "url": None if manual else f"https://github.com/{run.repository}/pull/{run.pr_number}"}


@router.get("/runs")
def runs():
    with session_factory()() as db:
        github = db.scalars(select(ReviewRun).options(selectinload(ReviewRun.findings))
                            .order_by(ReviewRun.created_at.desc()).limit(100)).all()
        manual = db.scalars(select(ManualRun).order_by(ManualRun.created_at.desc()).limit(100)).all()
        items = sorted([serialize(r) for r in [*github, *manual]], key=lambda r: r["created_at"], reverse=True)[:100]
        # Diff and full finding text are only returned by the detail endpoint.
        return [{**{k: v for k, v in r.items() if k not in {"diff", "findings"}},
                 "finding_count": len(r["findings"])} for r in items]


@router.get("/runs/{run_id}")
def detail(run_id: str):
    try:
        kind, number = run_id.split("-", 1)
        if kind not in {"manual", "github"}:
            raise ValueError
        identifier = int(number)
    except ValueError:
        raise HTTPException(404, "Review not found") from None
    with session_factory()() as db:
        run = db.get(ManualRun if kind == "manual" else ReviewRun, identifier)
        if run is None:
            raise HTTPException(404, "Review not found")
        return serialize(run)


@router.post("/reviews", status_code=202)
def manual_review(payload: ManualRequest):
    if not any(changed_lines(payload.diff).values()):
        raise HTTPException(422, "Provide a unified diff with file headers and added lines.")
    if payload.approach == "context" and not payload.context.strip():
        raise HTTPException(422, "Repository context is required for this approach.")
    with session_factory()() as db:
        run = ManualRun(title=payload.title, approach=payload.approach, status="queued",
                        data={"diff": payload.diff, "context": payload.context})
        db.add(run)
        db.flush()
        schedule(db, "manual", run.id)
        db.commit()
        return serialize(run)


@router.post("/runs/{run_id}/retry", status_code=202)
def retry(run_id: str):
    item = detail(run_id)
    model = ManualRun if item["source"] == "manual" else ReviewRun
    with session_factory()() as db:
        run = db.scalar(select(model).where(model.id == int(run_id.split("-", 1)[1])).with_for_update())
        if run.status != "failed":
            raise HTTPException(409, "Only failed reviews can be retried")
        run.status = "queued"
        schedule(db, item["source"], run.id)
        db.commit()
        return serialize(run)
