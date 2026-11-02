import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _novo_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import app.app as appmod
    monkeypatch.setattr(appmod.prefs_lib, 'ARQ', str(tmp_path / 'cfg.json'))
    monkeypatch.setattr(appmod.prefs_lib, 'ARQ_AUTO', str(tmp_path / 'auto.json'))
    monkeypatch.setattr(appmod.webbrowser, 'open', lambda *a, **k: True)
    from app.app import AppV101

    img = np.full((600, 800, 3), (35, 80, 35), np.uint8)
    caminho = tmp_path / 'placa.jpg'
    cv2.imwrite(str(caminho), img)
    app = AppV101(str(caminho))
    app.pads = [
        {'id': 1, 'cx': 100, 'cy': 100, 'x': 100, 'y': 100, 'w': 10, 'h': 10, 'area': 80, 'link': 'lk_a'},
        {'id': 2, 'cx': 140, 'cy': 100, 'x': 140, 'y': 100, 'w': 10, 'h': 10, 'area': 80},
        {'id': 3, 'cx': 180, 'cy': 100, 'x': 180, 'y': 100, 'w': 10, 'h': 10, 'area': 80},
    ]
    app.next_id = 4
    app.nets = []
    app.measurements = {}
    app.componentes = [{
        'id': 1, 'nome': 'J1', 'tipo': 'conector', 'forma': 'retangulo_v',
        'cor': [255, 200, 80], 'pads': [1, 2, 3], 'pino1': 2,
        'x1': 80, 'y1': 70, 'x2': 210, 'y2': 130, 'valor': '', 'tensao': '', 'obs': '',
    }]
    app.next_comp_id = 2
    app.comp_selected = 1
    app.views_store['verso'] = {
        'img_path': None,
        'pads': [{'id': 77, 'cx': 30, 'cy': 30, 'w': 8, 'h': 8, 'link': 'lk_a'}],
        'nets': [], 'next_net_id': 1, 'measurements': {}, 'componentes': [],
        'anotacoes': [], 'next_anot_id': 1,
    }
    return app


