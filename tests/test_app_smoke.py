import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_app_render_e_recursos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import app.app as appmod
    monkeypatch.setattr(appmod.prefs_lib, 'ARQ', str(tmp_path / 'cfg.json'))
    monkeypatch.setattr(appmod.prefs_lib, 'ARQ_AUTO', str(tmp_path / 'auto.json'))
    monkeypatch.setattr(appmod.webbrowser, 'open', lambda *a, **k: True)
    from app.app import AppV101

    img = np.full((900, 700, 3), (30, 90, 30), np.uint8)
    rng = np.random.default_rng(4)
    for _ in range(50):
        x = int(rng.integers(40, 660)); y = int(rng.integers(40, 860))
        cv2.rectangle(img, (x, y), (x + 10, y + 8), (210, 210, 210), -1)
    caminho = tmp_path / 'placa.jpg'
    cv2.imwrite(str(caminho), img)

    app = AppV101(str(caminho))
    assert app._render().shape[:2] == (app.view_h, app.view_w)

    # progresso e proximo sem medir
    app._proximo_sem_medir()
    assert app.right_mode == 'edit'
    app.edit_sliders[0].val = 3.3
    app.edit_status_idx = 1
    app._salvar_edicao()
    med, total, pct, fal = app._progresso()
    assert med == 1 and total == len(app.pads)

    # deteccao por exemplo (usa o 1o pad como template)
    app.selected = 0
    app._detectar_exemplo()
    assert len(app.pads) > 0
    assert app.detector_modo in ('smart', 'classico')

    # paleta de comandos
    app._abrir_paleta()
    app.paleta_cmd['query'] = 'relatorio'
    app._atualizar_paleta()
    assert app.paleta_cmd['itens']

    # camadas
    app._alternar_camada('pads')
    assert app.layers['pads'] in (True, False)

    # todos os botoes visiveis devem ter descricao/tooltip
    from core.presets import DESCRICOES_BOTOES
    botoes = app.botoes_menu + app.botoes_tab + app.botoes_toolbar + app.botoes_filtro
    faltando = [b.key for b in botoes if not (b.tooltip or b.key in DESCRICOES_BOTOES)]
    assert not faltando, faltando
    for b in botoes:
        x, y, w, h = b.rect
        alvo = app._get_tooltip_at(x + w // 2, y + h // 2)
        assert alvo is not None and alvo[0] is not None, b.key
    app.right_mode = 'camadas'; app._render()
    faltando_cam = [b.key for b in app.familia_botoes if not (b.tooltip or b.key in DESCRICOES_BOTOES or b.key.startswith('layer_'))]
    assert not faltando_cam, faltando_cam

    # componente: marcacao, pino 1 e pinagem ordenada
    comp = {'id': 1, 'nome': 'J1', 'tipo': 'conector', 'forma': 'retangulo_v', 'cor': [255, 200, 80],
            'pads': [app.pads[0]['id'], app.pads[1]['id'], app.pads[2]['id']],
            'x1': 0, 'y1': 0, 'x2': 100, 'y2': 100, 'valor': '', 'tensao': '', 'obs': ''}
    app.componentes = [comp]; app.next_comp_id = 2; app.comp_selected = 1
    app.selected = 0
    app._handle_comp_edit('comp_pino1')
    assert comp['pino1'] == app.pads[0]['id']
    lin = app._pinagem_conector(comp)
    assert lin[0]['pad'] == app.pads[0]['id']
    app._iniciar_edicao_componente(1)
    app._start_inline_input('comp_marcacao', 'BC547')
    app._confirm_inline_input()
    assert app.comp_edit_buf_marcacao == 'BC547'
    assert app._render().shape[:2] == (app.view_h, app.view_w)

    # vinculo entre visoes: propagacao de familia e navegacao
    app.view_atual = 'frente'
    p0 = app.pads[0]; p1 = app.pads[1]
    p0['link'] = 'lk_teste'
    app.views_store['verso'] = {
        'img_path': None, 'pads': [{'id': 77, 'cx': 10, 'cy': 10, 'w': 8, 'h': 8, 'link': 'lk_teste'}],
        'nets': [], 'next_net_id': 1, 'measurements': {}, 'componentes': [],
    }
    a = next(i for i, p in enumerate(app.pads) if p.get('id') == p0.get('id'))
    b = next(i for i, p in enumerate(app.pads) if p.get('id') == p1.get('id'))
    app._conectar(a, b)
    net_verso = app.views_store['verso']['nets']
    assert net_verso and 77 in net_verso[0]['pads'], net_verso
    net_frente = next(n for n in app.nets if p0.get('id') in n['pads'])
    assert net_verso[0].get('uid') == net_frente.get('uid')
    net_frente['nome'] = 'VCC'; net_frente['cor'] = [0, 0, 255]
    app._sincronizar_net(net_frente)
    assert net_verso[0]['nome'] == 'VCC'

    # medicao propagada para o pad passante do verso
    app.selected = a
    app._iniciar_edicao(a)
    app.edit_sliders[0].val = 3.3
    app.edit_status_idx = 1
    app._salvar_edicao()
    assert 77 in app.views_store['verso']['measurements'], app.views_store['verso']['measurements']

    app._desconectar(a)
    assert 77 not in (net_verso[0]['pads'] if net_verso else [])

    # navegacao ciclica (sem abrir dialogo)
    chamadas = []
    import types
    def _fake_trocar(self, v):
        chamadas.append(v); self.view_atual = v
    app._trocar_view = types.MethodType(_fake_trocar, app)
    app.view_atual = 'frente'
    app._ciclar_view(1); app._ciclar_view(-1)
    assert chamadas == ['verso', 'frente']

    # pasta de projetos + projeto novo a partir de fotos
    ws = tmp_path / 'PROJETOS'; proj = ws / 'IAW 9GV'; proj.mkdir(parents=True)
    cv2.imwrite(str(proj / 'foto1.jpg'), img)
    app.pasta_projetos = str(ws)
    lista = app._listar_projetos()
    assert any(os.path.normcase(os.path.abspath(p['pasta'])) == os.path.normcase(os.path.abspath(str(proj))) and p.get('novo') for p in lista), lista
    ok = app._abrir_projeto(str(proj))
    assert ok
    assert os.path.normcase(os.path.abspath(app.out_dir)) == os.path.normcase(os.path.abspath(str(proj)))
    assert os.path.exists(os.path.join(str(proj), 'sessao_v87.json'))
    assert len(app.pads) > 0

    # paleta de comandos renderiza
    app._abrir_paleta()
    assert app._render().shape[:2] == (app.view_h, app.view_w)

    # relatorio HTML
    app._gerar_relatorio()
    rels = [f for f in os.listdir(app.out_dir) if f.startswith('relatorio_')]
    assert rels, os.listdir(app.out_dir)
