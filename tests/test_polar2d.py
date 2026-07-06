"""Testy analizy 2D profilu: parsery (mock XFoil) + NeuralFoil + XFoil (jesli jest)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flovis.core.airfoil import Airfoil, polar2d  # noqa: E402

_SAMPLE_POLAR = """\
 XFOIL         Version 6.99
 alpha    CL        CD       CDp       CM
 ------ -------- --------- --------- --------
  0.000   0.2200   0.00600   0.00200  -0.0500
  4.000   0.7100   0.00900   0.00350  -0.0540
  8.000   1.0500   0.01600   0.00800  -0.0560
"""

_SAMPLE_CP = """\
   1.00000   0.10000
   0.50000  -0.80000
   0.00000   1.00000
"""


def test_parse_polar_file():
    a, cl, cd, cm = polar2d._parse_polar_file(_SAMPLE_POLAR)
    assert len(a) == 3
    assert np.isclose(cl[1], 0.71)
    assert np.isclose(cd[2], 0.016)
    assert np.isclose(cm[0], -0.05)


def test_parse_cp_file():
    x, cp = polar2d._parse_cp_file(_SAMPLE_CP)
    assert len(x) == 3
    assert np.isclose(cp[1], -0.8)


def test_polar2d_result_postprocess():
    res = polar2d.Polar2DResult(
        method="test", reynolds=3e5, ncrit=9, mach=0,
        alpha=np.array([0., 4., 8.]), cl=np.array([0.2, 0.7, 1.05]),
        cd=np.array([0.006, 0.009, 0.016]), cm=np.array([-0.05, -0.054, -0.056]))
    assert np.isclose(res.cl_max, 1.05)
    assert res.alpha_stall == 8.0
    assert res.ld_max > 0


def test_neuralfoil_if_available():
    if not polar2d.neuralfoil_available():
        pytest.skip("NeuralFoil niedostepny")
    af = Airfoil.from_naca("2412", n_points=120)
    r = polar2d.analyze_neuralfoil(af, alphas=np.array([0., 4., 8.]), reynolds=3e5)
    assert r.method == "NeuralFoil"
    assert 0.1 < r.cl[1] < 1.2          # rozsadne CL przy 4 deg


def test_xfoil_if_available():
    if not polar2d.xfoil_available():
        pytest.skip("XFoil niedostepny")
    af = Airfoil.from_naca("2412", n_points=120)
    r = polar2d.analyze_xfoil(af, alphas=np.array([0., 4., 8.]), reynolds=3e5)
    assert r.method == "XFoil"
    assert r.cl.size >= 2
    assert r.cl_max > 0.3
