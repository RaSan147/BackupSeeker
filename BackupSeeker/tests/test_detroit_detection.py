from unittest.mock import patch, MagicMock
from pathlib import Path
from BackupSeeker.plugins.detroit_become_human import DetroitBecomeHumanPlugin


def test_detroit_is_detected_via_stove_manifest():
    plugin = DetroitBecomeHumanPlugin()

    # If nothing exists, it should be False
    with patch("BackupSeeker.core.PathUtils.expand") as mock_expand:
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_expand.return_value = mock_path

        assert not plugin.is_detected()

    # If STOVE manifest exists, it should be True
    with patch("BackupSeeker.core.PathUtils.expand") as mock_expand:
        def expand_side_effect(path_str):
            mock_path = MagicMock()
            if "DETROITPC_IND_6.json" in path_str:
                mock_path.exists.return_value = True
            else:
                mock_path.exists.return_value = False
            return mock_path

        mock_expand.side_effect = expand_side_effect
        assert plugin.is_detected()


def test_detroit_is_detected_via_stove_logs():
    plugin = DetroitBecomeHumanPlugin()

    # If STOVE logs folder exists, it should be True
    with patch("BackupSeeker.core.PathUtils.expand") as mock_expand:
        def expand_side_effect(path_str):
            mock_path = MagicMock()
            if "DETROITPC_IND" in path_str and "logs" in path_str:
                mock_path.exists.return_value = True
            else:
                mock_path.exists.return_value = False
            return mock_path

        mock_expand.side_effect = expand_side_effect
        assert plugin.is_detected()
