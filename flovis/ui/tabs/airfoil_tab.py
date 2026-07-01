"""Zakladka: Generator i interaktywny edytor profili + bieguny 2D."""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                               QFormLayout, QLineEdit, QDoubleSpinBox, QSpinBox,
                               QPushButton, QLabel, QCheckBox, QFileDialog,
                               QComboBox, QMessageBox, QGridLayout)
from PySide6.QtCore import QThread, Signal

from ...core.airfoil import Airfoil, parse_naca, NacaSpec, generate
from ...core.airfoil import polar2d
from ..widgets.mpl_canvas import MplCanvas
from ..widgets.airfoil_editor import AirfoilEditor


class _PolarWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, airfoil, alphas, reynolds, ncrit, prefer):
        super().__init__()
        self.airfoil, self.alphas = airfoil, alphas
        self.reynolds, self.ncrit, self.prefer = reynolds, ncrit, prefer

    def run(self):
        try:
            res = polar2d.analyze_polar(
                self.airfoil, alphas=self.alphas, reynolds=self.reynolds,
                ncrit=self.ncrit, prefer=self.prefer)
            self.done.emit(res)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class AirfoilTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self._build()
        self._generate()

    # ------------------------------------------------------------------ build
    def _build(self):
        root = QHBoxLayout(self)
        left = QVBoxLayout()

        # --- generator ---
        gen = QGroupBox("Generator NACA")
        form = QFormLayout(gen)
        self.notation = QLineEdit("NACA 2412")
        self.notation.setPlaceholderText("np. 2412 lub 00011-0.825-35")
        form.addRow("Notacja", self.notation)
        self.modified = QCheckBox("Profil zmodyfikowany (4-cyfrowy)")
        self.modified.toggled.connect(self._toggle_modified)
        form.addRow(self.modified)
        self.le_factor = QDoubleSpinBox()
        self.le_factor.setRange(0.1, 3.0); self.le_factor.setValue(1.0)
        self.le_factor.setSingleStep(0.05); self.le_factor.setEnabled(False)
        form.addRow("Wsp. promienia natarcia", self.le_factor)
        self.maxt_pos = QDoubleSpinBox()
        self.maxt_pos.setRange(15, 60); self.maxt_pos.setValue(30)
        self.maxt_pos.setSuffix(" %"); self.maxt_pos.setEnabled(False)
        form.addRow("Polozenie max grubosci", self.maxt_pos)
        self.npoints = QSpinBox()
        self.npoints.setRange(40, 400); self.npoints.setValue(160)
        form.addRow("Liczba punktow", self.npoints)
        self.sharp_te = QCheckBox("Ostra krawedz splywu")
        form.addRow(self.sharp_te)
        btn_gen = QPushButton("Generuj profil")
        btn_gen.clicked.connect(self._generate)
        form.addRow(btn_gen)
        left.addWidget(gen)

        # --- edytor ---
        edit = QGroupBox("Edytor (przeciagaj punkty myszka)")
        eg = QGridLayout(edit)
        self.b_undo = QPushButton("Cofnij"); self.b_undo.setProperty("flat", True)
        self.b_undo.clicked.connect(self._undo)
        self.b_redo = QPushButton("Ponow"); self.b_redo.setProperty("flat", True)
        self.b_redo.clicked.connect(self._redo)
        b_ins = QPushButton("Wstaw punkt"); b_ins.setProperty("flat", True)
        b_ins.clicked.connect(lambda: self._op(self.editor.insert_point))
        b_del = QPushButton("Usun punkt"); b_del.setProperty("flat", True)
        b_del.clicked.connect(lambda: self._op(self.editor.delete_point))
        b_smooth = QPushButton("Wygladz"); b_smooth.setProperty("flat", True)
        b_smooth.clicked.connect(self._smooth)
        b_repanel = QPushButton("Repanelizacja"); b_repanel.setProperty("flat", True)
        b_repanel.clicked.connect(self._repanel)
        eg.addWidget(self.b_undo, 0, 0); eg.addWidget(self.b_redo, 0, 1)
        eg.addWidget(b_ins, 1, 0); eg.addWidget(b_del, 1, 1)
        eg.addWidget(b_smooth, 2, 0); eg.addWidget(b_repanel, 2, 1)
        self.snap = QCheckBox("Snap do cieciwy"); self.snap.setChecked(True)
        self.snap.toggled.connect(self._toggle_snap)
        self.compare = QCheckBox("Pokaz 'przed' (po wygladzaniu)")
        self.compare.toggled.connect(self._refresh_ghost)
        eg.addWidget(self.snap, 3, 0); eg.addWidget(self.compare, 3, 1)
        self.scale = QDoubleSpinBox(); self.scale.setRange(0.3, 2.0)
        self.scale.setValue(1.0); self.scale.setSingleStep(0.05)
        b_scale = QPushButton("Skala grubosci"); b_scale.setProperty("flat", True)
        b_scale.clicked.connect(self._apply_scale)
        eg.addWidget(self.scale, 4, 0); eg.addWidget(b_scale, 4, 1)
        left.addWidget(edit)

        # --- plik ---
        io_box = QGroupBox("Plik")
        iof = QVBoxLayout(io_box)
        b_load = QPushButton("Wczytaj .dat"); b_load.setProperty("flat", True)
        b_load.clicked.connect(self._load_dat)
        b_save = QPushButton("Zapisz .dat (Selig)")
        b_save.clicked.connect(self._save_dat)
        b_use = QPushButton("Uzyj w analizie"); b_use.setProperty("flat", True)
        b_use.clicked.connect(self._use_in_analysis)
        iof.addWidget(b_load); iof.addWidget(b_save); iof.addWidget(b_use)
        left.addWidget(io_box)

        # --- bieguny ---
        pol = QGroupBox("Bieguny profilu (2D)")
        pf = QFormLayout(pol)
        self.reynolds = QDoubleSpinBox(); self.reynolds.setRange(1e4, 1e7)
        self.reynolds.setDecimals(0); self.reynolds.setSingleStep(5e4)
        self.reynolds.setValue(3e5)
        pf.addRow("Liczba Reynoldsa", self.reynolds)
        self.ncrit = QDoubleSpinBox(); self.ncrit.setRange(1, 14)
        self.ncrit.setValue(9.0); self.ncrit.setSingleStep(0.5)
        pf.addRow("Ncrit", self.ncrit)
        self.method = QComboBox()
        self.method.addItem("Automatyczny (XFoil/NeuralFoil)", "auto")
        self.method.addItem("XFoil", "xfoil")
        self.method.addItem("NeuralFoil", "neuralfoil")
        pf.addRow("Metoda", self.method)
        self.b_polar = QPushButton("Policz bieguny")
        self.b_polar.clicked.connect(self._run_polar)
        pf.addRow(self.b_polar)
        left.addWidget(pol)
        left.addStretch()

        # --- prawa strona ---
        right = QVBoxLayout()
        self.editor = AirfoilEditor()
        self.editor.airfoilChanged.connect(self._on_airfoil_changed)
        right.addWidget(self.editor, 3)
        self.ghost = None

        self.info = QLabel(""); self.info.setObjectName("hint")
        right.addWidget(self.info)
        self.valid_lbl = QLabel(""); self.valid_lbl.setObjectName("hint")
        right.addWidget(self.valid_lbl)

        # wykresy biegunow
        pgrid = QGridLayout()
        self.pcanvas = {}
        for i, key in enumerate(["cl", "polar", "cp"]):
            c = MplCanvas(width=3.2, height=2.2)
            pgrid.addWidget(c, 0, i)
            self.pcanvas[key] = c
        pw = QWidget(); pw.setLayout(pgrid)
        right.addWidget(pw, 2)
        self.polar_info = QLabel(""); self.polar_info.setObjectName("metric")
        right.addWidget(self.polar_info)

        root.addLayout(left, 1)
        root.addLayout(right, 2)

    # --------------------------------------------------------------- generator
    def _toggle_modified(self, on):
        self.le_factor.setEnabled(on)
        self.maxt_pos.setEnabled(on)

    def _toggle_snap(self, on):
        self.editor.snap_enabled = on

    def _spec(self) -> NacaSpec:
        spec = parse_naca(self.notation.text())
        if self.modified.isChecked():
            spec.modified = True
            spec.le_factor = self.le_factor.value()
            spec.max_thickness_pos = self.maxt_pos.value() / 100.0
        return spec

    def _generate(self):
        try:
            spec = self._spec()
            x, y = generate(spec, self.npoints.value(), self.sharp_te.isChecked())
            af = Airfoil(x=x, y=y, name=spec.name, meta={"naca": spec.__dict__})
            self.editor.set_airfoil(af, reset=True)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Blad generowania", str(e))

    # ----------------------------------------------------------------- edycja
    def _op(self, fn):
        fn()

    def _undo(self):
        self.editor.undo()

    def _redo(self):
        self.editor.redo()

    def _smooth(self):
        self._ghost_before = self.editor.airfoil
        self.editor.smooth()
        self._refresh_ghost()

    def _repanel(self):
        self.editor.repanel(self.npoints.value())

    def _apply_scale(self):
        af = self.editor.airfoil
        if af is not None:
            self.editor.set_airfoil(af.scale_thickness(self.scale.value()))

    def _refresh_ghost(self, *_):
        # pokaz kontur sprzed wygladzenia jako bladsza linia
        if self.ghost is not None:
            self.editor.plot.removeItem(self.ghost)
            self.ghost = None
        before = getattr(self, "_ghost_before", None)
        if self.compare.isChecked() and before is not None:
            import pyqtgraph as pg
            self.ghost = pg.PlotCurveItem(
                before.x, before.y,
                pen=pg.mkPen("#9ca3af", width=1, style=2))
            self.editor.plot.addItem(self.ghost)

    # ------------------------------------------------------------------- plik
    def _load_dat(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Wczytaj profil", "",
                                            "Profil (*.dat *.txt)")
        if fn:
            self.editor.set_airfoil(Airfoil.from_dat(fn), reset=True)

    def _save_dat(self):
        af = self.editor.airfoil
        if not af:
            return
        fn, _ = QFileDialog.getSaveFileName(self, "Zapisz profil",
                                            f"{af.name}.dat",
                                            "Profil Selig (*.dat)")
        if fn:
            af.to_dat(fn)
            QMessageBox.information(self, "Zapisano", f"Profil zapisany:\n{fn}")

    def _use_in_analysis(self):
        if self.editor.airfoil is not None:
            self.state.current_airfoil = self.editor.airfoil
            QMessageBox.information(self, "OK",
                                    "Profil ustawiony jako biezacy do analizy.")

    def set_airfoil(self, af):
        """Ustawia profil z zewnatrz (np. po wczytaniu projektu)."""
        self.editor.set_airfoil(af, reset=True)

    # --------------------------------------------------------------- callbacks
    def _on_airfoil_changed(self, af: Airfoil):
        self.state.current_airfoil = af
        self.b_undo.setEnabled(self.editor.can_undo())
        self.b_redo.setEnabled(self.editor.can_redo())
        s = af.summary()
        self.info.setText(
            f"Punkty: {s['n_points']}   |   grubosc max: "
            f"{s['max_thickness']*100:.1f}% @ {s['max_thickness_pos']*100:.0f}%c"
            f"   |   strzalka: {s['max_camber']*100:.2f}% "
            f"@ {s['max_camber_pos']*100:.0f}%c")
        issues = af.validate()
        if issues:
            self.valid_lbl.setText("Uwaga: " + " ".join(issues))
            self.valid_lbl.setStyleSheet("color:#dc2626;")
        else:
            self.valid_lbl.setText("Geometria poprawna.")
            self.valid_lbl.setStyleSheet("color:#059669;")

    # ----------------------------------------------------------------- bieguny
    def _run_polar(self):
        af = self.editor.airfoil
        if af is None:
            return
        if af.validate():
            QMessageBox.warning(self, "Geometria",
                                "Popraw geometrie profilu przed analiza biegunow.")
            return
        self.b_polar.setEnabled(False)
        self.b_polar.setText("Liczenie...")
        self.state.status("Analiza biegunow profilu...")
        self.pworker = _PolarWorker(
            af, np.linspace(-6, 16, 23), self.reynolds.value(),
            self.ncrit.value(), self.method.currentData())
        self.pworker.done.connect(self._show_polar)
        self.pworker.failed.connect(self._polar_failed)
        self.pworker.start()

    def _polar_failed(self, msg):
        self.b_polar.setEnabled(True); self.b_polar.setText("Policz bieguny")
        QMessageBox.critical(self, "Blad analizy 2D", msg)

    def _show_polar(self, res):
        self.b_polar.setEnabled(True); self.b_polar.setText("Policz bieguny")
        self.state.current_polar2d = res
        # Cl(alfa)
        c = self.pcanvas["cl"]; c.clear()
        c.ax.plot(res.alpha, res.cl, "-o", color="#2563eb", ms=2.5, lw=1.4)
        c.ax.axhline(0, color="#9ca3af", lw=0.5)
        c.ax.set_xlabel("alpha [deg]", fontsize=8); c.ax.set_ylabel("Cl", fontsize=8)
        c.ax.set_title("Cl(alfa)", fontsize=9, weight="bold")
        self._style(c)
        # Cl(Cd)
        c = self.pcanvas["polar"]; c.clear()
        c.ax.plot(res.cd, res.cl, "-o", color="#2563eb", ms=2.5, lw=1.4)
        c.ax.set_xlabel("Cd", fontsize=8); c.ax.set_ylabel("Cl", fontsize=8)
        c.ax.set_title("Biegunowa Cl(Cd)", fontsize=9, weight="bold")
        self._style(c)
        # Cp
        c = self.pcanvas["cp"]; c.clear()
        if res.cp is not None and res.cp_x is not None:
            c.ax.plot(res.cp_x, res.cp, "-", color="#dc2626", lw=1.2)
            c.ax.invert_yaxis()
            c.ax.set_title(f"Cp @ {res.cp_alpha:.0f} deg", fontsize=9, weight="bold")
        else:
            c.ax.text(0.5, 0.5, "Cp dostepne tylko z XFoila",
                      ha="center", va="center", fontsize=8, color="#6b7280")
            c.ax.set_title("Rozklad Cp", fontsize=9, weight="bold")
        c.ax.set_xlabel("x/c", fontsize=8); c.ax.set_ylabel("Cp", fontsize=8)
        self._style(c)
        self.polar_info.setText(
            f"[{res.method}]  Cl_max = {res.cl_max:.2f} @ {res.alpha_stall:.1f} deg"
            f"   |   (Cl/Cd)_max = {res.ld_max:.0f} @ {res.alpha_ld_max:.1f} deg"
            f"   |   Re = {res.reynolds:.0f}")
        self.state.status(f"Bieguny gotowe ({res.method}).")

    @staticmethod
    def _style(c):
        c.ax.grid(True, color="#e5e7eb", lw=0.5)
        for s in ("top", "right"):
            c.ax.spines[s].set_visible(False)
        c.fig.tight_layout(); c.draw()
