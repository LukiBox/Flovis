"""Zakladka: Szablony 3D - wybor ukladu i edycja parametrow."""
from __future__ import annotations

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                               QFormLayout, QComboBox, QDoubleSpinBox,
                               QLabel, QScrollArea, QPushButton, QLineEdit)
from PySide6.QtCore import Qt

from ...core.geometry import Layout, make_template, ALL_TEMPLATES
from ..widgets.mpl_canvas import MplCanvas


class TemplatesTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self.model = make_template(Layout.LOW_WING)
        self._surf_widgets = []
        self._build()
        self._load_model()

    def _build(self):
        root = QHBoxLayout(self)
        left = QVBoxLayout()

        pick = QGroupBox("Uklad samolotu")
        pf = QFormLayout(pick)
        self.layout_cb = QComboBox()
        for lay in ALL_TEMPLATES:
            self.layout_cb.addItem(lay.value, lay)
        self.layout_cb.currentIndexChanged.connect(self._change_layout)
        pf.addRow("Konfiguracja", self.layout_cb)
        self.mass = QDoubleSpinBox(); self.mass.setRange(0.1, 50); self.mass.setSuffix(" kg")
        self.mass.valueChanged.connect(self._sync)
        pf.addRow("Masa", self.mass)
        self.cg = QDoubleSpinBox(); self.cg.setRange(0, 5); self.cg.setSuffix(" m")
        self.cg.setSingleStep(0.005); self.cg.setDecimals(3)
        self.cg.valueChanged.connect(self._sync)
        pf.addRow("Srodek ciezkosci x", self.cg)
        left.addWidget(pick)

        # parametry plaszczyzn w scrollu
        self.surf_area = QScrollArea(); self.surf_area.setWidgetResizable(True)
        self.surf_holder = QWidget()
        self.surf_layout = QVBoxLayout(self.surf_holder)
        self.surf_area.setWidget(self.surf_holder)
        left.addWidget(self.surf_area, 1)

        b_use = QPushButton("Ustaw jako biezacy model")
        b_use.clicked.connect(self._use)
        left.addWidget(b_use)

        right = QVBoxLayout()
        self.canvas = MplCanvas(width=6, height=4)
        right.addWidget(self.canvas)
        self.info = QLabel(""); self.info.setObjectName("hint")
        right.addWidget(self.info)

        root.addLayout(left, 1)
        root.addLayout(right, 1)

    def _change_layout(self):
        lay = self.layout_cb.currentData()
        self.model = make_template(lay)          # odporne na str (Qt splasza enum)
        self._load_model()
        self.state.status(f"Zaladowano uklad: {self.model.name}")

    def set_model(self, model):
        """Ustawia model z zewnatrz (np. po wczytaniu projektu)."""
        self.model = model
        want = getattr(model.layout, "value", str(model.layout))
        idx = -1
        for i in range(self.layout_cb.count()):
            data = self.layout_cb.itemData(i)
            if getattr(data, "value", str(data)) == want:
                idx = i
                break
        if idx >= 0:
            self.layout_cb.blockSignals(True)
            self.layout_cb.setCurrentIndex(idx)
            self.layout_cb.blockSignals(False)
        self._load_model()
        self.state.current_model = model

    def _load_model(self):
        self.mass.blockSignals(True); self.cg.blockSignals(True)
        self.mass.setValue(self.model.mass_kg)
        self.cg.setValue(self.model.cg_x)
        self.mass.blockSignals(False); self.cg.blockSignals(False)
        # odbuduj edytory plaszczyzn
        for i in reversed(range(self.surf_layout.count())):
            w = self.surf_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        self._surf_widgets = []
        for idx, s in enumerate(self.model.surfaces):
            box = QGroupBox(s.name)
            f = QFormLayout(box)
            fields = {}
            specs = [("span", "Rozpietosc [m]", 0.05, 5, 0.01),
                     ("root_chord", "Cieciwa nasady [m]", 0.02, 2, 0.005),
                     ("tip_chord", "Cieciwa konca [m]", 0.02, 2, 0.005),
                     ("sweep_deg", "Skos [deg]", -10, 45, 0.5),
                     ("dihedral_deg", "Wznios [deg]", -10, 20, 0.5),
                     ("x_le", "Pozycja X [m]", 0, 5, 0.01)]
            for attr, label, lo, hi, step in specs:
                sp = QDoubleSpinBox(); sp.setRange(lo, hi); sp.setSingleStep(step)
                sp.setDecimals(3); sp.setValue(getattr(s, attr))
                sp.valueChanged.connect(lambda v, i=idx, a=attr: self._edit(i, a, v))
                f.addRow(label, sp); fields[attr] = sp
            af = QLineEdit(s.airfoil_root)
            af.editingFinished.connect(
                lambda i=idx, w=af: self._edit(i, "airfoil_root", w.text()))
            f.addRow("Profil nasady", af)
            self.surf_layout.addWidget(box)
            self._surf_widgets.append(fields)
        self.surf_layout.addStretch()
        self._refresh()

    def _edit(self, idx, attr, value):
        setattr(self.model.surfaces[idx], attr, value)
        self._refresh()

    def _sync(self):
        self.model.mass_kg = self.mass.value()
        self.model.cg_x = self.cg.value()
        self._refresh()

    def _refresh(self):
        """Rysuje rzut z gory (planform) modelu."""
        self.canvas.clear()
        ax = self.canvas.ax
        for s in self.model.surfaces:
            if s.is_vertical:
                continue
            import numpy as np
            dx_tip = 0.5 * s.span * np.tan(np.deg2rad(s.sweep_deg))
            xle, c_r, c_t = s.x_le, s.root_chord, s.tip_chord
            half = s.span / 2
            xs = [xle, xle + c_r, xle + dx_tip + c_t, xle + dx_tip, xle]
            ys = [0, 0, half, half, 0]
            ax.fill(xs, ys, alpha=0.3, label=s.name)
            ax.fill(xs, [-v for v in ys], alpha=0.3)
        ax.axvline(self.model.cg_x, color="#dc2626", lw=1, ls="--", label="CG")
        ax.set_aspect("equal"); ax.grid(True, color="#e5e7eb", lw=0.5)
        ax.set_xlabel("X [m]"); ax.set_ylabel("Y [m]")
        ax.legend(fontsize=7, loc="upper right")
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        self.canvas.draw()
        w = self.model.wing
        AR = w.span**2 / w.area if w and w.area else 0
        self.info.setText(
            f"Powierzchnia skrzydla: {w.area*1e4:.0f} cm2   |   "
            f"MAC: {w.mac*1000:.0f} mm   |   wydluzenie AR: {AR:.1f}")
        self.state.current_model = self.model

    def _use(self):
        self.state.current_model = self.model
