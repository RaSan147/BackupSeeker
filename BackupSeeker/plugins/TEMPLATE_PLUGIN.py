from typing import List
from .base import GamePlugin


class TemplatePlugin(GamePlugin):
    """Plugin template to copy/rename when creating a new game plugin.

    Keep `game_id` stable once released; the UI uses it to link profiles
    back to your plugin. Prefer contracted environment variables in
    `save_paths` (e.g. `%USERPROFILE%`) so profiles are portable.
    """

    @property
    def game_id(self) -> str:
        return "template_game"

    @property
    def game_name(self) -> str:
        return "Template Game"

    @property
    def save_paths(self) -> List[str]:
        # Provide one or more candidate paths. The plugin loader will
        # use detection helpers to find the best match on the user's system.
        return [
            "%USERPROFILE%\\Saved Games\\TemplateGame",
        ]

    def preprocess_backup(self, profile_data: dict) -> dict:
        # Example hook: run before the core backup. You can modify
        # `profile_data` to change `save_path`, `file_patterns`, etc.
        return profile_data

    def postprocess_backup(self, result_data: dict) -> dict:
        # Example hook: run after backup completes. `result_data` may
        # include keys like `backup_path` with the created archive path.
        return result_data


def get_plugins():
    """Return a list of active plugin instances for the loader."""
    return [TemplatePlugin()]
