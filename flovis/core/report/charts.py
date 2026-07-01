"""Wykresy do raportow (matplotlib) - styl minimalistyczny."""
from __future__ import annotations

import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_ACCENT = "#2563eb"
_GRID = "#e5e7eb"


def _style(ax, xlabel, ylabel, title):
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=10, weight="bold", color="#111827")
    ax.grid(True, color=_GRID, linewidth=0.6)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(labelsize=8)


def _to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def cl_alpha_png(res) -> bytes:
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ax.plot(res.alpha_deg, res.CL, "-o", color=_ACCENT, ms=3, lw=1.6)
    ax.axhline(0, color="#9ca3af", lw=0.6)
    _style(ax, "alpha [deg]", "CL", "Krzywa sily nosnej CL(alpha)")
    return _to_png(fig)


def polar_png(res) -> bytes:
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ax.plot(res.CD, res.CL, "-o", color=_ACCENT, ms=3, lw=1.6)
    _style(ax, "CD", "CL", "Biegunowa CL(CD)")
    return _to_png(fig)


def cm_alpha_png(res) -> bytes:
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ax.plot(res.alpha_deg, res.Cm, "-o", color="#dc2626", ms=3, lw=1.6)
    ax.axhline(0, color="#9ca3af", lw=0.6)
    _style(ax, "alpha [deg]", "Cm", "Moment pochylajacy Cm(alpha)")
    return _to_png(fig)


def ld_png(res) -> bytes:
    import numpy as np
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ld = np.where(res.CD > 1e-6, res.CL / res.CD, 0)
    ax.plot(res.alpha_deg, ld, "-o", color="#059669", ms=3, lw=1.6)
    _style(ax, "alpha [deg]", "L/D", "Doskonalosc L/D(alpha)")
    return _to_png(fig)


def polar2d_cl_png(pol) -> bytes:
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ax.plot(pol.alpha, pol.cl, "-o", color=_ACCENT, ms=3, lw=1.6)
    ax.axhline(0, color="#9ca3af", lw=0.6)
    _style(ax, "alpha [deg]", "Cl", f"Profil: Cl(alfa)  [{pol.method}]")
    return _to_png(fig)


def polar2d_clcd_png(pol) -> bytes:
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ax.plot(pol.cd, pol.cl, "-o", color=_ACCENT, ms=3, lw=1.6)
    _style(ax, "Cd", "Cl", "Profil: biegunowa Cl(Cd)")
    return _to_png(fig)


def cp_png(pol) -> bytes:
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    if pol.cp is not None and pol.cp_x is not None:
        ax.plot(pol.cp_x, pol.cp, "-", color="#dc2626", lw=1.3)
        ax.invert_yaxis()
        _style(ax, "x/c", "Cp", f"Rozklad Cp @ {pol.cp_alpha:.0f} deg")
    else:
        ax.text(0.5, 0.5, "Cp dostepne tylko z XFoila", ha="center",
                va="center", fontsize=9, color="#6b7280")
        _style(ax, "x/c", "Cp", "Rozklad Cp")
    return _to_png(fig)


def airfoil_png(af) -> bytes:
    fig, ax = plt.subplots(figsize=(5.5, 1.8))
    ax.plot(af.x, af.y, "-", color=_ACCENT, lw=1.4)
    ax.fill(af.x, af.y, color=_ACCENT, alpha=0.06)
    ax.set_aspect("equal")
    ax.set_title(af.name, fontsize=10, weight="bold")
    ax.grid(True, color=_GRID, linewidth=0.5)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=7)
    return _to_png(fig)
