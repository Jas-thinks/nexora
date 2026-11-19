import json
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_role
from app.core.db import SessionLocal, get_db
from app.core.ratelimit import limiter
from app.core.security import decode_access_token
from app.models.community import Bookmark, Channel, Follow, Message, Mute, Reaction, Report
from app.models.user import AuditLog, User

router = APIRouter(tags=["community"])
DEFAULT_CHANNELS = [("general", "General", "Say hi, ask anything"), ("codeforces", "Codeforces", "Rounds, editorials, upsolving"), ("codechef", "CodeChef", "Starters and long challenges"),
                    ("leetcode", "LeetCode", "Interview-style problems"), ("atcoder", "AtCoder", "ABC / ARC / AGC"), ("dsa", "DSA Discussions", "Data structures and algorithms"),
                    ("dp", "Dynamic Programming", "States, transitions, optimisations"), ("graphs", "Graphs", "BFS, DFS, shortest paths, flows"), ("trees", "Trees", "Traversals, LCA, tree DP"),
                    ("system-design", "System Design", "HLD and LLD"), ("interview-prep", "Interview Preparation", "Mock interviews, experiences"), ("contests", "Contest Discussions", "Post-contest talk")]
EMOJI = {"👍", "🔥", "💡", "🎯", "❤️", "😂", "🤔"}


