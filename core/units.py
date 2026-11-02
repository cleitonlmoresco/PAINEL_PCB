"""Valores com unidades de bancada: 10k, 4.7u, 1M, 3V3, 100nF, 2m2..."""
from __future__ import annotations

import re

_PREFIXO = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'k': 1e3, 'K': 1e3, 'M': 1e6, 'G': 1e9}

CAMPOS = {
    'tensao': ('V', 1.0),
    'frequencia': ('Hz', 1.0),
    'resistencia': ('Ohm', 1.0),
    'capacitancia': ('uF', 1e6),
    'diodo': ('V', 1.0),
}


def parse_qty(texto):
    """Converte texto em valor base (SI). Retorna float ou None."""
    if texto is None:
        return None
    bruto = str(texto).strip().replace(',', '.').replace('Ω', '').replace('µ', 'u')
    if not bruto:
        return None
    bruto = bruto.replace(' ', '')
    t = bruto.lower()
    m = re.fullmatch(r'(\d+)([pnuµmkKMR])(\d+)', bruto)   # 4k7, 2m2, 1M5, 4R7, 0R1
    if m:
        pref = m.group(2)
        if pref in ('R', 'r'):
            return float(f"{m.group(1)}.{m.group(3)}")
        mult = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'k': 1e3, 'K': 1e3, 'M': 1e6}[pref]
        return float(f"{m.group(1)}.{m.group(3)}") * mult
    m = re.fullmatch(r'(\d+)[v](\d+)', t)                 # 3v3
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    m = re.fullmatch(r'(\d+(?:\.\d+)?)([a-zA-Z]*)', bruto)
    if not m:
        return None
    val = float(m.group(1)); suf = m.group(2); sl = suf.lower()
    if not suf:
        return val
    if sl in ('meg', 'mega'):
        return val * 1e6
    if sl == 'mhz':
        return val * 1e6
    if sl == 'khz':
        return val * 1e3
    first = suf[0]
    if first == 'M': return val * 1e6
    if first in ('k', 'K'): return val * 1e3
    if first in ('G', 'g'): return val * 1e9
    if first == 'm': return val * 1e-3
    if first in ('u', 'µ'): return val * 1e-6
    if first == 'n': return val * 1e-9
    if first == 'p': return val * 1e-12
    return val


def parse_valor(texto, campo):
    """Converte para a unidade de exibição do campo (ex.: cap em uF)."""
    t = str(texto or '').strip()
    tem_unidade = bool(re.search(r'[a-zA-ZµΩ]', t))
    v = parse_qty(t)
    if v is None:
        return None
    if not tem_unidade:
        return v  # já está na unidade de exibição
    if campo == 'capacitancia':
        return v * 1e6
    return v


def formatar(campo, valor):
    """Formata valor de exibição com unidade."""
    unidade, _ = CAMPOS.get(campo, ('', 1.0))
    try:
        v = float(valor)
    except Exception:
        return ''
    if campo == 'frequencia':
        if v >= 1e6: return f"{v/1e6:.3g} MHz"
        if v >= 1e3: return f"{v/1e3:.3g} kHz"
        return f"{v:.0f} Hz"
    if campo == 'capacitancia':
        if v >= 1e3: return f"{v/1e3:.3g} mF"
        return f"{v:.4g} uF"
    if campo == 'resistencia':
        if v >= 1e6: return f"{v/1e6:.3g} MOhm"
        if v >= 1e3: return f"{v/1e3:.3g} kOhm"
        return f"{v:.0f} Ohm"
    return f"{v:.4g} {unidade}"
