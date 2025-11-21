
Plugin Development Guide — BackupSeeker
======================================

This guide explains how to create, test, and share plugins for BackupSeeker. Two plugin formats are supported:
- Python module plugins placed in `BackupSeeker/plugins/`.
- JSONC descriptor entries in `BackupSeeker/plugins/games.jsonc` (comments with `//` are allowed and stripped at load time).

**1. Where to place plugins**
- Python plugins: `BackupSeeker/plugins/<your_plugin>.py` (module name must be a valid Python identifier).
- JSONC descriptors: add objects to `BackupSeeker/plugins/games.jsonc` or use `games.template.jsonc` as a starting point.

**2. Core concepts**
Plugins expose one or more `GamePlugin` instances describing:
- `game_id`: stable unique identifier (do not change once released).
- `game_name`: user-facing label.
- `save_paths`: list of contracted paths (use env vars like `%USERPROFILE%`).
- Optional `registry_keys` for Windows detection.
- Optional lifecycle hooks to customize backup/restore behavior.

**3. Contracted paths**
Always prefer environment-variable tokens (e.g. `%USERPROFILE%`, `%PUBLIC%`, `$HOME`) instead of absolute paths. The app stores contracted tokens and expands them at runtime for portability.

**4. Registry-based detection (Windows)**
Provide a list of `(registry_path, value_name)` pairs. If the expanded value resolves to an existing folder, detection can succeed.

Example:
```python
@property
def registry_keys(self) -> list[tuple[str, str]]:
    return [
        ("HKEY_LOCAL_MACHINE\\SOFTWARE\\MyGame", "InstallPath"),
    ]
```

**5. Lifecycle hooks**
Hooks receive and return plain dictionaries; return the input unchanged if you don't modify it.
- `preprocess_backup(profile_dict)` — run before backup starts (normalize paths, stage files).
- `postprocess_backup(result_dict)` — runs after ZIP creation (e.g. add hash, upload).
- `preprocess_restore(profile_dict)` — run before restore (create staging dirs).
- `postprocess_restore(result_dict)` — validate restore, cleanup, notify.

**6. Minimal Python plugin example**
Place this file at `BackupSeeker/plugins/mygame.py`:
```python
from typing import List
from .base import GamePlugin

class MyGamePlugin(GamePlugin):
    @property
    def game_id(self) -> str: return "mygame"

    @property
    def game_name(self) -> str: return "My Game"

    @property
    def save_paths(self) -> List[str]:
        return ["%USERPROFILE%\\Saved Games\\MyGame"]

def get_plugins():
    return [MyGamePlugin()]
```
Notes: When your plugin is imported as part of the `BackupSeeker.plugins` package, the relative import `from .base import GamePlugin` works. Alternatively use `from BackupSeeker.plugins.base import GamePlugin`.

**7. Advanced plugin (example postprocess hook)**
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
    def save_paths(self) -> List[str]:
        return ["%USERPROFILE%\\Saved Games\\MyGame"]

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

**8. JSONC descriptor example**
Add an object to the `games.jsonc` array (use `games.template.jsonc` as a scaffold):
```jsonc
{
  "id": "mygame_json",
  "name": "My Game (JSON)",
  "save_paths": ["%USERPROFILE%\\Saved Games\\MyGame"],
  "file_patterns": ["*.sav"],
  "registry_keys": []
}
```

**9. Testing checklist**
1. Launch app: `python -m BackupSeeker.main`
2. Open the Plugin panel in the UI.
3. Click `Reset` to reload Python and JSONC plugins.
4. Use `Auto Detect Installed` to run detection heuristics.
5. Add detected plugin(s) to profiles and run backup/restore flows.
6. Verify Safety archive creation and any hook side-effects (e.g. added hash).

**10. Best practices**
- Keep `game_id` stable once published.
- Prefer contracted env vars for portability.
- Keep plugins minimal and dependency-free where possible.
- For debugging, run the app from console to see tracebacks.

**11. Distribution & sharing**
Share the `.py` file or a JSONC snippet. Users drop them into `BackupSeeker/plugins/` and press `Reset`. Consider including a comment header with compatibility notes.

**12. Troubleshooting**
- Plugin not listed: ensure the filename is a valid module name and `get_plugins()` exists.
- Import errors: run `python -m BackupSeeker.main` from console to view tracebacks.
- Detection fails: expand contracted paths and verify they exist.

**13. Future ideas**
- Per-plugin settings UI.
- Async hooks for uploads.
- Signed/verified plugins and packaging standard.

**Requesting a scaffolded plugin**
If you want maintainers to provide a scaffold, supply: game title, contracted save path examples, optional registry keys, and any special handling notes. Maintainers can respond with a ready-made Python or JSONC entry.

---
Keep plugins lean, transparent, and deterministic. Happy building!
