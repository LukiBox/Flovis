"""
Solver dla szablonow - metoda siatki wirowej (VLM) z realnymi profilami.

Domyslnie uzywa AeroSandbox (VLM). Geometria budowana jest z rzeczywistych
profili zapisanych w Surface.airfoil_root/airfoil_tip (notacja NACA lub plik
.dat). Opcjonalne sprzezenie VLM<->XFoil (strip theory) dodaje realistyczny
opor profilowy i ogranicza CL przez 2D Cl_max profilu, dzieki czemu biegun 3D
jest miarodajny.

Gdy AeroSandbox nie jest dostepny - wbudowany estymator analityczny (teoria
linii nosnej + objetosc usterzenia). Oba zwracaja AnalysisResult.
"""
from __future__ import annotations

import numpy as np

from ..airfoil import Airfoil
from ..geometry.templates import AircraftModel, Surface
from .result import AnalysisResult

# lepkosc kinematyczna powietrza ~15 C [m^2/s]
_NU_AIR = 1.5e-5


def _common_postprocess(res: AnalysisResult) -> AnalysisResult:
    a = res.alpha_deg
    mask = np.abs(a) <= 6
    if mask.sum() >= 2:
        res.CL_alpha = float(np.polyfit(np.deg2rad(a[mask]), res.CL[mask], 1)[0])
        res.Cm_alpha = float(np.polyfit(np.deg2rad(a[mask]), res.Cm[mask], 1)[0])
    if res.CL_alpha != 0:
        res.neutral_point_x = res.cg_x - (res.Cm_alpha / res.CL_alpha) * res.mac
        res.static_margin = (res.neutral_point_x - res.cg_x) / res.mac
    res.CL_max = float(np.max(res.CL))
    with np.errstate(divide="ignore", invalid="ignore"):
        ld = np.where(res.CD > 1e-6, res.CL / res.CD, 0.0)
    i = int(np.argmax(ld))
    res.LD_max = float(ld[i])
    res.alpha_LD_max = float(a[i])
    return res


# ---------------------------------------------------------------------------
# AeroSandbox VLM
# ---------------------------------------------------------------------------

def _asb_airfoil(spec: str):
    """Zamienia opis profilu (NACA/.dat) na aerosandbox.Airfoil z wspolrzednych."""
    import aerosandbox as asb
    af = Airfoil.from_spec(spec, n_points=120)
    coords = np.column_stack([af.x, af.y])
    return asb.Airfoil(name=af.name, coordinates=coords)


def _build_airplane(model: AircraftModel):
    import aerosandbox as asb
    wings = []
    for s in model.surfaces:
        if s.is_vertical:
            continue
        root_af = _asb_airfoil(s.airfoil_root)
        tip_af = _asb_airfoil(s.airfoil_tip or s.airfoil_root)
        xsecs = [
            asb.WingXSec(xyz_le=[s.x_le, 0, s.z_pos], chord=s.root_chord,
                         twist=s.incidence_deg, airfoil=root_af),
            asb.WingXSec(
                xyz_le=[s.x_le + 0.5 * s.span * np.tan(np.deg2rad(s.sweep_deg)),
                        0.5 * s.span,
                        s.z_pos + 0.5 * s.span * np.tan(np.deg2rad(s.dihedral_deg))],
                chord=s.tip_chord, twist=s.incidence_deg, airfoil=tip_af),
        ]
        wings.append(asb.Wing(name=s.name, symmetric=True, xsecs=xsecs))
    return asb.Airplane(name=model.name, xyz_ref=[model.cg_x, 0, 0], wings=wings)


def _profile_drag_model(model: AircraftModel, velocity: float):
    """
    Buduje funkcje Cd_profilowy(CL) i 2D Cl_max z biegunow profilu nasady
    skrzydla (XFoil lub NeuralFoil) przy liczbie Reynoldsa lotu.

    Zwraca (cd_of_cl, cl_max_2d, info) albo (None, None, info) gdy brak danych.
    """
    from ..airfoil import polar2d
    wing = model.wing
    if wing is None:
        return None, None, "brak skrzydla"
    re = velocity * wing.mac / _NU_AIR
    try:
        af = Airfoil.from_spec(wing.airfoil_root, n_points=160)
        pol = polar2d.analyze_polar(af, alphas=np.linspace(-6, 16, 23),
                                    reynolds=re, prefer="auto")
    except Exception as e:  # noqa: BLE001
        return None, None, f"bieguny 2D niedostepne ({e})"
    cl = np.asarray(pol.cl); cd = np.asarray(pol.cd)
    order = np.argsort(cl)
    cl_s, cd_s = cl[order], cd[order]

    def cd_of_cl(clq):
        return np.interp(np.clip(clq, cl_s.min(), cl_s.max()), cl_s, cd_s)

    return cd_of_cl, pol.cl_max, f"{pol.method}, Re={re:.0f}"


