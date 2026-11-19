"""Interview resources: companies, which problems they are reported to ask, and a system-design question library.

Company->problem associations are COMMUNITY-REPORTED (candidates' recollections aggregated by third parties), not official company data, and
are stored as facts only (company, problem URL, frequency, recency) with attribution. See docs/interview-resources.md."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    tier: Mapped[str] = mapped_column(String(20), index=True)  # faang | bigtech | product | fintech | service | other  (OUR editorial grouping)
    domain: Mapped[str | None] = mapped_column(String(30), nullable=True)  # editorial, optional
    problem_count: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(80), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CompanyProblem(Base):
    __tablename__ = "company_problems"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    frequency: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100, relative within the company, as reported by the source
    recent: Mapped[bool] = mapped_column(default=False)  # reported within the source's most recent window we ingested
    __table_args__ = (UniqueConstraint("company_id", "problem_id"), Index("ix_cp_company_freq", "company_id", "frequency"))


class DesignQuestion(Base):
    __tablename__ = "design_questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(160))
    prompt: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(10), index=True)  # entry | mid | senior
    category: Mapped[str] = mapped_column(String(30), index=True)
    concepts: Mapped[list] = mapped_column(JSON, default=list)
    domains: Mapped[list] = mapped_column(JSON, default=list)  # editorial relevance, NOT reported interview data
    kind: Mapped[str] = mapped_column(String(10), default="hld")  # hld | lld


class CrashCourse(Base):
    """A user's 30/60-day interview crash course. `plan` is generated once (deterministic) from real company data; `done` holds manually ticked task ids."""
    __tablename__ = "crash_courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    days: Mapped[int] = mapped_column(Integer)
    track: Mapped[str] = mapped_column(String(10))  # both | dsa | sd
    level: Mapped[str] = mapped_column(String(10))
    target: Mapped[str] = mapped_column(String(80))  # a tier id or a company slug
    hours: Mapped[float] = mapped_column(Float, default=2.0)
    started_on: Mapped[str] = mapped_column(String(10))  # ISO date, in the student's own calendar
    plan: Mapped[list] = mapped_column(JSON, default=list)
    done: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
