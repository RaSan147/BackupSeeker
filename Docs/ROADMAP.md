# Roadmap

Phased direction for BackupSeeker. Items are aspirational until implemented; track detailed status in [PLANS.md](PLANS.md).

## Near term

- **Profile portability** — Import/export of profile sets (shareable JSON or documented bundle) to ease reinstalls.
- **Retention policies** — Optional limits on backup count or age per game folder to control disk use.
- **Scheduled backups** — Time- or idle-triggered backup (opt-in; design TBD for Windows scheduling).

## Mid term

- **Plugin UX** — Clearer discovery, reload feedback, and possibly a curated index shipped or linked from the app.
- **Curated plugin index** — Maintainer-reviewed list or repo of community plugins with compatibility notes.

## Long term

- **Optional cloud sync** — User opt-in only; encryption and provider choice documented before shipping.
- **Encrypted backups** — Optional at-rest encryption for ZIP or sidecar keys (design and UX TBD).

## Ideas from plugin / engineering notes

These are **not commitments**; capture here for prioritization discussion:

- Per-plugin settings UI.
- Async hooks for uploads or long-running post-backup steps.
- Signed or verified plugin packages and a packaging standard.

See also the **Future ideas** section in [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md).
