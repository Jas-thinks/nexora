"""Background worker: job queue, scheduler and notification ticks.

Run as its own process for a multi-replica deployment:   python -m app.worker
(with CODEMIND_WORKER_ENABLED=false on the API replicas). Several workers can run at once: jobs are claimed atomically, and the
periodic ticks only run on the elected leader (app.core.leader), so nothing is enqueued or emailed twice."""
import logging
import signal
import threading

log = logging.getLogger("nexora.worker")


def loop(stop: threading.Event, interval: float, scheduler: bool = True) -> None:
    from app.core import leader
    from app.core.db import SessionLocal
    from app.services import scheduler as sched
    from app.services.ingest import run_due_jobs
    n = 0
    while not stop.wait(interval):
        n += 1
        try:
            with SessionLocal() as db:
                lead = scheduler and leader.try_lead(db)
                if lead and n % max(1, int(60 / interval)) == 1:  # roughly once a minute
                    sched.tick(db)
                if lead and n % max(1, int(600 / interval)) == 2:  # about every 10 minutes
                    from app.services import notifications
                    notifications.tick(db)
                run_due_jobs(db, limit=5)  # every worker (leader or not) drains the queue
        except Exception:  # a failing poll must never kill the worker
            log.exception("worker poll failed")


def main() -> None:
    from app.core import observability
    from app.core.config import get_settings
    s = get_settings()
    s.validate_for_prod()
    observability.setup_logging()
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())  # finish the current poll, then exit: no job is abandoned mid-run on a rolling deploy
    log.info("worker started")
    loop(stop, s.worker_poll_seconds)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
