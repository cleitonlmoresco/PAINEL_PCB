"""Configuração hierárquica YAML + overrides por projeto + CLI."""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except Exception:
    yaml = None


DEFAULT_CONFIG = {
    "app": {
        "language": "pt",
        "theme": "light",
        "auto_save_interval": 60,
        "max_recent_projects": 10,
    },
    "detector": {
        "default_mode": "smart",
        "smart_sensitivity": 0.55,
        "ia_confidence": 0.35,
        "tile_size": 1024,
        "overlap": 128,
        "use_gpu": True,
        "gpu_prefer_cuda": True,
    },
    "ui": {
        "show_ids": True,
        "show_minimap": False,
        "show_mira": False,
        "font_scale": 1.0,
        "rail_width": 62,
    },
    "storage": {
        "auto_backup": True,
        "max_backups": 5,
        "atomic_writes": True,
        "format": "json",  # ou "msgpack" no futuro
    },
    "gpu": {
        "enabled": True,
        "prefer_cuda": True,
        "allow_opencl_software": False,
        "benchmark_on_start": True,
    },
    "detector_ia": {
        "model_path": "",
        "confidence": 0.35,
        "nms_iou": 0.45,
        "auto_fallback_cpu": True,
    },
    "export": {
        "default_format": "csv",
        "include_measurements": True,
        "include_annotations": True,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge recursivo de dicionários."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _resolve_path(path_str: str) -> Path:
    """Resolve caminho relativo ao arquivo de config ou cwd."""
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        # tenta relativo ao diretório do script principal
        base = Path(sys.argv[0]).resolve().parent if getattr(sys, 'frozen', False) else Path.cwd()
        p = (base / p).resolve()
    return p


def carregar_config(caminho: Optional[str] = None, cli_overrides: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Carrega configuração hierárquica:
    1. DEFAULT_CONFIG (defaults)
    2. Arquivo YAML global (~/.config/anotadorpad/config.yaml)
    3. Arquivo YAML do projeto (<projeto>/anotadorpad.yaml)
    4. Variáveis de ambiente ANOTADOR_*
    5. Overrides CLI (maior prioridade)
    """
    config = DEFAULT_CONFIG.copy()

    # 1. Config global do usuário
    global_config = Path.home() / '.config' / 'anotadorpad' / 'config.yaml'
    if global_config.exists() and yaml:
        try:
            with open(global_config, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f) or {}
            config = _deep_merge(config, user_config)
        except Exception as e:
            print(f"Aviso: erro lendo config global: {e}")

    # 2. Config do projeto (se caminho fornecido)
    if caminho:
        proj_config = Path(caminho)
        if proj_config.is_file():
            proj_config = proj_config.parent
        proj_yaml = proj_config / 'anotadorpad.yaml'
        if proj_yaml.exists() and yaml:
            try:
                with open(proj_yaml, 'r', encoding='utf-8') as f:
                    proj_config_data = yaml.safe_load(f) or {}
                config = _deep_merge(config, proj_config_data)
            except Exception as e:
                print(f"Aviso: erro lendo config do projeto: {e}")

    # 3. Variáveis de ambiente ANOTADOR_*
    for key, value in os.environ.items():
        if key.startswith('ANOTADOR_'):
            path_keys = key[len('ANOTADOR_'):].lower().split('_')
            d = config
            for pk in path_keys[:-1]:
                d = d.setdefault(pk, {})
            d[path_keys[-1]] = _parse_env_value(value)

    # 4. Overrides CLI
    if cli_overrides:
        config = _deep_merge(config, cli_overrides)

    return config


def _parse_env_value(value: str):
    """Converte string de env para tipo Python apropriado."""
    v = value.strip()
    if v.lower() in ('true', 'yes', 'on', '1'):
        return True
    if v.lower() in ('false', 'no', 'off', '0'):
        return False
    try:
        if '.' in v:
            return float(v)
        return int(v)
    except ValueError:
        return v


def salvar_config(config: dict, caminho: str, apenas_projeto: bool = False):
    """Salva configuração em YAML."""
    if not yaml:
        raise RuntimeError("PyYAML não instalado (pip install pyyaml)")
    destino = Path(caminho)
    if apenas_projeto:
        destino = destino.parent / 'anotadorpad.yaml'
    destino.parent.mkdir(parents=True, exist_ok=True)
    # Remove chaves que são defaults (para manter arquivo limpo)
    def _limpa(d, defaults):
        for k in list(d.keys()):
            if k in defaults:
                if isinstance(d[k], dict) and isinstance(defaults[k], dict):
                    _limpa(d[k], defaults[k])
                    if not d[k]:
                        del d[k]
                elif d[k] == defaults[k]:
                    del d[k]
    _limpa(config, DEFAULT_CONFIG)
    with open(destino, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, indent=2, allow_unicode=True, sort_keys=False)


def get_config_value(config: dict, path: str, default=None):
    """Acessa valor aninhado por path 'section.subsection.key'."""
    keys = path.split('.')
    d = config
    for k in keys:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return default
    return d


# Instância global lazy
_config_global: Optional[dict] = None


def get_config() -> dict:
    global _config_global
    if _config_global is None:
        _config_global = carregar_config()
    return _config_global


def set_config_global(config: dict):
    global _config_global
    _config_global = config