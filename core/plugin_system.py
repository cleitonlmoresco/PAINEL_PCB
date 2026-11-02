"""Sistema de plugins do AnotadorPad (M1).

Descoberta de plugins via:
  1. entry-points instalados (pip install -e . ou pacotes externos)
     grupo: ``anotadorpad.plugins``
  2. Pasta local ``plugins/`` ao lado do executável ou do repositório

Cada plugin expõe um objeto que herda de :class:`PluginBase` e pode:
  * Registrar comandos CLI (ex: ``anotador meu-plugin --opcao``)
  * Registrar botões na barra de opções da GUI
  * Disparar hooks em eventos da aplica��o (in�cio, troca de vis�o, detec��o,
    salva de sess�o, exporta��o PCB)
  * Acessar o estado da aplica��o (app, pads, views, etc.)

Exemplo de plugin externo (instalado via pip)::

    # setup.py / pyproject.toml do pacote externo
    [project.entry-points."anotadorpad.plugins"]
    meu_plugin = "meu_plugin:plugin"

    # meu_plugin.py
    from core.plugin_system import PluginBase

    class MeuPlugin(PluginBase):
        name = "meu_plugin"
        version = "1.0.0"

        def setup(self, manager):
            self.manager = manager

        def get_cli_commands(self):
            return [("meu-comando", self.cli_meu_comando, "Ajuda do comando")]

        def cli_meu_comando(self, app, argumento):
            print(f"Rodando meu plugin com {argumento}")

    plugin = MeuPlugin()
"""
from __future__ import annotations

import importlib
import importlib.metadata
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = [
    'PluginBase',
    'PluginManager',
    'PluginError',
    'discover_entry_point_plugins',
    'discover_local_plugins',
    'create_plugin_manager',
]

# Nome do grupo de entry-points usado para descobrir plugins instalados.
ENTRY_POINT_GROUP = 'anotadorpad.plugins'

# Pasta local (relativa ao cwd ou ao diretório do executável) onde plugins
# ``.py`` soltos s�o carregados automaticamente.
LOCAL_PLUGIN_DIRS = ('plugins', 'plugin')


class PluginError(Exception):
    """Erro relacionado ao carregamento ou execu��o de plugins."""


class PluginBase:
    """Classe base para todos os plugins do AnotadorPad.

    Substitua os m�todos que fizer sentido para o seu plugin. N�o �
    obrigat�rio implementar nada: o gerente ignora m�todos ausentes.
    """

    # Identificador nico do plugin (sem espa os, letras min culas).
    name: str = ''
    # Verso semntica do plugin.
    version: str = '1.0.0'
    # Descri��o curta (usada em listas de plugins e CLI --help).
    description: str = ''
    # Se True, o plugin ser carregado mesmo que lance exceo no setup.
    opcional: bool = True

    def __init__(self):
        self.manager: Optional['PluginManager'] = None
        self._ativo = False

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def setup(self, manager: 'PluginManager') -> None:
        """Chamado aps o plugin ser carregado com sucesso."""
        self.manager = manager
        self._ativo = True

    def teardown(self) -> None:
        """Chamado antes de descarregar o plugin (fechamento da app)."""
        self._ativo = False
        self.manager = None

    @property
    def ativo(self) -> bool:
        return self._ativo

    # ------------------------------------------------------------------
    # Hooks de eventos da aplica��o
    # ------------------------------------------------------------------
    def on_app_start(self, app: Any) -> None:
        """Chamado quando a interface (AppV101) inicia."""
        pass

    def on_app_exit(self, app: Any) -> None:
        """Chamado quando a interface est prestes a fechar."""
        pass

    def on_view_change(self, app: Any, old_view: str, new_view: str) -> None:
        """Chamado quando o usurio troca de viso (frente/verso/conector)."""
        pass

    def on_pad_detectado(self, app: Any, pads: List[Dict[str, Any]]) -> None:
        """Chamado aps a deteco de pads (smart/IA/tiles)."""
        pass

    def on_salvar_sessao(self, app: Any, dados_sessao: Dict[str, Any]) -> None:
        """Chamado antes de salvar a sesso; pode modificar dados_sessao."""
        pass

    def on_exportar_pcb(self, app: Any, formato: str, caminho: str) -> None:
        """Chamado aps exportar KiCad/Gerber."""
        pass

    # ------------------------------------------------------------------
    # Comandos CLI
    # ------------------------------------------------------------------
    def get_cli_commands(self) -> List[Tuple[str, Callable, str]]:
        """Retorna lista de (nome, funcao, ajuda) para registro no CLI.

        Cada funcao recebe (app, **kwargs) onde app pode ser None
        quando executado fora da GUI.
        """
        return []

    # ------------------------------------------------------------------
    # Barras de ferramentas GUI
    # ------------------------------------------------------------------
    def get_toolbar_buttons(self) -> List[Dict[str, Any]]:
        """Retorna lista de dicionrios para adicionar botoes na barra.

        Cada dicionrio pode conter: label, key, kind ('action'|'toggle'),
        ativo (bool), grupo (str).
        """
        return []


