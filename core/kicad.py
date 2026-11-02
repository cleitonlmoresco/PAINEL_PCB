"""Importacao/exportacao de placas: KiCad (.kicad_pcb), Eagle (.brd) e Gerber (RS-274X).

Sem dependencias externas: o parser de KiCad e um leitor de S-expression proprio
e o de Eagle usa ``xml.etree``. Gerber cobre o subconjunto usado por placas
reais (flashes D03 com aperturas C/R/O).

Convencoes
----------
* Tudo que sai daqui para o app esta em **pixels** da imagem atual.
* A escala vem de ``mm_por_px`` (regua do app). Sem escala calibrada, os
  desenhos sao encaixados na imagem (80% da area) e a escala usada e devolvida.
* Importadores devolvem ``{'pads', 'componentes', 'nets', 'escala', 'avisos'}``
  com indices de pad relativos a lista ``pads`` (0..n-1).
"""
from __future__ import annotations

import math
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    'exportar_kicad',
    'exportar_gerber',
    'importar_kicad',
    'importar_eagle',
    'importar_gerber',
    'importar_arquivo',
    'detectar_formato',
    'FORMATOS',
]

FORMATOS = {
    'kicad': 'KiCad PCB (.kicad_pcb)',
    'eagle': 'Eagle BRD (.brd)',
    'gerber': 'Gerber RS-274X (.gbr/.ger)',
}

_EXT_KICAD = ('.kicad_pcb', '.kicadpcb')
_EXT_EAGLE = ('.brd',)
_EXT_GERBER = ('.gbr', '.ger', '.gbl', '.gtl', '.art', '.pho')


# ============================================================================
# Helpers comuns
# ============================================================================

def _f(valor, padrao: float = 0.0) -> float:
    try:
        return float(str(valor).replace(',', '.'))
    except (TypeError, ValueError):
        return padrao


def _i(valor, padrao: int = 0) -> int:
    try:
        return int(round(float(str(valor).replace(',', '.'))))
    except (TypeError, ValueError):
        return padrao


def _rot(x: float, y: float, graus: float) -> Tuple[float, float]:
    """Rotacao anti-horaria no plano (coordenadas com Y para baixo)."""
    if not graus:
        return x, y
    a = math.radians(graus)
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


def _nome_seguro(texto: Any, limite: int = 60) -> str:
    """Sanitiza nomes para caber em strings do KiCad/Eagle."""
    s = str(texto or '').strip().replace('"', "'")
    s = re.sub(r'[\r\n\t]+', ' ', s)
    return s[:limite]


def _forma_pad(w: float, h: float, forma: str = '') -> str:
    f = str(forma or '').lower()
    if f in ('circulo', 'circle', 'redondo', 'round'):
        return 'circle'
    if f in ('oval', 'oblongo', 'obround', 'ovalado'):
        return 'oval'
    if w > 0 and h > 0 and abs(w - h) <= max(1.0, 0.2 * max(w, h)):
        return 'circle'
    return 'rect'


def _dimensoes_px(p: Dict[str, Any]) -> Tuple[float, float]:
    w = _f(p.get('w'), 0.0)
    h = _f(p.get('h'), 0.0)
    if w <= 0:
        w = max(1.0, _f(p.get('area'), 100.0) ** 0.5)
    if h <= 0:
        h = w
    return w, h


def _centro_px(p: Dict[str, Any]) -> Tuple[float, float]:
    x = p.get('cx', p.get('x'))
    y = p.get('cy', p.get('y'))
    return _f(x), _f(y)


def _encaixar(pontos: List[Tuple[float, float]], w_img: int, h_img: int,
              mm_por_px: float) -> Tuple[List[Tuple[float, float]], float]:
    """Converte mm -> px usando a escala calibrada ou encaixa na imagem.

    Retorna (pontos_px, mm_por_px_usado).
    """
    if not pontos:
        return [], mm_por_px or 0.0
    if mm_por_px and mm_por_px > 0:
        return [(x / mm_por_px, y / mm_por_px) for x, y in pontos], mm_por_px

    w_img = w_img or 1200
    h_img = h_img or 900
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    dx = max(max(xs) - min(xs), 1e-6)
    dy = max(max(ys) - min(ys), 1e-6)
    s = min((w_img * 0.8) / dx, (h_img * 0.8) / dy)
    ox = (w_img - dx * s) / 2.0 - min(xs) * s
    oy = (h_img - dy * s) / 2.0 - min(ys) * s
    return [(x * s + ox, y * s + oy) for x, y in pontos], 1.0 / s


