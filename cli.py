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

from core.plugin_system import create_plugin_manager, PluginError

app = typer.Typer(
    name="anotador",
    help="AnotadorPad - CLI unificado para detecção, treino e anotação de pads de PCB",
    add_completion=False,
    no_args_is_help=True,
)

# Gerente de plugins (carregado lazy na primeira utilizacao)
_plugin_mgr = None

def _get_plugin_mgr():
    global _plugin_mgr
    if _plugin_mgr is None:
        try:
            _plugin_mgr = create_plugin_manager(app=None)
        except Exception as e:
            print(f"Aviso: nao foi possível carregar plugins ({e})", file=sys.stderr)
            _plugin_mgr = PluginManager(app=None)  # vazio
    return _plugin_mgr

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


# ==================== IMPORT/EXPORT PCB (KiCad / Eagle / Gerber) ====================

@app.command("export-kicad")
def export_kicad(
    projeto: str = typer.Argument(..., help="Pasta do projeto (sessao_*.json / CSVs)"),
    saida: Optional[str] = typer.Option(None, "--saida", "-o", help="Arquivo .kicad_pcb"),
    escala: float = typer.Option(0.0, "--escala", "-e", help="mm por pixel (Régua do app); 0 = aviso/0.1"),
    lado: str = typer.Option("frente", "--lado", "-l", help="frente | verso"),
    largura: int = typer.Option(0, "--largura", help="Largura da imagem em px (contorno da placa)"),
    altura: int = typer.Option(0, "--altura", help="Altura da imagem em px"),
):
    """Exporta o projeto anotado para KiCad (.kicad_pcb)."""
    from core import kicad
    from storage.loader import carregar_projeto_universal

    pads, _meas, nets, comps, _ = carregar_projeto_universal(projeto)
    destino = saida or str(Path(projeto) / 'placa.kicad_pcb')
    res = kicad.exportar_kicad(pads, comps, nets, destino, escala, lado, largura, altura)
    print(f"KiCad: {res['pads']} pads, {res['nets']} nets -> {res['caminho']}")
    for aviso in res['avisos']:
        print(f"AVISO: {aviso}")


@app.command("export-gerber")
def export_gerber(
    projeto: str = typer.Argument(..., help="Pasta do projeto (sessao_*.json / CSVs)"),
    saida: Optional[str] = typer.Option(None, "--saida", "-o", help="Arquivo .gbr"),
    escala: float = typer.Option(0.0, "--escala", "-e", help="mm por pixel; 0 = aviso/0.1"),
    lado: str = typer.Option("frente", "--lado", "-l", help="frente | verso"),
    largura: int = typer.Option(0, "--largura"),
    altura: int = typer.Option(0, "--altura"),
):
    """Exporta o cobre (pads) do projeto para Gerber RS-274X."""
    from core import kicad
    from storage.loader import carregar_projeto_universal

    pads, _meas, _nets, _comps, _ = carregar_projeto_universal(projeto)
    destino = saida or str(Path(projeto) / 'gerber' / 'cobre.gbr')
    res = kicad.exportar_gerber(pads, destino, escala, largura, altura, lado)
    print(f"Gerber: {res['pads']} pads, {res['aperturas']} aperturas -> {res['caminho']}")
    for aviso in res['avisos']:
        print(f"AVISO: {aviso}")


@app.command("import-pcb")
def import_pcb(
    arquivo: str = typer.Argument(..., help=".kicad_pcb, .brd ou .gbr"),
    saida: str = typer.Option("pcb_importado", "--saida", "-o", help="Pasta de destino"),
    escala: float = typer.Option(0.0, "--escala", "-e", help="mm por pixel; 0 = encaixa na imagem"),
    largura: int = typer.Option(1200, "--largura"),
    altura: int = typer.Option(900, "--altura"),
):
    """Importa KiCad/Eagle/Gerber e grava pads/nets/componentes em CSV."""
    from core.kicad import importar_arquivo
    from storage.saver import salvar_csvs, salvar_componentes_csv

    res = importar_arquivo(arquivo, largura, altura, escala)
    if not res['pads']:
        print(f"Nada importado ({res['formato']}): {'; '.join(res['avisos']) or 'sem pads'}", file=sys.stderr)
        raise typer.Exit(1)

    Path(saida).mkdir(parents=True, exist_ok=True)
    salvar_csvs(res['pads'], {}, res['nets'], saida)
    salvar_componentes_csv(res['componentes'], saida)
    print(f"{res['formato']}: {len(res['pads'])} pads, {len(res['componentes'])} comps, "
          f"{len(res['nets'])} nets -> {Path(saida).resolve()}")
    for aviso in res['avisos']:
        print(f"AVISO: {aviso}")


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


# ==================== ACTIVE LEARNING ====================

