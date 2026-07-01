"""Osadzony wykres matplotlib w Qt."""
from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, width=5, height=3.2, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor="white")
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)

    def clear(self):
        self.fig.clf()
        self.ax = self.fig.add_subplot(111)
