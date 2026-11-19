"""In-app notifications (+ optional email). Generated from real state, deduplicated per user/day/event so ticks are idempotent."""
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai import Notification, UserPrefs
from app.models.daily import DailyChallenge, ReviewItem
from app.models.integrations import ConnectedProfile, Contest, Submission
from app.models.user import User


def _add(db: Session, uid: int, kind: str, title: str, body: str, href: str, key: str) -> bool:
    if db.scalar(select(Notification.id).where(Notification.user_id == uid, Notification.dedupe_key == key)):
        return False
    db.add(Notification(user_id=uid, kind=kind, title=title, body=body[:400], href=href, dedupe_key=key)); db.flush()
    return True


def generate(db: Session, user_id: int, now: datetime | None = None) -> int:
    from app.services.student_analytics import _streaks
    now = now or datetime.now(UTC)
    today = now.date(); n = 0
    days = {(a if a.tzinfo else a.replace(tzinfo=UTC)).date() for (a,) in db.execute(select(Submission.submitted_at).where(Submission.user_id == user_id, Submission.submitted_at >= now - timedelta(days=400)))}
    cur, _ = _streaks(days, today) if days else (0, 0)
    if cur >= 2 and today not in days:
        n += _add(db, user_id, "streak", f"Your {cur}-day streak ends tonight", "Solve one problem to keep it alive.", "/daily", f"streak:{today}")
    due = db.scalars(select(ReviewItem).where(ReviewItem.user_id == user_id, ReviewItem.due_at <= now)).all()
    if due:
        n += _add(db, user_id, "revision", f"{len(due)} problem(s) due for revision", "Spaced reviews are cheapest right now.", "/revision", f"revision:{today}")
    if days and not db.scalar(select(DailyChallenge.id).where(DailyChallenge.user_id == user_id, DailyChallenge.day == today, DailyChallenge.status != "swapped")):
        n += _add(db, user_id, "daily", "Your Daily Challenge is ready", "Chosen from your weakest evidence-backed pattern.", "/daily", f"daily:{today}")
    plats = {p for (p,) in db.execute(select(ConnectedProfile.platform).where(ConnectedProfile.user_id == user_id))}
    if plats:
        for c in db.scalars(select(Contest).where(Contest.platform.in_(plats), Contest.start_time > now, Contest.start_time <= now + timedelta(hours=24))):
            n += _add(db, user_id, "contest", f"{c.name} starts within 24h", f"{c.platform}: open the prep plan.", f"/contests?prep={c.id}", f"contest:{c.id}")
    db.commit()
    return n


def send_email(to: str, subject: str, body: str) -> bool:
    s = get_settings()
    if not s.smtp_host:
        return False  # not configured: nothing is sent and nothing is pretended
    msg = EmailMessage(); msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject; msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as c:
            c.starttls()
            if s.smtp_user:
                c.login(s.smtp_user, s.smtp_password)
            c.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError):
        return False


def email_pending(db: Session, sender=send_email, limit: int = 50) -> int:
    sent = 0
    for nt in db.scalars(select(Notification).where(Notification.emailed.is_(False), Notification.read.is_(False)).order_by(Notification.id).limit(limit)):
        pr = db.get(UserPrefs, nt.user_id)
        if not (pr and pr.email_notifications):
            continue
        u = db.get(User, nt.user_id)
        if u and sender(u.email, nt.title, f"{nt.body}\n\nOpen Nexora: {nt.href}"):
            nt.emailed = True; sent += 1
    db.commit()
    return sent


def tick(db: Session, now: datetime | None = None, max_users: int = 300) -> dict:
    now = now or datetime.now(UTC)
    uids = [u for (u,) in db.execute(select(Submission.user_id).where(Submission.submitted_at >= now - timedelta(days=30)).distinct().limit(max_users))]
    return {"users": len(uids), "created": sum(generate(db, u, now) for u in uids), "emailed": email_pending(db)}
