"""
Flovis project format (.flovis) - a zip of JSON/dat files.

Contains: the model (geometry), the current airfoil (.dat), analysis
settings and the last result. Restores the whole working state.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np

from .geometry.templates import AircraftModel
from .solvers.result import AnalysisResult
from .airfoil import Airfoil

FORMAT_VERSION = 1


def save_project(path: str | Path, model: AircraftModel | None = None,
                 airfoil: Airfoil | None = None, result: AnalysisResult | None = None,
                 settings: dict | None = None) -> Path:
    """Save the working state to a .flovis (zip) file."""
    path = Path(path)
    if path.suffix != ".flovis":
        path = path.with_suffix(".flovis")

    manifest = {"format": "flovis", "version": FORMAT_VERSION,
                "settings": settings or {}}

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        if model is not None:
            z.writestr("model.json", json.dumps(model.to_dict(),
                                                ensure_ascii=False, indent=2))
            manifest["has_model"] = True
        if airfoil is not None:
            dat = f"{airfoil.name}\n" + "\n".join(
                f"{x:10.6f} {y:10.6f}" for x, y in zip(airfoil.x, airfoil.y))
            z.writestr("airfoil.dat", dat)
            manifest["has_airfoil"] = True
        if result is not None:
            z.writestr("result.json", json.dumps(result.to_dict(),
                                                 ensure_ascii=False, indent=2))
            manifest["has_result"] = True
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False,
                                               indent=2))
    return path


def load_project(path: str | Path) -> dict:
    """
    Load a .flovis project. Returns a dict:
    {model, airfoil, result, settings}. Missing pieces = None.
    """
    path = Path(path)
    out = {"model": None, "airfoil": None, "result": None, "settings": {}}
    with zipfile.ZipFile(path, "r") as z:
        names = set(z.namelist())
        if "manifest.json" in names:
            out["settings"] = json.loads(z.read("manifest.json")).get("settings", {})
        if "model.json" in names:
            out["model"] = AircraftModel.from_dict(json.loads(z.read("model.json")))
        if "airfoil.dat" in names:
            lines = z.read("airfoil.dat").decode("utf-8").splitlines()
            name = lines[0].strip() if lines else "profil"
            coords = []
            for ln in lines[1:]:
                parts = ln.split()
                if len(parts) >= 2:
                    try:
                        coords.append((float(parts[0]), float(parts[1])))
                    except ValueError:
                        pass
            if coords:
                arr = np.array(coords)
                out["airfoil"] = Airfoil(x=arr[:, 0], y=arr[:, 1], name=name)
        if "result.json" in names:
            out["result"] = AnalysisResult.from_dict(json.loads(z.read("result.json")))
    return out