def _montar_resultado(entradas: List[Dict[str, Any]], formato: str,
                      escala: float, avisos: Optional[List[str]] = None) -> Dict[str, Any]:
    """Recebe pads já convertidos para px e monta o dicionario final."""
    pads: List[Dict[str, Any]] = []
    comps: Dict[str, Dict[str, Any]] = {}
    nets: Dict[str, Dict[str, Any]] = {}

    for e in entradas:
        idx = len(pads)
        w = max(1.0, _f(e.get('w'), 12.0))
        h = max(1.0, _f(e.get('h'), w))
        pad = {
            'id': idx,
            'cx': int(round(e['x'])),
            'cy': int(round(e['y'])),
            'x': int(round(e['x'])),
            'y': int(round(e['y'])),
            'w': int(round(w)),
            'h': int(round(h)),
            'area': int(round(w * h)),
            'manual': False,
            'forma': _forma_pad(w, h, e.get('forma', '')),
        }
        pino = _nome_seguro(e.get('pino'), 12)
        if pino:
            pad['pino'] = pino
        ref = _nome_seguro(e.get('ref'), 40)
        if ref:
            pad['ref'] = ref
            c = comps.setdefault(ref, {'nome': ref, 'tipo': 'conector' if _i(pino) else 'ci',
                                      'forma': 'retangulo_h', 'pads': []})
            c['pads'].append(idx)
        net = _nome_seguro(e.get('net'), 60)
        if net:
            n = nets.setdefault(net, {'nome': net, 'pads': []})
            n['pads'].append(idx)
        pads.append(pad)

    componentes = []
    for i, c in enumerate(comps.values(), start=1):
        xs = [pads[k]['cx'] for k in c['pads']]
        ys = [pads[k]['cy'] for k in c['pads']]
        c.update({'id': i, 'x1': min(xs), 'y1': min(ys), 'x2': max(xs), 'y2': max(ys),
                  'cor': [80, 140, 255], 'valor': '', 'tensao': '', 'obs': '',
                  'pino1': c['pads'][0] if c['pads'] else None})
        componentes.append(c)

    lista_nets = []
    for i, n in enumerate(nets.values(), start=1):
        n['id'] = i
        n['cor'] = [80, 140, 255]
        lista_nets.append(n)

    return {
        'formato': formato,
        'pads': pads,
        'componentes': componentes,
        'nets': lista_nets,
        'escala': float(escala or 0.0),
        'avisos': list(avisos or []),
    }


# ============================================================================
# S-Expression (KiCad)
# ============================================================================

def _tokenizar_sexpr(texto: str) -> List[str]:
    tokens: List[str] = []
    i, n = 0, len(texto)
    while i < n:
        c = texto[i]
        if c == '(' or c == ')':
            tokens.append(c)
            i += 1
        elif c == '"':
            i += 1
            buf = []
            while i < n:
                ch = texto[i]
                if ch == '\\' and i + 1 < n:
                    buf.append(texto[i + 1])
                    i += 2
                elif ch == '"':
                    i += 1
                    break
                else:
                    buf.append(ch)
                    i += 1
            tokens.append('\x00' + ''.join(buf))
        elif c in ' \t\r\n':
            i += 1
        else:
            j = i
            while j < n and texto[j] not in ' \t\r\n()"':
                j += 1
            tokens.append(texto[i:j])
            i = j
    return tokens


def _parse_sexpr(texto: str) -> List[Any]:
    tokens = _tokenizar_sexpr(texto)
    raiz: List[Any] = []
    pilha: List[List[Any]] = [raiz]
    for t in tokens:
        if t == '(':
            novo: List[Any] = []
            pilha[-1].append(novo)
            pilha.append(novo)
        elif t == ')':
            if len(pilha) > 1:
                pilha.pop()
        elif t.startswith('\x00'):
            pilha[-1].append(t[1:])
        else:
            pilha[-1].append(t)
    return raiz


def _filhos(no: List[Any], nome: str) -> List[List[Any]]:
    return [c for c in no if isinstance(c, list) and c and c[0] == nome]


def _primeiro(no: List[Any], nome: str) -> Optional[List[Any]]:
    for c in no:
        if isinstance(c, list) and c and c[0] == nome:
            return c
    return None


