"""
2D airfoil analysis - polars (Cl, Cd, Cm) and the Cp distribution.

Two methods, one result type (Polar2DResult):
  * XFoil (subprocess)  - the accurate viscous/inviscid solver,
  * NeuralFoil          - a fast neural predictor (fallback).

analyze_polar(..., prefer="auto") tries XFoil first and falls back to
NeuralFoil when the binary is missing or the run fails. The method used
is clearly marked in the result's .method field.
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .. import binaries
from .airfoil import Airfoil


@dataclass
class Polar2DResult:
    method: str                       # "XFoil" | "NeuralFoil"
    reynolds: float
    ncrit: float
    mach: float
    alpha: np.ndarray                 # converged angles [deg]
    cl: np.ndarray
    cd: np.ndarray
    cm: np.ndarray
    # pressure distribution for a chosen angle (optional)
    cp_x: np.ndarray | None = None
    cp: np.ndarray | None = None
    cp_alpha: float = 0.0
    # derived parameters
    cl_max: float = 0.0
    alpha_stall: float = 0.0
    ld_max: float = 0.0
    alpha_ld_max: float = 0.0
    note: str = ""
    extras: dict = field(default_factory=dict)

    def __post_init__(self):
        for k in ("alpha", "cl", "cd", "cm"):
            setattr(self, k, np.asarray(getattr(self, k), float))
        self._postprocess()

    def _postprocess(self):
        if self.cl.size:
            i = int(np.argmax(self.cl))
            self.cl_max = float(self.cl[i])
            self.alpha_stall = float(self.alpha[i])
            with np.errstate(divide="ignore", invalid="ignore"):
                ld = np.where(self.cd > 1e-6, self.cl / self.cd, 0.0)
            j = int(np.argmax(ld))
            self.ld_max = float(ld[j])
            self.alpha_ld_max = float(self.alpha[j])

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "reynolds": self.reynolds,
            "ncrit": self.ncrit,
            "mach": self.mach,
            "alpha": np.round(self.alpha, 3).tolist(),
            "cl": np.round(self.cl, 4).tolist(),
            "cd": np.round(self.cd, 5).tolist(),
            "cm": np.round(self.cm, 4).tolist(),
            "cl_max": round(self.cl_max, 3),
            "alpha_stall": round(self.alpha_stall, 2),
            "ld_max": round(self.ld_max, 1),
            "alpha_ld_max": round(self.alpha_ld_max, 2),
        }


# ----------------------------------------------------------------------------
# XFoil
# ----------------------------------------------------------------------------

def xfoil_available() -> bool:
    return binaries.xfoil_path() is not None


def _parse_polar_file(text: str) -> tuple[np.ndarray, ...]:
    """Parse an XFoil polar file (PACC). Returns (alpha, cl, cd, cm)."""
    a, cl, cd, cm = [], [], [], []
    for ln in text.splitlines():
        parts = ln.split()
        if len(parts) < 5:
            continue
        try:
            vals = [float(p) for p in parts[:5]]
        except ValueError:
            continue
        # kolumny: alpha CL CD CDp CM
        a.append(vals[0]); cl.append(vals[1]); cd.append(vals[2]); cm.append(vals[4])
    order = np.argsort(a)
    return (np.array(a)[order], np.array(cl)[order],
            np.array(cd)[order], np.array(cm)[order])


def _parse_cp_file(text: str) -> tuple[np.ndarray, np.ndarray]:
    """Parse a Cp file (CPWR): columns x, Cp (sometimes x, y, Cp)."""
    xs, cps = [], []
    for ln in text.splitlines():
        parts = ln.split()
        if len(parts) < 2:
            continue
        try:
            vals = [float(p) for p in parts]
        except ValueError:
            continue
        xs.append(vals[0])
        cps.append(vals[-1])     # ostatnia kolumna to Cp
    return np.array(xs), np.array(cps)


def analyze_xfoil(airfoil: Airfoil, alphas=np.linspace(-4, 14, 19),
                  reynolds: float = 3e5, ncrit: float = 9.0,
                  mach: float = 0.0, n_panels: int = 200,
                  iter_limit: int = 200, cp_alpha: float | None = None,
                  timeout: float = 90.0) -> Polar2DResult:
    """Run airfoil polars in XFoil. Raises RuntimeError when unavailable."""
    exe = binaries.xfoil_path()
    if exe is None:
        raise RuntimeError("The XFoil binary is not available.")

    alphas = np.asarray(alphas, float)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        dat = td / "airfoil.dat"
        polar = td / "polar.txt"
        airfoil.to_dat(dat)

        cmds = ["PLOP", "G F", ""]                  # disable graphics
        cmds += [f"LOAD {dat.name}", "PANE"]
        cmds += ["OPER", f"VISC {reynolds:.0f}"]
        if mach > 0:
            cmds.append(f"MACH {mach:.3f}")
        cmds += ["VPAR", f"N {ncrit:.2f}", ""]
        cmds += [f"ITER {iter_limit}"]
        cmds += ["PACC", polar.name, ""]            # polar accumulation

        # sweep from 0 up and from 0 down (better convergence near stall)
        pos = sorted(a for a in alphas if a >= 0)
        neg = sorted((a for a in alphas if a < 0), reverse=True)
        for a in pos:
            cmds.append(f"ALFA {a:.3f}")
        if neg:
            cmds.append("INIT")
            for a in neg:
                cmds.append(f"ALFA {a:.3f}")
        cmds += ["PACC"]                              # close accumulation (stay in OPER)

        # Cp distribution for the chosen angle (still in the OPER menu)
        cp_target = cp_alpha if cp_alpha is not None else _mid_alpha(alphas)
        cpfile = td / "cp.txt"
        cmds += [f"ALFA {cp_target:.3f}", f"CPWR {cpfile.name}"]
        cmds += ["", "QUIT", ""]                       # leave OPER, quit XFoil

        script = "\n".join(cmds) + "\n"
        try:
            subprocess.run([exe], input=script, cwd=td, text=True,
                           capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"XFoil exceeded the time limit ({timeout}s).") from e

        if not polar.exists():
            raise RuntimeError("XFoil produced no polar file "
                               "(no convergence or bad geometry).")
        a, cl, cd, cm = _parse_polar_file(polar.read_text())
        if a.size == 0:
            raise RuntimeError("XFoil did not converge for any angle of attack.")

        cp_x = cp_arr = None
        if cpfile.exists():
            cp_x, cp_arr = _parse_cp_file(cpfile.read_text())

    res = Polar2DResult(
        method="XFoil", reynolds=reynolds, ncrit=ncrit, mach=mach,
        alpha=a, cl=cl, cd=cd, cm=cm,
        cp_x=cp_x, cp=cp_arr, cp_alpha=float(cp_target),
        note=f"Converged {a.size}/{alphas.size} angles.",
    )
    return res


def _mid_alpha(alphas: np.ndarray) -> float:
    """An angle near the middle of the range (for the Cp plot)."""
    a = np.asarray(alphas, float)
    return float(a[np.argmin(np.abs(a - np.median(a)))])


# ----------------------------------------------------------------------------
# NeuralFoil
# ----------------------------------------------------------------------------

def neuralfoil_available() -> bool:
    try:
        import neuralfoil  # noqa: F401
        return True
    except Exception:
        return False


def analyze_neuralfoil(airfoil: Airfoil, alphas=np.linspace(-4, 14, 19),
                       reynolds: float = 3e5, ncrit: float = 9.0,
                       mach: float = 0.0,
                       model_size: str = "large") -> Polar2DResult:
    """Fast airfoil polar prediction (NeuralFoil)."""
    import neuralfoil as nf

    alphas = np.asarray(alphas, float)
    coords = np.column_stack([airfoil.x, airfoil.y])
    aero = nf.get_aero_from_coordinates(
        coordinates=coords, alpha=alphas, Re=reynolds,
        model_size=model_size,
    )
    cl = np.asarray(aero["CL"], float)
    cd = np.asarray(aero["CD"], float)
    cm = np.asarray(aero["CM"], float)
    conf = float(np.mean(aero.get("analysis_confidence", 1.0)))

    res = Polar2DResult(
        method="NeuralFoil", reynolds=reynolds, ncrit=ncrit, mach=mach,
        alpha=alphas, cl=cl, cd=cd, cm=cm,
        note=f"Neural prediction (confidence ~{conf:.2f}). "
             "Use XFoil for authoritative results.",
        extras={"confidence": round(conf, 3)},
    )
    return res


# ----------------------------------------------------------------------------
# Dyspozytor
# ----------------------------------------------------------------------------

def analyze_polar(airfoil: Airfoil, alphas=np.linspace(-4, 14, 19),
                  reynolds: float = 3e5, ncrit: float = 9.0, mach: float = 0.0,
                  prefer: str = "auto", cp_alpha: float | None = None
                  ) -> Polar2DResult:
    """
    Run airfoil polars. prefer: 'auto' | 'xfoil' | 'neuralfoil'.

    'auto' = XFoil when available, NeuralFoil on any failure.
    """
    if prefer in ("auto", "xfoil") and xfoil_available():
        try:
            return analyze_xfoil(airfoil, alphas, reynolds, ncrit, mach,
                                 cp_alpha=cp_alpha)
        except Exception as e:  # noqa: BLE001
            if prefer == "xfoil":
                raise
            print(f"[polar2d] XFoil failed ({e}); trying NeuralFoil.")
    if prefer == "xfoil":
        raise RuntimeError("XFoil is unavailable but method 'xfoil' was forced.")
    if neuralfoil_available():
        return analyze_neuralfoil(airfoil, alphas, reynolds, ncrit, mach)
    raise RuntimeError(
        "No 2D analysis method: neither XFoil nor NeuralFoil was found. "
        "Install NeuralFoil (pip install neuralfoil) or add the XFoil binary.")
