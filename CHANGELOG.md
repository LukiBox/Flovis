# Changelog

Wszystkie istotne zmiany w projekcie Flovis.

## [1.0.0] — 2026-07-01

Pierwsze pełne wydanie. Wszystkie główne ścieżki działają end-to-end.

### Dodane
- **Interaktywny edytor profili** (pyqtgraph): przeciąganie punktów, wstaw/usuń,
  undo/redo, snap do cięciwy, repanelizacja kosinusowa, walidacja geometrii.
- **Bieguny profilu 2D** — wrapper XFoil (subprocess) z rozkładem Cp oraz
  fallback NeuralFoil.
- **Solver VLM** z rzeczywistymi profilami i sprzężeniem VLM↔XFoil (teoria pasków),
  pełne pochodne stateczności, punkt neutralny.
- **Solver AVL** — generacja pliku `.avl`, uruchomienie binarki, parsowanie
  sił i pochodnych stateczności.
- **Metoda panelowa 3D dla STEP** (source-doublet, warunek Kutty) — wektoryzowana,
  z ograniczeniem liczby paneli i odpornym siatkowaniem (gmsh).
- **Widok 3D** (PyVista) z kolorowym, symetrycznym rozkładem ciśnień, CG i
  punktem neutralnym.
- **Raport PDF** — wielostronicowy: ocena R/Ż/Z, bieguny, pochodne stateczności,
  rozkład Cp, interpretacja AI, numeracja stron.
- **AI (Ollama)** — presety promptów, wykrywanie braku modelu, pełny kontekst.
- **Format projektu `.flovis`** (zapis/odczyt) + menu Plik + onboarding.
- Jasny, minimalistyczny motyw (wymuszany niezależnie od trybu ciemnego systemu).
- 28 testów pytest, spec PyInstaller.

### Uwagi
- Metoda panelowa STEP ma charakter poglądowy (solver niskiego rzędu); do
  wyników ilościowych zalecane VLM/AVL.