def _num_at(no: Optional[List[Any]]) -> Tuple[float, float, float]:
    if not no:
        return 0.0, 0.0, 0.0
    vals = [_f(x) for x in no[1:] if not isinstance(x, list)]
    while len(vals) < 3:
        vals.append(0.0)
    return vals[0], vals[1], vals[2]


# ============================================================================
# Exportacao KiCad
# ============================================================================

def exportar_kicad(pads: List[Dict[str, Any]], componentes: List[Dict[str, Any]],
                   nets: List[Dict[str, Any]], caminho: str, mm_por_px: float = 0.0,
                   lado: str = 'frente', w_px: int = 0, h_px: int = 0) -> Dict[str, Any]:
    """Gera um ``.kicad_pcb`` (KiCad 7/8/9) a partir dos pads anotados.

    Pads de um mesmo componente viram um ``footprint``; pads soltos entram em
    ``PADS_SOLTOS``. Familias viram nets.
    """
    avisos: List[str] = []
    if not mm_por_px or mm_por_px <= 0:
        mm_por_px = 0.1
        avisos.append('Escala nao calibrada: usei 0.1 mm/px (calibre com a Regua [R] para medidas reais).')

    espelhar = str(lado).lower() in ('verso', 'back', 'bottom', 'inferior', 'tras', 'traseira')
    camada = 'B.Cu' if espelhar else 'F.Cu'
    mask = 'B.Mask' if espelhar else 'F.Mask'
    paste = 'B.Paste' if espelhar else 'F.Paste'
    silk = 'B.SilkS' if espelhar else 'F.SilkS'

    def px_para_mm(p: Dict[str, Any]) -> Tuple[float, float, float, float]:
        x, y = _centro_px(p)
        if espelhar and w_px:
            x = w_px - x
        w, h = _dimensoes_px(p)
        return x * mm_por_px, y * mm_por_px, w * mm_por_px, h * mm_por_px

    # pad id -> net name
    net_do_pad: Dict[int, str] = {}
    for n in nets or []:
        nome = _nome_seguro(n.get('nome') or n.get('name'), 60)
        if not nome:
            continue
        for pid in (n.get('pads') or []):
            net_do_pad[int(pid)] = nome

    ids_validos = {int(p.get('id')) for p in pads}

    # agrupar pads por componente
    grupos: List[Tuple[str, List[Dict[str, Any]]]] = []
    usados: set = set()
    for comp in componentes or []:
        membros = [p for p in pads if int(p.get('id')) in set(comp.get('pads') or [])]
        if not membros:
            continue
        grupos.append((_nome_seguro(comp.get('nome') or ('C%d' % comp.get('id', 0)), 40), membros))
        usados.update(int(p.get('id')) for p in membros)
    soltos = [p for p in pads if int(p.get('id')) not in usados]
    if soltos:
        grupos.append(('PADS_SOLTOS', soltos))

    nets_usadas: List[str] = []
    for p in pads:
        nome = net_do_pad.get(int(p.get('id')))
        if nome and nome not in nets_usadas:
            nets_usadas.append(nome)

    linhas: List[str] = []
    add = linhas.append
    add('(kicad_pcb (version 20240108) (generator "AnotadorPad")')
    add('  (general (thickness 1.6))')
    add('  (paper "A4")')
    add('  (layers')
    add('    (0 "F.Cu" signal)')
    add('    (31 "B.Cu" signal)')
    add('    (36 "B.SilkS" user "B.Silkscreen")')
    add('    (37 "F.SilkS" user "F.Silkscreen")')
    add('    (44 "Edge.Cuts" user)')
    add('  )')
    add('  (setup (pad_to_mask_clearance 0))')

    if w_px and h_px:
        add('  (gr_rect (start 0 0) (end %.3f %.3f) (stroke (width 0.1) (type default)) (fill none) (layer "Edge.Cuts"))'
            % (w_px * mm_por_px, h_px * mm_por_px))

    add('  (net 0 "")')
    for i, nome in enumerate(nets_usadas, start=1):
        add('  (net %d "%s")' % (i, nome))
    net_num = {nome: i for i, nome in enumerate(nets_usadas, start=1)}

    n_pads = 0
    for nome_comp, membros in grupos:
        pts = [px_para_mm(p) for p in membros]
        cx = sum(t[0] for t in pts) / len(pts)
        cy = sum(t[1] for t in pts) / len(pts)
        add('  (footprint "AnotadorPad:%s" (layer "%s")' % (_nome_seguro(nome_comp, 40) or 'PAD', camada))
        add('    (at %.4f %.4f)' % (cx, cy))
        add('    (attr smd)')
        add('    (fp_text reference "%s" (at 0 -2.2) (layer "%s") (effects (font (size 1 1) (thickness 0.15))))'
            % (_nome_seguro(nome_comp, 40) or 'PAD', silk))
        add('    (fp_text value "" (at 0 2.2) (layer "%s") (effects (font (size 1 1) (thickness 0.15))))' % silk)
        for p, (x, y, w, h) in zip(membros, pts):
            forma = _forma_pad(w, h, p.get('forma', ''))
            pino = _nome_seguro(p.get('pino') or p.get('id'), 12) or '1'
            dx, dy = x - cx, y - cy
            if forma == 'circle':
                size = '%.4f %.4f' % (max(w, h), max(w, h))
                tipo = 'circle'
            elif forma == 'oval':
                size = '%.4f %.4f' % (max(w, h), min(w, h))
                tipo = 'oval'
            else:
                size = '%.4f %.4f' % (w, h)
                tipo = 'rect'
            trecho = ('      (pad "%s" smd %s (at %.4f %.4f) (size %s) (layers "%s" "%s" "%s")'
                      % (pino, tipo, dx, dy, size, camada, paste, mask))
            nome_net = net_do_pad.get(int(p.get('id')))
            if nome_net:
                trecho += ' (net %d "%s")' % (net_num[nome_net], nome_net)
            add(trecho + ')')
            n_pads += 1
        add('  )')

    add(')')

    pasta = os.path.dirname(os.path.abspath(caminho))
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    with open(caminho, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(linhas) + '\n')

    if not pads:
        avisos.append('Nenhum pad anotado: o arquivo saiu so com o contorno.')
    return {'caminho': caminho, 'pads': n_pads, 'nets': len(nets_usadas),
            'escala': mm_por_px, 'avisos': avisos, 'lado': 'verso' if espelhar else 'frente'}


