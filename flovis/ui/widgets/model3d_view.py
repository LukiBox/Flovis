"""
3D model view (PyVista / pyvistaqt), light theme.

Renders the AircraftModel as solids (wings/tails as thick surfaces, fuselage
as an ellipsoid). After an analysis it overlays a smooth pressure (Cp) field:
blue = suction (low pressure) to red = stagnation (high pressure). Shows the
CG and the neutral point.

Pressure fields:
  * templates - the panel method is solved on the STABLE rectangular
    equivalent of each surface (the calibrated regime) and the field is
    painted onto the displayed swept/tapered mesh, which shares the same
    structured grid topology. Solving directly on swept meshes is unstable.
  * STEP results - the field mapped onto the CAD geometry by the solver
    (extras: cp / cp_nodes / cp_faces) is rendered as a colored surface.
"""
from __future__ import annotations

import numpy as np

from ...core.geometry.templates import AircraftModel, Surface
from ...core.solvers import panel_method as pm

# light 3D theme (consistent with the rest of the UI)
_BG = "#f8f9fa"
_SURF = "#c9d4e3"
_EDGE = "#94a3b8"
_CMAP = "coolwarm"        # blue (low Cp) -> red (high Cp)
_CLIM = (-2.0, 1.0)


def _transform_points(pts: np.ndarray, s: Surface) -> np.ndarray:
    """Place surface-local coordinates in the model frame (dihedral, LE, vertical)."""
    pts = pts.copy()
    pts[:, 2] += np.abs(pts[:, 1]) * np.tan(np.deg2rad(s.dihedral_deg))
    if s.is_vertical:
        y = pts[:, 1].copy()
        z = pts[:, 2].copy()
        pts[:, 1] = z
        pts[:, 2] = np.abs(y)
    pts[:, 0] += s.x_le
    pts[:, 2] += s.z_pos
    return pts


def _faces_array(panels: np.ndarray) -> np.ndarray:
    return np.hstack([[len(q), *q] for q in panels])


def _naca_of(s: Surface, tip: bool = False) -> str:
    src = (s.airfoil_tip if tip else s.airfoil_root) or s.airfoil_root
    return (src or "0012").replace("NACA", "").strip() or "0012"


def _wing_mesh(s: Surface, n_chord: int = 24, n_span: int = 14):
    """Display mesh of a surface: real sweep, taper and airfoils."""
    try:
        return pm.make_wing_mesh(span=s.span, chord=s.root_chord,
                                 tip_chord=s.tip_chord, sweep_deg=s.sweep_deg,
                                 n_chord=n_chord, n_span=n_span,
                                 naca=_naca_of(s), naca_tip=_naca_of(s, tip=True))
    except Exception:  # noqa: BLE001
        return pm.make_wing_mesh(span=s.span, chord=s.root_chord,
                                 tip_chord=s.tip_chord, n_chord=n_chord,
                                 n_span=n_span)


def _surface_polydata(s: Surface, n_chord: int = 24, n_span: int = 14):
    """pv.PolyData of a thick surface (no Cp)."""
    import pyvista as pv
    mesh = _wing_mesh(s, n_chord, n_span)
    pts = _transform_points(mesh.nodes, s)
    return pv.PolyData(pts, _faces_array(mesh.panels)), mesh


def _pressure_polydata(s: Surface, alpha_deg: float, velocity: float):
    """
    pv.PolyData of a surface with a smooth, symmetric Cp field.

    The solve runs on the rectangular unswept equivalent (span, mean chord) -
    the regime where the low-order solver is validated - and the field is
    assigned to the displayed swept/tapered mesh, which has the identical
    structured panel ordering.
    """
    import pyvista as pv
    n_chord, n_span = 20, 12
    display = _wing_mesh(s, n_chord=n_chord, n_span=n_span)

    mean_chord = max(0.5 * (s.root_chord + s.tip_chord), 1e-6)
    try:
        solve_mesh = pm.make_wing_mesh(span=s.span, chord=mean_chord,
                                       n_chord=n_chord, n_span=n_span,
                                       naca=_naca_of(s))
    except Exception:  # noqa: BLE001
        solve_mesh = pm.make_wing_mesh(span=s.span, chord=mean_chord,
                                       n_chord=n_chord, n_span=n_span)
    a = np.deg2rad(alpha_deg)
    vinf = velocity * np.array([np.cos(a), 0.0, np.sin(a)])
    sol = pm.solve_panel(solve_mesh, vinf)
    cp = pm.symmetrize_cp(solve_mesh, pm.cp_clipped(sol["cp"], -2.5))

    pts = _transform_points(display.nodes, s)
    poly = pv.PolyData(pts, _faces_array(display.panels))
    poly.cell_data["Cp"] = cp          # identical grid ordering in both meshes
    return poly.cell_data_to_point_data()      # smooth gradient


