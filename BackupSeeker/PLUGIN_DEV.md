Plugin Development Guide — BackupSeeker
======================================
This guide covers creating, testing, and publishing plugins. Plugins extend detection and augment backup/restore behavior through simple lifecycle hooks. Two formats are supported: Python module plugins and JSONC descriptors.

1. Plugin Locations
-------------------
- Python: `BackupSeeker/plugins/<your_plugin>.py`
- JSONC: `BackupSeeker/plugins/games.jsonc` (array of objects; supports `//` comments stripped before parsing).

2. Core Concepts
----------------
`GamePlugin` instances describe:
- Identity: `game_id` (stable, unique), `game_name` (user‑facing label).
- Detection: one or more `save_paths` (contracted env vars), optional `registry_keys` for Windows.
- Backup scope: optional `file_patterns` (currently informational; core zips entire folder).
- Lifecycle hooks: pre/post backup & restore dict transformations.

3. Contracted Paths & Portability
---------------------------------
Use environment variables (`%USERPROFILE%`, `%PUBLIC%`, `$HOME`) instead of hard-coded absolute paths. The app stores contracted paths; expansion occurs at runtime (`PathUtils.expand`). Avoid user‑specific fragments in committed plugin code.

4. Registry-Based Detection (Windows)
-------------------------------------
Provide a list of tuples `(rooted_key_path, value_name)` e.g.:
```python
@property
def registry_keys(self) -> list[tuple[str, str]]:
    return [
        ("HKEY_LOCAL_MACHINE\\SOFTWARE\\MyGame", "InstallPath"),
        ("HKEY_CURRENT_USER\\SOFTWARE\\MyGame", "UserPath"),
    ]
```
If any key/value resolves to an existing folder, detection succeeds.

5. Lifecycle Hooks Explained
----------------------------
All hooks receive/return plain dictionaries so you can mutate `save_path` or attach metadata.
- `preprocess_backup(profile_dict)`: Last chance to normalize paths, stage temp files.
- `postprocess_backup(result_dict)`: Runs after successful ZIP creation (`{"backup_path": <str>}`) — add hashes, move files, upload, etc.
- `preprocess_restore(profile_dict)`: Adjust path or create staging directories before restore.
- `postprocess_restore(result_dict)`: Validate restored data, clear temp files, send notifications.
Hooks are optional; return the input unchanged if not used.

6. Minimal Python Plugin Example
--------------------------------
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

7. Advanced Python Plugin (Hooks & Registry)
-------------------------------------------
```python
from typing import List, Dict
from .base import GamePlugin
import hashlib, os

class MyAdvancedPlugin(GamePlugin):
    @property
    def game_id(self) -> str: return "mygame_adv"
    @property
    def game_name(self) -> str: return "My Game (Advanced)"
    @property
    def save_paths(self) -> List[str]: return ["%USERPROFILE%\\Saved Games\\MyGame"]
    @property
    def registry_keys(self) -> List[tuple[str, str]]: return [
        ("HKEY_LOCAL_MACHINE\\SOFTWARE\\MyGame", "InstallPath")
    ]

    def postprocess_backup(self, result_data: Dict) -> Dict:
        # Append a simple SHA256 of the zip for integrity.
        zip_path = result_data.get("backup_path")
        if zip_path and os.path.exists(zip_path):
            h = hashlib.sha256()
            with open(zip_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""): h.update(chunk)
            result_data["sha256"] = h.hexdigest()
        return result_data

def get_plugins():
    return [MyAdvancedPlugin()]
```

8. JSONC Descriptor Example
---------------------------
Add an object to the array in `games.jsonc`:
```jsonc
{
  "id": "mygame_json",
  "name": "My Game (JSON)",
  "save_paths": ["%USERPROFILE%\\Saved Games\\MyGame"],
  "file_patterns": ["*.sav"],
  "registry_keys": []
}
```
The loader removes lines starting with `//` before parsing.

9. Testing Checklist
--------------------
1. Launch app: `python -m BackupSeeker.main`
2. Open Plugin Panel.
3. Click `Reset` (reloads Python + JSONC plugins).
4. Use `🔍 Auto Detect Installed` (detected plugins appear bold).
5. Select plugin(s) → `➕ Add Selected to Profiles`.
6. Perform backup and restore; confirm Safety archive creation.
7. If using hooks, verify expected modifications (e.g., hash added).

10. Best Practices
------------------
- Stability: never change an existing `game_id` — introduce a new plugin.
- Portability: always prefer contracted env vars over absolute user paths.
- Minimalism: implement only required hooks; avoid heavy dependencies.
- Observability: if adding complex logic, log via `print()` for now (future logging surface TBD).
- Security: do not embed secrets or upload data without user consent.

11. Distribution & Sharing
--------------------------
Share the `.py` plugin file or JSONC snippet. Users drop it into `BackupSeeker/plugins/` and press `Reset`. Consider a version comment header for maintenance:
```python
# Plugin: MyAdvancedPlugin v1.2.0
# Compatible: BackupSeeker >=0.3.0
```

12. Troubleshooting
-------------------
- Plugin not listed: filename must be a valid Python identifier; ensure `get_plugins()` exists.
- Import errors: run from console to see tracebacks; temporary syntax issues are ignored silently by the loader.
- Detection fails: verify expanded path exists (`[Environment]::ExpandEnvironmentVariables(path)`).

13. Future Extensions (Ideas)
-----------------------------
- Per-plugin settings surface (custom UI form schema).
- Async hooks for large uploads.
- Signature verification for third-party plugin trust.
- Plugin packaging standard (wheel / zipped bundle).

14. Requesting a Scaffolded Plugin
----------------------------------
Provide: game title, save folder examples (contracted), optional registry keys, special handling notes (encryption, cloud). Maintainers can respond with a ready-made Python or JSONC entry.

---
Keep plugins lean, transparent, and deterministic. Happy building!
