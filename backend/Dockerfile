# One image recipe, three runtime targets:  api (default) · worker (same image, different command) · executor (needs a Docker CLI)
#   docker build --target api      -t nexora-api .
#   docker build --target executor -t nexora-executor .
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt "psycopg[binary]"
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
COPY data ./data

# ---- api / worker / migrate: NO Docker CLI and no Docker socket. Untrusted code never runs in this image.
FROM base AS api
RUN useradd -m -u 10001 nexora && chown -R nexora /app
USER nexora
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')" || exit 1
# Behind the load balancer: trust X-Forwarded-For so rate limits and logs see the real client, not the LB. Only the LB can reach this port.
# Migrations are NOT run here: with N replicas booting together they would race. The one-shot `migrate` service runs them first.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-2} --proxy-headers --forwarded-allow-ips='*' --timeout-graceful-shutdown 20"]

# ---- executor: the only image that talks to a Docker daemon. Run it on its own host/network (docs/CODE_EXECUTION.md).
FROM base AS executor
# Static Docker CLI from the official image. (Debian 13's `docker.io` package no longer ships the CLI, so apt cannot be relied on.)
COPY --from=docker:29-cli /usr/local/bin/docker /usr/local/bin/docker
EXPOSE 9000
HEALTHCHECK --interval=20s --timeout=5s --retries=5 CMD python -c "import socket;socket.create_connection(('127.0.0.1',9000),2)" || exit 1
CMD ["uvicorn", "app.execution.service:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "2"]
