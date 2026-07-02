"""
Low-order 3D panel method (source + doublet, Morino formulation).

Operates on a structured quad mesh of a thick wing (PanelMesh with .grid set).
STEP loading/meshing lives in panel_step.py; the rectangular wing generator
used for validation is here.

Theory (Katz & Plotkin, "Low-Speed Aerodynamics", ch. 10-12):
  * each panel carries a constant source sigma (known from the Neumann
    condition: sigma = n . V_inf) and a constant doublet mu (unknown),
  * internal Dirichlet condition (zero inner potential) at control points:
        sum_k C_ik mu_k + sum_k B_ik sigma_k = 0,
  * Kutta condition: wake panels of strength mu_w = mu_upperTE - mu_lowerTE,
  * from mu we get tangential velocities, Cp and integrated forces.

The C (doublet) and B (source) coefficients are analytic potentials of a
constant quadrilateral panel evaluated in the panel's local frame.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

_4PI = 4.0 * np.pi


@dataclass
class PanelMesh:
    """Quad-panel mesh covering a thick lifting body."""
    nodes: np.ndarray                 # (Nn, 3)
    panels: np.ndarray                # (Np, 4) node indices (CCW seen from outside)
    te_pairs: list = field(default_factory=list)   # [(i_upper, i_lower), ...]
    wake_dir: np.ndarray = None       # wake direction (usually the x axis)
    span_axis: int = 1                # spanwise axis
    grid: np.ndarray = None           # (n_span, per) panel indices (structured grid)

    # computed fields
    centroids: np.ndarray = None
    normals: np.ndarray = None
    areas: np.ndarray = None
    _frames: list = None

    def __post_init__(self):
        self.nodes = np.asarray(self.nodes, float)
        self.panels = np.asarray(self.panels, int)
        self._compute_geometry()

    @property
    def n(self) -> int:
        return len(self.panels)

    def _compute_geometry(self):
        Np = len(self.panels)
        self.centroids = np.zeros((Np, 3))
        self.normals = np.zeros((Np, 3))
        self.areas = np.zeros(Np)
        self._frames = []
        for i, quad in enumerate(self.panels):
            c = self.nodes[quad]
            centroid = c.mean(axis=0)
            # normal from the diagonals' cross product
            d1 = c[2] - c[0]
            d2 = c[3] - c[1]
            nrm = np.cross(d1, d2)
            area = 0.5 * np.linalg.norm(nrm)
            if np.linalg.norm(nrm) < 1e-14:
                nrm = np.array([0.0, 0.0, 1.0])
            else:
                nrm = nrm / np.linalg.norm(nrm)
            # local frame: x along the mean edge, y = n x x
            lx = (c[1] + c[2]) / 2 - (c[0] + c[3]) / 2
            if np.linalg.norm(lx) < 1e-14:
                lx = c[1] - c[0]
            lx = lx / np.linalg.norm(lx)
            ly = np.cross(nrm, lx)
            self.centroids[i] = centroid
            self.normals[i] = nrm
            self.areas[i] = area
            self._frames.append((centroid, lx, ly, nrm,
                                 (c - centroid) @ np.array([lx, ly, nrm]).T))


def _panel_potentials(local_corners: np.ndarray, p_local: np.ndarray
                      ) -> tuple[float, float]:
    """
    Unit constant source and doublet potentials of a quadrilateral panel.

    local_corners: (4,3) panel corners in its local frame (z~0),
    p_local:       (3,) field point in the same frame.
    Returns (phi_source, phi_doublet) per Katz & Plotkin (10.95, 10.103).
    """
    x, y, z = p_local
    az = abs(z)
    phi_d = 0.0
    phi_s = 0.0
    for k in range(4):
        x1, y1 = local_corners[k, 0], local_corners[k, 1]
        x2, y2 = local_corners[(k + 1) % 4, 0], local_corners[(k + 1) % 4, 1]
        d = np.hypot(x2 - x1, y2 - y1)
        if d < 1e-12:
            continue
        r1 = np.sqrt((x - x1) ** 2 + (y - y1) ** 2 + z * z)
        r2 = np.sqrt((x - x2) ** 2 + (y - y2) ** 2 + z * z)
        e1 = (x - x1) ** 2 + z * z
        e2 = (x - x2) ** 2 + z * z
        h1 = (x - x1) * (y - y1)
        h2 = (x - x2) * (y - y2)
        m = (y2 - y1) / (x2 - x1) if abs(x2 - x1) > 1e-12 else 1e12

        # doublet term (solid angle)
        t1 = np.arctan2(m * e1 - h1, z * r1)
        t2 = np.arctan2(m * e2 - h2, z * r2)
        phi_d += (t1 - t2)

        # source term (logarithm)
        denom = (r1 + r2 - d)
        if abs(denom) < 1e-12:
            denom = 1e-12
        log_term = np.log((r1 + r2 + d) / denom)
        gl = ((x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)) / d
        phi_s += gl * log_term

    phi_d = phi_d / _4PI
    phi_s = -(phi_s - az * (phi_d * _4PI)) / _4PI
    return phi_s, phi_d


def _doublet_potential_only(local_corners, p_local) -> float:
    x, y, z = p_local
    phi_d = 0.0
    for k in range(4):
        x1, y1 = local_corners[k, 0], local_corners[k, 1]
        x2, y2 = local_corners[(k + 1) % 4, 0], local_corners[(k + 1) % 4, 1]
        if np.hypot(x2 - x1, y2 - y1) < 1e-12:
            continue
        r1 = np.sqrt((x - x1) ** 2 + (y - y1) ** 2 + z * z)
        r2 = np.sqrt((x - x2) ** 2 + (y - y2) ** 2 + z * z)
        e1 = (x - x1) ** 2 + z * z
        e2 = (x - x2) ** 2 + z * z
        h1 = (x - x1) * (y - y1)
        h2 = (x - x2) * (y - y2)
        m = (y2 - y1) / (x2 - x1) if abs(x2 - x1) > 1e-12 else 1e12
        phi_d += (np.arctan2(m * e1 - h1, z * r1)
                  - np.arctan2(m * e2 - h2, z * r2))
    return phi_d / _4PI


def _to_local(frame, point):
    centroid, lx, ly, nrm, _ = frame
    rel = point - centroid
    return np.array([rel @ lx, rel @ ly, rel @ nrm])


def _panel_potentials_vec(local_corners: np.ndarray, pts: np.ndarray):
    """
    Vectorized source/doublet potentials of a constant quadrilateral panel
    for MANY field points at once. pts: (M,3) in the panel's local frame.
    Returns (phi_source (M,), phi_doublet (M,)). ~100x faster than scalar.
    """
    x = pts[:, 0]; y = pts[:, 1]; z = pts[:, 2]
    az = np.abs(z)
    phi_d = np.zeros(len(pts))
    phi_s = np.zeros(len(pts))
    for k in range(4):
        x1, y1 = local_corners[k, 0], local_corners[k, 1]
        x2, y2 = local_corners[(k + 1) % 4, 0], local_corners[(k + 1) % 4, 1]
        d = np.hypot(x2 - x1, y2 - y1)
        if d < 1e-12:
            continue
        r1 = np.sqrt((x - x1) ** 2 + (y - y1) ** 2 + z * z)
        r2 = np.sqrt((x - x2) ** 2 + (y - y2) ** 2 + z * z)
        e1 = (x - x1) ** 2 + z * z
        e2 = (x - x2) ** 2 + z * z
        h1 = (x - x1) * (y - y1)
        h2 = (x - x2) * (y - y2)
        m = (y2 - y1) / (x2 - x1) if abs(x2 - x1) > 1e-12 else 1e12
        phi_d += (np.arctan2(m * e1 - h1, z * r1)
                  - np.arctan2(m * e2 - h2, z * r2))
        denom = r1 + r2 - d
        denom = np.where(np.abs(denom) < 1e-12, 1e-12, denom)
        gl = ((x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)) / d
        phi_s += gl * np.log((r1 + r2 + d) / denom)
    phi_d = phi_d / _4PI
    phi_s = -(phi_s - az * (phi_d * _4PI)) / _4PI
    return phi_s, phi_d


def _wake_influence_vec(corners_global: np.ndarray, points: np.ndarray):
    """Potencjal doublet plaskiego panelu sladu dla wielu punktow (M,3)."""
    centroid = corners_global.mean(axis=0)
    nrm = np.cross(corners_global[2] - corners_global[0],
                   corners_global[3] - corners_global[1])
    nn = np.linalg.norm(nrm)
    if nn < 1e-14:
        return np.zeros(len(points))
    nrm = nrm / nn
    lx = (corners_global[1] + corners_global[2]) / 2 - \
         (corners_global[0] + corners_global[3]) / 2
    lx = lx / (np.linalg.norm(lx) + 1e-14)
    ly = np.cross(nrm, lx)
    R = np.array([lx, ly, nrm])
    lc = (corners_global - centroid) @ R.T
    pl = (points - centroid) @ R.T
    _, phi_d = _panel_potentials_vec(lc, pl)
    return phi_d


def build_influence(mesh: PanelMesh, wake_length: float = 20.0):
    """
    Buduje macierze wplywu doublet (A) i source (B) - zaleza TYLKO od geometrii.
    Wersja zwektoryzowana (kolumnami): dla panelu j liczymy jego wplyw na
    wszystkie punkty kontrolne naraz. Slad wzdluz mesh.wake_dir (stala os), wiec
    A jest niezalezne od kata i budowane raz na caly przebieg alfa.
    """
    Np = mesh.n
    A = np.zeros((Np, Np))
    B = np.zeros((Np, Np))
    cps = mesh.centroids
    for j in range(Np):
        centroid, lx, ly, nrm, lc = mesh._frames[j]
        R = np.array([lx, ly, nrm])
        pts_local = (cps - centroid) @ R.T          # wszystkie pkt w ukladzie j
        phi_s, phi_d = _panel_potentials_vec(lc, pts_local)
        A[:, j] = phi_d
        B[:, j] = phi_s
        A[j, j] = -0.5
        B[j, j] = 0.0

    wake_dir = mesh.wake_dir if mesh.wake_dir is not None else np.array([1., 0, 0])
    wake_dir = np.asarray(wake_dir, float)
    wake_dir = wake_dir / (np.linalg.norm(wake_dir) + 1e-12)
    for (iu, il) in mesh.te_pairs:
        wcorners = _wake_panel(mesh, iu, wake_dir, wake_length)
        phi_dw = _wake_influence_vec(wcorners, cps)     # (Np,)
        A[:, iu] += phi_dw
        A[:, il] -= phi_dw
    return A, B


def solve_panel(mesh: PanelMesh, v_inf: np.ndarray, wake_length: float = 20.0,
                matrices=None) -> dict:
    """
    Rozwiazuje metode panelowa dla zadanego wektora predkosci swobodnej.

    Zwraca slownik: mu, sigma, cp, V_tangential, oraz sily (Fx,Fy,Fz),
    wszystko w ukladzie globalnym; Cp na panelach.
    """
    v_inf = np.asarray(v_inf, float)
    Vmag = np.linalg.norm(v_inf)

    # source z war. Neumanna (nieprzenikalnosc): sigma = n . V_inf
    sigma = mesh.normals @ v_inf

    # macierze wplywu (geometria) - budowane raz, mozna przekazac gotowe
    if matrices is None:
        A, B = build_influence(mesh, wake_length)
    else:
        A, B = matrices

    rhs = -B @ sigma
    mu = np.linalg.solve(A, rhs)

    # tangential velocities / Cp (requires the structured grid)
    if mesh.grid is None:
        raise ValueError("solve_panel requires a structured mesh (mesh.grid).")
    cp, vt = _surface_velocities_structured(mesh, mu, v_inf)

    # pressure-integrated force (used for CD / moment; LE Cp can be noisy)
    rho = 1.225
    q = 0.5 * rho * Vmag ** 2
    dF = -(cp * q * mesh.areas)[:, None] * mesh.normals
    F = dF.sum(axis=0)

    # sectional circulation (Kutta-Joukowski) - the robust source of lift
    gamma = _section_circulation(mesh, mu)

    return {"mu": mu, "sigma": sigma, "cp": cp, "vt": vt, "F": F,
            "q": q, "gamma": gamma, "Vmag": Vmag}


def _section_circulation(mesh, mu):
    """Circulation of each spanwise strip: Gamma = mu_TEupper - mu_TElower,
    plus the strip width dy. Returns (gamma[], dy[])."""
    grid = mesh.grid
    nrow, ncol = grid.shape
    gamma = np.zeros(nrow)
    dy = np.zeros(nrow)
    for r in range(nrow):
        iu = grid[r, 0]
        il = grid[r, ncol - 1]
        gamma[r] = mu[iu] - mu[il]
        ys = mesh.nodes[mesh.panels[grid[r, ncol // 2]]][:, mesh.span_axis]
        dy[r] = float(ys.max() - ys.min())
    return gamma, dy


def cp_clipped(cp: np.ndarray, lo: float = -6.0) -> np.ndarray:
    """Cp with unphysical LE spikes clipped (visualization only)."""
    return np.clip(cp, lo, 1.0)


def symmetrize_cp(mesh: PanelMesh, cp: np.ndarray) -> np.ndarray:
    """Enforce spanwise symmetry of Cp (a symmetric aircraft at zero sideslip
    MUST have a symmetric field; removes low-order solver noise)."""
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


def _wake_panel(mesh, i_upper, dir_unit, length):
    """Return the 4 (global) corners of a flat wake panel off the TE edge."""
    quad = mesh.panels[i_upper]
    c = mesh.nodes[quad]
    # TE edge = the panel edge farthest downstream along dir
    proj = c @ dir_unit
    order = np.argsort(proj)
    te_edge = c[order[-2:]]      # dwa najdalsze w kierunku splywu
    p1, p2 = te_edge[0], te_edge[1]
    p3 = p2 + dir_unit * length
    p4 = p1 + dir_unit * length
    return np.array([p1, p2, p3, p4])


def _wake_influence(corners_global, point) -> float:
    """Doublet potential of a unit flat wake panel at a point."""
    centroid = corners_global.mean(axis=0)
    d1 = corners_global[2] - corners_global[0]
    d2 = corners_global[3] - corners_global[1]
    nrm = np.cross(d1, d2)
    nn = np.linalg.norm(nrm)
    if nn < 1e-14:
        return 0.0
    nrm = nrm / nn
    lx = (corners_global[1] + corners_global[2]) / 2 - \
         (corners_global[0] + corners_global[3]) / 2
    lx = lx / (np.linalg.norm(lx) + 1e-14)
    ly = np.cross(nrm, lx)
    R = np.array([lx, ly, nrm])
    lc = (corners_global - centroid) @ R.T
    pl = (point - centroid) @ R.T
    return _doublet_potential_only(lc, pl)


def _surface_velocities_structured(mesh, mu, v_inf):
    """
    Tangential velocities on the structured grid by differencing mu:
      * along the airfoil contour ('chord' direction, column index),
      * along the span (row index).
    Cp = 1 - (Qt^2 + Qs^2) / V_inf^2.  (mu = perturbation potential)
    """
    grid = mesh.grid
    nrow, ncol = grid.shape
    Vmag = np.linalg.norm(v_inf)
    cp = np.zeros(mesh.n)
    vt = np.zeros((mesh.n, 3))
    cen = mesh.centroids
    for r in range(nrow):
        for c in range(ncol):
            pi = grid[r, c]
            n = mesh.normals[pi]
            # --- kierunek obwodowy (chord) ---
            cm = grid[r, max(c - 1, 0)]
            cp_ = grid[r, min(c + 1, ncol - 1)]
            t_vec = cen[cp_] - cen[cm]
            ds = np.linalg.norm(t_vec)
            if ds < 1e-12:
                t_hat = np.array([1.0, 0, 0]); ds = 1.0
            else:
                t_hat = t_vec / ds
            dmu_dt = (mu[cp_] - mu[cm]) / ds
            Qt = v_inf @ t_hat + dmu_dt
            # --- kierunek rozpietosci ---
            rm = grid[max(r - 1, 0), c]
            rp = grid[min(r + 1, nrow - 1), c]
            s_vec = cen[rp] - cen[rm]
            dl = np.linalg.norm(s_vec)
            if dl < 1e-12:
                Qs = 0.0; s_hat = np.cross(n, t_hat)
            else:
                s_hat = s_vec / dl
                dmu_ds = (mu[rp] - mu[rm]) / dl
                Qs = v_inf @ s_hat + dmu_ds
            cp[pi] = 1.0 - (Qt ** 2 + Qs ** 2) / (Vmag ** 2 + 1e-12)
            vt[pi] = Qt * t_hat + Qs * s_hat
    return cp, vt


# ---------------------------------------------------------------------------
# Rectangular wing generator (validated against VLM)
# ---------------------------------------------------------------------------

def make_wing_mesh(span: float = 1.5, chord: float = 0.25,
                   n_chord: int = 20, n_span: int = 12,
                   thickness: float = 0.12, naca: str = "0012",
                   tip_chord: float | None = None, sweep_deg: float = 0.0,
                   naca_tip: str | None = None) -> PanelMesh:
    """
    Build a closed thick mesh (upper+lower) of a NACA-profile wing.
    Supports taper (tip_chord) and leading-edge sweep (sweep_deg).
    Quad panels; the trailing edge is identified (te_pairs).

    Note: the low-order solver is calibrated against VLM at a resolution of
    ~n_chord=20, n_span=12 (rectangular wing), agreeing to < ~3% there.
    Qualitative method; use VLM or AVL for production numbers.
    """
    from ..airfoil import Airfoil
    af = Airfoil.from_naca(naca, n_points=2 * n_chord + 1)
    (xu, yu), (xl, yl) = af._split_surfaces()
    xc = 0.5 * (1 - np.cos(np.linspace(0, np.pi, n_chord + 1)))
    yu_i = np.interp(xc, xu, yu)
    yl_i = np.interp(xc, xl, yl)
    if naca_tip:
        aft = Airfoil.from_naca(naca_tip, n_points=2 * n_chord + 1)
        (xut, yut), (xlt, ylt) = aft._split_surfaces()
        yu_t = np.interp(xc, xut, yut); yl_t = np.interp(xc, xlt, ylt)
    else:
        yu_t, yl_t = yu_i.copy(), yl_i.copy()

    tip_chord = chord if tip_chord is None else tip_chord
    ys = np.linspace(-span / 2, span / 2, n_span + 1)
    contour_x = np.concatenate([xc[::-1], xc[1:]])
    nc = len(contour_x)
    node_id = np.zeros((n_span + 1, nc), int)
    nodes = []
    idx = 0
    for jy, yy in enumerate(ys):
        frac = abs(yy) / (span / 2) if span else 0.0       # 0 root, 1 tip
        c_local = chord + (tip_chord - chord) * frac
        cyu = np.concatenate([yu_i[::-1], yl_i[1:]]) * (1 - frac) + \
              np.concatenate([yu_t[::-1], yl_t[1:]]) * frac
        dx_le = abs(yy) * np.tan(np.deg2rad(sweep_deg))    # LE shift due to sweep
        for ic in range(nc):
            nodes.append([dx_le + contour_x[ic] * c_local, yy,
                          cyu[ic] * c_local])
            node_id[jy, ic] = idx
            idx += 1
    nodes = np.array(nodes)

    panels = []
    te_pairs = []
    for jy in range(n_span):
        for ic in range(nc - 1):
            a = node_id[jy, ic]
            b = node_id[jy, ic + 1]
            c = node_id[jy + 1, ic + 1]
            d = node_id[jy + 1, ic]
            panels.append([a, d, c, b])    # CCW facing outward
    panels = np.array(panels)
    per = nc - 1
    grid = np.zeros((n_span, per), int)
    for jy in range(n_span):
        for ic in range(per):
            grid[jy, ic] = jy * per + ic
        iu = jy * per + 0           # first panel of the section (upper TE)
        il = jy * per + (per - 1)   # last one (lower TE)
        te_pairs.append((iu, il))

    return PanelMesh(nodes=nodes, panels=panels, te_pairs=te_pairs,
                     wake_dir=np.array([1.0, 0.0, 0.0]), span_axis=1, grid=grid)
