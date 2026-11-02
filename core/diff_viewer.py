"""Diff viewer: compara duas visões (frente x verso) da mesma placa.

Alinha as imagens via ORB+RANSAC (transform.alinhar_melhor), calcula
absdiff/heatmap e sobrepõe os pads anotados de cada visão sobre a imagem
alinhada, permitindo encontrar pads ausentes, desalinhados ou oxidados.

Sem dependências externas além de cv2/numpy (já usadas pelo app).
"""
from __future__ import annotations

import cv2
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from core.transform import alinhar_melhor, aplicar_h

__all__ = [
    'DiffResult',
    'calcular_diff',
    'desenhar_diff_lado_a_lado',
    'desenhar_diff_sobreposto',
    'resumo_diff_por_pad',
]


class DiffResult:
    """Resultado completo de uma comparação frente x verso."""

    def __init__(self, img_a: np.ndarray, img_b: np.ndarray,
                 mapa_diff: np.ndarray, mascara: np.ndarray,
                 heatmap: np.ndarray, H: Optional[np.ndarray],
                 espelhado: bool, score: int, threshold: int,
                 escala_mm_por_px: float = 0.0):
        self.img_a = img_a          # imagem de referência (frente)
        self.img_b = img_b          # imagem alvo (verso) já alinhada ao A
        self.mapa_diff = mapa_diff  # absdiff em escala de cinza (uint8)
        self.mascara = mascara      # máscara binária das diferenças (uint8 0/255)
        self.heatmap = heatmap      # heatmap colorido (BGR) das diferenças
        self.H = H                  # homografia que mapeia A -> B
        self.espelhado = espelhado  # se B precisou ser espelhado para casar
        self.score = score          # nº de inliers do alinhamento
        self.threshold = threshold  # limiar usado para binarizar a diferença
        self.escala_mm_por_px = escala_mm_por_px
        self.pixels_totais = int(mascara.size)
        self.pixels_diff = int(np.sum(mascara > 0))
        self.similaridade = 1.0 - (self.pixels_diff / max(1, self.pixels_totais))

    @property
    def pct_diff(self) -> float:
        return 100.0 * self.pixels_diff / max(1, self.pixels_totais)


def _mapear_pontos(H: Optional[np.ndarray], pontos: List[Tuple[float, float]],
                   w_img_b: int, espelhado: bool) -> List[Tuple[float, float]]:
    """Aplica homografia (com espelhamento) a uma lista de pontos."""
    if H is None or not pontos:
        return []
    out = aplicar_h(H, pontos)
    if espelhado:
        out = [(w_img_b - x, y) for x, y in out]
    return out


def _calcular_mascara_diff(gray_a: np.ndarray, gray_b: np.ndarray,
                           threshold: int) -> Tuple[np.ndarray, np.ndarray]:
    """absdiff + limiarização. Retorna (mapa_diff, mascara_binaria)."""
    diff = cv2.absdiff(gray_a, gray_b)
    _, mascara = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
    # fechamento leve para agrupar ruído em diferenças coesas
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, kernel, iterations=1)
    return diff, mascara


def _heatmap_da_mascara(mascara: np.ndarray) -> np.ndarray:
    """Converte máscara binária em heatmap colorido (COLORMAP_JET)."""
    # dilatar um pouco para o heatmap ficar visível ao redor da borda
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    dil = cv2.dilate(mascara, kernel, iterations=1)
    heat = cv2.applyColorMap(dil, cv2.COLORMAP_JET)
    return heat


