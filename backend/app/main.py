import socket
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import crashcourse as crashcourse_api, resources as resources_api, capture as capture_api, stress as stress_api, account, analytics_me, arena as arena_api, auth, catalog, community, daily_life, design, interview as interview_api, labels, profile, revision, gamification as gamification_api, mentor as mentor_api, studio, integrations, learn, practice
from app.core.config import get_settings


def create_app() -> FastAPI:
    s = get_settings()
    s.validate_for_prod()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        stop = threading.Event()
        th = None
        if s.worker_enabled:
            from app.worker import loop  # in-process worker: dev / single-box only. With several API replicas run `python -m app.worker` and set CODEMIND_WORKER_ENABLED=false
            th = threading.Thread(target=loop, args=(stop, s.worker_poll_seconds), daemon=True, name="nexora-worker")
            th.start()
        yield
        stop.set()

    app = FastAPI(title="Nexora CP Mentor", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])
    from app.core import observability
    observability.install(app)
    app.include_router(auth.router)
    app.include_router(account.router)
    app.include_router(practice.router)
    app.include_router(integrations.router)
    app.include_router(learn.router)
    app.include_router(catalog.router)
    app.include_router(analytics_me.router)
    app.include_router(mentor_api.router)
    app.include_router(studio.router)
    app.include_router(gamification_api.router)
    app.include_router(community.router)
    app.include_router(design.router)
    app.include_router(labels.router)
    app.include_router(revision.router)
    app.include_router(daily_life.router)
    app.include_router(arena_api.router)
    app.include_router(interview_api.router)
    app.include_router(profile.router)
    app.include_router(stress_api.router)
    app.include_router(capture_api.router)
    app.include_router(resources_api.router)
    app.include_router(crashcourse_api.router)

    instance = s.instance_id or socket.gethostname()

    @app.middleware("http")
    async def served_by(request, call_next):
        resp = await call_next(request)
        resp.headers["X-Served-By"] = instance
        return resp

    @app.get("/health")
    def health():
        """Liveness: the process is up. Cheap on purpose; the orchestrator restarts the container when this fails."""
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        """Readiness: can this replica serve traffic right now? The load balancer takes it out of rotation on 503 (it is NOT restarted)."""
        from fastapi.responses import JSONResponse
        from sqlalchemy import text

        from app.core.db import engine
        from app.core.redis_client import get_redis
        checks = {}
        try:
            with engine.connect() as c:
                c.execute(text("select 1"))
            checks["database"] = "ok"
        except Exception:  # noqa: BLE001
            checks["database"] = "down"
        if s.redis_url:  # Redis is optional: degraded, not unready, when it is down
            checks["redis"] = "ok" if get_redis() is not None else "degraded"
        ok = checks["database"] == "ok"
        return JSONResponse({"status": "ready" if ok else "unready", "checks": checks, "instance": instance}, status_code=200 if ok else 503)

    return app


app = create_app()
