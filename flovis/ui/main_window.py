"""Glowne okno Flovis - uklad zakladek."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QMainWindow, QTabWidget, QWidget, QVBoxLayout,
                               QLabel, QHBoxLayout, QFileDialog, QMessageBox,
                               QDialog, QPushButton)
from PySide6.QtCore import Qt

from .tabs.templates_tab import TemplatesTab
from .tabs.airfoil_tab import AirfoilTab
from .tabs.analysis_tab import AnalysisTab
from .tabs.model3d_tab import Model3DTab
from .tabs.report_tab import ReportTab
from .effects import apply_panel_shadows
from ..core import project as proj


class AppState:
    """Wspoldzielony stan miedzy zakladkami."""
    def __init__(self, window):
        self.window = window
        self.current_model = None
        self.current_airfoil = None
        self.current_result = None
        self.current_polar2d = None      # bieguny 2D profilu (Polar2DResult)
        self.project_path = None         # sciezka biezacego pliku .flovis

    def status(self, text: str):
        self.window.statusBar().showMessage(text, 6000)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flovis - analiza profili i skrzydel")
        self.resize(1180, 760)
        self.state = AppState(self)

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 10, 16, 4)
        title = QLabel("Flovis"); title.setObjectName("h1")
        sub = QLabel("uproszczona analiza aerodynamiczna modeli latajacych")
        sub.setObjectName("hint")
        hl.addWidget(title); hl.addSpacing(12); hl.addWidget(sub); hl.addStretch()

        self.tabs = QTabWidget()
        self.templates_tab = TemplatesTab(self.state)
        self.airfoil_tab = AirfoilTab(self.state)
        self.analysis_tab = AnalysisTab(self.state)
        self.model3d_tab = Model3DTab(self.state)
        self.report_tab = ReportTab(self.state)
        self.tabs.addTab(self.templates_tab, "  Szablony 3D  ")
        self.tabs.addTab(self.airfoil_tab, "  Profile  ")
        self.tabs.addTab(self.analysis_tab, "  Analiza  ")
        self.tabs.addTab(self.model3d_tab, "  Model 3D  ")
        self.tabs.addTab(self.report_tab, "  Raport  ")

        central = QWidget()
        central.setObjectName("central")
        v = QVBoxLayout(central)
        v.setContentsMargins(14, 8, 14, 12)
        v.setSpacing(8)
        v.addWidget(header)
        v.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        central.setStyleSheet("#central { background: #f8f9fa; }")

        self._build_menu()
        # miekkie cienie na panelach sterowania (efekt "unoszenia")
        apply_panel_shadows(self)
        self.statusBar().showMessage("Gotowy.")

    # ------------------------------------------------------------------ menu
    def _build_menu(self):
        m = self.menuBar().addMenu("&Plik")
        m.addAction("Nowy", self._new_project)
        m.addAction("Otworz...", self._open_project)
        m.addSeparator()
        m.addAction("Zapisz", self._save_project)
        m.addAction("Zapisz jako...", self._save_project_as)
        m.addSeparator()
        m.addAction("Eksport PDF...", self._export_pdf)
        m.addSeparator()
        m.addAction("Zakoncz", self.close)

    def _new_project(self):
        from ..core.geometry import make_template, Layout
        self.state.project_path = None
        self.templates_tab.set_model(make_template(Layout.LOW_WING))
        self.state.current_result = None
        self.state.current_polar2d = None
        self.tabs.setCurrentWidget(self.templates_tab)
        self.state.status("Nowy projekt.")

    def _open_project(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Otworz projekt", "",
                                            "Projekt Flovis (*.flovis)")
        if not fn:
            return
        try:
            data = proj.load_project(fn)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Blad odczytu", str(e))
            return
        if data["model"] is not None:
            self.templates_tab.set_model(data["model"])
        if data["airfoil"] is not None:
            self.airfoil_tab.set_airfoil(data["airfoil"])
        if data["result"] is not None:
            self.state.current_result = data["result"]
            self.analysis_tab.show_result(data["result"])
        self.state.project_path = fn
        self.state.status(f"Wczytano projekt: {Path(fn).name}")

    def _save_project(self):
        if self.state.project_path:
            self._write_project(self.state.project_path)
        else:
            self._save_project_as()

    def _save_project_as(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Zapisz projekt",
                                            "model.flovis",
                                            "Projekt Flovis (*.flovis)")
        if fn:
            self._write_project(fn)

    def _write_project(self, fn):
        try:
            p = proj.save_project(
                fn, model=self.state.current_model,
                airfoil=self.state.current_airfoil,
                result=self.state.current_result)
            self.state.project_path = str(p)
            self.state.status(f"Zapisano: {Path(p).name}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Blad zapisu", str(e))

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
    """Ekran startowy 'za reke': wybor sciezki pracy."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Witaj w Flovis")
        self.choice = None
        v = QVBoxLayout(self)
        title = QLabel("Od czego zaczniemy?"); title.setObjectName("h1")
        v.addWidget(title)
        sub = QLabel("Wybierz jedna z opcji - mozesz to zmienic w kazdej chwili.")
        sub.setObjectName("hint"); v.addWidget(sub)
        v.addSpacing(8)
        opts = [
            ("Zacznij od szablonu", "Gotowy uklad samolotu do edycji i analizy.",
             "template"),
            ("Wczytaj model STEP (.stp)", "Analiza dokladnej geometrii z CAD.",
             "step"),
            ("Edytuj profil", "Generator i interaktywny edytor profili lotniczych.",
             "airfoil"),
            ("Otworz projekt (.flovis)", "Wczytaj zapisany wczesniej projekt.",
             "open"),
        ]
        for label, desc, key in opts:
            b = QPushButton(f"{label}\n{desc}")
            b.setMinimumHeight(56)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            v.addWidget(b)
        skip = QPushButton("Pomin"); skip.setProperty("flat", True)
        skip.clicked.connect(self.reject)
        v.addWidget(skip)

    def _pick(self, key):
        self.choice = key
        self.accept()


def load_stylesheet() -> str:
    qss = Path(__file__).resolve().parents[1] / "resources" / "styles" / "flovis.qss"
    return qss.read_text(encoding="utf-8") if qss.exists() else ""
