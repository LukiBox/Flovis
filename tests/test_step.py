"""Regression tests for STEP analysis - guards the mapped Cp pressure field.

Historical bug: the direct panel solve on the raw STEP mesh produced a
saturated, uniformly-blue Cp field (all values pinned at the clip floor).
These tests generate a real STEP wing with gmsh and assert the field is
finite, non-saturated, contains both suction AND stagnation, and is
spanwise-symmetric; the fitted polar must have a sane lift-curve slope.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flovis.core.airfoil import Airfoil  # noqa: E402

gmsh = pytest.importorskip("gmsh")

from flovis.core.solvers import panel_step  # noqa: E402


@pytest.fixture(scope="module")
def wing_step(tmp_path_factory):
    """A simple rectangular NACA 2412 wing written to a STEP file."""
    out = tmp_path_factory.mktemp("step") / "wing.step"
    af = Airfoil.from_naca("2412", n_points=60)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("wing")
        occ = gmsh.model.occ

        def wire(y, chord):
            pts = [occ.addPoint(x * chord, y, z * chord)
                   for x, z in zip(af.x, af.y)]
            sp = occ.addSpline(pts + [pts[0]])
            return occ.addWire([sp])

        w1 = wire(-0.75, 0.25)
        w2 = wire(0.75, 0.25)
        occ.addThruSections([w1, w2], makeSolid=True)
        occ.synchronize()
        gmsh.write(str(out))
    finally:
        gmsh.finalize()
    return out


def test_step_pressure_field_not_broken(wing_step):
    res = panel_step.analyze_step(wing_step, velocity=15,
                                  alphas=np.array([0.0, 4.0, 8.0]))
    cp = np.asarray(res.extras["cp"])
    assert np.all(np.isfinite(cp))
    # a real pressure gradient: suction AND stagnation must both be present
    assert cp.min() < -0.3, "no suction region - field is broken"
    assert cp.max() > 0.3, "no stagnation region - field is broken"
    # not saturated: the bulk of the surface must NOT sit at the clip floor
    assert np.mean(cp <= -2.0) < 0.15, "field saturated at the clip floor"


def test_step_pressure_field_symmetric(wing_step):
    res = panel_step.analyze_step(wing_step, velocity=15,
                                  alphas=np.array([4.0]))
    cp = np.asarray(res.extras["cp"])
    nodes = np.asarray(res.extras["cp_nodes"])
    faces = np.asarray(res.extras["cp_faces"])
    fc = nodes[faces].mean(axis=1)
    left = cp[fc[:, 1] < -0.05]
    right = cp[fc[:, 1] > 0.05]
    assert len(left) and len(right)
    assert abs(left.mean() - right.mean()) < 0.05


def test_step_polar_sane(wing_step):
    res = panel_step.analyze_step(wing_step, velocity=15)
    # AR 6 rectangular wing: lifting line predicts ~4.5/rad
    assert 3.5 < res.CL_alpha < 5.5
    assert res.extras["n_panels"] > 100
    assert res.LD_max > 5
