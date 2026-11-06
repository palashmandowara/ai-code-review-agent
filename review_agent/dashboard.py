"""Authenticated dashboard API. Manual reviews never publish to GitHub."""
import hmac
import os
import time
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column

from .core import changed_lines, review
from .storage import Base, ReviewRun, session_factory


class ManualRun(Base):
    __tablename__ = "manual_review_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    approach: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


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
            "metadata": data.get("metadata", {}) if manual else (run.model_metadata or {}),
            "findings": findings, "diff": data.get("diff"),
            "error": ("Review failed. Check the provider configuration."
                      if run.status == "failed" else None),
            "url": None if manual else f"https://github.com/{run.repository}/pull/{run.pr_number}"}


@router.get("/runs")
def runs():
    with session_factory()() as db:
        github = db.scalars(select(ReviewRun).order_by(ReviewRun.created_at.desc()).limit(100)).all()
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


@router.post("/reviews", status_code=201)
async def manual_review(payload: ManualRequest):
    if not any(changed_lines(payload.diff).values()):
        raise HTTPException(422, "Provide a unified diff with file headers and added lines.")
    if payload.approach == "context" and not payload.context.strip():
        raise HTTPException(422, "Repository context is required for this approach.")
    started = time.monotonic()
    metadata = {}
    with session_factory()() as db:
        run = ManualRun(title=payload.title, approach=payload.approach, status="running", data={"diff": payload.diff})
        db.add(run)
        db.commit()
        try:
            findings = await review(payload.diff, payload.approach, context=payload.context, metadata=metadata)
            run.status = "completed"
            run.data = {"diff": payload.diff, "findings": [f.model_dump() for f in findings], "metadata": metadata,
                        "duration_ms": int((time.monotonic() - started) * 1000)}
        except Exception:
            run.status = "failed"
            run.data = {"diff": payload.diff, "metadata": metadata,
                        "duration_ms": int((time.monotonic() - started) * 1000)}
        db.commit()
        return serialize(run)
