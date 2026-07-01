"""
Solver AVL (Athena Vortex Lattice) - "tryb dokladny" dla szablonow.

Generuje plik geometrii .avl z AircraftModel (z realnymi profilami przez AFILE),
uruchamia binarke AVL przez subprocess, po czym parsuje:
  * sily calkowite (FT) dla kazdego kata -> CL, CD, Cm,
  * pochodne statecznosci (ST) -> CLa, Cma oraz punkt neutralny Xnp.

AVL liczy opor indukowany; opor profilowy dodajemy z biegunow 2D profilu
(to samo sprzezenie co w VLM), aby biegun byl realistyczny.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .. import binaries
from ..airfoil import Airfoil
from ..geometry.templates import AircraftModel
from .result import AnalysisResult


def avl_available() -> bool:
    return binaries.avl_path() is not None


# ---------------------------------------------------------------- generacja .avl

def _write_airfoil_files(model: AircraftModel, out_dir: Path) -> dict[str, Path]:
    """Zapisuje unikalne profile jako .dat i zwraca mape spec->sciezka."""
    files: dict[str, Path] = {}
    idx = 0
    for s in model.surfaces:
        for spec in (s.airfoil_root, s.airfoil_tip):
            spec = spec or s.airfoil_root
            if spec in files:
                continue
            af = Airfoil.from_spec(spec, n_points=120)
            p = out_dir / f"af_{idx}.dat"
            af.to_dat(p)
            files[spec] = p
            idx += 1
    return files


def _section(xle, yle, zle, chord, ainc, afile: Path) -> str:
    return (f"SECTION\n"
            f"{xle:.5f} {yle:.5f} {zle:.5f} {chord:.5f} {ainc:.3f}  8 0\n"
            f"AFILE\n{afile.as_posix()}\n")


def write_avl(model: AircraftModel, path: Path) -> Path:
    """Buduje plik geometrii .avl. Profile zapisywane obok jako .dat (AFILE)."""
    path = Path(path)
    out_dir = path.parent
    af_files = _write_airfoil_files(model, out_dir)

    wing = model.wing
    sref = model.reference_area or (wing.area if wing else 1.0)
    cref = wing.mac if wing else 1.0
    bref = wing.span if wing else 1.0

    lines = [
        model.name,
        "0.0",                         # Mach
        "0 0 0.0",                     # iYsym iZsym Zsym
        f"{sref:.5f} {cref:.5f} {bref:.5f}",
        f"{model.cg_x:.5f} 0.0 0.0",   # Xref Yref Zref (= CG)
        "0.0",                         # domyslny CDp
        "#",
    ]

    for s in model.surfaces:
        root_af = af_files[s.airfoil_root]
        tip_af = af_files[s.airfoil_tip or s.airfoil_root]
        lines += ["SURFACE", s.name, "8 1.0 16 -2.0"]   # Nchord Cspace Nspan Sspace
        if not s.is_vertical:
            lines.append("YDUPLICATE")
            lines.append("0.0")
        lines.append("#")
        if s.is_vertical:
            # rozpietosc wzdluz Z
            dz = s.span
            dx = s.span * np.tan(np.deg2rad(s.sweep_deg))
            lines.append(_section(s.x_le, 0.0, s.z_pos, s.root_chord,
                                  s.incidence_deg, root_af).rstrip())
            lines.append(_section(s.x_le + dx, 0.0, s.z_pos + dz, s.tip_chord,
                                  s.incidence_deg, tip_af).rstrip())
        else:
            half = 0.5 * s.span
            dx = half * np.tan(np.deg2rad(s.sweep_deg))
            dz = half * np.tan(np.deg2rad(s.dihedral_deg))
            lines.append(_section(s.x_le, 0.0, s.z_pos, s.root_chord,
                                  s.incidence_deg, root_af).rstrip())
            lines.append(_section(s.x_le + dx, half, s.z_pos + dz, s.tip_chord,
                                  s.incidence_deg, tip_af).rstrip())
        lines.append("#")

    path.write_text("\n".join(lines) + "\n")
    return path


# ----------------------------------------------------------------- parsowanie

def _find_float(text: str, key: str) -> float | None:
    m = re.search(re.escape(key) + r"\s*=\s*(-?\d+\.?\d*(?:[eE][-+]?\d+)?)", text)
    return float(m.group(1)) if m else None


def _parse_ft(text: str):
    return (_find_float(text, "CLtot"), _find_float(text, "CDtot"),
            _find_float(text, "Cmtot"))


# --------------------------------------------------------------------- solver

def solve_avl(model: AircraftModel, velocity: float = 15.0,
              alphas=np.linspace(-4, 12, 9), viscous: bool = True,
              timeout: float = 120.0) -> AnalysisResult:
    exe = binaries.avl_path()
    if exe is None:
        raise RuntimeError("Binarka AVL niedostepna (resources/bin/avl lub PATH).")

    alphas = np.asarray(alphas, float)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        avl_file = td / "model.avl"
        write_avl(model, avl_file)

        cmds = ["OPER"]
        ft_files = []
        for i, a in enumerate(alphas):
            ft = td / f"ft_{i}.txt"
            ft_files.append(ft)
            cmds += [f"A A {a:.3f}", "X", "FT", ft.as_posix()]
        # pochodne statecznosci w punkcie odniesienia
        st = td / "st.txt"
        a_ref = float(alphas[np.argmin(np.abs(alphas - 2.0))])
        cmds += [f"A A {a_ref:.3f}", "X", "ST", st.as_posix()]
        cmds += ["", "QUIT", ""]

        script = "\n".join(cmds) + "\n"
        try:
            subprocess.run([exe, avl_file.as_posix()], input=script, cwd=td,
                           text=True, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"AVL przekroczyl limit czasu ({timeout}s).") from e

        CL, CD, Cm, good_a = [], [], [], []
        for a, ft in zip(alphas, ft_files):
            if not ft.exists():
                continue
            cl, cd, cm = _parse_ft(ft.read_text())
            if cl is None:
                continue
            CL.append(cl); CD.append(cd if cd is not None else 0.0)
            Cm.append(cm if cm is not None else 0.0); good_a.append(a)

        if not CL:
            raise RuntimeError("AVL nie zwrocil zadnych wynikow (sprawdz geometrie).")

        CL = np.array(CL); CD_ind = np.array(CD); Cm = np.array(Cm)
        good_a = np.array(good_a)

        CLa = Cma = Xnp = None
        if st.exists():
            stx = st.read_text()
            CLa = _find_float(stx, "CLa")
            Cma = _find_float(stx, "Cma")
            Xnp = _find_float(stx, "Xnp")

    # opor profilowy z biegunow 2D (sprzezenie jak w VLM)
    extras = {}
    note = "AVL (opor indukowany)"
    if viscous:
        from .vlm import _profile_drag_model
        cd_of_cl, cl_max_2d, info = _profile_drag_model(model, velocity)
        if cd_of_cl is not None:
            CD = CD_ind + cd_of_cl(CL) + 0.006
            note = f"AVL + opor profilowy 2D ({info})"
            extras["coupling"] = info
            if cl_max_2d:
                CL = np.minimum(CL, 0.9 * cl_max_2d)
                extras["CL_max_2D"] = round(float(cl_max_2d), 3)
        else:
            CD = CD_ind + 0.012
    else:
        CD = CD_ind + 0.012

    res = AnalysisResult(
        method="AVL", model_name=model.name, alpha_deg=good_a,
        CL=CL, CD=CD, Cm=Cm, velocity=velocity,
        reference_area=model.reference_area,
        mac=model.wing.mac if model.wing else 0.0, cg_x=model.cg_x,
        extras=extras,
    )

    # pochodne i punkt neutralny: preferuj wartosci wprost z AVL
    a = res.alpha_deg
    mask = np.abs(a) <= 6
    res.CL_alpha = float(CLa) if CLa is not None else (
        float(np.polyfit(np.deg2rad(a[mask]), CL[mask], 1)[0]) if mask.sum() >= 2 else 0.0)
    res.Cm_alpha = float(Cma) if Cma is not None else (
        float(np.polyfit(np.deg2rad(a[mask]), Cm[mask], 1)[0]) if mask.sum() >= 2 else 0.0)
    if Xnp is not None:
        res.neutral_point_x = float(Xnp)
        res.static_margin = (res.neutral_point_x - res.cg_x) / res.mac if res.mac else 0.0
    elif res.CL_alpha:
        res.neutral_point_x = res.cg_x - (res.Cm_alpha / res.CL_alpha) * res.mac
        res.static_margin = (res.neutral_point_x - res.cg_x) / res.mac
    res.CL_max = float(np.max(CL))
    with np.errstate(divide="ignore", invalid="ignore"):
        ld = np.where(CD > 1e-6, CL / CD, 0.0)
    i = int(np.argmax(ld))
    res.LD_max = float(ld[i]); res.alpha_LD_max = float(a[i])
    res.extras["note"] = note
    return res
