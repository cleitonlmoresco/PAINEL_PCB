import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dataset import exportar_projetos, pre_anotar_album
from core.imgio import imwrite


def _projeto(tmp_path):
    proj = tmp_path / 'projeto ção'
    proj.mkdir()
    pasta_img = proj / 'imagens'; pasta_img.mkdir()
    img = np.full((300, 400, 3), (30, 100, 30), np.uint8)
    pads = []
    for i, (x, y) in enumerate(((60, 60), (160, 60), (260, 60), (60, 180), (160, 180), (260, 180))):
        cv2.rectangle(img, (x, y), (x + 14, y + 10), (215, 215, 215), -1)
        pads.append({'id': i + 1, 'cx': x + 7, 'cy': y + 5, 'w': 14, 'h': 10, 'area': 140})
    img_path = pasta_img / 'placa.jpg'
    imwrite(str(img_path), img)
    sess = proj / 'sessao_v87.json'
    sess.write_text(json.dumps({'views': {'frente': {'img_path': 'imagens/placa.jpg', 'pads': pads,
                                                     'measurements': {}, 'nets': [], 'componentes': []}},
                                'view_atual': 'frente'}), encoding='utf-8')
    return proj


def test_exportar_projetos(tmp_path):
    proj = _projeto(tmp_path)
    destino = tmp_path / 'dataset'
    stats = exportar_projetos([str(proj)], str(destino), tile=256, overlap=32, val_ratio=0.0)
    assert stats['imagens'] == 1
    assert stats['pads'] == 6
    assert stats['tiles'] >= 1
    assert os.path.exists(destino / 'data.yaml')
    labels = list((destino / 'labels' / 'train').glob('*.txt'))
    assert labels
    linhas = [l for f in labels for l in f.read_text().splitlines() if l.strip()]
    assert linhas
    for ln in linhas:
        partes = ln.split()
        assert len(partes) == 5 and partes[0] == '0'
        for v in partes[1:]:
            assert 0.0 <= float(v) <= 1.0


def test_pre_anotar_album_unicode(tmp_path):
    fotos = tmp_path / 'album placas ção'
    fotos.mkdir()
    img = np.full((240, 320, 3), (30, 100, 30), np.uint8)
    for x, y in ((40, 40), (120, 40), (200, 40)):
        cv2.rectangle(img, (x, y), (x + 14, y + 10), (215, 215, 215), -1)
    imwrite(str(fotos / 'foto1.jpg'), img)
    imwrite(str(fotos / 'foto2.jpg'), img)
    destino = tmp_path / 'ds_album'
    stats = pre_anotar_album(str(fotos), str(destino), tile=256, overlap=32, escala=1.0,
                             min_nitidez=0, min_mascara=0.0, min_pads=2, min_resolucao=0)
    assert stats['imagens'] == 2
    assert stats['tiles'] >= 2
    assert stats['pads'] >= 4
    assert os.path.exists(destino / 'data.yaml')
