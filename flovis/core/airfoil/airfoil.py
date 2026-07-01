"""
Klasa Airfoil - reprezentacja i operacje na profilu lotniczym.

Format wewnetrzny: wspolrzedne w kolejnosci Seliga (gora TE->LE, dol LE->TE),
ciecziwa znormalizowana 0..1. Operacje: wczytanie/zapis .dat (Selig),
wygladzanie, skalowanie grubosci, pomiar grubosci i strzalki ugiecia,
przesuwanie pojedynczych punktow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.interpolate import splev, splprep

from . import naca


@dataclass
class Airfoil:
    x: np.ndarray
    y: np.ndarray
    name: str = "profil"
    meta: dict = field(default_factory=dict)

    # ----- konstruktory -----
    @classmethod
    def from_naca(cls, text: str, n_points: int = 160, sharp_te: bool = False) -> "Airfoil":
        spec, x, y = naca.from_string(text, n_points, sharp_te)
        return cls(x=x, y=y, name=spec.name, meta={"naca": spec.__dict__})

    @classmethod
    def from_spec(cls, text: str, n_points: int = 160) -> "Airfoil":
        """Tworzy profil z opisu z geometrii: notacja NACA albo sciezka do .dat.

        Uzywane przez solvery (VLM/AVL) do zamiany Surface.airfoil_* na ksztalt.
        """
        s = (text or "").strip()
        p = Path(s)
        if s.lower().endswith((".dat", ".txt")) and p.exists():
            return cls.from_dat(p)
        return cls.from_naca(s, n_points=n_points)

    @classmethod
    def from_dat(cls, path: str | Path) -> "Airfoil":
        path = Path(path)
        lines = path.read_text().splitlines()
        name = path.stem
        coords = []
        for i, ln in enumerate(lines):
            ln = ln.strip()
            if not ln:
                continue
            parts = ln.replace(",", " ").split()
            try:
                xv, yv = float(parts[0]), float(parts[1])
            except (ValueError, IndexError):
                if i == 0:
                    name = ln  # naglowek z nazwa
                continue
            # pomijamy naglowek typu Lednicer (liczby punktow > 1)
            if abs(xv) > 1.5 or abs(yv) > 1.5:
                continue
            coords.append((xv, yv))
        arr = np.array(coords)
        return cls(x=arr[:, 0], y=arr[:, 1], name=name)

    # ----- zapis -----
    def to_dat(self, path: str | Path) -> Path:
        """Zapis w standardowym formacie Seliga (.dat)."""
        path = Path(path)
        with path.open("w") as f:
            f.write(f"{self.name}\n")
            for xv, yv in zip(self.x, self.y):
                f.write(f"{xv:10.6f} {yv:10.6f}\n")
        return path

    # ----- pomiary -----
    def _split_surfaces(self):
        """Dzieli kontur na gorna i dolna powierzchnie wzgledem LE (min x)."""
        le = int(np.argmin(self.x))
        xu, yu = self.x[: le + 1][::-1], self.y[: le + 1][::-1]  # LE->TE
        xl, yl = self.x[le:], self.y[le:]                         # LE->TE
        return (xu, yu), (xl, yl)

    def max_thickness(self) -> tuple[float, float]:
        """Zwraca (grubosc/c, polozenie x/c)."""
        (xu, yu), (xl, yl) = self._split_surfaces()
        xs = np.linspace(0.0, 1.0, 200)
        yu_i = np.interp(xs, xu, yu)
        yl_i = np.interp(xs, xl, yl)
        t = yu_i - yl_i
        i = int(np.argmax(t))
        return float(t[i]), float(xs[i])

    def max_camber(self) -> tuple[float, float]:
        """Zwraca (strzalka ugiecia/c, polozenie x/c)."""
        (xu, yu), (xl, yl) = self._split_surfaces()
        xs = np.linspace(0.0, 1.0, 200)
        camber = 0.5 * (np.interp(xs, xu, yu) + np.interp(xs, xl, yl))
        i = int(np.argmax(np.abs(camber)))
        return float(camber[i]), float(xs[i])

    # ----- operacje -----
    def scale_thickness(self, factor: float) -> "Airfoil":
        """Skaluje grubosc wzgledem linii szkieletowej, zachowujac camber."""
        (xu, yu), (xl, yl) = self._split_surfaces()
        xs = np.unique(np.concatenate([xu, xl]))
        yu_i = np.interp(xs, xu, yu)
        yl_i = np.interp(xs, xl, yl)
        camber = 0.5 * (yu_i + yl_i)
        half = 0.5 * (yu_i - yl_i) * factor
        nyu = camber + half
        nyl = camber - half
        x = np.concatenate([xs[::-1], xs[1:]])
        y = np.concatenate([nyu[::-1], nyl[1:]])
        return Airfoil(x=x, y=y, name=f"{self.name}_t{factor:g}", meta=dict(self.meta))

    def smooth(self, smoothing: float = 1e-4, n_points: int | None = None) -> "Airfoil":
        """Wygladza kontur splajnem parametrycznym (zachowuje LE/TE)."""
        n_points = n_points or len(self.x)
        pts = np.vstack([self.x, self.y])
        tck, _ = splprep(pts, s=smoothing, per=False)
        u = np.linspace(0.0, 1.0, n_points)
        xs, ys = splev(u, tck)
        return Airfoil(x=np.asarray(xs), y=np.asarray(ys),
                       name=f"{self.name}_smooth", meta=dict(self.meta))

    def move_point(self, index: int, dx: float, dy: float) -> "Airfoil":
        """Przesuwa pojedynczy punkt (edycja reczna)."""
        x = self.x.copy()
        y = self.y.copy()
        x[index] += dx
        y[index] += dy
        return Airfoil(x=x, y=y, name=self.name, meta=dict(self.meta))

    def set_point(self, index: int, x: float, y: float) -> "Airfoil":
        """Ustawia bezwzgledne polozenie punktu (drag w edytorze)."""
        nx = self.x.copy()
        ny = self.y.copy()
        nx[index] = x
        ny[index] = y
        return Airfoil(x=nx, y=ny, name=self.name, meta=dict(self.meta))

    def insert_point(self, index: int) -> "Airfoil":
        """Wstawia nowy punkt w polowie odcinka miedzy index a index+1."""
        i2 = min(index + 1, len(self.x) - 1)
        nx = 0.5 * (self.x[index] + self.x[i2])
        ny = 0.5 * (self.y[index] + self.y[i2])
        x = np.insert(self.x, index + 1, nx)
        y = np.insert(self.y, index + 1, ny)
        return Airfoil(x=x, y=y, name=self.name, meta=dict(self.meta))

    def delete_point(self, index: int) -> "Airfoil":
        """Usuwa punkt o danym indeksie."""
        x = np.delete(self.x, index)
        y = np.delete(self.y, index)
        return Airfoil(x=x, y=y, name=self.name, meta=dict(self.meta))

    def nearest_point(self, x: float, y: float, aspect: float = 1.0) -> int:
        """Indeks najblizszego punktu (do trafiania myszka w edytorze).

        aspect skaluje os Y, gdy wykres ma inne proporcje niz 1:1.
        """
        d2 = (self.x - x) ** 2 + ((self.y - y) * aspect) ** 2
        return int(np.argmin(d2))

    def repanel(self, n_points: int = 160) -> "Airfoil":
        """Repanelizacja kosinusowa: zageszcza punkty przy LE i TE.

        Interpoluje gorna i dolna powierzchnie na nowej siatce kosinusowej x,
        zachowujac ksztalt, ale ujednolicajac rozklad punktow.
        """
        (xu, yu), (xl, yl) = self._split_surfaces()
        x0 = float(min(xu[0], xl[0]))
        x1 = float(max(xu[-1], xl[-1]))
        n_side = max(n_points // 2 + 1, 3)
        beta = np.linspace(0.0, np.pi, n_side)
        xc = x0 + (x1 - x0) * 0.5 * (1.0 - np.cos(beta))
        yu_i = np.interp(xc, xu, yu)
        yl_i = np.interp(xc, xl, yl)
        # Selig: gora TE->LE, potem dol LE->TE
        x = np.concatenate([xc[::-1], xc[1:]])
        y = np.concatenate([yu_i[::-1], yl_i[1:]])
        return Airfoil(x=x, y=y, name=self.name, meta=dict(self.meta))

    # ----- walidacja geometrii -----
    def validate(self) -> list[str]:
        """Zwraca liste problemow geometrycznych (pusta = profil poprawny)."""
        issues: list[str] = []
        if len(self.x) < 5:
            issues.append("Zbyt malo punktow konturu.")
            return issues
        (xu, yu), (xl, yl) = self._split_surfaces()
        for nm, xs in (("gorna", xu), ("dolna", xl)):
            if np.any(np.diff(xs) < -1e-9):
                issues.append(
                    f"Powierzchnia {nm}: wspolrzedna x nie jest monotoniczna "
                    "(zawiniecie/przeskok konturu).")
        # samoprzeciecie: grubosc (gora - dol) nie moze byc ujemna w srodku
        lo = max(float(xu.min()), float(xl.min()))
        hi = min(float(xu.max()), float(xl.max()))
        if hi > lo:
            xs = np.linspace(lo, hi, 200)
            t = np.interp(xs, xu, yu) - np.interp(xs, xl, yl)
            if np.any(t < -1e-6):
                issues.append(
                    "Powierzchnia gorna schodzi ponizej dolnej - samoprzeciecie "
                    "konturu.")
        return issues

    def is_valid(self) -> bool:
        return not self.validate()

    def normalize(self) -> "Airfoil":
        """Normalizuje ciecziwe do 0..1 (LE w 0, TE w 1)."""
        xmin, xmax = self.x.min(), self.x.max()
        chord = xmax - xmin
        if chord == 0:
            return self
        x = (self.x - xmin) / chord
        y = self.y / chord
        return Airfoil(x=x, y=y, name=self.name, meta=dict(self.meta))

    def summary(self) -> dict:
        t, xt = self.max_thickness()
        c, xc = self.max_camber()
        return {
            "name": self.name,
            "n_points": int(len(self.x)),
            "max_thickness": round(t, 5),
            "max_thickness_pos": round(xt, 4),
            "max_camber": round(c, 5),
            "max_camber_pos": round(xc, 4),
        }
