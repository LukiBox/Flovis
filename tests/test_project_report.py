"""Testy I/O projektu (.flovis) i generowania raportu PDF."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flovis.core.geometry import make_template, Layout  # noqa: E402
from flovis.core.solvers import solve_analytic  # noqa: E402
from flovis.core.airfoil import Airfoil  # noqa: E402
from flovis.core import project  # noqa: E402
from flovis.core.report import build_report  # noqa: E402


def test_project_roundtrip(tmp_path):
    m = make_template(Layout.CANARD)
    af = Airfoil.from_naca("4412")
    res = solve_analytic(m, velocity=15)
    p = project.save_project(tmp_path / "proj.flovis", model=m, airfoil=af,
                             result=res, settings={"velocity": 15})
    assert p.exists() and p.stat().st_size > 0
    data = project.load_project(p)
    assert data["model"].layout == Layout.CANARD
    assert len(data["model"].surfaces) == 3
    assert len(data["airfoil"].x) == len(af.x)
    assert data["result"].method == res.method
    assert data["settings"]["velocity"] == 15


def test_pdf_generation(tmp_path):
    m = make_template(Layout.LOW_WING)
    res = solve_analytic(m, velocity=15)
    af = Airfoil.from_naca("2412")
    out = tmp_path / "raport.pdf"
    build_report(res, out, model=m, airfoil=af,
                 ai_text="Model wydaje sie stateczny.")
    assert out.exists() and out.stat().st_size > 1000


def test_pdf_without_ai(tmp_path):
    """Raport musi powstac takze bez tekstu AI (sekcja opcjonalna)."""
    m = make_template(Layout.LOW_WING)
    res = solve_analytic(m, velocity=15)
    out = tmp_path / "raport_bez_ai.pdf"
    build_report(res, out, model=m)
    assert out.exists() and out.stat().st_size > 1000
