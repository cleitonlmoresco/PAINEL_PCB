# Treino rápido em CPU (baseline) para começar a usar a IA hoje
# Uso: powershell -ExecutionPolicy Bypass -File tools\treinar_rapido.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot\..

$dataset = "C:\PCB_Painel\dataset_placas"
$subset  = "C:\PCB_Painel\dataset_rapido"

if (-not (Test-Path $dataset)) { throw "Dataset nao encontrado: $dataset" }

Write-Host "1) Criando subset equilibrado..."
py -3.11 tools\preparar_subset.py --dataset $dataset --saida $subset --train 600 --val 150 --vazios 0.2

Write-Host "2) Instalando dependencias (se necessario)..."
py -3.11 -m pip install -r requirements_treino.txt

Write-Host "3) Treinando YOLO11n (CPU) - baseline rapido..."
py -3.11 tools\treinar_pads.py --dataset $subset --epochs 12 --imgsz 512 --batch 8 --workers 4 --device cpu --nome pads_rapido

Write-Host ""
Write-Host "Modelo: models\pads.onnx (se o export falhou, veja a mensagem acima)"
Write-Host "No app: Ctrl+K -> Detector IA (modelo ONNX)"
