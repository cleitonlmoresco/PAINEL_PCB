import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import transform


def _placa_sintetica():
    img = np.full((320, 420, 3), 40, np.uint8)
    rng = np.random.default_rng(7)
    for _ in range(40):
        x = int(rng.integers(20, 380)); y = int(rng.integers(20, 280))
        cv2.circle(img, (x, y), int(rng.integers(3, 9)), (200, 200, 200), -1)
        cv2.rectangle(img, (x - 10, y - 10), (x + 10, y + 10), (120, 160, 120), 1)
    return img


def test_alinhar_e_transferir():
    img = _placa_sintetica()
    M = np.float32([[1.08, 0, 14], [0, 1.05, -9]])
    novo = cv2.warpAffine(img, M, (440, 340))
    H = transform.alinhar(img, novo)
    assert H is not None
    pads = [{'id': 1, 'cx': 100, 'cy': 100}, {'id': 2, 'cx': 300, 'cy': 200}]
    novos = transform.transferir_pads(pads, H)
    esperado = cv2.transform(np.float32([[[100, 100]], [[300, 200]]]), M).reshape(-1, 2)
    for p, e in zip(novos, esperado):
        assert abs(p['cx'] - e[0]) < 6, (p, e)
        assert abs(p['cy'] - e[1]) < 6, (p, e)


def test_centroides_csv(tmp_path):
    csv = tmp_path / 'pos.csv'
    csv.write_text('Ref,Mid X,Mid Y,Side\nR1,10,20,top\nC1,30,40,bottom\n', encoding='utf-8')
    linhas = transform.ler_centroides_csv(str(csv))
    assert len(linhas) == 2
    assert linhas[0]['ref'] == 'R1'
    pts = transform.encaixar_centroides(linhas, 400, 300, 0.0)
    assert len(pts) == 2
    assert 0 <= pts[0]['x'] <= 400 and 0 <= pts[0]['y'] <= 300
    # lado bottom deve ser espelhado
    pts2 = transform.encaixar_centroides([
        {'ref': 'A', 'x': 10, 'y': 20, 'side': 'top'},
        {'ref': 'B', 'x': 10, 'y': 20, 'side': 'bottom'},
    ], 400, 300, 1.0)
    assert abs((pts2[0]['x'] + pts2[1]['x']) - 400) <= 1
