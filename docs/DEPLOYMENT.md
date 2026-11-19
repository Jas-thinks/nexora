# Deployment

Architecture and failure behaviour: [`architecture/distributed-system.md`](architecture/distributed-system.md).
This page is the runbook.

## 1. Run the full stack locally (Docker)
```bash
cp .env.example .env        # set POSTGRES_PASSWORD, JWT_SECRET, EXECUTOR_KEY (the file shows how to generate them)
mkdir -p /srv/nexora-work && chmod 777 /srv/nexora-work     # or set SANDBOX_WORKDIR in .env to any host directory
docker pull python:3.12-alpine gcc:13                        # sandbox language images (see docs/CODE_EXECUTION.md for all)
make up           # http://localhost:8080
make smoke        # 15 end-to-end checks
make chaos        # failure drills
make observe      # Prometheus + Grafana (http://localhost:3001, admin / $GRAFANA_PASSWORD)
```
Scale a tier at runtime: `docker compose up -d --scale api=5 --scale worker=2` (nginx discovers new replicas within ~5 s).
Small machine? `API_REPLICAS=1 WEB_REPLICAS=1 WEB_CONCURRENCY=1` in `.env` (the default stack wants ~3 GB RAM).

**Why `SANDBOX_WORKDIR` exists:** the executor starts sandbox containers as *siblings* on the host's Docker daemon, so the scratch
directory it hands them must exist at the *same path* on the host and inside the executor container.

## 2. Production on a single VM (AWS EC2, Oracle Cloud, any Ubuntu host)
Which VM? The default stack needs ~3 GB RAM; a 1 GB free-tier micro will not run it (use the sizing knobs above and expect it to be tight).
Oracle Cloud's Always Free Arm VMs have the headroom (build with `MULTIARCH=true`, see below); on AWS use a `t3.small`/`t3.medium`
(paid, or covered by new-account credits). Nothing here has been run on a cloud VM yet; the stack itself was run locally.

1. **Bootstrap once** (as root on the VM): `deploy/vm/bootstrap.sh` installs Docker, creates the `deploy` user, the sandbox
   scratch dir, swap on small machines, a firewall that allows only SSH/80/443, and pre-pulls the sandbox images.
2. **Create `/opt/nexora/.env`** from `.env.example`: strong secrets, `DOMAIN=your.domain`, `IMAGE_REGISTRY=ghcr.io/<owner>/<repo>`,
   LLM keys, SMTP. Point the domain's A record at the VM.
3. **GitHub: Settings → Environments → `production`**
   | Kind | Name | Value |
   |---|---|---|
   | variable | `DEPLOY_HOST` | VM address (CD deploys only when this is set) |
   | variable | `DEPLOY_USER` | `deploy` |
   | variable | `DEPLOY_DOMAIN` | your domain (used for the public smoke test) |
   | variable | `DEPLOY_KNOWN_HOSTS` | output of `ssh-keyscan <host>`, verified out of band (pins the host key) |
   | secret | `DEPLOY_SSH_KEY` | private key whose public half is in `/home/deploy/.ssh/authorized_keys` |
   Optional: require reviewers on the `production` environment for manual approval; set repository variable `MULTIARCH=true` for amd64+arm64 images.
4. **Push to `main`.** CI → CD builds and pushes `api`, `web`, `executor` to GHCR tagged with the commit SHA → copies compose files to the VM →
   `deploy/vm/deploy.sh <sha>`: pull, one-shot migration, rolling container replacement, smoke test, **automatic rollback to the previous
   images if the smoke test fails**. `v*` tags also create a GitHub release.

TLS is automatic (Caddy + Let's Encrypt) once the domain resolves to the VM. Only 80/443 are public; Postgres, Redis, the executor
and Grafana are never published (Grafana is on the VM's loopback: `ssh -L 3001:localhost:3001 deploy@host`).

## 3. Roll back
`deploy.sh` rolls back images automatically on a failed smoke test. To go back by hand: `cd /opt/nexora && deploy/vm/deploy.sh <older-sha>`.
**Database migrations are forward-only**: images roll back, schema does not. Write migrations as expand-then-contract so the previous
image still works against the new schema; a destructive migration needs a manual restore from backup.

## 4. Sandbox in production
The Docker socket is root on its host. Run the `executor` on a **separate VM** with nothing else on it and point the API at it:
```bash
# runner VM:  docker compose up -d executor     (needs EXECUTOR_KEY; expose :9000 only to the API's address, e.g. via a private network or firewall rule)
# app VM .env: EXECUTOR_URL=http://<runner-private-ip>:9000    (same EXECUTOR_KEY)
```
Untrusted code still runs in network-less, read-only, resource-capped containers either way ([`CODE_EXECUTION.md`](CODE_EXECUTION.md)).

## 5. Free tiers, honestly
* **Compute:** Oracle Always Free Arm VM (4 OCPU / 24 GB) fits the whole stack; AWS free credits fit a `t3.small`+. A PaaS
  (Fly.io, Render, Railway) can host `api`/`web`/`worker` and managed Postgres/Redis but **cannot run the sandbox** (no Docker daemon),
  so code execution needs a separate VM anyway.
* **LLMs:** Gemini and Groq have free tiers (rate-limited); with no key the mentor runs offline. Free quotas and terms change: check them.
* **Email:** without SMTP, verification/reset links are logged server-side only. Use a transactional provider's free tier for real mail.

## 6. Before you call it production-ready (not done)
Backups and a tested restore, a Postgres replica/failover and Redis Sentinel (the data tier is single-instance), alerting rules,
Postgres/Redis exporters, a load test of this stack, secrets in a manager rather than `.env`, httpOnly-cookie sessions instead of
`localStorage` tokens, and a first real GitHub Actions run.

## Verified vs not
**Verified locally and on GitHub's runners** (first Actions run on `main`): the whole compose stack builds and boots in the right order (migrate -> api/worker), 3-replica spread, sandbox run through the executor, the replica-kill / Redis-loss / Postgres-restart drills, backend tests on SQLite and on Postgres 16 + Redis with migrations (`alembic check`), web typecheck/tests/build, extension tests, docs-sync. Verified locally only: Prometheus scraping, Grafana provisioning, production-overlay port exposure (only Caddy public; balancer on loopback), Caddyfile validity.
**Not verified:** pushing images to GHCR and the SSH deploy job (CD ran only as far as its gate), the cloud-VM scripts (`bootstrap.sh`, `deploy.sh` are syntax-checked only), TLS issuance, CodeQL (needs a public repo or code scanning), multi-arch builds.
