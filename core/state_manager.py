"""Gerenciador de estado centralizado - extraído de AppV101 para desacoplar lógica de UI."""
from __future__ import annotations
from __future__ import annotations
import copy
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from core.detector import detectar_pads_com_mascara_v84, detectar_pads_tiles
from core.detector_ia import DetectorIA
from core.detector_smart import detectar_pads_smart
from core.geometry import Viewport
from core.imgio import ler_imagem
from core.models import Pad
from core.prefs import carregar as carregar_prefs, salvar as salvar_prefs
from core.report import gerar_relatorio_html
from core.transform import _alinhar_interno, alinhar_melhor
from core.units import parse_valor, formatar as fmt_unidade
from core import gpu as gpu_lib
from core import prefs as prefs_lib
from core import report as report_lib
from core import transform as transform_lib
from storage.loader import (
    carregar_pads_csv,
    carregar_medicoes_e_nets,
    carregar_componentes_csv,
    carregar_projeto_universal,
    achar_imagem_projeto,
)
from storage.saver import (
    salvar_csvs,
    salvar_png,
    salvar_componentes_csv,
)
from storage.session import carregar_sessao, salvar_sessao


class StateManager:
    """
    Gerencia todo o estado mutável da aplicação:
    - pads, nets, components, measurements, annotations
    - views (frente/verso/conector) com estado independente
    - undo/redo stacks
    - seleções atuais
    - configurações de detector/GPU
    """

    def __init__(self, img_path: str, csv_path: Optional[str] = None):
        # Imagem base
        self.img = ler_imagem(img_path)
        if self.img is None:
            raise FileNotFoundError(img_path)
        self.img_path_original = img_path
        self.h0, self.w0 = self.img.shape[:2]

        # Configurações de UI
        self.right_w = 320
        self.rail_w = 62
        self.view_w = 1311  # será recalculado
        self.view_h = 706
        self.font_scale = 1.0

        # Estado principal
        self.pads: List[Dict] = []
        self.nets: List[Dict] = []
        self.components: List[Dict] = []
        self.measurements: Dict[int, Dict] = {}
        self.annotations: List[Dict] = []

        # Contadores de ID
        self.next_pad_id = 1
        self.next_net_id = 1
        self.next_comp_id = 1
        self.next_annot_id = 1

        # Seleções
        self.selected_pad_idx: Optional[int] = None
        self.selected_comp_id: Optional[int] = None
        self.selected_annot_id: Optional[int] = None
        self.familia_selected: Optional[int] = None

        # Views (frente/verso/conector)
        self.views_store: Dict[str, Dict] = {}
        self.view_atual = 'frente'
        self.views_disponiveis = [
            ('frente', 'FRENTE', '3'),
            ('verso', 'VERSO', '4'),
            ('conector', 'CONECTOR', '5'),
        ]

        # Configurações de detector
        self.detector_modo = 'smart'
        self.smart_sens = 0.55
        self.detector_ia: Optional[DetectorIA] = None
        self.modelo_ia = ''
        self.gpu_ativo = False
        self.gpu_info = {}
        self._gpu_pref_carregada = False

        # UI state
        self.mode = 'navegar'
        self.tab = 'calibrar'
        self.right_mode = 'menu'
        self.show_ids = True
        self.show_minimap = False
        self.show_mask = False
        self.mostrar_mira = False
        self.estado_placa = 'desligada'
        self.filter_familia_id: Optional[int] = None
        self.filter_status: Optional[str] = None
        self.filter_tipo: Optional[str] = None
        self.search_id: Optional[int] = None
        self.comp_forma_atual = 'retangulo_h'
        self.comp_scroll = 0
        self.familia_scroll = 0

        # Undo/Redo
        self.undo_stack: List[Dict] = []
        self.redo_stack: List[Dict] = []
        self.max_undo = 60

        # Auto-save
        self.dirty = False
        self.autosave_t = time.time()
        self.out_dir = ''
        self.session_path = ''

        # Preferences
        self.prefs = carregar_prefs()

        # Carregar projeto ou detectar pads
        if csv_path:
            self._carregar_projeto_csv(csv_path)
        else:
            self._detectar_pads_inicial()

        # Inicializar view padrão
        self._inicializar_views()

    def _carregar_projeto_csv(self, csv_path: str):
        """Carrega projeto a partir de CSVs."""
        pads = carregar_pads_csv(csv_path)
        self.pads = pads
        self.next_pad_id = max((p['id'] for p in pads), default=0) + 1
        self.measurements, self.nets = carregar_medicoes_e_nets(
            os.path.join(os.path.dirname(csv_path), 'medicoes_final.csv')
        ) if os.path.exists(os.path.join(os.path.dirname(csv_path), 'medicoes_final.csv')) else ({}, [])
        self.next_net_id = max((n['id'] for n in self.nets), default=0) + 1 if self.nets else 1
        comp_csv = os.path.join(os.path.dirname(csv_path), 'componentes_final.csv')
        if os.path.exists(comp_csv):
            self.components = carregar_componentes_csv(comp_csv)
            self.next_comp_id = max((c['id'] for c in self.components), default=0) + 1 if self.components else 1

    def _detectar_pads_inicial(self):
        """Detecção inicial de pads na imagem."""
        from core.detector_smart import detectar_pads_smart
        pads_auto, _ = detectar_pads_smart(
            self.img,
            escala=0.7,
            sensibilidade=self.smart_sens,
            area_min=6,
            area_max=1500,
            nms=10,
            rejeitar_vias=True,
            usar_gpu=self.gpu_ativo
        )
        for p in pads_auto:
            self.pads.append({
                'id': self.next_pad_id,
                'cx': p['cx'], 'cy': p['cy'],
                'x': p['cx'], 'y': p['cy'],
                'w': p['w'], 'h': p['h'],
                'area': p['area'],
                'manual': False,
                'score': p.get('score'),
                'forma': p.get('forma'),
            })
            self.next_pad_id += 1
        self.pads.sort(key=lambda p: (p['cy'] // 80, p['cx']))

    def _inicializar_views(self):
        """Inicializa o store de views com a view padrão."""
        self.views_store = {
            'frente': self._snapshot_view()
        }
        self.view_atual = 'frente'

    # ==================== SNAPSHOTS & UNDO/REDO ====================

    def _snapshot_view(self) -> Dict:
        """Captura snapshot completo da view atual."""
        return {
            'img_path': self.img_path_original,
            'pads': copy.deepcopy(self.pads),
            'measurements': copy.deepcopy(self.measurements),
            'nets': copy.deepcopy(self.nets),
            'components': copy.deepcopy(self.components),
            'annotations': copy.deepcopy(self.annotations),
            'next_pad_id': self.next_pad_id,
            'next_net_id': self.next_net_id,
            'next_comp_id': self.next_comp_id,
            'next_annot_id': self.next_annot_id,
        }

    def _salvar_view_atual(self):
        """Salva estado da view atual no store."""
        self.views_store[self.view_atual] = self._snapshot_view()

    def _aplicar_view(self, view_name: str):
        """Aplica estado de uma view salva."""
        if view_name not in self.views_store:
            return False
        self._salvar_view_atual()
        vd = self.views_store[view_name]
        self.pads = copy.deepcopy(vd['pads'])
        self.measurements = copy.deepcopy(vd['measurements'])
        self.nets = copy.deepcopy(vd['nets'])
        self.components = copy.deepcopy(vd['components'])
        self.annotations = copy.deepcopy(vd['annotations'])
        self.next_pad_id = vd['next_pad_id']
        self.next_net_id = vd['next_net_id']
        self.next_comp_id = vd['next_comp_id']
        self.next_annot_id = vd['next_annot_id']
        self.view_atual = view_name
        self._limpar_selecoes()
        return True

    def trocar_view(self, nova_view: str) -> bool:
        """Troca para outra view (frente/verso/conector)."""
        if nova_view not in [v[0] for v in self.views_disponiveis]:
            return False
        if nova_view == self.view_atual:
            return True

        # Auto-vincular se habilitado
        if getattr(self, 'auto_vincular', True):
            self._auto_vincular_com(nova_view)

        # Criar view se primeira vez
        if nova_view not in self.views_store:
            self.views_store[nova_view] = {
                'img_path': self.img_path_original,
                'pads': [], 'measurements': {}, 'nets': [], 'components': [],
                'annotations': [], 'next_annot_id': 1,
                'next_pad_id': 1, 'next_net_id': 1, 'next_comp_id': 1,
            }

        return self._aplicar_view(nova_view)

    def _snapshot(self) -> Dict:
        """Snapshot completo para undo/redo."""
        return {
            'pads': copy.deepcopy(self.pads),
            'measurements': copy.deepcopy(self.measurements),
            'nets': copy.deepcopy(self.nets),
            'components': copy.deepcopy(self.components),
            'annotations': copy.deepcopy(self.annotations),
            'next_pad_id': self.next_pad_id,
            'next_net_id': self.next_net_id,
            'next_comp_id': self.next_comp_id,
            'next_annot_id': self.next_annot_id,
            'selected_pad_idx': self.selected_pad_idx,
            'selected_comp_id': self.selected_comp_id,
            'selected_annot_id': self.selected_annot_id,
            'mode': self.mode,
            'tab': self.tab,
            'view_atual': self.view_atual,
            'right_mode': self.right_mode,
            '_uid': time.time_ns(),
        }

    def push_undo(self) -> int:
        """Salva estado atual na stack de undo."""
        snap = self._snapshot()
        self.undo_stack.append(snap)
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        return snap['_uid']

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        self.redo_stack.append(self._snapshot())
        snap = self.undo_stack.pop()
        self._aplicar_snapshot(snap)
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        self.undo_stack.append(self._snapshot())
        snap = self.redo_stack.pop()
        self._aplicar_snapshot(snap)
        return True

    def _aplicar_snapshot(self, snap: Dict):
        """Aplica snapshot completo (inclui views_store para undo cross-view)."""
        self.pads = snap['pads']
        self.measurements = snap['measurements']
        self.nets = snap['nets']
        self.components = snap['components']
        self.annotations = snap['annotations']
        self.next_pad_id = snap['next_pad_id']
        self.next_net_id = snap['next_net_id']
        self.next_comp_id = snap['next_comp_id']
        self.next_annot_id = snap['next_annot_id']
        self.selected_pad_idx = snap.get('selected_pad_idx')
        self.selected_comp_id = snap.get('selected_comp_id')
        self.selected_annot_id = snap.get('selected_annot_id')
        self.mode = snap.get('mode', 'navegar')
        self.tab = snap.get('tab', 'calibrar')
        self.view_atual = snap.get('view_atual', 'frente')
        self.right_mode = snap.get('right_mode', 'menu')
        # Restaurar views_store se presente (para undo cross-view)
        if 'views_store' in snap:
            self.views_store = copy.deepcopy(snap['views_store'])
        self._limpar_selecoes()
        self._invalidar_cache()

    def _limpar_selecoes(self):
        self.selected_pad_idx = None
        self.selected_comp_id = None
        self.selected_annot_id = None
        self.pending_connection = None

    # ==================== PERSISTÊNCIA ====================

    def _payload_sessao(self) -> Dict:
        """Prepara payload completo para salvar sessão."""
        return {
            'version': 'v11.7',
            'img_path': self.img_path_original,
            'pads': self.pads,
            'measurements': self.measurements,
            'nets': self.nets,
            'components': self.components,
            'annotations': self.annotations,
            'next_pad_id': self.next_pad_id,
            'next_net_id': self.next_net_id,
            'next_comp_id': self.next_comp_id,
            'next_annot_id': self.next_annot_id,
            'detector_modo': self.detector_modo,
            'smart_sens': self.smart_sens,
            'gpu_ativo': self.gpu_ativo,
            'modelo_ia': self.modelo_ia,
            'views': {k: copy.deepcopy(v) for k, v in self.views_store.items()},
            'view_atual': self.view_atual,
            'estado_placa': self.estado_placa,
            'filter_familia_id': self.filter_familia_id,
            'show_ids': self.show_ids,
            'show_minimap': self.show_minimap,
            'mostrar_mira': self.mostrar_mira,
            'mm_por_px': getattr(self, 'mm_por_px', 0.0),
            'auto_vincular': getattr(self, 'auto_vincular', True),
            'layers': getattr(self, 'layers', {}),
        }

    def salvar_sessao(self):
        """Salva sessão completa com backup rotativo."""
        from storage.session import _backup_sessao
        _backup_sessao(self.session_path)
        payload = self._payload_sessao()
        tmp = self.session_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.session_path)

    def salvar_csvs(self):
        """Salva CSVs do projeto atual."""
        salvar_csvs(self.pads, self.measurements, self.nets, self.out_dir)
        salvar_componentes_csv(self.components, self.out_dir)
        self.dirty = False

    # ==================== DETECÇÃO ====================

    def detectar(self, modo: Optional[str] = None, preservar_manuais: bool = True):
        """Roda detecção no modo especificado."""
        modo = modo or self.detector_modo
        p = self._params_from_sliders()
        manuais = [p for p in self.pads if p.get('manual')] if preservar_manuais else []

        if modo == 'ia':
            if not self._garantir_modelo_ia():
                modo = 'smart'
            else:
                conf_ia = max(0.20, min(0.90, self.smart_sens))
                if 'baseline' in os.path.basename(self.modelo_ia).lower():
                    conf_ia = min(conf_ia, 0.05)
                pads_auto, mask = self.detector_ia.detectar(
                    self.img, conf=conf_ia, nms=p['nms_dist'],
                    area_min=p['area_min'], area_max=max(p['area_max'], 3000)
                )
        elif modo == 'smart':
            pads_auto, mask = detectar_pads_smart(
                self.img, escala=p['scale'], sensibilidade=self.smart_sens,
                area_min=p['area_min'], area_max=max(p['area_max'], 1500),
                nms=p['nms_dist'], rejeitar_vias=p.get('reject_vias', True),
                usar_gpu=self.gpu_ativo
            )
        else:  # classico
            pads_auto, mask = detectar_pads_com_mascara_v84(
                self.img, scale=p['scale'], brilho_min=p['brilho_min'],
                brilho_max=p['brilho_max'], sat_max=p['sat_max'],
                area_min=p['area_min'], area_max=p['area_max'],
                nms_dist=p['nms_dist'], rejeitar_vias=p.get('reject_vias', True),
                usar_gpu=self.gpu_ativo
            )

        self.push_undo()
        new_pads = []
        for pp in pads_auto:
            novo = {
                'id': self.next_pad_id, 'cx': pp['cx'], 'cy': pp['cy'],
                'x': pp['cx'], 'y': pp['cy'], 'w': pp['w'], 'h': pp['h'],
                'area': pp['area'], 'manual': False,
            }
            if pp.get('score') is not None: novo['score'] = pp['score']
            if pp.get('forma'): novo['forma'] = pp['forma']
            new_pads.append(novo)
            self.next_pad_id += 1

        if preservar_manuais:
            filtrados = [m for m in manuais if not any(
                (m['cx'] - a['cx'])**2 + (m['cy'] - a['cy'])**2 < p['nms_dist']**2 * 4
                for a in pads_auto
            )]
            self.pads = new_pads + filtrados
        else:
            self.pads = new_pads
            self.nets = []
            self.next_net_id = 1
            self.filter_familia_id = None

        self.pads.sort(key=lambda p: (p['cy'] // 80, p['cx']))
        self._recalc_next_id()
        self._invalidar_cache()
        self.dirty = True

    def _garantir_modelo_ia(self) -> bool:
        """Carrega modelo IA se não carregado."""
        if self.detector_ia is not None:
            return True
        try:
            from core.detector_ia import DetectorIA
        except Exception as e:
            return False

        cands = []
        if self.modelo_ia:
            cands.append(self.modelo_ia)
        pastas = [os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else '',
                  os.path.dirname(__file__), os.path.dirname(os.path.dirname(__file__)),
                  os.getcwd(), os.path.abspath(self.out_dir)]
        for d in pastas:
            if not d: continue
            for nome in ('pads.onnx', 'pads_baseline.onnx'):
                cands.append(os.path.join(d, 'models', nome))
        cands += [os.path.join(os.path.dirname(__file__), '..', 'models', 'pads.onnx'),
                  os.path.join(os.path.dirname(__file__), '..', 'runs', 'pads_rapido', 'weights', 'best.onnx')]

        for c in cands:
            try:
                if c and os.path.exists(c):
                    self.detector_ia = DetectorIA(c)
                    self.modelo_ia = c
                    return True
            except Exception:
                continue
        return False

    # ==================== GPU ====================

    def alternar_gpu(self):
        """Liga/desliga GPU e salva preferência."""
        self.gpu_ativo = not self.gpu_ativo
        from core import gpu as gpu_lib
        self.gpu_info = gpu_lib.ativar(self.gpu_ativo)
        self.gpu_ativo = gpu_lib.usando_gpu()
        # Marca como preferência manual
        self.prefs['gpu_manual'] = True
        self.prefs['gpu_ativo'] = self.gpu_ativo
        self._salvar_prefs()

    # ==================== HELPERS ====================

    def _params_from_sliders(self) -> Dict:
        # Implementação simplificada - usa defaults se sliders não existirem
        return {
            'scale': 0.7, 'brilho_min': 140, 'brilho_max': 255,
            'sat_max': 50, 'area_min': 6, 'area_max': 1500,
            'nms_dist': 10, 'reject_vias': True,
        }

    def _recalc_next_id(self):
        ids = [p.get('id', 0) for p in self.pads]
        if ids:
            self.next_pad_id = max(self.next_pad_id or 0, max(ids) + 1)

    def _invalidar_cache(self):
        pass  # placeholder para cache de visíveis

    def _limpar_selecoes(self):
        self.selected_pad_idx = None
        self.selected_comp_id = None
        self.selected_annot_id = None
        self.pending_connection = None

    def _salvar_prefs(self):
        from core.prefs import salvar as salvar_prefs
        self.prefs['gpu_ativo'] = self.gpu_ativo
        self.prefs['show_ids'] = self.show_ids
        self.prefs['detector_modo'] = self.detector_modo
        self.prefs['smart_sens'] = self.smart_sens
        self.prefs['modelo_ia'] = self.modelo_ia
        salvar_prefs(self.prefs)


# ==================== EXPORTS ====================
__all__ = ['StateManager']