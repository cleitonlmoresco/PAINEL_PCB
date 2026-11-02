import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.detector import detectar_pads_com_mascara_v84, detectar_pads_tiles


def test_tiles_encontra_pads():
    img = np.full((640, 900, 3), (30, 90, 30), np.uint8)
    rng = np.random.default_rng(3)
    for _ in range(60):
        x = int(rng.integers(30, 860)); y = int(rng.integers(30, 600))
        cv2.rectangle(img, (x, y), (x + 10, y + 7), (200, 200, 200), -1)
    pads = detectar_pads_tiles(img, tile=320, overlap=60, brilho_min=140, brilho_max=255,
                               sat_max=60, area_min=20, area_max=400, nms_dist=12, reject_vias=False)
    assert len(pads) > 20
    # nenhum pad duplicado grosseiramente (NMS por tile)
    for i, p in enumerate(pads):
        for q in pads[i + 1:]:
            assert np.hypot(p['cx'] - q['cx'], p['cy'] - q['cy']) >= 12