def _desenhar_pads_sobre(img: np.ndarray, pads: List[Dict[str, Any]],
                         cor: Tuple[int, int, int], w_px: int, h_px: int,
                         mm_por_px: float = 0.0, rotulo: bool = False) -> np.ndarray:
    """Desenha contornos dos pads (cx,cy,w,h) sobre a imagem."""
    vis = img.copy()
    for p in pads or []:
        cx = int(p.get('cx', p.get('x', 0)))
        cy = int(p.get('cy', p.get('y', 0)))
        w = max(1, int(p.get('w', 12)))
        h = max(1, int(p.get('h', w)))
        x0, y0 = cx - w // 2, cy - h // 2
        x1, y1 = cx + w // 2, cy + h // 2
        cv2.rectangle(vis, (x0, y0), (x1, y1), cor, 2)
        cv2.circle(vis, (cx, cy), 2, (0, 0, 255), -1)
        if rotulo:
            pid = str(p.get('id', ''))
            cv2.putText(vis, pid, (x0, max(0, y0 - 3)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, cor, 1, cv2.LINE_AA)
    return vis


def calcular_diff(img_a: np.ndarray, img_b: np.ndarray,
                  threshold: int = 40,
                  escala_mm_por_px: float = 0.0) -> DiffResult:
    """Compara img_a (referência) com img_b (alvo).

    Alinha b sobre a via homografia (ORB+RANSAC), tenta espelhamento
    (frente x verso) e devolve mapa de diferença + heatmap.
    """
    if img_a is None or img_b is None:
        raise ValueError("img_a e img_b não podem ser None")

    # Alinhamento (tenta normal e espelhado)
    H, espelhado, score = alinhar_melhor(img_a, img_b, tentar_espelho=True)

    # Se não alinhou, compara direto (mesmo tamanho esperado)
    if H is None:
        b_alinhada = img_b.copy()
        if img_a.shape[:2] != img_b.shape[:2]:
            b_alinhada = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]),
                                    interpolation=cv2.INTER_AREA)
        H = np.eye(3, dtype=np.float64)
    else:
        h_a, w_a = img_a.shape[:2]
        h_b, w_b = img_b.shape[:2]
        if espelhado:
            b_flip = cv2.flip(img_b, 1)
            b_alinhada = cv2.warpPerspective(b_flip, H, (w_a, h_a))
        else:
            b_alinhada = cv2.warpPerspective(img_b, H, (w_a, h_a))

    gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(b_alinhada, cv2.COLOR_BGR2GRAY)
    if gray_a.shape != gray_b.shape:
        gray_b = cv2.resize(gray_b, (gray_a.shape[1], gray_a.shape[0]),
                            interpolation=cv2.INTER_AREA)

    mapa_diff, mascara = _calcular_mascara_diff(gray_a, gray_b, threshold)
    heatmap = _heatmap_da_mascara(mascara)

    return DiffResult(img_a, b_alinhada, mapa_diff, mascara, heatmap,
                      H, espelhado, score, threshold, escala_mm_por_px)


def desenhar_diff_lado_a_lado(res: DiffResult, pads_a: List[Dict[str, Any]],
                              pads_b: List[Dict[str, Any]],
                              w_max: int = 900) -> np.ndarray:
    """Renderiza [imagem A com pads | imagem B com pads + heatmap] lado a lado."""
    ia = res.img_a
    ib = res.img_b
    h, w = ia.shape[:2]
    escala = min(1.0, w_max / (w * 2 + 40))
    if escala < 1.0:
        nw, nh = max(1, int(w * escala)), max(1, int(h * escala))
        ia = cv2.resize(ia, (nw, nh), interpolation=cv2.INTER_AREA)
        ib = cv2.resize(ib, (nw, nh), interpolation=cv2.INTER_AREA)
        h, w = nh, nw
        # mapear pads para a escala
        pads_a = [{**p, 'cx': int(p.get('cx', p.get('x', 0)) * escala),
                   'cy': int(p.get('cy', p.get('y', 0)) * escala),
                   'w': max(1, int(p.get('w', 12) * escala)),
                   'h': max(1, int(p.get('h', p.get('w', 12)) * escala))}
                  for p in pads_a or []]
        pads_b = [{**p, 'cx': int(p.get('cx', p.get('x', 0)) * escala),
                   'cy': int(p.get('cy', p.get('y', 0)) * escala),
                   'w': max(1, int(p.get('w', 12) * escala)),
                   'h': max(1, int(p.get('h', p.get('w', 12)) * escala))}
                  for p in pads_b or []]

    # A: pads em verde (referência)
    vis_a = _desenhar_pads_sobre(ia, pads_a or [], (0, 255, 0), w, h)
    # B: pads em azul (alvo) + heatmap das diferenças em vermelho translúcido
    vis_b = _desenhar_pads_sobre(ib, pads_b or [], (255, 180, 0), w, h)
    heat = cv2.resize(res.heatmap, (w, h), interpolation=cv2.INTER_LINEAR)
    vis_b = cv2.addWeighted(vis_b, 0.6, heat, 0.4, 0)

    barra = np.full((h, 8, 3), (60, 60, 60), dtype=np.uint8)
    canvas = np.hstack([vis_a, barra, vis_b])
    # rótulos
    cv2.putText(canvas, 'FRENTE (ref)', (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0, 255, 0), 2, cv2.LINE_AA)
    cv2.putText(canvas, 'VERSO (alvo + heatmap)', (w + 18, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 180, 0), 2, cv2.LINE_AA)
    return canvas


