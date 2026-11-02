"""
Módulo de Detecção de Anomalias integrado ao AnotadorPad v11.

Permite comparar uma placa de teste com uma "placa de referência ouro"
usando detector_anomalias.py, gerando:
  - Relatório JSON de anomalias
  - Imagem overlay com bbox e rótulos
  - Salva em saida_anomalias/<timestamp>/

Uso direto:
    python anomalias_modulo.py --ouro imagens/placa_boa.jpg --teste imagens/placa_suspeita.jpg

Ou chame programaticamente:
    from anomalias_modulo import executar_comparacao
    resultado = executar_comparacao("ouro.jpg", "teste.jpg", "saida_anomalias")
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# Procura o detector_anomalias primeiro no próprio repositório (vendorizado)
# e, como fallback, na pasta pai (instalação antiga fora do repositório).
_HERE = Path(__file__).resolve().parent
_PARENT = _HERE.parent
for _p in (_HERE, _PARENT):
    if (_p / 'detector_anomalias.py').exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from detector_anomalias import (
    AlinhadorPlacas,
    NormalizadorIluminacao,
    ComparadorPlacas,
    ClassificadorAnomalias,
    VisualizadorAnomalias,
    ConfigAnomalias,
    ResultadoComparacao,
    Anomalia,
    TipoAnomalia,
    Severidade,
)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def carregar_imagem(caminho: str) -> np.ndarray:
    img = cv2.imread(caminho)
    if img is None:
        raise FileNotFoundError(f"Não foi possível ler a imagem: {caminho}")
    return img


def executar_comparacao(
    caminho_ouro: str,
    caminho_teste: str,
    dir_saida: Optional[str] = None,
    salvar_visualizacao: bool = True,
) -> Dict:
    """
    Executa o pipeline completo de detecção de anomalias.

    Passos:
      1. Carrega imagens (ouro e teste)
      2. Alinha geometricamente (ORB + homografia)
      3. Normaliza iluminação (CLAHE)
      4. Compara (AbsDiff + SSIM combinado)
      5. Classifica anomalias (faltante, extra, pad danificado, trilha rompida, corrosão...)
      6. Gera visualização e salva JSON

    Retorna dicionário com resultado completo.
    """
    img_ouro = carregar_imagem(caminho_ouro)
    img_teste = carregar_imagem(caminho_teste)

    cfg = ConfigAnomalias()

    # 1. Alinhamento
    alinhador = AlinhadorPlacas(cfg.alinhamento)
    img_ouro_al, img_teste_al, info_al = alinhador.alinhar(img_ouro, img_teste)

    # 2. Normalização
    normalizador = NormalizadorIluminacao(cfg.normalizacao)
    img_ouro_n = normalizador.normalizar(img_ouro_al)
    img_teste_n = normalizador.normalizar(img_teste_al)

    # 3. Comparação
    comparador = ComparadorPlacas(cfg.comparacao)
    mascara_diff, mapa_absdiff, mapa_ssim = comparador.comparar(img_ouro_n, img_teste_n)

    # 4. Classificação
    classificador = ClassificadorAnomalias(cfg.classificacao)
    anomalias: List[Anomalia] = classificador.classificar(
        mascara_diff, img_ouro_n, img_teste_n
    )

    # 5. Resultado estruturado
    total = len(anomalias)
    por_severidade: Dict[str, int] = {}
    for a in anomalias:
        por_severidade[a.severidade] = por_severidade.get(a.severidade, 0) + 1

    score_global = 1.0 - min(1.0, total / 50.0)  # heurística simples

    resultado = ResultadoComparacao(
        placa_ouro_path=caminho_ouro,
        placa_teste_path=caminho_teste,
        timestamp=_timestamp(),
        total_anomalias=total,
        anomalias_por_severidade=por_severidade,
        anomalias=anomalias,
        score_global_similaridade=round(score_global, 3),
        matriz_alinhamento=info_al.get("matriz_H"),
        deslocamento_detectado=(
            info_al.get("deslocamento_x", 0.0),
            info_al.get("deslocamento_y", 0.0),
        ),
        rotacao_detectada=info_al.get("rotacao_graus", 0.0),
        escala_detectada=info_al.get("escala", 1.0),
    )

    # 6. Salva arquivos
    if dir_saida is None:
        dir_saida = os.path.join("saida_anomalias", f"comparacao_{_timestamp()}")
    os.makedirs(dir_saida, exist_ok=True)

    # JSON do resultado
    json_path = os.path.join(dir_saida, "resultado_anomalias.json")
    dados_json = {
        "placa_ouro": resultado.placa_ouro_path,
        "placa_teste": resultado.placa_teste_path,
        "timestamp": resultado.timestamp,
        "total_anomalias": resultado.total_anomalias,
        "anomalias_por_severidade": resultado.anomalias_por_severidade,
        "score_global_similaridade": resultado.score_global_similaridade,
        "deslocamento_detectado": resultado.deslocamento_detectado,
        "rotacao_detectada": resultado.rotacao_detectada,
        "escala_detectada": resultado.escala_detectada,
        "alinhamento": info_al,
        "anomalias": [
            {
                "id": a.id,
                "tipo": a.tipo,
                "severidade": a.severidade,
                "bbox": a.bbox,
                "centro": a.centro,
                "area": a.area,
                "score_diferenca": a.score_diferenca,
                "descricao": a.descricao,
            }
            for a in resultado.anomalias
        ],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dados_json, f, indent=2, ensure_ascii=False)

    # Visualização overlay
    if salvar_visualizacao:
        vis = VisualizadorAnomalias(cfg.visualizacao)
        overlay = vis.gerar_overlay(
            img_ouro_al, img_teste_al, mascara_diff, resultado.anomalias
        )
        img_vis_path = os.path.join(dir_saida, "overlay_anomalias.png")
        cv2.imwrite(img_vis_path, overlay)

        # Máscara de diferença bruta
        mask_path = os.path.join(dir_saida, "mascara_diferenca.png")
        cv2.imwrite(mask_path, mascara_diff)

    resultado_dict = {
        "status": "ok",
        "dir_saida": dir_saida,
        "json_path": json_path,
        "total_anomalias": total,
        "por_severidade": por_severidade,
        "score_global": score_global,
        "alinhamento_sucesso": info_al.get("sucesso", False),
    }
    return resultado_dict


# =============================================================================
# 7. SIMPLE UI (tkinter) para seleção de arquivos
# =============================================================================

def _selecionar_arquivos() -> Tuple[Optional[str], Optional[str]]:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception:
        return None, None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    ouro = filedialog.askopenfilename(
        title="Selecione a PLACA OURO (referência boa)",
        filetypes=[("Imagens", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("Todos", "*.*")],
    )
    if not ouro:
        root.destroy()
        return None, None

    teste = filedialog.askopenfilename(
        title="Selecione a PLACA DE TESTE (suspeita)",
        filetypes=[("Imagens", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("Todos", "*.*")],
    )
    root.destroy()
    return ouro, teste


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detecção de anomalias em PCB (comparação com placa ouro)"
    )
    parser.add_argument("--ouro", help="Caminho da placa de referência ouro")
    parser.add_argument("--teste", help="Caminho da placa de teste (suspeita)")
    parser.add_argument("--saida", default=None, help="Pasta de saída (padrão: saida_anomalias/comparacao_<ts>)")
    parser.add_argument("--sem-visualizacao", action="store_true", help="Não gerar imagem overlay")
    args = parser.parse_args()

    ouro = args.ouro
    teste = args.teste

    if not ouro or not teste:
        ouro, teste = _selecionar_arquivos()

    if not ouro or not teste:
        print("ERRO: Arquivos não selecionados. Encerrando.")
        sys.exit(1)

    print(f"📷 Ouro: {ouro}")
    print(f"📷 Teste: {teste}")

    try:
        res = executar_comparacao(
            caminho_ouro=ouro,
            caminho_teste=teste,
            dir_saida=args.saida,
            salvar_visualizacao=not args.sem_visualizacao,
        )
        print(f"\nOK - Comparação concluída!")
        print(f"   Total de anomalias: {res['total_anomalias']}")
        print(f"   Por severidade: {res['por_severidade']}")
        print(f"   Score global de similaridade: {res['score_global']:.3f}")
        print(f"   Alinhamento sucesso: {res['alinhamento_sucesso']}")
        print(f"   Relatório: {res['json_path']}")
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