class Model3DView:
    """Thin layer over QtInteractor; created lazily (PyVista is heavy)."""

    def __init__(self, parent=None, off_screen=False):
        from pyvistaqt import QtInteractor
        self.plotter = QtInteractor(parent, off_screen=off_screen)
        self.plotter.set_background(_BG)
        self.widget = self.plotter
        self.model: AircraftModel | None = None
        self._result = None
        self._pressure = False
        self._layers = {"skrzydla": True, "kadlub": True, "markery": True}

    def set_model(self, model: AircraftModel):
        self.model = model
        self._result = None
        self._pressure = False
        self.render()

    def set_layer(self, name: str, on: bool):
        self._layers[name] = on
        self.render()

    def show_result(self, result):
        self._result = result
        self._pressure = True
        self.render()

    def show_step(self, result):
        """Render STEP geometry with its Cp field (no AircraftModel)."""
        self.model = None
        self._result = result
        self._pressure = True
        self.render()

    def _is_step_result(self, result) -> bool:
        ex = getattr(result, "extras", {}) or {}
        return ex.get("cp_nodes") is not None and ex.get("cp_faces") is not None

    # ------------------------------------------------------------------ render
    def render(self):
        import pyvista as pv
        result = self._result
        pressure = self._pressure
        p = self.plotter
        p.clear()
        p.set_background(_BG)

        # STEP mode: no AircraftModel, draw the CAD geometry + Cp
        if self.model is None and result is not None and self._is_step_result(result):
            self._render_step(result)
            return
        if self.model is None:
            p.add_text("No model", position="upper_left", color="#334155",
                       font_size=12)
            return
        m = self.model

        if self._layers.get("skrzydla", True):
            alpha = self._pressure_alpha(result)
            for s in m.surfaces:
                colored = False
                if pressure and result is not None and not s.is_vertical:
                    try:
                        poly = _pressure_polydata(
                            s, alpha, getattr(result, "velocity", 15.0))
                        p.add_mesh(poly, scalars="Cp", cmap=_CMAP, clim=_CLIM,
                                   smooth_shading=True, show_edges=False,
                                   name=f"surf_{s.name}",
                                   scalar_bar_args={"title": "Cp",
                                                    "color": "#1f2937",
                                                    "n_labels": 5})
                        colored = True
                    except Exception:  # noqa: BLE001
                        colored = False
                if not colored:
                    poly, _ = _surface_polydata(s)
                    p.add_mesh(poly, color=_SURF, show_edges=True,
                               edge_color=_EDGE, line_width=0.4,
                               smooth_shading=True, name=f"surf_{s.name}")

        if self._layers.get("kadlub", True) and m.fuselage_length > 0:
            ell = pv.ParametricEllipsoid(
                m.fuselage_length / 2, m.fuselage_diam / 2, m.fuselage_diam / 2)
            ell.translate((m.fuselage_length / 2, 0, 0), inplace=True)
            p.add_mesh(ell, color="#e2e8f0", opacity=0.5, name="fuselage",
                       smooth_shading=True)

        if self._layers.get("markery", True):
            self._add_markers(result)

        p.add_axes(color="#334155")
        try:
            p.reset_camera()
            p.view_isometric()
        except Exception:  # noqa: BLE001
            pass

    def _pressure_alpha(self, result) -> float:
        if result is None:
            return 4.0
        a = getattr(result, "alpha_LD_max", 0.0)
        if not np.isfinite(a) or a <= 0:
            a = 4.0
        return float(np.clip(a, 2.0, 8.0))

    def _add_markers(self, result):
        import pyvista as pv
        m = self.model
        cg = pv.Sphere(radius=max(m.fuselage_diam * 0.22, 0.01),
                       center=(m.cg_x, 0, 0))
        self.plotter.add_mesh(cg, color="#dc2626", name="cg")
        self.plotter.add_point_labels(
            [[m.cg_x, 0, m.fuselage_diam]], ["CG"], font_size=12,
            text_color="#dc2626", shape=None, name="cg_lbl")
        if result is not None and getattr(result, "neutral_point_x", 0):
            npx = result.neutral_point_x
            npm = pv.Sphere(radius=max(m.fuselage_diam * 0.18, 0.008),
                            center=(npx, 0, 0))
            self.plotter.add_mesh(npm, color="#059669", name="np")
            self.plotter.add_point_labels(
                [[npx, 0, -m.fuselage_diam]], ["Neutral point"], font_size=11,
                text_color="#059669", shape=None, name="np_lbl")

    def _add_step_pressure(self, result):
        """Render the Cp field computed on the STEP geometry as a surface."""
        import pyvista as pv
        ex = getattr(result, "extras", {}) or {}
        cp = ex.get("cp")
        nodes = ex.get("cp_nodes")
        faces = ex.get("cp_faces")
        if cp is None or nodes is None or faces is None:
            return
        poly = pv.PolyData(np.asarray(nodes), _faces_array(np.asarray(faces)))
        poly.cell_data["Cp"] = np.asarray(cp)
        poly = poly.cell_data_to_point_data()
        self.plotter.add_mesh(poly, scalars="Cp", cmap=_CMAP, clim=_CLIM,
                              smooth_shading=True, show_edges=False,
                              name="cp_field",
                              scalar_bar_args={"title": "Cp", "color": "#1f2937"})

    def _render_step(self, result):
        """Render the STEP body (colored by Cp) + CG / neutral-point markers."""
        import pyvista as pv
        ex = getattr(result, "extras", {}) or {}
        nodes = np.asarray(ex["cp_nodes"])
        self._add_step_pressure(result)
        span = nodes.max(0) - nodes.min(0)
        r = max(float(np.linalg.norm(span)) * 0.02, 1e-4)
        zc = float(nodes[:, 2].mean())
        cg = getattr(result, "cg_x", None)
        if self._layers.get("markery", True) and cg is not None:
            self.plotter.add_mesh(pv.Sphere(radius=r, center=(cg, 0, zc)),
                                  color="#dc2626", name="cg")
            npx = getattr(result, "neutral_point_x", 0.0)
            if npx:
                self.plotter.add_mesh(
                    pv.Sphere(radius=r * 0.85, center=(npx, 0, zc)),
                    color="#059669", name="np")
        self.plotter.add_axes(color="#334155")
        try:
            self.plotter.reset_camera()
            self.plotter.view_isometric()
        except Exception:  # noqa: BLE001
            pass

    def screenshot(self, path: str):
        self.plotter.screenshot(path)

    def close(self):
        try:
            self.plotter.close()
        except Exception:  # noqa: BLE001
            pass
