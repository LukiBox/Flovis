# Buduje Flovis.exe (PyInstaller) od zera - tworzy .venv, instaluje zaleznosci,
# uruchamia PyInstaller. Wymaga Windows + Python 3.10+ w PATH.
#
# Uzycie:  .\scripts\build_exe.ps1
# Flaga -Clean usuwa poprzednie build/ i dist/ przed budowa:
#   .\scripts\build_exe.ps1 -Clean
# Flaga -SkipInstall pomija tworzenie venv/instalacje (uzyj jesli srodowisko juz gotowe):
#   .\scripts\build_exe.ps1 -SkipInstall

param(
    [switch]$Clean,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ($root -match '[^\x00-\x7F]') {
    Write-Warning "Sciezka repozytorium zawiera znaki spoza ASCII ($root)."
    Write-Warning "PyInstaller/aerosandbox moga sie wywalic. Sklonuj repo do np. C:\Flovis\ i uruchom stamtad."
}

if (-not $SkipInstall) {
    $venvPath = Join-Path $root ".venv"
    if (-not (Test-Path $venvPath)) {
        Write-Output "Tworze srodowisko wirtualne w $venvPath ..."
        python -m venv $venvPath
    }

    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        throw "Nie znaleziono $venvPython - sprawdz instalacje Pythona (wymagany 3.10+)."
    }

    Write-Output "Instaluje zaleznosci (moze potrwac kilka minut, ciezkie pakiety: aerosandbox, vtk, gmsh)..."
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt

    $python = $venvPython
} else {
    $python = "python"
}

if ($Clean) {
    Write-Output "Czyszcze poprzednie build/ i dist/ ..."
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $root "build")
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $root "dist")
}

foreach ($bin in @("flovis\resources\bin\xfoil.exe", "flovis\resources\bin\avl.exe")) {
    if (-not (Test-Path (Join-Path $root $bin))) {
        throw "Brak wymaganego pliku: $bin - repozytorium jest niekompletne."
    }
}

Write-Output "Buduje Flovis.exe (PyInstaller)..."
& $python -m PyInstaller flovis.spec --noconfirm

$exePath = Join-Path $root "dist\Flovis.exe"
if (Test-Path $exePath) {
    Write-Output ""
    Write-Output "Gotowe: $exePath"
    Write-Output "Uwaga: przy nazwie uzytkownika ze znakami spoza ASCII uruchamiaj .exe"
    Write-Output "z folderu na sciezce ASCII (np. C:\Flovis\)."
} else {
    throw "Build nie powiodl sie - brak pliku dist\Flovis.exe."
}
