**BackupSeeker — Game Save Manager**
===================================

BackupSeeker is a lightweight, modular manager for creating, restoring, and safely archiving PC game save data. It combines a small testable core with a PyQt6 desktop UI and a flexible plugin system for game detection.

**Table of contents**
- **Overview**
- **Features**
- **Architecture**
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
- Lifecycle hooks for plugin-driven backup/restore extensions.

**Architecture (key files)**
- `BackupSeeker/core.py` — core logic and profile model.
- `BackupSeeker/ui.py` — main PyQt6 UI.
- `BackupSeeker/ui_fluent.py` — optional Fluent UI launcher using PyQt6-Fluent-Widgets.
- `BackupSeeker/plugin_manager.py` — plugin discovery and loading.
- `BackupSeeker/plugins/` — built-in plugin base + shipable plugin files.

**Installation**
Requirements:
- Python 3.11+ (tested with 3.13).

Install dependencies (recommended inside a virtual environment):
```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
If you want to use the Fluent widgets, also install:
```pwsh
python -m pip install "PyQt6-Fluent-Widgets[full]"
```

On Windows there's a convenience script: `install_me.bat` (inspects `requirements.txt`).

**Quick start**
From the repository root you can run either:
```pwsh
# run the package entry
python -m BackupSeeker.main
# or run the top-level launcher script
python BackupSeeker.py
```
To launch the Fluent UI directly for testing:
```pwsh
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

**Plugin system**
Supported plugin types:
- Python modules placed in `BackupSeeker/plugins/` exposing `get_plugins()`.
- JSONC descriptors inside `BackupSeeker/plugins/games.jsonc`.

Detection strategies include path existence checks and optional Windows registry lookups. Plugins can implement lifecycle hooks: `preprocess_backup`, `postprocess_backup`, `preprocess_restore`, `postprocess_restore`.

**Plugin development**
See `BackupSeeker/PLUGIN_DEV.md` for a full guide and examples. In short:
- Python plugins live in `BackupSeeker/plugins/<your_plugin>.py` and should provide `get_plugins()` returning one or more `GamePlugin` instances.
- JSONC entries are appended to `BackupSeeker/plugins/games.jsonc` or `games.template.jsonc` for reference.
- Use contracted env vars (e.g. `%USERPROFILE%`) for portability.

**Troubleshooting**
- Plugin not appearing: open the Plugin panel and click `Reset` to reload plugins.
- Detection issues: verify the expanded path exists in PowerShell using `Test-Path` with expanded variables.
- UI tracebacks: run the app from a console (`python -m BackupSeeker.main`) to see errors; check `gsm_config.json` rotation on parse errors.

**Roadmap (short)**
- Profile import/export, retention policies, scheduled backups.
- Improved plugin UX and curated plugin index.
- Optional cloud sync (user opt-in) and encrypted backups.

**Contributing**
See `CONTRIBUTING.md` for contribution guidelines. Keep changes small and focused; avoid changing existing `game_id` values for plugins.

**License**
This repository includes a `LICENSE` file (MIT). See `LICENSE` at the project root for terms.

---
For detailed plugin guidance, open `BackupSeeker/PLUGIN_DEV.md`.

