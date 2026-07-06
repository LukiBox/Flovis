"""Tiny persistent settings store (JSON in %APPDATA%/Flovis).

Same pattern as StructVis/SimVis: a flat key/value JSON file, loaded lazily
and written on every change. Shares the file the language setting already
lived in, so upgrading keeps the user's language choice.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_cache: dict[str, Any] | None = None


def _cfg_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "Flovis" / "settings.json"


def _load() -> dict[str, Any]:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(_cfg_path().read_text(encoding="utf-8"))
            if not isinstance(_cache, dict):
                _cache = {}
        except Exception:  # noqa: BLE001
            _cache = {}
    return _cache


def get(key: str, default: Any = None) -> Any:
    return _load().get(key, default)


def set_value(key: str, value: Any) -> None:
    data = _load()
    data[key] = value
    try:
        p = _cfg_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
