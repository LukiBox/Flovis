"""
Widok 3D modelu (PyVista / pyvistaqt) w jasnym motywie.

Renderuje AircraftModel jako bryly (skrzydla/usterzenia jako grube platy,
kadlub jako elipsoida). Po analizie naklada gladki rozklad cisnienia (Cp) na
powierzchni: kolory od niebieskiego (podcisnienie/ssanie) do czerwonego
(nadcisnienie/spietrzenie). Pokazuje srodek ciezkosci (CG) i punkt neutralny.

Dla szablonow Cp liczony jest metoda panelowa na powierzchni kazdego platu.
Dla wynikow STEP wykorzystywane jest pole Cp policzone na geometrii STEP.
"""
from __future__ import annotations

import numpy as np

from ...core.geometry.templates import AircraftModel, Surface
from ...core.solvers import panel_method as pm

# jasny motyw widoku 3D (spojny z reszta UI)
_BG = "#f8f9fa"
_SURF = "#c9d4e3"
_EDGE = "#94a3b8"
_CMAP = "coolwarm"        # niebieski (niskie Cp) -> czerwony (wysokie Cp)
_CLIM = (-2.0, 1.0)


def _transform_points(pts: np.ndarray, s: Surface) -> np.ndarray:
    """Przenosi wspolrzedne platu na pozycje w modelu (wznios, skos, LE, pion)."""
    pts = pts.copy()
    pts[:, 2] += np.abs(pts[:, 1]) * np.tan(np.deg2rad(s.dihedral_deg))
    if s.is_vertical:
        y = pts[:, 1].copy(); z = pts[:, 2].copy()
        pts[:, 1] = z
        pts[:, 2] = np.abs(y)
    pts[:, 0] += s.x_le
    pts[:, 2] += s.z_pos
    return pts


def _faces_array(panels: np.ndarray) -> np.ndarray:
    return np.hstack([[len(q), *q] for q in panels])


def _wing_mesh(s: Surface, n_chord: int = 24, n_span: int = 14):
    naca = s.airfoil_root.replace("NACA", "").strip() or "0012"
    naca_tip = (s.airfoil_tip or s.airfoil_root).replace("NACA", "").strip() or None
    try:
        return pm.make_wing_mesh(span=s.span, chord=s.root_chord,
                                 tip_chord=s.tip_chord, sweep_deg=s.sweep_deg,
                                 n_chord=n_chord, n_span=n_span, naca=naca,
                                 naca_tip=naca_tip)
    except Exception:  # noqa: BLE001
        return pm.make_wing_mesh(span=s.span, chord=s.root_chord,
                                 tip_chord=s.tip_chord, n_chord=n_chord,
                                 n_span=n_span)


def _surface_polydata(s: Surface, n_chord: int = 24, n_span: int = 14):
    """pv.PolyData grubego platu (bez Cp)."""
    import pyvista as pv
    mesh = _wing_mesh(s, n_chord, n_span)
    pts = _transform_points(mesh.nodes, s)
    return pv.PolyData(pts, _faces_array(mesh.panels)), mesh


def _symmetrize_cp(mesh, cp: np.ndarray) -> np.ndarray:
    """Wymusza symetrie Cp wzgledem osi rozpietosci (dla samolotu bez slizgu
    pole MUSI byc symetryczne; usuwa szum numeryczny solvera niskiego rzedu)."""
    if mesh.grid is None:
        return cp
    grid = mesh.grid
    nrow, ncol = grid.shape
    out = cp.copy()
    for r in range(nrow):
        rm = nrow - 1 - r
        for c in range(ncol):
            out[grid[r, c]] = 0.5 * (cp[grid[r, c]] + cp[grid[rm, c]])
    return out


def _pressure_polydata(s: Surface, alpha_deg: float, velocity: float):
    """pv.PolyData platu z gladkim, symetrycznym polem Cp (metoda panelowa)."""
    import pyvista as pv
    mesh = _wing_mesh(s, n_chord=20, n_span=12)
    a = np.deg2rad(alpha_deg)
    vinf = velocity * np.array([np.cos(a), 0.0, np.sin(a)])
    sol = pm.solve_panel(mesh, vinf)
    cp = pm.cp_clipped(sol["cp"], -4.0)
    cp = _symmetrize_cp(mesh, cp)
    pts = _transform_points(mesh.nodes, s)
    poly = pv.PolyData(pts, _faces_array(mesh.panels))
    poly.cell_data["Cp"] = cp
    return poly.cell_data_to_point_data()      # gladki gradient


