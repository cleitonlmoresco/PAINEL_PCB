"""Testes de importacao/exportacao KiCad, Eagle e Gerber."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import kicad


def _placa_exemplo():
    pads = [
        {'id': 1, 'cx': 100, 'cy': 120, 'x': 100, 'y': 120, 'w': 12, 'h': 12, 'area': 144,
         'manual': False, 'pino': '1', 'forma': 'circulo'},
        {'id': 2, 'cx': 160, 'cy': 120, 'x': 160, 'y': 120, 'w': 12, 'h': 12, 'area': 144,
         'manual': False, 'pino': '2', 'forma': 'circulo'},
        {'id': 3, 'cx': 400, 'cy': 300, 'x': 400, 'y': 300, 'w': 20, 'h': 10, 'area': 200,
         'manual': False, 'pino': 'A', 'forma': 'retangulo'},
    ]
    comps = [
        {'id': 1, 'nome': 'R1', 'tipo': 'resistor', 'pads': [1, 2], 'x1': 94, 'y1': 114,
         'x2': 166, 'y2': 126},
        {'id': 2, 'nome': 'J1', 'tipo': 'conector', 'pads': [3], 'x1': 390, 'y1': 295,
         'x2': 410, 'y2': 305},
    ]
    nets = [
        {'id': 1, 'nome': 'GND', 'pads': [2]},
        {'id': 2, 'nome': 'VCC', 'pads': [1, 3]},
    ]
    return pads, comps, nets


def test_exportar_kicad_estrutura(tmp_path):
    pads, comps, nets = _placa_exemplo()
    destino = tmp_path / 'placa.kicad_pcb'
    res = kicad.exportar_kicad(pads, comps, nets, str(destino), mm_por_px=0.1,
                               w_px=800, h_px=600)
    assert os.path.exists(destino)
    assert res['pads'] == 3
    assert res['nets'] == 2
    texto = destino.read_text(encoding='utf-8')
    assert '(kicad_pcb' in texto
    assert '"GND"' in texto and '"VCC"' in texto
    assert '(footprint "AnotadorPad:R1"' in texto
    assert 'Edge.Cuts' in texto
    # nomes de pad preservados
    assert '(pad "A"' in texto


def test_roundtrip_kicad(tmp_path):
    pads, comps, nets = _placa_exemplo()
    destino = tmp_path / 'placa.kicad_pcb'
    kicad.exportar_kicad(pads, comps, nets, str(destino), mm_por_px=0.1, w_px=800, h_px=600)

    res = kicad.importar_kicad(str(destino), w_img=800, h_img=600, mm_por_px=0.1)
    assert len(res['pads']) == 3
    assert res['escala'] == 0.1

    orig = {(p['cx'], p['cy']) for p in pads}
    novos = {(p['cx'], p['cy']) for p in res['pads']}
    for (x, y) in orig:
        assert any(abs(x - nx) <= 1 and abs(y - ny) <= 1 for nx, ny in novos), (x, y, novos)

    nomes = {n['nome'] for n in res['nets']}
    assert nomes == {'GND', 'VCC'}
    refs = {c['nome'] for c in res['componentes']}
    assert refs == {'R1', 'J1'}
    assert len(res['pads']) == len({p['id'] for p in res['pads']})


def test_exportar_gerber_e_reimportar(tmp_path):
    pads, _comps, _nets = _placa_exemplo()
    destino = tmp_path / 'cobre.gbr'
    res = kicad.exportar_gerber(pads, str(destino), mm_por_px=0.1, w_px=800, h_px=600)
    assert res['pads'] == 3
    assert res['aperturas'] >= 2
    texto = destino.read_text(encoding='utf-8')
    assert '%FSLAX46Y46*%' in texto and 'D03*' in texto

    volta = kicad.importar_gerber(str(destino), w_img=800, h_img=600, mm_por_px=0.1)
    assert len(volta['pads']) == 3
    orig = {(p['cx'], p['cy']) for p in pads}
    novos = {(p['cx'], p['cy']) for p in volta['pads']}
    for (x, y) in orig:
        assert any(abs(x - nx) <= 1 and abs(y - ny) <= 1 for nx, ny in novos), (x, y, novos)


def test_importar_eagle(tmp_path):
    brd = tmp_path / 'placa.brd'
    brd.write_text("""<?xml version="1.0" encoding="utf-8"?>
<eagle version="9.6">
  <drawing>
    <board>
      <libraries>
        <library name="conectores">
          <packages>
            <package name="P2">
              <pad name="1" x="0" y="0" drill="1.0" diameter="1.8"/>
              <pad name="2" x="2.54" y="0" drill="1.0" diameter="1.8"/>
            </package>
          </packages>
        </library>
      </libraries>
      <elements>
        <element name="J1" library="conectores" package="P2" x="10" y="20" rot="R0"/>
      </elements>
      <signals>
        <signal name="GND"><contactref element="J1" pad="1"/></signal>
        <signal name="VCC"><contactref element="J1" pad="2"/></signal>
      </signals>
    </board>
  </drawing>
</eagle>
""", encoding='utf-8')

    res = kicad.importar_eagle(str(brd), w_img=800, h_img=600)
    assert len(res['pads']) == 2
    assert res['componentes'][0]['nome'] == 'J1'
    assert {n['nome'] for n in res['nets']} == {'GND', 'VCC'}
    # os dois pads ficam na mesma linha (R0) e o pad 2 a direita do pad 1
    assert res['pads'][0]['cy'] == res['pads'][1]['cy']
    assert res['pads'][0]['cx'] < res['pads'][1]['cx']


def test_detectar_formato(tmp_path):
    k = tmp_path / 'a.kicad_pcb'
    k.write_text('(kicad_pcb (version 20240108))', encoding='utf-8')
    g = tmp_path / 'b.gbr'
    g.write_text('%FSLAX46Y46*%\n%MOMM*%\n', encoding='utf-8')
    e = tmp_path / 'c.brd'
    e.write_text('<eagle></eagle>', encoding='utf-8')
    assert kicad.detectar_formato(str(k)) == 'kicad'
    assert kicad.detectar_formato(str(g)) == 'gerber'
    assert kicad.detectar_formato(str(e)) == 'eagle'


def test_importar_arquivo_desconhecido(tmp_path):
    p = tmp_path / 'x.txt'
    p.write_text('nada aqui', encoding='utf-8')
    res = kicad.importar_arquivo(str(p), w_img=400, h_img=300)
    assert res['pads'] == []
    assert res['formato'] == 'desconhecido'
    assert res['avisos']
