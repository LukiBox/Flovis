"""Flovis main window - tabbed layout with language switch."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QMainWindow, QTabWidget, QWidget, QVBoxLayout,
                               QLabel, QHBoxLayout, QFileDialog, QMessageBox,
                               QDialog, QPushButton, QComboBox)
from PySide6.QtCore import Qt

from .tabs.templates_tab import TemplatesTab
from .tabs.airfoil_tab import AirfoilTab
from .tabs.analysis_tab import AnalysisTab
from .tabs.model3d_tab import Model3DTab
from .tabs.report_tab import ReportTab
from .effects import apply_panel_shadows
from ..core import project as proj
from ..core.i18n import t, set_language, get_language


class AppState:
    """State shared between tabs."""
    def __init__(self, window):
        self.window = window
        self.current_model = None
        self.current_airfoil = None
        self.current_result = None
        self.current_polar2d = None      # 2D airfoil polar (Polar2DResult)
        self.project_path = None         # path of the current .flovis file

    def status(self, text: str):
        self.window.statusBar().showMessage(text, 6000)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1180, 760)
        self.state = AppState(self)
        self._build_ui()

    # -------------------------------------------------------------- build / i18n
    def _build_ui(self):
        self.setWindowTitle(t("Flovis - airfoil & wing analysis"))

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 10, 16, 4)
        title = QLabel("Flovis"); title.setObjectName("h1")
        sub = QLabel(t("simplified aerodynamic analysis of flying models"))
        sub.setObjectName("hint")
        hl.addWidget(title); hl.addSpacing(12); hl.addWidget(sub); hl.addStretch()
        hl.addWidget(QLabel(t("Language:")))
        self.lang_cb = QComboBox()
        self.lang_cb.addItem("English", "en")
        self.lang_cb.addItem("Polski", "pl")
        self.lang_cb.setCurrentIndex(0 if get_language() == "en" else 1)
        self.lang_cb.setFixedWidth(110)
        self.lang_cb.currentIndexChanged.connect(self._on_language_change)
        hl.addWidget(self.lang_cb)

        self.tabs = QTabWidget()
        self.templates_tab = TemplatesTab(self.state)
        self.airfoil_tab = AirfoilTab(self.state)
        self.analysis_tab = AnalysisTab(self.state)
        self.model3d_tab = Model3DTab(self.state)
        self.report_tab = ReportTab(self.state)
        self.tabs.addTab(self.templates_tab, t("  Templates 3D  "))
        self.tabs.addTab(self.airfoil_tab, t("  Airfoil  "))
        self.tabs.addTab(self.analysis_tab, t("  Analysis  "))
        self.tabs.addTab(self.model3d_tab, t("  3D Model  "))
        self.tabs.addTab(self.report_tab, t("  Report  "))

        central = QWidget()
        central.setObjectName("central")
        v = QVBoxLayout(central)
        v.setContentsMargins(14, 8, 14, 12)
        v.setSpacing(8)
        v.addWidget(header)
        v.addWidget(self.tabs, 1)
        central.setStyleSheet("#central { background: #f8f9fa; }")
        self.setCentralWidget(central)

        self._build_menu()
        apply_panel_shadows(self)
        self.statusBar().showMessage(t("Ready."))

    def _on_language_change(self):
        lang = self.lang_cb.currentData()
        if lang and lang != get_language():
            set_language(lang)
            self._rebuild_ui()

    def _rebuild_ui(self):
        """Rebuild the whole UI in the new language, preserving current state."""
        self.menuBar().clear()
        self._build_ui()
        # restore state into the freshly created tabs
        if self.state.current_model is not None:
            self.templates_tab.set_model(self.state.current_model)
        if self.state.current_airfoil is not None:
            self.airfoil_tab.set_airfoil(self.state.current_airfoil)
        if self.state.current_result is not None:
            self.analysis_tab.show_result(self.state.current_result)

    # ------------------------------------------------------------------ menu
    def _build_menu(self):
        m = self.menuBar().addMenu(t("&File"))
        m.addAction(t("New"), self._new_project)
        m.addAction(t("Open..."), self._open_project)
        m.addSeparator()
        m.addAction(t("Save"), self._save_project)
        m.addAction(t("Save as..."), self._save_project_as)
        m.addSeparator()
        m.addAction(t("Export PDF..."), self._export_pdf)
        m.addSeparator()
        m.addAction(t("Quit"), self.close)

    def _new_project(self):
        from ..core.geometry import make_template, Layout
        self.state.project_path = None
        self.templates_tab.set_model(make_template(Layout.LOW_WING))
        self.state.current_result = None
        self.state.current_polar2d = None
        self.tabs.setCurrentWidget(self.templates_tab)
        self.state.status(t("New project."))

    def _open_project(self):
        fn, _ = QFileDialog.getOpenFileName(self, t("Open project"), "",
                                            t("Flovis project (*.flovis)"))
        if not fn:
            return
        try:
            data = proj.load_project(fn)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, t("Read error"), str(e))
            return
        if data["model"] is not None:
            self.templates_tab.set_model(data["model"])
        if data["airfoil"] is not None:
            self.airfoil_tab.set_airfoil(data["airfoil"])
        if data["result"] is not None:
            self.state.current_result = data["result"]
            self.analysis_tab.show_result(data["result"])
        self.state.project_path = fn
        self.state.status(t("Loaded project: {}").format(Path(fn).name))

    def _save_project(self):
        if self.state.project_path:
            self._write_project(self.state.project_path)
        else:
            self._save_project_as()

    def _save_project_as(self):
        fn, _ = QFileDialog.getSaveFileName(self, t("Save project"),
                                            "model.flovis",
                                            t("Flovis project (*.flovis)"))
        if fn:
            self._write_project(fn)

    def _write_project(self, fn):
        try:
            p = proj.save_project(
                fn, model=self.state.current_model,
                airfoil=self.state.current_airfoil,
                result=self.state.current_result)
            self.state.project_path = str(p)
            self.state.status(t("Saved: {}").format(Path(p).name))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, t("Save error"), str(e))

    def _export_pdf(self):
        self.tabs.setCurrentWidget(self.report_tab)
        self.report_tab._export_pdf()

    # ------------------------------------------------------------- onboarding
    def show_onboarding(self):
        dlg = OnboardingDialog(self)
        dlg.exec()
        choice = dlg.choice
        if choice == "template":
            self.tabs.setCurrentWidget(self.templates_tab)
        elif choice == "step":
            self.tabs.setCurrentWidget(self.analysis_tab)
            self.analysis_tab._run_step()
        elif choice == "airfoil":
            self.tabs.setCurrentWidget(self.airfoil_tab)
        elif choice == "open":
            self._open_project()


class OnboardingDialog(QDialog):
    """Guided start screen: pick a way to begin."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Welcome to Flovis"))
        self.choice = None
        v = QVBoxLayout(self)
        title = QLabel(t("Where do we start?")); title.setObjectName("h1")
        v.addWidget(title)
        sub = QLabel(t("Pick one option - you can change it any time."))
        sub.setObjectName("hint"); v.addWidget(sub)
        v.addSpacing(8)
        opts = [
            (t("Start from a template"),
             t("A ready aircraft layout to edit and analyze."), "template"),
            (t("Load a STEP model (.stp)"),
             t("Analyze exact CAD geometry."), "step"),
            (t("Edit an airfoil"),
             t("Airfoil generator and interactive editor."), "airfoil"),
            (t("Open a project (.flovis)"),
             t("Load a previously saved project."), "open"),
        ]
        for label, desc, key in opts:
            b = QPushButton(f"{label}\n{desc}")
            b.setMinimumHeight(56)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            v.addWidget(b)
        skip = QPushButton(t("Skip")); skip.setProperty("flat", True)
        skip.clicked.connect(self.reject)
        v.addWidget(skip)

    def _pick(self, key):
        self.choice = key
        self.accept()


def load_stylesheet() -> str:
    qss = Path(__file__).resolve().parents[1] / "resources" / "styles" / "flovis.qss"
    return qss.read_text(encoding="utf-8") if qss.exists() else ""
