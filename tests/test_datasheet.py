import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import datasheet


def _link(url):
    b = base64.urlsafe_b64encode(url.encode()).decode()
    return f'https://www.bing.com/ck/a?u=a1{b}&ntb=1'


def test_decode_bing():
    url = 'https://www.mouser.com/datasheet/2/149/BC547-190204.pdf'
    assert datasheet._decode_bing(_link(url)) == url


def test_extrair_urls():
    html = (f'<a href="{_link("https://www.ti.com/x.pdf")}">x</a>'
            '<a href="/search?q=nada">y</a>'
            '<a href="https://www.bing.com/images/search">z</a>')
    urls = datasheet._extrair_urls(html)
    assert urls == ['https://www.ti.com/x.pdf']


def test_busca_com_mock(monkeypatch):
    url = 'https://www.ti.com/datasheet.pdf'
    html = f'<html><a href="{_link(url)}">pdf</a></html>'

    class R:
        status_code = 200
        text = html

    monkeypatch.setattr(datasheet.requests, 'get', lambda *a, **k: R())
    res = datasheet.buscar_datasheet('BC547')
    assert res
    assert res[0]['url'] == url
    assert res[0]['pdf'] is True


def test_baixar_pdf(tmp_path, monkeypatch):
    class R:
        status_code = 200

        def iter_content(self, n):
            yield b'%PDF-1.4\n%conteudo'

    monkeypatch.setattr(datasheet.requests, 'get', lambda *a, **k: R())
    caminho = datasheet.baixar_pdf('https://x/y.pdf', str(tmp_path), nome='teste.pdf')
    assert caminho and os.path.exists(caminho)
    assert open(caminho, 'rb').read().startswith(b'%PDF')
