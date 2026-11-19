"""First-party system-design teaching notes (written for Nexora). Authored, NOT yet human-reviewed; short retrieval material for the mentor.
Front-loaded: the mentor sees only the first ~800 characters of each."""
def _n(slug, title, text):
    return dict(key=f"note:sd-{slug}", title=title, patterns=[], text=text)

DESIGN_NOTES = [
 _n("estimation", "Back-of-envelope capacity estimation (QPS, storage, bandwidth)",
    """Start every design with numbers. DAU x actions/user/day / 86,400 = average QPS; peak is usually 2-10x average. Storage = items/day x bytes/item x retention. Bandwidth = QPS x payload size.
Useful constants: 1 day = 86,400 s (~1e5); 1M req/day ~ 12 QPS; 1 KB x 1e9 = 1 TB. Read:write ratio decides caching vs write scaling.
Example: 100M new URLs/month = ~40 writes/s; at 10:1 reads = ~400 reads/s average; 500 bytes each x 12 months x 5 years = ~3 TB.
Use the result to choose: one DB node handles roughly a few thousand simple QPS; above that think replicas, cache, sharding. State assumptions out loud. Mistake: skipping estimation and drawing 20 boxes with no reason for any of them."""),
 _n("requirements", "Requirements first: functional, non-functional, scope",
    """Open every system-design answer by clarifying: (1) functional requirements - the 3-5 core user actions in scope; (2) non-functional - scale (users, QPS), latency targets, availability vs consistency, durability, geography; (3) out of scope - say what you will not design.
Turn vague goals into numbers: 'fast' = p99 < 200 ms; 'highly available' = 99.99% (about 52 minutes of downtime a year).
Then follow a fixed flow: requirements -> estimation -> API -> data model -> high-level architecture -> deep dives on the hardest 2 parts -> bottlenecks, failure modes, trade-offs. Interviewers mark structure and trade-off reasoning more than box count."""),
 _n("api-design", "API design for system design interviews",
    """Define the few endpoints that carry the core flows, with method, path, parameters and result. Prefer resource-oriented REST (POST /v1/urls, GET /v1/urls/{code}) or gRPC between internal services.
Decide: authentication (token in header), pagination (cursor-based beats offset at scale because offsets rescan), idempotency for writes that can be retried (client-supplied Idempotency-Key), rate limits, and versioning.
Return codes matter: 301 vs 302 for redirects changes caching behaviour. Keep payloads small; for large uploads return a pre-signed URL to object storage instead of proxying bytes through your servers."""),
 _n("load-balancing", "Load balancing: L4 vs L7, algorithms, health checks",
    """A load balancer spreads requests over healthy servers and removes failed ones using health checks. L4 (TCP) is fast and protocol-agnostic; L7 (HTTP) can route by path/header, terminate TLS and do sticky sessions.
Algorithms: round robin (simple), least connections (uneven request cost), consistent hashing (keep a key on the same server, e.g. caches). Keep app servers stateless so any instance can serve any request; store sessions in a shared store.
The load balancer is itself a single point of failure: run a pair (active-passive or active-active) or use a managed one. At global scale add DNS/anycast routing to the nearest region."""),
 _n("caching", "Caching strategies: cache-aside, write-through, write-back, invalidation",
    """Cache-aside: read cache, on miss read DB and populate; writes go to the DB and invalidate/update the cache. Simple and resilient (cache loss is only a slowdown). Write-through: write cache and DB together, consistent but slower writes. Write-back: write cache, flush later - fast but data loss risk.
Always set TTLs and an eviction policy (LRU is the default). Hard parts: invalidation (stale data), cache stampede when a hot key expires (use request coalescing/locking or jittered TTLs), hot keys (replicate or local-cache them), cold start (warm up).
Cache what is read-heavy and tolerant of staleness. Place caches at CDN, application (Redis/Memcached) and client levels."""),
 _n("sharding", "Database sharding and partitioning",
    """Sharding splits data across nodes when one node cannot hold the data or write load. Choose a shard key that spreads load evenly AND matches the main query (e.g. user_id). Range sharding is simple but creates hotspots; hash sharding spreads evenly but makes range scans hard; directory-based lookup is flexible but adds a lookup hop.
Costs: cross-shard joins/transactions are hard, resharding is painful (use consistent hashing or many small virtual shards to move less data), hot keys still exist (celebrity user).
Before sharding, exhaust: indexes, caching, read replicas, archiving. Say why you need it (write throughput or data size), not just 'for scale'."""),
 _n("replication", "Replication, failover and read replicas",
    """Replication copies data to other nodes for availability and read scaling. Leader-follower: writes go to the leader, followers serve reads; followers lag (replication lag), so a user may not read their own write - fix with read-your-writes (route that user to the leader briefly).
Synchronous replication loses no data on failover but adds latency and blocks if a replica is down; asynchronous is fast but may lose the last writes. Failover needs failure detection, leader election and fencing to avoid split brain.
Multi-leader and leaderless (quorum, R + W > N) designs trade consistency complexity for write availability across regions."""),
 _n("cap-consistency", "CAP theorem, consistency models and when to pick what",
    """During a network partition you must choose: consistency (reject/stall some requests) or availability (serve possibly stale data). It is a choice only during partitions; otherwise latency vs consistency is the everyday trade-off (PACELC).
Strong consistency: money, inventory, seat booking, unique usernames. Eventual consistency: feeds, likes, view counts, search indexes. Intermediate: read-your-writes, monotonic reads, causal consistency.
Name the consistency model per data type in your design instead of one global answer; use transactions or a single leader for the invariants that must never break."""),
 _n("consistent-hashing", "Consistent hashing",
    """Map both keys and nodes onto a hash ring; a key belongs to the first node clockwise. Adding/removing a node moves only ~1/N of the keys, unlike hash(key) mod N which remaps almost everything.
Use virtual nodes (each physical node appears many times on the ring) to even out load and let stronger machines take more. Replicate to the next R nodes on the ring for fault tolerance. Used by distributed caches, key-value stores (Dynamo-style) and load balancing for stateful backends."""),
 _n("message-queues", "Message queues, delivery guarantees and idempotent consumers",
    """Queues decouple producers from consumers, absorb spikes and let slow work run asynchronously (email, transcoding, fan-out). Delivery: at-most-once (may lose), at-least-once (may duplicate; the common default), exactly-once effects = at-least-once delivery + idempotent processing (dedupe key).
Kafka-style logs: partitioned, ordered within a partition, consumer groups, retention and replay. Queue brokers (SQS/RabbitMQ): per-message ack, visibility timeout, dead-letter queue for poison messages.
Design for retries with backoff, a DLQ, back-pressure, and monitor queue depth/age as your key health signal."""),
 _n("cdn", "CDN and edge caching",
    """A CDN caches static and video content on edge servers near users, cutting latency and origin load. Pull CDN fetches from origin on first miss; push CDN is pre-populated. Control freshness with Cache-Control/TTL and versioned URLs (asset.v123.js) so you rarely need purges.
Use for images, video segments, JS/CSS, downloads. Protect the origin with an origin shield tier. Dynamic personalised responses are usually not cacheable at the edge. Cost grows with egress, so tier hot vs cold content."""),
 _n("rate-limiting", "Rate limiting algorithms",
    """Token bucket: a bucket refills at a fixed rate up to a burst capacity; each request takes a token - allows bursts, most common. Leaky bucket: smooths output. Fixed window counter: simple but allows 2x bursts at window edges. Sliding window log/counter: accurate, costs more memory.
Distributed: keep counters in Redis with atomic INCR/Lua per key (user, IP, API key); decide fail-open vs fail-closed if the store is down (usually fail-open with local limits). Return 429 with Retry-After. Enforce at the API gateway, and rate-limit by identity, not just IP."""),
 _n("id-generation", "Unique ID generation (auto-increment, UUID, Snowflake)",
    """Auto-increment is simple but a single-node bottleneck and leaks counts. UUIDv4 needs no coordination but is 128-bit and random (bad index locality). Snowflake-style 64-bit IDs = timestamp + machine id + sequence: roughly time-ordered, sortable, generated locally at high rate; watch clock skew/backwards clocks.
For short codes (URL shortener): counter or range allocation per server + base62 encoding, or hash and resolve collisions; random codes need a uniqueness check."""),
 _n("fanout-feed", "News feed fan-out: push vs pull vs hybrid",
    """Fan-out on write (push): when a user posts, copy the post id into every follower's feed cache - fast reads, slow/expensive writes, bad for users with millions of followers. Fan-out on read (pull): build the feed at read time by merging followees' recent posts - cheap writes, slow reads.
Hybrid: push for normal users, pull for celebrities and merge at read time. Store only post ids in feed lists (e.g. Redis sorted sets), hydrate content from a post cache. Add ranking as a separate stage. Handle inactive users by not precomputing their feeds."""),
 _n("search-indexing", "Search: inverted index, sharding and ranking",
    """An inverted index maps each term to the list of documents containing it; queries intersect/merge posting lists and rank (TF-IDF/BM25 plus signals). Shard by document (each shard has a full index of its docs; query all shards and merge) so writes stay local; replicate for availability.
Updates: near-real-time via a write buffer and periodic segment merges (Lucene/Elasticsearch). Keep the database as the source of truth and feed the index through a change stream/queue. Autocomplete uses tries or prefix indexes with precomputed top suggestions."""),
 _n("object-storage", "Object storage for blobs (images, video, files)",
    """Store large binaries in object storage (S3-like) and keep only metadata (owner, key, size, status) in the database. Upload via pre-signed URLs straight from the client; process asynchronously (thumbnails, transcoding) through a queue and workers; serve through a CDN.
Large files: chunked/multipart upload with resume; dedupe by content hash; lifecycle rules to cheaper tiers. Durability comes from replication or erasure coding across zones. Never store blobs in the relational DB at scale."""),
 _n("websockets-realtime", "Real-time delivery: WebSocket, SSE, long polling",
    """Polling is simple but wasteful; long polling holds the request open; SSE is one-way server push over HTTP; WebSocket is a persistent two-way channel (chat, collaboration, live games).
Scaling WebSockets: connections are stateful, so keep a registry (user -> gateway server) in a fast store, or broadcast through pub/sub (Redis/Kafka) so any server can deliver to the right socket. Handle reconnect with last-seen message id, heartbeats, and offline users via a persistent queue plus push notifications."""),
 _n("geospatial", "Geospatial indexing: geohash, quadtree, S2",
    """To find 'things near me' avoid scanning all points. Geohash converts lat/lng to a string whose shared prefix means nearby (query the cell and its 8 neighbours); quadtree recursively splits dense regions; S2/H3 use hierarchical cells. Index drivers/places by cell and update on movement.
Hot cities need finer cells or sharding by region. For moving objects (drivers) keep positions in memory/Redis with TTL rather than writing every ping to a disk database."""),
 _n("availability-spof", "Availability, single points of failure and failure handling",
    """Availability = uptime fraction; 99.9% is ~8.8 h/year, 99.99% ~52 min. Remove single points of failure with redundancy at every tier (multiple LB, app instances, replicated DB, multi-AZ), and decide how each component fails: retries with exponential backoff and jitter, timeouts, circuit breakers, bulkheads, graceful degradation (serve stale/cached data).
Use health checks and automatic failover; test failure (chaos). Define SLIs/SLOs and alert on user-visible symptoms (error rate, latency), not just CPU."""),
 _n("db-choice", "Choosing a database: SQL vs NoSQL",
    """Relational (Postgres/MySQL): transactions, joins, constraints - default choice when you need correctness and the data fits one primary with replicas. Key-value/wide-column (DynamoDB, Cassandra): predictable low latency and horizontal scale for known access patterns, weak ad-hoc querying. Document: flexible schema. Graph: relationship traversals. Time-series: metrics. Search: Elasticsearch/OpenSearch.
Choose from access patterns and consistency needs, not fashion. It is normal to use several (polyglot persistence) with one source of truth. Say what you give up."""),
 _n("idempotency-payments", "Idempotency, transactions and payments correctness",
    """Retries are inevitable, so writes must be idempotent: the client sends an Idempotency-Key; the server stores key -> result and returns it on repeats. For money use a double-entry ledger (every transfer = debit + credit, append-only), strong consistency/transactions on the ledger, and reconciliation jobs against external systems.
Multi-service workflows: sagas with compensating actions rather than distributed two-phase commit. Use a state machine for orders/payments (created -> authorised -> captured -> settled) so every transition is explicit and auditable."""),
 _n("hot-keys-celebrity", "Hot keys and thundering herds",
    """A few keys receive disproportionate traffic (celebrity profile, viral post, flash-sale item). Mitigate: cache aggressively with local in-process caches, replicate hot keys across cache nodes, split a counter into N sub-counters and sum on read, add a random suffix to spread writes, coalesce identical concurrent requests, and use queues or reservation tokens for scarce inventory.
Detect hot keys with sampling and shed load (rate limit/queue) before they take the cluster down."""),
 _n("observability", "Observability: metrics, logs, traces and SLOs",
    """Metrics (counters, gauges, histograms) show trends and drive alerts; logs give detail; distributed traces follow one request across services. Track the golden signals: latency, traffic, errors, saturation. Define SLOs (e.g. 99.9% of requests < 300 ms) and alert on error-budget burn.
Add correlation/request ids everywhere, structured logs, dashboards per service, and runbooks. Mention it in a design: without it you cannot know the system is failing."""),
 _n("lld-principles", "Low-level design: classes, SOLID and common patterns",
    """Approach: clarify requirements, list entities and relationships, define responsibilities (single responsibility), then interfaces and key methods, then handle concurrency and extensibility. Prefer composition; program to interfaces.
Patterns that recur: Strategy (pluggable pricing/eviction/matching), State (vending machine, elevator, order lifecycle), Observer (notifications), Factory (create vehicles/pieces), Singleton (use sparingly), Decorator, Chain of Responsibility (logging, validation).
Show a clean class diagram, the main flow in code or pseudocode, and where locks or atomic operations protect shared state."""),
]
