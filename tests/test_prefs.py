import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import prefs


def test_roundtrip(tmp_path, monkeypatch):
    arq = tmp_path / 'cfg.json'
    monkeypatch.setattr(prefs, 'ARQ', str(arq))
    cfg = prefs.carregar()
    assert cfg['show_ids'] is True
    cfg['show_ids'] = False
    cfg['mm_por_px'] = 0.042
    prefs.salvar(cfg)
    cfg2 = prefs.carregar()
    assert cfg2['show_ids'] is False
    assert abs(cfg2['mm_por_px'] - 0.042) < 1e-9


def test_recentes(tmp_path, monkeypatch):
    arq = tmp_path / 'cfg2.json'
    monkeypatch.setattr(prefs, 'ARQ', str(arq))
    cfg = prefs.carregar()
    d1 = tmp_path / 'proj1'; d1.mkdir()
    d2 = tmp_path / 'proj2'; d2.mkdir()
    prefs.adicionar_recente(cfg, str(d1))
    prefs.adicionar_recente(cfg, str(d2))
    prefs.adicionar_recente(cfg, str(d1))
    assert cfg['recentes'][0].endswith('proj1')
    assert len(cfg['recentes']) == 2
    assert cfg['ultimo_projeto'].endswith('proj1')


def test_autosave(tmp_path, monkeypatch):
    arq = tmp_path / 'auto.json'
    monkeypatch.setattr(prefs, 'ARQ_AUTO', str(arq))
    prefs.salvar_autosave(str(tmp_path / 'p'), {'a': 1})
    d = prefs.carregar_autosave()
    assert d['payload'] == {'a': 1}
    prefs.limpar_autosave()
    assert prefs.carregar_autosave() is None
