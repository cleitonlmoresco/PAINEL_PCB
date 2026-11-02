"""Criação de dataset YOLO a partir de projetos anotados ou de um álbum de fotos.

- Tiles (recortes) para preservar tamanho real dos pads
- Split treino/validação por imagem de origem (sem vazamento)
- Pré-anotação automática com o detector smart (active learning)
"""
from __future__ import annotations

import glob
import json
import os
import zlib

import cv2

IMG_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.heic', '.heif')


def _resolver_img(caminho, projeto):
    if not caminho:
        return None
    cands = [caminho, os.path.join(projeto, str(caminho))]
    base = os.path.basename(str(caminho))
    for sub in ('imagens', 'images', 'capturas'):
        cands.append(os.path.join(projeto, sub, base))
    for c in cands:
        try:
            if os.path.exists(c):
                return c
        except Exception:
            continue
    return None


def _tiles(h, w, tile=1024, overlap=128):
    if h <= tile and w <= tile:
        return [(0, 0, w, h)]
    passo = max(64, tile - overlap)
    xs = list(range(0, max(1, w - tile + 1), passo))
    ys = list(range(0, max(1, h - tile + 1), passo))
    if xs[-1] + tile < w:
        xs.append(w - tile)
    if ys[-1] + tile < h:
        ys.append(h - tile)
    out = []
    for y in ys:
        for x in xs:
            out.append((x, y, min(tile, w - x), min(tile, h - y)))
    return out


def _labels_tile(pads, tx, ty, tw, th):
    linhas = []
    for p in pads:
        cx = p.get('cx'); cy = p.get('cy')
        if cx is None or cy is None:
            continue
        if not (tx <= cx < tx + tw and ty <= cy < ty + th):
            continue
        w = max(2.0, float(p.get('w', 12) or 12)); h = max(2.0, float(p.get('h', 12) or 12))
        x1 = max(tx, cx - w / 2); x2 = min(tx + tw, cx + w / 2)
        y1 = max(ty, cy - h / 2); y2 = min(ty + th, cy + h / 2)
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        linhas.append((0.5 * (x1 + x2 - tx) / tw, 0.5 * (y1 + y2 - ty) / th,
                       (x2 - x1) / tw, (y2 - y1) / th))
    return linhas


def _split(caminho, val_ratio):
    v = zlib.crc32(os.path.normcase(caminho).encode('utf-8')) % 100
    return 'val' if v < int(round(val_ratio * 100)) else 'train'


def preparar_destino(destino):
    for sub in ('images/train', 'images/val', 'labels/train', 'labels/val'):
        os.makedirs(os.path.join(destino, sub), exist_ok=True)


def escrever_yaml(destino):
    yml = f"""path: {os.path.abspath(destino).replace(chr(92), '/')}
train: images/train
val: images/val
names:
  0: pad
"""
    with open(os.path.join(destino, 'data.yaml'), 'w', encoding='utf-8') as f:
        f.write(yml)
    return os.path.join(destino, 'data.yaml')


