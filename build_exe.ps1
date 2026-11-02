# Gera dist\AnotadorPad.exe com PyInstaller (Windows)
# Uso:  powershell -ExecutionPolicy Bypass -File build_exe.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

py -3.11 -m pip install --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar PyInstaller" }

py -3.11 -m PyInstaller `
  --noconfirm --clean --onefile `
  --name AnotadorPad `
  --paths . --paths .. `
  --hidden-import detector_anomalias `
  --hidden-import filtros_pcb `
  --hidden-import core.dataset `
  --hidden-import core.detector_ia `
  --hidden-import core.detector_smart `
  --hidden-import core.datasheet `
  --hidden-import core.imgio `
  --hidden-import core.units `
  --hidden-import core.prefs `
  --hidden-import core.report `
  --hidden-import core.transform `
  --add-data "..\imagens;imagens" `
  main.py

if ($LASTEXITCODE -eq 0) {
  Write-Host ""
  Write-Host "OK! Executavel em: $PSScriptRoot\dist\AnotadorPad.exe"
} else {
  Write-Host "Falha no build"
}
