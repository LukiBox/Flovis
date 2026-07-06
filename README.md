<div align="center">

# Flovis

### Aerodynamics of flying models — simple, visual, offline

Flovis helps you analyze airfoils and wings, but without wrestling with the math. Pick a layout and you get polars, stability data, a 3D pressure map, and a ready-made PDF report. The report includes tips written by a local AI so nothing leaves your machine. Flovis is written in Python 3.10+ with a PySide6 UI, runs 100% offline, speaks English and Polish, and ships under the MIT license.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/UI-PySide6%20(Qt6)-41CD52?logo=qt&logoColor=white)
![Offline](https://img.shields.io/badge/Runs-100%25%20offline-2563EB)
![i18n](https://img.shields.io/badge/UI-English%20%2F%20Polski-2563EB)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## Who is Flovis for?

For hobbyists, RC modelers, and amateur designers who want to know if their model will actually fly without an aerodynamics degree or XFoil/AVL knowledge. Professional tools like XFLR5, XFoil, and AVL are powerful, but they can be intimidating. Flovis keeps the math out of sight behind a clean, minimal interface and suggests sensible defaults. Almost everything you need is two or three clicks away.

Under the hood, it’s running the same numerical engines the pros use, the math is the same, only UI changes.

---

## Features

6 parametric layouts — low wing, high wing, twin boom, pusher, canard, flying wing. Edit live and see the top‑view planform.

Interactive airfoil editor — drag points with the mouse, insert/delete, undo/redo, cosine repaneling, smoothing, and live geometry checks.

2D airfoil polars — bundled XFoil with full Cp distribution, plus NeuralFoil as a fast fallback. Cl(α), Cl(Cd), Cl_max, α_stall.

3D solvers — VLM (AeroSandbox) with real airfoils and XFoil coupling, AVL for accurate mode (bundled), and an instant analytic estimator for quick checks.

STEP (.stp) analysis — load CAD geometry and Flovis shows it in 3D with a colored pressure map.

3D view — model body with pressure colors (blue = suction, red = stagnation), CG and neutral point; rotate and zoom.

PDF report — multiple pages with a red/yellow/green rating, polars, stability derivatives, Cp distribution, and the AI‑written interpretation.

Local AI (Ollama) — the qwen3:30b-a3b model explains results in plain language. Fully offline and private.

Bilingual UI — English by default; switch to Polish with one click (the choice is remembered).

.flovis project files — save the whole working state and come back later.

Everything runs locally. Nothing leaves your computer — not even the AI.

---

## Quick start

```powershell
# 1. Clone the repository
git clone https://github.com/<your-user>/Flovis.git
cd Flovis

# 2. Virtual environment on an ASCII path (important!)
python -m venv C:\Users\Public\flovis-venv
C:\Users\Public\flovis-venv\Scripts\Activate.ps1

# 3. Dependencies
pip install -r requirements.txt

# 4. Run
python -m flovis.app
```

### Enabling the AI (optional)

Install [Ollama](https://ollama.com), then:

```powershell
ollama pull qwen3:30b-a3b
ollama serve
```

Flovis detects available models automatically. You can also generate the report
without AI so that section is optional. The AI answers in the app's current language.

---

## Building the executable (.exe)

```powershell
pip install pyinstaller
pyinstaller flovis.spec --noconfirm
```

Produces a single-file `dist/Flovis.exe` with XFoil/AVL bundled.

---

## Architecture

```
flovis/
  app.py                    # entry point (QApplication, light theme, i18n)
  core/
    i18n.py                 # lightweight English/Polish translation
    airfoil/                # NACA generator (classic + modified), editor, XFoil/NeuralFoil
    geometry/               # 6 parametric aircraft templates
    solvers/                # VLM (AeroSandbox), AVL, analytic, 3D panel method
    report/                 # charts + PDF generator (ReportLab)
    ai/                     # Ollama client (written interpretation)
    project.py              # .flovis format (save/load)
  ui/
    main_window.py          # window, menu, theme, onboarding, language switch
    tabs/                   # Templates / Airfoil / Analysis / 3D Model / Report
    widgets/                # pyqtgraph editor, PyVista 3D view, charts
  resources/
    styles/flovis.qss       # light, minimalist theme
    bin/                    # XFoil 6.99, AVL 3.52 (Windows)
tests/                      # pytest
```

| Layer | Technology |
|---|---|
| UI | PySide6 (Qt6) + matplotlib + pyqtgraph |
| 3D view | PyVista / VTK |
| 2D aero | XFoil (subprocess) + NeuralFoil |
| 3D aero | AeroSandbox (VLM) + AVL |
| STEP | gmsh (OpenCASCADE kernel) + 3D panel method |
| Reports | matplotlib + ReportLab |
| AI | Ollama (`qwen3:30b-a3b`) |

---

## How it work

- **NACA airfoils** — classic and modified 4-digit generator (shiftable max
  thickness position, adjustable LE radius), e.g. `0011-0.825-35`.
- **VLM** builds geometry from real airfoils and couples with XFoil (strip theory),
  so the 3D polar has realistic drag and `CL_max`.
- **AVL** is the "accurate mode" — full stability derivatives and neutral point
  straight from the solver.
- **STEP analysis** fits a planform to your CAD geometry, computes the polar
  with lifting-line theory, and paints the validated panel-method pressure
  field onto the real shape.

---

## Engineering notes

- **STEP analysis** is qualitative by design: forces come from lifting-line
  theory on the planform fitted to your geometry, and the surface pressure
  field is the validated panel solution (rectangular wing, < ~3% vs VLM)
  mapped onto the CAD shape. Great for visualization and sanity checks; for
  quantitative numbers use VLM or AVL.
- The analytic estimator exists for responsiveness ("instant answer");
  trustworthy results come from VLM/AVL.

---

## 📜 License

Flovis code: **MIT** (see [LICENSE](LICENSE)).

---

</div>
