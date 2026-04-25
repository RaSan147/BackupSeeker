from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class TemplatePlugin(GamePlugin):
    """Plugin template to copy/rename when creating a new game plugin.

    Keep `game_id` stable once released; the UI uses it to link profiles
    back to your plugin. Prefer contracted environment variables in
    ``save_sources`` directory paths (e.g. `%USERPROFILE%`) so profiles are portable.

    JSON snapshot plugins (games.jsonc) embed metadata only; mechanical
    plugins (default `plugin_kind` ``mechanical_python``) can drive backup
    and portable restore with code:

    - ``mechanical_collect_archive_rows`` — optional full control of which
      files go into the archive (return ``None`` for the default walk).
    - ``mechanical_finalize_bundle`` — tweak the bundle dict before write.
    - ``portable_restore(ctx)`` — embedded restore_cli loads your plugin and
      calls this; default runs file unpack + registry prompts from the bundle.
    - ``mechanical_after_app_restore`` — optional post-restore hook in the app.

    For manual plugin list control, define get_plugins() explicitly.
    For auto-discovery, this plugin's class is just enough—no get_plugins needed.
    """
    
    version: str = "1.0.0"  # Update when making plugin changes

    @property
    def game_id(self) -> str:
        return "template_game"

    @property
    def game_name(self) -> str:
        return "Template Game"

    @property
    def save_sources(self) -> List[Dict[str, Any]]:
        # One or more directory sources; multiple paths under the same ``id`` are alternatives (one ZIP root).
        return [
            {
                "id": "path_0",
                "kind": SAVE_KIND_DIRECTORY,
                "paths": ["%USERPROFILE%/Saved Games/TemplateGame"],
            },
        ]

    @property
    def icon(self) -> str:
        """Optional emoji or icon path for the game in the UI."""
        return "🎮"

    def preprocess_backup(self, profile_data: dict) -> dict:
        # Example hook: run before the core backup. You can modify
        # `profile_data` to change `save_path`, `file_patterns`, etc.
        return profile_data

    def postprocess_backup(self, result_data: dict) -> dict:
        # Example hook: run after backup completes. `result_data` may
        # include keys like `backup_path` with the created archive path.
        return result_data


def get_plugins():
    """Return a list of active plugin instances for the loader.
    
    Option 1 (manual—useful for selective loading):
        return [TemplatePlugin()]
    
    Option 2 (auto-discovery—finds all GamePlugin subclasses above):
        return auto_get_plugins()
    """
    # For this template, we show the manual approach:
    return [TemplatePlugin()]
