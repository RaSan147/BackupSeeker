# Product Requirements Document — BackupSeeker

## Problem statement

PC gamers lose progress when saves are corrupted, overwritten, or lost during reinstalls or hardware changes. Manually copying save folders is error-prone and easy to forget. BackupSeeker addresses this by offering a **desktop tool** to **back up** and **restore** game save data with **safety archives** and **portable paths**, extended by a **plugin system** so support for specific games can grow without rebuilding the core app.

## Product goals

1. **Reliable archiving** — Create timestamped ZIP backups of configured save locations with predictable on-disk layout.
2. **Safe restore** — Before overwriting live saves, create a Safety archive of the current state when possible.
3. **Portability** — Store paths using environment-variable tokens (for example `%USERPROFILE%`) so profiles survive machine moves.
4. **Extensibility** — Discover games via Python plugins and JSONC descriptors; optional lifecycle hooks for custom backup/restore behavior.
5. **Usability** — PyQt6 desktop UI (Fluent UI by default when dependencies are available), theme and window layout persistence.

## Target users

- **Primary:** Windows PC players who want local, user-controlled backups of game saves (no mandatory cloud).
- **Secondary:** Contributors who add or maintain game plugins and improve detection heuristics.

## In scope (current product)

| Area | Requirements |
|------|----------------|
| Profiles | Per-game profiles with save roots, optional plugin binding, compression and storage preferences as implemented in config. |
| Backup | Single ZIP per operation containing bundle metadata (`bundle.json`), README, portable restore helpers, embedded plugin source when applicable, and save files under logical keys. |
| Restore | List backups per profile; optional clear destination; Safety ZIP before extract; guarded ZIP member handling. |
| Plugins | Python modules under `BackupSeeker/plugins/` with `get_plugins()` or auto-discovered `GamePlugin` classes; JSON array in `games.jsonc`; declarative **`save_sources`** per plugin; optional `plugin_index.json` whitelist/blocklist; registry and path-based detection derived from sources. |
| Configuration | JSON config at `BackupSeeker/gsm_config.json`; corruption rotation to `.corrupted` and fresh defaults. |
| UI | Default entry via `BackupSeeker.main` → Fluent UI package when import succeeds; fallback to legacy `BackupSeeker.ui`. |

## Out of scope (for this PRD)

These may appear on the [roadmap](ROADMAP.md) but are **not** guaranteed current features:

- Mandatory cloud sync or vendor-hosted storage.
- Background scheduled backups unless/until implemented and documented.
- Automatic upload of saves or telemetry without explicit user opt-in and documentation.

## Non-functional requirements

- **Privacy:** Saves may contain personal data; the product must not exfiltrate them by default (see [CONTRIBUTING.md](../CONTRIBUTING.md) security section).
- **Maintainability:** Core backup logic lives in importable modules (`BackupSeeker.core`, `BackupSeeker.archive`) without requiring the GUI for programmatic use.
- **Compatibility:** Avoid breaking existing profile and `game_id` semantics without migration strategy and docs.

## Success criteria (qualitative)

- Users can complete **backup → restore → verify files** for a configured profile without data loss beyond documented edge cases.
- New plugins can be added following [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md) and appear after reload in the UI.
- Recovery from bad config is handled via rotation without silent data destruction.

## References

- User-facing overview: [README.md](../README.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
