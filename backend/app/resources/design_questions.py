"""System-design question library. Titles name widely known interview topics; every prompt below is written for Nexora.
`level` is our judgement of the usual seniority at which the question is asked; `domains` is an editorial relevance hint, NOT reported interview data."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.resources import DesignQuestion

# slug, title, level, category, kind, concepts, domains, prompt
Q = [
 ("url-shortener", "Design a URL shortener", "entry", "classic", "hld", ["id generation", "caching", "read-heavy", "sharding"], ["social", "search"], "Create short links that redirect quickly. Assume 100M new links a month, 10:1 read to write, links may expire, and optional custom aliases."),
 ("pastebin", "Design Pastebin", "entry", "storage", "hld", ["object storage", "ttl expiry", "caching", "abuse"], ["collab"], "Let users paste text and share a link. Support expiry, syntax highlighting metadata and very large pastes."),
 ("rate-limiter", "Design a rate limiter", "entry", "infra", "hld", ["token bucket", "sliding window", "distributed counters"], ["payments", "cloud"], "Limit requests per user/IP/API key across a fleet of API servers with minimal added latency and graceful behaviour when the limiter store fails."),
 ("key-value-store", "Design a distributed key-value store", "senior", "storage", "hld", ["consistent hashing", "replication", "quorum", "compaction"], ["cloud", "storage"], "Build a highly available key-value store with tunable consistency, partitioning, replication and failure recovery."),
 ("distributed-cache", "Design a distributed cache", "mid", "infra", "hld", ["consistent hashing", "eviction", "cache stampede", "replication"], ["ecommerce", "cloud"], "A cache cluster in front of databases: eviction, hot keys, invalidation and behaviour when nodes join or leave."),
 ("unique-id-generator", "Design a unique ID generator", "mid", "infra", "hld", ["snowflake ids", "clock skew", "ordering"], ["social", "payments"], "Generate globally unique, roughly time-ordered 64-bit IDs at 100k/s across data centres without a single bottleneck."),
 ("web-crawler", "Design a web crawler", "mid", "search", "hld", ["frontier queue", "politeness", "dedup", "bloom filter"], ["search"], "Crawl billions of pages respectfully, avoid duplicates and traps, and keep content fresh."),
 ("search-autocomplete", "Design search autocomplete", "mid", "search", "hld", ["trie", "ranking", "caching", "offline aggregation"], ["search", "ecommerce"], "Suggest the top completions as the user types, with sub-100ms latency and trending updates."),
 ("search-engine", "Design a search engine", "senior", "search", "hld", ["inverted index", "sharding", "ranking", "freshness"], ["search"], "Index a large corpus and answer keyword queries with ranked results. Cover index build, serving and updates."),
 ("typeahead-nearby", "Design nearby places search", "mid", "search", "hld", ["geohash", "quadtree", "read-heavy"], ["mobility", "delivery"], "Find places within a radius of a location. Cover indexing, updates when places change and hot regions."),
 ("whatsapp", "Design a chat app (WhatsApp)", "mid", "messaging", "hld", ["websocket", "delivery receipts", "offline delivery", "fan-out"], ["social"], "1:1 and group messaging, delivery/read receipts, offline delivery, media, 500M daily users."),
 ("slack", "Design a team chat (Slack)", "senior", "messaging", "hld", ["channels", "presence", "search", "websocket scaling"], ["collab"], "Workspaces, channels, threads, presence, search and notifications for large organisations."),
 ("notification-system", "Design a notification system", "mid", "messaging", "hld", ["queues", "retries", "idempotency", "user preferences"], ["ecommerce", "payments"], "Send push, SMS and email at scale with user preferences, rate limits, retries and no duplicates."),
 ("email-service", "Design an email service", "senior", "messaging", "hld", ["smtp", "storage", "spam", "search"], ["cloud"], "Receive, store, search and send email for millions of mailboxes with spam filtering."),
 ("news-feed", "Design a news feed (Facebook/Twitter)", "mid", "social", "hld", ["fan-out on write/read", "ranking", "caching", "celebrity problem"], ["social"], "Show each user a timeline of posts from people they follow, fast, handling accounts with millions of followers."),
 ("twitter", "Design Twitter", "mid", "social", "hld", ["timeline", "fan-out", "search", "trending"], ["social"], "Post, follow, timeline, search and trending topics at global scale."),
 ("instagram", "Design Instagram", "mid", "social", "hld", ["object storage", "cdn", "feed", "image pipeline"], ["social"], "Photo sharing with feed, follow graph, likes/comments and image processing."),
 ("social-graph", "Design a social graph / friend suggestions", "senior", "social", "hld", ["graph storage", "bfs limits", "offline compute"], ["social"], "Store follow/friend relations and compute mutual friends and suggestions."),
 ("likes-counter", "Design a likes/views counter", "mid", "social", "hld", ["write-heavy counters", "sharded counters", "approximation"], ["social", "streaming"], "Count likes and views for hot posts that receive 100k updates per second."),
 ("youtube", "Design YouTube / video streaming", "mid", "streaming", "hld", ["transcoding", "cdn", "adaptive bitrate", "object storage"], ["streaming"], "Upload, transcode and stream video globally with adaptive quality and cost control."),
 ("netflix", "Design Netflix", "senior", "streaming", "hld", ["cdn placement", "recommendations", "licensing regions", "resilience"], ["streaming"], "Global streaming service: catalogue, playback, regional rights and extreme resilience."),
 ("spotify", "Design a music streaming service", "mid", "streaming", "hld", ["audio streaming", "playlists", "offline sync", "recommendations"], ["streaming"], "Search, stream and download music, manage playlists and sync across devices."),
 ("live-streaming", "Design live video streaming", "senior", "streaming", "hld", ["ingest", "low latency", "chat fan-out", "cdn"], ["streaming", "social"], "Streamers broadcast to millions of viewers with live chat and a few seconds of latency."),
 ("video-conferencing", "Design video conferencing (Zoom)", "senior", "realtime", "hld", ["webrtc", "sfu vs mcu", "bandwidth adaptation", "signalling"], ["collab"], "Multi-party calls with screen sharing, recording and varying network quality."),
 ("uber", "Design a ride-hailing app (Uber)", "mid", "marketplace", "hld", ["geospatial index", "matching", "location updates", "surge pricing"], ["mobility"], "Match riders with nearby drivers in real time, track trips and compute fares."),
 ("food-delivery", "Design food delivery (Swiggy/Zomato)", "mid", "marketplace", "hld", ["order state machine", "dispatch", "eta", "search"], ["delivery"], "Browse restaurants, place orders, assign delivery partners and track orders live."),
 ("ecommerce", "Design an e-commerce platform (Amazon)", "senior", "marketplace", "hld", ["catalogue", "cart", "inventory consistency", "checkout", "search"], ["ecommerce"], "Catalogue, search, cart, checkout and order management with flash-sale spikes."),
 ("flash-sale", "Design a flash-sale / ticket booking system", "senior", "marketplace", "hld", ["inventory locking", "queueing", "idempotency", "overselling"], ["ecommerce", "streaming"], "Sell limited stock to a huge simultaneous crowd without overselling and without melting the database."),
 ("hotel-booking", "Design a hotel booking system", "mid", "marketplace", "hld", ["double booking", "availability search", "transactions"], ["mobility"], "Search availability and book rooms, preventing double booking under concurrency."),
 ("movie-booking", "Design BookMyShow (seat booking)", "mid", "marketplace", "hld", ["seat locking", "timeouts", "payments", "consistency"], ["streaming"], "Show listings and let users select and pay for seats with temporary holds."),
 ("payment-system", "Design a payment system", "senior", "payments", "hld", ["idempotency", "ledger", "reconciliation", "exactly-once effects"], ["payments"], "Process payments reliably: no double charge, auditable ledger, retries and reconciliation with banks."),
 ("digital-wallet", "Design a digital wallet (Paytm/PhonePe)", "senior", "payments", "hld", ["double-entry ledger", "transactions", "fraud checks"], ["payments"], "Store balances, transfer money between users and merchants, and detect fraud."),
 ("stock-exchange", "Design a stock trading platform", "senior", "payments", "hld", ["order book", "matching engine", "low latency", "fairness"], ["payments"], "Accept orders, match them with price-time priority, publish market data and keep a consistent audit trail."),
 ("google-drive", "Design Dropbox / Google Drive", "mid", "storage", "hld", ["chunking", "sync", "dedup", "conflict resolution"], ["storage", "collab"], "File storage and sync across devices with sharing, versioning and large files."),
 ("google-docs", "Design Google Docs (collaborative editing)", "senior", "realtime", "hld", ["operational transform / crdt", "websocket", "versioning"], ["collab"], "Many users edit one document in real time with conflict-free merging and history."),
 ("object-storage", "Design an object store (S3)", "senior", "storage", "hld", ["erasure coding", "metadata service", "durability", "multipart upload"], ["cloud", "storage"], "Store trillions of objects with 11 nines of durability, versioning and lifecycle rules."),
 ("distributed-file-system", "Design a distributed file system (GFS/HDFS)", "senior", "storage", "hld", ["chunk servers", "master metadata", "replication", "failure"], ["cloud"], "Store huge files across commodity machines tolerating constant failures."),
 ("distributed-queue", "Design a message queue (Kafka/SQS)", "senior", "infra", "hld", ["partitions", "ordering", "consumer groups", "delivery semantics"], ["cloud"], "A durable, scalable message broker with ordering guarantees, consumer groups and retention."),
 ("job-scheduler", "Design a distributed job scheduler", "mid", "infra", "hld", ["leases", "retries", "cron", "idempotency"], ["cloud"], "Run millions of scheduled and ad-hoc jobs reliably exactly when due, surviving worker crashes."),
 ("api-gateway", "Design an API gateway", "mid", "infra", "hld", ["routing", "auth", "rate limiting", "observability"], ["cloud", "payments"], "A single entry point for many services with authentication, throttling and tracing."),
 ("load-balancer", "Design a load balancer", "mid", "infra", "hld", ["algorithms", "health checks", "l4 vs l7", "ha"], ["cloud"], "Distribute traffic across servers with health checks, sticky sessions and its own high availability."),
 ("cdn", "Design a CDN", "senior", "infra", "hld", ["edge caching", "cache invalidation", "anycast/dns routing", "origin shield"], ["streaming", "cloud"], "Serve static and video content from edge locations worldwide with fast invalidation."),
 ("metrics-monitoring", "Design a metrics & monitoring system", "senior", "data", "hld", ["time-series db", "aggregation", "alerting", "cardinality"], ["cloud"], "Collect metrics from thousands of hosts, store time series, dashboards and alerts."),
 ("log-aggregation", "Design a distributed logging system", "mid", "data", "hld", ["agents", "ingest pipeline", "indexing", "retention"], ["cloud"], "Collect logs from every service, search them quickly and control cost with retention tiers."),
 ("analytics-pipeline", "Design a clickstream analytics pipeline", "senior", "data", "hld", ["lambda/kappa", "stream processing", "exactly-once", "olap"], ["ecommerce", "social"], "Ingest billions of events a day and answer dashboard queries within seconds."),
 ("top-k", "Design a 'top K' trending service", "mid", "data", "hld", ["count-min sketch", "sliding windows", "stream processing"], ["social", "streaming"], "Show the top K trending items in the last hour across a very high-volume event stream."),
 ("ad-click-aggregation", "Design ad click aggregation", "senior", "data", "hld", ["dedup", "late events", "windowing", "billing accuracy"], ["social", "search"], "Aggregate ad clicks accurately for billing and reporting despite duplicates and late data."),
 ("recommendation-system", "Design a recommendation system", "senior", "data", "hld", ["candidate generation", "ranking", "feature store", "cold start"], ["ecommerce", "streaming", "social"], "Serve personalised recommendations with low latency, and refresh models from fresh behaviour."),
 ("feature-flags", "Design a feature-flag service", "mid", "infra", "hld", ["config propagation", "sdk caching", "targeting rules"], ["cloud", "collab"], "Toggle features per user/segment instantly with no added latency and safe defaults when the service is down."),
 ("online-judge", "Design an online judge (LeetCode)", "mid", "realtime", "hld", ["sandboxing", "queueing", "leaderboard", "fairness"], ["collab"], "Accept submissions, run untrusted code safely against tests, and keep a live contest leaderboard."),
 ("leaderboard", "Design a real-time leaderboard", "mid", "realtime", "hld", ["sorted sets", "sharding", "approximate ranks"], ["streaming", "social"], "Rank millions of players with live updates and 'my rank' queries."),
 ("collab-whiteboard", "Design a collaborative whiteboard", "mid", "realtime", "hld", ["websocket", "crdt", "persistence"], ["collab"], "Many users draw on a shared canvas with low latency and persistence."),
 ("location-sharing", "Design live location sharing", "mid", "realtime", "hld", ["pub/sub", "battery", "privacy", "geo fan-out"], ["mobility", "social"], "Share a moving location with chosen friends in near real time."),
 ("google-maps", "Design a maps & navigation service", "senior", "search", "hld", ["tile serving", "routing graph", "traffic", "eta"], ["mobility", "search"], "Render maps, compute routes with live traffic and give accurate ETAs."),
 ("ticket-system", "Design an issue tracker / ticketing system", "entry", "classic", "hld", ["workflow", "search", "permissions", "notifications"], ["collab"], "Projects, issues, comments, workflows, search and notifications."),
 ("food-reviews", "Design a reviews & ratings service", "entry", "classic", "hld", ["aggregation", "spam", "ranking"], ["ecommerce", "delivery"], "Users review places/products; show trustworthy aggregate ratings and handle fake reviews."),
 ("calendar", "Design a calendar service", "mid", "classic", "hld", ["recurring events", "time zones", "invitations", "free/busy"], ["collab"], "Create recurring events, invite people, check availability across time zones."),
 ("url-metadata-preview", "Design link previews", "entry", "classic", "hld", ["crawling", "caching", "security (ssrf)"], ["social", "collab"], "Generate rich previews for links shared in a chat or feed, safely."),
 ("tinder", "Design a dating app matching", "mid", "social", "hld", ["geo search", "recommendation", "swipe consistency"], ["social"], "Show candidate profiles near me, record swipes and notify mutual matches instantly."),
 ("ai-chat-service", "Design a ChatGPT-like service", "senior", "realtime", "hld", ["gpu scheduling", "streaming responses", "rate limiting", "context storage"], ["cloud", "search"], "Serve LLM chat to millions: streaming tokens, GPU capacity, quotas, safety filters and conversation storage."),
 # low-level design (class design) questions
 ("lld-parking-lot", "Design a parking lot (LLD)", "entry", "lld", "lld", ["oop", "strategy", "concurrency"], [], "Class design for a multi-level parking lot: vehicles, spots, tickets, pricing and concurrency at the gates."),
 ("lld-lru-cache", "Design an LRU cache (LLD)", "entry", "lld", "lld", ["hash map + doubly linked list", "thread safety", "generics"], [], "Implement an LRU cache API with O(1) operations, then make it thread-safe and extensible to other eviction policies."),
 ("lld-elevator", "Design an elevator system (LLD)", "mid", "lld", "lld", ["state machine", "scheduling", "observer"], [], "Model several elevators, requests and a scheduling strategy."),
 ("lld-bookmyshow", "Design a movie ticket booking (LLD)", "mid", "lld", "lld", ["seat locking", "state pattern", "concurrency"], [], "Classes and flows for shows, seats, holds and payments, avoiding double booking."),
 ("lld-splitwise", "Design Splitwise (LLD)", "mid", "lld", "lld", ["graph of balances", "split strategies", "debt simplification"], [], "Groups, expenses split in different ways, balances and simplifying who owes whom."),
 ("lld-chess", "Design a chess game (LLD)", "mid", "lld", "lld", ["polymorphism", "move validation", "undo"], [], "Board, pieces, move rules, game state, check/checkmate detection and undo."),
 ("lld-logger", "Design a logging framework (LLD)", "entry", "lld", "lld", ["chain of responsibility", "singleton pitfalls", "appenders"], [], "Levels, formatters, multiple destinations and async writing."),
 ("lld-vending-machine", "Design a vending machine (LLD)", "entry", "lld", "lld", ["state pattern", "inventory", "payments"], [], "States, coin handling, dispensing and refunds."),
 ("lld-rate-limiter", "Design a rate limiter library (LLD)", "mid", "lld", "lld", ["strategy", "token bucket", "thread safety"], [], "A pluggable rate-limiting library with several algorithms and per-key limits."),
 ("lld-snake-ladder", "Design Snake & Ladder (LLD)", "entry", "lld", "lld", ["entities", "game loop", "extensibility"], [], "Players, dice, board with snakes and ladders and winning rules."),
]


def seed(db: Session) -> int:
    have = {q.slug: q for q in db.scalars(select(DesignQuestion))}
    n = 0
    for t in Q:
        slug, title, level, cat, kind, concepts, domains, prompt = t
        q = have.get(slug)
        if q is None:
            db.add(DesignQuestion(slug=slug, title=title, prompt=prompt, level=level, category=cat, concepts=concepts, domains=domains, kind=kind)); n += 1
        else:
            q.title, q.prompt, q.level, q.category, q.concepts, q.domains, q.kind = title, prompt, level, cat, concepts, domains, kind
    db.commit()
    return n
