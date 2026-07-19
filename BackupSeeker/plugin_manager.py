from __future__ import annotations

import importlib
import hashlib
import logging
import json
import pkgutil
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List
import shutil
import urllib.parse
import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Shared plugin infrastructure — not game plugins; never reported as load warnings.
_PLUGIN_SUPPORT_MODULES = frozenset({
	"base",
	"prompt_validation",
	"save_sources",
	"TEMPLATE_PLUGIN",
})


@dataclass(frozen=True)
class PluginLoadIssue:
	"""One plugin load warning or error with a verbose detail block for the UI."""

	severity: str  # "error" | "warning"
	source: str
	message: str
	detail: str = ""


@dataclass
class PluginLoadReport:
	"""Outcome of a plugin discovery/reload pass."""

	issues: List[PluginLoadIssue] = field(default_factory=list)
	loaded_count: int = 0
	code_module_count: int = 0
	purged_modules: List[str] = field(default_factory=list)
	duration_ms: float = 0.0
	hot: bool = False

	@property
	def ok(self) -> bool:
		return not any(i.severity == "error" for i in self.issues)

	@property
	def error_count(self) -> int:
		return sum(1 for i in self.issues if i.severity == "error")

	@property
	def warning_count(self) -> int:
		return sum(1 for i in self.issues if i.severity == "warning")


def _issue_from_exception(
	source: str,
	exc: BaseException,
	*,
	context: str = "",
	severity: str = "error",
) -> PluginLoadIssue:
	tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
	head = f"{type(exc).__name__}: {exc}"
	if context:
		head = f"{context} — {head}"
	return PluginLoadIssue(severity=severity, source=source, message=head, detail=tb)


def format_load_report_summary(report: PluginLoadReport) -> str:
	"""One-line summary suitable for InfoBar toasts."""

	if report.ok and not report.issues:
		return f"Loaded {report.loaded_count} plugin(s) from {report.code_module_count} module(s)."
	parts = [f"{report.loaded_count} plugin(s) loaded"]
	if report.error_count:
		parts.append(f"{report.error_count} error(s)")
	if report.warning_count:
		parts.append(f"{report.warning_count} warning(s)")
	return ", ".join(parts) + "."


