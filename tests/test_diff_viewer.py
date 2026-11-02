"""Testes para o módulo de Diff Viewer (frente x verso)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from core import diff_viewer


def _fundo_com_pad(cx, cy, w=20, h=20, cor=(100, 100, 100)):
    img = np.full((400, 400, 3), 30, dtype=np.uint8)
    cv2.rectangle(img, (cx - w // 2, cy - h // 2), (cx + w // 2, cy + h // 2), cor, -1)
    return img


def test_calcular_diff_imagens_iguais():
    img = _fundo_com_pad(200, 200)
    res = diff_viewer.calcular_diff(img, img.copy(), threshold=30)
    assert res.similaridade > 0.99
    assert res.pct_diff < 5.0
    assert res.H is not None


def test_calcular_diff_com_mudanca():
    base = _fundo_com_pad(200, 200, cor=(100, 100, 100))
    alterada = base.copy()
    cv2.rectangle(alterada, (190, 190), (210, 210), (200, 200, 200), -1)
    res = diff_viewer.calcular_diff(base, alterada, threshold=30)
    assert res.pct_diff > 0
    assert res.heatmap is not None
    assert res.mascara is not None


def test_desenhar_lado_a_lado():
    img_a = _fundo_com_pad(200, 200)
    img_b = _fundo_com_pad(200, 200, cor=(110, 110, 110))
    res = diff_viewer.calcular_diff(img_a, img_b, threshold=30)
    pads_a = [{'id': 1, 'cx': 200, 'cy': 200, 'w': 20, 'h': 20}]
    pads_b = [{'id': 1, 'cx': 200, 'cy': 200, 'w': 20, 'h': 20}]
    canvas = diff_viewer.desenhar_diff_lado_a_lado(res, pads_a, pads_b, w_max=400)
    assert canvas.shape[2] == 3
    assert canvas.shape[0] > 0 and canvas.shape[1] > 0


def test_desenhar_sobreposto():
    img_a = _fundo_com_pad(200, 200)
    img_b = _fundo_com_pad(200, 200, cor=(110, 110, 110))
    res = diff_viewer.calcular_diff(img_a, img_b, threshold=30)
    pads_a = [{'id': 1, 'cx': 200, 'cy': 200, 'w': 20, 'h': 20}]
    pads_b = [{'id': 1, 'cx': 200, 'cy': 200, 'w': 20, 'h': 20}]
    canvas = diff_viewer.desenhar_diff_sobreposto(res, pads_a, pads_b, alpha=0.5, w_max=400)
    assert canvas.shape[2] == 3


def test_resumo_diff_por_pad():
    base = np.full((400, 400), 100, dtype=np.uint8)
    alterada = base.copy()
    cv2.rectangle(alterada, (190, 190), (210, 210), 200, -1)  # mudança no pad 1
    # precisa de imagens coloridas para calcular_diff (converte interno)
    base_c = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    alt_c = cv2.cvtColor(alterada, cv2.COLOR_GRAY2BGR)
    res = diff_viewer.calcular_diff(base_c, alt_c, threshold=30)
    pads = [{'id': 1, 'cx': 200, 'cy': 200, 'w': 20, 'h': 20}]
    sumario = diff_viewer.resumo_diff_por_pad(res, pads, [], w_img_b=400)
    assert len(sumario) == 1
    assert sumario[0]['tem_diferenca'] is True or sumario[0]['diff_maximo'] > 30


def test_imagens_none_lanca_erro():
    try:
        diff_viewer.calcular_diff(None, np.zeros((100, 100, 3), np.uint8))
        assert False, "deveria levantar ValueError"
    except ValueError:
        pass
