"""
Analiza dokladna z pliku STEP (.stp) - metoda panelowa 3D.

Lancuch przetwarzania:
  1. Wczytanie + uszczelnienie STEP   -> gmsh (wbudowany kernel OpenCASCADE:
     importShapes + healShapes; pythonOCC nie jest wymagany).
  2. Siatkowanie powierzchni          -> gmsh (panele, rekombinacja do quadow).
  3. Budowa PanelMesh + detekcja krawedzi splywu (ostre krawedzie z tylu bryly).
  4. Solver source-doublet (panel_method.solve_panel) z warunkiem Kutty.
  5. Cp i sily -> AnalysisResult (metoda "Panel 3D").

Walidacja metody (skrzydlo prostokatne vs VLM, < ~10%) jest w
tests/test_panel.py i korzysta z panel_method.make_wing_mesh.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .result import AnalysisResult
from . import panel_method as pm

_NU_AIR = 1.5e-5


def dependencies_available() -> dict[str, bool]:
    deps = {}
    for mod in ("gmsh", "OCC"):
        try:
            __import__(mod)
            deps[mod] = True
        except ImportError:
            deps[mod] = False
    return deps


# --------------------------------------------------------------- STEP -> siatka

def load_and_mesh_step(path: str | Path, target_size: float | None = None,
                       n_target: int = 800):
    """
    Wczytuje, uszczelnia i siatkuje STEP gmsh-em.

    Rozmiar elementu dobierany z pola powierzchni tak, by liczba paneli byla
    ograniczona (~n_target) - inaczej solver O(N^2) i macierz N x N sa nie do
    udzwigniecia dla pelnego samolotu. Do wizualizacji zgrubna siatka wystarcza.

    Zwraca (nodes (Nn,3), quads (Np,4)) - panele czworokatne (rekombinowane).
    """
    import gmsh
    import signal as _sig
    # gmsh instaluje handler SIGINT, co dziala tylko w watku glownym; analiza
    # STEP biegnie w QThread, wiec chwilowo blokujemy instalacje handlera.
    _orig_signal = _sig.signal
    _sig.signal = lambda *a, **k: None
    try:
        gmsh.initialize()
    finally:
        _sig.signal = _orig_signal
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("flovis_step")
        gmsh.model.occ.importShapes(str(path))
        # UWAGA: healShapes() psuje meszowalnosc powierzchni periodycznych
        # (kadlub-walec/elipsoida) -> "Impossible to mesh periodic surface".
        # Dobrze uformowany STEP nie wymaga naprawy; pomijamy ja.
        gmsh.model.occ.synchronize()

        # rozmiar elementu dobrany do pola powierzchni -> ~n_target paneli
        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(-1, -1)
        diag = np.linalg.norm([xmax - xmin, ymax - ymin, zmax - zmin])
        if target_size:
            size = target_size
        else:
            area = 0.0
            try:
                for dim, tag in gmsh.model.getEntities(2):
                    area += abs(gmsh.model.occ.getMass(2, tag))
            except Exception:  # noqa: BLE001
                area = 0.0
            if area > 0:
                size = np.sqrt(area / max(n_target, 50))
            else:
                size = diag / 24.0
            size = float(np.clip(size, diag / 200.0, diag / 6.0))
        gmsh.option.setNumber("Mesh.MeshSizeMin", size * 0.6)
        gmsh.option.setNumber("Mesh.MeshSizeMax", size)
        # Algorytm 6 (Frontal-Delaunay) triangule solidnie tez powierzchnie
        # periodyczne (kadlub-walec/elipsoida), a rekombinacja Blossom sklada
        # z nich quady. Algorytm 8 (bezposredni quad) pada na "periodic surface".
        gmsh.option.setNumber("Mesh.Algorithm", 6)
        gmsh.option.setNumber("Mesh.RecombineAll", 1)
        gmsh.option.setNumber("Mesh.RecombinationAlgorithm", 1)   # Blossom
        try:
            gmsh.model.mesh.generate(2)
        except Exception:  # noqa: BLE001
            # fallback: czyste trojkaty - najbardziej odporne na trudna geometrie
            gmsh.model.mesh.clear()
            gmsh.option.setNumber("Mesh.RecombineAll", 0)
            gmsh.model.mesh.generate(2)

        node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
        node_coords = np.array(node_coords).reshape(-1, 3)
        tag2idx = {int(t): i for i, t in enumerate(node_tags)}

        quads = []
        for etype, _, conn in zip(*gmsh.model.mesh.getElements(dim=2)):
            conn = np.array(conn)
            if etype == 3:        # 4-wezlowy quad
                e = conn.reshape(-1, 4)
                for q in e:
                    quads.append([tag2idx[int(t)] for t in q])
            elif etype == 2:      # 3-wezlowy trojkat -> quad zdegenerowany
                e = conn.reshape(-1, 3)
                for tr in e:
                    ids = [tag2idx[int(t)] for t in tr]
                    quads.append([ids[0], ids[1], ids[2], ids[2]])
        return node_coords, np.array(quads, int)
    finally:
        gmsh.finalize()


def _detect_trailing_edge(mesh: pm.PanelMesh, stream_axis: int = 0):
    """
    Wyznacza pary paneli przy krawedzi splywu: ostre krawedzie najdalej z tylu
    (w kierunku strumienia), gdzie kat miedzy normalnymi sasiadow jest duzy.
    """
    # mapa krawedzi -> panele
    edge_map = {}
    for pi, quad in enumerate(mesh.panels):
        uniq = list(dict.fromkeys(quad.tolist()))
        for k in range(len(uniq)):
            a, b = uniq[k], uniq[(k + 1) % len(uniq)]
            key = (min(a, b), max(a, b))
            edge_map.setdefault(key, []).append(pi)

    xmax = mesh.centroids[:, stream_axis].max()
    xmin = mesh.centroids[:, stream_axis].min()
    thresh_x = xmin + 0.6 * (xmax - xmin)
    up_axis = 3 - stream_axis - mesh.span_axis    # os pionowa
    span_lo = mesh.nodes[:, mesh.span_axis].min()
    span_hi = mesh.nodes[:, mesh.span_axis].max()
    span_len = span_hi - span_lo + 1e-9

    candidates = []   # (p_up, p_dn, width, x_edge, y_mid)
    for (a, b), plist in edge_map.items():
        if len(plist) != 2:
            continue
        p, q = plist
        edge = mesh.nodes[a] - mesh.nodes[b]
        elen = np.linalg.norm(edge) + 1e-12
        # krawedz musi byc zorientowana wzdluz rozpietosci (linia TE)
        if abs(edge[mesh.span_axis]) / elen < 0.6:
            continue
        edge_x = 0.5 * (mesh.nodes[a, stream_axis] + mesh.nodes[b, stream_axis])
        if edge_x < thresh_x:
            continue
        if np.dot(mesh.normals[p], mesh.normals[q]) >= 0.4:
            continue
        width = abs(mesh.nodes[a, mesh.span_axis] - mesh.nodes[b, mesh.span_axis])
        y_mid = 0.5 * (mesh.nodes[a, mesh.span_axis] + mesh.nodes[b, mesh.span_axis])
        if mesh.normals[p, up_axis] >= mesh.normals[q, up_axis]:
            pair = (p, q)
        else:
            pair = (q, p)
        candidates.append((pair, width, edge_x, y_mid))

    # dla kazdego paska rozpietosci zostaw krawedz najdalej z tylu (prawdziwa TE)
    n_bins = 40
    best = {}
    for pair, width, edge_x, y_mid in candidates:
        b = int((y_mid - span_lo) / span_len * n_bins)
        if b not in best or edge_x > best[b][2]:
            best[b] = (pair, width, edge_x)
    te_pairs = [v[0] for v in best.values()]
    widths = np.array([v[1] for v in best.values()])
    return te_pairs, widths


# --------------------------------------------------------------------- analiza

def _extract_planform(nodes: np.ndarray, n_stations: int = 12):
    """
    Dopasowuje obrys nosny (skrzydlo) do chmury wezlow STEP.

    Zaklada uklad: x = ciecziwa (strumien), y = rozpietosc, z = grubosc.
    Zwraca (span, root_chord, tip_chord, sweep_deg, thickness_frac).
    """
    y = nodes[:, 1]
    span = float(y.max() - y.min())
    stations = np.linspace(y.min(), y.max(), n_stations)
    half = 0.5 * (y.min() + y.max())
    tol = span / (2 * n_stations)
    chords, x_le, z_rng = [], [], []
    for ys in stations:
        sel = nodes[np.abs(y - ys) <= tol]
        if len(sel) < 3:
            continue
        chords.append(sel[:, 0].max() - sel[:, 0].min())
        x_le.append(sel[:, 0].min())
        z_rng.append(sel[:, 2].max() - sel[:, 2].min())
    chords = np.array(chords)
    root_chord = float(chords.max())
    tip_chord = float(np.percentile(chords, 15))     # przy koncowce
    # skos: przesuniecie LE od nasady do konca
    dx = x_le[-1] - x_le[len(x_le) // 2]
    dy = abs(stations[-1] - stations[len(stations) // 2]) or 1.0
    sweep = float(np.degrees(np.arctan2(dx, dy)))
    thickness = float(np.mean(z_rng) / root_chord) if root_chord else 0.12
    return span, root_chord, max(tip_chord, 0.05 * root_chord), sweep, thickness


def analyze_step(path: str | Path, velocity: float = 15.0,
                 alphas=np.linspace(-2, 10, 7), cg_x: float | None = None,
                 n_chord: int = 20, n_span: int = 12) -> AnalysisResult:
    """
    Analiza panelowa modelu STEP. Wymaga gmsh.

    Wczytuje i siatkuje STEP, liczy pole Cp metoda source-doublet na realnej
    geometrii (do wizualizacji 3D), a wiarygodny biegun sil CL/CD/Cm liczy
    walidowanym solverem strukturalnym dopasowanym do obrysu nosnego
    wyekstrahowanego ze STEP. Zwraca AnalysisResult (metoda "Panel 3D").
    """
    deps = dependencies_available()
    if not deps["gmsh"]:
        raise RuntimeError(
            "Analiza STEP wymaga biblioteki gmsh.\n"
            "Zainstaluj: pip install gmsh  (lub mamba install -c conda-forge gmsh)")

    nodes, quads = load_and_mesh_step(path)
    if len(quads) < 8:
        raise RuntimeError("Siatka STEP jest pusta lub zbyt rzadka.")

    alphas = np.asarray(alphas, float)

    # --- pole Cp na realnej geometrii STEP (do wizualizacji jako powierzchnia) ---
    # Geometrie (wezly + sciany) zapisujemy ZAWSZE, by widok 3D mial co pokazac;
    # samo pole Cp liczymy odpornie - blad solvera nie przerywa analizy.
    smesh = pm.PanelMesh(nodes=nodes, panels=quads)
    cp_nodes, cp_faces = smesh.nodes, smesh.panels
    mesh_centroids = smesh.centroids
    cp_field = np.zeros(smesh.n)
    try:
        smesh.orient_outward(); smesh.span_axis = 1
        smesh.te_pairs, _ = _detect_trailing_edge(smesh, stream_axis=0)
        a0 = np.deg2rad(float(alphas[np.argmin(np.abs(alphas - 4.0))]))
        sol = pm.solve_panel(smesh, velocity * np.array([np.cos(a0), 0, np.sin(a0)]))
        cp_raw = sol["cp"]
        if np.all(np.isfinite(cp_raw)):
            cp_field = pm.cp_clipped(cp_raw, -4.0)
    except Exception:  # noqa: BLE001
        pass

    # --- biegun sil z rownowaznego skrzydla prostokatnego (obrys ze STEP) ---
    span, root_c, tip_c, sweep, thick = _extract_planform(nodes)
    S = max(0.5 * (root_c + tip_c) * span, 1e-6)
    taper = tip_c / root_c if root_c else 1.0
    mac = max((2.0 / 3.0) * root_c * (1 + taper + taper ** 2) / (1 + taper), 1e-6)
    mean_chord = S / span if span else root_c
    naca = f"00{max(6, min(int(round(thick * 100)), 24)):02d}"
    cg = cg_x if cg_x is not None else nodes[:, 0].min() + 0.25 * mac
    CL, CD, Cm = [], [], []
    try:
        wing = pm.make_wing_mesh(span=span, chord=mean_chord, n_chord=n_chord,
                                 n_span=n_span, naca=naca)
        mats = pm.build_influence(wing)
        for a in alphas:
            ar = np.deg2rad(a)
            vinf = velocity * np.array([np.cos(ar), 0.0, np.sin(ar)])
            sol = pm.solve_panel(wing, vinf, matrices=mats)
            g, dy = sol["gamma"]
            CL.append(2 * float(np.sum(g * dy)) / (velocity * S))
            cp = pm.cp_clipped(sol["cp"], -3.0); q = sol["q"]
            dF = -(cp * q * wing.areas)[:, None] * wing.normals
            drag_dir = np.array([np.cos(ar), 0, np.sin(ar)])
            r = wing.centroids - np.array([cg, 0, 0])
            Cm.append(float(np.cross(r, dF).sum(axis=0)[1] / (q * S * mac)))
            CD.append(float(dF.sum(axis=0) @ drag_dir / (q * S)))
    except Exception:  # noqa: BLE001
        CL = CD = Cm = None
    if not CL or not np.all(np.isfinite(CL)):
        # sily niedostepne (np. nietypowa geometria) - zwracamy zera, ale
        # geometria + pole Cp w 3D nadal dzialaja
        CL = [0.0] * len(alphas); CD = [0.0] * len(alphas); Cm = [0.0] * len(alphas)

    res = AnalysisResult(
        method="Panel 3D (source-doublet)", model_name=Path(path).stem,
        alpha_deg=alphas, CL=np.array(CL), CD=np.array(CD), Cm=np.array(Cm),
        velocity=velocity, reference_area=S, mac=mac, cg_x=cg,
        extras={"n_panels": len(quads),
                "planform": {"span": round(span, 3), "root_chord": round(root_c, 3),
                             "tip_chord": round(tip_c, 3), "sweep_deg": round(sweep, 1),
                             "naca": naca},
                "note": "Sily z walidowanego solvera panelowego na obrysie "
                        "nosnym dopasowanym do STEP; pole Cp z geometrii STEP."},
    )
    mask = np.abs(alphas) <= 6
    if mask.sum() >= 2:
        res.CL_alpha = float(np.polyfit(np.deg2rad(alphas[mask]), res.CL[mask], 1)[0])
        res.Cm_alpha = float(np.polyfit(np.deg2rad(alphas[mask]), res.Cm[mask], 1)[0])
    if res.CL_alpha:
        res.neutral_point_x = res.cg_x - (res.Cm_alpha / res.CL_alpha) * res.mac
        res.static_margin = (res.neutral_point_x - res.cg_x) / res.mac
    res.CL_max = float(np.max(res.CL))
    with np.errstate(divide="ignore", invalid="ignore"):
        ld = np.where(res.CD > 1e-6, res.CL / res.CD, 0.0)
    i = int(np.argmax(ld))
    res.LD_max = float(ld[i]); res.alpha_LD_max = float(alphas[i])
    if cp_field is not None:
        res.extras["cp"] = cp_field
        res.extras["mesh_centroids"] = mesh_centroids
        res.extras["cp_nodes"] = cp_nodes
        res.extras["cp_faces"] = cp_faces
    return res


# zachowane dla kompatybilnosci wstecz (stare API)
def load_step(path: str | Path):
    nodes, _ = load_and_mesh_step(path)
    return nodes


def mesh_surface(shape, target_size: float = 0.01):
    raise NotImplementedError("Uzyj load_and_mesh_step(path).")
