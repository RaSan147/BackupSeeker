from __future__ import annotations

try:
	import winreg
except Exception:  # pragma: no cover - non-Windows environments
	winreg = None
import inspect
import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core import PathUtils, zip_sanitized_key
from .prompt_validation import normalize_validations
from .save_sources import (
	CANDIDACY_ALWAYS,
	CANDIDACY_NO_CANDIDATE_THIS_OR_IDS,
	PROMPT_WHEN_NO_CANDIDATE,
	SAVE_KIND_DIRECTORY,
	flatten_locations_from_sources,
	flatten_paths_from_sources,
	registry_pairs_from_sources,
	sources_from_plugin_dict,
)

if TYPE_CHECKING:
	from ..core import GameProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RestoreInputSpec:
	"""Declarative prompts for bundled portable restore (stdin) or GUI restore/backup."""

	key: str
	prompt: str
	kind: str = "existing_directory"
	example: str = ""
	label: str = ""
	validations: tuple[str, ...] = ()
	candidacy: str = PROMPT_WHEN_NO_CANDIDATE
	candidacy_any_of_ids: tuple[str, ...] = ()


class GamePlugin(ABC):
	"""Base class for all game plugins.

	Subclass this to describe a game's save locations and optional
	lifecycle hooks. Implement required properties and override hooks
	if specialized behavior is needed during backup/restore.
	"""

	version: str = "1.0.0"  # Plugin version for tracking updates

	@property
	@abstractmethod
	def game_id(self) -> str:
		"""Unique identifier for the game."""

	# Runtime-populated fields for plugin asset management. Declared here
	# so static analyzers know these attributes exist when PluginManager
	# assigns to them (e.g. `_saved_icon` and `_icon_source`).
	_saved_icon: str = ""
	_icon_source: str = ""
	_saved_poster: str = ""
	_poster_source: str = ""
	# Set True after PluginManager has run download/copy for icon+poster (lazy).
	_visual_assets_loaded: bool = False

	@property
	@abstractmethod
	def game_name(self) -> str:
		"""Display name for the game."""

	@property
	@abstractmethod
	def save_sources(self) -> list[dict[str, Any]]:
		"""Declarative list of dicts: directory roots, registry probes, optional prompts.

		See :mod:`BackupSeeker.plugins.save_sources`. Derived APIs:
		:meth:`save_locations`, :meth:`save_paths`, :meth:`registry_keys`.
		"""

	@property
	def save_locations(self) -> list[tuple[str, str]]:
		"""Flattened ``(logical id, contracted path)`` from ``directory`` sources only."""

		return flatten_locations_from_sources(self.save_sources)

	@property
	def save_paths(self) -> list[str]:
		"""All directory candidate paths in schema order."""

		return flatten_paths_from_sources(self.save_sources)

	@property
	def file_patterns(self) -> list[str]:
		return ["*"]

	@property
	def registry_keys(self) -> list[tuple[str, str]]:
		return registry_pairs_from_sources(self.save_sources)

	@property
	def backup_registry_values(self) -> bool:
		"""When True, export ``registry_keys`` values into the archive bundle (opt-in)."""

		return False

	@property
	def zip_key_aliases(self) -> dict[str, str]:
		"""Optional logical_key → short tag for ZIP folder names (passed through ``sanitize_location_key``)."""

		return {}

	@property
	def backup_exclude_globs(self) -> list[str]:
		"""Glob patterns (relative POSIX paths) excluded from backup walks."""

		return []

	@property
	def clear_folder_on_restore(self) -> bool:
		"""If True, each save root is removed before unpack. If False, merge (ZIP overwrites paths only)."""

		return True

	@property
	def is_disabled(self) -> bool:
		"""When True, the plugin is loaded but ignored by the system."""

		return False

	@property
	def is_template(self) -> bool:
		"""When True, the plugin is treated as a template and not a real game plugin."""

		return False

	def save_detection_groups(self) -> list[tuple[str, list[str]]]:
		"""``(logical_key, paths…)`` - one group per ``directory`` source ``id``."""

		order: list[str] = []
		buckets: dict[str, list[str]] = {}
		for lk, p in self.save_locations:
			s = (p or "").strip()
			if not s:
				continue
			if lk not in buckets:
				order.append(lk)
				buckets[lk] = []
			buckets[lk].append(s)
		return [(k, buckets[k]) for k in order]

	def iter_detection_contracted_paths(self) -> list[str]:
		"""Flatten :meth:`save_detection_groups` (same order as grouped ``save_locations``)."""

		out: list[str] = []
		for _, plist in self.save_detection_groups():
			out.extend(plist)
		return out

	def save_candidate_root_exists(self) -> bool:
		"""True if any contracted candidate exists as a directory (skip optional install-dir prompts)."""

		for contracted in self.iter_detection_contracted_paths():
			if self._contracted_dir_exists(contracted):
				return True
		return False

	def _contracted_dir_exists(self, contracted: str) -> bool:
		try:
			p = PathUtils.expand(contracted)
		except (OSError, ValueError, KeyError):
			return False
		try:
			return p.exists() and p.is_dir()
		except OSError:
			return False

	def _contracted_save_root_from_pin_entry(self, entry: dict[str, Any], raw_pin: str) -> str | None:
		"""Expand a user-entered contracted path pin to the effective save root.

		If ``directory`` entry includes ``pin_relative_segments`` (POSIX-ish names under the pin),
		those segments are appended to the expanded pin root. Otherwise the pin is the save root.

		The pin itself must resolve to an existing directory.
		"""

		clean = PathUtils.clean_input_path(raw_pin or "")
		if not clean:
			return None
		try:
			base = PathUtils.expand(clean)
		except (OSError, ValueError, KeyError):
			return None
		try:
			if not base.is_dir():
				return None
		except OSError:
			return None

		segs_raw = entry.get("pin_relative_segments")
		dest: Path
		if isinstance(segs_raw, list) and segs_raw:
			parts = [str(x).strip() for x in segs_raw if str(x).strip()]
			dest = base
			for part in parts:
				dest = dest / part
			try:
				dest = dest.resolve(strict=False)
			except (OSError, ValueError):
				dest = Path(base)
				for part in parts:
					dest = dest / part
		else:
			try:
				dest = base.resolve(strict=False)
			except (OSError, ValueError):
				dest = base

		try:
			return PathUtils.contract(str(dest))
		except Exception:
			return None

	@property
	def icon(self) -> str:
		"""Optional icon for the game (emoji or path to icon file)."""
		return ""  # Default empty string

	@property
	def poster(self) -> str:
		"""Optional poster image for the game (URL or path to image file)."""
		return ""  # Default empty string

	# --- Optional lifecycle hooks (override as needed) ---

	def preprocess_backup(self, profile_data: dict) -> dict:
		"""Hook called before a backup starts.

		Can mutate and return a new profile dict (e.g. tweak save_path
		or patterns), or just return the original.
		"""

		return profile_data

	def postprocess_backup(self, result_data: dict) -> dict:
		"""Hook called after a backup finishes successfully.

		Can add metadata, verify results, etc.
		"""

		return result_data

	def preprocess_restore(self, profile_data: dict) -> dict:
		"""Hook called before restore starts."""

		return profile_data

	def postprocess_restore(self, result_data: dict) -> dict:
		"""Hook called after restore completes."""

		return result_data

	def is_detected(self) -> bool:
		"""Return True if the game appears installed on the current system.

		Detection uses two strategies:
		- Presence of configured registry keys (Windows only, checked first)
		- Existence of any `save_paths` after expansion
		"""
		# Check registry first as it's often more definitive of an active install
		if self._check_registry():
			return True
		
		# Check paths (group order when :meth:`save_detection_groups` is set)
		for path in self.iter_detection_contracted_paths():
			try:
				expanded = PathUtils.expand(path)
				if expanded.exists():
					return True
			except (OSError, ValueError, KeyError):
				# Handle malformed paths or unresolvable environment variables
				continue
		return False

	def _check_registry(self) -> bool:
		"""Check if the game is installed via registry keys (Windows only).
		
		Returns False silently if:
		- winreg is unavailable (non-Windows)
		- registry keys are not configured
		- keys don't exist (normal for uninstalled games)
		"""
		if winreg is None:
			return False
		
		for key_path, value_name in self.registry_keys:
			try:
				hkey_str, _, sub_key = key_path.partition('\\')
				hkey = (
					winreg.HKEY_CLASSES_ROOT if hkey_str == "HKEY_CLASSES_ROOT"
					else winreg.HKEY_LOCAL_MACHINE if hkey_str == "HKEY_LOCAL_MACHINE"
					else winreg.HKEY_USERS if hkey_str == "HKEY_USERS"
					else winreg.HKEY_CURRENT_CONFIG if hkey_str == "HKEY_CURRENT_CONFIG"
					else winreg.HKEY_CURRENT_USER
				)
				
				# Try default, 32-bit (WOW6432Node), and 64-bit registry views
				masks = [winreg.KEY_READ]
				if hasattr(winreg, "KEY_WOW64_32KEY"):
					masks.append(winreg.KEY_READ | winreg.KEY_WOW64_32KEY)
				if hasattr(winreg, "KEY_WOW64_64KEY"):
					masks.append(winreg.KEY_READ | winreg.KEY_WOW64_64KEY)

				for access_mask in masks:
					try:
						with winreg.OpenKey(hkey, sub_key, 0, access_mask) as key:
							install_path, _ = winreg.QueryValueEx(key, value_name)
							if install_path:
								p = Path(str(install_path).strip().strip('"'))
								if p.exists():
									return True
					except (FileNotFoundError, OSError):
						continue
			except (FileNotFoundError, OSError, AttributeError, TypeError):
				continue
		
		return False

	def get_detected_install_path(self) -> Path | None:
		"""Return the detected game installation root directory if available on the current machine."""
		if winreg is not None:
			for key_path, value_name in self.registry_keys:
				try:
					hkey_str, _, sub_key = key_path.partition("\\")
					hkey = (
						winreg.HKEY_CLASSES_ROOT if hkey_str == "HKEY_CLASSES_ROOT"
						else winreg.HKEY_LOCAL_MACHINE if hkey_str == "HKEY_LOCAL_MACHINE"
						else winreg.HKEY_USERS if hkey_str == "HKEY_USERS"
						else winreg.HKEY_CURRENT_CONFIG if hkey_str == "HKEY_CURRENT_CONFIG"
						else winreg.HKEY_CURRENT_USER
					)
					masks = [winreg.KEY_READ]
					if hasattr(winreg, "KEY_WOW64_32KEY"):
						masks.append(winreg.KEY_READ | winreg.KEY_WOW64_32KEY)
					if hasattr(winreg, "KEY_WOW64_64KEY"):
						masks.append(winreg.KEY_READ | winreg.KEY_WOW64_64KEY)

					for access_mask in masks:
						try:
							with winreg.OpenKey(hkey, sub_key, 0, access_mask) as key:
								val, _ = winreg.QueryValueEx(key, value_name)
								if val:
									p = Path(str(val).strip().strip('"'))
									if p.is_file():
										return p.parent
									if p.is_dir():
										return p
						except (FileNotFoundError, OSError):
							continue
				except Exception:
					continue
		return None

	def get_detected_path(self) -> str | None:
		"""Return the first `save_paths` entry that exists on disk, or None.

		The returned value is the *contracted* form (e.g. contains environment
		variables). The UI uses this to pre-fill new profiles.
		
		Safely handles malformed environment variables by skipping paths
		that can't be expanded.
		"""
		paths = self.iter_detection_contracted_paths()
		for path in paths:
			try:
				expanded = PathUtils.expand(path)
				if expanded.exists():
					return path
			except (OSError, ValueError, KeyError):
				# Skip paths with unresolvable environment variables
				continue
		
		# Fallback to first path even if it doesn't exist
		return paths[0] if paths else None

	def get_detected_paths(self) -> list[str]:
		"""Return all `save_paths` entries that exist on disk.
		
		Useful for games that split saves across multiple locations.
		Returns contracted form paths (with environment variables).
		"""
		detected = []
		for path in self.iter_detection_contracted_paths():
			try:
				expanded = PathUtils.expand(path)
				if expanded.exists():
					detected.append(path)
			except (OSError, ValueError, KeyError):
				# Skip paths with unresolvable environment variables
				continue
		return detected

	@staticmethod
	def get_codex_path(app_id: str) -> str:
		"""Generate CODEX save path for a game given its Steam AppID."""
		return f"%PUBLIC%/Documents/Steam/CODEX/{app_id}/remote"

	@staticmethod
	def get_tenoke_path(app_id: str) -> str:
		"""Generate TENOKE save path for a game given its Steam AppID."""
		return f"%PUBLIC%/Documents/Steam/TENOKE/{app_id}"

	@staticmethod
	def get_goldberg_path(app_id: str, subfolder: str = "remote") -> str:
		"""Generate Goldberg Steam emulator save path for a given Steam AppID."""
		sub = f"/{subfolder.strip('/')}" if subfolder.strip("/") else ""
		return f"%APPDATA%/Goldberg SteamEmu Saves/{app_id}{sub}"

	@staticmethod
	def get_goldberg_uplay_path(ubisoft_id: str) -> str:
		"""Generate Goldberg Uplay emulator save path for a given Ubisoft Game ID."""
		return f"%APPDATA%/Goldberg UplayEmu Saves/{ubisoft_id}"

	@staticmethod
	def get_goldberg_social_club_path(game_name: str) -> str:
		"""Generate Goldberg Social Club emulator save path for Rockstar titles."""
		return f"%APPDATA%/Goldberg SocialClubEmu Saves/{game_name}"

	@staticmethod
	def get_gse_path(app_id: str) -> str:
		"""Generate GSE / Hydra saves path for a given Steam AppID."""
		return f"%APPDATA%/GSE Saves/{app_id}"

	@staticmethod
	def get_rune_path(app_id: str, subfolder: str = "remote") -> str:
		"""Generate RUNE save path for a given Steam AppID."""
		sub = f"/{subfolder.strip('/')}" if subfolder.strip("/") else ""
		return f"%APPDATA%/RUNE/{app_id}{sub}"

	@staticmethod
	def get_flt_path(app_id: str, subfolder: str = "remote") -> str:
		"""Generate FairLight (FLT) save path for a given Steam AppID."""
		sub = f"/{subfolder.strip('/')}" if subfolder.strip("/") else ""
		return f"%APPDATA%/FLT/{app_id}{sub}"

	@staticmethod
	def get_empress_path(app_id: str, subfolder: str = "remote") -> str:
		"""Generate EMPRESS save path for a given Steam AppID."""
		sub = f"/{subfolder.strip('/')}" if subfolder.strip("/") else ""
		return f"%APPDATA%/EMPRESS/{app_id}{sub}"

	@staticmethod
	def get_cpy_path(app_id: str) -> str:
		"""Generate CPY save path for a given Steam AppID."""
		return f"%USERPROFILE%/Documents/CPY_SAVES/Player/{app_id}"

	@staticmethod
	def get_nemirtingas_paths(app_id: str) -> list[str]:
		"""Generate Nemirtingas SteamEmu save paths for a given Steam AppID."""
		return [
			f"%APPDATA%/NemirtingasSteamEmu/{app_id}",
			f"%APPDATA%/Nemirtingas/{app_id}",
		]

	@staticmethod
	def get_smart_steam_emu_path(app_id: str) -> str:
		"""Generate SmartSteamEmu save path for a given Steam AppID."""
		return f"%APPDATA%/SmartSteamEmu/{app_id}"

	@staticmethod
	def get_onlinefix_path(app_id: str) -> str:
		"""Generate OnlineFix save path for a given Steam AppID."""
		return f"%PUBLIC%/Documents/OnlineFix/{app_id}"

	@staticmethod
	def get_steam_install_path() -> Path | None:
		"""Return the detected Steam install directory if available on Windows."""
		if winreg is not None:
			for hive, subkey, val_name in [
				(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
				(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
				(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
			]:
				try:
					with winreg.OpenKey(hive, subkey) as k:
						val, _ = winreg.QueryValueEx(k, val_name)
						if val:
							p = Path(str(val))
							if p.exists() and p.is_dir():
								return p
				except Exception:
					pass
		for default_path in [
			r"%PROGRAMFILES(X86)%/Steam",
			r"%PROGRAMFILES%/Steam",
			r"%LOCALAPPDATA%/Steam",
		]:
			try:
				exp = PathUtils.expand(default_path)
				if exp.exists() and exp.is_dir():
					return exp
			except Exception:
				pass
		return None

	@classmethod
	def get_steam_library_paths(cls) -> list[Path]:
		"""Parse Steam's libraryfolders.vdf to find all Steam library root folders across all drives."""
		steam_root = cls.get_steam_install_path()
		if not steam_root:
			return []

		libraries: list[Path] = [steam_root]
		vdf_path = steam_root / "steamapps" / "libraryfolders.vdf"
		if not vdf_path.exists():
			vdf_path = steam_root / "config" / "config.vdf"

		if vdf_path.exists():
			try:
				import re
				with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
					content = f.read()
				for match in re.finditer(r'"path"\s*"([^"]+)"', content, re.IGNORECASE):
					raw_p = match.group(1).replace("\\\\", "\\")
					lib_p = Path(raw_p)
					if lib_p.exists() and lib_p.is_dir() and lib_p not in libraries:
						libraries.append(lib_p)
			except Exception:
				pass

		return libraries

	@classmethod
	def get_steam_app_install_path(cls, app_id: str) -> Path | None:
		"""Return the exact installation path of a Steam game given its AppID by checking app manifests."""
		import re
		app_id_str = str(app_id).strip()
		manifest_name = f"appmanifest_{app_id_str}.acf"

		for lib in cls.get_steam_library_paths():
			manifest_file = lib / "steamapps" / manifest_name
			if manifest_file.exists():
				try:
					with open(manifest_file, "r", encoding="utf-8", errors="ignore") as f:
						content = f.read()
					m_install = re.search(r'"installdir"\s*"([^"]+)"', content, re.IGNORECASE)
					if m_install:
						folder_name = m_install.group(1).strip()
						game_dir = lib / "steamapps" / "common" / folder_name
						if game_dir.exists() and game_dir.is_dir():
							return game_dir
				except Exception:
					pass

		# Fallback: check Windows registry for Steam App uninstaller
		if winreg is not None:
			for sub_key in (
				rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {app_id_str}",
				rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {app_id_str}",
			):
				masks = [winreg.KEY_READ]
				if hasattr(winreg, "KEY_WOW64_32KEY"):
					masks.append(winreg.KEY_READ | winreg.KEY_WOW64_32KEY)
				for access in masks:
					try:
						with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_key, 0, access) as k:
							val, _ = winreg.QueryValueEx(k, "InstallLocation")
							if val:
								p = Path(str(val).strip().strip('"'))
								if p.exists() and p.is_dir():
									return p
					except Exception:
						continue
		return None

	@classmethod
	def is_steam_app_installed(cls, app_id: str) -> bool:
		"""Check whether a Steam app is installed on the machine."""
		return cls.get_steam_app_install_path(app_id) is not None

	@classmethod
	def get_gog_install_path(cls, gog_id: str) -> Path | None:
		"""Query GOG registry to find the game installation directory."""
		if winreg is None:
			return None
		gog_id_str = str(gog_id).strip()
		subkeys = [
			rf"SOFTWARE\GOG.com\Games\{gog_id_str}",
			rf"SOFTWARE\WOW6432Node\GOG.com\Games\{gog_id_str}",
			rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{gog_id_str}_is1",
			rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{gog_id_str}_is1",
		]
		for sub_key in subkeys:
			masks = [winreg.KEY_READ]
			if hasattr(winreg, "KEY_WOW64_32KEY"):
				masks.append(winreg.KEY_READ | winreg.KEY_WOW64_32KEY)
			for access in masks:
				try:
					with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_key, 0, access) as k:
						for val_name in ("path", "InstallLocation", "PATH", "workingDir"):
							try:
								val, _ = winreg.QueryValueEx(k, val_name)
								if val:
									p = Path(str(val).strip().strip('"'))
									if p.exists() and p.is_dir():
										return p
							except Exception:
								continue
				except Exception:
					continue
		return None

	@classmethod
	def get_epic_install_path(cls, *app_names: str) -> Path | None:
		"""Query Epic Games Launcher manifests to retrieve the installation directory."""
		import json
		manifest_dir = PathUtils.expand("%PROGRAMDATA%/Epic/EpicGamesLauncher/Data/Manifests")
		if not manifest_dir.exists() or not manifest_dir.is_dir():
			return None

		search_set = {n.strip().lower() for n in app_names if n.strip()}
		try:
			for item_file in manifest_dir.glob("*.item"):
				try:
					with open(item_file, "r", encoding="utf-8", errors="ignore") as f:
						data = json.load(f)
					app_name = str(data.get("AppName") or "").strip().lower()
					disp_name = str(data.get("DisplayName") or "").strip().lower()
					main_name = str(data.get("MainGameAppName") or "").strip().lower()
					if app_name in search_set or disp_name in search_set or main_name in search_set:
						inst_loc = data.get("InstallLocation")
						if inst_loc:
							p = Path(str(inst_loc).strip().strip('"'))
							if p.exists() and p.is_dir():
								return p
				except Exception:
					continue
		except Exception:
			pass
		return None

	@classmethod
	def get_ubisoft_install_path(cls, ubisoft_id: str) -> Path | None:
		"""Query Ubisoft Connect registry keys for game installation directory."""
		if winreg is None:
			return None
		u_id = str(ubisoft_id).strip()
		subkeys = [
			rf"SOFTWARE\Ubisoft\Launcher\Installs\{u_id}",
			rf"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs\{u_id}",
		]
		for sub_key in subkeys:
			masks = [winreg.KEY_READ]
			if hasattr(winreg, "KEY_WOW64_32KEY"):
				masks.append(winreg.KEY_READ | winreg.KEY_WOW64_32KEY)
			for access in masks:
				try:
					with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_key, 0, access) as k:
						val, _ = winreg.QueryValueEx(k, "InstallDir")
						if val:
							p = Path(str(val).strip().strip('"'))
							if p.exists() and p.is_dir():
								return p
				except Exception:
					continue
		return None

	@classmethod
	def get_ubisoft_save_paths(cls, ubisoft_id: str) -> list[str]:
		"""Find Ubisoft Game Launcher save directories for a given game ID."""
		out: list[str] = []
		u_id = str(ubisoft_id).strip()
		root_dir = PathUtils.expand("%LOCALAPPDATA%/Ubisoft Game Launcher/savegames")
		if root_dir.exists() and root_dir.is_dir():
			try:
				for account_dir in root_dir.iterdir():
					if account_dir.is_dir() and account_dir.name not in ("0", "anonymous"):
						game_save_dir = account_dir / u_id
						if game_save_dir.exists() and game_save_dir.is_dir():
							out.append(PathUtils.contract(str(game_save_dir)))
				if not out:
					for account_dir in root_dir.iterdir():
						if account_dir.is_dir() and account_dir.name not in ("0", "anonymous"):
							out.append(PathUtils.contract(str(account_dir / u_id)))
			except Exception:
				pass
		return out

	@classmethod
	def get_steam_userdata_paths(cls, app_id: str, subfolder: str = "remote") -> list[str]:
		"""Scan and return existing Steam userdata save directories for a given AppID."""
		out: list[str] = []
		steam_dir = cls.get_steam_install_path()
		if not steam_dir:
			return out
		userdata_dir = steam_dir / "userdata"
		if not userdata_dir.exists() or not userdata_dir.is_dir():
			return out
		try:
			for user_folder in userdata_dir.iterdir():
				if not user_folder.is_dir() or user_folder.name in ("0", "anonymous"):
					continue
				app_save_dir = user_folder / str(app_id) / subfolder if subfolder else user_folder / str(app_id)
				if app_save_dir.exists() and app_save_dir.is_dir():
					out.append(PathUtils.contract(str(app_save_dir)))
		except Exception:
			pass
		return out

	@classmethod
	def get_all_steam_save_paths(cls, app_id: str, subfolder: str = "remote") -> list[str]:
		"""Return candidate save paths across Steam userdata and all major emulators."""
		paths: list[str] = []
		paths.extend(cls.get_steam_userdata_paths(app_id, subfolder))
		paths.append(cls.get_codex_path(app_id))
		paths.append(cls.get_codex_path(app_id).replace("/remote", ""))
		paths.append(cls.get_tenoke_path(app_id))
		paths.append(f"{cls.get_tenoke_path(app_id)}/remote")
		paths.append(cls.get_goldberg_path(app_id, subfolder))
		paths.append(cls.get_goldberg_path(app_id, ""))
		paths.append(cls.get_gse_path(app_id))
		paths.append(cls.get_rune_path(app_id, subfolder))
		paths.append(cls.get_rune_path(app_id, ""))
		paths.append(cls.get_flt_path(app_id, subfolder))
		paths.append(cls.get_flt_path(app_id, ""))
		paths.append(cls.get_empress_path(app_id, subfolder))
		paths.append(cls.get_empress_path(app_id, ""))
		paths.append(cls.get_cpy_path(app_id))
		paths.extend(cls.get_nemirtingas_paths(app_id))
		paths.append(cls.get_smart_steam_emu_path(app_id))
		paths.append(cls.get_onlinefix_path(app_id))
		return paths

	@classmethod
	def get_named_steam_emulator_sources(cls, app_id: str, subfolder: str = "remote") -> list[dict[str, Any]]:
		"""Return distinct, named save source entries for Steam userdata and all major emulators."""
		sources: list[dict[str, Any]] = []

		# 1. Official Steam Userdata
		steam_paths = cls.get_steam_userdata_paths(app_id, subfolder)
		steam_root = cls.get_steam_install_path()
		fallback_paths: list[str] = []
		if steam_paths:
			fallback_paths = steam_paths
		elif steam_root:
			fallback_paths = [PathUtils.contract(str(steam_root / "userdata" / "default" / str(app_id) / subfolder)).rstrip("/\\")]
		else:
			fallback_paths = [f"%PROGRAMFILES(X86)%/Steam/userdata/default/{app_id}/{subfolder}".rstrip("/\\")]

		sources.append({
			"id": "steam_userdata",
			"label": "Steam Official (userdata)",
			"kind": SAVE_KIND_DIRECTORY,
			"paths": fallback_paths,
		})

		# 2. CODEX / DODI Repack
		codex_root = cls.get_codex_path(app_id).replace("/remote", "")
		sources.append({
			"id": "codex_dodi",
			"label": "CODEX / DODI Repack",
			"kind": SAVE_KIND_DIRECTORY,
			"paths": [cls.get_codex_path(app_id), codex_root],
		})

		# 3. TENOKE Repack
		sources.append({
			"id": "tenoke",
			"label": "TENOKE Repack",
			"kind": SAVE_KIND_DIRECTORY,
			"paths": [cls.get_tenoke_path(app_id), f"{cls.get_tenoke_path(app_id)}/remote"],
		})

		# 4. Goldberg Steam Emulator
		goldberg_sub = cls.get_goldberg_path(app_id, subfolder)
		goldberg_root = cls.get_goldberg_path(app_id, "")
		sources.append({
			"id": "goldberg_emu",
			"label": "Goldberg Steam Emulator",
			"kind": SAVE_KIND_DIRECTORY,
			"paths": [goldberg_sub, goldberg_root] if goldberg_sub != goldberg_root else [goldberg_root],
		})

		# 5. GSE / Hydra
		sources.append({
			"id": "gse_hydra",
			"label": "GSE / Hydra Saves",
			"kind": SAVE_KIND_DIRECTORY,
			"paths": [cls.get_gse_path(app_id)],
		})

		# 6. RUNE Repack
		rune_sub = cls.get_rune_path(app_id, subfolder)
		rune_root = cls.get_rune_path(app_id, "")
		sources.append({
			"id": "rune",
			"label": "RUNE Repack",
			"kind": SAVE_KIND_DIRECTORY,
			"paths": [rune_sub, rune_root] if rune_sub != rune_root else [rune_root],
		})

		# 7. FairLight (FLT) Repack
		flt_sub = cls.get_flt_path(app_id, subfolder)
		flt_root = cls.get_flt_path(app_id, "")
		sources.append({
			"id": "flt",
			"label": "FairLight (FLT) Repack",
			"kind": SAVE_KIND_DIRECTORY,
			"paths": [flt_sub, flt_root] if flt_sub != flt_root else [flt_root],
		})

		# 8. EMPRESS Repack
		sources.append({
			"id": "empress",
			"label": "EMPRESS Repack",
			"kind": SAVE_KIND_DIRECTORY,
			"paths": [
				cls.get_empress_path(app_id, subfolder),
				cls.get_empress_path(app_id, ""),
				f"%PUBLIC%/Documents/EMPRESS/{app_id}/{subfolder}".rstrip("/\\"),
				f"%PUBLIC%/Documents/EMPRESS/{app_id}".rstrip("/\\"),
			],
		})

		# 9. CPY Repack
		sources.append({
			"id": "cpy",
			"label": "CPY Repack",
			"kind": SAVE_KIND_DIRECTORY,
			"paths": [
				cls.get_cpy_path(app_id),
				f"%USERPROFILE%/Documents/CPY_SAVES/{app_id}",
			],
		})

		# 10. Nemirtingas Steam Emu
		sources.append({
			"id": "nemirtingas",
			"label": "Nemirtingas Steam Emu",
			"kind": SAVE_KIND_DIRECTORY,
			"paths": cls.get_nemirtingas_paths(app_id),
		})

		# 11. SmartSteamEmu
		sources.append({
			"id": "smart_steam_emu",
			"label": "SmartSteamEmu Saves",
			"kind": SAVE_KIND_DIRECTORY,
			"paths": [cls.get_smart_steam_emu_path(app_id)],
		})

		# 12. OnlineFix
		sources.append({
			"id": "onlinefix",
			"label": "OnlineFix Saves",
			"kind": SAVE_KIND_DIRECTORY,
			"paths": [cls.get_onlinefix_path(app_id)],
		})

		return sources

	@classmethod
	def get_muicache_install_path(cls, exe_names: list[str]) -> Path | None:
		"""Query Windows MuiCache registry to find where an executable was launched from.

		Requires zero disk walking; instantly locates games moved via external SSD.
		"""
		if winreg is None:
			return None
		exe_set = {n.lower().strip() for n in exe_names if n.strip()}
		subkeys = [
			r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache",
			r"Software\Microsoft\Windows\CurrentVersion\Explorer\FeatureUsage\AppSwitched",
		]
		for sub_key in subkeys:
			try:
				with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as k:
					idx = 0
					while True:
						try:
							val_name, _, _ = winreg.EnumValue(k, idx)
							idx += 1
							clean_path = val_name.split(".FriendlyAppName")[0].split(".ApplicationCompany")[0].strip('" ')
							p = Path(clean_path)
							if p.name.lower() in exe_set and p.exists():
								parent = p.parent
								if parent.name.lower() in ("win64", "binaries", "shipping", "x64"):
									if parent.parent.name.lower() in ("binaries", "game"):
										return parent.parent.parent
									return parent.parent
								return parent
						except OSError:
							break
			except Exception:
				continue
		return None

	@classmethod
	def find_smart_install_candidates(
		cls,
		folder_names: list[str],
		exe_names: list[str] | None = None,
		steam_app_id: str | None = None,
	) -> list[Path]:
		"""Find game installation folders without brute-force directory walking.

		Uses targeted lookups:
		1. Steam manifest check
		2. Windows MuiCache execution history (instant for external SSDs)
		3. Shallow top-level check on active drives (depth 1 & 2 only)
		"""
		results: list[Path] = []
		seen: set[str] = set()

		def _add(p: Path | None) -> None:
			if p and p.exists() and p.is_dir():
				norm = str(p.resolve()).lower()
				if norm not in seen:
					seen.add(norm)
					results.append(p.resolve())

		if steam_app_id:
			_add(cls.get_steam_app_install_path(steam_app_id))

		if exe_names:
			_add(cls.get_muicache_install_path(exe_names))

		# Shallow check on mounted drive roots (depth 1 and 2 only)
		drives: list[str] = ["C:/", "D:/", "E:/", "F:/", "G:/"]
		if platform.system().lower() == "windows":
			try:
				import string
				from ctypes import windll  # type: ignore[attr-defined]
				bitmask = windll.kernel32.GetLogicalDrives()
				detected_drives = []
				for letter in string.ascii_uppercase:
					if bitmask & 1:
						detected_drives.append(f"{letter}:/")
					bitmask >>= 1
				if detected_drives:
					drives = detected_drives
			except Exception:
				pass

		for d in drives:
			drive_path = Path(d)
			if not drive_path.exists():
				continue
			for fn in folder_names:
				_add(drive_path / fn)
				_add(drive_path / "Games" / fn)
				_add(drive_path / "SteamLibrary" / "steamapps" / "common" / fn)

		return results

	@classmethod
	def detect_crack_signatures(cls, game_dir: Path | str) -> dict[str, Any]:
		"""Inspect a game directory for crack / emulator signatures and return detected metadata."""
		p = Path(game_dir)
		if not p.exists() or not p.is_dir():
			return {"detected": False, "crack_name": "None", "is_portable": False}

		# Check Goldberg Steam Emulator
		steam_settings = p / "steam_settings"
		if not steam_settings.exists():
			for sub in p.glob("**/steam_settings"):
				if sub.is_dir():
					steam_settings = sub
					break

		if steam_settings.exists() and steam_settings.is_dir():
			is_local = (steam_settings / "local_save.txt").exists() or (p / "local_save.txt").exists()
			return {
				"detected": True,
				"crack_name": "Goldberg Steam Emulator",
				"is_portable": is_local,
				"save_hint": "Local game folder" if is_local else "AppData Goldberg",
			}

		for ini_path in [p / "steam_emu.ini", *p.glob("**/steam_emu.ini")]:
			if ini_path.is_file():
				try:
					content = ini_path.read_text(encoding="utf-8", errors="ignore")
					if "TENOKE" in content:
						crack = "TENOKE Repack"
					elif "RUNE" in content:
						crack = "RUNE Repack"
					else:
						crack = "CODEX / DODI Repack"
					return {"detected": True, "crack_name": crack, "is_portable": False}
				except Exception:
					pass

		for flt_path in [p / "flt.ini", *p.glob("**/flt.ini")]:
			if flt_path.is_file():
				return {"detected": True, "crack_name": "FairLight (FLT)", "is_portable": False}

		for ali_path in [p / "ALI213.ini", *p.glob("**/ALI213.ini")]:
			if ali_path.is_file():
				return {"detected": True, "crack_name": "ALI213", "is_portable": True}

		for threedm_path in [p / "3DMGAME.ini", *p.glob("**/3DMGAME.ini")]:
			if threedm_path.is_file():
				return {"detected": True, "crack_name": "3DMGAME", "is_portable": True}

		return {"detected": False, "crack_name": "None", "is_portable": False}


	@classmethod
	def get_unity_install_path_from_log(cls, company: str, product: str) -> Path | None:
		"""Inspect Unity's Player.log, Player-prev.log, or output_log.txt to extract the game install folder.

		Searches for Mono/IL2CPP paths logged by the Unity engine on launch:
		- ``Mono path[0] = '<Install>/<DataDir>/Managed'``
		- ``Mono config path = '<Install>/MonoBleedingEdge/etc'``
		- ``Loading player data from <Install>/<DataDir>/data.unity3d``
		- ``[Subsystems] Discovering subsystems at path <Install>/<DataDir>/...``
		Returns the extracted Path if parsed, or None.
		"""
		import re

		def _extract_install_root(raw_path_str: str) -> Path | None:
			raw = Path(raw_path_str.strip().strip("'\""))
			for candidate in [raw, *raw.parents]:
				if candidate.name.endswith("_Data") or candidate.name == "MonoBleedingEdge":
					return candidate.parent
			if len(raw.parents) >= 2:
				return raw.parents[1]
			return raw.parent if raw.parent != raw else None

		log_dir = PathUtils.expand(f"%USERPROFILE%/AppData/LocalLow/{company}/{product}")
		if not log_dir.exists() or not log_dir.is_dir():
			return None

		for log_name in ("Player.log", "Player-prev.log", "output_log.txt"):
			log_path = log_dir / log_name
			if not log_path.exists() or not log_path.is_file():
				continue
			try:
				with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
					for _ in range(200):
						line = f.readline()
						if not line:
							break
						m_mono = re.search(r"Mono path\[0\]\s*=\s*'([^']+)'", line)
						if m_mono:
							root = _extract_install_root(m_mono.group(1))
							if root:
								return root
						m_cfg = re.search(r"Mono config path\s*=\s*'([^']+)'", line)
						if m_cfg:
							root = _extract_install_root(m_cfg.group(1))
							if root:
								return root
						m_data = re.search(r"Loading player data from\s+(.+)", line)
						if m_data:
							root = _extract_install_root(m_data.group(1))
							if root:
								return root
						m_sub = re.search(r"\[Subsystems\] Discovering subsystems at path\s+(.+)", line)
						if m_sub:
							root = _extract_install_root(m_sub.group(1))
							if root:
								return root
			except Exception:
				continue
		return None

	@classmethod
	def is_unity_game_installed(cls, company: str, product: str) -> bool | None:
		"""Check whether a Unity game is installed by verifying the path logged in Player.log.

		Returns:
			True if Player.log exists and the referenced install directory exists on disk.
			False if Player.log exists with an install path that no longer exists on disk.
			None if no Player.log could be found or parsed.
		"""
		install_path = cls.get_unity_install_path_from_log(company, product)
		if install_path is not None:
			try:
				return install_path.exists() and install_path.is_dir()
			except Exception:
				return False
		return None

	def to_profile(self) -> dict:
		"""Return fields for adding a profile; config stores only references.

		Display metadata lives on the plugin; persisted rows keep ``plugin_id``
		and ``plugin_version``. Save paths always come from the plugin at runtime.
		"""
		return {
			"plugin_id": self.game_id,
			"plugin_version": self.version,
		}

	@property
	def plugin_kind(self) -> str:
		"""``mechanical_python`` (code module) vs ``json_snapshot`` (``games.jsonc``)."""

		return "mechanical_python"

	def mechanical_finalize_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
		"""Optional last edit to the bundle dict before write (metadata, extra keys)."""

		return bundle

	def mechanical_collect_archive_rows(
		self,
		profile_dict: dict[str, Any],
		*,
		patterns: list[str],
		exclude_globs: list[str],
	) -> list[tuple[str, Path, Path]] | None:
		"""Return ``None`` for default directory walk; else explicit archive rows."""

		return None

	def _prompt_mode(self, pr: Mapping[str, Any]) -> str:
		m = str(pr.get("candidacy") or "").strip()
		if m:
			return m
		m = str(pr.get("when") or "").strip()
		return m or PROMPT_WHEN_NO_CANDIDATE

	def _directory_entry_has_disk_candidate(self, entry: dict[str, Any]) -> bool:
		paths = [str(x).strip() for x in (entry.get("paths") or []) if str(x).strip()]
		return bool(paths) and any(self._contracted_dir_exists(p) for p in paths)

	def _should_omit_restore_prompt(self, entry: dict[str, Any], pr: Mapping[str, Any]) -> bool:
		"""True → skip this prompt in :meth:`restore_input_specs` (disk / policy satisfied)."""

		mode = self._prompt_mode(pr)
		if mode == CANDIDACY_ALWAYS:
			return False
		if mode == CANDIDACY_NO_CANDIDATE_THIS_OR_IDS:
			if self._directory_entry_has_disk_candidate(entry):
				return True
			raw_ids = pr.get("candidacy_any_of_ids") or pr.get("or_directory_ids") or []
			if isinstance(raw_ids, str):
				raw_ids = [raw_ids]
			for oid in [str(x).strip() for x in raw_ids if str(x).strip()]:
				for e2 in self.save_sources:
					if str(e2.get("id") or "").strip() != oid:
						continue
					if e2.get("kind") != SAVE_KIND_DIRECTORY:
						continue
					if self._directory_entry_has_disk_candidate(e2):
						return True
			return False
		if mode in (PROMPT_WHEN_NO_CANDIDATE, "no_candidate_exists"):
			return self._directory_entry_has_disk_candidate(entry)
		return False

	def _restore_spec_from_prompt_entry(self, entry: dict[str, Any], pr: Mapping[str, Any]) -> RestoreInputSpec | None:
		if not isinstance(pr, dict):
			return None
		ik = str(pr.get("input_key") or "").strip()
		msg = str(pr.get("message") or "").strip()
		if not ik or not msg:
			return None
		kind = str(pr.get("input_kind") or "existing_directory").strip()
		ex = str(pr.get("example") or "").strip()
		lb = str(pr.get("label") or "").strip()
		vals = normalize_validations(pr.get("validations"))
		cm = self._prompt_mode(pr)
		raw_ids = pr.get("candidacy_any_of_ids") or pr.get("or_directory_ids") or []
		if isinstance(raw_ids, str):
			raw_ids = [raw_ids]
		c_any = tuple(str(x).strip() for x in raw_ids if str(x).strip())
		return RestoreInputSpec(
			key=ik,
			prompt=msg,
			kind=kind,
			example=ex,
			label=lb,
			validations=vals,
			candidacy=cm,
			candidacy_any_of_ids=c_any,
		)

	def restore_input_specs(self) -> list[RestoreInputSpec]:
		"""Prompts from ``directory`` entries subject to ``prompt.candidacy`` / ``prompt.when``."""

		specs: list[RestoreInputSpec] = []
		for entry in self.save_sources:
			if entry.get("kind") != SAVE_KIND_DIRECTORY:
				continue
			pr = entry.get("prompt")
			if not isinstance(pr, dict):
				continue
			spec = self._restore_spec_from_prompt_entry(entry, pr)
			if spec is None:
				continue
			if self._should_omit_restore_prompt(entry, pr):
				continue
			specs.append(spec)
		return specs

	def restore_input_specs_for_review(self) -> list[RestoreInputSpec]:
		"""Same definitions as :meth:`restore_input_specs`, but ignores on-disk omit rules (GUI review)."""

		specs: list[RestoreInputSpec] = []
		for entry in self.save_sources:
			if entry.get("kind") != SAVE_KIND_DIRECTORY:
				continue
			pr = entry.get("prompt")
			if not isinstance(pr, dict):
				continue
			spec = self._restore_spec_from_prompt_entry(entry, pr)
			if spec is None:
				continue
			specs.append(spec)
		return specs

	def primary_path_editor_hints(self) -> tuple[str, str] | None:
		"""Optional ``(heading, placeholder)`` for the profile-editor path row from ``save_sources`` prompts."""

		pk_raw = self.profile_primary_input_key()
		pk = pk_raw.strip() if isinstance(pk_raw, str) else ""
		if not pk:
			return None
		for entry in self.save_sources:
			if entry.get("kind") != SAVE_KIND_DIRECTORY:
				continue
			pr = entry.get("prompt")
			if not isinstance(pr, dict):
				continue
			if str(pr.get("input_key") or "").strip() != pk:
				continue
			lb = str(pr.get("editor_label") or "").strip()
			ph = str(pr.get("editor_placeholder") or "").strip()
			if lb and ph:
				return (lb, ph)
		return None

	def profile_primary_input_key(self) -> str | None:
		"""First ``prompt.input_key`` under a ``directory`` entry (persisted as ``plugin_inputs[input_key]``).

		Use the same string as that entry's ``id`` when the profile pins a folder for that root.
		"""

		for entry in self.save_sources:
			if entry.get("kind") != SAVE_KIND_DIRECTORY:
				continue
			pr = entry.get("prompt")
			if not isinstance(pr, dict):
				continue
			ik = str(pr.get("input_key") or "").strip()
			if ik:
				return ik
		return None

	def profile_restore_input_values(self, profile: GameProfile) -> dict[str, str]:
		"""Values for ``restore_input_specs`` keys stored on the profile (single primary pin by default)."""

		pk_raw = self.profile_primary_input_key()
		pk = pk_raw.strip() if isinstance(pk_raw, str) else ""
		if not pk:
			return {}
		pi = getattr(profile, "plugin_inputs", None) or {}
		raw = (pi.get(pk) or "").strip()
		return {pk: raw} if raw else {}

	def persist_restore_input_value(self, profile: GameProfile, key: str, value: str) -> None:
		"""Store interactive/GUI values under :attr:`GameProfile.plugin_inputs`."""

		clean = PathUtils.clean_input_path(value or "")
		contracted = PathUtils.contract(clean) if clean else ""
		if contracted:
			profile.plugin_inputs[key] = contracted
		else:
			profile.plugin_inputs.pop(key, None)

	def save_locations_for_profile(self, profile: GameProfile) -> list[tuple[str, str]] | None:
		"""Derive save roots from ``plugin_inputs`` using ``directory`` ``id`` keys and optional ``pin_relative_segments``."""

		pi = getattr(profile, "plugin_inputs", None) or {}
		out: list[tuple[str, str]] = []
		for entry in self.save_sources:
			if entry.get("kind") != SAVE_KIND_DIRECTORY:
				continue
			eid = str(entry.get("id") or "").strip() or "path_0"
			raw = (pi.get(eid) or "").strip()
			if not raw:
				continue
			cp = self._contracted_save_root_from_pin_entry(entry, raw)
			if cp:
				out.append((eid, cp))
		return out if out else None

	def bundle_root_overrides_from_restore_inputs(self, inputs: Mapping[str, str]) -> dict[str, str] | None:
		"""Map bundle ZIP ``sanitized_key`` → contracted save root from stdin/GUI inputs (declarative)."""

		out: dict[str, str] = {}
		for entry in self.save_sources:
			if entry.get("kind") != SAVE_KIND_DIRECTORY:
				continue
			eid = str(entry.get("id") or "").strip() or "path_0"
			raw = (inputs.get(eid) or "").strip()
			if not raw:
				continue
			cp = self._contracted_save_root_from_pin_entry(entry, raw)
			if not cp:
				continue
			sk = zip_sanitized_key(eid, self)
			out[sk] = cp
		return out if out else None

	def portable_restore(self, ctx: Any) -> None:
		"""Portable extract-and-restore only: optional stdin inputs, then default file + registry prompts."""

		specs = self.restore_input_specs()
		inputs = ctx.collect_restore_inputs(self) if specs else {}
		overrides = self.bundle_root_overrides_from_restore_inputs(inputs) if specs else None
		if overrides:
			ctx.apply_bundle_root_paths(overrides)
		ctx.run_default_file_and_registry()

	def mechanical_after_app_restore(self, info: dict[str, Any]) -> None:
		"""Called after a successful GUI restore (files + optional registry)."""


	def to_snapshot_dict(self) -> dict[str, Any]:
		"""JSON-safe subset embedded in bundle.json (no executable hook code)."""

		return {
			"game_id": self.game_id,
			"version": self.version,
			"_kind": self.plugin_kind,
			"save_sources": list(self.save_sources),
			"file_patterns": list(self.file_patterns),
			"clear_folder_on_restore": self.clear_folder_on_restore,
			"backup_registry_values": bool(self.backup_registry_values),
			"zip_key_aliases": dict(self.zip_key_aliases or {}),
			"backup_exclude_globs": list(self.backup_exclude_globs or []),
		}

	def extra_readme_lines(self) -> list[str]:
		"""Extra lines appended to archive README (short plugin-specific notes)."""

		return []


