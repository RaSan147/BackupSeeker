from unittest.mock import MagicMock
import unittest
from pathlib import Path

from BackupSeeker.plugins.base import GamePlugin, plugin_from_json
from BackupSeeker.plugins.TEMPLATE_PLUGIN import TemplatePlugin
from BackupSeeker.plugins.detroit_become_human import DetroitBecomeHumanPlugin
from BackupSeeker.plugin_manager import PluginManager


class TestPluginTemplate(unittest.TestCase):
    def test_default_is_template_is_false(self) -> None:
        # Standard code plugin should default to is_template = False
        detroit_plugin = DetroitBecomeHumanPlugin()
        self.assertFalse(detroit_plugin.is_template)

    def test_template_plugin_is_template_is_true(self) -> None:
        # TemplatePlugin should have is_template = True
        template_plugin = TemplatePlugin()
        self.assertTrue(template_plugin.is_template)

    def test_json_plugin_defaults_to_false(self) -> None:
        # JSON plugin without is_template should default to False
        data = {
            "id": "test_game_json",
            "name": "Test Game",
            "save_sources": [
                {
                    "id": "path_0",
                    "kind": "directory",
                    "paths": ["%USERPROFILE%/Saves"]
                }
            ]
        }
        plugin = plugin_from_json(data)
        self.assertFalse(plugin.is_template)

    def test_json_plugin_with_is_template_true(self) -> None:
        # JSON plugin with is_template explicitly set to True
        data = {
            "id": "test_game_json",
            "name": "Test Game",
            "is_template": True,
            "save_sources": [
                {
                    "id": "path_0",
                    "kind": "directory",
                    "paths": ["%USERPROFILE%/Saves"]
                }
            ]
        }
        plugin = plugin_from_json(data)
        self.assertTrue(plugin.is_template)

    def test_plugin_manager_skips_templates(self) -> None:
        # Set up a PluginManager and mock register plugin
        pm = PluginManager(Path("."))
        
        # Clear available plugins to start clean
        pm.available_plugins.clear()
        
        # Try registering a normal plugin (mocked)
        mock_normal = MagicMock()
        mock_normal.game_id = "normal_game"
        mock_normal.is_template = False
        mock_normal.is_disabled = False
        
        pm._register_plugin(mock_normal, "test_source", [])
        self.assertIn("normal_game", pm.available_plugins)
        
        # Try registering a template plugin (mocked)
        mock_template = MagicMock()
        mock_template.game_id = "template_game"
        mock_template.is_template = True
        mock_template.is_disabled = False
        
        pm._register_plugin(mock_template, "test_source", [])
        self.assertNotIn("template_game", pm.available_plugins)


if __name__ == "__main__":
    unittest.main()
