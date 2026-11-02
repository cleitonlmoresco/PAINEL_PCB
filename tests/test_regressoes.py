"""Regressoes da auditoria v11.4: bugs corrigidos em units/loader/saver/transform/widgets."""
import os

import cv2
import numpy as np


def test_units_notacao_resistiva_R(tmp_path):
    from core.units import parse_qty
    assert parse_qty('4R7') == 4.7
    assert parse_qty('0R1') == 0.1
    assert parse_qty('4k7') == 4700.0
    assert parse_qty('2.4g') == 2.4e9
    assert parse_qty('10k') == 10000.0
    assert parse_qty('1M5') == 1500000.0


def test_models_csv_celula_vazia(tmp_path):
    from core.models import Pad
    p = Pad.from_csv_row({'id': '3', 'x': '10.5', 'y': '20', 'w': '', 'h': None, 'area': '90.9', 'manual': 'N'})
    assert (p.id, p.cx, p.w, p.area) == (3, 10, 12, 90)
    assert p.manual is False


def test_loader_bom_e_coluna_manual_ausente(tmp_path):
    from storage.loader import carregar_pads_csv
    # BOM do Excel + coluna manual presente
    csv1 = tmp_path / 'bom.csv'
    csv1.write_text('id,x,y,w,h,area,manual,pino,gnd,link\n1,10,20,10,10,100,S,1,S,abc\n2,50,20,10,10,100,N,,N,\n', encoding='utf-8-sig')
    pads = carregar_pads_csv(str(csv1))
    assert len(pads) == 2
    assert pads[0]['pino'] == '1' and pads[0]['gnd'] and pads[0]['link'] == 'abc'
    assert not pads[1]['manual']
    # CSV antigo SEM coluna manual: nao pode marcar tudo como feito a mao
    csv2 = tmp_path / 'velho.csv'
    csv2.write_text('id,x,y,w,h,area\n1,10,20,10,10,100\n2,50,20,10,10,100\n', encoding='utf-8')
    pads = carregar_pads_csv(str(csv2))
    assert len(pads) == 2 and all(not p['manual'] for p in pads)


def test_loader_linha_curta_nao_descarta_medicao(tmp_path):
    from storage.loader import carregar_medicoes_e_nets
    csv = tmp_path / 'med.csv'
    csv.write_text(
        'id,x,y,manual,status,familia_id,familia_nome,V,Hz,forma,obs_ligada,R_ohm,continuidade,capacitancia,diodo_Vf,obs_desligada,net_ids,conecta_com\n'
        '1,10,20,S,OK,7,GND,3.30,1k,quadrado,,,,,,,abc\n'
        '2,50,20,S,SUSP,7,GND,1.10', encoding='utf-8')
    meas, nets = carregar_medicoes_e_nets(str(csv))
    assert 1 in meas and 2 in meas
    assert meas[2]['status'] == 'SUSP'
    assert nets and nets[0]['id'] == 7


def test_roundtrip_csv_preserva_pino_gnd_link(tmp_path):
    from storage.loader import carregar_pads_csv, carregar_componentes_csv
    from storage.saver import salvar_csvs, salvar_componentes_csv
    pads = [{'id': 1, 'x': 10, 'y': 20, 'w': 10, 'h': 10, 'area': 100, 'manual': True, 'pino': '1', 'gnd': True, 'link': 'uid-1'},
            {'id': 2, 'x': 50, 'y': 20, 'w': 10, 'h': 10, 'area': 100, 'manual': False, 'pino': '', 'gnd': False, 'link': ''}]
    salvar_csvs(pads, {1: {'status': 'OK'}}, [{'id': 7, 'nome': 'GND', 'cor': [100, 100, 100], 'pads': [1]}], str(tmp_path))
    pr = carregar_pads_csv(str(tmp_path / 'pads_final.csv'))
    assert pr[0]['pino'] == '1' and pr[0]['gnd'] and pr[0]['link'] == 'uid-1' and pr[0]['manual']
    # round-trip de componentes: cor/datasheet/pino1/sugestao
    comps = [{'id': 1, 'nome': 'U7', 'tipo': 'ci', 'forma': 'retangulo_h', 'cor': [80, 255, 120], 'pads': [1, 2],
              'valor': 'LM358', 'tensao': '', 'obs': '', 'marcacao': 'LM358', 'datasheet': 'C:\\x\\LM358.pdf',
              'pino1': 1, 'sugestao': 'marcacao de CI (68%)'}]
    salvar_componentes_csv(comps, str(tmp_path))
    c = carregar_componentes_csv(str(tmp_path / 'componentes_final.csv'))[0]
    assert c['cor'] == [80, 255, 120] and c['datasheet'] == 'C:\\x\\LM358.pdf' and c['pino1'] == 1 and c['sugestao']


