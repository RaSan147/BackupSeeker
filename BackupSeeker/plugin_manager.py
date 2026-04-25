from __future__ import annotations

import importlib
import logging
import json
import pkgutil
import time
from pathlib import Path
from typing import Dict, List
import shutil
import urllib.parse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .plugins.base import GamePlugin, plugin_from_json


def _bytes_look_like_image(data: bytes) -> bool:
	"""Reject empty responses and common HTML/error bodies mis-served as images."""

	if not data or len(data) < 12:
		return False
	if data[:3] == b"\xff\xd8\xff":
		return True
	if data[:8] == b"\x89PNG\r\n\x1a\n":
		return True
	if data[:6] in (b"GIF87a", b"GIF89a"):
		return True
	if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
		return True
	if data[:2] == b"BM":
		return True
	if data[:4] in (b"II*\x00", b"MM\x00*"):
		return True
	# Typical HTML/XML from misrouted error pages
	if data.lstrip()[:1] in (b"<", b"{"):
		return False
	return False


class PluginManager:
	"""Loads code-based and JSON-described game plugins.

	This manager discovers plugin modules under `plugins/` and reads a
	`games.jsonc` file for data-driven plugins. It normalizes imports so
	that the package folder can be renamed without breaking relative
	imports inside plugins.
	"""

	def __init__(self, base_dir: Path) -> None:
		self.base_dir = base_dir
		self.plugins_dir = base_dir / "plugins"
		self.available_plugins: Dict[str, GamePlugin] = {}
		# directory to store downloaded/copied plugin assets (images)
		self.data_dir = Path(base_dir) / "data"
		self.data_dir.mkdir(parents=True, exist_ok=True)
		self._http = self._make_http_session()
		self.load_plugins()

	@staticmethod
	def _make_http_session() -> requests.Session:
		"""Shared session with connection pooling and automatic retries for transient failures."""

		s = requests.Session()
		retry = Retry(
			total=5,
			connect=5,
			read=5,
			redirect=5,
			backoff_factor=0.35,
			status_forcelist=(408, 429, 500, 502, 503, 504),
			allowed_methods=frozenset({"GET", "HEAD"}),
		)
		adapter = HTTPAdapter(max_retries=retry, pool_connections=24, pool_maxsize=24)
		s.mount("https://", adapter)
		s.mount("http://", adapter)
		return s

	def load_plugins(self) -> None:
		self.available_plugins.clear()
		self._load_code_plugins()
		self._load_json_plugins()

	def get_plugin_for_profile(self, plugin_id: str | None) -> GamePlugin | None:
		if not plugin_id:
			return None
		return self.available_plugins.get(plugin_id)

	def _register_plugin(self, plugin: GamePlugin, source: str) -> None:
		gid = plugin.game_id
		if gid in self.available_plugins:
			logging.warning(
				"Duplicate plugin id %r: %s replaces existing entry (%s)",
				gid,
				source,
				type(self.available_plugins[gid]).__name__,
			)
		self.available_plugins[gid] = plugin

	def _plugin_index_filter(self) -> tuple[set[str] | None, set[str]]:
		"""Optional ``plugins/plugin_index.json``: ``modules`` whitelist, ``disabled`` blocklist."""

		idx_path = self.plugins_dir / "plugin_index.json"
		if not idx_path.exists():
			return None, set()
		try:
			raw = json.loads(idx_path.read_text(encoding="utf-8"))
		except Exception:
			logging.exception("Invalid plugin_index.json — ignoring")
			return None, set()
		if not isinstance(raw, dict):
			return None, set()
		modules = raw.get("modules")
		allowed: set[str] | None = None
		if isinstance(modules, list) and modules:
			allowed = {str(x).strip() for x in modules if str(x).strip()}
		disabled_raw = raw.get("disabled") or []
		disabled = {str(x).strip() for x in disabled_raw} if isinstance(disabled_raw, list) else set()
		return allowed, disabled

	def _load_code_plugins(self) -> None:
		if not self.plugins_dir.exists():
			return
		allowed, disabled = self._plugin_index_filter()
		for finder, name, ispkg in pkgutil.iter_modules([str(self.plugins_dir)]):
			if name.startswith("__"):
				continue
			if name in disabled:
				continue
			if allowed is not None and name not in allowed:
				continue
			try:
				# Import as a proper package submodule so relative imports work,
				# but resolve the current package name dynamically so the folder
				# can be renamed without breaking.
				pkg_name = __package__.rsplit(".", 1)[0]  # e.g. "BackupSeeker"
				full_name = f"{pkg_name}.plugins.{name}"
				module = importlib.import_module(full_name)
				try:
					get_plugins_fn = module.get_plugins
				except AttributeError:
					get_plugins_fn = None
				if callable(get_plugins_fn):
					plugins = get_plugins_fn()
					for plugin in plugins:
						self._init_plugin_asset_slots(plugin)
						self._register_plugin(plugin, f"code:{name}")
			except Exception:
				# Log plugin import errors at debug level; don't crash the app.
				logging.exception(f"Failed importing plugin module {name}")
				continue

	def _load_json_plugins(self) -> None:
		jsonc_path = self.plugins_dir / "games.jsonc"
		if not jsonc_path.exists():
			return
		try:
			# Strip simple // comments for JSONC-like support
			lines = []
			for line in jsonc_path.read_text(encoding="utf-8").splitlines():
				stripped = line.lstrip()
				if stripped.startswith("//"):
					continue
				lines.append(line)
			data = json.loads("\n".join(lines))
			if isinstance(data, list):
				for entry in data:
					try:
						plugin = plugin_from_json(entry)
						self._init_plugin_asset_slots(plugin)
						self._register_plugin(plugin, "json:games.jsonc")
					except Exception:
						logging.exception(f"Failed constructing plugin from entry: {entry}")
						continue
		except Exception:
			logging.exception("Failed loading JSON plugins")
			return

	def detect_games(self) -> List[Dict]:
		detected: List[Dict] = []
		for plugin in self.available_plugins.values():
			if plugin.is_detected():
				detected.append(plugin.to_profile())
		return detected

	def _download_file(self, url: str, dest: Path) -> bool:
		"""Download a URL to ``dest`` with retries, validation, and atomic replace.

		Startup pulls many posters/icons in quick succession; transient TLS/DNS/rate-limit
		errors and occasional non-image bodies are handled with retries instead of skipping
		the asset for the whole session.
		"""
		netloc = ""
		try:
			netloc = (urllib.parse.urlparse(url).netloc or "").lower()
		except Exception:
			pass

		# Poster/icon URLs are not necessarily Wikipedia. Only add Wikipedia-style Referer on
		# Wikimedia/Wikipedia hosts (their CDN expects it). Other origins: omit Referer — a
		# mismatched or fake Referer looks like spoofing and some CDNs/firewalls drop it.
		headers = {
			"User-Agent": "BackupSeeker/1.0 (desktop game save backup tool)",
			"Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
			"Accept-Language": "en-US,en;q=0.5",
		}
		if "wikimedia.org" in netloc or "wikipedia.org" in netloc:
			headers["Referer"] = "https://en.wikipedia.org/"

		dest.parent.mkdir(parents=True, exist_ok=True)
		tmp = dest.with_name(dest.name + ".part")
		last_err: BaseException | None = None

		for attempt in range(1, 4):
			try:
				r = self._http.get(url, headers=headers, timeout=(8, 25))
				r.raise_for_status()
				data = r.content
				if not _bytes_look_like_image(data):
					logging.warning(
						"Plugin asset download for %s is not a recognized image (%s bytes), retry %s/3",
						url,
						len(data),
						attempt,
					)
					last_err = ValueError("response is not image data")
					time.sleep(0.2 * attempt)
					continue
				tmp.write_bytes(data)
				try:
					tmp.replace(dest)
				except OSError:
					# Windows can briefly lock a previous file; retry write+replace once
					time.sleep(0.15)
					tmp.write_bytes(data)
					tmp.replace(dest)
				return True
			except Exception as e:
				last_err = e
				logging.debug("Download attempt %s failed for %s: %s", attempt, url, e)
				time.sleep(0.25 * attempt)
		try:
			if tmp.exists():
				tmp.unlink(missing_ok=True)
		except OSError:
			pass
		if last_err is not None:
			logging.debug("Giving up download for %s: %s", url, last_err)
		return False

	def _init_plugin_asset_slots(self, plugin: GamePlugin) -> None:
		"""Register icon/poster sources without downloading; :meth:`ensure_plugin_visual_assets` resolves them."""

		plugin._icon_source = plugin.icon or ""
		plugin._poster_source = plugin.poster or ""
		plugin._saved_icon = ""
		plugin._saved_poster = ""
		plugin._visual_assets_loaded = False

	def ensure_plugin_visual_assets(self, plugin: GamePlugin | None) -> None:
		"""Materialize icon/poster files on first use so startup does not fetch every plugin asset."""

		if plugin is None:
			return
		if getattr(plugin, "_visual_assets_loaded", False):
			return
		try:
			self._process_plugin_icon(plugin)
		except Exception:
			logging.exception("Failed processing icon for plugin %s", plugin.game_id)
		try:
			self._process_plugin_poster(plugin)
		except Exception:
			logging.exception("Failed processing poster for plugin %s", plugin.game_id)
		plugin._visual_assets_loaded = True

	def _process_plugin_asset(self, plugin: GamePlugin, asset_type: str, asset_value: str) -> str:
		"""Process a plugin asset (icon or poster) - download or copy to data directory.
		
		Args:
			plugin: GamePlugin instance
			asset_type: "icon" or "poster"
			asset_value: URL or file path to the asset
			
		Returns:
			The saved asset path, or empty string if not saved
		"""
		if not asset_value:
			return ""
		
		asset_value = str(asset_value).strip()
		
		# Handle URLs
		if asset_value.lower().startswith(("http://", "https://")):
			try:
				parsed = urllib.parse.urlparse(asset_value)
				fn = Path(parsed.path).name or f"{plugin.game_id}.{asset_type}"
				dest = self.data_dir / f"plugin_{plugin.game_id}_{fn}"
				if self._download_file(asset_value, dest):
					return str(dest)
			except Exception:
				logging.exception(f"Failed to download {asset_type} for {plugin.game_id} from {asset_value}")
			return ""
		
		# Handle local file paths
		p = Path(asset_value)
		if p.exists():
			try:
				# If already inside data dir, use as-is
				if self.data_dir in p.parents or p.resolve() == self.data_dir:
					return str(p)
				# Otherwise copy to data dir
				dest = self.data_dir / f"plugin_{plugin.game_id}_{p.name}"
				shutil.copy2(str(p), str(dest))
				return str(dest)
			except Exception:
				logging.exception(f"Failed to copy {asset_type} for {plugin.game_id} from {p}")
				return ""
		
		# Unknown format (emoji, etc.) - leave empty
		return ""

	def _process_plugin_icon(self, plugin: GamePlugin) -> None:
		"""Process plugin icon - download or copy to data directory.
		
		Sets plugin._saved_icon and plugin._icon_source.
		"""
		icon = plugin.icon or ""
		plugin._icon_source = icon
		plugin._saved_icon = self._process_plugin_asset(plugin, "icon", icon)

	def _process_plugin_poster(self, plugin: GamePlugin) -> None:
		"""Process plugin poster - download or copy to data directory.
		
		Sets plugin._saved_poster and plugin._poster_source.
		"""
		poster = plugin.poster or ""
		plugin._poster_source = poster
		plugin._saved_poster = self._process_plugin_asset(plugin, "poster", poster)