# ============================================================================
# Exportacao Gerber (cobre)
# ============================================================================

def exportar_gerber(pads: List[Dict[str, Any]], caminho: str, mm_por_px: float = 0.0,
                    w_px: int = 0, h_px: int = 0, lado: str = 'frente') -> Dict[str, Any]:
    """Gera um Gerber RS-274X com os pads como flashes (cobre do lado escolhido)."""
    avisos: List[str] = []
    if not mm_por_px or mm_por_px <= 0:
        mm_por_px = 0.1
        avisos.append('Escala nao calibrada: usei 0.1 mm/px.')
    espelhar = str(lado).lower() in ('verso', 'back', 'bottom', 'inferior', 'tras', 'traseira')

    aps: List[Tuple[str, float, float]] = []   # (tipo, w, h)
    defs: List[str] = []
    flashes: List[str] = []

    # Gerber usa Y para cima: inverte em torno da altura da placa.
    pontos = []
    for p in pads:
        x, y = _centro_px(p)
        if espelhar and w_px:
            x = w_px - x
        w, h = _dimensoes_px(p)
        pontos.append((x * mm_por_px, y * mm_por_px, w * mm_por_px, h * mm_por_px,
                       _forma_pad(w, h, p.get('forma', ''))))
    altura_mm = (h_px * mm_por_px) if h_px else (max((t[1] for t in pontos), default=0.0) or 1.0)

    for x_mm, y_mm, w_mm, h_mm, tipo in pontos:
        y_mm = altura_mm - y_mm
        chave = ('C', w_mm, w_mm) if tipo == 'circle' else ('O' if tipo == 'oval' else 'R', w_mm, h_mm)

        if chave not in aps:
            aps.append(chave)
            d = 10 + len(aps) - 1
            if chave[0] == 'C':
                defs.append('%%ADD%dC,%.6f*%%' % (d, chave[1]))
            else:
                defs.append('%%ADD%d%s,%.6fX%.6f*%%' % (d, chave[0], chave[1], chave[2]))
        d = 10 + aps.index(chave)
        xi = int(round(x_mm * 1e6))
        yi = int(round(y_mm * 1e6))
        flashes.append('D%d*' % d)
        flashes.append('X%dY%dD03*' % (xi, yi))

    linhas = ['G04 AnotadorPad - cobre %s*' % ('inferior' if espelhar else 'superior'),
              '%FSLAX46Y46*%', '%MOMM*%']
    linhas.extend(defs)
    linhas.extend(flashes)
    linhas.append('M02*')

    pasta = os.path.dirname(os.path.abspath(caminho))
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    with open(caminho, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(linhas) + '\n')

    return {'caminho': caminho, 'pads': len(pads), 'aperturas': len(aps),
            'escala': mm_por_px, 'avisos': avisos, 'lado': 'verso' if espelhar else 'frente'}