def test_anotacoes_pinos_gnd_e_propagacao(tmp_path, monkeypatch):
    app = _novo_app(tmp_path, monkeypatch)
    app._trocar_aba('anotar')

    # anotacao livre: criar, confirmar, editar e remover
    app._criar_anotacao(120, 140, '')
    app.inline_input_buffer = 'Verificar C12'
    app._confirm_inline_input()
    assert len(app.anotacoes) == 1
    assert app.anotacoes[0]['text'] == 'Verificar C12'
    assert app.anot_selected == app.anotacoes[0]['id']
    a = app.anotacoes[0]
    app._editar_anotacao(a)
    app.inline_input_buffer = 'C12 aberto'
    app._confirm_inline_input()
    assert a['text'] == 'C12 aberto'
    # desenho da anotacao
    canvas = app._render()
    assert canvas.shape[:2] == (app.view_h, app.view_w)

    # arrastar anotacao no modo navegar
    app.mode = 'navegar'
    bx, by, bw, bh = app._anot_display_rect(a)
    ox0, oy0 = a['x'], a['y']
    app._on_mouse(cv2.EVENT_LBUTTONDOWN, bx + bw // 2, by + bh // 2, 0, None)
    assert app.drag_mode == 'anot'
    app._on_mouse(cv2.EVENT_MOUSEMOVE, bx + bw // 2 + 30, by + bh // 2 + 20, 0, None)
    app._on_mouse(cv2.EVENT_LBUTTONUP, bx + bw // 2 + 30, by + bh // 2 + 20, 0, None)
    assert (a['x'], a['y']) != (ox0, oy0)
    app._undo()
    a = app.anotacoes[0]
    assert (a['x'], a['y']) == (ox0, oy0)

    # nomear pino e marcar GND
    app._nomear_pino_pad(0)
    app.inline_input_buffer = 'A3'
    app._confirm_inline_input()
    assert app.pads[0]['pino'] == 'A3'
    app._toggle_gnd_pad(0)
    assert app.pads[0]['gnd'] is True
    # propagou para o pad passante do verso
    verso = app.views_store['verso']['pads'][0]
    assert verso.get('pino') == 'A3' and verso.get('gnd') is True

    # relatorio inclui anotacao, pino e GND
    app._gerar_relatorio()
    rel = next(os.path.join(app.out_dir, f) for f in os.listdir(app.out_dir) if f.startswith('relatorio_'))
    html = open(rel, encoding='utf-8').read()
    assert 'C12 aberto' in html
    assert 'A3' in html
    assert 'GND' in html

    # desmarcar GND tambem propaga (sem apagar o nome do pino)
    app._toggle_gnd_pad(0)
    assert not app.pads[0].get('gnd')
    assert not verso.get('gnd')
    assert app.pads[0].get('pino') == 'A3' and verso.get('pino') == 'A3'

    # numeracao automatica comeca pelo pino 1 (pad 2)
    app._numerar_pinos_componente()
    assert app.pads[1].get('pino') == '1'
    assert app.pads[0].get('pino') == '2'
    assert app.pads[2].get('pino') == '3'

    # painel lateral/menu e menus contextuais renderizam
    app.right_mode = 'menu'
    app._render()
    top_painel = 60
    app.sidebar.layout(app.left_w, top_painel, app.right_w, app.view_h - 36 - top_painel, app.font_scale)
    # FIX v11.4: cliques fantasma em botoes fora da area visivel foram bloqueados;
    # rolar a sidebar ate a secao VISAO antes de clicar
    sec_y = app.sidebar.section_rects['VISAO'][1]
    app.sidebar.scroll = max(0, sec_y - 80)
    app.sidebar.layout(app.left_w, top_painel, app.right_w, app.view_h - 36 - top_painel, app.font_scale)
    btn = next(b for b in app.sidebar.buttons if b.action == 'toggle_ids')
    bx, by, bw, bh = btn.rect
    assert app.sidebar._visible(by, bh)
    antes = app.show_ids
    app._on_mouse(cv2.EVENT_LBUTTONDOWN, bx + bw // 2, by + bh // 2, 0, None)
    assert app.show_ids != antes
    app.right_mode = 'inspetor'

    # clique direito no pad abre menu; clique no item marca GND
    app.selected = 0
    app.pads[0].pop('gnd', None)
    app.context_menu_pad.bounds = (app.view_w, app.view_h)
    sx, sy = app._orig_to_disp(app.pads[0]['cx'], app.pads[0]['cy']); sy += app._oy_off()
    app._on_mouse(cv2.EVENT_RBUTTONDOWN, sx, sy, 0, None)
    assert app.context_menu_pad.visible
    itens = app.context_menu_pad.items
    idx = next(i for i, it in enumerate(itens) if it[2] == 'gnd_toggle')
    rx, ry, rw, rh = app.context_menu_pad.rect
    app._on_mouse(cv2.EVENT_LBUTTONDOWN, rx + 20, ry + 5 + idx * 30 + 15, 0, None)
    assert app.pads[0].get('gnd') is True
    assert not app.context_menu_pad.visible

    # CSV inclui pino, GND e link
    from storage.saver import salvar_csvs
    from storage.loader import carregar_pads_csv
    app.pads[0]['gnd'] = True
    out_csv = tmp_path / 'csv'
    salvar_csvs(app.pads, app.measurements, app.nets, str(out_csv))
    lidos = {p['id']: p for p in carregar_pads_csv(str(out_csv / 'pads_final.csv'))}
    assert lidos[1].get('pino') == '2'
    assert lidos[1].get('gnd') is True
    assert lidos[1].get('link') == 'lk_a'

    # remover anotacao
    app._remover_anotacao()
    assert not app.anotacoes


def test_anotacao_cancelada_nao_fica_vazia(tmp_path, monkeypatch):
    app = _novo_app(tmp_path, monkeypatch)
    app._criar_anotacao(50, 50, '')
    assert len(app.anotacoes) == 1
    app._cancel_inline_input()
    assert not app.anotacoes


def test_reconhecimento_de_componentes(tmp_path, monkeypatch):
    app = _novo_app(tmp_path, monkeypatch)
    app._trocar_aba('anotar')
    casos = [
        ({'id': 10, 'nome': 'U7', 'marcacao': 'LM358', 'valor': '', 'forma': 'retangulo_h',
          'pads': [1, 2, 3, 4, 5, 6, 7, 8]}, 'ci'),
        ({'id': 11, 'nome': 'R5', 'marcacao': '', 'valor': '10k', 'forma': 'quadrado',
          'pads': [1, 2]}, 'resistor'),
        ({'id': 12, 'nome': 'C12', 'marcacao': '', 'valor': '100nF', 'forma': 'circulo',
          'pads': [1, 2]}, 'capacitor'),
        ({'id': 13, 'nome': 'Q1', 'marcacao': 'BC547', 'valor': '', 'forma': 'hexagono',
          'pads': [1, 2, 3]}, 'transistor'),
        ({'id': 14, 'nome': 'D3', 'marcacao': '1N4148', 'valor': '', 'forma': 'triangulo',
          'pads': [1, 2]}, 'diodo'),
        ({'id': 15, 'nome': 'J2', 'marcacao': '', 'valor': '', 'forma': 'retangulo_v',
          'pads': [1, 2, 3, 4, 5, 6]}, 'conector'),
    ]
    app.componentes = []
    for comp, esperado in casos:
        comp.setdefault('tensao', ''); comp.setdefault('obs', '')
        comp.setdefault('x1', 0); comp.setdefault('y1', 0); comp.setdefault('x2', 50); comp.setdefault('y2', 50)
        tipo, motivo, conf, valor = app._sugerir_tipo_componente(comp)
        assert tipo == esperado, (comp['nome'], tipo, motivo, conf)
        assert conf >= 60 and motivo
        app.componentes.append(comp)
        app.comp_selected = comp['id']
        app._reconhecer_componente(comp)
        assert comp['tipo'] == esperado
        assert comp.get('sugestao')

    # pino 1 heuristico: pad retangular no topo de um componente vertical
    app.pads = [
        {'id': 1, 'cx': 100, 'cy': 100, 'x': 100, 'y': 100, 'w': 12, 'h': 12, 'area': 120, 'forma': 'retangulo'},
        {'id': 2, 'cx': 100, 'cy': 124, 'x': 100, 'y': 124, 'w': 10, 'h': 10, 'area': 90, 'forma': 'circulo'},
        {'id': 3, 'cx': 100, 'cy': 148, 'x': 100, 'y': 148, 'w': 10, 'h': 10, 'area': 90, 'forma': 'circulo'},
    ]
    comp = {'id': 20, 'nome': 'J3', 'tipo': 'conector', 'forma': 'retangulo_v',
            'x1': 90, 'y1': 90, 'x2': 110, 'y2': 160, 'pads': [1, 2, 3], 'pino1': None}
    app.componentes.append(comp); app.comp_selected = 20
    app._auto_pino1_componente(comp)
    assert comp['pino1'] == 1

    # botoes do editor de componente respondem ao mouse
    app.comp_selected = 10
    app._iniciar_edicao_componente(10)
    btn_nome = next(b for b in app.comp_edit_field_btns if b.key == 'comp_field_nome')
    bx, by, bw, bh = btn_nome.rect
    app._on_mouse(cv2.EVENT_LBUTTONDOWN, bx + bw // 2, by + bh // 2, 0, None)
    assert app.inline_input_active and app.inline_input_field == 'comp_nome'
    app._cancel_inline_input()
    app.comp_selected = 10
    app._iniciar_edicao_componente(10)
    btn_rec = next(b for b in app.comp_edit_action_btns if b.key == 'comp_reconhecer')
    bx, by, bw, bh = btn_rec.rect
    app._on_mouse(cv2.EVENT_LBUTTONDOWN, bx + bw // 2, by + bh // 2, 0, None)
    comp10 = next(c for c in app.componentes if c['id'] == 10)
    assert comp10['tipo'] == 'ci'

    # clique numa linha da lista de componentes abre o editor
    app.comp_selected = None; app.comp_edit_field_btns = []
    app.right_mode = 'componentes'
    app._render()
    y0 = app._toolbar_h() + 58
    app._on_mouse(cv2.EVENT_LBUTTONDOWN, app.left_w + 20, y0 + 14, 0, None)
    assert app.comp_selected == 10
    assert app.comp_edit_field_btns


def test_datasheet_livre_por_part_number(tmp_path, monkeypatch):
    app = _novo_app(tmp_path, monkeypatch)
    chamadas = []
    import core.datasheet as ds
    monkeypatch.setattr(ds, 'buscar_datasheet', lambda termo, limite=8: chamadas.append((termo, limite)) or [])
    app.componentes = []
    app.comp_selected = None
    app._datasheet_livre()
    assert app.inline_input_active and app.inline_input_field == 'datasheet_termo'
    app.inline_input_buffer = 'BC547'
    app._confirm_inline_input()
    assert chamadas and chamadas[0][0] == 'BC547'

