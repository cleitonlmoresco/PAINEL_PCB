"""Alinhamento de imagens e importação de centroides (CSV/KiCad)."""
from __future__ import annotations

import csv
import os

import cv2
import numpy as np


def _alinhar_interno(img_orig, img_novo):
    if img_orig is None or img_novo is None:
        return None, 0
    g1 = cv2.cvtColor(img_orig, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(img_novo, cv2.COLOR_BGR2GRAY)
    s = 1.0
    maior = max(g1.shape)
    if maior > 1600:
        s = 1600.0 / maior
        g1 = cv2.resize(g1, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        g2 = cv2.resize(g2, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    orb = cv2.ORB_create(4000)
    k1, d1 = orb.detectAndCompute(g1, None)
    k2, d2 = orb.detectAndCompute(g2, None)
    if d1 is None or d2 is None or len(k1) < 8 or len(k2) < 8:
        return None, 0
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    pares = bf.knnMatch(d1, d2, k=2)
    bons = [m for par in pares if len(par) == 2 for m, n in [par] if m.distance < 0.75 * n.distance]
    if len(bons) < 8:
        return None, 0
    src = np.float32([k1[m.queryIdx].pt for m in bons]).reshape(-1, 1, 2)
    dst = np.float32([k2[m.trainIdx].pt for m in bons]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    if H is None:
        return None, 0
    # saneamento: homografia degradada (padroes repetitivos) manda pads p/ fora da imagem.
    # Aceita apenas H que projeta os cantos da referencia proximo da imagem alvo.
    try:
        det = float(np.linalg.det(H[:2, :2]))
        if not np.isfinite(det) or det < 1e-4 or det > 1e4:
            return None, 0
        cantos = np.float32([[0, 0], [g1.shape[1], 0], [0, g1.shape[0]], [g1.shape[1], g1.shape[0]]]).reshape(-1, 1, 2)
        proj = cv2.perspectiveTransform(cantos, H).reshape(-1, 2)
        h_n, w_n = g2.shape[:2]
        dentro = (proj[:, 0].max() <= w_n * 1.35 and proj[:, 0].min() >= -w_n * 0.35
                  and proj[:, 1].max() <= h_n * 1.35 and proj[:, 1].min() >= -h_n * 0.35)
        if not dentro:
            return None, 0
    except Exception:
        return None, 0
    score = int(mask.sum()) if mask is not None else 0
    if s != 1.0:
        S = np.array([[s, 0, 0], [0, s, 0], [0, 0, 1]], dtype=np.float64)
        S_inv = np.array([[1.0 / s, 0, 0], [0, 1.0 / s, 0], [0, 0, 1]], dtype=np.float64)
        H = S_inv @ H @ S
    return H, score


def alinhar(img_orig, img_novo):
    """Estima homografia entre duas fotos da mesma placa (ORB + RANSAC)."""
    H, _ = _alinhar_interno(img_orig, img_novo)
    return H


def alinhar_melhor(img_orig, img_novo, tentar_espelho=True):
    """Alinha testando a imagem normal e espelhada (frente x verso).

    Retorna (H, espelhado, inliers). Se espelhado=True, o mapa é:
      ponto_destino = (largura_novo - x', y')  onde (x',y') = H * ponto_origem
    """
    H1, n1 = _alinhar_interno(img_orig, img_novo)
    melhor = (H1, False, n1) if H1 is not None else (None, False, 0)
    if tentar_espelho:
        H2, n2 = _alinhar_interno(img_orig, cv2.flip(img_novo, 1))
        if H2 is not None and (melhor[0] is None or n2 > melhor[2]):
            melhor = (H2, True, n2)
    return melhor


def aplicar_h(H, pontos):
    if H is None or not pontos:
        return []
    pts = np.float32([[p[0], p[1]] for p in pontos]).reshape(-1, 1, 2)
    out = cv2.perspectiveTransform(pts, H).reshape(-1, 2)
    return [(float(x), float(y)) for x, y in out]


def transferir_pads(pads, H):
    pts = aplicar_h(H, [(p.get('cx', 0), p.get('cy', 0)) for p in pads])
    novos = []
    for p, (x, y) in zip(pads, pts):
        q = dict(p)
        q['cx'] = int(round(x)); q['cy'] = int(round(y))
        q['x'] = q['cx']; q['y'] = q['cy']
        novos.append(q)
    return novos


def transferir_componentes(comps, H):
    novos = []
    for c in comps:
        pts = aplicar_h(H, [(c.get('x1', 0), c.get('y1', 0)), (c.get('x2', 0), c.get('y2', 0))])
        if len(pts) != 2:
            continue
        q = dict(c)
        q['x1'], q['y1'] = int(round(pts[0][0])), int(round(pts[0][1]))
        q['x2'], q['y2'] = int(round(pts[1][0])), int(round(pts[1][1]))
        novos.append(q)
    return novos


def ler_centroides_csv(caminho):
    """Lê centroides de CSV (KiCad pos / genérico): ref, x, y, lado."""
    linhas = []
    try:
        with open(caminho, encoding='utf-8-sig', errors='ignore') as f:
            amostra = f.read(8192)
            f.seek(0)
            delim = ';' if amostra.count(';') > amostra.count(',') else ','
            rd = csv.DictReader(f, delimiter=delim)
            cols = {str(c).strip().lower(): c for c in (rd.fieldnames or []) if c}

            def get(row, *nomes):
                for n in nomes:
                    if n in cols:
                        return row.get(cols[n], '')
                return ''

            for row in rd:
                try:
                    ref = get(row, 'ref', 'reference', 'designator', 'refdes', 'reference(s)', 'component')
                    x = get(row, 'mid x', 'x', 'posx', 'pos_x', 'at x', 'center x', 'x (mm)', 'x(mm)')
                    y = get(row, 'mid y', 'y', 'posy', 'pos_y', 'at y', 'center y', 'y (mm)', 'y(mm)')
                    lado = str(get(row, 'side', 'layer', 'camada', 'side (f/b)')).strip().lower()
                    x = float(str(x).replace(',', '.'))
                    y = float(str(y).replace(',', '.'))
                    linhas.append({'ref': ref.strip(), 'x': x, 'y': y, 'side': lado})
                except Exception:
                    continue
    except Exception:
        return []
    return linhas


def encaixar_centroides(linhas, w_img, h_img, mm_por_px=0.0):
    """Converte centroides (mm) para pixels, com espelhamento do lado inferior."""
    if not linhas:
        return []
    if mm_por_px and mm_por_px > 0:
        pts = [(l['x'] / mm_por_px, l['y'] / mm_por_px, l) for l in linhas]
    else:
        xs = [l['x'] for l in linhas]; ys = [l['y'] for l in linhas]
        minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
        sx = (w_img * 0.8) / max(1e-6, maxx - minx)
        sy = (h_img * 0.8) / max(1e-6, maxy - miny)
        s = min(sx, sy)
        ox = (w_img - (maxx - minx) * s) / 2.0
        oy = (h_img - (maxy - miny) * s) / 2.0
        pts = [((l['x'] - minx) * s + ox, (l['y'] - miny) * s + oy, l) for l in linhas]
    out = []
    for x, y, l in pts:
        lado = str(l.get('side', '')).lower()
        if lado in ('bottom', 'back', 'b', 'bot', 'inferior'):
            x = w_img - x
        out.append({'ref': l.get('ref', ''), 'x': int(round(x)), 'y': int(round(y))})
    return out
