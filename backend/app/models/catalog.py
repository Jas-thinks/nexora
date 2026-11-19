from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class Problem(Base):
    __tablename__ = "problems"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(64))  # e.g. "4A"
    name: Mapped[str] = mapped_column(String(300))
    rating: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    url: Mapped[str] = mapped_column(String(500))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Provenance / canonical identity (see docs/problem-data-model.md)
    canonical_url: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    source_difficulty: Mapped[str | None] = mapped_column(String(40), nullable=True)  # label as given by a source
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | inaccessible | discontinued | missing_upstream
    # --- acquisition provenance (original source data is preserved separately from the normalised columns)
    contest_ref: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    problem_index: Mapped[str | None] = mapped_column(String(16), nullable=True)
    time_limit_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_limit_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)  # which API/page produced the record
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_record: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # raw record as received
    statement_access: Mapped[str] = mapped_column(String(20), default="link_only")  # link_only | metadata_only | excerpt | full (only if licence allows)
    solved_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # latest observed (history in snapshots)
    submission_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (UniqueConstraint("platform", "external_id"),)


class ProblemStatisticsSnapshot(Base):
    __tablename__ = "problem_statistics_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(80))
    solved_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submission_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accepted_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SyncCheckpoint(Base):
    """Resumable position of a backfill/refresh stage for one platform."""
    __tablename__ = "sync_checkpoints"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(40))
    stage: Mapped[str] = mapped_column(String(30))  # enumerate | details
    cursor: Mapped[dict] = mapped_column(JSON, default=dict)
    done: Mapped[bool] = mapped_column(default=False)
    discovered: Mapped[int] = mapped_column(Integer, default=0)  # what the source says exist (if it says)
    retrieved: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("platform", "stage"),)


class SyncFailure(Base):
    __tablename__ = "sync_failures"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    stage: Mapped[str] = mapped_column(String(30))
    ref: Mapped[str] = mapped_column(String(200))  # page / id that failed
    error: Mapped[str] = mapped_column(String(600))
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved: Mapped[bool] = mapped_column(default=False)


class ProblemAlias(Base):
    """Explicit, evidence-backed equivalence between two Problem rows (never inferred from titles)."""
    __tablename__ = "problem_aliases"
    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    alias_problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    evidence: Mapped[str] = mapped_column(String(300))  # e.g. "same canonical_url", "official mirror: <url>"
    __table_args__ = (UniqueConstraint("problem_id", "alias_problem_id"),)


class Sheet(Base):
    __tablename__ = "sheets"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(String(1000), default="")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    source_url: Mapped[str] = mapped_column(String(500), default="")
    license: Mapped[str] = mapped_column(String(120), default="")
    access_status: Mapped[str] = mapped_column(String(30), default="imported")  # imported|inaccessible|user_import
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    import_report: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("slug", "owner_id"),)


class SheetSection(Base):
    __tablename__ = "sheet_sections"
    id: Mapped[int] = mapped_column(primary_key=True)
    sheet_id: Mapped[int] = mapped_column(ForeignKey("sheets.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("sheet_sections.id", ondelete="CASCADE"), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class SheetItem(Base):
    __tablename__ = "sheet_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    sheet_id: Mapped[int] = mapped_column(ForeignKey("sheets.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    section: Mapped[str] = mapped_column(String(200), default="")
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sheet_sections.id", ondelete="SET NULL"), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    source_title: Mapped[str] = mapped_column(String(300), default="")
    source_difficulty: Mapped[str | None] = mapped_column(String(40), nullable=True)


class ProblemStatus(Base):
    __tablename__ = "problem_status"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    solved: Mapped[bool] = mapped_column(default=False)
    attempts: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # self_reported | verified_submission | user_import  (verified always wins over self-reported)
    provenance: Mapped[str] = mapped_column(String(24), default="self_reported")
    first_solved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "problem_id"),)


class TopicMastery(Base):
    __tablename__ = "topic_mastery"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(80))
    p_known: Mapped[float] = mapped_column(default=0.2)
    attempts: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "topic"),)
