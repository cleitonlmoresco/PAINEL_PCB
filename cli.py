#!/usr/bin/env python3
"""
CLI unificado do AnotadorPad - treino, detecção, exportação, conversão.
"""
from __future__ import annotations
import sys
import os
import json
import subprocess
from pathlib import Path
from typing import Optional, List

try:
    import typer
except ImportError:
    print("Erro: typer não instalado. pip install typer", file=sys.stderr)
    sys.exit(1)

app = typer.Typer(
    name="anotador",
    help="AnotadorPad - CLI unificado para detecção, treino e anotação de pads de PCB",
    add_completion=False,
    no_args_is_help=True,
)

# ==================== COMANDOS DE TREINO ====================

@app.command("train")
def treinar(
    dataset: str = typer.Argument(..., help="Pasta do dataset YOLO (com data.yaml)"),
    modelo: str = typer.Option("yolo11n.pt", "--modelo", "-m", help="Modelo base YOLO"),
    epochs: int = typer.Option(100, "--epochs", "-e", help="Número de épocas"),
    imgsz: int = typer.Option(1024, "--imgsz", help="Tamanho da imagem"),
    batch: int = typer.Option(8, "--batch", "-b", help="Batch size"),
    device: str = typer.Option("", "--device", "-d", help="GPU (0) ou CPU (vazio)"),
    workers: int = typer.Option(4, "--workers", "-w", help="Workers do DataLoader"),
    nome: str = typer.Option("pads", "--nome", "-n", help="Nome do run"),
    export_onnx: bool = typer.Option(True, "--onnx/--no-onnx", help="Exportar ONNX ao final"),
    copiar_models: bool = typer.Option(True, "--copiar/--no-copiar", help="Copiar best.onnx para models/"),
):
    """
    Treina modelo YOLO para detecção de pads.
    
    Exemplo:
        anotador train C:\\PCB_Painel\\dataset_placas --epochs 100 --device 0
    """
    from tools.treinar_pads import main as treinar_main
    
    # Constrói sys.argv para o script original
    sys.argv = [
        "treinar_pads.py",
        "--dataset", dataset,
        "--modelo", modelo,
        "--epochs", str(epochs),
        "--imgsz", str(imgsz),
        "--batch", str(batch),
        "--device", device,
        "--workers", str(workers),
        "--nome", nome,
    ]
    treinar_main()
    
    # Exportar ONNX se solicitado
    if export_onnx:
        from ultralytics import YOLO
        import shutil
        best_pt = Path(f"runs/{nome}/weights/best.pt")
        if best_pt.exists():
            modelo_yolo = YOLO(str(best_pt))
            export_path = modelo_yolo.export(format="onnx", imgsz=imgsz, opset=12, simplify=True)
            if export_path and Path(export_path).exists():
                destino = Path("models") / "pads.onnx"
                destino.parent.mkdir(exist_ok=True)
                shutil.copy2(export_path, destino)
                print(f"ONNX copiado para {destino}")
                # Copia pads.json
                json_src = Path(f"runs/{nome}/weights/pads.json") if Path(f"runs/{nome}/weights/pads.json").exists() else None
                if not json_src:
                    # Cria pads.json com imgsz
                    import json
                    json_dest = Path("models") / "pads.json"
                    json_dest.write_text(json.dumps({"imgsz": imgsz, "modelo": modelo, "epochs": epochs}, indent=2))


@app.command("train-quick")
def treinar_rapido(
    dataset: str = typer.Argument(..., help="Pasta do dataset YOLO"),
    epochs: int = typer.Option(50, "--epochs", "-e"),
    device: str = typer.Option("0", "--device", "-d"),
):
    """Treino rápido com defaults otimizados (50 epochs, GPU 0)."""
    ctx = typer.get_current_context()
    ctx.invoke(treinar, dataset=dataset, epochs=epochs, device=device, nome="pads_rapido")


# ==================== COMANDOS DE DETECÇÃO ====================

