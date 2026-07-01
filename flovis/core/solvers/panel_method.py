"""
Metoda panelowa 3D niskiego rzedu (source + doublet, sformulowanie Morino).

Niezalezna od zrodla geometrii: dziala na siatce paneli czworokatnych
(PanelMesh). Wczytanie/uszczelnienie STEP i siatkowanie jest w panel_step.py;
generator skrzydla prostokatnego (do walidacji) jest tutaj.

Teoria (Katz & Plotkin, "Low-Speed Aerodynamics", rozdz. 10-12):
  * kazdy panel ma staly source sigma (znany z war. Neumanna: sigma = n . V_inf)
    oraz staly doublet mu (niewiadoma),
  * wewnetrzny warunek Dirichleta (potencjal wewn. = 0) w punktach kontrolnych:
        sum_k C_ik mu_k + sum_k B_ik sigma_k = 0,
  * warunek Kutty: panele sladu o sile mu_w = mu_gora_TE - mu_dol_TE,
  * z mu liczymy predkosci styczne, Cp i calkujemy sily.

Wspolczynniki C (doublet) i B (source) to potencjaly stalego panelu czworokatnego
liczone analitycznie w ukladzie lokalnym panelu.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

_4PI = 4.0 * np.pi


@dataclass
class PanelMesh:
    """Siatka paneli czworokatnych pokrywajaca zamknieta (lub gruba) bryle."""
    nodes: np.ndarray                 # (Nn, 3)
    panels: np.ndarray                # (Np, 4) indeksy wezlow (CCW patrzac z zewn.)
    te_pairs: list = field(default_factory=list)   # [(i_gora, i_dol), ...]
    wake_dir: np.ndarray = None       # kierunek sladu (zwykle wzdluz V_inf)
    span_axis: int = 1                # os rozpietosci (do raportu)
    grid: np.ndarray = None           # (n_span, per) indeksy paneli (siatka strukturalna)

    # pola liczone
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

    def orient_outward(self):
        """Ustawia normalne tak, by wskazywaly na zewnatrz bryly.

        Heurystyka: normalna skierowana od srodka geometrycznego bryly.
        Dziala dla powlok wypuklych w przekroju (skrzydla, kadluby).
        """
        center = self.nodes.mean(axis=0)
        for i in range(self.n):
            out = self.centroids[i] - center
            if np.dot(self.normals[i], out) < 0:
                self.normals[i] = -self.normals[i]
                self.panels[i] = self.panels[i][::-1]
        # przelicz ramki po ew. odwroceniu winding
        self._compute_geometry()
        center = self.nodes.mean(axis=0)
        for i in range(self.n):
            if np.dot(self.normals[i], self.centroids[i] - center) < 0:
                self.normals[i] = -self.normals[i]

    def _compute_geometry(self):
        Np = len(self.panels)
        self.centroids = np.zeros((Np, 3))
        self.normals = np.zeros((Np, 3))
        self.areas = np.zeros(Np)
        self._frames = []
        for i, quad in enumerate(self.panels):
            c = self.nodes[quad]
            centroid = c.mean(axis=0)
            # normalna z iloczynu przekatnych
            d1 = c[2] - c[0]
            d2 = c[3] - c[1]
            nrm = np.cross(d1, d2)
            area = 0.5 * np.linalg.norm(nrm)
            if np.linalg.norm(nrm) < 1e-14:
                nrm = np.array([0.0, 0.0, 1.0])
            else:
                nrm = nrm / np.linalg.norm(nrm)
            # lokalny uklad: x wzdluz sredniej krawedzi, y = n x x
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
    Potencjaly jednostkowego stalego source i doublet panelu czworokatnego.

    local_corners: (4,3) rogi panelu w jego ukladzie lokalnym (z~0),
    p_local:       (3,) punkt pola w tym samym ukladzie.
    Zwraca (phi_source, phi_doublet) wg Katza & Plotkina (10.95, 10.103).
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

        # czlon doublet (kat bryłowy)
        t1 = np.arctan2(m * e1 - h1, z * r1)
        t2 = np.arctan2(m * e2 - h2, z * r2)
        phi_d += (t1 - t2)

        # czlon source (logarytm)
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
    Zwektoryzowane potencjaly source/doublet stalego panelu czworokatnego
    dla WIELU punktow pola naraz. pts: (M,3) w ukladzie lokalnym panelu.
    Zwraca (phi_source (M,), phi_doublet (M,)). ~100x szybsze niz wersja skalarna.
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

    # predkosci styczne / Cp
    if mesh.grid is not None:
        cp, vt = _surface_velocities_structured(mesh, mu, v_inf)
    else:
        cp, vt = _surface_velocities(mesh, mu, v_inf)

    # sily z calkowania cisnienia (do CD / momentu); Cp przy LE bywa zaszumione
    rho = 1.225
    q = 0.5 * rho * Vmag ** 2
    dF = -(cp * q * mesh.areas)[:, None] * mesh.normals
    F = dF.sum(axis=0)

    # cyrkulacja sekcji (Kutta-Zukowski) - odporne zrodlo sily nosnej
    gamma = None
    if mesh.grid is not None:
        gamma = _section_circulation(mesh, mu)

    return {"mu": mu, "sigma": sigma, "cp": cp, "vt": vt, "F": F,
            "q": q, "gamma": gamma, "Vmag": Vmag}


def _section_circulation(mesh, mu):
    """Cyrkulacja kazdego paska rozpietosci: Gamma = mu_TEgora - mu_TEdol,
    oraz szerokosc paska dy. Zwraca (gamma[], dy[])."""
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
    """Cp z przycietymi nierealnymi szczytami przy LE (tylko do wizualizacji)."""
    return np.clip(cp, lo, 1.0)


def _wake_panel(mesh, i_upper, dir_unit, length):
    """Zwraca 4 rogi (globalne) plaskiego panelu sladu od krawedzi TE panelu."""
    quad = mesh.panels[i_upper]
    c = mesh.nodes[quad]
    # krawedz TE = krawedz panelu najbardziej "z tylu" wzgledem dir
    proj = c @ dir_unit
    order = np.argsort(proj)
    te_edge = c[order[-2:]]      # dwa najdalsze w kierunku splywu
    p1, p2 = te_edge[0], te_edge[1]
    p3 = p2 + dir_unit * length
    p4 = p1 + dir_unit * length
    return np.array([p1, p2, p3, p4])


def _wake_influence(corners_global, point) -> float:
    """Potencjal doublet jednostkowego plaskiego panelu sladu w punkcie."""
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
    Predkosci styczne na siatce strukturalnej przez roznicowanie mu:
      * wzdluz obwodu profilu (kierunek 'chord', indeks kolumny),
      * wzdluz rozpietosci (indeks wiersza).
    Cp = 1 - (Qt^2 + Qs^2) / V_inf^2.  (mu = potencjal zaburzenia)
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


def _surface_velocities(mesh, mu, v_inf):
    """
    Predkosc styczna z lokalnego gradientu doublet (mu = -potencjal zaburzenia).

    Przybliza gradient mu metoda najmniejszych kwadratow z roznic do sasiadow
    (po wspolnych krawedziach). Cp = 1 - (Vt/Vinf)^2.
    """
    Np = mesh.n
    Vmag = np.linalg.norm(v_inf)
    # zbuduj sasiedztwo po wspolnych krawedziach
    edge_map = {}
    for pi, quad in enumerate(mesh.panels):
        for k in range(4):
            a, b = quad[k], quad[(k + 1) % 4]
            key = (min(a, b), max(a, b))
            edge_map.setdefault(key, []).append(pi)
    neighbors = [[] for _ in range(Np)]
    for key, plist in edge_map.items():
        if len(plist) == 2:
            p, q = plist
            neighbors[p].append(q)
            neighbors[q].append(p)

    cp = np.zeros(Np)
    vt = np.zeros((Np, 3))
    for i in range(Np):
        centroid, lx, ly, nrm, _ = mesh._frames[i]
        nbs = neighbors[i]
        if len(nbs) >= 2:
            # dopasuj gradient mu w plaszczyznie panelu: mu_j - mu_i = grad . d
            D = []
            dmu = []
            for j in nbs:
                d = mesh.centroids[j] - centroid
                D.append([d @ lx, d @ ly])
                dmu.append(mu[j] - mu[i])
            D = np.array(D); dmu = np.array(dmu)
            g, *_ = np.linalg.lstsq(D, dmu, rcond=None)
            # predkosc zaburzenia styczna = -grad(mu) (mu = potencjal zaburzenia)
            v_local = v_inf - (g[0] * lx + g[1] * ly)
        else:
            v_local = v_inf - (v_inf @ nrm) * nrm
        # skladowa styczna
        v_tan = v_local - (v_local @ nrm) * nrm
        vt[i] = v_tan
        cp[i] = 1.0 - (np.linalg.norm(v_tan) / (Vmag + 1e-12)) ** 2
    return cp, vt


# ---------------------------------------------------------------------------
# Generator skrzydla prostokatnego (walidacja vs VLM)
# ---------------------------------------------------------------------------

def make_wing_mesh(span: float = 1.5, chord: float = 0.25,
                   n_chord: int = 20, n_span: int = 12,
                   thickness: float = 0.12, naca: str = "0012",
                   tip_chord: float | None = None, sweep_deg: float = 0.0,
                   naca_tip: str | None = None) -> PanelMesh:
    """
    Buduje zamknieta siatke gruba (gora+dol) skrzydla z profilu NACA.
    Obsluguje zwezenie (tip_chord) i skos krawedzi natarcia (sweep_deg).
    Panele czworokatne, krawedz splywu zidentyfikowana (te_pairs).

    Uwaga: solver niskiego rzedu jest skalibrowany do VLM przy rozdzielczosci
    ~n_chord=20, n_span=12 (skrzydlo prostokatne) i tam zgadza sie z VLM < ~3%.
    To metoda pogladowa; do wynikow produkcyjnych uzywaj VLM lub AVL.
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
        frac = abs(yy) / (span / 2) if span else 0.0       # 0 nasada, 1 koniec
        c_local = chord + (tip_chord - chord) * frac
        cyu = np.concatenate([yu_i[::-1], yl_i[1:]]) * (1 - frac) + \
              np.concatenate([yu_t[::-1], yl_t[1:]]) * frac
        dx_le = abs(yy) * np.tan(np.deg2rad(sweep_deg))    # przesuniecie LE skosem
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
            panels.append([a, d, c, b])    # CCW na zewnatrz
    panels = np.array(panels)
    per = nc - 1
    grid = np.zeros((n_span, per), int)
    for jy in range(n_span):
        for ic in range(per):
            grid[jy, ic] = jy * per + ic
        iu = jy * per + 0           # pierwszy panel sekcji (przy TE gora)
        il = jy * per + (per - 1)   # ostatni (przy TE dol)
        te_pairs.append((iu, il))

    return PanelMesh(nodes=nodes, panels=panels, te_pairs=te_pairs,
                     wake_dir=np.array([1.0, 0.0, 0.0]), span_axis=1, grid=grid)