# ============================================================================
# Importacao KiCad
# ============================================================================

def importar_kicad(caminho: str, w_img: int = 0, h_img: int = 0,
                   mm_por_px: float = 0.0) -> Dict[str, Any]:
    """Le pads, componentes e nets de um ``.kicad_pcb``."""
    with open(caminho, 'r', encoding='utf-8', errors='ignore') as f:
        texto = f.read()
    arvore = _parse_sexpr(texto)
    raiz = arvore[0] if arvore else []
    avisos: List[str] = []

    nomes_net: Dict[str, str] = {}
    for n in _filhos(raiz, 'net'):
        if len(n) >= 3:
            nomes_net[str(n[1])] = _nome_seguro(n[2], 60)

    brutos: List[Dict[str, Any]] = []
    for fp in _filhos(raiz, 'footprint') + _filhos(raiz, 'module'):
        fx, fy, frot = _num_at(_primeiro(fp, 'at'))
        ref = ''
        for t in _filhos(fp, 'fp_text'):
            if len(t) >= 3 and t[1] == 'reference':
                ref = _nome_seguro(t[2], 40)
        for prop in _filhos(fp, 'property'):
            if len(prop) >= 3 and prop[1] in ('Reference', 'reference'):
                ref = _nome_seguro(prop[2], 40)
        for pad in _filhos(fp, 'pad'):
            if len(pad) < 4:
                continue
            pino = _nome_seguro(pad[1], 12)
            px, py, prot = _num_at(_primeiro(pad, 'at'))
            rx, ry = _rot(px, py, frot)
            ax, ay = fx + rx, fy + ry
            sw, sh, _ = _num_at(_primeiro(pad, 'size'))
            net = ''
            n = _primeiro(pad, 'net')
            if n and len(n) >= 2:
                net = nomes_net.get(str(n[1]), '') or (_nome_seguro(n[2], 60) if len(n) >= 3 else '')
            brutos.append({'x': ax, 'y': ay, 'w': sw or 1.0, 'h': sh or sw or 1.0,
                           'forma': _forma_pad(sw, sh), 'pino': pino, 'ref': ref,
                           'net': net, '_rot': prot})

    pontos = [(b['x'], b['y']) for b in brutos]
    px_pts, escala = _encaixar(pontos, w_img, h_img, mm_por_px)
    fator = escala if escala > 0 else 1.0
    for b, (x, y) in zip(brutos, px_pts):
        b['x'], b['y'] = x, y
        b['w'] = b['w'] / fator
        b['h'] = b['h'] / fator

    if not brutos:
        avisos.append('Nenhum pad encontrado no arquivo (footprints vazios?).')
    res = _montar_resultado(brutos, 'kicad', escala, avisos)
    res['arquivo'] = caminho
    return res


# ============================================================================
# Importacao Eagle
# ============================================================================

def _rot_eagle(x: float, y: float, rot: str) -> Tuple[float, float]:
    r = (rot or 'R0').strip().upper()
    espelhar = r.startswith('M')
    if espelhar:
        x = -x
    m = re.search(r'(\d+)', r)
    ang = float(m.group(1)) if m else 0.0
    # Eagle gira anti-horario com Y para cima; aqui ja trabalhamos em mm Y-up
    a = math.radians(ang)
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


