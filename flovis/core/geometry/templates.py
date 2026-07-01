"""
Parametryczne szablony samolotow dla Flovis.

Kazdy szablon to zestaw parametrow geometrycznych z rozsadnymi wartosciami
domyslnymi. Na ich podstawie budowany jest uproszczony model obliczeniowy
(plaszczyzny nosne dla VLM). Szablon jest niezalezny od solvera - solver
(vlm.py) przyjmuje obiekt AircraftModel.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum


class Layout(str, Enum):
    LOW_WING = "Low wing (classic)"
    HIGH_WING = "High wing"
    TWIN_BOOM = "Twin boom"
    PUSHER = "Pusher"
    FLYING_WING = "Flying wing"
    CANARD = "Canard"


@dataclass
class Surface:
    """Pojedyncza plaszczyzna nosna (skrzydlo / usterzenie)."""
    name: str
    span: float            # rozpietosc [m] (pelna)
    root_chord: float      # cieciwa przy kadlubie [m]
    tip_chord: float       # cieciwa na koncu [m]
    sweep_deg: float = 0.0    # skos krawedzi natarcia [deg]
    dihedral_deg: float = 0.0
    incidence_deg: float = 0.0
    x_le: float = 0.0      # pozycja krawedzi natarcia nasady wzdluz X [m]
    z_pos: float = 0.0     # pozycja pionowa [m]
    airfoil_root: str = "NACA 2412"
    airfoil_tip: str = "NACA 2412"
    is_vertical: bool = False

    @property
    def area(self) -> float:
        return 0.5 * (self.root_chord + self.tip_chord) * self.span

    @property
    def mac(self) -> float:
        cr, ct = self.root_chord, self.tip_chord
        if cr + ct == 0:
            return 0.0
        taper = ct / cr
        return (2.0 / 3.0) * cr * (1 + taper + taper**2) / (1 + taper)

    @classmethod
    def from_dict(cls, d: dict) -> "Surface":
        fields = {k: d[k] for k in d if k in cls.__dataclass_fields__}
        return cls(**fields)


@dataclass
class AircraftModel:
    name: str
    layout: Layout
    surfaces: list[Surface] = field(default_factory=list)
    fuselage_length: float = 1.0
    fuselage_diam: float = 0.12
    mass_kg: float = 2.0
    cg_x: float = 0.25        # polozenie srodka ciezkosci wzdluz X [m]

    @property
    def wing(self) -> Surface | None:
        for s in self.surfaces:
            if s.name.lower().startswith("wing") and not s.is_vertical:
                return s
        return self.surfaces[0] if self.surfaces else None

    @property
    def reference_area(self) -> float:
        w = self.wing
        return w.area if w else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["layout"] = self.layout.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AircraftModel":
        layout = d.get("layout", Layout.LOW_WING.value)
        try:
            layout = Layout(layout)
        except ValueError:
            layout = Layout.LOW_WING
        surfaces = [Surface.from_dict(s) for s in d.get("surfaces", [])]
        return cls(
            name=d.get("name", "model"), layout=layout, surfaces=surfaces,
            fuselage_length=d.get("fuselage_length", 1.0),
            fuselage_diam=d.get("fuselage_diam", 0.12),
            mass_kg=d.get("mass_kg", 2.0), cg_x=d.get("cg_x", 0.25),
        )


# ---------- biblioteka szablonow ----------

def _classic(layout: Layout, z_wing: float) -> AircraftModel:
    wing = Surface("Wing", span=1.5, root_chord=0.25, tip_chord=0.18,
                   sweep_deg=2, dihedral_deg=4, x_le=0.30, z_pos=z_wing,
                   airfoil_root="NACA 2412", airfoil_tip="NACA 2410")
    htail = Surface("Horizontal tail", span=0.5, root_chord=0.14,
                    tip_chord=0.10, x_le=0.95, z_pos=z_wing,
                    airfoil_root="NACA 0010", airfoil_tip="NACA 0010")
    vtail = Surface("Vertical tail", span=0.22, root_chord=0.16,
                    tip_chord=0.10, x_le=0.95, is_vertical=True,
                    airfoil_root="NACA 0010", airfoil_tip="NACA 0010")
    return AircraftModel(
        name=layout.value, layout=layout,
        surfaces=[wing, htail, vtail],
        fuselage_length=1.15, fuselage_diam=0.12,
        mass_kg=2.0, cg_x=0.36,
    )


def make_template(layout) -> AircraftModel:
    """Zwraca gotowy model z domyslnymi parametrami dla danego ukladu.

    Przyjmuje Layout albo jego wartosc tekstowa (Qt splasza Layout(str,Enum)
    do zwyklego stringa w userData combo).
    """
    if not isinstance(layout, Layout):
        layout = Layout(layout)
    if layout == Layout.LOW_WING:
        return _classic(layout, z_wing=-0.04)
    if layout == Layout.HIGH_WING:
        return _classic(layout, z_wing=0.05)
    if layout == Layout.TWIN_BOOM:
        m = _classic(layout, z_wing=0.0)
        m.surfaces[1].x_le = 0.85   # usterzenia na belkach
        m.surfaces[2].x_le = 0.85
        return m
    if layout == Layout.PUSHER:
        m = _classic(layout, z_wing=0.0)
        m.fuselage_length = 1.0
        return m
    if layout == Layout.CANARD:
        wing = Surface("Wing", span=1.5, root_chord=0.26, tip_chord=0.18,
                       sweep_deg=4, dihedral_deg=3, x_le=0.55, z_pos=0.0)
        canard = Surface("Canard", span=0.6, root_chord=0.14, tip_chord=0.10,
                         x_le=0.10, z_pos=0.0,
                         airfoil_root="NACA 0012", airfoil_tip="NACA 0012")
        vtail = Surface("Vertical tail", span=0.22, root_chord=0.16,
                        tip_chord=0.10, x_le=0.95, is_vertical=True)
        return AircraftModel(layout.value, layout, [wing, canard, vtail],
                             fuselage_length=1.1, mass_kg=2.2, cg_x=0.58)
    if layout == Layout.FLYING_WING:
        wing = Surface("Wing", span=1.6, root_chord=0.35, tip_chord=0.12,
                       sweep_deg=22, dihedral_deg=2, x_le=0.0, z_pos=0.0,
                       airfoil_root="NACA 0012-1.0-30",
                       airfoil_tip="NACA 0010-1.0-30")
        return AircraftModel(layout.value, layout, [wing],
                             fuselage_length=0.35, fuselage_diam=0.08,
                             mass_kg=1.4, cg_x=0.16)
    raise ValueError(f"Unknown layout: {layout}")


ALL_TEMPLATES = list(Layout)
