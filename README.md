BackupSeeker — Game Save Manager
================================

BackupSeeker is a lightweight, modular manager for creating, restoring, and safely archiving PC game save data. It combines a small testable core with a PyQt6 desktop UI and a flexible plugin system for game detection.

Table of Contents
-----------------
1. Overview
2. Features
3. Why BackupSeeker?
4. Architecture
5. Installation
6. Quick Start
7. Configuration File
9. Plugin System
10. Developing Plugins (Summary)
11. Troubleshooting
12. Roadmap
13. Contributing
14. License
15. UI Roadmap

Overview
--------
BackupSeeker helps you avoid losing progress by making timestamped, compressed backups of game save folders. A “Safety” archive is automatically created on restore to guard against accidental overwrite.

Features
--------
- Profile-based save management (add, edit, delete game save profiles).

## Fluent UI Migration

This repository is being migrated to use PyQt6-Fluent-Widgets (Fluent mode)
for a cleaner, modern UI. A starter Fluent entry module has been added as
`BackupSeeker/ui_fluent.py` that initializes the Fluent library and launches
the existing main window. The migration will proceed incrementally — native
Fluent widgets will replace standard widgets over time.

If you want to enable the Fluent UI locally, install the requirements and run
the Fluent launcher:

PowerShell (example):
```
& C:/Python/Python313/python.exe -m pip install -r requirements.txt
& C:/Python/Python313/python.exe -m pip install "PyQt6-Fluent-Widgets[full]"
& C:/Python/Python313/python.exe -m BackupSeeker.ui_fluent
```

Or use the bundled installer script on Windows:
```
install_me.bat
```

Note: the project assumes `PyQt6` and `PyQt6-Fluent-Widgets[full]` are available
in the target environment.

- Timestamped ZIP backups (optional compression toggle per profile).
- Automatic Safety archives before every restore operation.
- Portable path handling via environment-variable contraction (e.g. `%USERPROFILE%`).
- Theme switching (system / dark / light) with persisted window geometry.
- Plugin discovery (Python modules + JSONC descriptors) and auto-detection of installed games.
- Extensible lifecycle hooks for specialized backup/restore behaviors.

Why BackupSeeker?
-----------------
Many save managers either hard‑code paths, lack cross-system portability, or skip safety restore safeguards. BackupSeeker focuses on:
- Portability: contracted paths keep profiles reusable across machines.
- Safety: automatic pre-restore archiving prevents destructive restores.
- Extensibility: pluggable detection and lifecycle hooks.
- Simplicity: single clear backup artifact (`<Game>_<timestamp>.zip`).

Architecture
------------
- `BackupSeeker/core.py`: Pure logic (config, profile model, backup/restore helpers).
- `BackupSeeker/ui.py`: PyQt6 GUI (profiles, backup/restore dashboard, plugin & storage panels).
- `BackupSeeker/plugin_manager.py`: Discovers code and JSONC game plugins.
- `BackupSeeker/plugins/base.py`: Plugin abstract base class + JSON adapter.
- Backup storage (configurable):
	- Default: `./backups/` in the current working directory when the app launches.
	- Fixed/custom: any user-chosen folder via Storage menu.
	Each game gets its own subfolder plus a `Safety/` subfolder.

Installation
------------
Requirements:
- Python 3.11+ (tested with 3.13) on Windows (other OS support depends on plugin paths).
- PyQt6.

Install dependencies (PowerShell):
```pwsh
python -m pip install --upgrade pip
python -m pip install PyQt6
```
Optionally create a virtual environment:
```pwsh
python -m venv .venv
./.venv/Scripts/Activate.ps1
python -m pip install PyQt6
```

Quick Start
-----------
Run from the repository root:
```pwsh
python -m BackupSeeker.main
```
Add your first profile with “Add Game”, paste the save folder (it will be contracted automatically), then click “BACKUP NOW”.

Configuration File
------------------
The file `BackupSeeker/gsm_config.json` stores:
- `games`: array of game profile objects (id, name, save_path, flags).
- `theme`, `window_geometry`, `table_widths`, `last_updated`.
- `backup_location_mode`: `cwd` or `fixed` (controls where backups go).
- `backup_fixed_path`: absolute path used when mode is `fixed`.
Corruption handling: on JSON decode failure the file is renamed to `gsm_config.json.corrupted` and a fresh config is started.

Backups & Safety Archives
-------------------------
Storage root:
- Default: `./backups/` relative to the process working directory.
- Fixed: user-selected directory stored in config.

Layout:
- Regular backups: `<StorageRoot>/<GameName>/<GameName>_<YYYY-MM-DD_hh-mm-ss>.zip`.
- Safety archives (created before any restore): `<StorageRoot>/<GameName>/Safety/SAFETY_<timestamp>.zip` — snapshot of target folder pre-restore.

Restore process:
1. Safety archive created if existing data present.
2. (Optional) Clear folder when `clear_folder_on_restore` is true.
3. Selected backup ZIP extracted.


Plugin System
-------------
Supported types:
- Python modules: implement `get_plugins()` returning one or more subclasses of `GamePlugin`.
- JSONC descriptors: objects inside `plugins/games.jsonc` (supports `//` comments).
Detection strategies:
- Path existence check on any `save_paths` entry.
- Optional Windows registry key checks (see `registry_keys`).
Lifecycle hooks (`GamePlugin`): `preprocess_backup`, `postprocess_backup`, `preprocess_restore`, `postprocess_restore` (each receives/returns plain dicts).

Developing Plugins (Summary)
----------------------------
Minimal Python plugin example:
```python
from typing import List
from .base import GamePlugin

class MyGamePlugin(GamePlugin):
		@property
		def game_id(self) -> str: return "mygame"
		@property
		def game_name(self) -> str: return "My Game"
		@property
		def save_paths(self) -> List[str]: return ["%USERPROFILE%\\Saved Games\\MyGame"]

def get_plugins():
		return [MyGamePlugin()]
```
JSONC entry:
```jsonc
{
	"id": "mygame_json",
	"name": "My Game (JSON)",
	"save_paths": ["%USERPROFILE%\\Saved Games\\MyGame"],
	"file_patterns": ["*.sav"],
	"registry_keys": []
}
```
See `PLUGIN_DEV.md` for advanced hooks and registry examples.

Troubleshooting
---------------
- Plugin missing: Open Plugin Panel, click `Reset` to reload modules and JSON; confirm file naming and `get_plugins()` presence.
- Detection not highlighting: Verify contracted path vs real path; open PowerShell and check `Test-Path (Expand-EnvironmentVariables <path>)`.
- UI errors: Run `python -m BackupSeeker.main` from console to view traceback; corrupted config will auto-rotate.

Roadmap
-------
- One-click test profile generation.
- Profile import/export (JSON) & backup retention policies.
- Non-blocking plugin error/report panel.
- Scheduled backups & optional cloud sync (user opt-in).
- Marketplace / curated plugin index.
- Advanced diff view before restore.
- Storage improvements (multi-root presets, quota / auto-prune policies).

Contributing
------------
See `CONTRIBUTING.md` for guidelines (issues, PR flow, coding standards, plugin submission). Focus on small, reviewable changes; keep `game_id` stable.

License
-------
No license file is currently included. Add a `LICENSE` (e.g. MIT or Apache-2.0) to enable reuse and contribution. Until then, treat the code as “All rights reserved”.

Security & Data Disclaimer
--------------------------
Backups may contain personal or sensitive game data. Do not publish raw backups. For future cloud sync features ensure encryption at rest and in transit.

---
For deeper plugin development details, read `PLUGIN_DEV.md`.

