import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.report import gerar_html


def test_relatorio(tmp_path):
    views = {
        'frente': {
            'pads': [{'id': 1}, {'id': 2}, {'id': 3}],
            'measurements': {'1': {'status': 'OK'}, '2': {'status': 'FALHA'}},
            'nets': [{'id': 1, 'nome': 'VCC', 'pads': [1, 2]}],
            'componentes': [{'id': 1, 'nome': 'C1', 'tipo': 'capacitor', 'valor': '100nF', 'tensao': '16V', 'pads': [1]}],
        },
        'verso': {'pads': [], 'measurements': {}, 'nets': [], 'componentes': []},
    }
    destino = tmp_path / 'rel.html'
    r = gerar_html(str(destino), str(tmp_path), views, {'projeto_nome': 'teste'}, 0.05)
    assert r and os.path.exists(r)
    txt = open(r, encoding='utf-8').read()
    assert 'Relatório do Projeto' in txt
    assert 'VCC' in txt
    assert 'C1' in txt
    assert 'OK 1' in txt and 'FALHA 1' in txt
    assert 'FRENTE' in txt and 'VERSO' in txt
