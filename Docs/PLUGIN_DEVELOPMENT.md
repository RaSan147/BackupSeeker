# Plugin Development Guide — BackupSeeker

Canonical location for this guide is **`Docs/PLUGIN_DEVELOPMENT.md`**. For how plugins are loaded at runtime, see [ARCHITECTURE.md](ARCHITECTURE.md) (sections **Layers** and **Plugins**).

This guide explains how to create, test, and share plugins for BackupSeeker. Two plugin formats are supported:

- Python module plugins placed in `BackupSeeker/plugins/`.
- JSONC descriptor entries in `BackupSeeker/plugins/games.jsonc` (comments with `//` are allowed and stripped at load time).

## 1. Where to place plugins

- Python plugins: `BackupSeeker/plugins/<your_plugin>.py` (module name must be a valid Python identifier).
- JSONC descriptors: add objects to `BackupSeeker/plugins/games.jsonc` or copy from `games.template.jsonc`.

## 2. Core concepts

Plugins expose one or more `GamePlugin` instances describing:

- `game_id`: stable unique identifier (do not change once released).
- `game_name`: user-facing label.
- **`save_sources`**: declarative list of save “sources” (see below). This is the **canonical** shape; properties like `save_paths`, `save_locations`, and `registry_keys` are **derived** for compatibility and detection.
- Optional `icon` / `poster` (emoji, file path, or URL — URLs are cached under `BackupSeeker/data/` by the plugin manager).
- Optional `registry_keys`-style behavior via `kind: registry_windows` entries inside `save_sources`.
- Optional lifecycle hooks and **mechanical** overrides for advanced backup/restore (see `BackupSeeker/plugins/TEMPLATE_PLUGIN.py`).

### `save_sources` schema (summary)

Full rules and normalization live in [`BackupSeeker/plugins/save_sources.py`](../BackupSeeker/plugins/save_sources.py) (module docstring). Each entry is a dict:

- **`kind: directory`** — `id`, `paths` (contracted path strings; multiple paths under the same `id` are alternatives sharing one logical ZIP root). Optional `prompt`, `pin_relative_segments`, labels, etc.
- **`kind: registry_windows`** — Windows install detection: `key_path`, `value_name` (pairs become `registry_keys`).

Use forward slashes in path strings for portability on Windows.

## 3. Contracted paths

Always prefer environment-variable tokens (e.g. `%USERPROFILE%`, `%PUBLIC%`, `$HOME`) instead of absolute paths. The app stores contracted tokens and expands them at runtime.

Between segments, use forward slashes (`/`) — valid on Windows through Python’s path APIs, and you avoid doubled backslashes or raw string literals.

## 4. Registry-based detection (Windows)

Prefer declaring registry probes inside **`save_sources`** with `kind: registry_windows` and `key_path` / `value_name`.

If you only use the derived `registry_keys` property in documentation, remember it is filled from those entries.

## 5. Lifecycle hooks

Hooks receive and return plain dictionaries; return the input unchanged if you don't modify it.

- `preprocess_backup(profile_dict)` — run before backup starts (normalize paths, stage files).
- `postprocess_backup(result_dict)` — runs after ZIP creation (e.g. add hash, upload).
- `preprocess_restore(profile_dict)` — run before restore (create staging dirs).
- `postprocess_restore(result_dict)` — validate restore, cleanup, notify.

### Mechanical / portable hooks (optional)

For full control of archive contents, bundle metadata, or embedded CLI restore, see **`BackupSeeker/plugins/TEMPLATE_PLUGIN.py`** — it documents `mechanical_collect_archive_rows`, `mechanical_finalize_bundle`, `portable_restore`, `mechanical_after_app_restore`, and related extension points.

## 6. Minimal Python plugin example

Prefer copying `BackupSeeker/plugins/TEMPLATE_PLUGIN.py` and renaming the class. Minimal inline example:

```python
from typing import Any, Dict, List

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY


class MyGamePlugin(GamePlugin):
    @property
    def game_id(self) -> str:
        return "mygame"

    @property
    def game_name(self) -> str:
        return "My Game"

    @property
    def save_sources(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "path_0",
                "kind": SAVE_KIND_DIRECTORY,
                "paths": ["%USERPROFILE%/Saved Games/MyGame"],
            },
        ]


def get_plugins():
    return [MyGamePlugin()]
```

Notes: When your plugin is imported as part of the `BackupSeeker.plugins` package, relative imports like `from .base import GamePlugin` work. Alternatively use `from BackupSeeker.plugins.base import GamePlugin`.

## 7. Advanced plugin (example postprocess hook)

```python
from typing import Any, Dict, List
import hashlib
import os

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY


class MyAdvancedPlugin(GamePlugin):
    @property
    def game_id(self) -> str:
        return "mygame_adv"

    @property
    def game_name(self) -> str:
        return "My Game (Advanced)"

    @property
    def save_sources(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "path_0",
                "kind": SAVE_KIND_DIRECTORY,
                "paths": ["%USERPROFILE%/Saved Games/MyGame"],
            },
        ]

    def postprocess_backup(self, result_data: Dict) -> Dict:
        zip_path = result_data.get("backup_path")
        if zip_path and os.path.exists(zip_path):
            h = hashlib.sha256()
            with open(zip_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            result_data["sha256"] = h.hexdigest()
        return result_data


def get_plugins():
    return [MyAdvancedPlugin()]
```

## 8. JSONC descriptor example

Align with `games.template.jsonc` — use **`save_sources`** (not legacy flat `save_paths` only):

```jsonc
{
  "id": "mygame_json",
  "name": "My Game (JSON)",
  "save_sources": [
    {
      "id": "path_0",
      "kind": "directory",
      "paths": ["%USERPROFILE%/Saved Games/MyGame"]
    }
  ],
  "file_patterns": ["*.sav"]
}
```

Optional fields such as `backup_exclude_globs`, `zip_key_aliases`, `readme_extra_lines`, and `clear_folder_on_restore` are documented in the template file.

## 9. Testing checklist

1. Launch app: `python -m BackupSeeker.main`
2. Open the Plugin panel in the UI.
3. Click `Reset` to reload Python and JSONC plugins.
4. Use `Auto Detect Installed` to run detection heuristics.
5. Add detected plugin(s) to profiles and run backup/restore flows.
6. Verify Safety archive creation and any hook side-effects (e.g. added hash).

## 10. Best practices

- Keep `game_id` stable once published.
- Prefer **`save_sources`** so detection, bundle metadata, and portable restore stay consistent.
- Prefer contracted env vars for portability.
- Keep plugins minimal and dependency-free where possible.
- For debugging, run the app from console to see tracebacks.

## 11. Distribution & sharing

Share the `.py` file or a JSONC snippet. Users drop them into `BackupSeeker/plugins/` and press `Reset`. Consider including a comment header with compatibility notes.

## 12. Troubleshooting

- Plugin not listed: ensure the filename is a valid module name and `get_plugins()` exists (or use the auto-discovery pattern from `TEMPLATE_PLUGIN.py`).
- Import errors: run `python -m BackupSeeker.main` from console to view tracebacks.
- Detection fails: expand contracted paths and verify they exist.

## 13. Future ideas

- Per-plugin settings UI.
- Async hooks for uploads.
- Signed/verified plugins and packaging standard.

## Requesting a scaffolded plugin

If you want maintainers to provide a scaffold, supply: game title, contracted save path examples, optional registry keys, and any special handling notes. Maintainers can respond with a ready-made Python or JSONC entry.

---

Keep plugins lean, transparent, and deterministic. Happy building!
