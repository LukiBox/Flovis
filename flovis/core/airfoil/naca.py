"""
Generatory profili NACA dla Flovis.

Obsluga:
  * NACA 4-cyfrowy klasyczny (np. 2412, 0012)
  * NACA 4-cyfrowy ZMODYFIKOWANY (np. 0012-63), z dwoma dodatkowymi
    parametrami:
        - wspolczynnik promienia natarcia (LE radius factor),
          1.0 = jak w klasycznym 4-cyfrowym,
        - polozenie maksymalnej grubosci (x/c).

Metoda dla profilu zmodyfikowanego jest klasyczna (Stack & von Doenhoff,
NACA Report 492 / Ladson): rozdzial rozkladu grubosci na czesc przednia
i tylna z warunkami ciaglosci wartosci, nachylenia i krzywizny w punkcie
maksymalnej grubosci.

Rozklad grubosci (polowa grubosci, y_t):
  przod  0 <= x <= m :  y_t = 5t (a0*sqrt(x) + a1*x + a2*x^2 + a3*x^3)
  tyl    m <= x <= 1 :  y_t = 5t (d0 + d1*X + d2*X^2 + d3*X^3),  X = 1 - x

gdzie a0 wynika z promienia natarcia, a pozostale wspolczynniki z warunkow
domkniecia. Dla LE factor = 1.0 i m = 0.3 odtwarza klasyczny profil 4-cyfrowy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np


# Tabela nachylenia krawedzi splywu d1 w funkcji polozenia max. grubosci
# (NACA, wartosci klasyczne). Interpolacja liniowa, klampowanie na brzegach.
_D1_TABLE_X = np.array([0.2, 0.3, 0.4, 0.5, 0.6])
_D1_TABLE_D1 = np.array([0.200, 0.234, 0.315, 0.465, 0.700])


def _d1_from_position(m: float) -> float:
    return float(np.interp(m, _D1_TABLE_X, _D1_TABLE_D1))


def _cosine_spacing(n: int) -> np.ndarray:
    """Zageszczenie punktow przy krawedziach natarcia i splywu."""
    beta = np.linspace(0.0, np.pi, n)
    return 0.5 * (1.0 - np.cos(beta))


def _camber_line(x: np.ndarray, m: float, p: float):
    """Klasyczna linia szkieletowa 4-cyfrowa. Zwraca (yc, dyc/dx)."""
    yc = np.zeros_like(x)
    dyc = np.zeros_like(x)
    if m == 0.0 or p == 0.0:
        return yc, dyc
    front = x < p
    back = ~front
    yc[front] = m / p**2 * (2 * p * x[front] - x[front] ** 2)
    dyc[front] = 2 * m / p**2 * (p - x[front])
    yc[back] = m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x[back] - x[back] ** 2)
    dyc[back] = 2 * m / (1 - p) ** 2 * (p - x[back])
    return yc, dyc


def _thickness_standard(x: np.ndarray, t: float, sharp_te: bool) -> np.ndarray:
    """Klasyczny rozklad grubosci 4-cyfrowy (polowa grubosci)."""
    a4 = -0.1036 if sharp_te else -0.1015
    return 5 * t * (
        0.2969 * np.sqrt(x)
        - 0.1260 * x
        - 0.3516 * x**2
        + 0.2843 * x**3
        + a4 * x**4
    )


def _thickness_modified(x: np.ndarray, t: float, m: float, le_factor: float,
                        sharp_te: bool) -> np.ndarray:
    """
    Zmodyfikowany rozklad grubosci 4-cyfrowy.

    m         - polozenie maksymalnej grubosci (x/c), np. 0.35
    le_factor - mnoznik promienia natarcia (1.0 = klasyczny)
    """
    # a0 z promienia natarcia: r_LE = 1.1019*t^2*le_factor^2  =>  a0 = 0.296904*le_factor
    a0 = 0.296904 * le_factor

    # --- czesc tylna: domkniecie z warunkow g(m)=0.1, g'(m)=0 ---
    d0 = 0.0 if sharp_te else 0.002
    d1 = _d1_from_position(m)
    Xm = 1.0 - m
    # g(Xm) = d0 + d1*Xm + d2*Xm^2 + d3*Xm^3 = 0.1
    # dyt/dx = 0  ->  d1 + 2 d2 Xm + 3 d3 Xm^2 = 0
    A_aft = np.array([[Xm**2, Xm**3],
                      [2 * Xm, 3 * Xm**2]])
    b_aft = np.array([0.1 - d0 - d1 * Xm, -d1])
    d2, d3 = np.linalg.solve(A_aft, b_aft)

    # krzywizna czesci tylnej w punkcie m:  d^2g/dx^2 = 2 d2 + 6 d3 Xm
    gpp_m = 2 * d2 + 6 * d3 * Xm

    # --- czesc przednia: a1,a2,a3 z f(m)=0.1, f'(m)=0, f''(m)=gpp_m ---
    sm = np.sqrt(m)
    # f  = a0 sqrt x + a1 x + a2 x^2 + a3 x^3
    # f' = a0/(2 sqrt x) + a1 + 2 a2 x + 3 a3 x^2
    # f''= -a0/(4 x^1.5) + 2 a2 + 6 a3 x
    A_fwd = np.array([
        [m,       m**2,      m**3],         # f(m)
        [1.0,     2 * m,     3 * m**2],     # f'(m)
        [0.0,     2.0,       6 * m],        # f''(m)
    ])
    b_fwd = np.array([
        0.1 - a0 * sm,
        -a0 / (2 * sm),
        gpp_m + a0 / (4 * m**1.5),
    ])
    a1, a2, a3 = np.linalg.solve(A_fwd, b_fwd)

    yt = np.empty_like(x)
    front = x <= m
    back = ~front
    xf = x[front]
    yt[front] = 5 * t * (a0 * np.sqrt(xf) + a1 * xf + a2 * xf**2 + a3 * xf**3)
    Xb = 1.0 - x[back]
    yt[back] = 5 * t * (d0 + d1 * Xb + d2 * Xb**2 + d3 * Xb**3)
    return yt


@dataclass
class NacaSpec:
    """Znormalizowana specyfikacja profilu NACA."""
    max_camber: float = 0.0       # m, ulamek (0.02 = 2%)
    camber_pos: float = 0.0       # p, ulamek (0.4 = 40%)
    thickness: float = 0.12       # t, ulamek (0.12 = 12%)
    le_factor: float = 1.0        # mnoznik promienia natarcia (modyfikacja)
    max_thickness_pos: float = 0.30  # m_t, ulamek; 0.30 = klasyczny
    modified: bool = False

    @property
    def name(self) -> str:
        base = f"NACA {int(round(self.max_camber*100))}{int(round(self.camber_pos*10))}{int(round(self.thickness*100)):02d}"
        if self.modified:
            return f"{base}-{self.le_factor:g}-{int(round(self.max_thickness_pos*100))}"
        return base


def parse_naca(text: str) -> NacaSpec:
    """
    Parsuje notacje NACA.

    Akceptuje:
      "2412"              -> klasyczny 4-cyfrowy
      "0012"              -> symetryczny klasyczny
      "0012-6-3"          -> zmodyfikowany: LE index 6, max grubosc 30%
      "00011-0.825-35"    -> rozszerzona notacja Flovis:
                             cyfry profilu, wspolczynnik LE, pozycja max grubosci [%]

    W notacji rozszerzonej pierwszy czlon to cyfry camber+grubosc:
      ostatnie 2 cyfry = grubosc [%], poprzedzajace = camber (m, p).
    """
    text = text.strip().upper().replace("NACA", "").strip()
    parts = [p for p in re.split(r"[-\s]+", text) if p]
    if not parts:
        raise ValueError("Pusta specyfikacja NACA")

    digits = parts[0]
    if len(digits) < 4:
        digits = digits.zfill(4)
    # ostatnie 2 cyfry: grubosc; reszta: camber
    thickness = int(digits[-2:]) / 100.0
    camber_digits = digits[:-2]
    if len(camber_digits) >= 2:
        m = int(camber_digits[0]) / 100.0
        p = int(camber_digits[1]) / 10.0
    elif len(camber_digits) == 1:
        m = int(camber_digits[0]) / 100.0
        p = 0.0
    else:
        m = p = 0.0

    spec = NacaSpec(max_camber=m, camber_pos=p, thickness=thickness)

    if len(parts) >= 3:
        spec.modified = True
        spec.le_factor = float(parts[1])
        pos = float(parts[2])
        spec.max_thickness_pos = pos / 100.0 if pos > 1.0 else pos
    elif len(parts) == 2:
        # forma klasyczna zmodyfikowana "IT" jako jeden czlon, np. "63"
        spec.modified = True
        it = parts[1]
        spec.le_factor = int(it[0]) / 6.0          # indeks LE: 6 = normalny
        spec.max_thickness_pos = int(it[1]) / 10.0
    return spec


def generate(spec: NacaSpec, n_points: int = 160, sharp_te: bool = False):
    """
    Generuje wspolrzedne profilu w kolejnosci Seliga:
    od krawedzi splywu gora -> natarcie -> krawedz splywu dol.

    Zwraca (x, y) jako tablice numpy.
    """
    xc = _cosine_spacing(n_points // 2 + 1)
    yc, dyc = _camber_line(xc, spec.max_camber, spec.camber_pos)

    if spec.modified:
        yt = _thickness_modified(xc, spec.thickness, spec.max_thickness_pos,
                                 spec.le_factor, sharp_te)
    else:
        yt = _thickness_standard(xc, spec.thickness, sharp_te)

    theta = np.arctan(dyc)
    xu = xc - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = xc + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)

    # Selig: gora od TE do LE, potem dol od LE do TE
    x = np.concatenate([xu[::-1], xl[1:]])
    y = np.concatenate([yu[::-1], yl[1:]])
    return x, y


def from_string(text: str, n_points: int = 160, sharp_te: bool = False):
    """Skrot: tekst NACA -> (spec, x, y)."""
    spec = parse_naca(text)
    x, y = generate(spec, n_points, sharp_te)
    return spec, x, y
