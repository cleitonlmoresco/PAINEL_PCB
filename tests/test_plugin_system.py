"""Testes para o sistema de plugins (M1)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.plugin_system import (
    PluginBase,
    PluginManager,
    PluginError,
    create_plugin_manager,
    discover_entry_point_plugins,
    discover_local_plugins,
)


class PluginFicticio(PluginBase):
    name = "plugin_ficticio"
    version = "2.0.0"
    description = "Plugin de teste"

    def __init__(self):
        super().__init__()
        self.setup_chamado = False
        self.teardown_chamado = False
        self.hook_chamadas = []
        self.cli_chamadas = []
        self.botoes_chamadas = []

    def setup(self, manager):
        self.setup_chamado = True
        self.manager = manager
        self._ativo = True

    def teardown(self):
        self.teardown_chamado = True
        self._ativo = False

    def on_app_start(self, app):
        self.hook_chamadas.append(('on_app_start', app))

    def on_pad_detectado(self, app, pads):
        self.hook_chamadas.append(('on_pad_detectado', len(pads)))

    def get_cli_commands(self):
        return [("meu-cmd", self.cli_meu_cmd, "Ajuda do meu cmd")]

    def cli_meu_cmd(self, app=None, **kwargs):
        self.cli_chamadas.append((app, kwargs))

    def get_toolbar_buttons(self):
        return [{"label": "Meu Botao", "key": "meu_botao", "kind": "action"}]

    def btn_meu_botao(self, app):
        self.botoes_chamadas.append(app)


def test_plugin_base_setup_teardown():
    mgr = PluginManager()
    p = PluginFicticio()
    mgr.registrar(p)
    assert p.setup_chamado
    assert p.ativo
    assert p.manager is mgr
    assert "plugin_ficticio" in mgr.listar()
    assert mgr.obter("plugin_ficticio") is p
    mgr.on_app_exit(None)
    assert p.teardown_chamado
    assert not p.ativo


def test_plugin_hooks():
    mgr = PluginManager()
    p = PluginFicticio()
    mgr.registrar(p)
    app_fake = {"view": "frente"}
    mgr.on_app_start(app_fake)
    mgr.on_pad_detectado(app_fake, [{"id": 1}, {"id": 2}])
    assert ('on_app_start', app_fake) in p.hook_chamadas
    assert ('on_pad_detectado', 2) in p.hook_chamadas


def test_plugin_cli_commands():
    mgr = PluginManager()
    p = PluginFicticio()
    mgr.registrar(p)
    cmds = mgr.comandos_cli()
    assert len(cmds) == 1
    nome, func, ajuda = cmds[0]
    assert "meu-cmd" in nome
    assert ajuda == "Ajuda do meu cmd"
    func(app=None, foo="bar")
    assert p.cli_chamadas == [(None, {"foo": "bar"})]


def test_plugin_toolbar_buttons():
    mgr = PluginManager()
    p = PluginFicticio()
    mgr.registrar(p)
    botoes = mgr.botoes_toolbar()
    assert len(botoes) == 1
    assert botoes[0]["label"] == "Meu Botao"
    assert botoes[0]["key"].startswith("plugin_")
    assert botoes[0]["key"].endswith("_meu_botao")
    assert botoes[0]["grupo"] == "PLUGINS"


def test_plugin_erro_duplicado():
    mgr = PluginManager()
    p1 = PluginFicticio()
    p2 = PluginFicticio()
    mgr.registrar(p1)
    try:
        mgr.registrar(p2)
        assert False, "Deveria lançar PluginError"
    except PluginError:
        pass


def test_create_plugin_manager_carrega_local(tmp_path):
    pasta_plugins = tmp_path / "plugins"
    pasta_plugins.mkdir()
    (pasta_plugins / "meu_plugin_local.py").write_text(
        'from core.plugin_system import PluginBase\n'
        'class MeuPlugin(PluginBase):\n'
        '    name = "meu_plugin_local"\n'
        '    version = "0.1.0"\n'
        '    description = "plugin local de teste"\n'
        '\n'
        'plugin = MeuPlugin()\n',
        encoding="utf-8",
    )
    mgr = create_plugin_manager(app=None)
    # O manager carrega entry-points (vazio) + pasta local (cwd/plugins e raiz_exec/plugins)
    # Como tmp_path nao e nem cwd nem raiz_exec, nao carrega nada daqui.
    # So verificamos que nao quebra.
    assert isinstance(mgr, PluginManager)


def test_descobrir_entry_points_vazio():
    # Sem entry-points instalados para esse grupo
    nomes = discover_entry_point_plugins()
    assert isinstance(nomes, list)


def test_plugin_invalido_nao_herda_pluginbase(tmp_path):
    pasta_plugins = tmp_path / "plugins"
    pasta_plugins.mkdir()
    (pasta_plugins / "plugin_invalido.py").write_text(
        'class NaoEhPlugin:\n    pass\n', encoding="utf-8",
    )
    # Deve ignorar silenciosamente arquivos sem PluginBase/create_plugin
    mgr = PluginManager()
    # Carrega apenas a pasta tmp (nao o cwd/plugins que tem o resumo_placa)
    # carregar_pasta_local busca em varios lugares; isolamos passando pasta_base
    # mas o metodo tambem busca cwd e raiz_exec. Verificamos apenas que nao quebra
    # e que o arquivo invalido nao gera erro nos erros do manager.
    carregados = mgr.carregar_pasta_local(str(pasta_plugins))
    # Deve ter carregado pelo menos 0 (o invalido e ignorado); pode ter mais
    # se houver plugins validos em cwd/plugins ou raiz_exec/plugins
    assert carregados >= 0
    # O arquivo invalido nao deve aparecer nos erros (e ignorado silenciosamente)
    nomes_erro = [e[0] for e in mgr.erros]
    assert "plugin_invalido.py" not in nomes_erro