@app.command("active-learn")
def active_learn(
    dataset: str = typer.Argument(..., help="Pasta com imagens não rotuladas"),
    modelo: str = typer.Option("models/pads.onnx", "--modelo", "-m"),
    iteracoes: int = typer.Option(5, "--iter", "-i", help="Número de iterações"),
    batch: int = typer.Option(20, "--batch", "-b", help="Amostras por iteração"),
    conf_pseudo: float = typer.Option(0.8, "--conf-pseudo", help="Confiança para pseudo-label"),
    epocas_finetune: int = typer.Option(5, "--epochs", "-e"),
    saida: str = typer.Option("active_learning_data", "--saida", "-o"),
):
    """
    Executa loop de Active Learning completo.
    
    Exemplo:
        anotador active-learn C:\\fotos\\placas --iter 10 --batch 30
    """
    from core.active_learning import ActiveLearningOrchestrator, ActiveLearningConfig
    
    config = ActiveLearningConfig(
        model_path=modelo,
        dataset_dir=saida,
        query_batch_size=batch,
        pseudo_label_confidence=conf_pseudo,
        finetune_epochs=epocas_finetune,
    )
    
    orchestrator = ActiveLearningOrchestrator(config)
    
    # Coletar imagens
    imagens = []
    for ext in ('.jpg', '.jpeg', '.png', '.bmp'):
        imagens.extend(Path(dataset).glob(f"*{ext}"))
    
    if not imagens:
        print("Nenhuma imagem encontrada")
        raise typer.Exit(1)
    
    print(f"Iniciando Active Learning: {len(imagens)} imagens, {iteracoes} iterações")
    
    for i in range(iteracoes):
        print(f"\n=== Iteração {i+1}/{iteracoes} ===")
        
        # Selecionar batch de imagens não processadas
        batch_imgs = list(Path(dataset).glob("*.jpg"))[:batch]  # Simplificado
        
        def progress(stage, metrics):
            print(f"  [{stage}] {metrics}")
        
        metrics = orchestrator.run_iteration(
            [str(p) for p in batch_imgs],
            progress_callback=lambda s, m: print(f"  [{s}] {m}")
        )
        
        print(f"  Iteração {i+1} concluída: {metrics}")
    
    print("\nActive Learning concluído!")
    print(f"Total rotulado: {len(orchestrator.labeled_samples)}")


# ==================== PLUGINS (CLI) ====================

@app.command("plugin-list")
def plugin_list():
    """Lista todos os plugins carregados (entry-points e pasta plugins/)."""
    print("=== Plugins do AnotadorPad ===")
    print(_get_plugin_mgr().resumo())
    if not _get_plugin_mgr().plugins:
        print("  (nenhum plugin carregado)")
    cmds = _get_plugin_mgr().comandos_cli()
    if cmds:
        print("\nComandos CLI de plugins disponíveis:")
        for nome, func, ajuda in cmds:
            partes = nome.split(':', 1)
            cmd_nome = partes[1] if len(partes) == 2 else nome
            print(f"  anotador {cmd_nome}   - {ajuda}")


@app.command("plugin-info")
def plugin_info(nome: str):
    """Exibe detalhes de um plugin carregado."""
    plugin = _get_plugin_mgr().obter(nome)
    if plugin is None:
        print(f"Plugin '{nome}' não encontrado.")
        print(f"Plugins disponíveis: {', '.join(_get_plugin_mgr().listar()) or '(nenhum)'}")
        raise typer.Exit(1)
    print(f"=== Plugin: {nome} ===")
    print(f"Versão: {plugin.version}")
    print(f"Descrição: {plugin.description}")
    print(f"Ativo: {plugin.ativo}")
    cmds = plugin.get_cli_commands()
    if cmds:
        print("Comandos CLI:")
        for nm, func, ajuda in cmds:
            print(f"  - {nm}: {ajuda}")
    botoes = plugin.get_toolbar_buttons()
    if botoes:
        print(f"Botões GUI: {len(botoes)}")


@app.command("plugin-exec")
def plugin_exec(
    nome: str = typer.Argument(..., help="Nome do comando do plugin (ex: resumo)"),
    argumento: str = typer.Argument("", help="Argumento opcional para o comando"),
):
    """Executa um comando de plugin registrado."""
    # Busca o comando em todos os plugins
    encontrado = None
    for nome_plugin, func, ajuda in _get_plugin_mgr().comandos_cli():
        partes = nome_plugin.split(':', 1)
        cmd_nome = partes[1] if len(partes) == 2 else nome_plugin
        if cmd_nome == nome:
            encontrado = func
            break
    if encontrado is None:
        print(f"Comando de plugin '{nome}' não encontrado.")
        cmds = _get_plugin_mgr().comandos_cli()
        if cmds:
            print("Comandos disponíveis:")
            for n, f, a in cmds:
                partes = n.split(':', 1)
                print(f"  - {partes[1] if len(partes) == 2 else n}: {a}")
        raise typer.Exit(1)
    try:
        encontrado(app=None, argumento=argumento)
    except TypeError:
        encontrado(app=None)
    except Exception as e:
        print(f"Erro ao executar plugin '{nome}': {e}", file=sys.stderr)
        raise typer.Exit(1)


# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    app()