def test_transform_rejeita_homografia_degenerada(tmp_path):
    from core.transform import _alinhar_interno
    # identidade: mesma imagem deve alinhar
    rng = np.random.default_rng(7)
    img = np.full((400, 500, 3), (40, 90, 40), np.uint8)
    for yy in range(4):
        for xx in range(5):
            cv2.circle(img, (60 + xx * 90, 60 + yy * 90), 8, (210, 210, 210), -1)
    H, n = _alinhar_interno(img, img.copy())
    assert H is not None and n > 20
    # imagem vazia (sem features) nao deve produzir H
    blank = np.full((400, 500, 3), 15, np.uint8)
    H2, n2 = _alinhar_interno(img, blank)
    assert H2 is None


def test_geometry_tamanho_zero(tmp_path):
    from core.geometry import Viewport
    v = Viewport(0, 0, 1000, 800, 300)
    assert v.base_scale > 0


def test_detector_imagem_minuscula(tmp_path):
    from core.detector import detectar_pads_com_mascara_v84
    img = np.full((14, 12, 3), 200, np.uint8)
    pads, _ = detectar_pads_com_mascara_v84(img, scale=0.05)
    assert pads == []


def test_detector_ia_dedup_por_iou(tmp_path):
    from core.detector_ia import DetectorIA
    a = {'cx': 100, 'cy': 100, 'w': 20, 'h': 20, 'area': 400}
    b = {'cx': 116, 'cy': 100, 'w': 20, 'h': 20, 'area': 400}  # IoU ~0.17, centro 16>=14
    c = {'cx': 100, 'cy': 102, 'w': 20, 'h': 20, 'area': 400}  # centro < 14
    assert DetectorIA._duplicada(a, c, 14)
    assert not DetectorIA._duplicada(a, b, 14)


def test_sidebar_nao_clica_fora_da_area_visivel(tmp_path, monkeypatch):
    from core import prefs as prefs_lib
    prefs_lib.ARQ = str(tmp_path / 'cfg.json'); prefs_lib.ARQ_AUTO = str(tmp_path / 'auto.json')
    from ui.sidebar import criar_sidebar_padrao
    sb = criar_sidebar_padrao(700, 0, 320, 700, 1.0)
    sb.layout(700, 0, 320, 700, 1.0)
    # botao da secao VISAO (fora da area visivel no layout inicial)
    btn = next(b for b in sb.buttons if b.action == 'toggle_ids')
    x, y, w, h = btn.rect
    assert not sb._visible(y, h)
    assert sb.handle_click(x + w // 2, y + h // 2) is None
    # clique no header NAO dispara toggle de secao invisivel
    assert sb.handle_click(710, 10) is None


def test_rail_offset_na_conversao_de_coordenadas():
    """Rail a esquerda desloca o canvas: ida e volta devem ser consistentes."""
    from app.app import AppV101
    app = AppV101.__new__(AppV101)
    app.base_scale = 0.5; app.zoom = 1.0
    app.pan_x = 10; app.pan_y = 20; app.rail_w = 62
    sx, sy = app._orig_to_disp(100, 120)
    assert sx == int(100 * 0.5 + 10 + 62)
    assert sy == int(120 * 0.5 + 20)
    ox, oy = app._disp_to_orig(sx, sy)
    assert (ox, oy) == (100, 120)


def test_gpu_reconhece_vendor_e_software():
    from core.gpu import _vendor_do_nome, _eh_software
    assert _vendor_do_nome('Ellesmere') == 'AMD'
    assert _vendor_do_nome('AMD Radeon RX 580') == 'AMD'
    assert _vendor_do_nome('NVIDIA GeForce RTX 3060') == 'NVIDIA'
    assert _vendor_do_nome('Intel(R) UHD Graphics 620') == 'Intel'
    assert _vendor_do_nome('Apple M2') == 'Apple'
    assert _eh_software('llvmpipe (LLVM 15.0.7, 256 bits)')
    assert not _eh_software('Ellesmere')
    from core import gpu
    info = gpu.detectar()
    assert 'modo' in info and 'device' in info and 'vendor' in info

