# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec dla Flovis - pojedynczy plik wykonywalny Windows.

Buduj:  pyinstaller flovis.spec
Wynik:  dist/Flovis.exe

Dolacza binaria XFoil/AVL (resources/bin), motyw QSS oraz dane ciezkich
bibliotek (aerosandbox, casadi, vtk, pyvista, gmsh, neuralfoil).
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = []
binaries = []
hiddenimports = []

# ciezkie pakiety z danymi / dynamicznym importem
for pkg in ("aerosandbox", "casadi", "neuralfoil", "pyvista", "pyvistaqt",
            "vtkmodules", "gmsh"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass

# zasoby Flovis: binarki XFoil/AVL + motyw QSS
datas += [
    ("flovis/resources/bin/xfoil.exe", "resources/bin"),
    ("flovis/resources/bin/avl.exe", "resources/bin"),
    ("flovis/resources/styles/flovis.qss", "resources/styles"),
]

hiddenimports += ["ollama", "reportlab", "scipy.interpolate", "pyqtgraph"]


a = Analysis(
    ["flovis/app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PyQt6"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Flovis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # aplikacja okienkowa (bez konsoli)
    icon=None,
)
