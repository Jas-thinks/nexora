"""Deterministic architecture reviewer. Findings are rule-based and explainable; the coverage score only measures presence of components the
scenario usually needs - it is a checklist, NOT a grade of design quality. An LLM can add narrative on top, but never replaces these rules."""
from collections import defaultdict, deque

NODE_TYPES = {"client", "cdn", "api_gateway", "load_balancer", "app_server", "auth_service", "rate_limiter", "cache", "database", "message_broker", "worker",
              "object_storage", "search_engine", "monitoring", "sandbox"}
STATEFUL = {"database", "cache", "message_broker", "search_engine", "object_storage"}
SCENARIOS = {
    "url-shortener": dict(title="Design a URL Shortener", prompt="Shorten URLs, redirect with low latency, 100M new URLs/month, 10:1 read:write.",
                          needs=dict(read_heavy=True, media=False, async_writes=False, strong_consistency=False), expected=["load_balancer", "app_server", "database", "cache"]),
    "whatsapp": dict(title="Design WhatsApp", prompt="1:1 and group chat, delivery receipts, offline delivery, 500M DAU.",
                     needs=dict(read_heavy=False, media=True, async_writes=True, strong_consistency=False, realtime=True), expected=["load_balancer", "app_server", "database", "message_broker", "object_storage", "cache"]),
    "youtube": dict(title="Design YouTube", prompt="Upload, transcode, stream video globally; recommendations out of scope.",
                    needs=dict(read_heavy=True, media=True, async_writes=True, strong_consistency=False), expected=["cdn", "object_storage", "message_broker", "worker", "database", "load_balancer", "app_server"]),
    "rate-limiter": dict(title="Design a Rate Limiter", prompt="Limit requests per user/IP across a fleet of API servers with low added latency.",
                         needs=dict(read_heavy=False, media=False, async_writes=False, strong_consistency=False), expected=["api_gateway", "rate_limiter", "cache"]),
    "distributed-cache": dict(title="Design a Distributed Cache", prompt="Key-value cache with replication, eviction, and consistent hashing.",
                              needs=dict(read_heavy=True, media=False, async_writes=False, strong_consistency=False), expected=["load_balancer", "cache", "monitoring"]),
    "online-judge": dict(title="Design an Online Judge", prompt="Accept code submissions, run them safely, rank contestants live.",
                         needs=dict(read_heavy=False, media=False, async_writes=True, strong_consistency=True), expected=["load_balancer", "app_server", "message_broker", "sandbox", "database", "cache"]),
}


def _validate(graph: dict) -> tuple[dict, list]:
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    edges = [(e["from"], e["to"]) for e in graph.get("edges", []) if e.get("from") in nodes and e.get("to") in nodes]
    return nodes, edges


TRIGGERS = {
    "read_heavy": ("read", "feed", "redirect", "browse", "timeline", "catalog", "catalogue", "lookup", "view", "stream", "serve", "autocomplete", "recommend"),
    "media": ("video", "image", "photo", "file", "upload", "music", "audio", "media", "document", "attachment"),
    "async_writes": ("transcod", "notification", "email", "sms", "fan-out", "fanout", "queue", "batch", "pipeline", "analytics", "process", "judge", "schedule", "job", "order"),
    "strong_consistency": ("payment", "money", "wallet", "booking", "inventory", "ledger", "transaction", "seat", "bank", "balance", "ticket", "oversell", "double book"),
    "realtime": ("chat", "live", "real-time", "realtime", "message", "collaborat", "presence", "tracking", "location", "multiplayer", "leaderboard"),
    "search": ("search", "autocomplete", "typeahead", "index", "crawl", "full-text"),
    "api_edge": ("api", "rate limit", "throttl", "gateway", "public"),
}


def infer_needs(text: str) -> dict:
    """Open-ended questions have no template, so infer what the design likely needs from the words of the prompt. Heuristic, shown to the
    student with the triggering words so they can disagree; it only drives the checklist and a few rules, never a score."""
    t = (text or "").lower()
    needs, why = {}, {}
    for k, words in TRIGGERS.items():
        hit = [w for w in words if w in t]
        if hit:
            needs[k] = True; why[k] = hit[:3]
    exp = ["load_balancer", "app_server", "database"]
    if needs.get("read_heavy"): exp.append("cache")
    if needs.get("media"): exp += ["object_storage", "cdn"]
    if needs.get("async_writes"): exp += ["message_broker", "worker"]
    if needs.get("search"): exp.append("search_engine")
    if needs.get("api_edge"): exp += ["api_gateway", "rate_limiter"]
    exp.append("monitoring")
    return {"needs": needs, "expected": list(dict.fromkeys(exp)), "why": why}


