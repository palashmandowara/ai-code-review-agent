"""Durable SQL outbox and bounded RQ delivery. Never execute submitted code."""
import asyncio
import logging
import os
import time
from datetime import datetime, timezone

from redis import Redis
from rq import Queue, Retry
from sqlalchemy import func, select

from .core import review
from .storage import ManualRun, ReviewOutbox, ReviewRun, session_factory

logger = logging.getLogger(__name__)


def connection():
    return Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                          socket_connect_timeout=3, socket_timeout=5)


def schedule(db, kind, run_id):
    # The caller commits this in the same transaction as the run.
    db.add(ReviewOutbox(kind=kind, run_id=run_id))


def dispatch_once():
    queue = Queue("reviews", connection=connection())
    with session_factory()() as db:
        pending = db.scalars(select(ReviewOutbox).where(ReviewOutbox.delivered_at.is_(None))
                             .order_by(ReviewOutbox.id).limit(100)).all()
        delivered = 0
        for item in pending:
            # Stable ID makes a crash after enqueue/before SQL acknowledgement recoverable.
            job_id = f"review-{item.kind}-{item.run_id}-{item.id}"
            if queue.fetch_job(job_id) is None:
                queue.enqueue("review_agent.jobs.execute", item.kind, item.run_id,
                              job_id=job_id, job_timeout=300, result_ttl=86400,
                              retry=Retry(max=2, interval=[60, 180]))
            item.delivered_at = datetime.now(timezone.utc)
            db.commit()
            delivered += 1
        return delivered


def execute(kind, run_id):
    # RQ deliveries are at-least-once; serialize publication across duplicate jobs.
    with connection().lock(f"review-lock:{kind}:{run_id}", timeout=330, blocking_timeout=5):
        if kind == "github":
            from .github import process_pull_request
            process_pull_request(run_id)
        elif kind == "manual":
            process_manual(run_id)
        else:
            raise ValueError("Unknown review job kind")


def process_manual(run_id):
    with session_factory()() as db:
        run = db.get(ManualRun, run_id)
        if not run or run.status == "completed":
            return
        run.status = "running"
        db.commit()
        started = time.monotonic()
        metadata = {}
        data = dict(run.data)
        try:
            findings = asyncio.run(review(data["diff"], run.approach,
                                          context=data.get("context", ""), metadata=metadata))
            data["findings"] = [f.model_dump() for f in findings]
            run.status = "completed"
            data.pop("error", None)
        except Exception as exc:
            run.status = "failed"
            data["error"] = type(exc).__name__  # never persist provider credentials or response bodies
            raise
        finally:
            data.update(metadata=metadata, duration_ms=int((time.monotonic() - started) * 1000))
            run.data = data
            db.commit()


def reconcile_interrupted():
    """Mark terminal RQ failures visible; scheduled retries remain resumable."""
    queue = Queue("reviews", connection=connection())
    with session_factory()() as db:
        latest = select(func.max(ReviewOutbox.id)).group_by(ReviewOutbox.kind, ReviewOutbox.run_id)
        rows = db.scalars(select(ReviewOutbox).where(ReviewOutbox.id.in_(latest),
                                                   ReviewOutbox.delivered_at.is_not(None))).all()
        for item in rows:
            model = ManualRun if item.kind == "manual" else ReviewRun
            run = db.get(model, item.run_id)
            if not run or run.status not in {"running", "queued"}:
                continue
            job = queue.fetch_job(f"review-{item.kind}-{item.run_id}-{item.id}")
            age = (datetime.now(timezone.utc) - item.delivered_at.replace(tzinfo=timezone.utc)).total_seconds()
            if (job and job.get_status() in {"failed", "stopped", "canceled"}) or (job is None and age > 360):
                run.status = "failed"
                if isinstance(run, ReviewRun):
                    run.error = "Worker interrupted or job expired"
                else:
                    run.data = {**run.data, "error": "Worker interrupted or job expired"}
        db.commit()


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            dispatch_once()
            reconcile_interrupted()
        except Exception as exc:
            logger.warning("Dispatcher unavailable: %s", type(exc).__name__)
        time.sleep(5)


if __name__ == "__main__":
    main()
