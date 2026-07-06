"""
Interactive airfoil editor (pyqtgraph).

Features:
  * dragging individual contour points with the mouse,
  * inserting / deleting points (at the selection),
  * undo / redo (a stack of Airfoil states),
  * snap to chord (y -> 0 within a small distance),
  * cosine repaneling,
  * live geometry validation (color + message).

Emits airfoilChanged(Airfoil) after every change.
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout

from ...core.airfoil import Airfoil


class _DraggableContour(pg.GraphItem):
    """Kontur jako lamana z przeciaganymi wezlami (na bazie pyqtgraph)."""

    def __init__(self):
        self.drag_index: int | None = None
        self.drag_offset = None
        self.on_drag = None       # callback(index, x, y) podczas ruchu
        self.on_release = None    # callback() po puszczeniu
        super().__init__()

    def setData(self, **kwds):
        self.data = kwds
        if "pos" in kwds:
            n = len(kwds["pos"])
            # polacz kolejne punkty w lamana
            adj = np.column_stack([np.arange(n - 1), np.arange(1, n)])
            self.data["adj"] = adj
        super().setData(**self.data)

    def mouseDragEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            ev.ignore()
            return
        if ev.isStart():
            pos = ev.buttonDownPos()
            pts = self.scatter.pointsAt(pos)
            if len(pts) == 0:
                self.drag_index = None
                ev.ignore()
                return
            ind = pts[0].index()
            self.drag_index = ind
            self.drag_offset = self.data["pos"][ind] - np.array([pos.x(), pos.y()])
        elif ev.isFinish():
            if self.drag_index is not None and self.on_release:
                self.on_release()
            self.drag_index = None
            return
        else:
            if self.drag_index is None:
                ev.ignore()
                return

        ind = self.drag_index
        new = np.array([ev.pos().x(), ev.pos().y()]) + self.drag_offset
        self.data["pos"][ind] = new
        super().setData(**self.data)
        if self.on_drag:
            self.on_drag(ind, float(new[0]), float(new[1]))
        ev.accept()


class AirfoilEditor(QWidget):
    airfoilChanged = Signal(object)
    pointSelected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.airfoil: Airfoil | None = None
        self._undo: list[Airfoil] = []
        self._redo: list[Airfoil] = []
        self.selected: int = 0
        self.snap_enabled = True
        self.snap_tol = 0.004

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        from .. import theme
        self.plot = pg.PlotWidget()
        self.plot.setBackground(theme.plot_bg())
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setAspectLocked(True)
        self.plot.setLabel("bottom", "x/c")
        self.plot.setLabel("left", "y/c")
        lay.addWidget(self.plot)

        self.curve = pg.PlotCurveItem(pen=pg.mkPen("#2563eb", width=2))
        self.plot.addItem(self.curve)
        self.graph = _DraggableContour()
        self.graph.on_drag = self._on_drag
        self.graph.on_release = self._on_release
        self.plot.addItem(self.graph)
        # podswietlenie zaznaczonego punktu
        self.sel_marker = pg.ScatterPlotItem(
            size=12, pen=pg.mkPen("#dc2626", width=2), brush=None)
        self.plot.addItem(self.sel_marker)
        # klik wybiera punkt
        self.graph.scatter.sigClicked.connect(self._on_click)

    # ---------- stan ----------
    def set_airfoil(self, af: Airfoil, push_undo: bool = True, reset: bool = False):
        if reset:
            self._undo.clear()
            self._redo.clear()
        elif push_undo and self.airfoil is not None:
            self._undo.append(self._clone(self.airfoil))
            self._redo.clear()
        self.airfoil = af
        self.selected = min(self.selected, len(af.x) - 1)
        self._render()
        self.airfoilChanged.emit(af)

    @staticmethod
    def _clone(af: Airfoil) -> Airfoil:
        return Airfoil(x=af.x.copy(), y=af.y.copy(), name=af.name,
                       meta=dict(af.meta))

    def _render(self):
        af = self.airfoil
        pos = np.column_stack([af.x, af.y])
        self.graph.setData(pos=pos, size=7,
                           symbolBrush=pg.mkBrush("#93c5fd"),
                           symbolPen=pg.mkPen("#2563eb"), pxMode=True)
        self.curve.setData(af.x, af.y)
        self._update_selection()

    def _update_selection(self):
        af = self.airfoil
        if af is None or not len(af.x):
            return
        i = int(np.clip(self.selected, 0, len(af.x) - 1))
        self.sel_marker.setData([af.x[i]], [af.y[i]])

    # ---------- interakcja ----------
    def _on_click(self, scatter, points):
        if len(points):
            self.selected = points[0].index()
            self._update_selection()
            self.pointSelected.emit(self.selected)

    def _on_drag(self, index, x, y):
        if self.snap_enabled and abs(y) < self.snap_tol:
            y = 0.0
        # aktualizacja modelu w locie (bez undo na kazda klatke)
        self.airfoil = self.airfoil.set_point(index, x, y)
        self.selected = index
        self.curve.setData(self.airfoil.x, self.airfoil.y)
        self._update_selection()

    def _on_release(self):
        # zatwierdz przesuniecie jako jeden krok undo
        af = self.airfoil
        self._undo.append(self._clone(af))
        if len(self._undo) > 100:
            self._undo.pop(0)
        self._redo.clear()
        self._render()
        self.airfoilChanged.emit(af)

    # ---------- operacje ----------
    def insert_point(self):
        if self.airfoil is None:
            return
        self.set_airfoil(self.airfoil.insert_point(self.selected))

    def delete_point(self):
        if self.airfoil is None or len(self.airfoil.x) <= 5:
            return
        self.set_airfoil(self.airfoil.delete_point(self.selected))

    def repanel(self, n_points: int = 160):
        if self.airfoil is not None:
            self.set_airfoil(self.airfoil.repanel(n_points))

    def smooth(self):
        if self.airfoil is not None:
            self.set_airfoil(self.airfoil.smooth())

    def undo(self):
        if self._undo:
            self._redo.append(self._clone(self.airfoil))
            self.airfoil = self._undo.pop()
            self._render()
            self.airfoilChanged.emit(self.airfoil)

    def redo(self):
        if self._redo:
            self._undo.append(self._clone(self.airfoil))
            self.airfoil = self._redo.pop()
            self._render()
            self.airfoilChanged.emit(self.airfoil)

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)
