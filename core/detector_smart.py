"""Detector 'smart' de pads: iluminação adaptativa, forma, espessura e furo.

Diferenças vs detector clássico (limiar fixo):
- Limiar de metal automático (Otsu entre pixels de baixa saturação);
- Remove texto/trilhas finas pela espessura (distance transform);
- Detecta e rejeita vias/furos (contorno com furo interno);
- Classifica forma (circulo/retangulo/oval) e ângulo;
- Score de confiança por pad;
- Modo 'por exemplo': template matching multi-escala a partir de um pad real.
"""
from __future__ import annotations

import cv2
import numpy as np


def _limiar_metal(img_bgr):
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    S = hsv[:, :, 1]; V = hsv[:, :, 2]
    baixa = S < 110
    amostra = V[baixa] if int(baixa.sum()) > 200 else V.ravel()
    try:
        thr, _ = cv2.threshold(amostra.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    except Exception:
        thr = 140.0
    return float(np.clip(thr, 80, 225))


def detectar_pads_smart(img_bgr, escala=1.0, sensibilidade=0.55, area_min=6, area_max=1500,
                        nms=10, rejeitar_vias=True, usar_gpu=False):
    """Retorna (pads, mascara). Pads incluem score, forma e angulo."""
    s = max(0.2, min(1.0, float(escala)))
    h0, w0 = img_bgr.shape[:2]
    img = img_bgr if s >= 0.999 else cv2.resize(img_bgr, (max(1, int(w0 * s)), max(1, int(h0 * s))), interpolation=cv2.INTER_AREA)
    # Pre-processamento na VRAM quando disponivel (AMD/Intel/NVIDIA via OpenCL).
    # Se o driver falhar, repete em CPU sem interromper a deteccao.
    hsv = None; mask_green = None
    kc = max(5, int(25 * s / 0.6) | 1)
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kc, kc))
    if usar_gpu:
        try:
            u = cv2.UMat(img)
            u_hsv = cv2.cvtColor(u, cv2.COLOR_BGR2HSV)
            u_mask = cv2.inRange(u_hsv, np.array([35, 20, 20], np.uint8), np.array([90, 255, 255], np.uint8))
            u_mask = cv2.morphologyEx(u_mask, cv2.MORPH_CLOSE, k_close, iterations=3)
            hsv = u_hsv.get(); mask_green = u_mask.get()
        except Exception:
            hsv = None; mask_green = None
    if hsv is None:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask_green = cv2.inRange(hsv, np.array([35, 20, 20]), np.array([90, 255, 255]))
        mask_green = cv2.morphologyEx(mask_green, cv2.MORPH_CLOSE, k_close, iterations=3)
    H, S, V = cv2.split(hsv)

    # ROI = placa (verde), com folga
    cnts, _ = cv2.findContours(mask_green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    roi = np.zeros(mask_green.shape, np.uint8)
    area_placa = roi.shape[0] * roi.shape[1]
    maior_verde = max((cv2.contourArea(c) for c in cnts), default=0.0)
    # so confia no ROI se o contorno verde maior for de fato uma placa (>=3% da imagem);
    # ruido verde minutilo restringiria a busca a uma celula falsa e perderia quase tudo
    if cnts and maior_verde >= 0.03 * area_placa:
        maior_idx = int(np.argmax([cv2.contourArea(c) for c in cnts]))
        cv2.drawContours(roi, [cnts[maior_idx]], -1, 255, -1)
        ke = max(3, int(18 * s / 0.6) | 1)
        roi = cv2.erode(roi, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ke, ke)), iterations=1)
    else:
        roi[:] = 255

    thr = _limiar_metal(img)
    sens = float(np.clip(sensibilidade, 0.0, 1.0))
    # base parecida com o detector clássico, mas adaptativa
    brilho_min = float(np.clip(thr * (1.05 - 0.25 * sens), 115, 150))
    sat_max = int(np.clip(45 + 45 * sens, 45, 90))
    metal = ((S < sat_max) & (V > brilho_min) & (V < 252)).astype(np.uint8) * 255
    metal = cv2.bitwise_and(metal, roi)
    # remove texto/trilhas finas
    metal = cv2.morphologyEx(metal, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)
    metal = cv2.morphologyEx(metal, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)

    dist = cv2.distanceTransform(metal, cv2.DIST_L2, 5)
    cnts, hier = cv2.findContours(metal, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    hier = hier[0] if hier is not None else []

    furos = {}
    for i, c in enumerate(cnts):
        if hier[i][3] != -1:
            pai = hier[i][3]
            furos[pai] = furos.get(pai, 0) + cv2.contourArea(c)

    pads = []
    for i, cnt in enumerate(cnts):
        if hier[i][3] != -1:
            continue
        area = cv2.contourArea(cnt)
        area_orig = area / (s * s)
        if area_orig < area_min or area_orig > area_max:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 3 or h < 3:
            continue
        local_dist = dist[y:y + h, x:x + w]
        espessura = 2.0 * float(local_dist.max()) if local_dist.size else 0.0
        local_V = V[y:y + h, x:x + w]; local_S = S[y:y + h, x:x + w]
        perim = cv2.arcLength(cnt, True)
        circularidade = 4 * np.pi * area / (perim * perim) if perim > 0 else 0
        hull = cv2.convexHull(cnt); ha = cv2.contourArea(hull)
        solidez = area / ha if ha > 0 else 0
        extensao = area / (w * h) if w * h > 0 else 0
        aspecto = max(w, h) / max(1, min(w, h))
        ratio_furo = furos.get(i, 0) / area if area > 0 else 0
        v_medio = float(local_V.mean()) if local_V.size else 0
        s_medio = float(local_S.mean()) if local_S.size else 0
        esp_rel = espessura / max(1.0, float(min(w, h)))
        rect = cv2.minAreaRect(cnt)
        (rcx, rcy), (rw2, rh2), ang = rect
        preench_rect = area / max(1.0, rw2 * rh2)

        # texto de serigrafia/trilhas: traco fino relativo ao tamanho
        if esp_rel < 0.32 and area_orig < 900:
            continue
        if extensao < 0.50:
            continue
        # texto e trilhas: muito fino, muito alongado ou escuro
        if aspecto > 5.0 or solidez < 0.55:
            continue
        if v_medio < 155 and area_orig < 200:
            continue
        if espessura < 2.6 * max(0.75, s) and area_orig < 150:
            continue
        # vias/furos: aro com furo interno grande
        tem_furo = ratio_furo > 0.18
        if tem_furo and rejeitar_vias:
            continue

        # retangulo minimo (orientacao)
        if circularidade >= 0.82:
            forma = 'circulo'
        elif preench_rect >= 0.82 and extensao >= 0.75:
            forma = 'retangulo'
        elif extensao >= 0.6:
            forma = 'oval'
        else:
            forma = 'poligono'

        score = 0.40 * solidez + 0.25 * min(1.0, circularidade) + 0.20 * min(1.0, espessura / 6.0) + 0.15 * min(1.0, extensao)
        if tem_furo:
            score *= 0.6
        if score < 0.40:
            continue

        M = cv2.moments(cnt)
        if M['m00'] == 0:
            continue
        cx = int((M['m10'] / M['m00']) / s)
        cy = int((M['m01'] / M['m00']) / s)
        pads.append({
            'cx': cx, 'cy': cy, 'w': int(w / s), 'h': int(h / s), 'area': int(area_orig),
            'score': round(float(score), 3), 'forma': forma,
            'angulo': round(float(ang), 1), 'via': bool(tem_furo), 'manual': False,
        })

    pads.sort(key=lambda p: p['score'], reverse=True)
    keep = []
    d = max(4, int(nms))
    for p in pads:
        if any(np.hypot(p['cx'] - q['cx'], p['cy'] - q['cy']) < d for q in keep):
            continue
        keep.append(p)
    keep.sort(key=lambda p: (p['cy'] // 80, p['cx']))
    mask_full = metal if (s >= 0.999) else cv2.resize(metal, (w0, h0), interpolation=cv2.INTER_NEAREST)
    return keep, mask_full


def detectar_por_exemplo(img_bgr, cx, cy, w, h, sensibilidade=0.72, max_pads=800):
    """Template matching multi-escala a partir de um pad de referencia (coordenadas originais).

    Busca em resolução reduzida (rápido), com máximos locais e NMS; retorna coordenadas originais.
    """
    h_img, w_img = img_bgr.shape[:2]
    bw = max(4, int(w)); bh = max(4, int(h))
    x1 = max(0, int(cx - bw / 2)); y1 = max(0, int(cy - bh / 2))
    x2 = min(w_img, x1 + bw); y2 = min(h_img, y1 + bh)
    templ = img_bgr[y1:y2, x1:x2]
    if templ.shape[0] < 4 or templ.shape[1] < 4:
        return [], None
    # reduz para busca rápida
    fator = min(1.0, 1600.0 / max(h_img, w_img))
    busca = img_bgr if fator >= 0.999 else cv2.resize(img_bgr, (int(w_img * fator), int(h_img * fator)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(busca, cv2.COLOR_BGR2GRAY)
    tg = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
    bw_s = max(3, int(round(bw * fator))); bh_s = max(3, int(round(bh * fator)))
    escalas = (0.7, 0.85, 1.0, 1.2, 1.45)
    achados = []
    for sc in escalas:
        tw = max(3, int(bw_s * sc)); th = max(3, int(bh_s * sc))
        if tw >= gray.shape[1] or th >= gray.shape[0]:
            continue
        t = cv2.resize(tg, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
        # máximos locais acima do limiar
        picos = (res == cv2.dilate(res, np.ones((3, 3), np.uint8))) & (res >= float(sensibilidade))
        ys, xs = np.where(picos)
        for yy, xx in zip(ys, xs):
            achados.append((float(res[yy, xx]), int((xx + tw / 2) / fator), int((yy + th / 2) / fator)))
    achados.sort(key=lambda t: t[0], reverse=True)
    keep = []
    dmin = max(8, int(min(bw, bh) * 0.9))
    for v, px, py in achados:
        if all(np.hypot(px - k[1], py - k[2]) > dmin for k in keep):
            keep.append((v, px, py))
        if len(keep) >= max_pads:
            break
    pads = [{'cx': px, 'cy': py, 'w': bw, 'h': bh, 'area': bw * bh, 'score': round(v, 3),
             'forma': 'exemplo', 'manual': False} for v, px, py in keep]
    pads.sort(key=lambda p: (p['cy'] // 80, p['cx']))
    return pads, None
