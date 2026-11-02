"""Busca de datasheets na internet (Bing) + download de PDF.

Sem API key: usa a página de resultados do Bing, decodifica os redirecionamentos
(bing.com/ck/a?u=a1...) e prioriza PDFs de fabricantes/distribuidores conhecidos.
"""
from __future__ import annotations

import base64
import os
import re
import urllib.parse

import requests

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36'}

DOMINIOS_BONS = (
    'mouser.', 'digikey.', 'ti.com', 'st.com', 'nxp.com', 'infineon.com', 'microchip.com',
    'onsemi.com', 'vishay.com', 'analog.com', 'maximintegrated.com', 'renesas.com',
    'toshiba.', 'farnell.com', 'sparkfun.com', 'alldatasheet', 'datasheet', 'lcsc.com',
    'rs-online', 'arrow.com', 'futureelectronics', 'pdf1.alldatasheet',
)


def _decode_bing(href):
    try:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        u = qs.get('u', [''])[0]
        if u.startswith('a1'):
            b = u[2:]
            b += '=' * (-len(b) % 4)
            return base64.urlsafe_b64decode(b).decode('utf-8', 'ignore')
    except Exception:
        return None
    return None


def _extrair_urls(html):
    urls = []
    for h in re.findall(r'href="([^"]+)"', html):
        h = h.replace('&amp;', '&')
        destino = None
        if 'bing.com/ck/a' in h:
            destino = _decode_bing(h)
        elif h.startswith('http'):
            destino = h
        if not destino:
            continue
        if not destino.startswith('http'):
            continue
        low = destino.lower()
        if any(x in low for x in ('bing.com', 'microsoft.com', 'msn.com', 'go.microsoft')):
            continue
        if destino not in urls:
            urls.append(destino)
    return urls


def _score(url, termo):
    low = url.lower()
    s = 10 if ('.pdf' in low) else 0
    if any(d in low for d in DOMINIOS_BONS):
        s += 4
    limpo = re.sub(r'[^a-z0-9]', '', termo.lower())
    if limpo and limpo in re.sub(r'[^a-z0-9]', '', low):
        s += 2
    return s


def buscar_datasheet(termo, limite=8, timeout=25):
    """Retorna lista de resultados ordenados: [{'url','pdf','score'}]."""
    termo = (termo or '').strip()
    if not termo:
        return []
    consultas = [f'{termo} datasheet filetype:pdf', f'{termo} datasheet pdf', f'{termo} datasheet']
    todos = []
    for q in consultas:
        try:
            url = 'https://www.bing.com/search?q=' + urllib.parse.quote_plus(q)
            r = requests.get(url, headers=UA, timeout=timeout)
            if r.status_code != 200:
                continue
            for u in _extrair_urls(r.text):
                if u not in [t['url'] for t in todos]:
                    todos.append({'url': u, 'pdf': '.pdf' in u.lower(), 'score': _score(u, termo)})
        except Exception:
            continue
        if len([t for t in todos if t['pdf']]) >= 3:
            break
    todos.sort(key=lambda t: (-t['score'], not t['pdf']))
    return todos[:limite]


def baixar_pdf(url, pasta, nome=None, timeout=60):
    """Baixa um PDF; retorna caminho local ou None."""
    try:
        os.makedirs(pasta, exist_ok=True)
        r = requests.get(url, headers=UA, timeout=timeout, stream=True)
        if r.status_code != 200:
            return None
        primeiro = next(r.iter_content(2048), b'')
        if b'%PDF' not in primeiro:
            return None
        # sanitiza SEMPRE o nome (do chamador ou da URL) e impede path traversal
        nome = nome or os.path.basename(urllib.parse.urlparse(url).path) or 'datasheet'
        nome = re.sub(r'[^A-Za-z0-9._-]+', '_', str(nome)) or 'datasheet'
        if not nome.lower().endswith('.pdf'):
            nome += '.pdf'
        destino = os.path.join(pasta, nome)
        tmp = destino + '.part'
        with open(tmp, 'wb') as f:
            f.write(primeiro)
            for chunk in r.iter_content(65536):
                if chunk:
                    f.write(chunk)
        os.replace(tmp, destino)
        return destino
    except Exception:
        try: os.remove(tmp)
        except Exception: pass
        return None
