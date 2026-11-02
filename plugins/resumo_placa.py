"""Plugin de exemplo: estatísticas rápidas da placa.

Demonstra como um plugin do AnotadorPad pode:
  * Registrar um comando CLI (`anotador stats:resumo --projeto <pasta>`)
  * Adicionar um botão na barra de ferramentas (grupo PLUGINS)
  * Responder a hooks (troca de visão, detecção de pads)
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from core.plugin_system import PluginBase


class ResumoPlacaPlugin(PluginBase):
    name = "resumo_placa"
    version = "1.0.0"
    description = "Exibe resumo rpido de pads/famílias da placa atual"

    # ------------------------------------------------------------------
    # Comandos CLI
    # ------------------------------------------------------------------
    def get_cli_commands(self) -> List[Tuple[str, Callable, str]]:
        return [
            ("resumo", self.cli_resumo, "Exibe resumo de pads/famílias do projeto"),
        ]

    def cli_resumo(self, app: Any = None) -> None:
        """Imprime o número de pads, famílias e componentes do projeto."""
        if app is None:
            print("Este comando requer a GUI aberta. Use: anotador resumo")
            return
        pads = app.pads or []
        nets = app.nets or []
        comps = app.componentes or []
        print(f"=== Resumo da placa ({app.view_atual.upper()}) ===")
        print(f"Pads: {len(pads)}")
        print(f"Famílias/nets: {len(nets)}")
        print(f"Componentes: {len(comps)}")
        if app.mm_por_px:
            area_mm2 = sum((p.get('w', 0) * p.get('h', 0)) for p in pads) * (app.mm_por_px ** 2)
            print(f"Área total dos pads: {area_mm2:.1f} mm² (escala {app.mm_por_px} mm/px)")

    # ------------------------------------------------------------------
    # Botões da toolbar GUI
    # ------------------------------------------------------------------
    def get_toolbar_buttons(self) -> List[Dict[str, Any]]:
        return [
            {
                'label': 'Resumo Placa',
                'key': 'plugin_resumo',
                'kind': 'action',
                'grupo': 'PLUGINS',
                'ativo': False,
            },
        ]

    def btn_resumo(self, app: Any) -> None:
        """Acao do botao da toolbar: exibe resumo da placa atual."""
        pads = app.pads or []
        nets = app.nets or []
        comps = app.componentes or []
        app._flash(f"Resumo: {len(pads)} pads, {len(nets)} familias, {len(comps)} componentes",cor=(0,220,120),dur=4.0)
        print(f"=== Resumo da placa ({app.view_atual.upper()}) ===")
        print(f"Pads: {len(pads)}")
        print(f"Famílias/nets: {len(nets)}")
        print(f"Componentes: {len(comps)}")
        if app.mm_por_px:
            area_mm2 = sum((p.get('w', 0) * p.get('h', 0)) for p in pads) * (app.mm_por_px ** 2)
            print(f"Área total dos pads: {area_mm2:.1f} mm² (escala {app.mm_por_px} mm/px)")

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    def on_pad_detectado(self, app: Any, pads: List[Dict[str, Any]]) -> None:
        if pads:
            print(f"[Plugin resumo_placa] {len(pads)} pads detectados na visão {app.view_atual}")


plugin = ResumoPlacaPlugin()