def _stability_derivatives(airplane, velocity, alpha_ref=2.0):
    """Liczy pochodne po predkosci katowej q (CL_q, Cm_q) metoda roznicowa.

    Zwraca slownik (moze byc pusty, gdy AeroSandbox nie wspiera danego pola).
    """
    import aerosandbox as asb
    out = {}
    try:
        mac = airplane.wings[0].mean_aerodynamic_chord()
        qhat = 0.02                      # bezwymiarowa predkosc pochylania
        q = qhat * 2 * velocity / mac
        base = asb.VortexLatticeMethod(
            airplane=airplane,
            op_point=asb.OperatingPoint(velocity=velocity, alpha=alpha_ref)).run()
        rot = asb.VortexLatticeMethod(
            airplane=airplane,
            op_point=asb.OperatingPoint(velocity=velocity, alpha=alpha_ref, q=q)
        ).run()
        out["CL_q"] = float((rot["CL"] - base["CL"]) / qhat)
        out["Cm_q"] = float((rot["Cm"] - base["Cm"]) / qhat)
    except Exception:  # noqa: BLE001
        pass
    return out


def solve_aerosandbox(model: AircraftModel, velocity: float = 15.0,
                      alphas=np.linspace(-4, 12, 9),
                      viscous: bool = True) -> AnalysisResult:
    import aerosandbox as asb

    airplane = _build_airplane(model)
    alphas = np.asarray(alphas, float)
    # liczymy kat po kacie (stabilne przy numpy 2.x / aerosandbox)
    CL_l, CD_l, Cm_l = [], [], []
    for a in alphas:
        op = asb.OperatingPoint(velocity=velocity, alpha=float(a))
        aero = asb.VortexLatticeMethod(airplane=airplane, op_point=op).run()
        CL_l.append(float(aero["CL"]))
        CD_l.append(float(aero["CD"]))
        Cm_l.append(float(aero["Cm"]))
    CL = np.array(CL_l)
    CD_ind = np.array(CD_l)        # opor indukowany z VLM
    Cm = np.array(Cm_l)

    extras = {}
    note = "VLM (opor indukowany)"
    cl_max_2d = None
    if viscous:
        cd_of_cl, cl_max_2d, info = _profile_drag_model(model, velocity)
        if cd_of_cl is not None:
            CD = CD_ind + cd_of_cl(CL) + 0.006     # + drobny opor kadluba/szczegolow
            note = f"VLM + opor profilowy 2D ({info})"
            extras["coupling"] = info
        else:
            CD = CD_ind + 0.012
            note = f"VLM (ryczaltowy opor pasozytniczy; {info})"
    else:
        CD = CD_ind + 0.012

    # ograniczenie CL przez 2D Cl_max (3D max ~0.9 * 2D)
    if cl_max_2d:
        cl_max_3d = 0.9 * cl_max_2d
        CL = np.minimum(CL, cl_max_3d)
        extras["CL_max_2D"] = round(float(cl_max_2d), 3)

    res = AnalysisResult(
        method="VLM (AeroSandbox)", model_name=model.name,
        alpha_deg=np.asarray(alphas, float), CL=CL, CD=CD, Cm=Cm,
        velocity=velocity, reference_area=model.reference_area,
        mac=model.wing.mac if model.wing else 0.0, cg_x=model.cg_x,
        extras=extras,
    )
    res = _common_postprocess(res)
    res.extras["note"] = note
    res.extras.update(_stability_derivatives(airplane, velocity))
    return res


# ---------------------------------------------------------------------------
# Estymator analityczny (fallback)
# ---------------------------------------------------------------------------

def solve_analytic(model: AircraftModel, velocity: float = 15.0,
                   alphas=np.linspace(-4, 12, 9)) -> AnalysisResult:
    wing = model.wing
    AR = wing.span**2 / wing.area if wing.area else 6.0
    e = 0.85
    a0 = 2 * np.pi
    a_wing = a0 / (1 + a0 / (np.pi * e * AR))
    alpha0 = -2.0

    a = np.asarray(alphas, float)
    CL = a_wing * np.deg2rad(a - alpha0)

    Cd0 = 0.022
    CD = Cd0 + CL**2 / (np.pi * e * AR)

    htail = next((s for s in model.surfaces if "poziome" in s.name.lower()), None)
    if htail:
        lt = htail.x_le - model.cg_x
        Vh = (htail.area * lt) / (wing.area * wing.mac)
    else:
        Vh = 0.5
    a_tail = a0 / (1 + a0 / (np.pi * e * max(htail.span**2 / htail.area, 3))) if htail else 4.0
    Cm_alpha = -Vh * a_tail * 0.9
    Cm0 = 0.05
    Cm = Cm0 + Cm_alpha * np.deg2rad(a)

    CL = np.clip(CL, None, 1.35)

    res = AnalysisResult(
        method="Analityczny (linia nosna)", model_name=model.name,
        alpha_deg=a, CL=CL, CD=CD, Cm=Cm,
        velocity=velocity, reference_area=wing.area,
        mac=wing.mac, cg_x=model.cg_x,
        extras={"AR": round(AR, 2), "e": e, "Vh": round(Vh, 3)},
    )
    return _common_postprocess(res)


def analyze(model: AircraftModel, velocity: float = 15.0,
            alphas=np.linspace(-4, 12, 9), prefer="auto") -> AnalysisResult:
    """Wybiera solver. prefer: 'auto' | 'aerosandbox' | 'analytic' | 'avl'."""
    if prefer == "avl":
        from .avl import solve_avl
        return solve_avl(model, velocity, alphas)
    if prefer in ("auto", "aerosandbox"):
        try:
            return solve_aerosandbox(model, velocity, alphas)
        except Exception as e:  # noqa: BLE001
            if prefer == "aerosandbox":
                raise
            print(f"[vlm] AeroSandbox niedostepny ({e}); estymator analityczny.")
    return solve_analytic(model, velocity, alphas)
