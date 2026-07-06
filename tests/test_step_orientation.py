"""STEP orientation: auto-detect, manual override, subprocess meshing."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flovis.core.solvers.panel_step import (ORIENTATIONS, orient_nodes)  # noqa: E402


def _wing_cloud(chord_ax=0, span_ax=1):
    """A fake wing point cloud: chord 0.25, span 1.5, thickness 0.03."""
    rng = np.random.default_rng(3)
    n = 4000
    pts = np.zeros((n, 3))
    thick_ax = ({0, 1, 2} - {chord_ax, span_ax}).pop()
    pts[:, chord_ax] = rng.uniform(0.0, 0.25, n)
    pts[:, span_ax] = rng.uniform(-0.75, 0.75, n)
    pts[:, thick_ax] = rng.uniform(-0.015, 0.015, n)
    return pts


@pytest.mark.parametrize("chord_ax,span_ax", [(0, 1), (0, 2), (1, 0),
                                              (1, 2), (2, 0), (2, 1)])
def test_auto_detect_any_export_convention(chord_ax, span_ax):
    """Whatever axes the CAD used, auto lands span on Y and chord on X."""
    pts = _wing_cloud(chord_ax, span_ax)
    out, label = orient_nodes(pts, "auto")
    ext = out.max(0) - out.min(0)
    assert ext[1] > ext[0] > ext[2]          # span > chord > thickness
    assert np.isclose(ext[1], 1.5, atol=0.01)
    assert np.isclose(ext[0], 0.25, atol=0.01)
    assert "(auto)" in label


def test_manual_orientation_override():
    pts = _wing_cloud(chord_ax=2, span_ax=0)   # exotic export
    out, label = orient_nodes(pts, "chord Z, span X")
    ext = out.max(0) - out.min(0)
    assert np.isclose(ext[0], 0.25, atol=0.01)  # chord on X now
    assert np.isclose(ext[1], 1.5, atol=0.01)   # span on Y now
    assert label == "chord Z, span X"


def test_orientation_names_are_complete():
    assert set(ORIENTATIONS) == {"auto", "chord X, span Y", "chord X, span Z",
                                 "chord Y, span X", "chord Y, span Z",
                                 "chord Z, span X", "chord Z, span Y"}
    with pytest.raises(ValueError):
        orient_nodes(np.zeros((4, 3)), "nonsense")


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("gmsh"),
    reason="gmsh not installed")
def test_subprocess_meshing_round_trip(tmp_path):
    """The killable-subprocess path returns the same kind of mesh."""
    gmsh = pytest.importorskip("gmsh")
    from flovis.core.solvers.panel_step import load_and_mesh_step_safe
    out = tmp_path / "box.step"
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("box")
        gmsh.model.occ.addBox(0, 0, 0, 0.25, 1.5, 0.03)
        gmsh.model.occ.synchronize()
        gmsh.write(str(out))
    finally:
        gmsh.finalize()
    nodes, quads = load_and_mesh_step_safe(out, timeout_s=120.0)
    assert len(nodes) > 20 and len(quads) > 8
    assert nodes.shape[1] == 3 and quads.shape[1] == 4
