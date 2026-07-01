<div align="center">

# ✈️ Flovis

### Aerodynamika modeli latających — prosto, wizualnie, offline

**Analizuj profile i skrzydła jak w XFLR5, ale bez wchodzenia w matematykę.**
Flovis prowadzi Cię za rękę: wybierasz układ, klikasz „analizuj", a dostajesz
bieguny, stateczność, kolorowy rozkład ciśnień w 3D i gotowy raport PDF —
z opisem słownym napisanym przez lokalną sztuczną inteligencję.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/UI-PySide6%20(Qt6)-41CD52?logo=qt&logoColor=white)
![Offline](https://img.shields.io/badge/Dzia%C5%82a-100%25%20offline-2563EB)
![License](https://img.shields.io/badge/Licencja-MIT-green)
![Tests](https://img.shields.io/badge/testy-28%20passed-success)

</div>

---

## 🎯 Dla kogo jest Flovis?

Dla **pasjonatów, modelarzy i konstruktorów-amatorów**, którzy chcą wiedzieć,
*czy ich model poleci* — bez dyplomu z aerodynamiki i bez walki z surowym
XFoilem czy AVL z linii poleceń.

> Zawodowe narzędzia (XFLR5, XFoil, AVL) są potężne, ale onieśmielają.
> Flovis chowa całą matematykę za czystym, minimalistycznym interfejsem
> i **domyślnie podpowiada bezpieczne wartości**. Wszystkie najważniejsze
> akcje są w 2–3 kliknięciach.

Pod maską pracują jednak **prawdziwe silniki numeryczne** — te same, których
używają profesjonaliści.

---

## ✨ Co potrafi

| | Funkcja |
|---|---|
| 🛩️ | **6 parametrycznych układów** — dolnopłat, górnopłat, układ z belkami, silnik pchający, kaczka, latające skrzydło. Edytujesz na żywo, widzisz rzut z góry. |
| ✏️ | **Interaktywny edytor profili** — przeciągasz punkty myszą, wstawiasz/usuwasz, cofasz (undo/redo), repanelizacja kosinusowa, wygładzanie, walidacja geometrii na żywo. |
| 📈 | **Bieguny profilu 2D** — solidny **XFoil** (w komplecie) z pełnym rozkładem `Cp`, oraz **NeuralFoil** jako błyskawiczny fallback. Cl(α), Cl(Cd), Cl_max, α_stall. |
| 🌬️ | **Solvery 3D** — **VLM** (AeroSandbox) z realnymi profilami i sprzężeniem z XFoil, **AVL** (tryb dokładny, w komplecie) oraz estymator analityczny „od ręki". |
| 🧊 | **Analiza STEP (.stp)** — wczytaj geometrię z CAD, a Flovis pokaże ją w 3D z **kolorowym rozkładem ciśnień**. |
| 🎨 | **Widok 3D** — bryła modelu z mapą ciśnień (niebieski = ssanie, czerwony = spiętrzenie), CG i punkt neutralny, obrót/zoom. |
| 📄 | **Raport PDF** — wielostronicowy: ocena „czerwony/żółty/zielony", bieguny, pochodne stateczności, rozkład Cp i **interpretacja słowna z AI**. |
| 🤖 | **Lokalna AI (Ollama)** — model `qwen3:30b-a3b` tłumaczy wyniki prostym językiem. W pełni offline, prywatnie, na Twoim komputerze. |
| 💾 | **Format projektu `.flovis`** — zapisz cały stan pracy (model, profil, ustawienia, wyniki) i wróć do niego później. |

> 🔒 **Wszystko działa offline.** Nic nie wychodzi do internetu — nawet AI liczy się lokalnie.

---

## 🖼️ Zrzuty ekranu

> 📸 Wrzuć swoje zrzuty do `docs/screenshots/` (np. `templates.png`,
> `pressure3d.png`), a następnie odkomentuj poniższą tabelę — obrazy pojawią się
> na tej stronie.

<!--
| Szablony i geometria | Rozkład ciśnień 3D |
|---|---|
| ![Szablony](docs/screenshots/templates.png) | ![Cisnienie 3D](docs/screenshots/pressure3d.png) |
-->

---

## 🚀 Szybki start

> ⚠️ **Ważne (Windows z polskimi znakami w nazwie użytkownika, np. `Łukasz`):**
> biblioteka **casadi** (silnik AeroSandbox) nie ładuje swoich wtyczek ze ścieżki
> zawierającej znaki spoza ASCII. Dlatego **środowisko wirtualne musi leżeć na
> ścieżce ASCII**, np. `C:\Users\Public\flovis-venv`. Sam projekt może być gdziekolwiek.

```powershell
# 1. Sklonuj repozytorium
git clone https://github.com/<twoj-user>/Flovis.git
cd Flovis

# 2. Środowisko wirtualne na ścieżce ASCII (ważne!)
python -m venv C:\Users\Public\flovis-venv
C:\Users\Public\flovis-venv\Scripts\Activate.ps1

# 3. Zależności
pip install -r requirements.txt

# 4. Start
python -m flovis.app
```

### 🤖 Uruchomienie AI (opcjonalne)

Zainstaluj [Ollama](https://ollama.com), a następnie:

```powershell
ollama pull qwen3:30b-a3b
ollama serve
```

Flovis sam wykryje dostępne modele. **Raport wygenerujesz też bez AI** — sekcja jest opcjonalna.

---

## 🧪 Testy

```powershell
python -m pytest tests/ -q
```

**28 testów**: silnik i edytor profili, solvery (VLM vs analityczny vs AVL),
wrapper XFoil + NeuralFoil, **metoda panelowa vs VLM (< 10%)**, I/O projektu, generowanie PDF.

---

## 📦 Budowa pliku wykonywalnego (.exe)

```powershell
pip install pyinstaller
pyinstaller flovis.spec --noconfirm
```

Powstaje `dist/Flovis.exe` (jeden plik) z dołączonymi binarkami XFoil/AVL.

> Uwaga: plik one-file rozpakowuje się do `%TEMP%`. Przy nazwie użytkownika ze
> znakami spoza ASCII uruchamiaj `.exe` z folderu na ścieżce ASCII (np. `C:\Flovis\`).

---

## 🏗️ Architektura

```
flovis/
  app.py                    # punkt wejścia (QApplication, jasny motyw)
  core/
    airfoil/                # generator NACA (klasyczny + zmodyfikowany), edytor, XFoil/NeuralFoil
    geometry/               # 6 parametrycznych szablonów samolotów
    solvers/                # VLM (AeroSandbox), AVL, analityczny, metoda panelowa 3D
    report/                 # wykresy + generator PDF (ReportLab)
    ai/                     # klient Ollama (interpretacja słowna)
    project.py              # format .flovis (zapis/odczyt)
  ui/
    main_window.py          # okno, menu, motyw, onboarding
    tabs/                   # Szablony / Profile / Analiza / Model 3D / Raport
    widgets/                # edytor pyqtgraph, widok 3D PyVista, wykresy
  resources/
    styles/flovis.qss       # jasny, minimalistyczny motyw
    bin/                    # XFoil 6.99, AVL 3.52 (Windows)
tests/                      # pytest
```

| Warstwa | Technologia |
|---|---|
| UI | PySide6 (Qt6) + matplotlib + pyqtgraph |
| Widok 3D | PyVista / VTK |
| Aero 2D | XFoil (subprocess) + NeuralFoil |
| Aero 3D | AeroSandbox (VLM) + AVL |
| STEP | gmsh (kernel OpenCASCADE) + metoda panelowa 3D |
| Raporty | matplotlib + ReportLab |
| AI | Ollama (`qwen3:30b-a3b`) |

---

## 🔬 Jak to działa (w skrócie)

- **Profile NACA** — generator klasyczny i **zmodyfikowany 4-cyfrowy** (przesuwana
  pozycja maks. grubości, regulowany promień natarcia), np. `0011-0.825-35`.
- **VLM** buduje geometrię z rzeczywistych profili i sprzęga się z XFoilem
  (teoria pasków), dzięki czemu biegun 3D ma realistyczny opór i `CL_max`.
- **AVL** to „tryb dokładny" — pełne pochodne stateczności i punkt neutralny
  prosto z solvera.
- **Metoda panelowa STEP** (source-doublet, warunek Kutty) daje jakościowy
  rozkład ciśnień na dowolnej geometrii z CAD.

---

## ⚠️ Uwagi inżynierskie (uczciwie)

- **Metoda panelowa STEP** to solver **niskiego rzędu o charakterze poglądowym** —
  świetny do wizualizacji rozkładu ciśnień i szybkiej oceny, ale do liczb
  ilościowych używaj **VLM lub AVL**. Dla dowolnej geometrii jest skalibrowany do
  VLM na skrzydle prostokątnym (zgodność < ~3%).
- **Estymator analityczny** służy responsywności („wynik od ręki"); miarodajne
  wyniki daje VLM/AVL.

---

## 🗺️ Status

Wszystkie główne funkcje działają end-to-end: **szablon → analiza → AI → PDF**
oraz **import STEP → rozkład ciśnień 3D**. Zobacz [CHANGELOG.md](CHANGELOG.md).

---

## 📜 Licencja

Kod Flovis: **MIT** (patrz [LICENSE](LICENSE)).
Dołączone binarki i biblioteki mają własne licencje — szczegóły w
[THIRD_PARTY.md](THIRD_PARTY.md) (XFoil i AVL to oprogramowanie Marka Dreli,
na licencji GPL).

---

<div align="center">

**Zbudowane dla tych, którzy kochają latać to, co sami zaprojektowali. 🛩️**

</div>
