"""Testy solverow 3D: analityczny, VLM, AVL - zgodnosc rzedu wielkosci."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flovis.core.geometry import make_template, Layout  # noqa: E402
from flovis.core.solvers import (solve_analytic, solve_aerosandbox,  # noqa: E402
                                 solve_avl, avl_available)

_ALPHAS = np.linspace(-4, 10, 6)


def _slope(res):
    a = res.alpha_deg
    return float(np.polyfit(np.deg2rad(a), res.CL, 1)[0])


def test_analytic_basic():
    m = make_template(Layout.LOW_WING)
    res = solve_analytic(m, velocity=15, alphas=_ALPHAS)
    assert res.method.startswith("Analityczny")
    assert 3.0 < res.CL_alpha < 7.0          # rozsadne nachylenie /rad
    assert res.static_margin != 0.0


def test_vlm_if_available():
    asb = pytest.importorskip("aerosandbox")
    m = make_template(Layout.LOW_WING)
    res = solve_aerosandbox(m, velocity=15, alphas=_ALPHAS, viscous=False)
    assert res.method.startswith("VLM")
    assert 3.5 < res.CL_alpha < 6.5


def test_vlm_vs_analytic_same_order():
    pytest.importorskip("aerosandbox")
    m = make_template(Layout.LOW_WING)
    a = solve_analytic(m, velocity=15, alphas=_ALPHAS)
    v = solve_aerosandbox(m, velocity=15, alphas=_ALPHAS, viscous=False)
    # zgodnosc rzedu wielkosci nachylenia CL
    assert abs(a.CL_alpha - v.CL_alpha) / v.CL_alpha < 0.4


def test_avl_if_available():
    if not avl_available():
        pytest.skip("AVL niedostepny")
    m = make_template(Layout.LOW_WING)
    res = solve_avl(m, velocity=15, alphas=_ALPHAS)
    assert res.method == "AVL"
    assert 3.5 < res.CL_alpha < 6.5
    assert res.neutral_point_x > 0


def test_avl_vs_vlm_agree():
    if not avl_available():
        pytest.skip("AVL niedostepny")
    pytest.importorskip("aerosandbox")
    m = make_template(Layout.LOW_WING)
    v = solve_aerosandbox(m, velocity=15, alphas=_ALPHAS, viscous=False)
    a = solve_avl(m, velocity=15, alphas=_ALPHAS)
    assert abs(a.CL_alpha - v.CL_alpha) / v.CL_alpha < 0.15    # < 15%
