from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class DailyChallenge(Base):
    __tablename__ = "daily_challenges"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    mode: Mapped[str] = mapped_column(String(20), default="personalized")
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    primary_pattern: Mapped[str | None] = mapped_column(String(60), nullable=True)
    objective_scores: Mapped[dict] = mapped_column(JSON, default=dict)  # per-objective feature values actually used
    explanation: Mapped[dict] = mapped_column(JSON, default=dict)
    policy_version: Mapped[str] = mapped_column(String(40), default="daily-v1")
    status: Mapped[str] = mapped_column(String(12), default="assigned")  # assigned | completed | skipped | swapped
    swaps: Mapped[int] = mapped_column(Integer, default=0)
    feedback: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # at most one non-swapped challenge per user/day/mode is enforced in the service (swapped rows stay as history)
    __table_args__ = (Index("ix_daily_user_day_mode", "user_id", "day", "mode"),)


class ReviewItem(Base):
    """Spaced-repetition schedule for problems the student has attempted (Leitner-style intervals)."""
    __tablename__ = "review_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    box: Mapped[int] = mapped_column(Integer, default=0)
    last_result: Mapped[str] = mapped_column(String(12), default="")
    __table_args__ = (UniqueConstraint("user_id", "problem_id"),)


class ReviewLog(Base):
    __tablename__ = "review_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    result: Mapped[str] = mapped_column(String(8))  # good | again
    was_due: Mapped[bool] = mapped_column(default=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class MistakeNote(Base):
    __tablename__ = "mistake_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    note: Mapped[str] = mapped_column(String(2000), default="")
    cause: Mapped[str | None] = mapped_column(String(20), nullable=True)  # student's own diagnosis: logic | edge-case | complexity | implementation | concept | careless
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "problem_id"),)
