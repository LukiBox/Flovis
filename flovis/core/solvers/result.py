"""Wspolny format wynikow analizy aerodynamicznej."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np


@dataclass
class AnalysisResult:
    method: str                       # "VLM (AeroSandbox)", "AVL", "Panel 3D", "Analityczny"
    model_name: str
    alpha_deg: np.ndarray             # przebieg kata natarcia
    CL: np.ndarray
    CD: np.ndarray
    Cm: np.ndarray                    # moment wzgledem CG
    velocity: float = 15.0            # [m/s]
    reference_area: float = 0.0
    mac: float = 0.0

    # stateczność
    CL_alpha: float = 0.0             # [1/rad]
    Cm_alpha: float = 0.0             # [1/rad]
    neutral_point_x: float = 0.0      # [m]
    static_margin: float = 0.0        # ulamek MAC
    cg_x: float = 0.0

    # osiagi
    CL_max: float = 0.0
    LD_max: float = 0.0
    alpha_LD_max: float = 0.0
    extras: dict = field(default_factory=dict)

    def polar(self):
        return self.CD, self.CL

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("alpha_deg", "CL", "CD", "Cm"):
            d[k] = np.asarray(d[k]).round(5).tolist()
        # zostaw tylko skalarne extras (odrzuc tablice/pole Cp itp.)
        d["extras"] = {k: v for k, v in (self.extras or {}).items()
                       if isinstance(v, (int, float, str, bool))}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisResult":
        kw = {k: d[k] for k in d if k in cls.__dataclass_fields__ and k != "extras"}
        for k in ("alpha_deg", "CL", "CD", "Cm"):
            if k in kw:
                kw[k] = np.asarray(kw[k], float)
        return cls(**kw)

    def summary_text(self) -> str:
        return (
            f"Metoda: {self.method}\n"
            f"Model: {self.model_name}\n"
            f"V = {self.velocity:.1f} m/s, S = {self.reference_area:.4f} m^2, "
            f"MAC = {self.mac:.4f} m\n"
            f"CL_alpha = {self.CL_alpha:.3f} /rad ({np.deg2rad(1)*self.CL_alpha:.4f} /deg)\n"
            f"Cm_alpha = {self.Cm_alpha:.3f} /rad\n"
            f"Punkt neutralny x = {self.neutral_point_x:.4f} m\n"
            f"CG x = {self.cg_x:.4f} m\n"
            f"Zapas statecznosci = {self.static_margin*100:.1f}% MAC\n"
            f"CL_max ~ {self.CL_max:.3f}\n"
            f"(L/D)_max ~ {self.LD_max:.1f} przy alpha = {self.alpha_LD_max:.1f} deg"
        )