def format_load_report_verbose(report: PluginLoadReport) -> str:
	"""Multi-line report for log panels and detail dialogs."""

	lines = [
		format_load_report_summary(report),
		f"Reload: {'hot' if report.hot else 'cold'} | "
		f"modules scanned: {report.code_module_count} | "
		f"purged from sys.modules: {len(report.purged_modules)} | "
		f"{report.duration_ms:.0f} ms",
	]
	if report.purged_modules:
		lines.append("")
		lines.append("Purged modules:")
		for name in report.purged_modules[:40]:
			lines.append(f"  - {name}")
		if len(report.purged_modules) > 40:
			lines.append(f"  … and {len(report.purged_modules) - 40} more")
	if report.issues:
		lines.append("")
		lines.append("Issues:")
		for issue in report.issues:
			flag = issue.severity.upper()
			lines.append(f"[{flag}] {issue.source}")
			lines.append(f"  {issue.message}")
			if issue.detail.strip():
				for detail_line in issue.detail.strip().splitlines():
					lines.append(f"    {detail_line}")
	return "\n".join(lines)


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
		self.available_plugins: Dict[str, object] = {}
		# directory to store downloaded/copied plugin assets (images)
		self.data_dir = Path(base_dir) / "data"
		self.data_dir.mkdir(parents=True, exist_ok=True)
		self.poster_cache_dir = self.data_dir / "cache" / "posters"
		self.poster_cache_dir.mkdir(parents=True, exist_ok=True)
		self._http = self._make_http_session()
		self.on_reload: Callable[[PluginLoadReport], None] | None = None
		self.on_visual_assets_ready: Callable[[object], None] | None = None
		self._asset_loading: set[str] = set()
		self._asset_callbacks: Dict[str, List[callable]] = {}
		self._asset_locks: Dict[str, threading.RLock] = {}
		self._download_semaphore = threading.Semaphore(2)
		self._asset_retry_after: Dict[str, float] = {}
		self.last_load_report: PluginLoadReport = PluginLoadReport()
		self.reload_plugins(hot=False)

	@staticmethod
	def _make_http_session() -> requests.Session:
		"""Shared session with connection pooling and automatic retries for transient failures."""

		s = requests.Session()
		retry = Retry(
			total=2,
			connect=2,
			read=2,
			redirect=5,
			backoff_factor=0.35,
			status_forcelist=(408, 429, 500, 502, 503, 504),
			allowed_methods=frozenset({"GET", "HEAD"}),
			respect_retry_after_header=False,
		)
		adapter = HTTPAdapter(max_retries=retry, pool_connections=24, pool_maxsize=24)
		s.mount("https://", adapter)
		s.mount("http://", adapter)
		return s

	def load_plugins(self) -> PluginLoadReport:
		"""Reload all plugins (hot). Prefer :meth:`reload_plugins` for explicit control."""

		return self.reload_plugins(hot=True)

	def reload_plugins(self, *, hot: bool = True) -> PluginLoadReport:
		"""Discover plugins from ``plugins/`` and ``games.jsonc``.

		When *hot* is True, purge cached ``*.plugins.*`` modules from ``sys.modules``
		so edited ``.py`` files are re-imported on the next pass.
		"""

		start = time.perf_counter()
		issues: List[PluginLoadIssue] = []
		purged: List[str] = []
		prev_ids = set(self.available_plugins.keys())

		if hot:
			purged = self._purge_plugin_package_modules()

		self.available_plugins.clear()
		self._asset_loading.clear()
		self._asset_callbacks.clear()
		code_modules, code_issues = self._load_code_plugins()
		issues.extend(code_issues)
		json_issues = self._load_json_plugins()
		issues.extend(json_issues)

		new_ids = set(self.available_plugins.keys())
		for missing in sorted(prev_ids - new_ids):
			issues.append(
				PluginLoadIssue(
					"warning",
					f"plugin:{missing}",
					f"Plugin {missing!r} was available before reload but is missing now.",
					"Profiles still reference this id; backup/restore may fail until the plugin loads again.",
				)
			)

		report = PluginLoadReport(
			issues=issues,
			loaded_count=len(self.available_plugins),
			code_module_count=code_modules,
			purged_modules=purged,
			duration_ms=(time.perf_counter() - start) * 1000.0,
			hot=hot,
		)
		self.last_load_report = report
		self.hydrate_all_plugins_from_cache()
		if self.on_reload is not None:
			try:
				self.on_reload(report)
			except Exception:
				logger.exception("PluginManager.on_reload callback failed")
		return report

	def _plugins_package_prefix(self) -> str:
		pkg_name = __package__.rsplit(".", 1)[0]
		return f"{pkg_name}.plugins."

	def _purge_plugin_package_modules(self) -> List[str]:
		"""Drop cached plugin package modules so hot reload picks up file edits."""

		prefix = self._plugins_package_prefix()
		pkg_root = prefix.rstrip(".")
		purged: List[str] = []
		for name in list(sys.modules.keys()):
			if name == pkg_root or name.startswith(prefix):
				del sys.modules[name]
				purged.append(name)
		return sorted(purged)

	def get_plugin_for_profile(self, plugin_id: str | None):
		if not plugin_id:
			return None
		return self.available_plugins.get(plugin_id)

	def _plugins_base(self):
		"""Import ``plugins.base`` after each purge so ``isinstance`` checks stay valid."""

		pkg_name = __package__.rsplit(".", 1)[0]
		mod = importlib.import_module(f"{pkg_name}.plugins.base")
		return mod.GamePlugin, mod.plugin_from_json

	def _register_plugin(
		self,
		plugin: object,
		source: str,
		issues: List[PluginLoadIssue],
	) -> None:
		gid = (getattr(plugin, "game_id", "") or "").strip()
		if not gid:
			issues.append(
				PluginLoadIssue(
					"error",
					source,
					"Plugin has empty game_id and was skipped.",
					f"Plugin type: {type(plugin).__name__}",
				)
			)
			return
		if getattr(plugin, "is_disabled", False):
			logger.info("Plugin %r is disabled and will be ignored.", gid)
			return
		if getattr(plugin, "is_template", False):
			logger.info("Plugin %r is a template and will be ignored.", gid)
			return
		if gid in self.available_plugins:
			prev = self.available_plugins[gid]
			msg = (
				f"Duplicate plugin id {gid!r}: {source} replaces "
				f"{type(prev).__name__} from an earlier entry in this reload."
			)
			logger.warning(msg)
			issues.append(PluginLoadIssue("warning", source, msg, ""))
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

	def _load_code_plugins(self) -> tuple[int, List[PluginLoadIssue]]:
		issues: List[PluginLoadIssue] = []
		module_count = 0
		if not self.plugins_dir.exists():
			issues.append(
				PluginLoadIssue(
					"warning",
					str(self.plugins_dir),
					"Plugins directory does not exist; no code plugins loaded.",
					"",
				)
			)
			return module_count, issues

		allowed, disabled = self._plugin_index_filter()
		pkg_name = __package__.rsplit(".", 1)[0]
		GamePlugin, _plugin_from_json = self._plugins_base()
		for _finder, name, _ispkg in pkgutil.iter_modules([str(self.plugins_dir)]):
			if name.startswith("__"):
				continue
			if name in _PLUGIN_SUPPORT_MODULES:
				continue
			mod_path = self.plugins_dir / f"{name}.py"
			source = f"code:{name} ({mod_path})"
			if name in disabled:
				issues.append(
					PluginLoadIssue(
						"warning",
						source,
						f"Module {name!r} is listed in plugin_index.json disabled and was skipped.",
						"",
					)
				)
				continue
			if allowed is not None and name not in allowed:
				continue
			module_count += 1
			try:
				full_name = f"{pkg_name}.plugins.{name}"
				module = importlib.import_module(full_name)
				get_plugins_fn = getattr(module, "get_plugins", None)
				if not callable(get_plugins_fn):
					issues.append(
						PluginLoadIssue(
							"warning",
							source,
							f"Module {name!r} has no callable get_plugins(); skipped.",
							f"Expected get_plugins() -> list[GamePlugin] in {mod_path}",
						)
					)
					continue
				try:
					plugins = get_plugins_fn()
				except Exception as exc:
					logger.exception("get_plugins() failed for %s", name)
					issues.append(_issue_from_exception(source, exc, context="get_plugins() raised"))
					continue
				if plugins is None:
					issues.append(
						PluginLoadIssue(
							"warning",
							source,
							"get_plugins() returned None; expected a list.",
							"",
						)
					)
					continue
				if not isinstance(plugins, (list, tuple)):
					issues.append(
						PluginLoadIssue(
							"error",
							source,
							f"get_plugins() returned {type(plugins).__name__}, expected list or tuple.",
							"",
						)
					)
					continue
				if not plugins:
					issues.append(
						PluginLoadIssue(
							"warning",
							source,
							"get_plugins() returned an empty list.",
							"",
						)
					)
				for idx, plugin in enumerate(plugins):
					if not isinstance(plugin, GamePlugin):
						issues.append(
							PluginLoadIssue(
								"error",
								f"{source}#[{idx}]",
								f"Entry {idx} is {type(plugin).__name__}, not GamePlugin.",
								"Each get_plugins() item must be a GamePlugin instance.",
							)
						)
						continue
					try:
						self._init_plugin_asset_slots(plugin)
						self._register_plugin(plugin, f"{source}#[{idx}]", issues)
					except Exception as exc:
						logger.exception("Failed registering plugin from %s index %s", name, idx)
						issues.append(_issue_from_exception(f"{source}#[{idx}]", exc, context="register"))
			except Exception as exc:
				logger.exception("Failed importing plugin module %s", name)
				issues.append(_issue_from_exception(source, exc, context="import module"))
		return module_count, issues

	def _load_json_plugins(self) -> List[PluginLoadIssue]:
		issues: List[PluginLoadIssue] = []
		_GamePlugin, plugin_from_json = self._plugins_base()
		jsonc_path = self.plugins_dir / "games.jsonc"
		if not jsonc_path.exists():
			return issues
		source = f"json:{jsonc_path.name} ({jsonc_path})"
		try:
			lines = []
			for line in jsonc_path.read_text(encoding="utf-8").splitlines():
				stripped = line.lstrip()
				if stripped.startswith("//"):
					continue
				lines.append(line)
			data = json.loads("\n".join(lines))
		except Exception as exc:
			logger.exception("Failed parsing JSON plugins from %s", jsonc_path)
			issues.append(_issue_from_exception(source, exc, context="parse games.jsonc"))
			return issues

		if not isinstance(data, list):
			issues.append(
				PluginLoadIssue(
					"error",
					source,
					f"games.jsonc root must be a JSON array, got {type(data).__name__}.",
					"",
				)
			)
			return issues

		for idx, entry in enumerate(data):
			entry_source = f"{source}#[{idx}]"
			try:
				if not isinstance(entry, dict):
					issues.append(
						PluginLoadIssue(
							"error",
							entry_source,
							f"Entry {idx} must be an object, got {type(entry).__name__}.",
							"",
						)
					)
					continue
				plugin = plugin_from_json(entry)
				self._init_plugin_asset_slots(plugin)
				self._register_plugin(plugin, entry_source, issues)
			except Exception as exc:
				logger.exception("Failed constructing plugin from games.jsonc entry %s", idx)
				issues.append(_issue_from_exception(entry_source, exc, context="plugin_from_json"))
		return issues

	def detect_games(self) -> List[Dict]:
		detected: List[Dict] = []
		for plugin in self.available_plugins.values():
			if plugin.is_detected():
				detected.append(plugin.to_profile())
		return detected

	def _poster_still_needed(self, plugin: object) -> bool:
		"""True while a configured poster is not yet available on disk."""

		poster = (getattr(plugin, "poster", "") or "").strip()
		if not poster:
			return False
		if getattr(plugin, "_saved_poster", ""):
			return False
		if poster.lower().startswith(("http://", "https://")):
			dest = self._asset_cache_path(plugin, "poster", poster)
			return dest is not None and not self._asset_cache_hit(dest)
		return not Path(poster).exists()

	def _sync_visual_assets_loaded_flag(self, plugin: object) -> None:
		plugin._visual_assets_loaded = not self._poster_still_needed(plugin)

	def _download_file(self, url: str, dest: Path) -> bool:
		"""Download a URL to ``dest`` with retries, validation, and atomic replace.

		Startup pulls many posters/icons in quick succession; transient TLS/DNS/rate-limit
		errors and occasional non-image bodies are handled with retries instead of skipping
		the asset for the whole session.
		"""
		if dest.exists() and dest.stat().st_size > 0:
			return True

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
		max_attempts = 5

		with self._download_semaphore:
			for attempt in range(max_attempts):
				try:
					r = self._http.get(url, headers=headers, timeout=(4.0, 12.0))
					if r.status_code == 429:
						last_err = requests.HTTPError(f"429 Too Many Requests for {url}")
						delay = min(8.0, 0.6 * (2 ** attempt))
						logging.debug(
							"Rate-limited downloading %s (attempt %s/%s); retry in %.1fs",
							url,
							attempt + 1,
							max_attempts,
							delay,
						)
						time.sleep(delay)
						continue
					r.raise_for_status()
					data = r.content
					if not _bytes_look_like_image(data):
						logging.warning(
							"Plugin asset download for %s is not a recognized image (%s bytes)",
							url,
							len(data),
						)
						last_err = ValueError("response is not image data")
					else:
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
					logging.debug(
						"Download failed for %s (attempt %s/%s): %s",
						url,
						attempt + 1,
						max_attempts,
						e,
					)
					if attempt < max_attempts - 1:
						time.sleep(min(6.0, 0.4 * (2 ** attempt)))

		try:
			if tmp.exists():
				tmp.unlink(missing_ok=True)
		except OSError:
			pass
		if last_err is not None:
			logging.debug("Giving up download for %s: %s", url, last_err)
		return False

	def _init_plugin_asset_slots(self, plugin: object) -> None:
		"""Reset cached asset paths before (re)loading a plugin instance."""

		plugin._saved_icon = ""
		plugin._saved_poster = ""
		plugin._visual_assets_loaded = False

	def _asset_cache_path(self, plugin: object, asset_type: str, asset_value: str) -> Path | None:
		"""Stable cache path from plugin id, asset kind, and source string (URL or file path)."""

		asset_value = str(asset_value or "").strip()
		if not asset_value:
			return None
		gid = (getattr(plugin, "game_id", "") or "").strip() or "plugin"
		digest = hashlib.sha256(asset_value.encode("utf-8")).hexdigest()[:16]
		ext = ".img"
		if asset_value.lower().startswith(("http://", "https://")):
			try:
				parsed = urllib.parse.urlparse(asset_value)
				fn = Path(urllib.parse.unquote(parsed.path)).name
				if "." in fn:
					ext = "." + fn.rsplit(".", 1)[-1].lower()[:8]
			except Exception:
				pass
		else:
			suffix = Path(asset_value).suffix.lower()
			if suffix in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"):
				ext = suffix
		cache_root = self.poster_cache_dir if asset_type == "poster" else self.data_dir
		return cache_root / f"{gid}_{asset_type}_{digest}{ext}"

	def _asset_cache_hit(self, dest: Path) -> bool:
		try:
			return dest.exists() and dest.stat().st_size > 0
		except OSError:
			return False

	def _asset_lock_for(self, game_id: str) -> threading.RLock:
		lock = self._asset_locks.get(game_id)
		if lock is None:
			lock = threading.RLock()
			self._asset_locks[game_id] = lock
		return lock

	def _dispatch_on_main_thread(self, fn: callable) -> None:
		"""Run ``fn`` on the Qt GUI thread (required before touching widgets)."""

		try:
			from PyQt6.QtCore import QCoreApplication, QThread, QTimer

			app = QCoreApplication.instance()
			if app is not None and QThread.currentThread() is app.thread():
				fn()
				return
			if app is not None:
				QTimer.singleShot(0, fn)
				return
		except Exception:
			pass
		try:
			fn()
		except Exception:
			logger.exception("Main-thread dispatch failed")

	def _asset_needs_processing(self, plugin: object, asset_type: str, asset_value: str) -> bool:
		"""True when a remote URL or copyable file still needs to be materialized on disk."""

		asset_value = str(asset_value or "").strip()
		if not asset_value:
			return False
		if asset_value.lower().startswith(("http://", "https://")):
			dest = self._asset_cache_path(plugin, asset_type, asset_value)
			if dest is None:
				return False
			return not self._asset_cache_hit(dest)
		path = Path(asset_value)
		if path.is_file():
			dest = self._asset_cache_path(plugin, asset_type, asset_value)
			if dest is None:
				return False
			return not self._asset_cache_hit(dest)
		# Emoji / inline icons — nothing to download or cache.
		return False

	def hydrate_plugin_from_cache(self, plugin: object) -> bool:
		"""Point plugin at on-disk poster/icon files when cached. Returns True if download still needed."""

		if getattr(plugin, "_visual_assets_loaded", False):
			return self._poster_still_needed(plugin)

		need_icon = self._asset_needs_processing(plugin, "icon", getattr(plugin, "icon", "") or "")
		need_poster = self._asset_needs_processing(plugin, "poster", getattr(plugin, "poster", "") or "")
		if need_icon or need_poster:
			return True

		try:
			self._process_plugin_icon(plugin)
		except Exception:
			logging.exception("Failed processing icon for plugin %s", getattr(plugin, "game_id", "?"))
		try:
			self._process_plugin_poster(plugin)
		except Exception:
			logging.exception("Failed processing poster for plugin %s", getattr(plugin, "game_id", "?"))
		self._sync_visual_assets_loaded_flag(plugin)
		return self._poster_still_needed(plugin)

	def hydrate_all_plugins_from_cache(self) -> list[object]:
		"""Hydrate every loaded plugin from disk cache. Returns plugins still needing download."""

		pending: list[object] = []
		for plugin in self.available_plugins.values():
			if self.hydrate_plugin_from_cache(plugin):
				pending.append(plugin)
		return pending

	def _finish_visual_asset_callbacks(self, plugin: object) -> None:
		gid = (getattr(plugin, "game_id", "") or "").strip()
		callbacks: List[callable] = []
		if gid:
			with self._asset_lock_for(gid):
				self._asset_loading.discard(gid)
				callbacks = list(self._asset_callbacks.pop(gid, []))
		ready_hook = self.on_visual_assets_ready

		def dispatch() -> None:
			for cb in callbacks:
				try:
					cb()
				except Exception:
					logger.exception("Plugin visual asset callback failed for %r", gid)
			if ready_hook is not None:
				try:
					ready_hook(plugin)
				except Exception:
					logger.exception("on_visual_assets_ready failed for %r", gid)

		self._dispatch_on_main_thread(dispatch)

	def ensure_plugin_visual_assets(self, plugin: object | None, on_complete: callable | None = None) -> None:
		"""Materialize icon/poster files on first use so startup does not fetch every plugin asset."""

		if plugin is None:
			return
		gid = (getattr(plugin, "game_id", "") or "").strip() or "?"
		if getattr(plugin, "_visual_assets_loaded", False):
			if on_complete:
				self._dispatch_on_main_thread(on_complete)
			return

		# Check if download or copy is actually needed
		need_processing = self._asset_needs_processing(
			plugin, "icon", getattr(plugin, "icon", "") or ""
		) or self._asset_needs_processing(plugin, "poster", getattr(plugin, "poster", "") or "")

		with self._asset_lock_for(gid):
			if on_complete:
				self._asset_callbacks.setdefault(gid, []).append(on_complete)
			if gid in self._asset_loading:
				return
			if not need_processing:
				try:
					self._process_plugin_icon(plugin)
				except Exception:
					logging.exception("Failed processing icon for plugin %s", plugin.game_id)
				try:
					self._process_plugin_poster(plugin)
				except Exception:
					logging.exception("Failed processing poster for plugin %s", plugin.game_id)
				self._sync_visual_assets_loaded_flag(plugin)
				self._finish_visual_asset_callbacks(plugin)
				return
			self._asset_loading.add(gid)

		def worker() -> None:
			try:
				try:
					self._process_plugin_icon(plugin)
				except Exception:
					logging.exception("Failed processing icon for plugin %s", plugin.game_id)
				try:
					self._process_plugin_poster(plugin)
				except Exception:
					logging.exception("Failed processing poster for plugin %s", plugin.game_id)
				self._sync_visual_assets_loaded_flag(plugin)
			finally:
				self._finish_visual_asset_callbacks(plugin)
				if self._poster_still_needed(plugin):
					delay = min(10.0, 1.5 + 0.75 * len(self._asset_retry_after))
					self._asset_retry_after[gid] = time.monotonic() + delay
					self._schedule_asset_retry(plugin, delay)

		threading.Thread(target=worker, daemon=True, name=f"plugin-assets-{gid}").start()

	def _schedule_asset_retry(self, plugin: object, delay: float) -> None:
		"""Queue a deferred poster retry so rate-limited downloads are not abandoned."""

		delay = max(0.25, float(delay))
		gid = (getattr(plugin, "game_id", "") or "").strip() or "?"

		def retry() -> None:
			try:
				self.ensure_plugin_visual_assets(plugin)
			except Exception:
				logger.exception("Deferred visual asset retry failed for %r", gid)

		threading.Timer(delay, retry).start()

	def _process_plugin_asset(self, plugin: object, asset_type: str, asset_value: str) -> str:
		"""Download or copy a plugin icon/poster into the cache using a hash-based path."""

		if not asset_value:
			return ""

		asset_value = str(asset_value).strip()
		if not asset_value.lower().startswith(("http://", "https://")):
			p = Path(asset_value)
			if not p.exists():
				return ""
			if self.data_dir in p.parents or p.resolve() == self.data_dir.resolve():
				return str(p.resolve())

		dest = self._asset_cache_path(plugin, asset_type, asset_value)
		if dest is None:
			return ""

		if self._asset_cache_hit(dest):
			return str(dest)

		dest.parent.mkdir(parents=True, exist_ok=True)

		if asset_value.lower().startswith(("http://", "https://")):
			try:
				if self._download_file(asset_value, dest):
					return str(dest)
			except Exception:
				logging.exception(
					"Failed to download %s for %s from %s",
					asset_type,
					getattr(plugin, "game_id", "?"),
					asset_value,
				)
			return ""

		try:
			shutil.copy2(asset_value, dest)
			return str(dest)
		except Exception:
			logging.exception(
				"Failed to copy %s for %s from %s",
				asset_type,
				getattr(plugin, "game_id", "?"),
				asset_value,
			)
			return ""

	def _process_plugin_icon(self, plugin: object) -> None:
		plugin._saved_icon = self._process_plugin_asset(plugin, "icon", plugin.icon or "")

	def _process_plugin_poster(self, plugin: object) -> None:
		plugin._saved_poster = self._process_plugin_asset(plugin, "poster", plugin.poster or "")
