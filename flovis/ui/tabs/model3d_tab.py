"""Zakladka: Model 3D - wizualizacja bryly i rozkladu cisnienia (PyVista)."""
from __future__ import annotations

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                               QPushButton, QCheckBox, QLabel, QMessageBox)


class Model3DTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self.view = None
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        left = QVBoxLayout()

        box = QGroupBox("Widok 3D")
        v = QVBoxLayout(box)
        b_load = QPushButton("Pokaz biezacy model")
        b_load.clicked.connect(self._load_model)
        v.addWidget(b_load)
        b_press = QPushButton("Nalozy rozklad cisnienia (Cp)")
        b_press.setProperty("flat", True)
        b_press.clicked.connect(self._show_pressure)
        v.addWidget(b_press)
        b_reset = QPushButton("Resetuj widok"); b_reset.setProperty("flat", True)
        b_reset.clicked.connect(self._reset)
        v.addWidget(b_reset)
        left.addWidget(box)

        layers = QGroupBox("Warstwy")
        lv = QVBoxLayout(layers)
        self.cb_wings = QCheckBox("Skrzydla / usterzenia"); self.cb_wings.setChecked(True)
        self.cb_fus = QCheckBox("Kadlub"); self.cb_fus.setChecked(True)
        self.cb_mark = QCheckBox("CG i punkt neutralny"); self.cb_mark.setChecked(True)
        for cb, key in ((self.cb_wings, "skrzydla"), (self.cb_fus, "kadlub"),
                        (self.cb_mark, "markery")):
            cb.toggled.connect(lambda on, k=key: self._toggle(k, on))
            lv.addWidget(cb)
        left.addWidget(layers)

        self.hint = QLabel("Wczytaj model z zakladki Szablony, a tu zobaczysz "
                           "bryle 3D. Po analizie nalozy mape cisnienia.")
        self.hint.setObjectName("hint"); self.hint.setWordWrap(True)
        left.addWidget(self.hint)
        left.addStretch()

        self.holder = QVBoxLayout()
        self.placeholder = QLabel("Widok 3D pojawi sie tutaj po wczytaniu modelu.")
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
                self, "Widok 3D niedostepny",
                "Nie udalo sie zainicjowac widoku PyVista/VTK:\n" + str(e))
            return False

    def _load_model(self):
        if self.state.current_model is None:
            QMessageBox.information(self, "Brak modelu",
                                    "Najpierw ustaw model w zakladce Szablony.")
            return
        if not self._ensure_view():
            return
        self.view.set_model(self.state.current_model)
        self.hint.setText("Obracaj mysza, przyblizaj scrollem. "
                          "Nalozy Cp po wykonaniu analizy panelowej/STEP.")

    def _is_step(self, res) -> bool:
        ex = getattr(res, "extras", {}) or {}
        return ex.get("cp_nodes") is not None

    def _show_pressure(self):
        if not self._ensure_view():
            return
        res = self.state.current_result
        if res is None:
            QMessageBox.information(self, "Brak wynikow",
                                    "Najpierw uruchom analize (Analiza / STEP).")
            if self.state.current_model is not None:
                self.view.set_model(self.state.current_model)
            return
        if not self._is_step(res) and self.state.current_model is None:
            QMessageBox.information(self, "Brak modelu",
                                    "Najpierw ustaw model w zakladce Szablony.")
            return
        self._render_pressure(res)

    def show_step_result(self, res):
        """Renderuje geometrie STEP z Cp (wywolywane po analizie STEP)."""
        if not self._ensure_view():
            return
        self._render_pressure(res)

    def _render_pressure(self, res):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        self.hint.setText("Licze rozklad cisnienia na powierzchni...")
        self.state.status("Rozklad cisnienia (Cp) w toku...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            if self._is_step(res):
                self.view.show_step(res)
            else:
                self.view.show_result(res)
        finally:
            QApplication.restoreOverrideCursor()
        self.hint.setText("Rozklad Cp: niebieski = podcisnienie (ssanie), "
                          "czerwony = nadcisnienie (spietrzenie). Obracaj mysza.")
        self.state.status("Rozklad cisnienia gotowy.")

    def _toggle(self, key, on):
        if self.view is not None:
            self.view.set_layer(key, on)

    def _reset(self):
        if self.view is not None:
            self.view.render(result=self.state.current_result)
