**BackupSeeker — Game Save Manager**
===================================

BackupSeeker is a lightweight, modular manager for creating, restoring, and safely archiving PC game save data. It combines a small testable core with a PyQt6 desktop UI and a flexible plugin system for game detection.

**Table of contents**
- **Overview**
- **Features**
- **Architecture**
- **Documentation** (`Docs/`)
- **Installation**
- **Quick start**
- **Configuration**
- **Backups & Safety**
- **Plugin system**
- **Plugin development**
- **Troubleshooting**
- **Roadmap**
- **Contributing**
- **License**

**Overview**
BackupSeeker creates timestamped ZIP archives of game save folders and provides a safety archive on restore to prevent accidental data loss.

**Features**
- Timestamped ZIP backups (per-profile compression settings).
- Automatic Safety archives before each restore.
- Portable contracted paths (environment variable tokens like `%USERPROFILE%`).
- Theme switching and persisted window geometry.
- Plugin discovery: Python modules + JSONC descriptors.
- Declarative `save_sources` (directories, registry probes, prompts) with lifecycle hooks for backup/restore extensions.

**Architecture (key files)**
- `BackupSeeker/core.py` — core logic, `GameProfile`, backup/restore orchestration.
- `BackupSeeker/main.py` — entry: Fluent UI when imports succeed, else legacy `BackupSeeker.ui.run_app`.
- `BackupSeeker/ui_fluent/` — Fluent UI (PyQt6-Fluent-Widgets): `app_runner.py` (`run_modern_fluent_app`), `main_window.py`, dashboard/plugins/profiles/backups pages, `fluent_impl.py` re-exports.
- `BackupSeeker/modern_widgets.py` — shared Fluent cards, navigation helpers, dialogs.
- `BackupSeeker/ui.py` — legacy PyQt6 UI (`run_app`) used as fallback.
- `BackupSeeker/plugin_manager.py` — plugin discovery and asset download (icons/posters).
- `BackupSeeker/plugins/base.py` — `GamePlugin` API; `plugins/save_sources.py` — `save_sources` schema.
- `BackupSeeker/plugins/` — built-in plugins, `games.jsonc`, templates.

For layering, startup flow, and backup pipeline details, see [Docs/ARCHITECTURE.md](Docs/ARCHITECTURE.md).

**Documentation (`Docs/`)**

| Doc | Contents |
|-----|----------|
| [Docs/PRD.md](Docs/PRD.md) | Product goals, scope, success criteria |
| [Docs/ARCHITECTURE.md](Docs/ARCHITECTURE.md) | System design and runtime flow |
| [Docs/ROADMAP.md](Docs/ROADMAP.md) | Phased roadmap |
| [Docs/PLANS.md](Docs/PLANS.md) | Planning backlog and initiatives |
| [Docs/WORKFLOW.md](Docs/WORKFLOW.md) | Dev and PR workflow |
| [Docs/PLUGIN_DEVELOPMENT.md](Docs/PLUGIN_DEVELOPMENT.md) | Plugin authoring |

Index: [Docs/README.md](Docs/README.md).

**Installation**
Requirements:
- Python 3.11+ (tested with 3.13).

Install dependencies (recommended inside a virtual environment). `requirements.txt` includes PyQt6, PyQt6-Fluent-Widgets, frameless window support, and `requests` (plugin assets).

```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows there is a convenience script: `install_me.bat` (runs `pip install -r requirements.txt` next to the batch file).

**Quick start**
From the repository root:

```pwsh
# Preferred package entry (Fluent UI; falls back to legacy UI on failure)
python -m BackupSeeker.main

# Or the top-level launcher (delegates to BackupSeeker.main)
python BackupSeeker.py

# Launch Fluent UI directly (same runner as main’s happy path)
python -m BackupSeeker.ui_fluent
```

Add a profile via the UI, paste or browse to the save folder (the app will contract environment variables), then click **BACKUP NOW**.

**Configuration**
The runtime config is stored in `BackupSeeker/gsm_config.json`. It contains profiles, UI settings (theme, window geometry), and backup location settings (`cwd` vs `fixed` + `backup_fixed_path`). If the file is corrupted it is rotated to `gsm_config.json.corrupted` and a fresh config is created.

**Backups & Safety archives**
- Default storage root: `./backups/` relative to the process working directory.
- Layout: `<StorageRoot>/<GameName>/<GameName>_<YYYY-MM-DD_hh-mm-ss>.zip`.
- Safety archives (before restore): `<StorageRoot>/<GameName>/Safety/SAFETY_<timestamp>.zip`.

Restore steps performed by the app:
1. Create Safety archive of current save folder (if present).
2. Optionally clear destination folder (if configured).
3. Extract selected backup ZIP.

**Maintenance scripts**
- `scripts/upgrade_backup_zips.ps1` (and `.bat` wrapper) — refresh embedded portable tooling inside existing backup ZIPs via `python -m BackupSeeker.archive.upgrade_zip`. See script header for usage.

**Plugin system**
Supported plugin types:
- Python modules placed in `BackupSeeker/plugins/` exposing `get_plugins()` (or discoverable `GamePlugin` subclasses per template).
- JSONC descriptors inside `BackupSeeker/plugins/games.jsonc`.

Plugins describe saves through **`save_sources`** (directory paths, optional Windows registry entries, prompts). Derived fields such as `save_paths` and `registry_keys` are computed from that list. Optional filtering via `plugins/plugin_index.json` (allow/block lists). Plugins can implement lifecycle hooks: `preprocess_backup`, `postprocess_backup`, `preprocess_restore`, `postprocess_restore`, and advanced **mechanical** hooks for custom archive rows or portable restore (see template plugin).

**Plugin development**
See [Docs/PLUGIN_DEVELOPMENT.md](Docs/PLUGIN_DEVELOPMENT.md) for a full guide. In short:
- Python plugins live in `BackupSeeker/plugins/<your_plugin>.py` and should subclass `GamePlugin` with `save_sources` (preferred) or rely on derived `save_paths`.
- JSONC entries go in `BackupSeeker/plugins/games.jsonc`; use `games.template.jsonc` as a scaffold.
- Use contracted env vars (e.g. `%USERPROFILE%`) for portability.

**Troubleshooting**
- Plugin not appearing: open the Plugin panel and click `Reset` to reload plugins.
- Detection issues: verify the expanded path exists in PowerShell using `Test-Path` with expanded variables.
- UI tracebacks: run the app from a console (`python -m BackupSeeker.main`) to see errors; check `gsm_config.json` rotation on parse errors.

**Roadmap**
See [Docs/ROADMAP.md](Docs/ROADMAP.md) for phased planning. Highlights:

- Profile import/export, retention policies, scheduled backups.
- Improved plugin UX and curated plugin index.
- Optional cloud sync (user opt-in) and encrypted backups.

**Contributing**
See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines. Keep changes small and focused; avoid changing existing `game_id` values for plugins.

**License**
This repository includes a `LICENSE` file (MIT). See `LICENSE` at the project root for terms.

---
For detailed plugin guidance, see [Docs/PLUGIN_DEVELOPMENT.md](Docs/PLUGIN_DEVELOPMENT.md).