class Model3DView:
    """Lekka warstwa nad QtInteractor; tworzona leniwie (PyVista ciezki)."""

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
        """Renderuje geometrie STEP z polem Cp (bez AircraftModel)."""
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

        # tryb STEP: brak AircraftModel, rysujemy geometrie STEP + Cp
        if self.model is None and result is not None and self._is_step_result(result):
            self._render_step(result)
            return
        if self.model is None:
            p.add_text("No model", position="upper_left", color="#334155",
                       font_size=12)
            return
        m = self.model

        has_surface_cp = False
        if self._layers.get("skrzydla", True):
            alpha = self._pressure_alpha(result)
            for s in m.surfaces:
                colored = False
                if pressure and result is not None and not s.is_vertical:
                    try:
                        poly = _pressure_polydata(s, alpha, getattr(result, "velocity", 15.0))
                        p.add_mesh(poly, scalars="Cp", cmap=_CMAP, clim=_CLIM,
                                   smooth_shading=True, show_edges=False,
                                   name=f"surf_{s.name}",
                                   scalar_bar_args={"title": "Cp", "color": "#1f2937",
                                                    "n_labels": 5})
                        colored = True
                        has_surface_cp = True
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

        # pole Cp z geometrii STEP (jesli wynik je zawiera i nie liczylismy z platow)
        if pressure and not has_surface_cp:
            self._add_step_pressure(result)

        p.add_axes(color="#334155")
        try:
            p.reset_camera(); p.view_isometric()
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
        cg = pv.Sphere(radius=max(m.fuselage_diam * 0.22, 0.01), center=(m.cg_x, 0, 0))
        self.plotter.add_mesh(cg, color="#dc2626", name="cg")
        self.plotter.add_point_labels(
            [[m.cg_x, 0, m.fuselage_diam]], ["CG"], font_size=12,
            text_color="#dc2626", shape=None, name="cg_lbl")
        if result is not None and getattr(result, "neutral_point_x", 0):
            npx = result.neutral_point_x
            npm = pv.Sphere(radius=max(m.fuselage_diam * 0.18, 0.008), center=(npx, 0, 0))
            self.plotter.add_mesh(npm, color="#059669", name="np")
            self.plotter.add_point_labels(
                [[npx, 0, -m.fuselage_diam]], ["Neutral point"], font_size=11,
                text_color="#059669", shape=None, name="np_lbl")

    def _add_step_pressure(self, result):
        """Renderuje pole Cp policzone na geometrii STEP jako kolorowa powierzchnie."""
        import pyvista as pv
        ex = getattr(result, "extras", {}) or {}
        cp = ex.get("cp")
        nodes = ex.get("cp_nodes")
        faces = ex.get("cp_faces")
        if cp is None:
            return
        if nodes is not None and faces is not None:
            poly = pv.PolyData(np.asarray(nodes), _faces_array(np.asarray(faces)))
            poly.cell_data["Cp"] = np.asarray(cp)
            poly = poly.cell_data_to_point_data()
            self.plotter.add_mesh(poly, scalars="Cp", cmap=_CMAP, clim=_CLIM,
                                  smooth_shading=True, show_edges=False,
                                  name="cp_field",
                                  scalar_bar_args={"title": "Cp", "color": "#1f2937"})
        else:
            cen = ex.get("mesh_centroids")
            if cen is None:
                return
            cloud = pv.PolyData(np.asarray(cen)); cloud["Cp"] = np.asarray(cp)
            self.plotter.add_mesh(cloud, scalars="Cp", cmap=_CMAP, clim=_CLIM,
                                  point_size=10, render_points_as_spheres=True,
                                  name="cp_field", scalar_bar_args={"title": "Cp"})

    def _render_step(self, result):
        """Renderuje bryle STEP (kolorowana Cp) + markery CG / punkt neutralny."""
        import pyvista as pv
        ex = getattr(result, "extras", {}) or {}
        nodes = np.asarray(ex["cp_nodes"])
        self._add_step_pressure(result)
        # markery skalowane do gabarytu geometrii STEP
        span = nodes.max(0) - nodes.min(0)
        r = max(float(np.linalg.norm(span)) * 0.02, 1e-4)
        zc = float(nodes[:, 2].mean())
        cg = getattr(result, "cg_x", None)
        if self._layers.get("markery", True) and cg is not None:
            self.plotter.add_mesh(pv.Sphere(radius=r, center=(cg, 0, zc)),
                                  color="#dc2626", name="cg")
            npx = getattr(result, "neutral_point_x", 0.0)
            if npx:
                self.plotter.add_mesh(pv.Sphere(radius=r * 0.85, center=(npx, 0, zc)),
                                      color="#059669", name="np")
        self.plotter.add_axes(color="#334155")
        try:
            self.plotter.reset_camera(); self.plotter.view_isometric()
        except Exception:  # noqa: BLE001
            pass

    def screenshot(self, path: str):
        self.plotter.screenshot(path)

    def close(self):
        try:
            self.plotter.close()
        except Exception:  # noqa: BLE001
            pass
