"""
Efekt Windows 11 Mica (rozmyte, przezroczyste tlo okna) przez DWM.

Dziala tylko na Windows 11 (build >= 22000). Na innych systemach funkcje sa
bezpiecznym no-op, a aplikacja uzywa jasnego, plaskiego tla.
"""
from __future__ import annotations

import ctypes
import sys

# atrybuty DWM
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_SYSTEMBACKDROP_TYPE = 38
# typy tla: 1=Auto, 2=None, 3=Mica, 4=Acrylic, 5=Tabbed
_DWMSBT_MAINWINDOW = 2   # Mica


def _win_build() -> int:
    try:
        return sys.getwindowsversion().build
    except Exception:
        return 0


def mica_supported() -> bool:
    """Czy system wspiera Mica (Windows 11 22000+)."""
    return sys.platform == "win32" and _win_build() >= 22000


def apply_mica(window, light: bool = True) -> bool:
    """
    Nakłada efekt Mica na okno Qt. Zwraca True gdy sie powiodlo.

    Wymaga, by okno mialo juz uchwyt (wywoluj po pierwszym show / w showEvent)
    oraz atrybutu Qt.WA_TranslucentBackground na oknie.
    """
    if not mica_supported():
        return False
    try:
        hwnd = int(window.winId())
        dwm = ctypes.windll.dwmapi
        dark = ctypes.c_int(0 if light else 1)
        dwm.DwmSetWindowAttribute(
            hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark), 4)
        backdrop = ctypes.c_int(_DWMSBT_MAINWINDOW)
        dwm.DwmSetWindowAttribute(
            hwnd, _DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(backdrop), 4)
        return True
    except Exception:
        return False