def _processar_imagem(caminho, pads, destino, tile, overlap, val_ratio, nome_base, split_forcado=None):
    from core.imgio import ler_imagem, imwrite
    img = ler_imagem(caminho)
    if img is None:
        return 0
    h, w = img.shape[:2]
    split = split_forcado or _split(caminho, val_ratio)
    total = 0
    for i, (x, y, tw, th) in enumerate(_tiles(h, w, tile, overlap)):
        crop = img[y:y + th, x:x + tw]
        if crop.shape[0] < 16 or crop.shape[1] < 16:
            continue
        nome = f"{nome_base}_{i:04d}"
        imwrite(os.path.join(destino, 'images', split, nome + '.jpg'), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
        linhas = _labels_tile(pads, x, y, tw, th)
        with open(os.path.join(destino, 'labels', split, nome + '.txt'), 'w', encoding='utf-8') as f:
            for cx, cy, bw, bh in linhas:
                f.write(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
        total += 1
    return total


def _sessoes_por_pasta(pastas):
    """Retorna (pasta, sessão mais recente) para cada pasta que tem sessões."""
    por_pasta = {}
    for pasta in pastas:
        try:
            achados = glob.glob(os.path.join(pasta, '**', 'sessao_*.json'), recursive=True)
        except Exception:
            achados = []
        for sess in achados:
            d = os.path.dirname(sess)
            chave = os.path.normcase(os.path.abspath(d))
            try:
                mt = os.path.getmtime(sess)
            except Exception:
                mt = 0
            atual = por_pasta.get(chave)
            if atual is None or mt > atual[2]:
                por_pasta[chave] = (d, sess, mt)
    return [(d, s) for d, s, _ in por_pasta.values()]


def exportar_projetos(pastas, destino, tile=1024, overlap=128, val_ratio=0.2, progresso=None):
    """Exporta as anotações dos projetos (todas as visões) para dataset YOLO."""
    preparar_destino(destino)
    stats = {'imagens': 0, 'tiles': 0, 'pads': 0, 'projetos': 0}
    pares = _sessoes_por_pasta(pastas)
    for idx, (projeto, sess) in enumerate(pares):
        try:
            with open(sess, encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
        views = data.get('views') if isinstance(data.get('views'), dict) else None
        if not views:
            views = {'frente': data}
        stats['projetos'] += 1
        for nome_view, vd in views.items():
            img_path = _resolver_img(vd.get('img_path'), projeto)
            pads = vd.get('pads') or []
            if not img_path or not pads:
                continue
            base = f"{os.path.basename(os.path.abspath(projeto))}_{nome_view}".replace(' ', '_')
            n = _processar_imagem(img_path, pads, destino, tile, overlap, val_ratio, base)
            stats['imagens'] += 1; stats['tiles'] += n; stats['pads'] += len(pads)
            if progresso:
                progresso(f"{base}: {n} tiles, {len(pads)} pads")
    escrever_yaml(destino)
    return stats


def avaliar_foto_pcb(img):
    """Heurística de curadoria: nitidez + presença de máscara de solda colorida."""
    if img is None:
        return False, 'ilegivel'
    h, w = img.shape[:2]
    if min(h, w) < 700:
        return False, 'baixa_resolucao'
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    nitidez = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if nitidez < 55:
        return False, 'desfocada'
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    S = hsv[:, :, 1]; V = hsv[:, :, 2]
    mascara = ((S > 60) & (V > 40) & (V < 215))
    ratio = float(mascara.mean())
    if ratio < 0.18:
        return False, 'sem_mascara'
    return True, f'ok_nitidez={nitidez:.0f}_mascara={ratio:.2f}'


def pre_anotar_album(pasta_fotos, destino, tile=1024, overlap=128, val_ratio=0.2,
                     escala=0.7, sensibilidade=0.55, usar_gpu=False, progresso=None,
                     min_pads=12, min_nitidez=55, min_mascara=0.18, min_resolucao=700, curadoria_csv=None):
    """Pré-anota um álbum de fotos com smart + curadoria (nitidez/máscara/pads)."""
    from core.detector_smart import detectar_pads_smart
    from core.imgio import ler_imagem
    preparar_destino(destino)
    fotos = []
    for raiz, _, arquivos in os.walk(pasta_fotos):
        for a in arquivos:
            if a.lower().endswith(IMG_EXTS):
                fotos.append(os.path.join(raiz, a))
    fotos.sort()
    stats = {'imagens': 0, 'tiles': 0, 'pads': 0, 'falhas': 0, 'ignoradas': 0}
    linhas_csv = [('arquivo', 'status', 'motivo', 'pads', 'tiles')]
    for i, caminho in enumerate(fotos):
        img = ler_imagem(caminho)
        if img is None:
            stats['falhas'] += 1
            linhas_csv.append((os.path.basename(caminho), 'falha', 'ilegivel', 0, 0))
            continue
        ok = True; motivo = 'ok'
        h, w = img.shape[:2]
        if min(h, w) < min_resolucao:
            ok, motivo = False, 'baixa_resolucao'
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            nit = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            S = hsv[:, :, 1]; V = hsv[:, :, 2]
            masc = float(((S > 60) & (V > 40) & (V < 215)).mean())
            if nit < min_nitidez:
                ok, motivo = False, 'desfocada'
            elif masc < min_mascara:
                ok, motivo = False, 'sem_mascara'
        if not ok:
            stats['ignoradas'] += 1
            linhas_csv.append((os.path.basename(caminho), 'ignorada', motivo, 0, 0))
            if progresso:
                progresso(f"[{i+1}/{len(fotos)}] IGNORADA ({motivo}): {os.path.basename(caminho)}")
            continue
        try:
            pads, _ = detectar_pads_smart(img, escala=escala, sensibilidade=sensibilidade,
                                          area_min=6, area_max=3000, nms=14,
                                          rejeitar_vias=True, usar_gpu=usar_gpu)
        except Exception:
            stats['falhas'] += 1
            continue
        if len(pads) < min_pads:
            stats['ignoradas'] += 1
            linhas_csv.append((os.path.basename(caminho), 'ignorada', f'poucos_pads({len(pads)})', len(pads), 0))
            if progresso:
                progresso(f"[{i+1}/{len(fotos)}] IGNORADA (pads={len(pads)}): {os.path.basename(caminho)}")
            continue
        base = os.path.splitext(os.path.basename(caminho))[0].replace(' ', '_')
        n = _processar_imagem(caminho, pads, destino, tile, overlap, val_ratio, base)
        stats['imagens'] += 1; stats['tiles'] += n; stats['pads'] += len(pads)
        linhas_csv.append((os.path.basename(caminho), 'ok', 'ok', len(pads), n))
        if progresso:
            progresso(f"[{i+1}/{len(fotos)}] {os.path.basename(caminho)}: {len(pads)} pads, {n} tiles")
    escrever_yaml(destino)
    if curadoria_csv:
        try:
            import csv as _csv
            with open(curadoria_csv, 'w', newline='', encoding='utf-8') as f:
                w = _csv.writer(f); w.writerows(linhas_csv)
        except Exception:
            pass
    return stats