DOC_SECTIONS = [
    ("requirements", "Requirements & scope", "Functional + non-functional requirements, what is out of scope."),
    ("estimation", "Capacity estimation", "QPS, storage, bandwidth with your assumptions."),
    ("api", "API design", "The few endpoints that carry the core flows."),
    ("data_model", "Data model", "Entities, keys, indexes and the choice of database."),
    ("deep_dives", "Deep dives", "The 2-3 hardest components and how they work."),
    ("tradeoffs", "Bottlenecks & trade-offs", "What breaks first, failure modes, what you gave up."),
]


def doc_checklist(doc: dict | None) -> dict:
    """Process checklist for the written HLD. Presence and size only: it says nothing about quality (the mentor judges that)."""
    doc = doc or {}
    items = []
    for key, label, hint in DOC_SECTIONS:
        txt = str(doc.get(key) or "")
        words = len(txt.split())
        items.append({"key": key, "label": label, "hint": hint, "words": words, "done": words >= 12, "has_numbers": any(ch.isdigit() for ch in txt) if key == "estimation" else None})
    done = sum(i["done"] for i in items)
    return {"items": items, "ratio": round(done / len(items), 2), "note": "Counts sections with at least a few sentences. It does not judge the content."}


def review(graph: dict, scenario: str | None = None, prompt: str = "", doc: dict | None = None) -> dict:
    nodes, edges = _validate(graph)
    sc = SCENARIOS.get(scenario or "")
    inferred = None if sc else infer_needs(prompt + " " + str((doc or {}).get("requirements", ""))[:600])
    needs = sc["needs"] if sc else inferred["needs"]
    expected = sc["expected"] if sc else inferred["expected"]
    by_type: dict[str, list[str]] = defaultdict(list)
    for nid, n in nodes.items():
        by_type[n.get("type")].append(nid)
    adj: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
    f: list[dict] = []

    def add(rule, sev, nds, msg, fix):
        f.append({"rule": rule, "severity": sev, "nodes": nds, "message": msg, "suggestion": fix})

    for nid, n in nodes.items():
        if n.get("type") not in NODE_TYPES:
            add("unknown-type", "low", [nid], f"'{n.get('label', nid)}' has an unknown component type '{n.get('type')}'.", "Use one of the supported component types.")
    if not nodes:
        return {"findings": [], "coverage": None, "note": "Add components to get a review.", "questions": [], "doc": doc_checklist(doc), "inferred": inferred}
    clients = by_type["client"]
    reach: set[str] = set()
    q = deque(clients)
    while q:
        x = q.popleft()
        if x in reach: continue
        reach.add(x); q.extend(adj[x])
    # --- critical rules
    for a, b in edges:
        if nodes[a].get("type") == "client" and nodes[b].get("type") in ("database", "cache", "message_broker"):
            add("exposed-datastore", "high", [a, b], f"The client talks directly to '{nodes[b].get('label', b)}' ({nodes[b]['type']}).",
                "Put an application tier (behind a gateway/load balancer) between clients and data stores: auth, validation and rate limiting live there.")
    for nid in by_type["app_server"] + by_type["database"] + by_type["load_balancer"] + by_type["cache"] + by_type["message_broker"]:
        if nid in reach and int(nodes[nid].get("replicas", 1) or 1) < 2:
            t = nodes[nid]["type"]
            add("spof", "high" if t in ("database", "load_balancer") else "medium", [nid], f"'{nodes[nid].get('label', nid)}' ({t}) is on the request path with a single replica: a single point of failure.",
                {"database": "Add a replica/standby with automatic failover (and decide sync vs async replication).", "load_balancer": "Run an active-passive or active-active pair (or a managed LB).",
                 "app_server": "Run 2+ stateless instances.", "cache": "Replicate or shard the cache and make the app tolerate cache loss.", "message_broker": "Use a replicated/clustered broker."}[t])
    apps = by_type["app_server"]
    if apps and not by_type["load_balancer"] and not by_type["api_gateway"]:
        add("no-entry-tier", "medium", apps, "App servers are exposed without a load balancer or API gateway.", "Add a load balancer (health checks, distribution) or API gateway in front.")
    if sum(int(nodes[a].get("replicas", 1) or 1) for a in apps) > 1 and not by_type["load_balancer"] and not by_type["api_gateway"]:
        add("replicas-without-lb", "high", apps, "Multiple app instances exist but nothing distributes traffic to them.", "Add a load balancer.")
    dbs = by_type["database"]
    if dbs and needs.get("read_heavy") and not by_type["cache"]:
        add("missing-cache", "medium", dbs, "The workload is read-heavy but there is no cache in front of the database.", "Add a cache (cache-aside with TTL) for hot reads; plan invalidation.")
    if needs.get("media") and not (by_type["object_storage"] or by_type["cdn"]):
        add("media-without-storage", "high", [], "The scenario serves large media but there is no object storage/CDN.", "Store blobs in object storage and serve through a CDN; keep metadata in the database.")
    if needs.get("search") and not by_type["search_engine"]:
        add("missing-search", "medium", dbs, "The question involves search but there is no search index/engine: scanning the primary database will not scale.", "Add a search index (inverted index / Elasticsearch-style) fed from the database through a queue or change stream.")
    if needs.get("async_writes") and not by_type["message_broker"]:
        add("missing-queue", "medium", apps, "Heavy or slow write paths are handled synchronously: no message broker/queue.", "Queue the slow work (transcoding, fan-out, judging) and process it with workers; add retries and a dead-letter queue.")
    if needs.get("strong_consistency"):
        for d in dbs:
            if str(nodes[d].get("consistency", "")).lower() == "eventual" or str(nodes[d].get("kind", "")).lower() == "nosql" and not nodes[d].get("consistency"):
                add("consistency-mismatch", "medium", [d], f"The scenario needs strong consistency but '{nodes[d].get('label', d)}' is eventual/unspecified NoSQL.", "Use a relational/strongly-consistent store for the source of truth or state the consistency model explicitly.")
    if apps and clients and not (by_type["auth_service"] or by_type["api_gateway"]):
        add("no-auth-layer", "medium", apps, "No authentication/authorization component is shown on the path from clients.", "Add an auth service or an API gateway that enforces authN/Z.")
    if (by_type["api_gateway"] or apps) and clients and not by_type["rate_limiter"] and not by_type["api_gateway"]:
        add("no-rate-limit", "low", apps, "No rate limiting is shown for a public API.", "Rate-limit at the gateway (token bucket per user/IP).")
    if not by_type["monitoring"]:
        add("no-observability", "low", [], "No monitoring/observability component: you cannot detect or debug failures.", "Add metrics, logs and tracing with alerts on SLOs.")
    for nid in nodes:
        if nid not in reach and nodes[nid].get("type") != "client" and clients:
            add("unreachable", "low", [nid], f"'{nodes[nid].get('label', nid)}' is not reachable from any client.", "Connect it to the request path or remove it.")
    if not clients:
        add("no-client", "low", [], "There is no client node, so request flow cannot be checked.", "Add a client.")
    sev = {"high": 0, "medium": 1, "low": 2}
    f.sort(key=lambda x: (sev[x["severity"]], x["rule"]))
    have = [t for t in expected if by_type.get(t)]
    cov = {"present": have, "missing": [t for t in expected if t not in have], "ratio": round(len(have) / len(expected), 2),
           "note": "Checklist of components this kind of system usually needs" + (" (inferred from your prompt, so it may be wrong for unusual designs)." if inferred else ".") + " Not a quality score."}
    return {"findings": f, "coverage": cov, "counts": {s: sum(1 for x in f if x["severity"] == s) for s in ("high", "medium", "low")}, "questions": follow_ups(f, scenario, nodes),
            "doc": doc_checklist(doc), "inferred": inferred}


