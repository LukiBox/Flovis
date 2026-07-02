"""
Locating the external binaries (XFoil, AVL).

Search order:
  1. environment variable (FLOVIS_XFOIL / FLOVIS_AVL),
  2. the bundled resources/bin directory (Flovis / PyInstaller build),
  3. the system PATH.

The app works out of the box with the bundled binaries, and an advanced
user can point to their own build via an environment variable.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _bin_dir() -> Path:
    """Directory of bundled binaries (also valid inside a PyInstaller build)."""
    if getattr(sys, "frozen", False):  # PyInstaller
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "resources" / "bin"
    # flovis/core/binaries.py -> flovis/resources/bin
    return Path(__file__).resolve().parents[1] / "resources" / "bin"


def find_binary(name: str, env_var: str | None = None) -> str | None:
    """
    Return the path to a binary, or None when not found.

    name     - base name, e.g. "xfoil" (.exe appended on Windows)
    env_var  - optional environment variable holding a full path
    """
    exe = name + (".exe" if os.name == "nt" else "")

    if env_var and os.environ.get(env_var):
        p = Path(os.environ[env_var])
        if p.exists():
            return str(p)

    candidate = _bin_dir() / exe
    if candidate.exists():
        return str(candidate)

    # system PATH
    found = shutil.which(name) or shutil.which(exe)
    return found


def xfoil_path() -> str | None:
    return find_binary("xfoil", "FLOVIS_XFOIL")


def avl_path() -> str | None:
    return find_binary("avl", "FLOVIS_AVL")
