"""Flovis application entry point."""
from __future__ import annotations

import sys


def _force_light_palette(app):
    """
    Force a LIGHT theme regardless of the OS dark mode.

    Qt6 on Windows adopts the dark OS palette automatically and QSS overrides
    only some elements, leaving dark fields/backgrounds behind. The Fusion
    style honors the explicit palette + QSS, giving a consistent light look.
    """
    from PySide6.QtGui import QPalette, QColor
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#f8f9fa"))
    pal.setColor(QPalette.WindowText, QColor("#1f2937"))
    pal.setColor(QPalette.Base, QColor("#ffffff"))
    pal.setColor(QPalette.AlternateBase, QColor("#f3f4f6"))
    pal.setColor(QPalette.Text, QColor("#1f2937"))
    pal.setColor(QPalette.Button, QColor("#ffffff"))
    pal.setColor(QPalette.ButtonText, QColor("#1f2937"))
    pal.setColor(QPalette.BrightText, QColor("#dc2626"))
    pal.setColor(QPalette.ToolTipBase, QColor("#1f2937"))
    pal.setColor(QPalette.ToolTipText, QColor("#ffffff"))
    pal.setColor(QPalette.Highlight, QColor("#2563eb"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.PlaceholderText, QColor("#9ca3af"))
    pal.setColor(QPalette.Link, QColor("#2563eb"))
    for grp in (QPalette.Disabled,):
        pal.setColor(grp, QPalette.Text, QColor("#9ca3af"))
        pal.setColor(grp, QPalette.ButtonText, QColor("#9ca3af"))
        pal.setColor(grp, QPalette.WindowText, QColor("#9ca3af"))
    app.setPalette(pal)


def _apply_light_theme():
    """Force a light theme in the chart libraries (pyqtgraph defaults to black)."""
    try:
        import pyqtgraph as pg
        pg.setConfigOption("background", "w")     # white background
        pg.setConfigOption("foreground", "#1f2937")  # dark axes/text
        pg.setConfigOption("antialias", True)
    except Exception:  # noqa: BLE001
        pass
    try:
        import matplotlib as mpl
        mpl.rcParams.update({
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#9ca3af",
            "axes.labelcolor": "#1f2937",
            "text.color": "#1f2937",
            "xtick.color": "#6b7280",
            "ytick.color": "#6b7280",
            "font.size": 9,
        })
    except Exception:  # noqa: BLE001
        pass


def main():
    from PySide6.QtWidgets import QApplication
    from flovis.ui.main_window import MainWindow, load_stylesheet

    app = QApplication(sys.argv)
    app.setApplicationName("Flovis")
    _force_light_palette(app)      # force light theme despite OS dark mode
    _apply_light_theme()
    app.setStyleSheet(load_stylesheet())

    win = MainWindow()
    win.show()
    win.show_onboarding()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
