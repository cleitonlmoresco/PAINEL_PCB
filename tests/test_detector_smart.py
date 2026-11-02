import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.detector_smart import detectar_pads_smart, detectar_por_exemplo


def _placa():
    img = np.full((420, 520, 3), (30, 100, 30), np.uint8)
    # pads SMD (retangulos claros)
    pos = []
    for gy in range(60, 380, 60):
        for gx in range(50, 470, 60):
            cv2.rectangle(img, (gx, gy), (gx + 12, gy + 8), (210, 210, 210), -1)
            pos.append((gx + 6, gy + 4))
    # texto fino (deve ser ignorado)
    cv2.putText(img, 'R12 C34', (60, 410), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 1)
    # via: anel claro com furo escuro no centro
    cv2.circle(img, (470, 60), 12, (220, 220, 220), 4)
    cv2.circle(img, (470, 60), 5, (30, 100, 30), -1)
    return img, pos


def test_smart_detecta_pads_e_rejeita_via():
    img, pos = _placa()
    pads, mask = detectar_pads_smart(img, escala=1.0, sensibilidade=0.55, area_min=20, area_max=600, nms=10, rejeitar_vias=True)
    assert len(pads) >= len(pos) - 6, len(pads)
    # via nao deve aparecer com rejeitar_vias
    assert all(np.hypot(p['cx'] - 470, p['cy'] - 60) > 14 for p in pads)
    # pads reais devem estar perto das posicoes conhecidas
    for (px, py) in pos[:6]:
        assert any(np.hypot(p['cx'] - px, p['cy'] - py) < 8 for p in pads), (px, py)


def test_smart_por_exemplo():
    img = np.full((240, 320, 3), (30, 100, 30), np.uint8)
    centros = []
    for gx, gy in ((40, 40), (120, 40), (200, 40), (40, 140), (120, 140)):
        cv2.rectangle(img, (gx, gy), (gx + 12, gy + 10), (215, 215, 215), -1)
        centros.append((gx + 6, gy + 5))
    pads, _ = detectar_por_exemplo(img, centros[0][0], centros[0][1], 14, 12, sensibilidade=0.75)
    assert len(pads) >= 4, len(pads)
    for (px, py) in centros:
        assert any(np.hypot(p['cx'] - px, p['cy'] - py) < 6 for p in pads), (px, py)
