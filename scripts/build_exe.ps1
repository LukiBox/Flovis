# Buduje Flovis.exe (PyInstaller) z katalogu repozytorium.
# Uzycie:  .\scripts\build_exe.ps1
# Wymaga aktywnego srodowiska z zainstalowanym pyinstaller (pip install pyinstaller).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m PyInstaller flovis.spec --noconfirm

Write-Output ""
Write-Output "Gotowe: $root\dist\Flovis.exe"
Write-Output "Uwaga: przy nazwie uzytkownika ze znakami spoza ASCII uruchamiaj .exe"
Write-Output "z folderu na sciezce ASCII (np. C:\Flovis\)."
