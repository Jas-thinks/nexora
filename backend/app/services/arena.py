"""Practice arena: private timed matches (2-8 players) on Nexora-authored problems, judged by the sandbox against hidden tests.
Fairness: players never see hidden tests or each other's code, only pass counts; the winner is the earliest FULL solve, else (at timeout) most tests passed, ties are draws."""
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.arena import problems as P
from app.execution import runner
from app.models.ai import Match, MatchPlayer
from app.models.user import User


def _aw(d):
    return None if d is None else (d if d.tzinfo else d.replace(tzinfo=UTC))


def create(db: Session, user_id: int, problem_key: str, minutes: int = 20, max_players: int = 2) -> Match:
    if problem_key not in P.PROBLEMS:
        raise ValueError("unknown problem")
    if not 5 <= minutes <= 90 or not 2 <= max_players <= 8:
        raise ValueError("minutes must be 5-90 and players 2-8")
    m = Match(code=secrets.token_hex(3).upper(), creator_id=user_id, problem_key=problem_key, minutes=minutes, max_players=max_players)
    db.add(m); db.flush()
    db.add(MatchPlayer(match_id=m.id, user_id=user_id, total_tests=len(P.PROBLEMS[problem_key]["tests"]))); db.commit()
    return m


def join(db: Session, user_id: int, code: str) -> Match:
    m = db.scalar(select(Match).where(Match.code == code.upper()))
    if m is None:
        raise LookupError("No match with that code")
    if db.scalar(select(MatchPlayer.id).where(MatchPlayer.match_id == m.id, MatchPlayer.user_id == user_id)):
        return m
    if m.status != "waiting":
        raise PermissionError("This match has already started")
    n = len(db.scalars(select(MatchPlayer.id).where(MatchPlayer.match_id == m.id)).all())
    if n >= m.max_players:
        raise PermissionError("This match is full")
    db.add(MatchPlayer(match_id=m.id, user_id=user_id, total_tests=len(P.PROBLEMS[m.problem_key]["tests"]))); db.commit()
    return m


def start(db: Session, user_id: int, mid: int, now: datetime | None = None) -> Match:
    m = db.get(Match, mid)
    if m is None or m.creator_id != user_id:
        raise LookupError("Match not found")
    if m.status != "waiting":
        raise PermissionError("Already started")
    if len(db.scalars(select(MatchPlayer.id).where(MatchPlayer.match_id == mid)).all()) < 2:
        raise PermissionError("Need at least 2 players")
    m.status, m.started_at = "running", now or datetime.now(UTC)
    db.commit()
    return m


def settle(db: Session, m: Match, now: datetime | None = None) -> Match:
    """Finish the match when someone solved it or time ran out. Idempotent."""
    now = now or datetime.now(UTC)
    if m.status != "running":
        return m
    ps = db.scalars(select(MatchPlayer).where(MatchPlayer.match_id == m.id)).all()
    solved = sorted((p for p in ps if p.solved_at), key=lambda p: _aw(p.solved_at))
    over = now >= _aw(m.started_at) + timedelta(minutes=m.minutes)
    if solved:
        m.winner_id, m.result_note = solved[0].user_id, "First full solve"
    elif over:
        best = max((p.best_passed for p in ps), default=0)
        tops = [p for p in ps if p.best_passed == best]
        if best == 0 or len(tops) > 1:
            m.winner_id, m.result_note = None, "Draw: " + ("nobody passed a test" if best == 0 else f"{len(tops)} players tied on {best} tests")
        else:
            m.winner_id, m.result_note = tops[0].user_id, f"Time up: most tests passed ({best})"
    else:
        return m
    m.status, m.ended_at = "finished", now
    db.commit()
    return m


def submit(db: Session, user_id: int, mid: int, language: str, code: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    m = db.get(Match, mid)
    pl = db.scalar(select(MatchPlayer).where(MatchPlayer.match_id == mid, MatchPlayer.user_id == user_id)) if m else None
    if m is None or pl is None:
        raise LookupError("Match not found")
    settle(db, m, now)
    if m.status != "running":
        raise PermissionError("The match is not running")
    res = runner.judge(language, code, P.tests_for(m.problem_key))
    if res.verdict == "ERR":
        raise RuntimeError(res.note)
    passed = sum(1 for t in res.tests if t["verdict"] == "OK")
    pl.attempts += 1; pl.last_submit_at = now; pl.best_passed = max(pl.best_passed, passed)
    full = res.verdict == "OK" and passed == pl.total_tests
    if full and pl.solved_at is None:
        pl.solved_at = now
    db.commit()
    settle(db, m, now)
    return {"verdict": "ACCEPTED" if full else res.verdict, "passed": passed, "total": pl.total_tests, "per_test": [t["verdict"] for t in res.tests], "compile_error": res.stderr[:600] if res.verdict == "CE" else None,
            "match_status": m.status}


def state(db: Session, user_id: int, mid: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    m = db.get(Match, mid)
    me = db.scalar(select(MatchPlayer).where(MatchPlayer.match_id == mid, MatchPlayer.user_id == user_id)) if m else None
    if m is None or me is None:
        raise LookupError("Match not found")
    settle(db, m, now)
    ps = db.scalars(select(MatchPlayer).where(MatchPlayer.match_id == mid).order_by(MatchPlayer.id)).all()
    names = {u.id: u.display_name for u in db.scalars(select(User).where(User.id.in_([p.user_id for p in ps])))}
    left = None if m.status != "running" else max(0, int((_aw(m.started_at) + timedelta(minutes=m.minutes) - now).total_seconds()))
    return {"id": m.id, "code": m.code, "status": m.status, "minutes": m.minutes, "max_players": m.max_players, "seconds_left": left, "is_creator": m.creator_id == user_id,
            "problem": P.public(m.problem_key) if m.status != "waiting" else {"title": P.PROBLEMS[m.problem_key]["title"], "level": P.PROBLEMS[m.problem_key]["level"], "hidden_tests": len(P.PROBLEMS[m.problem_key]["tests"])},
            "players": [{"name": names.get(p.user_id, "?"), "you": p.user_id == user_id, "attempts": p.attempts, "best_passed": p.best_passed, "total": p.total_tests, "solved": p.solved_at is not None} for p in ps],
            "winner": names.get(m.winner_id) if m.winner_id else None, "result": m.result_note or None}