class Hub:
    """In-process pub/sub for WebSocket fan-out. Same interface a Redis pub/sub implementation would have (publish/subscribe per channel)."""
    def __init__(self): self.rooms: dict[int, set[WebSocket]] = {}

    async def join(self, cid: int, ws: WebSocket): self.rooms.setdefault(cid, set()).add(ws)
    def leave(self, cid: int, ws: WebSocket): self.rooms.get(cid, set()).discard(ws)

    async def publish(self, cid: int, payload: dict):
        dead = []
        for ws in list(self.rooms.get(cid, ())):
            try:
                await ws.send_text(json.dumps(payload, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead: self.leave(cid, ws)


hub = Hub()


def seed_channels(db: Session) -> None:
    have = set(db.scalars(select(Channel.slug)))
    for s, n, t in DEFAULT_CHANNELS:
        if s not in have: db.add(Channel(slug=s, name=n, topic=t))
    db.commit()


def _msg(db: Session, m: Message, me: int | None = None) -> dict:
    u = db.get(User, m.user_id) if m.user_id else None
    rx: dict = {}
    for e, uid in db.execute(select(Reaction.emoji, Reaction.user_id).where(Reaction.message_id == m.id)):
        r = rx.setdefault(e, {"count": 0, "mine": False}); r["count"] += 1; r["mine"] = r["mine"] or uid == me
    replies = db.scalar(select(func.count()).select_from(Message).where(Message.parent_id == m.id, Message.deleted.is_(False))) or 0
    return {"id": m.id, "channel_id": m.channel_id, "parent_id": m.parent_id, "kind": m.kind, "language": m.language, "author": u.display_name if u else "deleted user",
            "author_id": m.user_id, "content": "[message removed by a moderator]" if m.deleted else m.content, "deleted": m.deleted, "created_at": m.created_at, "reactions": rx, "replies": replies}


@router.get("/channels")
def channels(user: User = Depends(current_user), db: Session = Depends(get_db)):
    seed_channels(db)
    return [{"id": c.id, "slug": c.slug, "name": c.name, "topic": c.topic} for c in db.scalars(select(Channel).order_by(Channel.id))]


class ChannelIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]{3,40}$")
    name: str = Field(min_length=2, max_length=80)
    topic: str = Field("", max_length=200)


@router.post("/channels", status_code=201)
def create_channel(body: ChannelIn, user: User = Depends(require_role("moderator", "admin")), db: Session = Depends(get_db)):
    if db.scalar(select(Channel).where(Channel.slug == body.slug)):
        raise HTTPException(409, "Channel exists")
    c = Channel(slug=body.slug, name=body.name, topic=body.topic, created_by=user.id)
    db.add(c); db.commit()
    return {"id": c.id, "slug": c.slug}


@router.get("/channels/{cid}/messages")
def messages(cid: int, before: int | None = None, limit: int = Query(30, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Channel, cid) is None:
        raise HTTPException(404, "Channel not found")
    q = select(Message).where(Message.channel_id == cid, Message.parent_id.is_(None))
    if before:
        q = q.where(Message.id < before)
    rows = db.scalars(q.order_by(Message.id.desc()).limit(limit + 1)).all()
    more = len(rows) > limit
    rows = rows[:limit]
    return {"items": [_msg(db, m, user.id) for m in reversed(rows)], "next_before": rows[-1].id if more and rows else None}


@router.get("/messages/{mid}/thread")
def thread(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    root = db.get(Message, mid)
    if root is None:
        raise HTTPException(404, "Message not found")
    replies = db.scalars(select(Message).where(Message.parent_id == mid).order_by(Message.id)).all()
    return {"root": _msg(db, root, user.id), "replies": [_msg(db, m, user.id) for m in replies]}


class PostIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    kind: str = Field("text", pattern="^(text|code)$")
    language: str | None = Field(None, max_length=16)
    parent_id: int | None = None


def _check_can_post(db: Session, user: User, content: str, cid: int) -> None:
    now = datetime.now(UTC)
    for m in db.scalars(select(Mute).where(Mute.user_id == user.id)):
        until = m.until if m.until.tzinfo else m.until.replace(tzinfo=UTC)
        if until > now:
            raise HTTPException(403, f"You are muted until {until.isoformat()}: {m.reason or 'moderator action'}")
    limiter.check(f"msg:{user.id}", 8, 10.0)  # 8 messages / 10 s
    recent = db.scalar(select(func.count()).select_from(Message).where(Message.user_id == user.id, Message.content == content, Message.created_at >= now - timedelta(seconds=60)))
    if recent:
        raise HTTPException(429, "Duplicate message: please don't repeat yourself.")
    if content.lower().count("http") > 3:
        raise HTTPException(422, "Too many links in one message.")


@router.post("/channels/{cid}/messages", status_code=201)
async def post_message(cid: int, body: PostIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Channel, cid) is None:
        raise HTTPException(404, "Channel not found")
    if body.parent_id:
        parent = db.get(Message, body.parent_id)
        if parent is None or parent.channel_id != cid:
            raise HTTPException(404, "Parent message not found in this channel")
        if parent.parent_id:
            raise HTTPException(422, "Threads are one level deep: reply to the thread's first message.")
    _check_can_post(db, user, body.content, cid)
    m = Message(channel_id=cid, user_id=user.id, parent_id=body.parent_id, kind=body.kind, language=body.language, content=body.content)
    db.add(m); db.commit()
    out = _msg(db, m, user.id)
    await hub.publish(cid, {"type": "message", "message": out})
    return out


class ReactIn(BaseModel):
    emoji: str


@router.post("/messages/{mid}/react")
async def react(mid: int, body: ReactIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(Message, mid)
    if m is None or m.deleted:
        raise HTTPException(404, "Message not found")
    if body.emoji not in EMOJI:
        raise HTTPException(422, f"emoji must be one of {sorted(EMOJI)}")
    ex = db.scalar(select(Reaction).where(Reaction.message_id == mid, Reaction.user_id == user.id, Reaction.emoji == body.emoji))
    if ex: db.delete(ex)
    else: db.add(Reaction(message_id=mid, user_id=user.id, emoji=body.emoji))
    db.commit()
    out = _msg(db, m, user.id)
    await hub.publish(m.channel_id, {"type": "reaction", "message_id": mid, "reactions": out["reactions"]})
    return out["reactions"]


@router.post("/messages/{mid}/bookmark")
def bookmark(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Message, mid) is None:
        raise HTTPException(404, "Message not found")
    ex = db.scalar(select(Bookmark).where(Bookmark.message_id == mid, Bookmark.user_id == user.id))
    if ex: db.delete(ex)
    else: db.add(Bookmark(message_id=mid, user_id=user.id))
    db.commit()
    return {"bookmarked": ex is None}


@router.get("/bookmarks")
def bookmarks(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ms = db.scalars(select(Message).join(Bookmark, Bookmark.message_id == Message.id).where(Bookmark.user_id == user.id, Message.deleted.is_(False)).order_by(Bookmark.id.desc()))
    return [_msg(db, m, user.id) for m in ms]


@router.get("/search/messages")
def search(q: str = Query(min_length=2, max_length=80), channel_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Message).where(Message.deleted.is_(False), Message.content.ilike(f"%{q.replace('%', '').replace('_', '')}%"))
    if channel_id: stmt = stmt.where(Message.channel_id == channel_id)
    return [_msg(db, m, user.id) for m in db.scalars(stmt.order_by(Message.id.desc()).limit(30))]


@router.post("/users/{uid}/follow")
def follow(uid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if uid == user.id or db.get(User, uid) is None:
        raise HTTPException(422, "Invalid user")
    ex = db.scalar(select(Follow).where(Follow.follower_id == user.id, Follow.followee_id == uid))
    if ex: db.delete(ex)
    else: db.add(Follow(follower_id=user.id, followee_id=uid))
    db.commit()
    return {"following": ex is None}


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


@router.post("/messages/{mid}/report", status_code=201)
def report(mid: int, body: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Message, mid) is None:
        raise HTTPException(404, "Message not found")
    if db.scalar(select(Report).where(Report.message_id == mid, Report.reporter_id == user.id)):
        raise HTTPException(409, "You already reported this message")
    db.add(Report(message_id=mid, reporter_id=user.id, reason=body.reason)); db.commit()
    return {"reported": True}


@router.get("/mod/reports")
def reports(user: User = Depends(require_role("moderator", "admin")), db: Session = Depends(get_db)):
    out = []
    for r in db.scalars(select(Report).where(Report.status == "open").order_by(Report.id)):
        m = db.get(Message, r.message_id)
        out.append({"id": r.id, "reason": r.reason, "message": _msg(db, m) if m else None, "reporter_id": r.reporter_id})
    return out


class ModIn(BaseModel):
    action: str = Field(pattern="^(delete|dismiss|mute)$")
    mute_hours: int = Field(24, ge=1, le=720)


@router.post("/mod/reports/{rid}")
async def moderate(rid: int, body: ModIn, mod: User = Depends(require_role("moderator", "admin")), db: Session = Depends(get_db)):
    r = db.get(Report, rid)
    if r is None or r.status != "open":
        raise HTTPException(404, "Open report not found")
    m = db.get(Message, r.message_id)
    if body.action == "dismiss":
        r.status = "dismissed"
    else:
        r.status = "actioned"
        if m:
            m.deleted = True
            if body.action == "mute" and m.user_id:
                db.add(Mute(user_id=m.user_id, until=datetime.now(UTC) + timedelta(hours=body.mute_hours), reason=r.reason, by=mod.id))
    db.add(AuditLog(user_id=mod.id, action=f"mod.{body.action}", detail={"report": rid, "message": r.message_id}))
    db.commit()
    if m and body.action != "dismiss":
        await hub.publish(m.channel_id, {"type": "deleted", "message_id": m.id})
    return {"status": r.status}


@router.websocket("/ws/channels/{cid}")
async def ws_channel(ws: WebSocket, cid: int, token: str = Query("")):
    """Real-time channel feed. Auth: access token as ?token=. Server pushes message/reaction/deleted events; clients post via REST."""
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        await ws.close(code=4401); return
    with SessionLocal() as db:
        u = db.get(User, int(payload["sub"]))
        if u is None or not u.is_active or db.get(Channel, cid) is None:
            await ws.close(code=4404); return
    await ws.accept()
    await hub.join(cid, ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive pings; inbound data is ignored on purpose
    except WebSocketDisconnect:
        pass
    finally:
        hub.leave(cid, ws)
