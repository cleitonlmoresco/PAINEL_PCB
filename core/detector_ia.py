"""Inferência de pads com modelo YOLO exportado para ONNX (cv2.dnn, sem torch)."""
from __future__ import annotations

import os

import cv2
import numpy as np


def _letterbox(img, size):
    h, w = img.shape[:2]
    r = min(size / max(1, w), size / max(1, h))
    nw, nh = max(1, int(round(w * r))), max(1, int(round(h * r)))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.full((size, size, 3), 114, np.uint8)
    dx = (size - nw) // 2; dy = (size - nh) // 2
    canvas[dy:dy + nh, dx:dx + nw] = resized
    return canvas, r, dx, dy


def _tiles(h, w, tile, overlap):
    if h <= tile and w <= tile:
        return [(0, 0, w, h)]
    passo = max(64, tile - overlap)
    xs = list(range(0, max(1, w - tile + 1), passo))
    ys = list(range(0, max(1, h - tile + 1), passo))
    if xs[-1] + tile < w:
        xs.append(w - tile)
    if ys[-1] + tile < h:
        ys.append(h - tile)
    return [(x, y, min(tile, w - x), min(tile, h - y)) for y in ys for x in xs]


class DetectorIA:
    """Carrega um .onnx YOLOv8/11 (detecção) e procura pads em tiles."""

    def __init__(self, caminho, tile=1024, overlap=128, size=None):
        if not caminho or not os.path.exists(caminho):
            raise FileNotFoundError(caminho)
        self.caminho = caminho
        self.net = cv2.dnn.readNetFromONNX(caminho)
        self.backend = 'CPU'
        self._configurar_backend()
        meta = os.path.splitext(caminho)[0] + '.json'
        if size is None:
            size = 1024
            try:
                if os.path.exists(meta):
                    import json
                    with open(meta, encoding='utf-8') as f:
                        size = int(json.load(f).get('imgsz') or 1024)
            except Exception:
                size = 1024
        self.tile = int(tile); self.overlap = int(overlap); self.size = int(size)

    def _configurar_backend(self):
        """Usa VRAM por padrao: CUDA (NVIDIA) > OpenCL (AMD/Intel/NVIDIA) > CPU."""
        try:
            if getattr(cv2, 'cuda', None) is not None and cv2.cuda.getCudaEnabledDeviceCount() > 0 \
                    and hasattr(cv2.dnn, 'DNN_BACKEND_CUDA') and hasattr(cv2.dnn, 'DNN_TARGET_CUDA'):
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
                self.backend = 'CUDA'
                return
        except Exception:
            pass
        try:
            if cv2.ocl.haveOpenCL() and cv2.ocl.useOpenCL():
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_OPENCL)
                self.backend = 'OPENCL'
                return
        except Exception:
            pass
        try:
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        except Exception:
            pass
        self.backend = 'CPU'

    def _infer(self, crop):
        lb, r, dx, dy = _letterbox(crop, self.size)
        blob = cv2.dnn.blobFromImage(lb, 1 / 255.0, (self.size, self.size), swapRB=True, crop=False)
        self.net.setInput(blob)
        try:
            out = np.asarray(self.net.forward())
        except Exception:
            # driver OpenCL/CUDA instavel: cai para CPU sem derrubar o app
            try:
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                self.backend = 'CPU'
                out = np.asarray(self.net.forward())
            except Exception:
                return []
        # Alguns drivers AMD falham ao compilar kernels do DNN e devolvem saida
        # vazia sem excecao. Detecta e repete na CPU uma vez.
        if self.backend != 'CPU':
            try:
                _o = out[0] if out.ndim == 3 else out
                if _o.shape[0] < _o.shape[1]:
                    _o = _o.T
                if _o.size == 0 or float(_o[:, 4:].max()) < 1e-4:
                    self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                    self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                    self.backend = 'CPU'
                    self.net.setInput(blob)
                    out = np.asarray(self.net.forward())
            except Exception:
                pass
        if out.ndim == 3:
            out = out[0]
        if out.shape[0] < out.shape[1]:
            out = out.T  # (N, 4+nc)
        if out.shape[1] < 5:
            return []
        cxcywh = out[:, :4]
        scores = out[:, 4:]
        cls = np.argmax(scores, axis=1)
        conf = np.max(scores, axis=1)
        res = []
        for (cx, cy, bw, bh), c, k in zip(cxcywh, conf, cls):
            x = (cx - bw / 2 - dx) / r
            y = (cy - bh / 2 - dy) / r
            w = bw / r; h = bh / r
            res.append((x, y, w, h, float(c), int(k)))
        return res

    def detectar(self, img_bgr, conf=0.35, nms=14, area_min=6, area_max=3000):
        h, w = img_bgr.shape[:2]
        bruto = []
        for (tx, ty, tw, th) in _tiles(h, w, self.tile, self.overlap):
            crop = img_bgr[ty:ty + th, tx:tx + tw]
            if crop.shape[0] < 16 or crop.shape[1] < 16:
                continue
            for (bx, by, bw, bh, c, k) in self._infer(crop):
                if c < conf:
                    continue
                area = bw * bh
                if area < area_min or area > area_max:
                    continue
                bruto.append({'cx': int(tx + bx + bw / 2), 'cy': int(ty + by + bh / 2),
                              'w': max(2, int(bw)), 'h': max(2, int(bh)), 'area': int(area),
                              'score': round(c, 3), 'manual': False})
        bruto.sort(key=lambda p: p['score'], reverse=True)
        keep = []
        d = max(4, int(nms))
        for p in bruto:
            if any(self._duplicada(p, q, d) for q in keep):
                continue
            keep.append(p)
        keep.sort(key=lambda p: (p['cy'] // 80, p['cx']))
        return keep, None

    @staticmethod
    def _duplicada(p, q, d_centro):
        """Duplicado se centros colidem OU caixas se sobrepoe (pad cortado na costura dos tiles, idem vias)."""
        if np.hypot(p['cx'] - q['cx'], p['cy'] - q['cy']) < d_centro:
            return True
        ax1, ay1 = p['cx'] - p['w'] / 2.0, p['cy'] - p['h'] / 2.0
        ax2, ay2 = p['cx'] + p['w'] / 2.0, p['cy'] + p['h'] / 2.0
        bx1, by1 = q['cx'] - q['w'] / 2.0, q['cy'] - q['h'] / 2.0
        bx2, by2 = q['cx'] + q['w'] / 2.0, q['cy'] + q['h'] / 2.0
        iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
        ih = max(0.0, min(ay2, by2) - max(ay1, by1))
        inter = iw * ih
        if inter <= 0:
            return False
        uniao = p['area'] + q['area'] - inter
        return uniao > 0 and (inter / uniao) > 0.45