def desenhar_diff_sobreposto(res: DiffResult, pads_a: List[Dict[str, Any]],
                             pads_b: List[Dict[str, Any]],
                             alpha: float = 0.5,
                             w_max: int = 900) -> np.ndarray:
    """Renderiza [imagem A com heatmap de diferença sobreposta]."""
    ia = res.img_a.copy()
    h, w = ia.shape[:2]
    escala = min(1.0, w_max / w)
    if escala < 1.0:
        nw, nh = max(1, int(w * escala)), max(1, int(h * escala))
        ia = cv2.resize(ia, (nw, nh), interpolation=cv2.INTER_AREA)
        res.heatmap = cv2.resize(res.heatmap, (nw, nh), interpolation=cv2.INTER_LINEAR)
        res.mapa_diff = cv2.resize(res.mapa_diff, (nw, nh), interpolation=cv2.INTER_LINEAR)
        h, w = nh, nw
        pads_a = [{**p, 'cx': int(p.get('cx', p.get('x', 0)) * escala),
                   'cy': int(p.get('cy', p.get('y', 0)) * escala),
                   'w': max(1, int(p.get('w', 12) * escala)),
                   'h': max(1, int(p.get('h', p.get('w', 12)) * escala))}
                  for p in pads_a or []]
        pads_b = [{**p, 'cx': int(p.get('cx', p.get('x', 0)) * escala),
                   'cy': int(p.get('cy', p.get('y', 0)) * escala),
                   'w': max(1, int(p.get('w', 12) * escala)),
                   'h': max(1, int(p.get('h', p.get('w', 12)) * escala))}
                  for p in pads_b or []]

    # imagem base + heatmap das diferenças
    vis = cv2.addWeighted(ia, 1.0 - alpha, res.heatmap, alpha, 0)
    # pads A em verde (ref), pads B em vermelho (alvo, mapeados pela homografia)
    vis = _desenhar_pads_sobre(vis, pads_a or [], (0, 255, 0), w, h, rotulo=True)
    vis = _desenhar_pads_sobre(vis, pads_b or [], (0, 120, 255), w, h)

    # estatísticas no canto
    txt = f"diff: {res.pct_diff:.1f}% | inliers: {res.score}"
    cv2.putText(vis, txt, (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.rectangle(vis, (6, h - 26), (6 + len(txt) * 8, h - 6), (0, 0, 0), -1)
    cv2.putText(vis, txt, (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA)
    return vis


def resumo_diff_por_pad(res: DiffResult, pads_a: List[Dict[str, Any]],
                        pads_b: List[Dict[str, Any]],
                        w_img_b: int) -> List[Dict[str, Any]]:
    """Para cada pad de A, verifica se há diferença correspondente em B.

    Retorna lista de dicts com id, diff_maximo, tem_diferenca.
    """
    resumo: List[Dict[str, Any]] = []
    mascara = res.mascara
    for p in pads_a or []:
        cx = int(p.get('cx', p.get('x', 0)))
        cy = int(p.get('cy', p.get('y', 0)))
        w = max(1, int(p.get('w', 12)))
        h = max(1, int(p.get('h', w)))
        x0, y0 = max(0, cx - w // 2), max(0, cy - h // 2)
        x1, y1 = min(mascara.shape[1], cx + w // 2), min(mascara.shape[0], cy + h // 2)
        regiao = mascara[y0:y1, x0:x1]
        diff_maximo = float(np.max(res.mapa_diff[y0:y1, x0:x1])) if regiao.size else 0.0
        pct = float(np.sum(regiao > 0) / max(1, regiao.size))
        tem = pct > 0.15  # >15% da área do pad diferente
        resumo.append({
            'id': p.get('id'),
            'cx': cx, 'cy': cy,
            'diff_maximo': diff_maximo,
            'pct_diferenca': pct,
            'tem_diferenca': bool(tem),
        })
    return resumo