def follow_ups(findings: list[dict], scenario: str | None, nodes: dict) -> list[str]:
    qs = []
    rules = {x["rule"] for x in findings}
    nm = lambda ids: ", ".join(nodes[i].get("label", i) for i in ids[:2] if i in nodes)
    for x in findings:
        if x["rule"] == "spof":
            qs.append(f"What happens to users when {nm(x['nodes'])} fails? How quickly do you recover and what is lost?")
        elif x["rule"] == "missing-cache":
            qs.append("Your reads hit the database directly. At 10x traffic, what breaks first and how would a cache change that? How do you invalidate it?")
        elif x["rule"] == "missing-queue":
            qs.append("Which operations can be made asynchronous, and what delivery guarantee (at-least-once vs exactly-once) do you need?")
        elif x["rule"] == "exposed-datastore":
            qs.append("Why can the client reach the data store directly? Walk me through authentication and abuse prevention.")
        elif x["rule"] == "consistency-mismatch":
            qs.append("Which operations need strong consistency here, and what do you give up to get it (CAP / latency)?")
    base = {"url-shortener": ["How do you generate unique short codes without collisions at scale?", "How would you shard the mapping table?"],
            "whatsapp": ["How do you deliver messages to offline users and guarantee ordering?", "How do group messages fan out?"],
            "youtube": ["How is a video transcoded and when is it considered available?", "How do you keep CDN cost under control?"],
            "rate-limiter": ["Token bucket vs sliding window: trade-offs? Where does the counter live?", "How do you stay accurate across multiple regions?"],
            "distributed-cache": ["How does consistent hashing handle node joins/leaves?", "What eviction policy and why?"],
            "online-judge": ["How do you isolate untrusted code and enforce limits?", "How do you keep the live ranking consistent under load?"]}
    qs += base.get(scenario or "", ["What are the main bottlenecks in your design, and how would you measure them?"])
    if not rules:
        qs.insert(0, "Your diagram has no rule violations. Which failure scenario worries you most, and what would you monitor?")
    seen, out = set(), []
    for q in qs:
        if q not in seen: seen.add(q); out.append(q)
    return out[:6]
