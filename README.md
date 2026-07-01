<div align="center">

# ✈️ Flovis

### Aerodynamics of flying models — simple, visual, offline

**Analyze airfoils and wings like in XFLR5, but without wrestling with the math.**
Flovis guides you by the hand: pick a layout, click "analyze", and you get polars,
stability, a colorful 3D pressure map and a ready-made PDF report — complete with a
plain-language write-up produced by a **local** AI.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/UI-PySide6%20(Qt6)-41CD52?logo=qt&logoColor=white)
![Offline](https://img.shields.io/badge/Runs-100%25%20offline-2563EB)
![i18n](https://img.shields.io/badge/UI-English%20%2F%20Polski-2563EB)
![License](https://img.shields.io/badge/License-MIT-green)
![Tests](https://img.shields.io/badge/tests-28%20passed-success)

</div>

---

## 🎯 Who is Flovis for?

For **hobbyists, RC modelers and amateur designers** who want to know
*whether their model will actually fly* — without an aerodynamics degree and
without fighting raw XFoil or AVL on the command line.

> Professional tools (XFLR5, XFoil, AVL) are powerful but intimidating.
> Flovis hides the math behind a clean, minimalist interface and
> **suggests safe defaults**. Every key action is 2–3 clicks away.

Under the hood, though, it runs **real numerical engines** — the same ones the
pros use.

---

## ✨ Features

| | Feature |
|---|---|
| 🛩️ | **6 parametric layouts** — low wing, high wing, twin boom, pusher, canard, flying wing. Edit live, see the top-view planform. |
| ✏️ | **Interactive airfoil editor** — drag points with the mouse, insert/delete, undo/redo, cosine repaneling, smoothing, live geometry validation. |
| 📈 | **2D airfoil polars** — bundled **XFoil** with full `Cp` distribution, plus **NeuralFoil** as a lightning-fast fallback. Cl(α), Cl(Cd), Cl_max, α_stall. |
| 🌬️ | **3D solvers** — **VLM** (AeroSandbox) with real airfoils and XFoil coupling, **AVL** (accurate mode, bundled), and an instant analytic estimator. |
| 🧊 | **STEP (.stp) analysis** — load CAD geometry and Flovis shows it in 3D with a **colored pressure distribution**. |
| 🎨 | **3D view** — model body with a pressure map (blue = suction, red = stagnation), CG and neutral point, rotate/zoom. |
| 📄 | **PDF report** — multi-page: red/yellow/green rating, polars, stability derivatives, Cp distribution and an **AI written interpretation**. |
| 🤖 | **Local AI (Ollama)** — the `qwen3:30b-a3b` model explains the results in plain language. Fully offline and private. |
| 🌍 | **Bilingual UI** — English by default, one click to switch to Polish (and back). Remembered across runs. |
| 💾 | **`.flovis` project format** — save the whole working state (model, airfoil, settings, results) and come back later. |

> 🔒 **Everything runs offline.** Nothing leaves your machine — even the AI runs locally.

---

## 🖼️ Screenshots

> 📸 Drop your screenshots into `docs/screenshots/` (e.g. `templates.png`,
> `pressure3d.png`) and uncomment the table below to show them here.

<!--
| Templates & geometry | 3D pressure distribution |
|---|---|
| ![Templates](docs/screenshots/templates.png) | ![Pressure 3D](docs/screenshots/pressure3d.png) |
-->

---

## 🚀 Quick start

> ⚠️ **Important (Windows with non-ASCII characters in the username, e.g. `Łukasz`):**
> the **casadi** library (AeroSandbox's engine) cannot load its plugins from a path
> containing such characters. So the **virtual environment must live on an ASCII
> path**, e.g. `C:\Users\Public\flovis-venv`. The project itself can be anywhere.

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

### 🤖 Enabling the AI (optional)

Install [Ollama](https://ollama.com), then:

```powershell
ollama pull qwen3:30b-a3b
ollama serve
```

Flovis detects available models automatically. **You can also generate the report
without AI** — that section is optional. The AI answers in the app's current language.

---

## 🧪 Tests

```powershell
python -m pytest tests/ -q
```

**28 tests**: airfoil engine and editor, solvers (VLM vs analytic vs AVL), XFoil
wrapper + NeuralFoil, **panel method vs VLM (< 10%)**, project I/O, PDF generation.

---

## 📦 Building the executable (.exe)

```powershell
pip install pyinstaller
pyinstaller flovis.spec --noconfirm
```

Produces a single-file `dist/Flovis.exe` with XFoil/AVL bundled.

> Note: the one-file exe unpacks to `%TEMP%`. With a non-ASCII username, run the
> `.exe` from an ASCII path (e.g. `C:\Flovis\`).

---

## 🏗️ Architecture

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

## 🔬 How it works (in short)

- **NACA airfoils** — classic and **modified 4-digit** generator (shiftable max
  thickness position, adjustable LE radius), e.g. `0011-0.825-35`.
- **VLM** builds geometry from real airfoils and couples with XFoil (strip theory),
  so the 3D polar has realistic drag and `CL_max`.
- **AVL** is the "accurate mode" — full stability derivatives and neutral point
  straight from the solver.
- **STEP panel method** (source-doublet, Kutta condition) gives a qualitative
  pressure distribution on any CAD geometry.

---

## ⚠️ Engineering notes (honest)

- The **STEP panel method** is a **low-order, qualitative** solver — great for
  visualizing the pressure distribution and quick sanity checks, but for
  quantitative numbers use **VLM or AVL**. For arbitrary geometry it is calibrated
  to VLM on a rectangular wing (agreement < ~3%).
- The **analytic estimator** exists for responsiveness ("instant answer");
  trustworthy results come from VLM/AVL.

---

## 🗺️ Status

All main paths work end-to-end: **template → analysis → AI → PDF** and
**STEP import → 3D pressure distribution**. See [CHANGELOG.md](CHANGELOG.md).

---

## 📜 License

Flovis code: **MIT** (see [LICENSE](LICENSE)).
Bundled binaries and libraries keep their own licenses — details in
[THIRD_PARTY.md](THIRD_PARTY.md) (XFoil and AVL are Mark Drela's GPL software).

---

<div align="center">

**Built for those who love to fly what they designed themselves. 🛩️**

</div>
