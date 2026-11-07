import os
from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class ReviewRun(Base):
    __tablename__ = "review_runs"
    __table_args__ = (UniqueConstraint("repository", "pr_number", "head_sha", "approach",
                                      name="uq_review_commit_approach"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String(100), unique=True)
    repository: Mapped[str] = mapped_column(String(300))
    installation_id: Mapped[int] = mapped_column(Integer)
    pr_number: Mapped[int] = mapped_column(Integer)
    head_sha: Mapped[str] = mapped_column(String(100))
    approach: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    findings: Mapped[list["StoredFinding"]] = relationship(back_populates="run")


class StoredFinding(Base):
    __tablename__ = "findings"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("review_runs.id"))
    data: Mapped[dict] = mapped_column(JSON)
    run: Mapped[ReviewRun] = relationship(back_populates="findings")


class ManualRun(Base):
    __tablename__ = "manual_review_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    approach: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReviewOutbox(Base):
    """Committed with a run, then delivered to Redis by the dispatcher."""
    __tablename__ = "review_outbox"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    run_id: Mapped[int] = mapped_column(Integer)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


@lru_cache(maxsize=8)
def _sessions(url):
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def session_factory():
    return _sessions(os.getenv("DATABASE_URL", "sqlite:///./review_agent.db"))

