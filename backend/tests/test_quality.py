from app.core import db as dbmod
from app.models.catalog import Problem
from app.models.integrations import Submission
from app.services.quality import build_report
from datetime import UTC, datetime

from tests.conftest import register


def test_report_counts_missing_data_and_unlinked_submissions(client):
    register(client)  # user 1 must exist: Postgres enforces the foreign key that SQLite ignores
    with dbmod.SessionLocal() as db:
        db.add_all([Problem(platform="codeforces", external_id="1A", name="a", rating=800, tags=["math"], url="u"),
                    Problem(platform="leetcode", external_id="x", name="x", rating=None, tags=[], url="u2")])
        db.add_all([Submission(user_id=1, platform="codeforces", external_id="s1", problem_ref="1A", problem_id=1, verdict="AC", submitted_at=datetime.now(UTC)),
                    Submission(user_id=1, platform="codeforces", external_id="s2", problem_ref="9Z", problem_id=None, verdict="WA", submitted_at=datetime.now(UTC))])
        db.commit()
        m = build_report(db)
    assert m["problems_total"] == 2 and m["problems_without_rating"] == 1 and m["problems_without_tags"] == 1
    assert m["submissions_unlinked_to_catalog"] == 1 and m["submission_link_rate"] == 0.5


def test_empty_database_reports_none_not_zero_division(client):
    with dbmod.SessionLocal() as db:
        m = build_report(db, persist=False)
    assert m["submission_link_rate"] is None
