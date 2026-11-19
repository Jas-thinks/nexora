from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.arena import problems as P
from app.core import db as dbmod
from app.execution import runner
from app.services import arena
from tests.conftest import auth, register

REAL = runner.docker_ready() and runner.image_present(runner.LANGS["python"].image)

SOLUTIONS = {
    "array-sum": "n=int(input());print(sum(map(int,input().split())))",
    "max-subarray": "n=int(input());a=list(map(int,input().split()))\nb=c=a[0]\nfor x in a[1:]:\n    c=max(x,c+x);b=max(b,c)\nprint(b)",
    "balanced-brackets": "s=input().strip();st=[];m={')':'(',']':'[','}':'{'};ok=True\nfor c in s:\n    if c in '([{': st.append(c)\n    elif not st or st.pop()!=m[c]: ok=False;break\nprint('YES' if ok and not st else 'NO')",
    "unique-window": "s=input().strip();last={};best=l=0\nfor i,c in enumerate(s):\n    if c in last and last[c]>=l: l=last[c]+1\n    last[c]=i;best=max(best,i-l+1)\nprint(best)",
    "gcd-all": "import math\nn=int(input());g=0\nfor x in map(int,input().split()): g=math.gcd(g,x)\nprint(g)",
    "pair-target": "n,t=map(int,input().split());a=list(map(int,input().split()));s=set();r='NO'\nfor x in a:\n    if t-x in s: r='YES';break\n    s.add(x)\nprint(r)",
    "huge-fibonacci": "M=10**9+7\ndef f(k):\n    if k==0: return 0,1\n    a,b=f(k>>1);c=a*((2*b-a)%M)%M;d=(a*a+b*b)%M\n    return (d,(c+d)%M) if k&1 else (c,d)\nprint(f(int(input()))[0])",
    "grid-escape": "import sys\nfrom collections import deque\nh,w=map(int,input().split());g=[input() for _ in range(h)]\nfor i in range(h):\n    for j in range(w):\n        if g[i][j]=='S': s=(i,j)\n        if g[i][j]=='T': t=(i,j)\nd={s:0};q=deque([s]);r=-1\nwhile q:\n    x,y=q.popleft()\n    if (x,y)==t: r=d[t];break\n    for dx,dy in((1,0),(-1,0),(0,1),(0,-1)):\n        nx,ny=x+dx,y+dy\n        if 0<=nx<h and 0<=ny<w and g[nx][ny]!='#' and (nx,ny) not in d: d[(nx,ny)]=d[(x,y)]+1;q.append((nx,ny))\nprint(r)",
}


def test_every_problem_has_samples_hidden_tests_and_no_leaks():
    for k, v in P.PROBLEMS.items():
        assert len(v["tests"]) >= 8 and v["samples"] and v["statement"] and v["input"] and v["output"], k
        pub = P.public(k)
        assert "tests" not in pub and pub["hidden_tests"] == len(v["tests"]) and len(pub["samples"]) == len(v["samples"])


def test_reference_functions_agree_with_brute_force():
    import random
    r = random.Random(1)
    for _ in range(200):
        a = [r.randint(-9, 9) for _ in range(r.randint(1, 9))]
        assert P.ref_kadane(a) == max(sum(a[i:j]) for i in range(len(a)) for j in range(i + 1, len(a) + 1))
        t = r.randint(-12, 12)
        assert P.ref_two_sum(a, t) == ("YES" if any(a[i] + a[j] == t for i in range(len(a)) for j in range(len(a)) if i != j) else "NO")
        s = "".join(r.choice("abc") for _ in range(r.randint(1, 10)))
        assert P.ref_unique(s) == max(len(set(s[i:j])) == j - i and j - i or 0 for i in range(len(s)) for j in range(i + 1, len(s) + 1))
    assert [P.ref_fib(n) for n in range(10)] == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34] and P.ref_fib(10**18) == P.ref_fib(10**18)
    assert P.ref_brackets("{[()]}") == "YES" and P.ref_brackets("([)]") == "NO" and P.ref_grid(["S#T"]) == -1 and P.ref_grid(["S.T"]) == 2


@pytest.mark.skipif(not REAL, reason="Docker + python image required")
@pytest.mark.parametrize("key", list(P.PROBLEMS))
def test_correct_solution_passes_every_sample_and_hidden_test_in_the_real_sandbox(key, monkeypatch):
    monkeypatch.setitem(runner.LIMITS, "time_s", 6.0)
    samples = [{"input": i, "expected": o} for i, o in P.PROBLEMS[key]["samples"]]
    r = runner.judge("python", SOLUTIONS[key], samples + P.tests_for(key))
    assert r.verdict == "OK", [(t["n"], t["verdict"], t["stderr"][:80]) for t in r.tests if t["verdict"] != "OK"]


@pytest.mark.skipif(not REAL, reason="Docker + python image required")
def test_naive_quadratic_solution_is_rejected_by_the_large_tests(monkeypatch):
    monkeypatch.setitem(runner.LIMITS, "time_s", 3.0)
    naive = "n=int(input());a=list(map(int,input().split()));b=a[0]\nfor i in range(n):\n    s=0\n    for j in range(i,n):\n        s+=a[j];b=max(b,s)\nprint(b)"
    r = runner.judge("python", naive, P.tests_for("max-subarray"))
    assert r.verdict == "TLE" and r.tests[0]["verdict"] == "OK"  # right on small inputs, too slow on n=200000


