"""Typed access to :class:`~BackupSeeker.plugins.base.GamePlugin` APIs.

Imports ``GamePlugin`` lazily inside functions so :mod:`BackupSeeker.core` can
keep loading order compatible with ``plugins.base`` importing ``PathUtils``.
"""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, TypeVar

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


@dataclass(frozen=True)
class PluginHookError(RuntimeError):
	"""Raised when a plugin lifecycle hook fails; carries a verbose traceback."""

	plugin_id: str
	hook: str
	message: str
	detail: str

	def __str__(self) -> str:
		return f"[{self.plugin_id}] {self.hook}: {self.message}"


def format_plugin_hook_error(err: PluginHookError, *, include_traceback: bool = True) -> str:
	lines = [str(err)]
	if include_traceback and err.detail.strip():
		lines.append("")
		lines.append(err.detail.strip())
	return "\n".join(lines)


def run_plugin_hook(
	plugin: object | None,
	hook: str,
	*args: Any,
	default: _T | None = None,
	reraise: bool = True,
	**kwargs: Any,
) -> Any:
	"""Call ``plugin.<hook>(*args, **kwargs)`` with structured error reporting."""

	p = as_game_plugin(plugin)
	if p is None:
		return default
	fn = getattr(p, hook, None)
	if not callable(fn):
		return default
	try:
		return fn(*args, **kwargs)
	except Exception as exc:
		detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
		err = PluginHookError(
			plugin_id=plugin_log_id(plugin),
			hook=hook,
			message=f"{type(exc).__name__}: {exc}",
			detail=detail,
		)
		logger.exception("Plugin hook %s failed for %r", hook, plugin_log_id(plugin))
		if reraise:
			raise err from exc
		return default


def as_game_plugin(plugin: object | None):
	"""Return ``plugin`` when it is a :class:`~BackupSeeker.plugins.base.GamePlugin`, else ``None``."""
	if plugin is None:
		return None
	from .plugins.base import GamePlugin

	return plugin if isinstance(plugin, GamePlugin) else None


def _gp(plugin: object | None):
	return as_game_plugin(plugin)


def plugin_game_id(plugin: object | None) -> str:
	p = _gp(plugin)
	return (p.game_id if p else "") or ""


def plugin_log_id(plugin: object | None) -> str:
	s = plugin_game_id(plugin)
	return s if s else "?"


def clear_folder_on_restore(plugin: object | None) -> bool:
	if plugin is None:
		return True
	p = _gp(plugin)
	if p is None:
		return True
	return bool(p.clear_folder_on_restore)


def backup_exclude_globs(plugin: object) -> List[str]:
	p = _gp(plugin)
	if p is None:
		return []
	return list(p.backup_exclude_globs or [])


def mechanical_collect_archive_rows(
	plugin: object,
	profile_dict: Dict[str, Any],
	*,
	patterns: List[str],
	exclude_globs: List[str],
):
	p = _gp(plugin)
	if p is None:
		return None
	try:
		return p.mechanical_collect_archive_rows(profile_dict, patterns=patterns, exclude_globs=exclude_globs)
	except Exception as exc:
		detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
		err = PluginHookError(
			plugin_id=plugin_log_id(plugin),
			hook="mechanical_collect_archive_rows",
			message=f"{type(exc).__name__}: {exc}",
			detail=detail,
		)
		logger.exception("mechanical_collect_archive_rows failed for %r", plugin_log_id(plugin))
		raise err from exc


def call_to_snapshot_dict(plugin: object) -> Dict[str, Any]:
	p = _gp(plugin)
	if p is None:
		return {}
	try:
		raw = p.to_snapshot_dict()
		return dict(raw) if isinstance(raw, dict) else {}
	except Exception:
		logger.exception("to_snapshot_dict failed for plugin %r", plugin_log_id(plugin))
		return {}


def mechanical_finalize_bundle(plugin: object, bundle_body: Dict[str, Any]) -> Dict[str, Any]:
	p = _gp(plugin)
	if p is None:
		return bundle_body
	try:
		return p.mechanical_finalize_bundle(bundle_body) or bundle_body
	except Exception as exc:
		detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
		err = PluginHookError(
			plugin_id=plugin_log_id(plugin),
			hook="mechanical_finalize_bundle",
			message=f"{type(exc).__name__}: {exc}",
			detail=detail,
		)
		logger.exception("mechanical_finalize_bundle failed for %r", plugin_log_id(plugin))
		raise err from exc


def extra_readme_lines(plugin: object) -> List[str]:
	p = _gp(plugin)
	if p is None:
		return []
	try:
		return [str(x) for x in (p.extra_readme_lines() or []) if str(x).strip()]
	except Exception:
		return []


def registry_export_pairs(plugin: object) -> List[Tuple[str, str]]:
	p = _gp(plugin)
	if p is None or not p.backup_registry_values:
		return []
	out: List[Tuple[str, str]] = []
	for item in p.registry_keys or []:
		if isinstance(item, (tuple, list)) and len(item) >= 2:
			out.append((str(item[0]), str(item[1])))
	return out


def embed_arc_basename(plugin: object) -> str:
	s = plugin_game_id(plugin)
	return s if s else "plugin"


def mechanical_after_app_restore(plugin: object, info: Dict[str, Any]) -> None:
	p = _gp(plugin)
	if p is None:
		return
	try:
		p.mechanical_after_app_restore(info)
	except Exception as exc:
		detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
		err = PluginHookError(
			plugin_id=plugin_log_id(plugin),
			hook="mechanical_after_app_restore",
			message=f"{type(exc).__name__}: {exc}",
			detail=detail,
		)
		logger.exception("mechanical_after_app_restore failed for %r", plugin_log_id(plugin))
		raise err from exc
