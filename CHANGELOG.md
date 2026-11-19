# Changelog
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [SemVer](https://semver.org/); the project is pre-1.0, so minor versions may change behaviour.

## [Unreleased]

## [0.1.0] - 2026-11-19
First tracked release.

### Added
- **Learning engine:** Daily Challenge with a measured holdout experiment, Pattern Universe, Revision Centre, Mistake Notebook, Learning Planner, AI Mentor (hint ladder, RAG, streaming, offline fallback).
- **Interview prep:** company-wise DSA resources (470 companies), 70-question system-design library, open-ended System Design Lab with AI review, 30/60-day crash courses, Mock Interview, Practice Arena.
- **Tooling:** sandboxed Coding Studio (C++/Python/Java/JavaScript), stress tester, browser extension for verdict capture, algorithm visualizer.
- **Platform:** email verification, password reset, TOTP MFA, notifications, public profiles.
- **Distributed deployment:** nginx load balancer, stateless API replicas, dedicated workers with atomic job claiming and leader election, Redis cache and shared rate limits, one-shot migrations, isolated code executor, Prometheus and Grafana.
- **Delivery:** GitHub Actions CI (lint, SQLite and Postgres/Redis tests, web, image scan, full-stack smoke and failure drills), CD to GHCR with SSH deploy and automatic rollback, dependency audit, Dependabot.

### Known limitations
See [Honest status](README.md#honest-status) and [docs/ROADMAP.md](docs/ROADMAP.md).
