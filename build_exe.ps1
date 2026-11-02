# Gera dist\AnotadorPad.exe com PyInstaller (Windows)
# Uso:  powershell -ExecutionPolicy Bypass -File build_exe.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host "Instalando dependencias..." -ForegroundColor Cyan
py -3.11 -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependencias" }

py -3.11 -m pip install -q --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar PyInstaller" }

Write-Host "Compilando executavel..." -ForegroundColor Cyan
py -3.11 -m PyInstaller `
  --noconfirm --clean --onefile `
  --name AnotadorPad `
  --paths . `
  --hidden-import detector_anomalias `
  --hidden-import anomalias_modulo `
  --hidden-import core.dataset `
  --hidden-import core.detector_ia `
  --hidden-import core.detector_smart `
  --hidden-import core.datasheet `
  --hidden-import core.imgio `
  --hidden-import core.units `
  --hidden-import core.prefs `
  --hidden-import core.report `
  --hidden-import core.transform `
  --hidden-import core.state_manager `
  --hidden-import core.active_learning `
  main.py

if ($LASTEXITCODE -eq 0) {
  $exe = Join-Path $PSScriptRoot 'dist\AnotadorPad.exe'
  $mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
  Write-Host ""
  Write-Host "OK! Executavel em: $exe ($mb MB)" -ForegroundColor Green
} else {
  throw "Falha no build"
}
