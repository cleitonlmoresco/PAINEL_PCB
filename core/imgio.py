"""Leitura/escrita de imagens à prova de Unicode e HEIC (Windows).

cv2.imread/imwrite falham em caminhos com acentos; aqui usamos bytes + imdecode/imencode
e, como fallback, Pillow (com suporte a HEIC se pillow-heif estiver instalado).
"""
from __future__ import annotations

import os

import cv2
import numpy as np


def imread(caminho, flags=cv2.IMREAD_COLOR):
    try:
        dados = np.fromfile(str(caminho), dtype=np.uint8)
        if dados.size == 0:
            return None
        return cv2.imdecode(dados, flags)
    except Exception:
        return None


def imwrite(caminho, img, params=None):
    try:
        ext = os.path.splitext(str(caminho))[1] or '.jpg'
        ok, buf = cv2.imencode(ext, img, params or [])
        if not ok:
            return False
        buf.tofile(str(caminho))
        return True
    except Exception:
        return False


def _via_pillow(caminho):
    try:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except Exception:
            pass
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(str(caminho))).convert('RGB')
        return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    except Exception:
        return None


def ler_imagem(caminho):
    """Lê JPG/PNG/BMP/HEIC mesmo com acentos/unicode no caminho."""
    if not caminho or not os.path.exists(str(caminho)):
        return None
    img = imread(caminho)
    if img is not None:
        return img
    return _via_pillow(caminho)
