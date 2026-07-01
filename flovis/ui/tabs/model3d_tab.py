"""Tab: 3D Model - geometry and pressure-distribution visualization (PyVista)."""
from __future__ import annotations

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                               QPushButton, QCheckBox, QLabel, QMessageBox)

from ...core.i18n import t


class Model3DTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self.view = None
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        left = QVBoxLayout()

        box = QGroupBox(t("3D view"))
        v = QVBoxLayout(box)
        b_load = QPushButton(t("Show current model"))
        b_load.clicked.connect(self._load_model)
        v.addWidget(b_load)
        b_press = QPushButton(t("Apply pressure field (Cp)"))
        b_press.setProperty("flat", True)
        b_press.clicked.connect(self._show_pressure)
        v.addWidget(b_press)
        b_reset = QPushButton(t("Reset view")); b_reset.setProperty("flat", True)
        b_reset.clicked.connect(self._reset)
        v.addWidget(b_reset)
        left.addWidget(box)

        layers = QGroupBox(t("Layers"))
        lv = QVBoxLayout(layers)
        self.cb_wings = QCheckBox(t("Wings / tails")); self.cb_wings.setChecked(True)
        self.cb_fus = QCheckBox(t("Fuselage")); self.cb_fus.setChecked(True)
        self.cb_mark = QCheckBox(t("CG and neutral point")); self.cb_mark.setChecked(True)
        for cb, key in ((self.cb_wings, "skrzydla"), (self.cb_fus, "kadlub"),
                        (self.cb_mark, "markery")):
            cb.toggled.connect(lambda on, k=key: self._toggle(k, on))
            lv.addWidget(cb)
        left.addWidget(layers)

        self.hint = QLabel(t("Load a model from the Templates tab to see the 3D "
                             "body here. After an analysis the pressure map is applied."))
        self.hint.setObjectName("hint"); self.hint.setWordWrap(True)
        left.addWidget(self.hint)
        left.addStretch()

        self.holder = QVBoxLayout()
        self.placeholder = QLabel(t("The 3D view appears here once a model is loaded."))
        self.placeholder.setObjectName("hint")
        self.holder.addWidget(self.placeholder)

        root.addLayout(left, 0)
        rw = QWidget(); rw.setLayout(self.holder)
        root.addWidget(rw, 1)

    def _ensure_view(self) -> bool:
        if self.view is not None:
            return True
        try:
            from ..widgets.model3d_view import Model3DView
            self.view = Model3DView(self)
            if self.placeholder is not None:
                self.placeholder.setParent(None); self.placeholder = None
            self.holder.addWidget(self.view.widget)
            return True
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(
                self, t("3D view unavailable"),
                t("Could not initialize the PyVista/VTK view:\n") + str(e))
            return False

    def _load_model(self):
        if self.state.current_model is None:
            QMessageBox.information(self, t("No model"),
                                    t("Set up a model in the Templates tab first."))
            return
        if not self._ensure_view():
            return
        self.view.set_model(self.state.current_model)
        self.hint.setText(t("Rotate with the mouse, zoom with the scroll wheel. "
                            "Cp is applied after a panel/STEP analysis."))

    def _is_step(self, res) -> bool:
        ex = getattr(res, "extras", {}) or {}
        return ex.get("cp_nodes") is not None

    def _show_pressure(self):
        if not self._ensure_view():
            return
        res = self.state.current_result
        if res is None:
            QMessageBox.information(self, t("No results"),
                                    t("Run an analysis first (Analysis / STEP)."))
            if self.state.current_model is not None:
                self.view.set_model(self.state.current_model)
            return
        if not self._is_step(res) and self.state.current_model is None:
            QMessageBox.information(self, t("No model"),
                                    t("Set up a model in the Templates tab first."))
            return
        self._render_pressure(res)

    def show_step_result(self, res):
        """Render STEP geometry with Cp (called after a STEP analysis)."""
        if not self._ensure_view():
            return
        self._render_pressure(res)

    def _render_pressure(self, res):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        self.hint.setText(t("Computing the surface pressure distribution..."))
        self.state.status(t("Pressure distribution (Cp) running..."))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            if self._is_step(res):
                self.view.show_step(res)
            else:
                self.view.show_result(res)
        finally:
            QApplication.restoreOverrideCursor()
        self.hint.setText(t("Cp field: blue = suction (low pressure), "
                            "red = stagnation (high pressure). Rotate with the mouse."))
        self.state.status(t("Pressure distribution ready."))

    def _toggle(self, key, on):
        if self.view is not None:
            self.view.set_layer(key, on)

    def _reset(self):
        if self.view is not None:
            self.view.render()
