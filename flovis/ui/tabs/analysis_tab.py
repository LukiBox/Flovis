"""Tab: Analysis - run a solver and preview the results."""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                               QFormLayout, QDoubleSpinBox, QComboBox,
                               QPushButton, QLabel, QFileDialog, QMessageBox,
                               QGridLayout)
from PySide6.QtCore import QThread, Signal

from ...core.solvers import analyze, panel_step
from ...core.i18n import t
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
    """STEP analysis in the background - keeps the UI responsive.

    Meshing runs in a killable subprocess (cancel/timeout safe); the meshed
    arrays are also emitted so the tab can re-run the analysis with a
    different orientation without re-meshing.
    """
    progress = Signal(str)
    meshed = Signal(object)                 # (nodes, quads, model_name)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, path, velocity, orientation):
        super().__init__()
        self.path, self.velocity = path, velocity
        self.orientation = orientation

    def run(self):
        try:
            from pathlib import Path
            self.progress.emit(t("Loading and meshing STEP geometry..."))
            nodes, quads = panel_step.load_and_mesh_step_safe(self.path)
            name = Path(self.path).stem
            self.meshed.emit((nodes, quads, name))
            self.progress.emit(t("Fitting planform and mapping Cp..."))
            res = panel_step.analyze_step_mesh(
                nodes, quads, model_name=name, velocity=self.velocity,
                orientation=self.orientation)
            self.done.emit(res)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class _ReorientWorker(QThread):
    """Re-run the fitted analysis on the cached mesh (fast, no gmsh)."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, mesh, velocity, orientation):
        super().__init__()
        self.mesh, self.velocity = mesh, velocity
        self.orientation = orientation

    def run(self):
        try:
            nodes, quads, name = self.mesh
            res = panel_step.analyze_step_mesh(
                nodes, quads, model_name=name, velocity=self.velocity,
                orientation=self.orientation)
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

        cfg = QGroupBox(t("Analysis setup"))
        f = QFormLayout(cfg)
        self.velocity = QDoubleSpinBox(); self.velocity.setRange(2, 80)
        self.velocity.setValue(15); self.velocity.setSuffix(" m/s")
        f.addRow(t("Velocity"), self.velocity)
        self.solver = QComboBox()
        self.solver.addItem(t("Automatic (VLM/analytic)"), "auto")
        self.solver.addItem("VLM (AeroSandbox)", "aerosandbox")
        self.solver.addItem(t("AVL (accurate mode)"), "avl")
        self.solver.addItem(t("Analytic"), "analytic")
        f.addRow(t("Solver"), self.solver)
        left.addWidget(cfg)

        b_run = QPushButton(t("Run template analysis"))
        b_run.clicked.connect(self._run)
        left.addWidget(b_run)

        step = QGroupBox(t("Exact analysis (.stp)"))
        sf = QVBoxLayout(step)
        self.b_step = QPushButton(t("Load STEP and analyze"))
        self.b_step.setProperty("flat", True)
        self.b_step.clicked.connect(self._step_button)
        sf.addWidget(self.b_step)
        orient_row = QHBoxLayout()
        orient_row.addWidget(QLabel(t("Orientation")))
        self.step_orient = QComboBox()
        self.step_orient.addItem(t("Auto-detect"), "auto")
        for key in panel_step.ORIENTATIONS:
            if key != "auto":
                self.step_orient.addItem(t(key), key)
        self.step_orient.currentIndexChanged.connect(self._reorient_step)
        orient_row.addWidget(self.step_orient, 1)
        sf.addLayout(orient_row)
        orient_hint = QLabel(t("Wrong way up or sideways? Pick which CAD "
                               "axes are chord and span - the analysis "
                               "reruns instantly, no re-mesh."))
        orient_hint.setObjectName("hint"); orient_hint.setWordWrap(True)
        sf.addWidget(orient_hint)
        deps = panel_step.dependencies_available()
        ok = deps.get("gmsh", False)
        status = t("ready (gmsh)") if ok else t("MISSING gmsh - install: pip install gmsh")
        lbl = QLabel(t("STEP engine: {}").format(status)); lbl.setObjectName("hint")
        lbl.setWordWrap(True)
        sf.addWidget(lbl)
        self.step_status = QLabel(""); self.step_status.setObjectName("hint")
        self.step_status.setWordWrap(True)
        sf.addWidget(self.step_status)
        left.addWidget(step)
        self._step_mesh = None            # cached (nodes, quads, name)
        self._step_running = False

        self.metrics = QGroupBox(t("Results"))
        self.mlay = QGridLayout(self.metrics)
        self._metric_labels = {}
        for i, (key, name) in enumerate([
            ("CL_alpha", "CL_alpha [/rad]"), ("Cm_alpha", "Cm_alpha [/rad]"),
            ("CL_max", "CL max"), ("LD_max", "(L/D) max"),
            ("static_margin", t("Static margin [%MAC]")),
            ("neutral_point_x", t("Neutral point [m]"))]):
            self.mlay.addWidget(QLabel(name), i, 0)
            v = QLabel("-"); v.setObjectName("metric")
            self.mlay.addWidget(v, i, 1)
            self._metric_labels[key] = v
        left.addWidget(self.metrics)
        left.addStretch()

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
            QMessageBox.warning(self, t("No model"),
                                t("Set up a model in the Templates tab first."))
            return
        self.state.status(t("Analysis running..."))
        self.worker = _Worker(model, self.velocity.value(),
                              self.solver.currentData())
        self.worker.done.connect(self._show)
        self.worker.failed.connect(
            lambda m: QMessageBox.critical(self, t("Analysis error"), m))
        self.worker.start()

    def _step_button(self):
        """Load-and-analyze normally; while running, the button cancels."""
        if self._step_running:
            panel_step.cancel_current_mesh()
            self.step_status.setText(t("Cancelling..."))
            return
        self._run_step()

    def _run_step(self):
        if not panel_step.dependencies_available().get("gmsh", False):
            QMessageBox.warning(
                self, t("STEP engine missing"),
                t("STEP analysis requires gmsh.\nInstall:  pip install gmsh"))
            return
        fn, _ = QFileDialog.getOpenFileName(self, t("Load STEP model"), "",
                                            "STEP (*.stp *.step)")
        if not fn:
            return
        self._step_running = True
        self.b_step.setText(t("Cancel (analysis running...)"))
        self.step_status.setText(t("Loading geometry..."))
        self.state.status(t("STEP analysis: loading and meshing..."))
        self.step_worker = _StepWorker(fn, self.velocity.value(),
                                       self.step_orient.currentData())
        self.step_worker.progress.connect(self.step_status.setText)
        self.step_worker.meshed.connect(self._step_meshed)
        self.step_worker.done.connect(self._step_done)
        self.step_worker.failed.connect(self._step_failed)
        self.step_worker.start()

    def _step_meshed(self, mesh):
        self._step_mesh = mesh                    # (nodes, quads, name)

    def _reorient_step(self):
        """Orientation changed: rerun the fit on the cached mesh (no gmsh)."""
        if self._step_mesh is None or self._step_running:
            return
        self._step_running = True
        self.b_step.setText(t("Cancel (analysis running...)"))
        self.step_status.setText(t("Re-fitting with the new orientation..."))
        self.reorient_worker = _ReorientWorker(
            self._step_mesh, self.velocity.value(),
            self.step_orient.currentData())
        self.reorient_worker.done.connect(self._step_done)
        self.reorient_worker.failed.connect(self._step_failed)
        self.reorient_worker.start()

    def _step_done(self, res):
        self._step_running = False
        self.b_step.setEnabled(True)
        self.b_step.setText(t("Load STEP and analyze"))
        n = res.extras.get("n_panels", "?")
        pf = res.extras.get("planform", {})
        orient = res.extras.get("orientation", "")
        self.step_status.setText(
            t("Done: {n} panels. Planform: span {s} m, chord {c} m, airfoil {a}.")
            .format(n=n, s=pf.get('span', '?'), c=pf.get('root_chord', '?'),
                    a=pf.get('naca', '?'))
            + (f"   [{t('orientation')}: {orient}]" if orient else ""))
        self._show(res)
        win = getattr(self.state, "window", None)
        shown_3d = False
        if win is not None and hasattr(win, "model3d_tab") and hasattr(win, "tabs"):
            try:
                win.model3d_tab.show_step_result(res)
                win.tabs.setCurrentWidget(win.model3d_tab)
                shown_3d = True
            except Exception:  # noqa: BLE001
                shown_3d = False
        tail = (t("STEP geometry with the Cp field is now in the 3D Model tab.")
                if shown_3d else
                t("View the Cp field in the 3D Model tab ('Apply Cp' button)."))
        QMessageBox.information(
            self, t("STEP analysis finished"),
            t("Method: {m}\nSTEP panels: {n}\nCL_alpha = {cla} /rad\n"
              "(L/D)_max = {ld}\n\n").format(
                m=res.method, n=n, cla=f"{res.CL_alpha:.2f}",
                ld=f"{res.LD_max:.1f}") + tail)

    def _step_failed(self, msg):
        self._step_running = False
        self.b_step.setEnabled(True)
        self.b_step.setText(t("Load STEP and analyze"))
        cancelled = "cancel" in msg.lower()
        self.step_status.setText(t("Cancelled.") if cancelled
                                 else t("STEP analysis error."))
        self.state.status(t("STEP analysis failed."))
        if not cancelled:
            QMessageBox.critical(self, t("STEP analysis error"), msg)

    def show_result(self, res):
        """Show a result from outside (e.g. after loading a project)."""
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
            "polar": (res.CD, res.CL, "CD", "CL", t("Polar"), "#2563eb"),
            "cm": (res.alpha_deg, res.Cm, "alpha [deg]", "Cm", "Cm(alpha)", "#dc2626"),
            "ld": (res.alpha_deg, np.where(res.CD > 1e-6, res.CL / res.CD, 0),
                   "alpha [deg]", "L/D", t("Efficiency"), "#059669"),
        }
        for key, (x, y, xl, yl, title, col) in plots.items():
            c = self.canvases[key]; c.clear()
            c.ax.plot(x, y, "-o", color=col, ms=3, lw=1.4)
            c.ax.set_xlabel(xl, fontsize=8); c.ax.set_ylabel(yl, fontsize=8)
            c.ax.set_title(title, fontsize=9, weight="bold")
            c.ax.grid(True, color="#e5e7eb", lw=0.5)
            for s in ("top", "right"):
                c.ax.spines[s].set_visible(False)
            c.fig.tight_layout(); c.draw()
        self.state.status(t("Analysis ready ({}).").format(res.method))