def importar_eagle(caminho: str, w_img: int = 0, h_img: int = 0,
                   mm_por_px: float = 0.0) -> Dict[str, Any]:
    """Le pads/componentes/nets de um ``.brd`` do Eagle (XML)."""
    avisos: List[str] = []
    try:
        raiz = ET.parse(caminho).getroot()
    except ET.ParseError as e:
        return _montar_resultado([], 'eagle', 0.0, ['BRD invalido: %s' % e])

    pacotes: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for lib in raiz.findall('.//libraries/library'):
        lib_nome = lib.get('name') or ''
        for pkg in lib.findall('./packages/package'):
            defs: List[Dict[str, Any]] = []
            for p in pkg.findall('pad'):
                d = _f(p.get('diameter'), 0.0) or _f(p.get('drill'), 1.0) * 1.6
                defs.append({'nome': p.get('name') or '', 'x': _f(p.get('x')),
                             'y': _f(p.get('y')), 'w': d, 'h': d, 'rot': 'R0', 'forma': 'circle'})
            for s in pkg.findall('smd'):
                defs.append({'nome': s.get('name') or '', 'x': _f(s.get('x')),
                             'y': _f(s.get('y')), 'w': _f(s.get('dx'), 1.0),
                             'h': _f(s.get('dy'), 1.0), 'rot': s.get('rot') or 'R0',
                             'forma': 'rect'})
            pacotes[(lib_nome, pkg.get('name') or '')] = defs

    elementos = raiz.findall('.//elements/element')
    if not elementos:
        avisos.append('Nenhum elemento (componente) no BRD.')

    brutos: List[Dict[str, Any]] = []
    mapa_elemento_pad: Dict[Tuple[str, str], int] = {}
    for el in elementos:
        nome = el.get('name') or ''
        ex, ey = _f(el.get('x')), _f(el.get('y'))
        rot = el.get('rot') or 'R0'
        defs = pacotes.get((el.get('library') or '', el.get('package') or ''), [])
        for d in defs:
            ox, oy = _rot_eagle(d['x'], d['y'], d['rot'] if rot in ('', 'R0') else rot)
            ax, ay = ex + ox, ey + oy
            mapa_elemento_pad[(nome, d['nome'])] = len(brutos)
            brutos.append({'x': ax, 'y': ay, 'w': d['w'], 'h': d['h'],
                           'forma': d['forma'], 'pino': d['nome'], 'ref': nome, 'net': ''})

    # signals -> nets
    for sig in raiz.findall('.//signals/signal'):
        nome_net = _nome_seguro(sig.get('name'), 60)
        if not nome_net:
            continue
        for cr in sig.findall('contactref'):
            idx = mapa_elemento_pad.get((cr.get('element') or '', cr.get('pad') or ''))
            if idx is not None:
                brutos[idx]['net'] = nome_net

    # Eagle usa Y para cima: espelha para o padrao da imagem (Y para baixo)
    if brutos:
        maxy = max(b['y'] for b in brutos)
        altura = (h_img * mm_por_px) if (h_img and mm_por_px and mm_por_px > 0) else maxy
        for b in brutos:
            b['y'] = altura - b['y']

    pontos = [(b['x'], b['y']) for b in brutos]
    px_pts, escala = _encaixar(pontos, w_img, h_img, mm_por_px)
    fator = escala if escala > 0 else 1.0
    for b, (x, y) in zip(brutos, px_pts):
        b['x'], b['y'] = x, y
        b['w'] = b['w'] / fator
        b['h'] = b['h'] / fator

    res = _montar_resultado(brutos, 'eagle', escala, avisos)
    res['arquivo'] = caminho
    return res


# ============================================================================
# Importacao Gerber
# ============================================================================

_RE_ADD = re.compile(r'%ADD(\d+)([A-Za-z]),([^*%]*)\*?%?')
_RE_UNIT = re.compile(r'%MO(MM|IN)\*%')
_RE_FORMAT = re.compile(r'%FSLAX(\d)(\d)Y(\d)(\d)\*%')
_RE_SELECT = re.compile(r'(?:G54)?D(\d+)\*')
_RE_FLASH = re.compile(r'X([+-]?\d+)Y([+-]?\d+)D0?3\*')
_RE_OF = re.compile(r'%OFA([+-]?[\d.]+)B([+-]?[\d.]+)\*%')


