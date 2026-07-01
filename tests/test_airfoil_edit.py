"""Testy operacji edytorskich profilu: repanelizacja, walidacja, wstaw/usun."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flovis.core.airfoil import Airfoil  # noqa: E402


def test_repanel_changes_count_keeps_shape():
    af = Airfoil.from_naca("2412", n_points=120)
    r = af.repanel(180)
    assert abs(len(r.x) - 181) <= 2
    t0, _ = af.max_thickness()
    t1, _ = r.max_thickness()
    assert abs(t0 - t1) < 0.01      # ksztalt zachowany


def test_validate_good_airfoil():
    af = Airfoil.from_naca("2412")
    assert af.is_valid()
    assert af.validate() == []


def test_validate_detects_self_intersection():
    af = Airfoil.from_naca("0012", n_points=120)
    # wepchnij gorny punkt mocno w dol -> samoprzeciecie
    i = int(np.argmax(af.y))
    bad = af.set_point(i, af.x[i], -0.3)
    assert not bad.is_valid()


def test_insert_delete_point():
    af = Airfoil.from_naca("2412", n_points=100)
    n = len(af.x)
    ins = af.insert_point(10)
    assert len(ins.x) == n + 1
    dele = ins.delete_point(10)
    assert len(dele.x) == n


def test_from_spec_naca_and_modified():
    a1 = Airfoil.from_spec("NACA 2412")
    a2 = Airfoil.from_spec("0011-0.825-35")
    assert a1.x.size > 10 and a2.x.size > 10
