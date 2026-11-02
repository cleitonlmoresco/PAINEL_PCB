import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.units import parse_qty, parse_valor, formatar


def test_prefixos():
    assert parse_qty('10k') == 10000
    assert abs(parse_qty('4.7u') - 4.7e-6) < 1e-12
    assert parse_qty('1M') == 1e6
    assert abs(parse_qty('2m2') - 2.2e-3) < 1e-12
    assert abs(parse_qty('4k7') - 4700) < 1e-9


def test_notacao_tensao():
    assert abs(parse_qty('3V3') - 3.3) < 1e-9
    assert abs(parse_qty('1v8') - 1.8) < 1e-9


def test_unidades_formato():
    assert abs(parse_valor('100nF', 'capacitancia') - 0.1) < 1e-9   # 0.1 uF
    assert abs(parse_valor('4.7u', 'capacitancia') - 4.7) < 1e-9
    assert parse_valor('100', 'capacitancia') == 100               # sem unidade = uF
    assert parse_valor('10k', 'resistencia') == 10000
    assert abs(parse_valor('16V', 'tensao') - 16) < 1e-9


def test_formatar():
    assert 'kHz' in formatar('frequencia', 1000)
    assert 'uF' in formatar('capacitancia', 4.7)
    assert 'kOhm' in formatar('resistencia', 10000)
    assert 'V' in formatar('tensao', 3.3)


def test_invalidos():
    assert parse_qty('') is None
    assert parse_qty('abc') is None