def plugin_from_json(data: dict) -> GamePlugin:
	"""Create a simple data-driven plugin from a JSONC-like descriptor.

	Requires ``save_sources`` (list of dicts); see :mod:`BackupSeeker.plugins.save_sources`.
	"""

	class JsonGamePlugin(GamePlugin):
		def __init__(self, d: dict) -> None:
			self._data = d

		@property
		def plugin_kind(self) -> str:
			return "json_snapshot"

		@property
		def version(self) -> str:
			return str(self._data.get("version", "1.0.0"))

		@property
		def game_id(self) -> str:
			return self._data["id"]

		@property
		def game_name(self) -> str:
			return self._data["name"]

		@property
		def save_sources(self) -> list[dict[str, Any]]:
			return sources_from_plugin_dict(self._data)

		@property
		def file_patterns(self) -> list[str]:
			return self._data.get("file_patterns", ["*"])

		@property
		def backup_registry_values(self) -> bool:
			return bool(self._data.get("backup_registry_values", False))

		@property
		def zip_key_aliases(self) -> dict[str, str]:
			raw = self._data.get("zip_key_aliases")
			return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}

		@property
		def backup_exclude_globs(self) -> list[str]:
			raw = self._data.get("backup_exclude_globs")
			return [str(x) for x in raw] if isinstance(raw, list) else []

		@property
		def clear_folder_on_restore(self) -> bool:
			return bool(self._data.get("clear_folder_on_restore", True))

		@property
		def is_disabled(self) -> bool:
			return bool(self._data.get("is_disabled", False))

		@property
		def is_template(self) -> bool:
			return bool(self._data.get("is_template", False))

		@property
		def icon(self) -> str:
			return self._data.get("icon", "")

		@property
		def poster(self) -> str:
			return self._data.get("poster", "")

		def extra_readme_lines(self) -> list[str]:
			raw = self._data.get("readme_extra_lines")
			if isinstance(raw, list):
				return [str(x) for x in raw if str(x).strip()]
			return []

	return JsonGamePlugin(data)


def auto_get_plugins() -> list[GamePlugin]:
	"""Auto-discover and return all GamePlugin subclasses in the calling module.
	
	Use in plugin files instead of manually implementing get_plugins():
	
		# In my_game_plugin.py
		class MyGamePlugin(GamePlugin):
			...
		
		# No need for get_plugins() anymore!
		get_plugins = auto_get_plugins
	"""
	frame = inspect.currentframe()
	if frame is None or frame.f_back is None:
		return []
	
	caller_module_name = frame.f_back.f_globals['__name__']
	
	# Find all concrete GamePlugin subclasses defined in the caller's module
	plugins: list[GamePlugin] = [
		cls()  # type: ignore[abstract]
		for cls in GamePlugin.__subclasses__()
		if cls.__module__ == caller_module_name and not inspect.isabstract(cls)
	]
	
	return plugins


