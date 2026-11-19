import pytest
from sqlalchemy import select

from app.core import db as dbmod
from app.core.ratelimit import limiter
from app.models.user import User
from tests.conftest import auth, register


@pytest.fixture()
def env(client):
    a = register(client, "a@example.com"); b = register(client, "b@example.com")
    ha, hb = auth(a), auth(b)
    chans = client.get("/channels", headers=ha).json()
    return client, a, b, ha, hb, chans[0]["id"]


def post(c, h, cid, text, **kw):
    return c.post(f"/channels/{cid}/messages", headers=h, json={"content": text, **kw})


def make_mod(email):
    with dbmod.SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email)); u.role = "moderator"; db.commit()


def test_default_channels_seeded_and_auth_required(env):
    c, a, b, ha, hb, cid = env
    names = [x["slug"] for x in c.get("/channels", headers=ha).json()]
    assert {"general", "codeforces", "dp", "graphs", "system-design", "interview-prep", "contests"} <= set(names)
    assert c.get("/channels").status_code == 401


def test_post_paginate_and_threads(env):
    c, a, b, ha, hb, cid = env
    ids = [post(c, ha, cid, f"msg {i}").json()["id"] for i in range(5)]
    page1 = c.get(f"/channels/{cid}/messages?limit=2", headers=hb).json()
    assert [m["content"] for m in page1["items"]] == ["msg 3", "msg 4"] and page1["next_before"] == ids[3]
    page2 = c.get(f"/channels/{cid}/messages?limit=2&before={page1['next_before']}", headers=hb).json()
    assert [m["content"] for m in page2["items"]] == ["msg 1", "msg 2"]
    r1 = post(c, hb, cid, "reply one", parent_id=ids[0]).json()
    assert post(c, hb, cid, "nested", parent_id=r1["id"]).status_code == 422  # one level of threading
    th = c.get(f"/messages/{ids[0]}/thread", headers=ha).json()
    assert th["root"]["replies"] == 1 and th["replies"][0]["content"] == "reply one"
    assert all(m["parent_id"] is None for m in c.get(f"/channels/{cid}/messages?limit=50", headers=ha).json()["items"])  # replies stay out of the main feed


def test_code_snippets_reactions_bookmarks_search_follow(env):
    c, a, b, ha, hb, cid = env
    m = post(c, ha, cid, "int main(){}", kind="code", language="cpp").json()
    assert m["kind"] == "code" and m["language"] == "cpp"
    assert c.post(f"/messages/{m['id']}/react", headers=hb, json={"emoji": "🔥"}).json()["🔥"] == {"count": 1, "mine": True}
    assert c.post(f"/messages/{m['id']}/react", headers=hb, json={"emoji": "🔥"}).json() == {}  # toggle off
    assert c.post(f"/messages/{m['id']}/react", headers=hb, json={"emoji": "💩"}).status_code == 422
    assert c.post(f"/messages/{m['id']}/bookmark", headers=hb).json()["bookmarked"] and len(c.get("/bookmarks", headers=hb).json()) == 1
    assert [x["id"] for x in c.get("/search/messages?q=main", headers=ha).json()] == [m["id"]]
    assert c.get("/search/messages?q=%25", headers=ha).status_code == 422
    uid_b = c.get("/auth/me", headers=hb).json()["id"]
    assert c.post(f"/users/{uid_b}/follow", headers=ha).json()["following"] and c.post(f"/users/{c.get('/auth/me', headers=ha).json()['id']}/follow", headers=ha).status_code == 422


def test_spam_controls_rate_limit_duplicates_links(env):
    c, a, b, ha, hb, cid = env
    assert post(c, ha, cid, "same").status_code == 201 and post(c, ha, cid, "same").status_code == 429
    assert post(c, ha, cid, "http://a http://b http://c http://d").status_code == 422
    limiter.hits.clear()
    codes = [post(c, hb, cid, f"flood {i}").status_code for i in range(10)]
    assert codes[:8] == [201] * 8 and codes[8:] == [429, 429]
    assert c.post(f"/channels/{cid}/messages", headers=ha, json={"content": "x" * 4001}).status_code == 422


def test_moderation_flow_report_delete_mute_and_permissions(env):
    c, a, b, ha, hb, cid = env
    bad = post(c, hb, cid, "buy cheap followers").json()
    assert c.post(f"/messages/{bad['id']}/report", headers=ha, json={"reason": "spam"}).status_code == 201
    assert c.post(f"/messages/{bad['id']}/report", headers=ha, json={"reason": "spam"}).status_code == 409
    assert c.get("/mod/reports", headers=ha).status_code == 403  # students cannot moderate
    make_mod("a@example.com")
    ha2 = auth(c.post("/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"}).json())
    rep = c.get("/mod/reports", headers=ha2).json()
    assert len(rep) == 1 and rep[0]["message"]["content"] == "buy cheap followers"
    assert c.post(f"/mod/reports/{rep[0]['id']}", headers=ha2, json={"action": "mute", "mute_hours": 2}).json()["status"] == "actioned"
    shown = c.get(f"/channels/{cid}/messages", headers=ha2).json()["items"][-1]
    assert shown["deleted"] and "removed by a moderator" in shown["content"]
    limiter.hits.clear()
    r = post(c, hb, cid, "i am back")
    assert r.status_code == 403 and "muted" in r.json()["detail"]
    assert c.post("/channels", headers=hb, json={"slug": "my-room", "name": "My room"}).status_code == 403
    assert c.post("/channels", headers=ha2, json={"slug": "my-room", "name": "My room"}).status_code == 201


def test_websocket_requires_valid_token_and_receives_live_events(env):
    c, a, b, ha, hb, cid = env
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect(f"/ws/channels/{cid}?token=bad"):
            pass
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect(f"/ws/channels/99999?token={a['access_token']}"):
            pass
    with c.websocket_connect(f"/ws/channels/{cid}?token={a['access_token']}") as ws, c.websocket_connect(f"/ws/channels/{cid}?token={b['access_token']}") as ws2:
        m = post(c, hb, cid, "live hello").json()
        ev = ws.receive_json(); ev2 = ws2.receive_json()
        assert ev["type"] == "message" and ev["message"]["content"] == "live hello" and ev2["message"]["id"] == m["id"]
        c.post(f"/messages/{m['id']}/react", headers=ha, json={"emoji": "👍"})
        assert ws.receive_json()["type"] == "reaction"
