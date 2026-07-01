"""Testy silnika profili Flovis."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flovis.core.airfoil import Airfoil, parse_naca, generate  # noqa: E402


def test_standard_thickness():
    """NACA 2412 -> grubosc ~12% w okolicy 30% cieciwy."""
    af = Airfoil.from_naca("2412")
    t, xt = af.max_thickness()
    assert abs(t - 0.12) < 0.005, f"grubosc {t}"
    assert 0.25 < xt < 0.35, f"polozenie {xt}"


def test_standard_camber():
    af = Airfoil.from_naca("2412")
    c, xc = af.max_camber()
    assert abs(c - 0.02) < 0.004, f"camber {c}"
    assert 0.35 < xc < 0.45, f"polozenie camber {xc}"


def test_symmetric_zero_camber():
    af = Airfoil.from_naca("0012")
    c, _ = af.max_camber()
    assert abs(c) < 1e-3


def test_modified_thickness_position():
    """Zmodyfikowany 0011 z max grubosci przesunieta na 35%."""
    spec = parse_naca("0011-1.0-35")
    assert spec.modified
    af = Airfoil.from_naca("0011-1.0-35")
    t, xt = af.max_thickness()
    assert abs(t - 0.11) < 0.008, f"grubosc {t}"
    assert 0.30 < xt < 0.40, f"polozenie max grubosci {xt}"


def test_modified_le_radius_effect():
    """Wiekszy wspolczynnik LE -> grubszy nos (wieksza grubosc przy x=5%)."""
    sharp = Airfoil.from_naca("0012-0.5-30")
    blunt = Airfoil.from_naca("0012-1.5-30")
    (xu_s, yu_s), _ = sharp._split_surfaces()
    (xu_b, yu_b), _ = blunt._split_surfaces()
    y_s = np.interp(0.05, xu_s, yu_s)
    y_b = np.interp(0.05, xu_b, yu_b)
    assert y_b > y_s, f"nos: ostry={y_s} tepy={y_b}"


def test_dat_roundtrip(tmp_path):
    af = Airfoil.from_naca("4412")
    p = af.to_dat(tmp_path / "test.dat")
    af2 = Airfoil.from_dat(p)
    assert len(af2.x) == len(af.x)
    assert np.allclose(af.x, af2.x, atol=1e-5)
    assert np.allclose(af.y, af2.y, atol=1e-5)


def test_scale_thickness():
    af = Airfoil.from_naca("0012")
    thick = af.scale_thickness(1.5)
    t0, _ = af.max_thickness()
    t1, _ = thick.max_thickness()
    assert abs(t1 - 1.5 * t0) < 0.01


def test_closed_le_te_order():
    """Kontur zaczyna i konczy sie blisko TE (x~1)."""
    af = Airfoil.from_naca("2412")
    assert af.x[0] > 0.9 and af.x[-1] > 0.9
    assert af.x.min() < 0.01  # LE blisko 0


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    import tempfile
    passed = 0
    for fn in fns:
        try:
            if "tmp_path" in fn.__code__.co_varnames:
                fn(Path(tempfile.mkdtemp()))
            else:
                fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL  {fn.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{passed}/{len(fns)} testow zaliczonych")
