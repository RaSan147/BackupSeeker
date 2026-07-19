"""Optional Windows registry export/import for backup bundles (opt-in per plugin)."""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict, List, Tuple

try:
	import winreg
except Exception:  # pragma: no cover
	winreg = None  # type: ignore

JsonDict = Dict[str, Any]

if sys.platform != "win32" or winreg is None:  # pragma: no cover
	_EXPORT_ERR = "not Windows or winreg unavailable"
else:
	_EXPORT_ERR = ""


def _parse_key_path(key_path: str):
	"""Split 'HKEY_CURRENT_USER\\\\Software\\\\Foo' -> (hkey_const, subkey)."""

	part = key_path.partition("\\")
	hkey_str = part[0].strip()
	sub_key = part[2].strip()
	if not sub_key:
		return None
	hkey = getattr(winreg, hkey_str, None)  # type: ignore[arg-type]
	if hkey is None:
		return None
	return hkey, sub_key


def export_registry_entries(entries: List[Tuple[str, str]]) -> JsonDict:
	"""Read registry values; store as JSON-safe structures."""

	out: JsonDict = {"entries": []}
	if _EXPORT_ERR:
		logging.debug("registry export skipped: %s", _EXPORT_ERR)
		return out

	for key_path, value_name in entries:
		row: JsonDict = {}
		try:
			parsed = _parse_key_path(key_path)
			if parsed is None:
				out["entries"].append(
					{"key_path": key_path, "value_name": value_name, "error": "bad key_path"}
				)
				continue
			hkey_handle, sub_key = parsed
			with winreg.OpenKey(hkey_handle, sub_key, 0, winreg.KEY_READ) as key:  # type: ignore[arg-type]
				val_type, val_data = None, None
				try:
					val_type, val_data = winreg.QueryValueEx(key, value_name)  # type: ignore[arg-type]
				except OSError:
					out["entries"].append(
						{
							"key_path": key_path,
							"value_name": value_name,
							"error": "not found",
						}
					)
					continue

				ft = ""
				payload: Any = None
				if val_type == winreg.REG_SZ:
					ft = "REG_SZ"
					payload = str(val_data)
				elif val_type == winreg.REG_EXPAND_SZ:
					ft = "REG_EXPAND_SZ"
					payload = str(val_data)
				elif val_type == winreg.REG_DWORD:
					ft = "REG_DWORD"
					payload = int(val_data)
				else:
					ft = "UNSUPPORTED"
					payload = None

				row = {
					"hive": key_path.partition("\\")[0],
					"subkey": sub_key,
					"value_name": value_name,
					"win_type": ft,
					"data": payload,
				}
				out["entries"].append(row)
		except OSError as e:
			out["entries"].append(
				{"key_path": key_path, "value_name": value_name, "error": str(e)[:200]}
			)

	return out


def import_registry_entries(registry_export: JsonDict | None) -> None:
	"""Write registry values from bundle export (same shape as embedded CLI)."""

	if not isinstance(registry_export, dict) or winreg is None:
		return

	entries = registry_export.get("entries")
	if not isinstance(entries, list):
		return

	for item in entries:
		if not isinstance(item, dict):
			continue
		hive_s = item.get("hive")
		subkey = item.get("subkey")
		val_name = item.get("value_name")
		win_type = item.get("win_type")
		val_data = item.get("data")
		if (
			not isinstance(hive_s, str)
			or not isinstance(subkey, str)
			or not isinstance(val_name, str)
			or win_type not in ("REG_SZ", "REG_EXPAND_SZ", "REG_DWORD")
		):
			continue
		hkey = getattr(winreg, hive_s, None)
		if hkey is None:
			continue
		try:
			with winreg.CreateKeyEx(hkey, subkey, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
				if win_type == "REG_DWORD" and isinstance(val_data, int):
					winreg.SetValueEx(key, val_name, 0, winreg.REG_DWORD, val_data)
				elif isinstance(val_data, str):
					reg_t = winreg.REG_EXPAND_SZ if win_type == "REG_EXPAND_SZ" else winreg.REG_SZ
					winreg.SetValueEx(key, val_name, 0, reg_t, val_data)
		except OSError as e:
			logging.warning("registry restore failed (%s\\%s): %s", subkey, val_name, e)