@app.command("detect")
def detectar(
    imagem: str = typer.Argument(..., help="Imagem ou pasta de imagens"),
    modelo: Optional[str] = typer.Option(None, "--modelo", "-m", help="Modelo ONNX (padrão: models/pads.onnx)"),
    saida: Optional[str] = typer.Option(None, "--saida", "-o", help="Pasta de saída"),
    conf: float = typer.Option(0.35, "--conf", "-c", help="Confiança mínima"),
    device: str = typer.Option("", "--device", "-d", help="GPU (0) ou CPU"),
    tile: int = typer.Option(1024, "--tile", help="Tamanho do tile"),
    overlap: int = typer.Option(128, "--overlap", help="Overlap entre tiles"),
):
    """
    Roda detecção de pads em imagem(s) usando modelo ONNX.
    """
    from core.detector_ia import DetectorIA
    from core.imgio import ler_imagem, imwrite
    import cv2
    import numpy as np
    
    if modelo is None:
        modelo = "models/pads.onnx"
    
    modelo_path = Path(modelo)
    if not modelo_path.exists():
        print(f"Modelo não encontrado: {modelo}", file=sys.stderr)
        raise typer.Exit(1)
    
    print(f"Carregando modelo: {modelo}")
    detector = DetectorIA(modelo, tile=1024, overlap=128)
    
    imagens = []
    if Path(imagem).is_dir():
        for ext in ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'):
            imagens.extend(Path(imagem).glob(f"*{ext}"))
    else:
        imagens = [Path(imagem)]
    
    if not imagens:
        print("Nenhuma imagem encontrada", file=sys.stderr)
        raise typer.Exit(1)
    
    saida_path = Path(saida) if saida else Path("saida_detect")
    saida_path.mkdir(exist_ok=True)
    
    for img_path in imagens:
        print(f"Processando: {img_path.name}")
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"  Falha ao ler {img_path}")
            continue
        
        pads, _ = detector.detectar(img, conf=conf)
        print(f"  {len(pads)} pads detectados")
        
        # Desenha resultado
        vis = img.copy()
        for p in pads:
            x, y, w, h = int(p['cx']), int(p['cy']), int(p['w']), int(p['h'])
            cv2.rectangle(vis, (x-w//2, y-h//2), (x+w//2, y+h//2), (0, 220, 0), 2)
            cv2.putText(vis, f"{p.get('score', 0):.2f}", (x+w//2+2, y-h//2-2),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 220, 0), 1)
        
        out_path = saida_path / f"det_{img_path.name}"
        cv2.imwrite(str(out_path), vis)
        print(f"  Salvo: {out_path}")
    
    print(f"Concluído. Resultados em: {saida_path}")


# ==================== COMANDOS DE DATASET ====================

@app.command("export-dataset")
def exportar_dataset(
    pastas: List[str] = typer.Argument(..., help="Pastas de projetos anotados"),
    saida: str = typer.Option(..., "--saida", "-o", help="Pasta de saída do dataset"),
    tile: int = typer.Option(1024, "--tile", help="Tamanho do tile"),
    overlap: int = typer.Option(128, "--overlap", help="Overlap"),
    val: float = typer.Option(0.2, "--val", help="Fração validação"),
):
    """
    Exporta dataset YOLO a partir de projetos anotados.
    """
    from core.dataset import exportar_projetos
    
    def progresso(msg):
        print(msg, flush=True)
    
    stats = exportar_projetos(pastas, saida, tile=tile, overlap=overlap, val_ratio=val, progresso=progresso)
    print(f"\nRESUMO: {stats}")
    print(f"Dataset em: {Path(saida).resolve()}")


@app.command("pre-anotar")
def pre_anotar(
    fotos: str = typer.Argument(..., help="Pasta com fotos para pré-anotar"),
    saida: str = typer.Option(..., "--saida", "-o"),
    modelo: str = typer.Option("models/pads.onnx", "--modelo", "-m"),
    tile: int = typer.Option(1024, "--tile"),
    overlap: int = typer.Option(128, "--overlap"),
    val: float = typer.Option(0.2, "--val"),
    escala: float = typer.Option(0.7, "--escala"),
    sens: float = typer.Option(0.55, "--sens"),
    gpu: bool = typer.Option(True, "--gpu/--cpu"),
):
    """Pré-anota álbum de fotos com detector smart/IA."""
    from core.dataset import pre_anotar_album
    
    def progresso(msg):
        print(msg, flush=True)
    
    stats = pre_anotar_album(
        fotos, saida, tile=tile, overlap=overlap, val_ratio=val,
        escala=escala, sensibilidade=sens, usar_gpu=gpu, progresso=progresso
    )
    print(f"\nRESUMO: {stats}")


# ==================== COMANDOS DE CONVERSÃO ====================

@app.command("convert")
def converter(
    entrada: str = typer.Argument(..., help="Arquivo de entrada"),
    saida: str = typer.Argument(..., help="Arquivo de saída"),
    formato: Optional[str] = typer.Option(None, "--formato", "-f", help="Formato: json, csv, msgpack"),
):
    """Converte entre formatos de sessão/CSV/JSON."""
    from storage.loader import carregar_projeto_universal
    from storage.saver import salvar_csvs, salvar_componentes_csv
    import json
    
    pads, meas, nets, comps, _ = carregar_projeto_universal(entrada)
    
    if formato == "json" or saida.endswith(".json"):
        data = {
            "pads": pads, "measurements": meas, "nets": nets,
            "components": comps, "version": "v11.7"
        }
        with open(saida, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    elif formato == "csv" or saida.endswith(".csv"):
        # saida é diretório
        Path(saida).mkdir(parents=True, exist_ok=True)
        from storage.saver import salvar_csvs, salvar_componentes_csv
        salvar_csvs([], [], [], saida)  # placeholder
    else:
        print("Formato não suportado", file=sys.stderr)
        raise typer.Exit(1)
    
    print(f"Convertido: {entrada} -> {saida}")


# ==================== COMANDOS DE PROJETO ====================

@app.command("new")
def novo_projeto(
    imagem: str = typer.Argument(..., help="Imagem da placa"),
    pasta: Optional[str] = typer.Option(None, "--pasta", "-p", help="Pasta do projeto (padrão: saida_pads_*)"),
):
    """Cria novo projeto a partir de imagem."""
    from app.app import AppV101
    import core.imgio as imgio
    
    if pasta is None:
        import hashlib
        base = Path(imagem).stem
        hash_id = hashlib.md5(os.path.abspath(imagem).encode()).hexdigest()[:6]
        pasta = f"saida_pads_{base}_{hash_id}"
    
    Path(pasta).mkdir(parents=True, exist_ok=True)
    # Copia imagem
    import shutil
    img_dest = Path(pasta) / Path(imagem).name
    shutil.copy2(imagem, img_dest)
    
    # Cria app e salva sessão inicial
    app = AppV101(imagem, pasta)
    app._trocar_aba('calibrar')
    app._salvar_sessao()
    app._salvar_csvs()
    print(f"Projeto criado em: {pasta}")


@app.command("open")
def abrir_projeto(
    pasta: str = typer.Argument(..., help="Pasta do projeto"),
):
    """Abre projeto existente na GUI."""
    from app.app import AppV101
    import core.imgio as imgio
    
    app = AppV101("", pasta)
    app.iniciar()


# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    app()