# ---------------------------------------------------------------- match engine (judge mocked for speed)
@pytest.fixture()
def duo(client, monkeypatch):
    register(client, "a@example.com"); register(client, "b@example.com"); register(client, "c@example.com")
    def fake(language, code, tests, max_tests=40):
        n = len(tests); ok = code.strip() == "ok"; k = n if ok else (n // 2 if code.strip() == "half" else 0)
        return runner.RunResult("OK" if ok else "WA", tests=[{"n": i + 1, "verdict": "OK" if i < k else "WA", "wall_ms": 1, "stdout": "", "expected": "", "stderr": ""} for i in range(n)])
    monkeypatch.setattr(runner, "judge", fake)
    from app.models.user import User
    with dbmod.SessionLocal() as db:
        return [u.id for u in db.scalars(select(User).order_by(User.id))]


def test_create_join_start_rules(duo):
    a, b, c = duo
    with dbmod.SessionLocal() as db:
        with pytest.raises(ValueError): arena.create(db, a, "nope")
        with pytest.raises(ValueError): arena.create(db, a, "array-sum", 2, 2)
        m = arena.create(db, a, "array-sum", 10, 2)
        with pytest.raises(PermissionError): arena.start(db, a, m.id)               # needs 2 players
        arena.join(db, b, m.code.lower()); arena.join(db, b, m.code)                # idempotent, case-insensitive
        with pytest.raises(PermissionError): arena.join(db, c, m.code)              # full
        with pytest.raises(LookupError): arena.start(db, b, m.id)                   # only the creator
        with pytest.raises(LookupError): arena.join(db, c, "ZZZZZZ")
        s = arena.state(db, a, m.id)
        assert s["status"] == "waiting" and "statement" not in s["problem"]          # problem is hidden until start
        arena.start(db, a, m.id)
        assert "statement" in arena.state(db, b, m.id)["problem"] and "tests" not in arena.state(db, b, m.id)["problem"]


def test_first_full_solve_wins_and_progress_hides_code(duo):
    a, b, c = duo; t0 = datetime.now(UTC)
    with dbmod.SessionLocal() as db:
        m = arena.create(db, a, "array-sum", 10, 3); arena.join(db, b, m.code); arena.join(db, c, m.code); arena.start(db, a, m.id, t0)
        r = arena.submit(db, b, m.id, "python", "half", t0 + timedelta(minutes=1))
        assert r["verdict"] == "WA" and 0 < r["passed"] < r["total"] and r["match_status"] == "running"
        assert arena.submit(db, c, m.id, "python", "ok", t0 + timedelta(minutes=2))["verdict"] == "ACCEPTED"
        s = arena.state(db, a, m.id, t0 + timedelta(minutes=3))
        assert s["status"] == "finished" and s["winner"] and s["result"] == "First full solve"
        assert {p["name"] for p in s["players"] if p["solved"]} and all("code" not in p for p in s["players"])
        with pytest.raises(PermissionError): arena.submit(db, b, m.id, "python", "ok", t0 + timedelta(minutes=4))  # match over


def test_timeout_picks_most_tests_passed_or_a_draw(duo):
    a, b, c = duo; t0 = datetime.now(UTC)
    with dbmod.SessionLocal() as db:
        m = arena.create(db, a, "array-sum", 5, 2); arena.join(db, b, m.code); arena.start(db, a, m.id, t0)
        arena.submit(db, a, m.id, "python", "half", t0 + timedelta(minutes=1))
        s = arena.state(db, a, m.id, t0 + timedelta(minutes=6))
        assert s["status"] == "finished" and s["winner"] is not None and "Time up" in s["result"]
        m2 = arena.create(db, a, "array-sum", 5, 2); arena.join(db, b, m2.code); arena.start(db, a, m2.id, t0)
        s2 = arena.state(db, a, m2.id, t0 + timedelta(minutes=6))
        assert s2["winner"] is None and "Draw" in s2["result"]


def test_api_flow_authz_validation_and_rate_limit(duo, client):
    login = lambda e: auth(client.post("/auth/login", json={"email": e, "password": "correct-horse-battery"}).json())
    ha, hb, hc = login("a@example.com"), login("b@example.com"), login("c@example.com")
    assert client.get("/arena/problems").status_code == 401 and len(client.get("/arena/problems", headers=ha).json()) == 8
    assert "tests" not in client.get("/arena/problems/array-sum", headers=ha).json() and client.get("/arena/problems/nope", headers=ha).status_code == 404
    m = client.post("/arena/matches", headers=ha, json={"problem_key": "array-sum", "minutes": 10}).json()
    assert client.post("/arena/matches", headers=ha, json={"problem_key": "array-sum", "minutes": 1}).status_code == 422
    assert client.post("/arena/matches/join", headers=hb, json={"code": m["code"]}).status_code == 200
    assert client.get(f"/arena/matches/{m['id']}", headers=hc).status_code == 404            # outsiders cannot peek
    assert client.post(f"/arena/matches/{m['id']}/start", headers=hb).status_code == 404      # only the creator starts
    assert client.post(f"/arena/matches/{m['id']}/start", headers=ha).json()["status"] == "running"
    assert client.post(f"/arena/matches/{m['id']}/submit", headers=hc, json={"language": "python", "code": "ok"}).status_code == 404
    assert client.post(f"/arena/matches/{m['id']}/submit", headers=hb, json={"language": "cobol", "code": "x"}).status_code == 422
    r = client.post(f"/arena/matches/{m['id']}/submit", headers=hb, json={"language": "python", "code": "ok"}).json()
    assert r["verdict"] == "ACCEPTED" and client.get("/arena/matches", headers=hb).json()[0]["winner"]
