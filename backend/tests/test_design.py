import pytest

from app.design.review import SCENARIOS, review
from tests.conftest import auth, register


def N(id, type, **kw): return {"id": id, "type": type, "label": kw.pop("label", id), **kw}
def E(a, b): return {"from": a, "to": b}
def rules(r): return {f["rule"] for f in r["findings"]}


GOOD = {"nodes": [N("c", "client"), N("lb", "load_balancer", replicas=2), N("gw", "api_gateway"), N("a", "app_server", replicas=3), N("db", "database", replicas=2, consistency="strong"),
                  N("ca", "cache", replicas=2), N("m", "monitoring")], "edges": [E("c", "lb"), E("lb", "gw"), E("gw", "a"), E("a", "ca"), E("a", "db")]}


def test_well_formed_design_has_no_high_severity_findings():
    r = review(GOOD, "url-shortener")
    assert r["counts"]["high"] == 0 and "spof" not in rules(r) and r["coverage"]["missing"] == [] and r["coverage"]["ratio"] == 1.0


def test_single_database_and_lb_are_spofs_with_severity_and_fix():
    g = {"nodes": [N("c", "client"), N("lb", "load_balancer"), N("a", "app_server", replicas=2), N("db", "database")], "edges": [E("c", "lb"), E("lb", "a"), E("a", "db")]}
    r = review(g)
    spof = [f for f in r["findings"] if f["rule"] == "spof"]
    assert {f["nodes"][0] for f in spof} == {"lb", "db"} and all(f["severity"] == "high" for f in spof) and "failover" in [f for f in spof if f["nodes"] == ["db"]][0]["suggestion"]


def test_spof_ignores_components_not_on_the_request_path():
    g = {"nodes": [N("c", "client"), N("a", "app_server", replicas=2), N("db", "database"), N("orphan", "database")], "edges": [E("c", "a")]}
    r = review(g)
    assert "spof" not in rules(r) and "unreachable" in rules(r)


def test_client_to_database_is_exposed_datastore():
    r = review({"nodes": [N("c", "client"), N("db", "database", replicas=2)], "edges": [E("c", "db")]})
    f = [x for x in r["findings"] if x["rule"] == "exposed-datastore"][0]
    assert f["severity"] == "high" and f["nodes"] == ["c", "db"]


def test_scenario_specific_rules_cache_queue_media_consistency():
    g = {"nodes": [N("c", "client"), N("lb", "load_balancer", replicas=2), N("a", "app_server", replicas=2), N("db", "database", replicas=2, kind="nosql")], "edges": [E("c", "lb"), E("lb", "a"), E("a", "db")]}
    assert "missing-cache" in rules(review(g, "url-shortener"))
    assert {"media-without-storage", "missing-queue"} <= rules(review(g, "youtube"))
    assert "consistency-mismatch" in rules(review(g, "online-judge"))
    assert "missing-cache" not in rules(review(g, "whatsapp"))  # not read-heavy


def test_replicas_without_lb_and_no_entry_tier():
    g = {"nodes": [N("c", "client"), N("a", "app_server", replicas=4)], "edges": [E("c", "a")]}
    assert {"replicas-without-lb", "no-entry-tier"} <= rules(review(g))


def test_edges_to_unknown_nodes_and_unknown_types_do_not_crash():
    r = review({"nodes": [N("c", "client"), N("x", "quantum_db")], "edges": [E("c", "x"), E("c", "ghost")]})
    assert "unknown-type" in rules(r)
    assert review({"nodes": [], "edges": []})["findings"] == []


def test_follow_up_questions_are_derived_from_findings_and_scenario():
    g = {"nodes": [N("c", "client"), N("lb", "load_balancer", replicas=2), N("a", "app_server", replicas=2), N("db", "database", label="Primary DB")], "edges": [E("c", "lb"), E("lb", "a"), E("a", "db")]}
    q = review(g, "url-shortener")["questions"]
    assert any("Primary DB" in x and "fails" in x for x in q) and any("short codes" in x for x in q) and len(q) <= 6 and len(set(q)) == len(q)
    assert all(SCENARIOS[s]["expected"] for s in SCENARIOS)


@pytest.fixture()
def env(client):
    return client, auth(register(client))


GRAPH = {"nodes": [{"id": "c", "type": "client", "label": "Browser"}, {"id": "a", "type": "app_server", "label": "API", "replicas": 2}], "edges": [{"from": "c", "to": "a"}]}


def test_api_crud_review_validation_and_isolation(env):
    c, h = env
    assert c.get("/design/scenarios", headers=h).json()["scenarios"][0]["id"]
    rv = c.post("/design/review", headers=h, json={"title": "t", "scenario": "url-shortener", "graph": GRAPH}).json()
    assert "no-entry-tier" in {f["rule"] for f in rv["findings"]}
    did = c.post("/design", headers=h, json={"title": "My URL shortener", "scenario": "url-shortener", "graph": GRAPH}).json()["id"]
    assert c.get(f"/design/{did}", headers=h).json()["graph"]["nodes"][0]["id"] == "c"
    assert c.put(f"/design/{did}", headers=h, json={"title": "v2", "graph": GRAPH}).json()["saved"]
    assert c.get("/design", headers=h).json()[0]["title"] == "v2"
    other = auth(register(c, "b@example.com"))
    assert c.get(f"/design/{did}", headers=other).status_code == 404 and c.delete(f"/design/{did}", headers=other).status_code == 404
    assert c.post("/design", headers=h, json={"title": "x", "scenario": "nope", "graph": GRAPH}).status_code == 422
    assert c.post("/design", headers=h, json={"title": "x", "graph": {"nodes": [{"id": "a", "type": "client", "replicas": 0}]}}).status_code == 422
    assert c.delete(f"/design/{did}", headers=h).status_code == 204 and c.get("/design", headers=h).json() == []
    assert c.get("/design").status_code == 401
