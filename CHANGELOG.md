# Changelog

All notable changes to Flovis.

## [1.1.0] — 2026-07-02

### Fixed
- **STEP pressure field completely rebuilt.** The previous direct panel solve
  on the raw, unstructured STEP mesh was numerically fragile and could produce
  a saturated, uniformly-blue Cp field. The field is now the validated
  structured-wing solution **mapped onto the real CAD geometry** (per
  connected component: chord fraction + span station + upper/lower blend) —
  smooth, symmetric and correct on single wings and full aircraft alike.
- **Swept/tapered template surfaces** (e.g. the flying wing) now show a proper
  pressure gradient: the solve runs on the stable rectangular equivalent and
  the field is painted onto the displayed swept mesh (same grid topology).
- **STEP forces** switched to lifting-line theory on the fitted planform —
  trustworthy at any aspect ratio (the low-order panel solver is only
  calibrated at NACA 0012 / AR 6 and drifted badly outside that point).
- Guarded planform extraction against degenerate geometry (empty span bins).
- The 3D (VTK) view is closed safely before a language-switch UI rebuild.

### Changed
- STEP meshes are denser (~3000 panels) for smoother visuals — and analysis is
  *faster*, because no O(N²) solve runs on the STEP mesh anymore.
- Entire source code (docstrings and comments) translated to English.
- Removed dead code (unused mica backend, unstructured velocity
  reconstruction, trailing-edge detection on arbitrary meshes).

### Added
- STEP regression tests (`tests/test_step.py`): generate a real STEP wing and
  assert the Cp field is finite, non-saturated, has both suction and
  stagnation, and is spanwise-symmetric. 31 tests total.

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
