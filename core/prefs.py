"""Preferências globais e autosave (recuperação de sessão)."""
from __future__ import annotations

import json
import os

ARQ = os.path.join(os.path.expanduser('~'), '.pcb_painel.json')
ARQ_AUTO = os.path.join(os.path.expanduser('~'), '.pcb_painel_autosave.json')

PADRAO = {
    'ultimo_projeto': '',
    'recentes': [],
    'gpu_ativo': None,
    'show_ids': True,
    'preset': 'preset_smd',
    'mm_por_px': 0.0,
    'detector_modo': 'smart',
    'smart_sens': 0.55,
    'pasta_projetos': '',
    'ultima_pasta': '',
    'auto_vincular': True,
    'layers': {'pads': True, 'ids': True, 'familias': True, 'componentes': True, 'linhas': True, 'mascara': True},
}


def carregar():
    d = {k: (dict(v) if isinstance(v, dict) else (list(v) if isinstance(v, list) else v)) for k, v in PADRAO.items()}
    try:
        with open(ARQ, encoding='utf-8') as f:
            dados = json.load(f)
        if isinstance(dados, dict):
            for k, v in dados.items():
                d[k] = v
        if not isinstance(d.get('layers'), dict):
            d['layers'] = dict(PADRAO['layers'])
        else:
            for k, v in PADRAO['layers'].items():
                d['layers'].setdefault(k, v)
        if not isinstance(d.get('recentes'), list):
            d['recentes'] = []
    except Exception as e:
        # JSON corrompido ou ilegivel: usa padroes, mas deixa visivel o motivo
        if os.path.exists(ARQ):
            print(f"aviso: prefs corrompidas ({e}); usando padroes")
    return d


def salvar(cfg):
    try:
        tmp = ARQ + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(tmp, ARQ)
    except Exception as e:
        print(f"aviso: falha ao salvar prefs: {e}")


def adicionar_recente(cfg, pasta):
    try:
        pasta = os.path.abspath(pasta)
    except Exception:
        return
    rec = [p for p in cfg.get('recentes', []) if os.path.normcase(str(p)) != os.path.normcase(pasta)]
    rec.insert(0, pasta)
    cfg['recentes'] = rec[:12]
    cfg['ultimo_projeto'] = pasta
    salvar(cfg)


def salvar_autosave(projeto, payload):
    try:
        tmp = ARQ_AUTO + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'projeto': os.path.abspath(projeto), 'payload': payload}, f, ensure_ascii=False)
        os.replace(tmp, ARQ_AUTO)
    except Exception:
        pass


def carregar_autosave():
    try:
        with open(ARQ_AUTO, encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get('payload'), dict) and d.get('projeto'):
            return d
    except Exception:
        pass
    return None


def limpar_autosave():
    try:
        os.remove(ARQ_AUTO)
    except Exception:
        pass