def importar_gerber(caminho: str, w_img: int = 0, h_img: int = 0,
                    mm_por_px: float = 0.0) -> Dict[str, Any]:
    """Le pads (flashes D03) de um Gerber RS-274X."""
    avisos: List[str] = []
    with open(caminho, 'r', encoding='utf-8', errors='ignore') as f:
        texto = f.read()

    unidade = 1.0
    if _RE_UNIT.search(texto) and 'IN' in (_RE_UNIT.search(texto).group(1) or ''):
        unidade = 25.4

    xi, xd = 4, 6
    m = _RE_FORMAT.search(texto)
    if m:
        xi, xd = int(m.group(1)), int(m.group(2))
    div = 10.0 ** xd

    ofx, ofy = 0.0, 0.0
    m = _RE_OF.search(texto)
    if m:
        ofx, ofy = _f(m.group(1)), _f(m.group(2))

    aperturas: Dict[str, Tuple[str, float, float]] = {}
    for m in _RE_ADD.finditer(texto):
        dcode, forma, resto = m.group(1), m.group(2).upper(), m.group(3)
        vals = [_f(v) for v in re.split(r'[Xx]', resto.strip('*% ')) if v.strip()]
        if forma == 'C':
            w = h = vals[0] if vals else 0.1
            tipo = 'circle'
        elif forma in ('R', 'O'):
            w = vals[0] if vals else 0.1
            h = vals[1] if len(vals) > 1 else w
            tipo = 'rect' if forma == 'R' else 'oval'
        elif forma == 'P':
            w = h = vals[0] if vals else 0.1
            tipo = 'circle'
        else:
            continue
        aperturas[dcode] = (tipo, w * unidade, h * unidade)

    atual: Optional[str] = None
    brutos: List[Dict[str, Any]] = []
    for linha in texto.replace('\r', '').split('\n'):
        for cmd in linha.split('*'):
            cmd = cmd.strip()
            if not cmd:
                continue
            ms = _RE_SELECT.fullmatch(cmd + '*')
            if ms and not cmd.startswith('X'):
                atual = ms.group(1)
                continue
            mf = _RE_FLASH.fullmatch(cmd + '*')
            if mf and atual is not None and atual in aperturas:
                x = int(mf.group(1)) / div * unidade + ofx
                y = int(mf.group(2)) / div * unidade + ofy
                tipo, w, h = aperturas[atual]
                brutos.append({'x': x, 'y': y, 'w': w, 'h': h, 'forma': tipo,
                               'pino': '', 'ref': '', 'net': ''})

    if not brutos:
        avisos.append('Nenhum flash D03 encontrado: Gerber pode ser so de trilhas/contorno.')

    if brutos:
        maxy = max(b['y'] for b in brutos)
        altura = (h_img * mm_por_px) if (h_img and mm_por_px and mm_por_px > 0) else maxy
        for b in brutos:
            b['y'] = altura - b['y']

    pontos = [(b['x'], b['y']) for b in brutos]
    px_pts, escala = _encaixar(pontos, w_img, h_img, mm_por_px)
    fator = escala if escala > 0 else 1.0
    for b, (x, y) in zip(brutos, px_pts):
        b['x'], b['y'] = x, y
        b['w'] = b['w'] / fator
        b['h'] = b['h'] / fator

    res = _montar_resultado(brutos, 'gerber', escala, avisos)
    res['arquivo'] = caminho
    res['aperturas'] = len(aperturas)
    return res


# ============================================================================
# Deteccao de formato / dispatcher
# ============================================================================

def detectar_formato(caminho: str) -> str:
    """Descobre o formato pela extensao e, se preciso, pelo conteudo."""
    ext = os.path.splitext(str(caminho))[1].lower()
    if ext in _EXT_KICAD:
        return 'kicad'
    if ext in _EXT_EAGLE:
        return 'eagle'
    if ext in _EXT_GERBER:
        return 'gerber'
    try:
        with open(caminho, 'r', encoding='utf-8', errors='ignore') as f:
            inicio = f.read(4096)
    except OSError:
        return 'desconhecido'
    if '(kicad_pcb' in inicio:
        return 'kicad'
    if '<eagle' in inicio:
        return 'eagle'
    if '%FS' in inicio or '%ADD' in inicio:
        return 'gerber'
    return 'desconhecido'


def importar_arquivo(caminho: str, w_img: int = 0, h_img: int = 0,
                     mm_por_px: float = 0.0) -> Dict[str, Any]:
    """Importa KiCad, Eagle ou Gerber detectando o formato automaticamente."""
    formato = detectar_formato(caminho)
    if formato == 'kicad':
        return importar_kicad(caminho, w_img, h_img, mm_por_px)
    if formato == 'eagle':
        return importar_eagle(caminho, w_img, h_img, mm_por_px)
    if formato == 'gerber':
        return importar_gerber(caminho, w_img, h_img, mm_por_px)
    return _montar_resultado([], 'desconhecido', 0.0,
                             ['Formato nao reconhecido. Use .kicad_pcb, .brd ou .gbr.'])
