"""Tab: Templates 3D - pick a layout, edit parameters, place control surfaces."""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                               QFormLayout, QComboBox, QDoubleSpinBox,
                               QLabel, QScrollArea, QPushButton, QLineEdit)

from ...core.geometry import (ALL_TEMPLATES, ControlKind, ControlSurface,
                              Layout, default_control_surfaces, make_template)
from ...core.i18n import t
from .. import theme
from ..widgets.mpl_canvas import MplCanvas


class TemplatesTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self.model = make_template(Layout.LOW_WING)
        self._surf_widgets = []
        self._building = False
        self._build()
        self._load_model()

    def _build(self):
        root = QHBoxLayout(self)
        left = QVBoxLayout()

        pick = QGroupBox(t("Aircraft layout"))
        pf = QFormLayout(pick)
        self.layout_cb = QComboBox()
        for lay in ALL_TEMPLATES:
            self.layout_cb.addItem(t(lay.value), lay.value)
        self.layout_cb.currentIndexChanged.connect(self._change_layout)
        pf.addRow(t("Configuration"), self.layout_cb)
        self.mass = QDoubleSpinBox(); self.mass.setRange(0.1, 50); self.mass.setSuffix(" kg")
        self.mass.valueChanged.connect(self._sync)
        pf.addRow(t("Mass"), self.mass)
        self.cg = QDoubleSpinBox(); self.cg.setRange(0, 5); self.cg.setSuffix(" m")
        self.cg.setSingleStep(0.005); self.cg.setDecimals(3)
        self.cg.valueChanged.connect(self._sync)
        pf.addRow(t("Center of gravity x"), self.cg)
        left.addWidget(pick)

        self.surf_area = QScrollArea(); self.surf_area.setWidgetResizable(True)
        self.surf_holder = QWidget()
        self.surf_layout = QVBoxLayout(self.surf_holder)
        self.surf_area.setWidget(self.surf_holder)
        left.addWidget(self.surf_area, 1)

        b_use = QPushButton(t("Set as current model"))
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
        self.model = make_template(lay)          # robust to str (Qt flattens enum)
        self._load_model()
        self.state.status(t("Loaded layout: {}").format(t(self.model.name)))

    def set_model(self, model):
        """Set the model from outside (e.g. after loading a project)."""
        self.model = model
        want = getattr(model.layout, "value", str(model.layout))
        idx = -1
        for i in range(self.layout_cb.count()):
            if str(self.layout_cb.itemData(i)) == want:
                idx = i
                break
        if idx >= 0:
            self.layout_cb.blockSignals(True)
            self.layout_cb.setCurrentIndex(idx)
            self.layout_cb.blockSignals(False)
        self._load_model()
        self.state.current_model = model

    # ------------------------------------------------------------- editors
    def _load_model(self):
        self._building = True
        self.mass.blockSignals(True); self.cg.blockSignals(True)
        self.mass.setValue(self.model.mass_kg)
        self.cg.setValue(self.model.cg_x)
        self.mass.blockSignals(False); self.cg.blockSignals(False)
        for i in reversed(range(self.surf_layout.count())):
            item = self.surf_layout.takeAt(i)
            w = item.widget()
            if w:
                w.deleteLater()
        self._surf_widgets = []
        for idx, s in enumerate(self.model.surfaces):
            box = QGroupBox(t(s.name))
            f = QFormLayout(box)
            fields = {}
            specs = [("span", t("Span [m]"), 0.05, 5, 0.01),
                     ("root_chord", t("Root chord [m]"), 0.02, 2, 0.005),
                     ("tip_chord", t("Tip chord [m]"), 0.02, 2, 0.005),
                     ("sweep_deg", t("Sweep [deg]"), -10, 45, 0.5),
                     ("dihedral_deg", t("Dihedral [deg]"), -10, 20, 0.5),
                     ("x_le", t("Position X [m]"), 0, 5, 0.01)]
            for attr, label, lo, hi, step in specs:
                sp = QDoubleSpinBox(); sp.setRange(lo, hi); sp.setSingleStep(step)
                sp.setDecimals(3); sp.setValue(getattr(s, attr))
                sp.valueChanged.connect(lambda v, i=idx, a=attr: self._edit(i, a, v))
                f.addRow(label, sp); fields[attr] = sp
            af = QLineEdit(s.airfoil_root)
            af.editingFinished.connect(
                lambda i=idx, w=af: self._edit(i, "airfoil_root", w.text()))
            f.addRow(t("Root airfoil"), af)
            self.surf_layout.addWidget(box)
            self._surf_widgets.append(fields)

        self._build_controls_editor()
        self.surf_layout.addStretch()
        self._building = False
        self._refresh()

    def _build_controls_editor(self):
        box = QGroupBox(t("Control surfaces"))
        v = QVBoxLayout(box)
        hint = QLabel(t("Carried through to StructVis and SimVis - the "
                        "simulator derives control power from this placement."))
        hint.setObjectName("hint"); hint.setWordWrap(True)
        v.addWidget(hint)
        names = [s.name for s in self.model.surfaces]
        for idx, cs in enumerate(self.model.control_surfaces):
            row_box = QGroupBox(t(cs.kind.value))
            f = QFormLayout(row_box)
            kind = QComboBox()
            for k in ControlKind:
                kind.addItem(t(k.value), k.value)
            kind.setCurrentIndex(list(ControlKind).index(cs.kind))
            kind.currentIndexChanged.connect(
                lambda _i, i=idx, w=kind: self._edit_cs(i, "kind",
                                                        w.currentData()))
            f.addRow(t("Type"), kind)
            parent = QComboBox()
            parent.addItems(names)
            if cs.parent in names:
                parent.setCurrentText(cs.parent)
            parent.currentTextChanged.connect(
                lambda v_, i=idx: self._edit_cs(i, "parent", v_))
            f.addRow(t("On surface"), parent)
            for attr, label, lo, hi, step in (
                    ("span_start", t("Span from"), 0.0, 0.98, 0.05),
                    ("span_end", t("Span to"), 0.02, 1.0, 0.05),
                    ("chord_fraction", t("Chord fraction"), 0.05, 0.75, 0.05),
                    ("max_deflection_deg", t("Throw [deg]"), 5.0, 60.0, 1.0)):
                sp = QDoubleSpinBox(); sp.setRange(lo, hi)
                sp.setSingleStep(step); sp.setDecimals(2)
                sp.setValue(getattr(cs, attr))
                sp.valueChanged.connect(
                    lambda v_, i=idx, a=attr: self._edit_cs(i, a, v_))
                f.addRow(label, sp)
            rm = QPushButton(t("Remove")); rm.setProperty("flat", True)
            rm.clicked.connect(lambda _=False, i=idx: self._remove_cs(i))
            f.addRow(rm)
            v.addWidget(row_box)
        add_row = QHBoxLayout()
        b_add = QPushButton(t("Add control surface")); b_add.setProperty("flat", True)
        b_add.clicked.connect(self._add_cs)
        b_def = QPushButton(t("Reset to defaults")); b_def.setProperty("flat", True)
        b_def.clicked.connect(self._default_cs)
        add_row.addWidget(b_add); add_row.addWidget(b_def)
        v.addLayout(add_row)
        self.surf_layout.addWidget(box)

    # ------------------------------------------------------------- edits
    def _edit(self, idx, attr, value):
        setattr(self.model.surfaces[idx], attr, value)
        self._refresh()

    def _edit_cs(self, idx, attr, value):
        if self._building or idx >= len(self.model.control_surfaces):
            return
        cs = self.model.control_surfaces[idx]
        if attr == "kind":
            cs.kind = ControlKind(value)
            if cs.name in {k.value for k in ControlKind}:
                cs.name = cs.kind.value
        else:
            setattr(cs, attr, value)
        # keep the extent ordered without fighting the user mid-typing
        if cs.span_end < cs.span_start + 0.02:
            cs.span_end = min(cs.span_start + 0.02, 1.0)
        self._refresh()

    def _add_cs(self):
        wing = self.model.wing
        self.model.control_surfaces.append(ControlSurface(
            ControlKind.FLAP, wing.name if wing else "Wing",
            0.10, 0.42, chord_fraction=0.30, max_deflection_deg=35.0))
        self._load_model()

    def _remove_cs(self, idx):
        if 0 <= idx < len(self.model.control_surfaces):
            del self.model.control_surfaces[idx]
            self._load_model()

    def _default_cs(self):
        self.model.control_surfaces = default_control_surfaces(
            self.model.layout, self.model.surfaces)
        self._load_model()

    def _sync(self):
        self.model.mass_kg = self.mass.value()
        self.model.cg_x = self.cg.value()
        self._refresh()

    # ------------------------------------------------------------- planform
    def _refresh(self):
        """Draw the top-view planform, control surfaces included."""
        if self._building:
            return
        self.canvas.clear()
        theme.style_canvas(self.canvas)
        ax = self.canvas.ax
        tok = theme.tokens()
        for s in self.model.surfaces:
            if s.is_vertical:
                continue
            dx_tip = 0.5 * s.span * np.tan(np.deg2rad(s.sweep_deg))
            xle, c_r, c_t = s.x_le, s.root_chord, s.tip_chord
            half = s.span / 2
            xs = [xle, xle + c_r, xle + dx_tip + c_t, xle + dx_tip, xle]
            ys = [0, 0, half, half, 0]
            ax.fill(xs, ys, alpha=0.35, color=tok["accent"], label=t(s.name))
            ax.fill(xs, [-v for v in ys], alpha=0.35, color=tok["accent"])
        self._draw_control_surfaces(ax)
        ax.axvline(self.model.cg_x, color=tok["danger"], lw=1, ls="--",
                   label="CG")
        ax.set_aspect("equal"); ax.grid(True, lw=0.5)
        ax.set_xlabel("X [m]"); ax.set_ylabel("Y [m]")
        leg = ax.legend(fontsize=7, loc="upper right")
        leg.get_frame().set_alpha(0.6)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        self.canvas.draw()
        w = self.model.wing
        AR = w.span**2 / w.area if w and w.area else 0
        self.info.setText(
            t("Wing area: {a} cm2   |   MAC: {m} mm   |   aspect ratio AR: {ar}")
            .format(a=f"{w.area*1e4:.0f}", m=f"{w.mac*1000:.0f}", ar=f"{AR:.1f}"))
        self.state.current_model = self.model

    def _draw_control_surfaces(self, ax):
        """Amber patches: the hinged part of each horizontal parent surface."""
        tok = theme.tokens()
        by_name = {s.name: s for s in self.model.surfaces}
        labeled = False
        for cs in self.model.control_surfaces:
            s = by_name.get(cs.parent)
            if s is None or s.is_vertical:
                continue
            half = s.span / 2

            def le(eta):
                return s.x_le + half * eta * np.tan(np.deg2rad(s.sweep_deg))

            def chord(eta):
                return s.root_chord + (s.tip_chord - s.root_chord) * eta

            e0, e1 = cs.span_start, cs.span_end
            xa0 = le(e0) + (1 - cs.chord_fraction) * chord(e0)
            xa1 = le(e1) + (1 - cs.chord_fraction) * chord(e1)
            xt0 = le(e0) + chord(e0)
            xt1 = le(e1) + chord(e1)
            for sign in (1, -1):
                ys = [half * e0 * sign, half * e1 * sign,
                      half * e1 * sign, half * e0 * sign]
                ax.fill([xa0, xa1, xt1, xt0], ys, alpha=0.9,
                        color=tok["warning"], lw=0,
                        label=t("controls") if not labeled else None)
                labeled = True

    def _use(self):
        self.state.current_model = self.model
