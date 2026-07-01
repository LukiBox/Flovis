"""Test integracyjny metody panelowej: skrzydlo prostokatne vs VLM (< ~10%)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flovis.core.solvers import panel_method as pm  # noqa: E402


def _panel_cl(mesh, span, chord, adeg, V=15.0):
    a = np.deg2rad(adeg)
    vinf = V * np.array([np.cos(a), 0, np.sin(a)])
    sol = pm.solve_panel(mesh, vinf)
    g, dy = sol["gamma"]
    S = span * chord
    return 2 * float(np.sum(g * dy)) / (V * S)


def test_panel_lift_slope_linear():
    """CL rosnie liniowo z alfa i jest ~zerowe przy 0 (profil symetryczny)."""
    mesh = pm.make_wing_mesh(span=1.5, chord=0.25, n_chord=20, n_span=12,
                             naca="0012")
    cl0 = _panel_cl(mesh, 1.5, 0.25, 0.0)
    cl4 = _panel_cl(mesh, 1.5, 0.25, 4.0)
    cl8 = _panel_cl(mesh, 1.5, 0.25, 8.0)
    assert abs(cl0) < 0.02
    assert cl4 > 0.15
    # liniowosc: cl8 ~ 2*cl4
    assert abs(cl8 - 2 * cl4) / cl4 < 0.2


def test_panel_vs_vlm_within_10pct():
    """Nachylenie CL_alpha metody panelowej zgodne z VLM < 10% (skalibrowana siatka)."""
    pytest.importorskip("aerosandbox")
    from flovis.core.geometry.templates import Surface, AircraftModel, Layout
    from flovis.core.solvers import solve_aerosandbox

    span, chord = 1.5, 0.25
    mesh = pm.make_wing_mesh(span=span, chord=chord, n_chord=20, n_span=12,
                             naca="0012")
    alphas = np.array([0., 2., 4., 6.])
    cls = np.array([_panel_cl(mesh, span, chord, a) for a in alphas])
    slope_panel = np.polyfit(np.deg2rad(alphas), cls, 1)[0]

    w = Surface("Skrzydlo", span=span, root_chord=chord, tip_chord=chord,
                airfoil_root="NACA 0012", airfoil_tip="NACA 0012")
    m = AircraftModel("plyta", Layout.LOW_WING, [w], cg_x=chord * 0.25)
    v = solve_aerosandbox(m, velocity=15, alphas=alphas, viscous=False)

    rel = abs(slope_panel - v.CL_alpha) / v.CL_alpha
    assert rel < 0.10, f"panel {slope_panel:.3f} vs VLM {v.CL_alpha:.3f} ({rel*100:.0f}%)"
