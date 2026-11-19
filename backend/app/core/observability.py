"""Security headers, request IDs + structured JSON logs, Prometheus metrics."""
import json
import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Histogram, generate_latest

from app.core.config import get_settings

REQS = Counter("nexora_http_requests_total", "HTTP requests", ["method", "route", "status"])
LAT = Histogram("nexora_http_request_seconds", "HTTP latency", ["method", "route"], buckets=(.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, 30, 60, 120))
LLM_TOK = Counter("nexora_llm_tokens_total", "LLM tokens", ["provider", "kind"])
LLM_CALLS = Counter("nexora_llm_calls_total", "LLM calls", ["provider", "ok"])
SANDBOX = Counter("nexora_sandbox_runs_total", "Sandbox runs", ["language", "verdict"])
log = logging.getLogger("nexora.access")


class JsonFormatter(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        d = {"ts": self.formatTime(r), "level": r.levelname, "logger": r.name, "msg": r.getMessage()}
        d.update(getattr(r, "extra_fields", {}))
        if r.exc_info:
            d["exc"] = self.formatException(r.exc_info)
        return json.dumps(d, default=str)


def setup_logging() -> None:
    if get_settings().log_json and not any(isinstance(h.formatter, JsonFormatter) for h in logging.getLogger().handlers):
        h = logging.StreamHandler(); h.setFormatter(JsonFormatter())
        logging.getLogger("nexora").addHandler(h); logging.getLogger("nexora").setLevel(logging.INFO)


def install(app: FastAPI) -> None:
    setup_logging()
    prod = get_settings().env == "prod"

    @app.middleware("http")
    async def mw(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        t0 = time.perf_counter()
        try:
            resp: Response = await call_next(request)
        except Exception:
            log.exception("unhandled error", extra={"extra_fields": {"request_id": rid, "path": request.url.path}})
            raise
        dt = time.perf_counter() - t0
        route = getattr(request.scope.get("route"), "path", "unmatched")  # template, not the raw URL: bounded label cardinality, no ids in metrics
        REQS.labels(request.method, route, str(resp.status_code)).inc(); LAT.labels(request.method, route).observe(dt)
        resp.headers.update({"X-Request-ID": rid, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                             "Permissions-Policy": "camera=(), microphone=(), geolocation=()", "Cross-Origin-Opener-Policy": "same-origin"})
        if request.url.path.startswith(("/auth", "/me")):
            resp.headers["Cache-Control"] = "no-store"
        if prod:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path not in ("/health", "/metrics"):
            log.info("request", extra={"extra_fields": {"request_id": rid, "method": request.method, "route": route, "status": resp.status_code, "ms": round(dt * 1000, 1)}})
        return resp

    @app.get("/metrics", include_in_schema=False)
    def metrics(request: Request):
        s = get_settings()
        auth = request.headers.get("authorization", "")
        if not (s.metrics_token and auth == f"Bearer {s.metrics_token}"):
            raise HTTPException(401, "metrics require the metrics token")
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
