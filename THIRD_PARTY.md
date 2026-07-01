# Licencje zależności i dołączonych binariów

Kod źródłowy Flovis jest na licencji **MIT** (patrz `LICENSE`). Poniższe
komponenty stron trzecich zachowują swoje własne licencje.

## Dołączone binaria (`flovis/resources/bin/`)

| Program | Wersja | Autor | Licencja |
|---|---|---|---|
| **XFoil** | 6.99 | Mark Drela, Harold Youngren (MIT) | **GPL** |
| **AVL** | 3.52 | Mark Drela, Harold Youngren (MIT) | **GPL** |

XFoil i AVL to darmowe, otwarte oprogramowanie rozpowszechniane na licencji GNU
GPL. Binaria dołączono dla wygody użytkownika (aby aplikacja działała „od ręki").
Są to niezmodyfikowane pliki wykonawcze pobrane ze stron autorów:

- XFoil: https://web.mit.edu/drela/Public/web/xfoil/
- AVL: https://web.mit.edu/drela/Public/web/avl/

Dołączenie tych binariów obok kodu MIT jest formą **agregacji** — każdy komponent
podlega swojej licencji. Jeśli redystrybuujesz Flovis, respektuj warunki GPL dla
XFoil/AVL. Możesz też usunąć binaria z `flovis/resources/bin/` — aplikacja
wskaże, że są niedostępne, i użyje NeuralFoil (2D) oraz VLM (3D).

## Kluczowe biblioteki Pythona

| Biblioteka | Licencja | Zastosowanie |
|---|---|---|
| PySide6 (Qt for Python) | LGPL v3 | interfejs graficzny |
| AeroSandbox | MIT | solver VLM, NeuralFoil |
| NeuralFoil | MIT | szybka predykcja biegunów 2D |
| gmsh | GPL | siatkowanie geometrii STEP |
| PyVista / VTK | MIT / BSD | widok 3D |
| pyqtgraph | MIT | interaktywny edytor profili |
| matplotlib | PSF/BSD-like | wykresy |
| ReportLab | BSD | generowanie PDF |
| NumPy / SciPy | BSD | obliczenia |
| Ollama (klient) | MIT | integracja z lokalnym modelem AI |

Pełne teksty licencji znajdziesz w dystrybucjach poszczególnych pakietów
(`pip show <pakiet>`), na ich stronach domowych oraz w repozytoriach źródłowych.
