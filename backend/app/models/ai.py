from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class UserPrefs(Base):
    """Explicit, user-controlled privacy switches. Defaults are the privacy-preserving ones."""
    __tablename__ = "user_prefs"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    training_opt_in: Mapped[bool] = mapped_column(default=False)      # may mentor chats be used to fine-tune models?
    leaderboard_visible: Mapped[bool] = mapped_column(default=False)  # appear on public leaderboards?
    share_progress: Mapped[bool] = mapped_column(default=False)
    email_notifications: Mapped[bool] = mapped_column(default=False)
    experiment_opt_out: Mapped[bool] = mapped_column(default=False)  # always get the full policy; excluded from analysis
    daily_goal: Mapped[int] = mapped_column(Integer, default=1)   # solves per day
    weekly_goal: Mapped[int] = mapped_column(Integer, default=5)  # solves per week
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LLMCall(Base):
    __tablename__ = "llm_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(80))
    purpose: Mapped[str] = mapped_column(String(30), default="mentor")
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(default=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class MentorMessage(Base):
    __tablename__ = "mentor_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    thread: Mapped[str] = mapped_column(String(40), default="default")
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(20), default="concept")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # sources, provider, validation flags, hint_level
    feedback: Mapped[int | None] = mapped_column(Integer, nullable=True)  # +1 / -1
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index("ix_mentor_user_thread", "user_id", "thread", "id"),)


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True)  # stable id, e.g. "note:binary-search" or "user:12:abc"
    kind: Mapped[str] = mapped_column(String(20))  # note | pattern | user_note
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # pattern ids, license, source
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embed_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TrainingExample(Base):
    """Consent-gated fine-tuning corpus. Only created for users with prefs.training_opt_in; user id is NOT stored."""
    __tablename__ = "training_examples"
    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(20))
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # student feedback, used to filter
    provider: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CodeRun(Base):
    __tablename__ = "code_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int | None] = mapped_column(ForeignKey("problems.id", ondelete="SET NULL"), nullable=True)
    language: Mapped[str] = mapped_column(String(12))
    code: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(String(6))
    wall_ms: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(8), default="run")  # run | judge
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CodeDraft(Base):
    __tablename__ = "code_drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(60))  # "scratch" or "problem:<id>"
    language: Mapped[str] = mapped_column(String(12))
    code: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index("ux_draft", "user_id", "key", "language", unique=True),)


class Design(Base):
    __tablename__ = "designs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    scenario: Mapped[str | None] = mapped_column(String(30), nullable=True)
    graph: Mapped[dict] = mapped_column(JSON, default=dict)
    # open-ended design: ANY question, plus the written HLD sections (requirements, estimates, API, data model, deep dives, trade-offs)
    prompt: Mapped[str] = mapped_column(Text, default="")
    doc: Mapped[dict] = mapped_column(JSON, default=dict)
    question: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)  # slug from the question library, if started from one
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RecommendationLog(Base):
    """One row per recommendation shown. The basis of the experiment: arm, what was shown, and the state at assignment."""
    __tablename__ = "recommendation_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    challenge_id: Mapped[int | None] = mapped_column(ForeignKey("daily_challenges.id", ondelete="SET NULL"), nullable=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    arm: Mapped[str] = mapped_column(String(10))  # treatment | control
    policy: Mapped[str] = mapped_column(String(30))
    pattern: Mapped[str | None] = mapped_column(String(60), nullable=True)
    est_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    in_analysis: Mapped[bool] = mapped_column(default=True)  # False when the user opted out of the experiment
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ProblemPatternLabel(Base):
    """Problem-level pattern label. Only status='accepted' labels count as mastery evidence. LLM/rule output stays 'proposed' until reviewed."""
    __tablename__ = "problem_pattern_labels"
    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    pattern_id: Mapped[str] = mapped_column(String(60), index=True)
    source: Mapped[str] = mapped_column(String(10))  # rule | llm | human
    confidence: Mapped[float] = mapped_column(default=0.5)
    reason: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(10), default="proposed", index=True)  # proposed | accepted | rejected
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("problem_id", "pattern_id"),)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(400), default="")
    href: Mapped[str] = mapped_column(String(160), default="")
    dedupe_key: Mapped[str] = mapped_column(String(80))
    read: Mapped[bool] = mapped_column(default=False)
    emailed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key"),)


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    platform: Mapped[str] = mapped_column(String(20), default="codeforces")
    target: Mapped[int] = mapped_column(Integer)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    problem_key: Mapped[str] = mapped_column(String(40))
    minutes: Mapped[int] = mapped_column(Integer, default=20)
    max_players: Mapped[int] = mapped_column(Integer, default=2)
    status: Mapped[str] = mapped_column(String(10), default="waiting")  # waiting | running | finished
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    result_note: Mapped[str] = mapped_column(String(200), default="")


class MatchPlayer(Base):
    __tablename__ = "match_players"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    best_passed: Mapped[int] = mapped_column(Integer, default=0)
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    solved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_submit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("match_id", "user_id"),)


class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    minutes: Mapped[int] = mapped_column(Integer, default=45)
    status: Mapped[str] = mapped_column(String(10), default="running")  # running | finished
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rubric: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    self_eval: Mapped[dict | None] = mapped_column(JSON, nullable=True)
