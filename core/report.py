"""Relatório HTML do projeto (abre no navegador / salva PDF pela impressão)."""
from __future__ import annotations

import html
import os
import re
import time


def _e(t):
    return html.escape(str(t if t is not None else ''))


def _conta_status(pads, meas):
    n = {'OK': 0, 'SUSP': 0, 'FALHA': 0, 'VAZIO': 0}
    for p in pads:
        m = meas.get(str(p.get('id'))) or meas.get(p.get('id')) or {}
        st = m.get('status') if isinstance(m, dict) else None
        if st in ('OK', 'SUSP', 'FALHA'):
            n[st] += 1
        else:
            n['VAZIO'] += 1
    return n


def gerar_html(destino, projeto, views, est=None, mm_por_px=0.0):
    """Gera um relatório HTML com resumo por visão, famílias, medições e componentes."""
    est = est or {}
    agora = time.strftime('%d/%m/%Y %H:%M')
    partes = []
    for nome_view, vd in (views or {}).items():
        pads = vd.get('pads') or []
        meas = vd.get('measurements') or {}
        nets = vd.get('nets') or []
        comps = vd.get('componentes') or []
        img = vd.get('img_path') or ''
        if img and not os.path.isabs(img):
            cand = os.path.join(projeto, img)
            if os.path.exists(cand):
                img = cand
        n = _conta_status(pads, meas)
        medidos = n['OK'] + n['SUSP'] + n['FALHA']
        total = max(1, len(pads))
        pct = int(100 * medidos / total)
        partes.append(f"<h2>Visão {_e(nome_view.upper())}</h2>")
        if img and os.path.exists(str(img)):
            try:
                from urllib.request import pathname2url
                img_url = pathname2url(os.path.abspath(str(img)))
            except Exception:
                img_url = _e(os.path.abspath(str(img)).replace('\\', '/'))
            partes.append(f'<p><img src="file://{img_url}" style="max-width:520px;border:1px solid #333;border-radius:8px"></p>')
        partes.append(
            f"<p class='kpis'>Pads: <b>{len(pads)}</b> · Medidos: <b>{medidos}</b> ({pct}%) · "
            f"<span class='ok'>OK {n['OK']}</span> · <span class='susp'>SUSP {n['SUSP']}</span> · "
            f"<span class='falha'>FALHA {n['FALHA']}</span> · <span class='vazio'>Sem medir {n['VAZIO']}</span></p>"
        )
        if nets:
            partes.append('<h3>Famílias</h3><table><tr><th>#</th><th>Nome</th><th>Pads</th><th>OK</th><th>SUSP</th><th>FALHA</th><th>Sem medir</th></tr>')
            for net in nets:
                nn = {'OK': 0, 'SUSP': 0, 'FALHA': 0, 'VAZIO': 0}
                for pid in net.get('pads', []):
                    m = meas.get(str(pid)) or meas.get(pid) or {}
                    st = m.get('status') if isinstance(m, dict) else None
                    if st in nn:
                        nn[st] += 1
                    else:
                        nn['VAZIO'] += 1
                partes.append(f"<tr><td>{net.get('id')}</td><td>{_e(net.get('nome') or '')}</td><td>{len(net.get('pads', []))}</td>")
                partes.append(f"<td class='ok'>{nn['OK']}</td><td class='susp'>{nn['SUSP']}</td><td class='falha'>{nn['FALHA']}</td><td class='vazio'>{nn['VAZIO']}</td></tr>")
            partes.append('</table>')
        if comps:
            partes.append('<h3>Componentes</h3><table><tr><th>#</th><th>Nome</th><th>Tipo</th><th>Valor</th><th>Tensão</th><th>Pinos</th><th>Pino 1</th></tr>')
            for c in comps:
                partes.append(f"<tr><td>{c.get('id')}</td><td>{_e(c.get('nome'))}</td><td>{_e(c.get('tipo'))}</td>"
                              f"<td>{_e(c.get('valor'))}</td><td>{_e(c.get('tensao'))}</td><td>{len(c.get('pads', []))}</td>"
                              f"<td>{_e(c.get('pino1') or '-')}</td></tr>")
            partes.append('</table>')
        anots = vd.get('anotacoes') or []
        if anots:
            partes.append('<h3>Anotações</h3><table><tr><th>#</th><th>Texto</th><th>X</th><th>Y</th></tr>')
            for a in anots:
                partes.append(f"<tr><td>{a.get('id')}</td><td>{_e(a.get('text'))}</td>"
                              f"<td>{a.get('x')}</td><td>{a.get('y')}</td></tr>")
            partes.append('</table>')
        if pads:
            def _ordem_natural(v):
                return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', str(v or ''))]
            pads_ord = sorted(pads, key=lambda pp: _ordem_natural(pp.get('pino') or pp['id']))
            partes.append('<h3>Medições</h3><table><tr><th>Pad</th><th>Pino</th><th>GND</th><th>Status</th><th>Tensão</th><th>Freq</th><th>Forma</th><th>R</th><th>Cont</th><th>Cap</th><th>Vf</th><th>Obs</th></tr>')
            for p in pads_ord:
                pid = p.get('id')
                m = meas.get(str(pid)) or meas.get(pid) or {}
                lig = m.get('ligada') or {}
                des = m.get('desligada') or {}
                st = m.get('status') or ''
                cls = {'OK': 'ok', 'SUSP': 'susp', 'FALHA': 'falha'}.get(st, 'vazio')
                obs = (str(lig.get('obs', '')) + ' ' + str(des.get('obs', ''))).strip()
                gnd = "<span class='ok'>SIM</span>" if p.get('gnd') else '-'
                partes.append(
                    f"<tr><td>{pid}</td><td>{_e(p.get('pino') or '')}</td><td>{gnd}</td><td class='{cls}'>{_e(st)}</td><td>{_e(lig.get('tensao'))}</td><td>{_e(lig.get('frequencia'))}</td>"
                    f"<td>{_e(lig.get('forma'))}</td><td>{_e(des.get('resistencia'))}</td><td>{_e(des.get('continuidade'))}</td>"
                    f"<td>{_e(des.get('capacitancia'))}</td><td>{_e(des.get('diodo'))}</td><td>{_e(obs)}</td></tr>"
                )
            partes.append('</table>')

    css = """
    body{font-family:Segoe UI,Arial,sans-serif;background:#14161c;color:#e8e8ee;margin:28px;max-width:1100px}
    h1{margin:0 0 4px 0} h2{margin-top:28px;border-bottom:1px solid #333;padding-bottom:6px}
    h3{margin:18px 0 6px;color:#9fc3ff}
    .meta{color:#9aa0ad;font-size:13px}
    .kpis{background:#1d2029;border:1px solid #2e323d;padding:10px 12px;border-radius:8px}
    table{border-collapse:collapse;width:100%;font-size:12.5px;margin:6px 0 18px}
    th,td{border:1px solid #2e323d;padding:5px 7px;text-align:left}
    th{background:#232733;color:#cfd6e4}
    tr:nth-child(even) td{background:#1a1d25}
    .ok{color:#4ade80}.susp{color:#38bdf8}.falha{color:#f87171}.vazio{color:#9aa0ad}
    """
    doc = f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<title>Relatório - {_e(est.get('projeto_nome', os.path.basename(projeto)))}</title><style>{css}</style></head><body>
<h1>Relatório do Projeto</h1>
<div class="meta">Projeto: <b>{_e(projeto)}</b> · Gerado em {agora} · {'Escala: %.4f mm/px' % mm_por_px if mm_por_px else 'Escala não calibrada'}</div>
{''.join(partes)}
</body></html>"""
    try:
        with open(destino, 'w', encoding='utf-8') as f:
            f.write(doc)
        return destino
    except Exception:
        return None
