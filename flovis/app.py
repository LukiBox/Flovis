"""Flovis application entry point."""
from __future__ import annotations

import sys


def main():
    # STEP meshing runs in a multiprocessing child; in the frozen exe the
    # child re-executes Flovis.exe, and freeze_support() must intercept it
    # before any Qt starts (otherwise every mesh spawns a second window).
    import multiprocessing
    multiprocessing.freeze_support()

    from PySide6.QtWidgets import QApplication
    from flovis.ui import theme
    from flovis.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Flovis")
    app.setOrganizationName("LukiBox")
    theme.apply(app)               # token theme: dark default, light optional

    win = MainWindow()
    win.show()
    win.show_onboarding()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
