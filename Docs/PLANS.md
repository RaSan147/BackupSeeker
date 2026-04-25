# Plans hub

Use this file for **structured planning** that spans multiple releases. Use **GitHub issues** for discrete bugs and small tasks; use this hub when you want a durable backlog table or a place to track **active initiatives** without opening many documents.

## What belongs here vs issues

| Use **issues** | Use **this hub** |
|----------------|------------------|
| Bug reports, single-feature PRs | Cross-cutting themes (e.g. “retention + UX”) |
| Discussion per ticket | Ordered backlog with priority and status |
| CI or one-off fixes | Initiative narrative with links out to issues |

## Backlog

Seed items derived from [ROADMAP.md](ROADMAP.md). Update priority and status as work progresses.

| Feature / theme | Priority | Status | Notes |
|-------------------|----------|--------|-------|
| Profile import/export | P2 | Not started | Align with config schema versioning |
| Backup retention policies | P2 | Not started | Per-profile or global caps |
| Scheduled backups | P3 | Not started | Windows Task Scheduler vs in-process timer |
| Plugin panel / discovery UX | P2 | Not started | Reload, errors, curated list entry point |
| Curated plugin index | P3 | Not started | Doc or repo; no telemetry by default |
| Optional encrypted backups | P3 | Not started | Threat model + key handling first |
| Optional cloud sync | P4 | Not started | Opt-in, encryption, provider abstraction |

## Active initiatives

_Use this section for work in flight. Link PRs and issues._

- (None recorded.)

## Completed plans

_Move finished initiatives here with a one-line outcome and optional link to release or PR._

- **Documentation aligned with codebase (2026-04)** — README, `Docs/*`, `CONTRIBUTING.md`, `OPTIMIZATION_LOG.md`, and `REFACTORING_NOTES.md` updated for Fluent `ui_fluent` package layout, `save_sources` plugin API, pinned `requirements.txt`, and `scripts/upgrade_backup_zips`.
