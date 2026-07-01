# Changelog

All notable changes to Flovis.

## [1.0.0] — 2026-07-01

First full release. All main paths work end-to-end.

### Added
- **Bilingual UI** — English by default, one-click switch to Polish (remembered
  across runs). The AI answers in the selected language.
- **Interactive airfoil editor** (pyqtgraph): drag points, insert/delete,
  undo/redo, snap to chord, cosine repaneling, live geometry validation.
- **2D airfoil polars** — XFoil (subprocess) with Cp distribution and a
  NeuralFoil fallback.
- **VLM solver** with real airfoils and VLM↔XFoil coupling (strip theory),
  full stability derivatives and neutral point.
- **AVL solver** — generates the `.avl` file, runs the binary, parses forces
  and stability derivatives.
- **3D panel method for STEP** (source-doublet, Kutta condition) — vectorized,
  with a bounded panel count and robust meshing (gmsh).
- **3D view** (PyVista) with a smooth, symmetric pressure distribution, CG and
  neutral point.
- **PDF report** — multi-page: R/Y/G rating, polars, stability derivatives,
  Cp distribution, AI interpretation, page numbers.
- **AI (Ollama)** — prompt presets, missing-model detection, full context.
- **`.flovis` project format** (save/load) + File menu + onboarding.
- Light, minimalist theme (forced regardless of the OS dark mode).
- 28 pytest tests, PyInstaller spec.

### Notes
- The STEP panel method is qualitative (low-order solver); for quantitative
  results prefer VLM/AVL.
