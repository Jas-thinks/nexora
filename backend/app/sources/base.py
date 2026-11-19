from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator


@dataclass
class ProblemRecord:
    platform: str
    external_id: str
    name: str
    url: str
    rating: int | None = None
    source_difficulty: str | None = None
    tags: list[str] = field(default_factory=list)
    contest_ref: str | None = None
    problem_index: str | None = None
    time_limit_ms: int | None = None
    memory_limit_kb: int | None = None
    published_at: datetime | None = None
    solved_count: int | None = None
    submission_count: int | None = None
    accepted_count: int | None = None
    raw: dict | None = None
    section: str | None = None  # source-native grouping (e.g. CSES sections)


class ProblemSource:
    """A discoverable problem archive. `pages(cursor)` yields (records, next_cursor); next_cursor None => enumeration complete.
    `discovered_total` (if the source states it) lets us report coverage against the source's own claim."""
    platform = ""
    source_name = ""
    complete_enumeration = True   # does one full pass list every accessible problem?
    statement_access = "link_only"
    discovered_total: int | None = None

    def pages(self, cursor: dict | None) -> Iterator[tuple[list[ProblemRecord], dict | None]]:
        raise NotImplementedError

    def details(self, ref: str) -> ProblemRecord | None:  # optional second stage
        return None
