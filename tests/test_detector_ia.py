import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import detector_ia


def test_meta_imgsz(tmp_path, monkeypatch):
    onnx = tmp_path / 'pads.onnx'
    onnx.write_bytes(b'fake')
    (tmp_path / 'pads.json').write_text('{"imgsz": 512}', encoding='utf-8')
    monkeypatch.setattr(cv2.dnn, 'readNetFromONNX', lambda p: object())
    det = detector_ia.DetectorIA(str(onnx))
    assert det.size == 512
    det2 = detector_ia.DetectorIA(str(onnx), size=640)
    assert det2.size == 640


def test_letterbox_e_tiles():
    img = np.zeros((300, 500, 3), np.uint8)
    lb, r, dx, dy = detector_ia._letterbox(img, 256)
    assert lb.shape == (256, 256, 3)
    tiles = detector_ia._tiles(3000, 4000, 1024, 128)
    assert tiles and all(t[2] <= 1024 and t[3] <= 1024 for t in tiles)
    # cobertura total
    assert min(t[0] for t in tiles) == 0 and min(t[1] for t in tiles) == 0
    assert max(t[0] + t[2] for t in tiles) >= 4000 - 1