# ========================================================================
# Gerente de plugins
# ========================================================================

class PluginManager:
    """Carrega, organiza e exp�e plugins para o resto da aplica��o."""

    def __init__(self, app: Optional[Any] = None):
        self.app = app
        self.plugins: Dict[str, PluginBase] = {}
        self._ordem_carregamento: List[str] = []
        self.erros: List[Tuple[str, str]] = []  # (nome, traceback)

    # ------------------------------------------------------------------
    # Descoberta
    # ------------------------------------------------------------------
    def carregar_entry_points(self) -> int:
        """Carrega plugins via entry-points instalados (pip)."""
        carregados = 0
        try:
            eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
        except Exception:
            # Python < 3.10 ou metadata indisponível
            eps = []
        for ep in eps:
            try:
                cls_or_inst = ep.load()
                inst = cls_or_inst() if isinstance(cls_or_inst, type) else cls_or_inst
                if not isinstance(inst, PluginBase):
                    raise PluginError(f"{ep.name}: noo herda PluginBase")
                self._registrar(ep.name, inst)
                carregados += 1
            except Exception as e:
                tb = traceback.format_exc()
                self.erros.append((ep.name, tb))
                if not getattr(inst, 'opcional', True):
                    raise
        return carregados

    def carregar_pasta_local(self, pasta_base: Optional[str] = None) -> int:
        """Carrega plugins .py soltos na pasta ``plugins/``."""
        carregados = 0
        candidatos: List[Path] = []
        if pasta_base:
            candidatos.append(Path(pasta_base).resolve())
        # Pasta plugins/ ao lado do cwd e ao lado do executável/script
        candidatos.append(Path.cwd().resolve() / 'plugins')
        try:
            raiz_exec = Path(sys.argv[0]).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
            candidatos.append((raiz_exec / 'plugins').resolve())
        except Exception:
            pass
        # Deduplica pastas pelo caminho absoluto
        pastas_vistas: set = set()
        candidatos_unicos: List[Path] = []
        for pasta in candidatos:
            if pasta in pastas_vistas:
                continue
            pastas_vistas.add(pasta)
            candidatos_unicos.append(pasta)

        for pasta in candidatos_unicos:
            if not pasta.is_dir():
                continue
            for arquivo in sorted(pasta.glob('*.py')):
                if arquivo.name.startswith('_'):
                    continue
                nome_mod = arquivo.stem
                try:
                    # Usa o caminho absoluto como nome do módulo para evitar colisões
                    spec = importlib.util.spec_from_file_location(
                        f"plugin_local_{arquivo.resolve()}", str(arquivo))
                    if spec is None or spec.loader is None:
                        continue
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    # Procura por instância de PluginBase ou fábrica create_plugin()
                    inst = None
                    for attr in dir(mod):
                        obj = getattr(mod, attr)
                        if isinstance(obj, PluginBase):
                            inst = obj
                            break
                    if inst is None and hasattr(mod, 'create_plugin'):
                        inst = mod.create_plugin()
                    if inst is None:
                        continue
                    self._registrar(nome_mod, inst)
                    carregados += 1
                except Exception as e:
                    tb = traceback.format_exc()
                    self.erros.append((arquivo.name, tb))
        return carregados

    # ------------------------------------------------------------------
    # Registro
    # ------------------------------------------------------------------
    def _registrar(self, nome: str, plugin: PluginBase) -> None:
        if nome in self.plugins:
            raise PluginError(f"Plugin '{nome}' j registrado")
        plugin.name = nome or plugin.name
        plugin.setup(self)
        self.plugins[nome] = plugin
        self._ordem_carregamento.append(nome)

    def registrar(self, plugin: PluginBase) -> None:
        """Registra um plugin instnciado manualmente."""
        nome = plugin.name or type(plugin).__name__
        self._registrar(nome, plugin)

    def obter(self, nome: str) -> Optional[PluginBase]:
        return self.plugins.get(nome)

    def listar(self) -> List[str]:
        return list(self._ordem_carregamento)

    def ativos(self) -> List[str]:
        return [n for n, p in self.plugins.items() if p.ativo]

    # ------------------------------------------------------------------
    # Execu��o de hooks
    # ------------------------------------------------------------------
    def _chamar_hook(self, nome_hook: str, *args, **kwargs) -> List[Any]:
        """Chama o hook em todos os plugins ativos. Retorna lista de resultados."""
        resultados: List[Any] = []
        for nome in self._ordem_carregamento:
            plugin = self.plugins[nome]
            if not plugin.ativo:
                continue
            metodo = getattr(plugin, nome_hook, None)
            if metodo is None:
                continue
            try:
                resultados.append(metodo(*args, **kwargs))
            except Exception as e:
                tb = traceback.format_exc()
                self.erros.append((f"{nome}.{nome_hook}", tb))
                if not plugin.opcional:
                    raise
        return resultados

    def on_app_start(self, app: Any) -> None:
        self.app = app
        self._chamar_hook('on_app_start', app)

    def on_app_exit(self, app: Any) -> None:
        self._chamar_hook('on_app_exit', app)
        for nome in list(self._ordem_carregamento):
            try:
                self.plugins[nome].teardown()
            except Exception:
                pass

    def on_view_change(self, app: Any, old_view: str, new_view: str) -> None:
        self._chamar_hook('on_view_change', app, old_view, new_view)

    def on_pad_detectado(self, app: Any, pads: List[Dict[str, Any]]) -> None:
        self._chamar_hook('on_pad_detectado', app, pads)

    def on_salvar_sessao(self, app: Any, dados_sessao: Dict[str, Any]) -> None:
        self._chamar_hook('on_salvar_sessao', app, dados_sessao)

    def on_exportar_pcb(self, app: Any, formato: str, caminho: str) -> None:
        self._chamar_hook('on_exportar_pcb', app, formato, caminho)

    # ------------------------------------------------------------------
    # Comandos CLI
    # ------------------------------------------------------------------
    def comandos_cli(self) -> List[Tuple[str, Callable, str]]:
        """Retorna todos os comandos CLI de todos os plugins."""
        cmds: List[Tuple[str, Callable, str]] = []
        for nome in self._ordem_carregamento:
            plugin = self.plugins[nome]
            if not plugin.ativo:
                continue
            try:
                for nm, func, ajuda in plugin.get_cli_commands():
                    cmds.append((f"{nome}:{nm}", func, ajuda))
            except Exception:
                tb = traceback.format_exc()
                self.erros.append((f"{nome}.get_cli_commands", tb))
        return cmds

    # ------------------------------------------------------------------
    # Botes GUI
    # ------------------------------------------------------------------
    def botoes_toolbar(self) -> List[Dict[str, Any]]:
        """Retorna todos os botes de toolbar de todos os plugins."""
        botoes: List[Dict[str, Any]] = []
        for nome in self._ordem_carregamento:
            plugin = self.plugins[nome]
            if not plugin.ativo:
                continue
            try:
                for btn in plugin.get_toolbar_buttons():
                    btn = dict(btn)
                    chave_original = btn.get('key', 'acao')
                    # Sempre prefixa com o nome do plugin para evitar colisoes
                    btn['key'] = f"plugin_{nome}_{chave_original}"
                    btn.setdefault('grupo', 'PLUGINS')
                    botoes.append(btn)
            except Exception:
                tb = traceback.format_exc()
                self.erros.append((f"{nome}.get_toolbar_buttons", tb))
        return botoes

    # ------------------------------------------------------------------
    # Utilitrios
    # ------------------------------------------------------------------
    def resumo(self) -> str:
        linhas = [f"Plugins carregados: {len(self.plugins)}"]
        for nome in self._ordem_carregamento:
            p = self.plugins[nome]
            status = "ativo" if p.ativo else "inativo"
            linhas.append(f"  - {nome} v{p.version} [{status}] - {p.description}")
        if self.erros:
            linhas.append(f"  Erros: {len(self.erros)}")
        return '\n'.join(linhas)


# ========================================================================
# Fbricas de conveniencia
# ========================================================================

def create_plugin_manager(app: Optional[Any] = None) -> PluginManager:
    """Cria um PluginManager j populado com entry-points e pasta local."""
    mgr = PluginManager(app=app)
    mgr.carregar_entry_points()
    mgr.carregar_pasta_local()
    return mgr


def discover_entry_point_plugins() -> List[str]:
    """Lista nomes de plugins disponveis via entry-points (sem carregar)."""
    try:
        eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    except Exception:
        return []
    return [ep.name for ep in eps]


def discover_local_plugins(pasta_base: Optional[str] = None) -> List[str]:
    """Lista arquivos .py candidatos em plugins/ (sem carregar)."""
    encontrados: List[str] = []
    pastas: List[Path] = []
    if pasta_base:
        pastas.append(Path(pasta_base))
    pastas.append(Path.cwd() / 'plugins')
    try:
        raiz_exec = Path(sys.argv[0]).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
        pastas.append(raiz_exec / 'plugins')
    except Exception:
        pass
    for pasta in pastas:
        if not pasta.is_dir():
            continue
        for arq in sorted(pasta.glob('*.py')):
            if not arq.name.startswith('_'):
                encontrados.append(str(arq))
    return encontrados
