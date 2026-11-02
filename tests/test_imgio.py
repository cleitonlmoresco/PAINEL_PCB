import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.imgio import imwrite, ler_imagem


def test_unicode_path_roundtrip(tmp_path):
    pasta = tmp_path / 'placas eletrônicas'
    pasta.mkdir()
    caminho = pasta / 'foto_çãõ.jpg'
    img = np.zeros((40, 60, 3), np.uint8)
    img[:, :] = (10, 200, 30)
    assert imwrite(str(caminho), img)
    lida = ler_imagem(str(caminho))
    assert lida is not None
    assert lida.shape[:2] == (40, 60)
    # cv2.imread direto falha ou funciona dependendo do Windows; nosso leitor deve funcionar sempre
