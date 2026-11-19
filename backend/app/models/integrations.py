from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class ConnectedProfile(Base):
    __tablename__ = "connected_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(40))
    handle: Mapped[str] = mapped_column(String(120))
    # public_api: data pulled from a documented/public API | user_imported | link_only
    data_level: Mapped[str] = mapped_column(String(20), default="link_only")
    status: Mapped[str] = mapped_column(String(20), default="linked")  # linked|ok|error
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "platform", "handle"),)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("connected_profiles.id", ondelete="SET NULL"), nullable=True)
    platform: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(80))
    problem_id: Mapped[int | None] = mapped_column(ForeignKey("problems.id", ondelete="SET NULL"), nullable=True, index=True)
    problem_ref: Mapped[str] = mapped_column(String(120))
    verdict: Mapped[str] = mapped_column(String(12))  # AC WA TLE MLE RE CE OTHER
    raw_verdict: Mapped[str] = mapped_column(String(60), default="")
    language: Mapped[str | None] = mapped_column(String(80), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    in_contest: Mapped[bool | None] = mapped_column(nullable=True)  # None = unknown, never guessed
    provenance: Mapped[str] = mapped_column(String(16), default="verified")  # verified | user_imported
    __table_args__ = (UniqueConstraint("user_id", "platform", "external_id"),
                      Index("ix_sub_user_time", "user_id", "submitted_at"))


class Contest(Base):
    __tablename__ = "contests"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(300))
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str] = mapped_column(String(500))
    rated: Mapped[bool | None] = mapped_column(nullable=True)
    source: Mapped[str] = mapped_column(String(80))  # which API produced this row
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("platform", "external_id"),)


class RatingHistory(Base):
    """One row per rated contest participation."""
    __tablename__ = "rating_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("connected_profiles.id", ondelete="SET NULL"), nullable=True)
    platform: Mapped[str] = mapped_column(String(40))
    contest_ref: Mapped[str] = mapped_column(String(80))
    contest_name: Mapped[str] = mapped_column(String(300))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    old_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    performance: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None when platform doesn't expose it
    __table_args__ = (UniqueConstraint("user_id", "platform", "contest_ref"),
                      Index("ix_rating_user_time", "user_id", "at"))


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("connected_profiles.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))  # profile_sync | contests | problems
    platform: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(12), default="queued", index=True)  # queued running succeeded failed dead
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DataQualityReport(Base):
    __tablename__ = "data_quality_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    scope: Mapped[str] = mapped_column(String(60))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
