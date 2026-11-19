#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 22.04/24.04 VM (AWS EC2, Oracle Cloud, GCP, any VPS). Idempotent.  Run as root:
#   curl -fsSL <raw url of this file> | sudo bash        (or copy it over and run it)
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root"; exit 1; }
DEPLOY_USER="${DEPLOY_USER:-deploy}"; APP_DIR="${APP_DIR:-/opt/nexora}"; WORKDIR="${SANDBOX_WORKDIR:-/srv/nexora-work}"

if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sh; fi           # Docker's own installer (docs.docker.com/engine/install)
id "$DEPLOY_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$DEPLOY_USER"
usermod -aG docker "$DEPLOY_USER"
mkdir -p "$APP_DIR" "$WORKDIR" "/home/$DEPLOY_USER/.ssh"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"; chmod 777 "$WORKDIR"                          # sandbox containers (uid 65534) write compiled binaries here
touch "/home/$DEPLOY_USER/.ssh/authorized_keys"; chmod 700 "/home/$DEPLOY_USER/.ssh"; chmod 600 "/home/$DEPLOY_USER/.ssh/authorized_keys"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"

# Small free-tier VMs run out of memory during image pulls/builds: add swap once.
if [ ! -f /swapfile ] && [ "$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)" -lt 4096 ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# Firewall: SSH + web only. Postgres, Redis, the executor and Grafana are never published.
if command -v ufw >/dev/null; then ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw allow 443/udp >/dev/null; ufw --force enable >/dev/null; fi

# Sandbox language images are pulled ahead of time so the first user run is not a multi-minute download.
for img in python:3.12-alpine gcc:13 eclipse-temurin:21-jdk-alpine node:22-alpine; do docker pull -q "$img" >/dev/null || echo "warning: could not pull $img"; done

echo "bootstrap done."
echo " 1. add the CI deploy public key to /home/$DEPLOY_USER/.ssh/authorized_keys"
echo " 2. create $APP_DIR/.env from .env.example (strong POSTGRES_PASSWORD, JWT_SECRET, EXECUTOR_KEY, DOMAIN, IMAGE_REGISTRY)"
echo " 3. point your domain's A record at this VM, then push to main (or run deploy.sh by hand)"
