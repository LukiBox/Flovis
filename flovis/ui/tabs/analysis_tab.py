"""Zakladka: Analiza - uruchomienie solvera i podglad wynikow."""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                               QFormLayout, QDoubleSpinBox, QComboBox,
                               QPushButton, QLabel, QFileDialog, QMessageBox,
                               QGridLayout)
from PySide6.QtCore import QThread, Signal

from ...core.solvers import analyze, panel_step
from ..widgets.mpl_canvas import MplCanvas


class _Worker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, model, velocity, prefer):
        super().__init__()
        self.model, self.velocity, self.prefer = model, velocity, prefer

    def run(self):
        try:
            res = analyze(self.model, velocity=self.velocity,
                          alphas=np.linspace(-4, 14, 10), prefer=self.prefer)
            self.done.emit(res)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class _StepWorker(QThread):
    """Analiza STEP w tle - nie blokuje UI (gmsh + solver panelowy trwaja)."""
    progress = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, path, velocity):
        super().__init__()
        self.path, self.velocity = path, velocity

    def run(self):
        try:
            self.progress.emit("Wczytywanie i siatkowanie geometrii STEP...")
            res = panel_step.analyze_step(self.path, velocity=self.velocity)
            self.done.emit(res)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class AnalysisTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        left = QVBoxLayout()

        cfg = QGroupBox("Konfiguracja analizy")
        f = QFormLayout(cfg)
        self.velocity = QDoubleSpinBox(); self.velocity.setRange(2, 80)
        self.velocity.setValue(15); self.velocity.setSuffix(" m/s")
        f.addRow("Predkosc", self.velocity)
        self.solver = QComboBox()
        self.solver.addItem("Automatyczny (VLM/analityczny)", "auto")
        self.solver.addItem("VLM (AeroSandbox)", "aerosandbox")
        self.solver.addItem("AVL (tryb dokladny)", "avl")
        self.solver.addItem("Analityczny", "analytic")
        f.addRow("Solver", self.solver)
        left.addWidget(cfg)

        b_run = QPushButton("Uruchom analize szablonu")
        b_run.clicked.connect(self._run)
        left.addWidget(b_run)

        step = QGroupBox("Analiza dokladna (.stp)")
        sf = QVBoxLayout(step)
        self.b_step = QPushButton("Wczytaj STEP i analizuj")
        self.b_step.setProperty("flat", True)
        self.b_step.clicked.connect(self._run_step)
        sf.addWidget(self.b_step)
        deps = panel_step.dependencies_available()
        ok = deps.get("gmsh", False)
        status = "gotowe (gmsh)" if ok else "BRAK gmsh - zainstaluj: pip install gmsh"
        lbl = QLabel(f"Silnik STEP: {status}"); lbl.setObjectName("hint")
        lbl.setWordWrap(True)
        sf.addWidget(lbl)
        self.step_status = QLabel(""); self.step_status.setObjectName("hint")
        self.step_status.setWordWrap(True)
        sf.addWidget(self.step_status)
        left.addWidget(step)

        self.metrics = QGroupBox("Wyniki")
        self.mlay = QGridLayout(self.metrics)
        self._metric_labels = {}
        for i, (key, name) in enumerate([
            ("CL_alpha", "CL_alpha [/rad]"), ("Cm_alpha", "Cm_alpha [/rad]"),
            ("CL_max", "CL max"), ("LD_max", "(L/D) max"),
            ("static_margin", "Zapas statecz. [%MAC]"),
            ("neutral_point_x", "Pkt neutralny [m]")]):
            self.mlay.addWidget(QLabel(name), i, 0)
            v = QLabel("-"); v.setObjectName("metric")
            self.mlay.addWidget(v, i, 1)
            self._metric_labels[key] = v
        left.addWidget(self.metrics)
        left.addStretch()

        # prawy: 4 wykresy
        right = QGridLayout()
        self.canvases = {}
        for i, key in enumerate(["cl", "polar", "cm", "ld"]):
            c = MplCanvas(width=4, height=2.6)
            right.addWidget(c, i // 2, i % 2)
            self.canvases[key] = c
        rw = QWidget(); rw.setLayout(right)

        root.addLayout(left, 1)
        root.addWidget(rw, 2)

    def _run(self):
        model = self.state.current_model
        if model is None:
            QMessageBox.warning(self, "Brak modelu",
                                "Najpierw skonfiguruj model w zakladce Szablony.")
            return
        self.state.status("Analiza w toku...")
        self.worker = _Worker(model, self.velocity.value(),
                              self.solver.currentData())
        self.worker.done.connect(self._show)
        self.worker.failed.connect(
            lambda m: QMessageBox.critical(self, "Blad analizy", m))
        self.worker.start()

    def _run_step(self):
        if not panel_step.dependencies_available().get("gmsh", False):
            QMessageBox.warning(
                self, "Brak silnika STEP",
                "Analiza STEP wymaga biblioteki gmsh.\n"
                "Zainstaluj:  pip install gmsh")
            return
        fn, _ = QFileDialog.getOpenFileName(self, "Wczytaj model STEP", "",
                                            "STEP (*.stp *.step)")
        if not fn:
            return
        self.b_step.setEnabled(False)
        self.b_step.setText("Analiza STEP w toku...")
        self.step_status.setText("Wczytywanie geometrii...")
        self.state.status("Analiza STEP: wczytywanie i siatkowanie...")
        self.step_worker = _StepWorker(fn, self.velocity.value())
        self.step_worker.progress.connect(self.step_status.setText)
        self.step_worker.done.connect(self._step_done)
        self.step_worker.failed.connect(self._step_failed)
        self.step_worker.start()

    def _step_done(self, res):
        self.b_step.setEnabled(True)
        self.b_step.setText("Wczytaj STEP i analizuj")
        n = res.extras.get("n_panels", "?")
        pf = res.extras.get("planform", {})
        self.step_status.setText(
            f"Gotowe: {n} paneli. Obrys: rozp. {pf.get('span','?')} m, "
            f"cieciwa {pf.get('root_chord','?')} m, profil {pf.get('naca','?')}.")
        self._show(res)
        # automatycznie pokaz geometrie STEP z rozkladem Cp w widoku 3D
        win = getattr(self.state, "window", None)
        shown_3d = False
        if win is not None and hasattr(win, "model3d_tab") and hasattr(win, "tabs"):
            try:
                win.model3d_tab.show_step_result(res)
                win.tabs.setCurrentWidget(win.model3d_tab)
                shown_3d = True
            except Exception:  # noqa: BLE001
                shown_3d = False
        tail = ("Geometria STEP z rozkladem Cp jest juz w zakladce Model 3D."
                if shown_3d else
                "Pole Cp obejrzysz w zakladce Model 3D (przycisk 'Nalozy Cp').")
        QMessageBox.information(
            self, "Analiza STEP zakonczona",
            f"Metoda: {res.method}\nPaneli STEP: {n}\n"
            f"CL_alpha = {res.CL_alpha:.2f} /rad\n"
            f"(L/D)_max = {res.LD_max:.1f}\n\n" + tail)

    def _step_failed(self, msg):
        self.b_step.setEnabled(True)
        self.b_step.setText("Wczytaj STEP i analizuj")
        self.step_status.setText("Blad analizy STEP.")
        self.state.status("Analiza STEP nie powiodla sie.")
        QMessageBox.critical(self, "Blad analizy STEP", msg)

    def show_result(self, res):
        """Wyswietla wynik z zewnatrz (np. po wczytaniu projektu)."""
        self._show(res)

    def _show(self, res):
        self.state.current_result = res
        m = self._metric_labels
        m["CL_alpha"].setText(f"{res.CL_alpha:.2f}")
        m["Cm_alpha"].setText(f"{res.Cm_alpha:.2f}")
        m["CL_max"].setText(f"{res.CL_max:.2f}")
        m["LD_max"].setText(f"{res.LD_max:.1f}")
        m["static_margin"].setText(f"{res.static_margin*100:.0f}")
        m["neutral_point_x"].setText(f"{res.neutral_point_x:.3f}")

        plots = {
            "cl": (res.alpha_deg, res.CL, "alpha [deg]", "CL", "CL(alpha)", "#2563eb"),
            "polar": (res.CD, res.CL, "CD", "CL", "Biegunowa", "#2563eb"),
            "cm": (res.alpha_deg, res.Cm, "alpha [deg]", "Cm", "Cm(alpha)", "#dc2626"),
            "ld": (res.alpha_deg, np.where(res.CD > 1e-6, res.CL / res.CD, 0),
                   "alpha [deg]", "L/D", "Doskonalosc", "#059669"),
        }
        for key, (x, y, xl, yl, t, col) in plots.items():
            c = self.canvases[key]; c.clear()
            c.ax.plot(x, y, "-o", color=col, ms=3, lw=1.4)
            c.ax.set_xlabel(xl, fontsize=8); c.ax.set_ylabel(yl, fontsize=8)
            c.ax.set_title(t, fontsize=9, weight="bold")
            c.ax.grid(True, color="#e5e7eb", lw=0.5)
            for s in ("top", "right"):
                c.ax.spines[s].set_visible(False)
            c.fig.tight_layout(); c.draw()
        self.state.status(f"Analiza gotowa ({res.method}).")
