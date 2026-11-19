from dataclasses import dataclass, field
from datetime import datetime


class NotSupported(Exception):
    """Raised when a platform adapter does not provide a capability (never faked)."""


@dataclass
class ProfileInfo:
    handle: str
    display_name: str | None = None
    rating: int | None = None
    max_rating: int | None = None
    rank: str | None = None


@dataclass
class NormSubmission:
    external_id: str
    problem_ref: str
    verdict: str  # AC WA TLE MLE RE CE OTHER
    raw_verdict: str
    submitted_at: datetime
    language: str | None = None
    time_ms: int | None = None
    memory_kb: int | None = None
    in_contest: bool | None = None
    provenance: str = "verified"


@dataclass
class NormRating:
    contest_ref: str
    contest_name: str
    at: datetime
    old_rating: int | None
    new_rating: int | None
    rank: int | None = None
    performance: int | None = None


@dataclass
class NormContest:
    external_id: str
    name: str
    start_time: datetime | None
    duration_seconds: int | None
    url: str
    rated: bool | None = None
    source: str = ""


@dataclass
class NormProblem:
    external_id: str
    name: str
    url: str
    rating: int | None = None
    tags: list[str] = field(default_factory=list)
    source_difficulty: str | None = None


@dataclass
class SubmissionPage:
    items: list[NormSubmission]
    checkpoint: dict  # opaque, adapter-defined; persisted so the next sync is incremental
    skipped: int = 0


VERDICTS = {"AC", "WA", "TLE", "MLE", "RE", "CE", "OTHER"}
