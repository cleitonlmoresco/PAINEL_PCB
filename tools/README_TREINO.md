# Treinar a IA de pads — guia prático

## Visão geral
```
fotos do álbum ──► pré-anotação (smart) ──► dataset YOLO (tiles 1024)
                                             │
projetos corrigidos ───────────────────────► ├──► treino (YOLO11) ──► models/pads.onnx
                                             │
                                             └──► app: Detector IA
```

## 1. Gerar dataset do álbum (pré-anotação)
```powershell
py -3.11 tools/exportar_dataset.py album `
  --fotos "C:\PCB_Painel\placas eletronicas\Placas eletrônicas -1-001\Placas eletrônicas" `
  --saida "C:\PCB_Painel\dataset_placas" --escala 0.7 --tile 1024 --val 0.2
```
- HEIC suportado (pillow-heif)
- Vídeos (.mp4) são ignorados
- Cada foto vira tiles de 1024×1024 (pads preservam o tamanho real)
- Labels: classe `0 = pad`, formato YOLO normalizado

## 2. Dataset dos projetos já anotados (ground truth)
```powershell
py -3.11 tools/exportar_dataset.py projetos --pastas C:\PCB_Painel --saida C:\PCB_Painel\dataset_projetos
```
Você pode exportar os dois para a MESMA pasta de saída (os nomes não colidem).

## 3. Treinar
### Opção 0 — baseline rápido em CPU (script pronto)
```powershell
powershell -ExecutionPolicy Bypass -File tools\treinar_rapido.ps1
```
Cria subset de 600+150 tiles, treina YOLO11n por 12 épocas a 512 e exporta
`models/pads.onnx` (qualidade inicial; ideal é treinar completo em GPU).

### Opção A — GPU própria (NVIDIA/CUDA)
```powershell
py -3.11 -m pip install -r requirements_treino.txt
py -3.11 tools/treinar_pads.py --dataset C:\PCB_Painel\dataset_placas --epochs 100 --imgsz 1024 --batch 16
```
### Opção B — Google Colab (recomendado p/ 500 fotos)
Abra `tools/Colab_Treinar_Pads.ipynb`, envie o zip de `dataset_placas` e rode as células.
### Opção C — CPU
Funciona, mas 500 fotos pode levar dias. Reduza `--imgsz 640 --epochs 40 --batch 4`.

## 4. Usar no app
1. Copie o `.onnx` exportado para `anotador-modular\models\pads.onnx`
   (e o `pads.json` ao lado, com o `imgsz`)
2. Para o **EXE**: copie também para `anotador-modular\dist\models\pads.onnx`
3. No app: `Ctrl+K` → **Detector IA (modelo ONNX)**
4. Ajuste a sensibilidade (mesma da paleta) e rode `[D]`

## 5. Active learning (o que mais melhora)
1. Treine um modelo inicial (acima)
2. Use **Detector IA** para pré-anotar fotos novas
3. Corrija no app (mover/remover/adicionar pads)
4. Exporte os projetos corrigidos e **re-treine**

## Métricas e qualidade
- Após treinar, valide: `metrica mAP50` do YOLO; ideal > 0.80 para pads
- Dataset desbalanceado? Mantenha tiles vazios (o exporter os inclui) para reduzir falsos positivos
- Se muitos falsos positivos de texto: aumente a sensibilidade para 0.65 e re-exporte

## Estrutura esperada
```
dataset_placas/
  data.yaml
  images/train/*.jpg
  images/val/*.jpg
  labels/train/*.txt
  labels/val/*.txt
```
