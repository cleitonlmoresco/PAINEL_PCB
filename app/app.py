"""
AppV11 - Modular + FIXES solicitados
Compatível v84..v10.3
"""
import cv2
import numpy as np
import os
import sys
# FIX v11: permite rodar tanto como modulo quanto direto
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import json
import glob
import hashlib
import copy
import re
import time
import colorsys
import unicodedata
import webbrowser
import uuid


def _ascii(t):
    """Normaliza texto para o cv2 desenhar bem (sem acentos/unicode)."""
    if not isinstance(t, str):
        return t
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode('ascii')
    for a, b in (('—', '-'), ('–', '-'), ('·', '|'), ('→', '->'), ('…', '...')):
        t = t.replace(a, b)
    return t


def _tinta(cor, f=0.62):
    """Escurece cores vivas para ficarem legiveis sobre o tema claro (BGR)."""
    try:
        return tuple(max(0, min(255, int(c * f))) for c in cor[:3])
    except Exception:
        return (40, 44, 52)

# Imports modulares
from core import gpu as gpu_lib
from core import prefs as prefs_lib
from core import report as report_lib
from core import transform as transform_lib
from core import kicad as kicad_lib
from core import dialogs as dialogs_lib
from core import diff_viewer as diff_lib
from core import plugin_system as plugin_lib
from core.units import parse_valor, formatar as fmt_unidade
from core.detector import detectar_pads_com_mascara_v84, detectar_pads_tiles
from core.imgio import ler_imagem, imwrite as imwrite_u
from core.detector_smart import detectar_pads_smart, detectar_por_exemplo
from anomalias_modulo import executar_comparacao
from core.presets import PRESETS_BANCADA_V84, PALETA, PALETA_32, THEME, CORES_SEMANTICAS, CORES_STATUS, DESCRICOES_BOTOES, FORMAS_COMPONENTE, COMPONENTES_TIPOS, cor_semantica
from storage.loader import carregar_pads_csv, carregar_medicoes_e_nets, carregar_componentes_csv, carregar_projeto_universal
from storage.loader import resolver_img_sessao as _loader_resolver_img, procurar_imagem_projeto as _loader_procurar_img
from storage.saver import salvar_csvs, salvar_png, salvar_componentes_csv
from storage.session import carregar_sessao, salvar_sessao
from ui.theme import THEME as THEME_UI, gerar_cor_familia_infinita
from ui.widgets import ButtonV5, CustomSlider, DropdownPreset, DropdownPaleta, draw_rounded_rect, put_text_center, DropdownPaleta
from ui.sidebar import Sidebar, ContextMenu, criar_sidebar_padrao, criar_menu_contexto_pad, criar_menu_contexto_componente, criar_menu_contexto_familia

# Re-exporta THEME para compatibilidade
THEME = THEME_UI

def get_screen_size():
    try:
        import tkinter as tk
        r=tk.Tk()
        w=r.winfo_screenwidth(); h=r.winfo_screenheight()
        r.destroy()
        return w,h
    except:
        return 1366,768

class AppV101:
    JANELA="AnotadorPad v11.2 - FRENTE/VERSO/CONECTOR + GPU"
    CORES_STATUS={'OK':(0,200,0),'SUSP':(0,200,255),'FALHA':(0,0,220),None:(160,160,160)}
    def __init__(self,img_path,csv_path=None):
        sw,sh=get_screen_size()
        self.view_w=max(1024,min(1920,int(sw*0.96)))
        self.view_h=max(600,min(1080,int(sh*0.92)))
        self.right_w=max(300,min(380,int(self.view_w*0.24)))
        self.left_w=self.view_w-self.right_w
        self.rail_w=62  # barra de ferramentas vertical (estilo editor de imagens)
        self.font_scale=self.view_w/1366.0

        self.img=ler_imagem(img_path)
        if self.img is None: raise FileNotFoundError(img_path)
        self.img_path_original=img_path
        self.h0,self.w0=self.img.shape[:2]
        base=os.path.splitext(os.path.basename(img_path))[0]
        path_hash=hashlib.md5(os.path.abspath(img_path).encode()).hexdigest()[:6]
        self.out_dir=f"saida_pads_{base}_{path_hash}"
        os.makedirs(self.out_dir,exist_ok=True)
        self.session_path=f"{self.out_dir}/sessao_v87.json"

        # FIX v11: Inicializa ANTES de carregar - corrige bug compatibilidade
        self.pads=[]
        self.next_id=1
        self.measurements={}
        self.nets=[]
        self.next_net_id=1
        self.componentes=[]
        self.next_comp_id=1
        self.estado_placa='desligada'
        self.dirty=False
        self.undo_stack=[]
        self.redo_stack=[]
        self.mask_preview=None
        self.show_mask=False
        self.show_ids=True

        if csv_path and os.path.exists(csv_path):
            if os.path.isdir(csv_path):
                pads_csv=os.path.join(csv_path,'pads_final.csv')
                med_csv=os.path.join(csv_path,'medicoes_final.csv')
                comp_csv=os.path.join(csv_path,'componentes_final.csv')
                if os.path.exists(pads_csv):
                    raw=carregar_pads_csv(pads_csv)
                    self.pads=[{'id':p['id'],'cx':p['x'],'cy':p['y'],'x':p['x'],'y':p['y'],'w':p['w'],'h':p['h'],'area':p['w']*p['h'],'manual':p['manual']} for p in raw]
                    self.next_id=max((p['id'] for p in self.pads),default=0)+1
                    if os.path.exists(med_csv):
                        meas,nets=carregar_medicoes_e_nets(med_csv)
                        self.measurements=meas
                        if nets:
                            self.nets=nets
                            self.next_net_id=max([n['id'] for n in nets],default=0)+1
                    if os.path.exists(comp_csv):
                        self.componentes=carregar_componentes_csv(comp_csv)
                        self.next_comp_id=max([c['id'] for c in self.componentes],default=0)+1
            else:
                raw=carregar_pads_csv(csv_path)
                self.pads=[{'id':p['id'],'cx':p['x'],'cy':p['y'],'x':p['x'],'y':p['y'],'w':p['w'],'h':p['h'],'area':p['w']*p['h'],'manual':p['manual']} for p in raw]
                self.next_id=max((p['id'] for p in self.pads),default=0)+1
                dir_csv=os.path.dirname(os.path.abspath(csv_path))
                med_csv=os.path.join(dir_csv,'medicoes_final.csv')
                comp_csv=os.path.join(dir_csv,'componentes_final.csv')
                if os.path.exists(med_csv):
                    meas,nets=carregar_medicoes_e_nets(med_csv)
                    self.measurements=meas
                    if nets:
                        self.nets=nets
                        self.next_net_id=max([n['id'] for n in nets],default=0)+1
                if os.path.exists(comp_csv):
                    comps=carregar_componentes_csv(comp_csv)
                    if comps:
                        self.componentes=comps
                        self.next_comp_id=max([c['id'] for c in comps],default=0)+1

        self.comp_selected=None
        self.comp_forma_atual='circulo'
        self.comp_tipo_atual='capacitor'
        self.comp_drawing=False
        self.comp_drag_start=None
        self.comp_drag_end=None
        self.comp_scroll=0
        self.comp_edit_field_btns=[]
        self.comp_edit_tipo_btns=[]
        self.comp_edit_action_btns=[]
        self.comp_edit_buf_nome=''
        self.comp_edit_buf_valor=''
        self.comp_edit_buf_tensao=''
        self.comp_edit_buf_obs=''
        self.paleta_dropdown=None

        self.zoom=1.0
        self.pan_x=0
        self.pan_y=0
        self.base_scale=min((self.view_h-160)/max(1,self.h0),self._canvas_w()/max(1,self.w0))
        self.base_scale=max(0.05,self.base_scale)
        self._centrar_imagem()

        self.drag_mode=None
        self.drag_source=None
        self.drag_start=(0,0)
        self._drag_pad_orig=None
        self._drag_pad_moved=False
        self._drag_snapshot_id=None

        self.tab='calibrar'
        self.mode='navegar'
        self.selected=None
        self.pending_connection=None
        self.hover_idx=-1
        self.filter_status=None
        self.filter_tipo=None
        self.search_id=None
        self.filter_familia_id=None

        self.tooltip="v11 Modular - 78% imagem | Zoom 0.1-20x"
        self.right_mode='calib'
        self._visiveis=set()
        self._cache_visiveis_dirty=True
        self._cache_linhas=[]
        self._cache_linhas_dirty=True

        self._flash_until=0
        self._flash_msg=""
        self._flash_cor=(0,0,0)
        self._confirm_action=None
        self.backend_info=self._detect_backend()
        self.gpu_info=gpu_lib.detectar()
        self.gpu_ativo=gpu_lib.usando_gpu()
        self._gpu_pref_carregada=False
        self.gpu_bench=None
        self.last_detect_ms=None
        self.prefs=prefs_lib.carregar()
        self.pasta_projetos=self._detectar_pasta_projetos()
        self.auto_vincular=bool(self.prefs.get('auto_vincular',True))
        self.layers={k:bool((self.prefs.get('layers') or {}).get(k,True)) for k in ('pads','ids','familias','componentes','linhas','mascara','pinos','anotacoes')}
        self.mm_por_px=float(self.prefs.get('mm_por_px') or 0.0)
        self.show_ids=bool(self.prefs.get('show_ids',True))
        self.detector_modo=str(self.prefs.get('detector_modo') or 'smart')
        self.smart_sens=float(self.prefs.get('smart_sens') or 0.55)
        self.detector_ia=None
        self.modelo_ia=str(self.prefs.get('modelo_ia') or '')
        self.paleta_cmd={'active':False,'query':'','sel':0,'itens':[]}
        self.regua_modo=False; self.regua_pts=[]; self._regua_px=0.0
        self.comp_drag_kind=None; self.comp_drag_orig=None
        self.autosave_t=0.0
        self.views_store={}
        self.view_atual='frente'
        self.views_disponiveis=[('frente','FRENTE','3'),('verso','VERSO','4'),('conector','CONECTOR','5')]
        self._thumbs={}
        self._pad_to_net={}
        # ==================== DIFF VIEWER (frente x verso) ====================
        self.modo_diff=False               # ativa o diff viewer
        self.diff_view_ref='frente'        # visão de referência
        self.diff_view_alvo='verso'        # visão alvo
        self.diff_alpha=0.5                # opacidade do heatmap (sobreposto)
        self.diff_threshold=40             # limiar de diferença (0-255)
        self.diff_side_by_side=True        # True=lado a lado | False=sobreposto
        self.diff_result=None              # cache do último cálculo
        self.diff_precisa_recalcular=True
        # ==================== PLUGIN SYSTEM (M1) ====================
        self.plugin_mgr = plugin_lib.create_plugin_manager(app=self)
        self.plugin_cmds_registrados = {}
        # Anotacoes livres + marcacao de pinos/GND (estilo RastreCurve)
        self.anotacoes=[]
        self.next_anot_id=1
        self.anot_selected=None
        self._anot_draft=None
        self._anot_drag=None
        self._anot_undo_feito=False
        self.mostrar_mira=bool(self.prefs.get('mostrar_mira',True))

        self.show_minimap=True
        self.minimap_w=160
        self.minimap_h=100
        self.minimap_hover=False

        self.preset_dropdown=None
        self.preset_selected_key='preset_smd'

        self.mouse_x=0
        self.mouse_y=0
        self.tooltip_target=None
        self.tooltip_target_time=0
        self.tooltip_shown=False
        self.tooltip_title=""
        self.tooltip_lines=[]
        self.tooltip_delay=0.45

        rw=self.right_w
        self.sliders=[CustomSlider(0,110,rw-40,36,"Scale",20,100,70,"%", "{:.0f}"), CustomSlider(0,160,rw-40,36,"BrilhoMin",40,200,140,"", "{:.0f}"), CustomSlider(0,210,rw-40,36,"BrilhoMax",150,300,255,"", "{:.0f}"), CustomSlider(0,260,rw-40,36,"SatMax",20,150,50,"", "{:.0f}"), CustomSlider(0,310,rw-40,36,"AreaMin",5,200,6,"px", "{:.0f}"), CustomSlider(0,360,rw-40,36,"AreaMax",100,3000,250,"px", "{:.0f}"), CustomSlider(0,410,rw-40,36,"NMS",5,30,14,"px", "{:.0f}")]
        self.edit_sliders=[]
        self.edit_status_idx=0
        self.edit_forma=''
        self.edit_cont=''
        self.edit_obs_lig=''
        self.edit_obs_des=''
        self.edit_status_btns=[]
        self.edit_action_btns=[]
        self.edit_field_btns=[]

        self.familia_scroll=0
        self.familia_selected=None
        self.familia_botoes=[]
        self.botoes_tab=[]
        self.botoes_menu=[]
        self.botoes_toolbar=[]
        self.botoes_filtro=[]
        self._last_tab=None

        self.inline_input_active=False
        self.inline_input_field=''
        self.inline_input_buffer=''
        self.inline_input_target_id=None
        self.inline_input_rect=None
        self.cursor_blink=0

        self._init_botoes()
        self._rebuild_toolbar()
        # Sidebar moderna
        # FIX v11.4: retangulo inicial com a largura real do painel (antes era 280 fixo,
        # mas right_w e 300..380: a sidebar nascia fora da janela ate o 1o layout)
        self.sidebar = criar_sidebar_padrao(0, 0, 320, self.view_h, self.font_scale)
        self.context_menu_pad = criar_menu_contexto_pad(self.font_scale)
        self.context_menu_comp = criar_menu_contexto_componente(self.font_scale)
        self.context_menu_familia = criar_menu_contexto_familia(self.font_scale)
        self.context_menu_anot = ContextMenu(self.font_scale)
        self.context_menu_anot.items = [
            ('Editar anotacao', 'E', 'anot_editar', 'default'),
            ('Excluir anotacao', 'DEL', 'anot_excluir', 'danger'),
        ]
        self._carregar_sessao()
        if not self._gpu_pref_carregada and bool(self.prefs.get('gpu_manual')) and self.prefs.get('gpu_ativo') is not None:
            self.gpu_ativo=bool(self.prefs.get('gpu_ativo'))
            self.gpu_info=gpu_lib.ativar(self.gpu_ativo); self.gpu_ativo=gpu_lib.usando_gpu(); self._gpu_pref_carregada=True
        if not self._gpu_pref_carregada: self._escolher_gpu_inicial()
        if not self.pads: self._detectar(preservar_manuais=False)
        self._invalidar_cache_visiveis()
        self._centrar_imagem()


    def _aplicar_gpu_sessao(self,data):
        """VRAM por padrao; so respeita 'usar_gpu' salvo se o usuario desligou com [J]."""
        manual=bool(self.prefs.get('gpu_manual'))
        if manual and isinstance(data,dict) and 'usar_gpu' in data:
            self.gpu_info=gpu_lib.ativar(bool(data.get('usar_gpu')))
        else:
            self.gpu_info=gpu_lib.ligar_por_padrao()
        self.gpu_ativo=gpu_lib.usando_gpu(); self._gpu_pref_carregada=True

    def _escolher_gpu_inicial(self):
        """Sem preferencia salva: usa a VRAM por padrao sempre que houver GPU.

        O benchmark roda apenas para informar o desempenho; nao desliga a GPU.
        """
        self.gpu_info=gpu_lib.ligar_por_padrao()
        self.gpu_ativo=gpu_lib.usando_gpu()
        if self.gpu_info.get('software'):
            self.gpu_info=gpu_lib.ativar(False); self.gpu_ativo=False
            print("OpenCL de software detectado (llvmpipe/SwiftShader): usando CPU")
            return
        if not self.gpu_ativo:
            return
        try:
            h,w=self.img.shape[:2]; fator=min(1.0,800.0/max(h,w))
            amostra=self.img if fator>=1.0 else cv2.resize(self.img,(max(64,int(w*fator)),max(64,int(h*fator))),interpolation=cv2.INTER_AREA)
            resultado=gpu_lib.benchmark(amostra)
            self.gpu_bench=resultado
            # mantem a GPU ligada mesmo se o benchmark empatar/perder; o usuario pode desligar com [J]
            self.gpu_info=gpu_lib.ativar(True); self.gpu_ativo=gpu_lib.usando_gpu()
            print(f"GPU {self.gpu_info.get('vendor','')} ({self.gpu_info.get('device','')}) | benchmark CPU {resultado.get('cpu_ms',0):.0f} ms | GPU {resultado.get('gpu_ms',0):.0f} ms | VRAM ON")
        except Exception:
            pass


    def _detect_backend(self):
        try: info=cv2.getBuildInformation(); return 'QT' if 'QT' in info else 'GTK' if 'GTK' in info else 'unknown'
        except: return 'unknown'
    def _toolbar_h(self):
        fb=getattr(self,'_toolbar_bottom',0)
        if fb: return fb
        b=getattr(self,'botoes_filtro',None)
        return (b[-1].rect[1]+36) if b else 110
    def _panel_top(self): return 72
    def _oy_off(self): return self._toolbar_h()+4
    def _cx0(self): return getattr(self,'rail_w',0)
    def _canvas_w(self): return max(160,self.left_w-self._cx0())
    def _clamp_familia_scroll(self):
        max_scroll=max(0,len(self.nets)-9); self.familia_scroll=max(0,min(self.familia_scroll,max_scroll))
        if self.familia_selected is not None:
            if not any(n['id']==self.familia_selected for n in self.nets): self.familia_selected=None
    def _recalc_next_id(self):
        # FIX v11.4: so CRESCE. Antes, view sem pads voltava next_id p/ 1 e um id
        # reutilizado herdava medicoes/links residuais de pad apagado
        ids=[p.get('id',0) for p in self.pads]
        if ids: self.next_id=max(self.next_id or 0, max(ids)+1)
    def _aplicar_preset(self,chave):
        p=PRESETS_BANCADA_V84.get(chave)
        if not p: return
        self.preset_selected_key=chave
        self.sliders[0].val=p["scale"]; self.sliders[1].val=p["brilho_min"]; self.sliders[2].val=p["brilho_max"]; self.sliders[3].val=p["sat_max"]; self.sliders[4].val=p["area_min"]; self.sliders[5].val=p["area_max"]; self.sliders[6].val=p["nms_dist"]
        if self.preset_dropdown: self.preset_dropdown.selected_key=chave; self.preset_dropdown.expanded=False
        self._invalidar_cache_visiveis(); self._flash(f"Preset {p['label']}: {p['desc'][:30]}",cor=(0,200,255),dur=2.0)
        self._salvar_prefs()

    def _init_botoes(self):
        # v11.5: barra superior enxuta (estilo visualizador de fotos) - o resto vive no Menu
        self.botoes_menu=[
            ButtonV5(8,3,116,25,"Abrir [O]",'abrir_img','success'),
            ButtonV5(132,3,112,25,"Projeto [L]",'abrir_proj','default'),
            ButtonV5(252,3,96,25,"Pasta [K]",'abrir_pasta','default'),
            ButtonV5(356,3,92,25,"Salvar [S]",'salvar','success'),
            ButtonV5(456,3,104,25,"Desfazer [Z]",'undo','default'),
            ButtonV5(568,3,112,25,"Refazer [C+Y]",'redo','default'),
            ButtonV5(self.view_w-204,3,96,25,"GPU [J]",'toggle_gpu','toggle'),
            ButtonV5(self.view_w-100,3,92,25,"Menu",'sidebar','toggle'),
        ]
        self.botoes_tab=[ButtonV5(8,31,132,27,"CALIBRAR [1]",'tab_calibrar','tab'), ButtonV5(146,31,120,27,"ANOTAR [2]",'tab_anotar','tab')]; self.botoes_tab[0].ativo=True
        # Abas de visão do projeto (frente/verso/conector) - alinhadas à direita da barra de abas
        self.botoes_view=[]; larguras={'frente':92,'verso':88,'conector':124}
        botoes_nav=56
        total=botoes_nav+sum(larguras[k] for k,_,_ in self.views_disponiveis)+4*(len(self.views_disponiveis)-1)
        xv=max(int(self.left_w*0.46)+12,self.left_w-total-8)
        self.botoes_view.append(ButtonV5(xv,31,24,25,"<",'view_ant','toggle'))
        self.botoes_view.append(ButtonV5(xv+28,31,24,25,">",'view_prox','toggle'))
        xv+=botoes_nav
        for chave,rotulo,tecla in self.views_disponiveis:
            self.botoes_view.append(ButtonV5(xv,31,larguras[chave],25,f"{rotulo} [{tecla}]",f"view_{chave}",'filter'))
            xv+=larguras[chave]+4
        self.botoes_view[2].ativo=True
    def _largura_botao(self,label,kind='default'):
        w=int((len(label)*6.8+28)*self.font_scale)
        return w+10 if kind=='success' else w

    def _layout_grupos(self,grupos,y0=64):
        """v11.6: barra agrupada por contexto - cada grupo tem legenda visivel."""
        self.toolbar_groups=[]; self.botoes_toolbar=[]; self.botoes_filtro=[]
        x=8; y=y0; cap_h=13; bnt_h=26; pad=6; gap=7; interno=5
        max_x=self.left_w-8
        for titulo,defs in grupos:
            gx_w=sum(self._largura_botao(l,kd)+(0 if i==0 else interno) for i,(l,k,kd) in enumerate(defs))+2*pad
            if x+gx_w>max_x and x>8:
                x=8; y+=cap_h+4+bnt_h+pad+gap
            gh=cap_h+4+bnt_h+pad-3
            self.toolbar_groups.append((titulo,(x,y,gx_w,gh)))
            bx=x+pad; by=y+cap_h+4
            for label,key,kind in defs:
                w=self._largura_botao(label,kind)
                self.botoes_toolbar.append(ButtonV5(bx,by,w,bnt_h,label,key,kind))
                bx+=w+interno
            x+=gx_w+gap
        self._toolbar_bottom=y+cap_h+4+bnt_h+pad+8

    def _hint_modo(self):
        return {
            'navegar':'Seleciona pad; botao do meio move a placa.',
            'adicionar':'Clique na placa para criar um pad manual.',
            'mover':'Arraste um pad para mover.',
            'remover':'Clique num pad para remover.',
            'medir':'Clique num pad para abrir a medicao.',
            'conectar':'Clique em dois pads para ligar na mesma familia.',
            'desconectar':'Clique num pad para tirar da familia.',
            'anotacao':'Clique cria anotacao; duplo clique edita.',
            'pino':'Clique num pad para nomear o pino.',
            'gnd':'Clique num pad para marcar/desmarcar GND.',
            'componente':'Arraste na placa para desenhar o componente.',
        }.get(self.mode,'Selecione uma ferramenta acima. Passe o mouse para ver a descricao.')

    _MODO_DA_RAIL={'modo_nav':'navegar','modo_add':'adicionar','modo_move':'mover','modo_del':'remover',
                   'modo_med':'medir','modo_con':'conectar','modo_descon':'desconectar',
                   'modo_anot':'anotacao','modo_pino':'pino','modo_gnd':'gnd','modo_comp':'componente',
                   'modo_al_validar':'validar_al'}

    def _rail_grupos(self):
        if self.tab=='calibrar':
            return [[('modo_nav','NAV','Navegar'),('modo_add','ADD','Adicionar'),('modo_move','MOV','Mover'),('modo_del','DEL','Remover')]]
        return [
            [('modo_nav','NAV','Navegar'),('modo_med','MED','Medir')],
            [('modo_add','ADD','Adicionar'),('modo_del','DEL','Remover'),('modo_con','CON','Conectar'),('modo_descon','DES','Descon.')],
            [('modo_anot','TXT','Anotar'),('modo_pino','PIN','Pino'),('modo_gnd','GND','GND'),('modo_comp','CMP','Comp.')],
            [('modo_al_validar','VAL','Validar AL')],
        ]

    def _layout_rail(self):
        """Rail vertical de ferramentas (estilo Photoshop/Affinity)."""
        self.rail_btns=[]
        x=5; w=max(44,self._cx0()-10); h=36; gap=2; grupo_gap=5
        y=self._toolbar_h()+10
        for grupo in self._rail_grupos():
            for key,icon,label in grupo:
                if y+h>self.view_h-42: break
                self.rail_btns.append({'key':key,'icon':icon,'label':label,'rect':(x,y,w,h)})
                y+=h+gap
            y+=grupo_gap

    def _rail_hit(self,x,y):
        for b in getattr(self,'rail_btns',[]):
            rx,ry,rw,rh=b['rect']
            if rx<=x<=rx+rw and ry<=y<=ry+rh: return b['key']
        return None

    def _draw_rail(self,canvas):
        x0=self._cx0(); top=self._toolbar_h()
        cv2.rectangle(canvas,(0,top),(x0,self.view_h-36),THEME['panel_toolbar'],-1)
        cv2.line(canvas,(x0,top),(x0,self.view_h-36),THEME['border'],1)
        for b in getattr(self,'rail_btns',[]):
            key,icon,label=b['key'],b['icon'],b['label']; rx,ry,rw,rh=b['rect']
            modo=self._MODO_DA_RAIL.get(key)
            ativo=(self.mode==modo) if modo else (key=='toggle_mira' and self.mostrar_mira)
            hover=(rx<=self.mouse_x<=rx+rw and ry<=self.mouse_y<=ry+rh)
            bg=THEME['accent'] if ativo else ((250,242,236) if hover else THEME['card'])
            fg=(255,255,255) if ativo else THEME['text_main']
            bd=THEME['accent'] if ativo else THEME['border']
            cv2.rectangle(canvas,(rx+1,ry+2),(rx+rw+1,ry+rh+2),THEME['shadow'],-1)
            draw_rounded_rect(canvas,rx,ry,rw,rh,7,bg,-1)
            draw_rounded_rect(canvas,rx,ry,rw,rh,7,(0,0,0),1,bd)
            (iw,ih),_=cv2.getTextSize(icon,cv2.FONT_HERSHEY_SIMPLEX,0.32,1)
            cv2.putText(canvas,icon,(rx+(rw-iw)//2,ry+16),cv2.FONT_HERSHEY_SIMPLEX,0.32,fg,1,cv2.LINE_AA)
            (lw,lh),_=cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,0.19,1)
            cv2.putText(canvas,label,(rx+(rw-lw)//2,ry+28),cv2.FONT_HERSHEY_SIMPLEX,0.19,fg,1,cv2.LINE_AA)

    def _rebuild_toolbar(self):
        if self._last_tab==self.tab and self.botoes_toolbar: return
        self._last_tab=self.tab
        if self.tab=='calibrar':
            grupos=[
                ("DETECCAO",[("Detectar",'detectar','success'),("Smart",'detectar_smart','toggle'),("IA ONNX",'modo_detector_ia','toggle'),("Exemplo",'detectar_exemplo','action'),("Tiles",'detectar_tiles','action'),("Reset",'reset','danger')]),
                ("VISAO",[("Mascara",'mascara','toggle'),("IDs",'toggle_ids','toggle'),("Fit",'fit','default'),("Vincular",'vincular_views','action'),("Foto da visao",'view_img','action')]),
                ("FILTROS",[("Todos",'f_todos','filter'),("Auto",'f_auto','filter'),("Manual",'f_manual','filter'),("Buscar",'buscar','action')]),
            ]
        else:
            grupos=[
                ("COMPONENTES",[("Datasheet",'comp_datasheet','action'),("Auto pino 1",'comp_auto_pino1','action'),("Reconhecer",'comp_reconhecer','action'),("Numerar",'pin_numerar','action')]),
                ("PAD",[("Editar",'editar','action'),("Duplicar",'duplicar','action'),("Isolar",'isolar','action')]),
                ("ACTIVE LEARNING",[("Validar AL",'modo_al_validar','action'),("Pseudo-Label",'al_pseudo','action'),("Treinar LoRA",'al_train','action')]),
                ("VISAO",[("Familias",'familias','toggle'),("Camadas",'camadas','toggle'),("IDs",'toggle_ids','toggle'),("Mira",'toggle_mira','toggle')]),
                ("FILTROS",[("Todos",'f_todos','filter'),("OK",'f_ok','filter'),("SUSP",'f_susp','filter'),("FALHA",'f_falha','filter'),("Sem medir",'f_vazio','filter'),("Buscar",'buscar','action')]),
                ("PLACA",[("LIG/DESL",'toggle_estado','toggle')]),
                ("PCB",[("KiCad",'export_kicad','success'),("Gerber",'export_gerber','success'),("Importar",'import_pcb','action')]),
                ("DIFF",[("Diff frente x verso",'modo_diff','toggle'),("Lado a lado",'diff_lado_a_lado','toggle'),("Sobreposto",'diff_sobreposto','toggle'),("Recalcular",'diff_recalcular','action')]),
            ]
        self._layout_grupos(grupos)
        # --- Botoes de plugins (M1) ---
        botoes_plugin = self.plugin_mgr.botoes_toolbar()
        if botoes_plugin:
            # Agrupa botoes de plugin num grupo proprio na toolbar
            grupos_plugin=[("PLUGINS",[(b['label'],b['key'],b.get('kind','action')) for b in botoes_plugin])]
            self._layout_grupos(grupos_plugin,y0=self._toolbar_bottom+8)

    # TOOLTIP
    def _get_tooltip_at(self, mx, my):
        if mx<self._cx0() and my>=self._toolbar_h():
            for b in getattr(self,'rail_btns',[]):
                rx,ry,rw,rh=b['rect']
                if rx<=mx<=rx+rw and ry<=my<=ry+rh:
                    desc=DESCRICOES_BOTOES.get(b['key'])
                    if desc: return (f"rail_{b['key']}",desc[0],desc[1])
                    if b['key']=='toggle_mira': return ("rail_mira","MIRA DE PRECISAO",["Liga/desliga a mira no cursor","Ajuda a acertar o centro do pad"])
                    return (f"rail_{b['key']}",b['label'],[])
        for zkey,(zx,zy,zw,zh) in getattr(self,'zoom_btns',[]):
            if zx<=mx<=zx+zw and zy<=my<=zy+zh:
                tabela={'out':("ZOOM -",["Diminui o zoom","Atalho: roda do mouse"]),
                        'in':("ZOOM +",["Aumenta o zoom","Atalho: roda do mouse"]),
                        'fit':("ZOOM / FIT",[f"Zoom atual {int(round(self.zoom*100))}%","Clique para mostrar a placa inteira","Atalho: 0"])}
                t,l=tabela.get(zkey,("ZOOM",[])); return (f"zoom_{zkey}",t,l)
        for b in self.botoes_menu:
            if b.hit(mx,my):
                desc=DESCRICOES_BOTOES.get(b.key)
                if desc: return (f"btn_{b.key}", desc[0], desc[1])
        for b in self.botoes_tab:
            if b.hit(mx,my):
                desc=DESCRICOES_BOTOES.get(b.key)
                if desc: return (f"btn_{b.key}", desc[0], desc[1])
        for b in self.botoes_view:
            if b.hit(mx,my):
                if b.key=='view_ant': return (b.key,"VISAO ANTERIOR",["Clique ou tecla ,","Cicla FRENTE > VERSO > CONECTOR"])
                if b.key=='view_prox': return (b.key,"PROXIMA VISAO",["Clique ou tecla .","Cicla FRENTE > VERSO > CONECTOR"])
                vk=b.key.replace('view_','')
                vd=self.views_store.get(vk,{})
                npads=len(self.pads) if vk==self.view_atual else len(vd.get('pads') or [])
                tem_img=bool((self.img_path_original if vk==self.view_atual else vd.get('img_path')))
                linhas=[f"{npads} pads anotados", "Imagem carregada" if tem_img else "Sem imagem definida", "Clique para trocar de visão"]
                return (f"view_{vk}", f"VISÃO {b.label.split('[')[0].strip()}", linhas)
        for b in self.botoes_toolbar+self.botoes_filtro:
            if b.hit(mx,my):
                desc=DESCRICOES_BOTOES.get(b.key)
                if desc: return (f"btn_{b.key}", desc[0], desc[1])
        if self.preset_dropdown:
            if self.preset_dropdown.expanded:
                for i,key in enumerate(PRESETS_BANCADA_V84.keys()):
                    x,y,w,h=self.preset_dropdown.rect
                    iy=y+h+2+i*44
                    if x<=mx<=x+w and iy<=my<=iy+40:
                        p=PRESETS_BANCADA_V84[key]
                        lines=[p['desc'], f"Scale:{p['scale']}% Bmin:{p['brilho_min']} A:{p['area_max']} NMS:{p['nms_dist']}", f"Anti-via:{'ON' if p.get('reject_vias') else 'OFF'}", "Clique para aplicar"]
                        return (f"preset_{key}", f"PRESET {p['label']}", lines)
            else:
                if self.preset_dropdown.hit(mx,my):
                    p=PRESETS_BANCADA_V84.get(self.preset_dropdown.selected_key)
                    if p: return (f"preset_header", f"PRESETS - {p['label']}", [p['desc'], "Clique para expandir", f"Atual: Bmin {p['brilho_min']} Area {p['area_max']} NMS {p['nms_dist']}"])
        if mx>=self.left_w:
            for s in self.sliders+self.edit_sliders:
                if s.hit_track(mx-self.left_w-10, my):
                    return (f"slider_{s.label}", f"SLIDER {s.label}", [f"Valor: {s.val:.1f} {s.unit}", "Arraste para ajustar", "Aguarde 1s para ver dica"])
            for b in self.edit_field_btns:
                if b.hit(mx,my):
                    if 'Forma' in b.label: return (f"field_forma", "CAMPO FORMA DE ONDA", ["Ex: senoidal, quadrada, DC, pulso", "Clique para digitar", f"Atual: {self.edit_forma or 'vazio'}"])
                    elif 'Cont' in b.label: return (f"field_cont", "CAMPO CONTINUIDADE", ["Valores: OK, ABERTO, CURTO, etc", "Clique para digitar", f"Atual: {self.edit_cont or 'vazio'}"])
                    elif 'Obs Ligada' in b.label: return (f"field_obs_lig", "OBSERVAÇÃO PLACA LIGADA", ["Anotações com placa energizada", "Ex: sem sinal, oscilando", f"Atual: {self.edit_obs_lig[:30] or 'vazio'}"])
                    elif 'Obs Desligada' in b.label: return (f"field_obs_des", "OBSERVAÇÃO PLACA DESLIGADA", ["Anotações com placa desligada", "Ex: resistor queimado", f"Atual: {self.edit_obs_des[:30] or 'vazio'}"])
            for b in self.edit_status_btns+self.edit_action_btns+self.familia_botoes:
                if b.hit(mx,my):
                    if b.key.startswith('layer_'):
                        ch=b.key.replace('layer_','')
                        return (b.key, f"CAMADA {ch.upper()}", [f"Estado: {'VISIVEL' if self.layers.get(ch,True) else 'OCULTA'}", "Clique para alternar"])
                    if b.key.startswith('fam_sel_'):
                        try: nid=int(b.key.split('_')[-1])
                        except Exception: nid=None
                        net=next((n for n in self.nets if n['id']==nid),None) if nid is not None else None
                        if net:
                            nome=net.get('nome') or f"Fam {net['id']}"
                            return (b.key, f"FAMILIA #{net['id']} {nome}", [f"{len(net.get('pads',[]))} pads", "Clique para selecionar/trocar cor"])
                    desc=DESCRICOES_BOTOES.get(b.key)
                    if desc: return (f"btn_{b.key}", desc[0], desc[1])
                    return (f"btn_{b.key}", b.label, [b.tooltip] if b.tooltip else [])
            for b in getattr(self,'comp_edit_field_btns',[])+getattr(self,'comp_edit_tipo_btns',[])+getattr(self,'comp_edit_action_btns',[]):
                if b.hit(mx,my):
                    desc=DESCRICOES_BOTOES.get(b.key)
                    if desc: return (f"btn_{b.key}", desc[0], desc[1])
                    return (f"btn_{b.key}", b.label, [b.tooltip] if b.tooltip else [])
            return (None, "", [])
        if my>=self._toolbar_h():
            oy_off=self._oy_off(); ox,oy=self._disp_to_orig(mx, my-oy_off); idx=self._pad_no_ponto(ox,oy, raio=40)
            if idx is not None and idx<len(self.pads):
                p=self.pads[idx]; pid=p.get('id',0); m=self.measurements.get(pid,{}) if isinstance(self.measurements,dict) else {}; status=m.get('status','') if isinstance(m,dict) else ''
                fam_nome="Nenhuma"
                for net in self.nets:
                    if pid in net['pads']: fam_nome=net.get('nome',f"Fam {net['id']}") or f"Fam {net['id']}"; break
                title=f"PAD #{pid} {'MANUAL' if p.get('manual') else 'AUTO'}"
                lines=[f"X={p['cx']} Y={p['cy']} Área={p['area']}px", f"Status: {status or 'Sem medir'} | Fam: {fam_nome}", f"Pino: {p.get('pino') or '-'} | GND: {'SIM' if p.get('gnd') else 'nao'}", "Clique: Seleciona | E: Edita | Dir: menu | Y/I/U: anota/pino/GND"]
                if p.get('link'):
                    alvos=self._alvos_do_link(p['link'])
                    lines.insert(2,"Passante: "+(", ".join(alvos) if alvos else "sim"))
                return (f"pad_{pid}", title, lines)
        if self.show_minimap:
            mw,mh=self.minimap_w,self.minimap_h; mx_map=self.left_w-mw-12; my_map=self._toolbar_h()+8
            if mx_map<=mx<=mx_map+mw and my_map<=my<=my_map+mh:
                return ("minimap", "MINIMAPA", ["Visão geral", "Retângulo = área visível", "Clique para navegar", f"Zoom {self.zoom:.1f}x"])
        return (None, "", [])
    def _update_tooltip(self, mx, my, now):
        target_key, title, lines = self._get_tooltip_at(mx, my)
        if target_key is None:
            if self.tooltip_target is not None: self.tooltip_target=None; self.tooltip_shown=False; self.tooltip_target_time=0
            return
        if target_key != self.tooltip_target:
            self.tooltip_target=target_key; self.tooltip_target_time=now; self.tooltip_shown=False; self.tooltip_title=title; self.tooltip_lines=lines
        else:
            elapsed=now - self.tooltip_target_time
            if elapsed>=self.tooltip_delay and not self.tooltip_shown:
                self.tooltip_shown=True; self.tooltip_title=title; self.tooltip_lines=lines
    def _get_tooltip_position(self, mx, my, box_w, box_h):
        bx=mx+18; by=my+22
        if mx > self.view_w - 300 or bx+box_w > self.view_w - 8: bx=mx - box_w - 18
        if my > self.view_h - 180 or by+box_h > self.view_h - 40: by=my - box_h - 18
        if mx > self.view_w * 0.65 and my > self.view_h * 0.65: bx=mx - box_w - 18; by=my - box_h - 18
        if mx < 150 and my < 150: bx=mx+18; by=my+22
        bx=max(6, min(bx, self.view_w - box_w - 6)); by=max(6, min(by, self.view_h - box_h - 6))
        return bx,by

    def _params_from_sliders(self): 
        reject=PRESETS_BANCADA_V84.get(self.preset_selected_key,{}).get('reject_vias',True)
        return {"scale":self.sliders[0].val/100.0,"brilho_min":int(self.sliders[1].val),"brilho_max":int(self.sliders[2].val),"sat_max":int(self.sliders[3].val),"area_min":int(self.sliders[4].val),"area_max":int(self.sliders[5].val),"nms_dist":int(self.sliders[6].val),"reject_vias":reject}
    def _invalidar_cache_visiveis(self): self._cache_visiveis_dirty=True; self._cache_linhas_dirty=True
    def _marcar_dirty(self): self.dirty=True; self._invalidar_cache_visiveis()
    def _flash(self,msg,cor=(0,180,255),dur=1.5): self._flash_msg=msg; self._flash_cor=cor; self._flash_until=time.time()+dur
    def _trocar_aba(self,nova): self.tab=nova; self.botoes_tab[0].ativo=(nova=='calibrar'); self.botoes_tab[1].ativo=(nova=='anotar'); self._ir_para_navegar(); self._rebuild_toolbar(); self.right_mode='calib' if nova=='calibrar' else 'inspetor'; self._invalidar_cache_visiveis()
    def _ir_para_navegar(self):
        self.inline_input_active=False; self.inline_input_field=''; self.inline_input_buffer=''; self.inline_input_target_id=None; self.inline_input_rect=None
        self.pending_connection=None; self.drag_mode=None; self.drag_source=None; self._drag_pad_orig=None; self._drag_pad_moved=False; self._drag_snapshot_id=None
        for s in self.sliders: s.dragging=False
        for s in self.edit_sliders: s.dragging=False
        self.edit_sliders=[]; self.edit_field_btns=[]; self.edit_status_btns=[]; self.edit_action_btns=[]
        self.mode='navegar'
        if self.right_mode in ('edit','familias'): self.right_mode='inspetor' if self.tab=='anotar' else 'calib'
        self.tooltip="NAVEGAR"; self.tooltip_shown=False; self.tooltip_target=None
    def _reset_zoom_fit(self):
        self.zoom=1.0
        self._centrar_imagem()
    def _acao_zoom(self,key):
        """Botoes flutuantes de zoom (estilo visualizador de fotos)."""
        if key=='fit':
            self._reset_zoom_fit(); self._flash(f"Zoom {int(self.zoom*100)}% (fit)",cor=(0,200,255),dur=1.4); return
        f=1.25 if key=='in' else 1/1.25
        novo=max(0.1,min(20.0,self.zoom*f))
        fator=novo/self.zoom if self.zoom else 1.0
        cx=self._cx0()+self._canvas_w()/2.0; cy=(self._oy_off()+(self.view_h-40))/2.0
        self.pan_x=cx-(cx-self.pan_x)*fator
        self.pan_y=cy-(cy-self.pan_y)*fator
        self.zoom=novo; self._invalidar_cache_visiveis()
    def _start_inline_input(self,field,current="",target_id=None, rect=None):
        self.inline_input_active=True; self.inline_input_field=field; self.inline_input_buffer=current; self.inline_input_target_id=target_id; self.inline_input_rect=rect; self.tooltip_shown=False
    def _confirm_inline_input(self):
        field=self.inline_input_field; buf=self.inline_input_buffer.strip()
        if field=='forma': self.edit_forma=buf
        elif field=='cont': self.edit_cont=buf.upper() if buf else ''
        elif field=='obs_lig': self.edit_obs_lig=buf[:80]
        elif field=='obs_des': self.edit_obs_des=buf[:80]
        elif field.startswith('edit_num_'):
            try: idx=int(field.rsplit('_',1)[1])
            except Exception: idx=-1
            if 0<=idx<len(self.edit_sliders):
                campo=['tensao','frequencia','resistencia','capacitancia','diodo'][idx]
                v=parse_valor(buf,campo)
                if v is not None:
                    s=self.edit_sliders[idx]; s.val=max(s.min_v,min(s.max_v,v))
                elif buf:
                    self._flash(f"Valor invalido para {campo}: '{buf}' (ex: 5V, 1k, 4.7uF)",cor=(255,180,0),dur=3.5)
        elif field=='escala_mm':
            try: mm=float((buf or '').replace(',','.'))
            except Exception: mm=0.0
            px=getattr(self,'_regua_px',0.0)
            if mm>0 and px>0:
                self.mm_por_px=mm/px; self._salvar_prefs()
                self._flash(f"Escala: {self.mm_por_px:.4f} mm/px",cor=(0,220,120),dur=3.0)
        elif field=='comp_nome': self.comp_edit_buf_nome=buf
        elif field=='comp_valor': self.comp_edit_buf_valor=buf
        elif field=='comp_tensao': self.comp_edit_buf_tensao=buf
        elif field=='comp_marcacao': self.comp_edit_buf_marcacao=buf
        elif field=='comp_obs': self.comp_edit_buf_obs=buf
        elif field=='comp_pinos':
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp:
                import re as _re
                ids=[]
                for x in _re.findall(r'\d+',buf):
                    pid=int(x)
                    if any(p.get('id')==pid for p in self.pads) and pid not in ids: ids.append(pid)
                comp['pads']=ids; self._marcar_dirty()
        elif field=='buscar':
            try: self.search_id=int(buf) if buf else None
            except: self.search_id=None
            self._invalidar_cache_visiveis()
        elif field=='datasheet_termo':
            if buf:
                comp={'id':None,'nome':buf,'marcacao':buf,'valor':'','datasheet':''}
                self._buscar_datasheet_componente(comp)
        elif field=='pino_nome':
            pad=next((p for p in self.pads if p.get('id')==self.inline_input_target_id),None)
            if pad:
                self._push_undo()
                if buf: pad['pino']=buf[:24]
                else: pad.pop('pino',None)
                n=self._propagar_marcas_pad(pad,('pino',))
                self._marcar_dirty()
                extra=f" (+{n} passante(s))" if n else ""
                self._flash(f"Pino do pad #{pad.get('id')}: {buf or 'removido'}{extra}",cor=(0,220,120) if buf else (180,180,190),dur=2.2)
        elif field=='anotacao':
            a=self._anotacao_por_id(self.inline_input_target_id)
            if a:
                if buf:
                    a['text']=buf[:120]; self.anot_selected=a['id']; self._marcar_dirty()
                else:
                    self.anotacoes=[x for x in self.anotacoes if x.get('id')!=a.get('id')]
                    if self.anot_selected==a.get('id'): self.anot_selected=None
                    self._marcar_dirty()
        elif field=='rename_familia':
            net=next((n for n in self.nets if n['id']==self.inline_input_target_id),None)
            if net and buf:
                net['nome']=buf
                semi=cor_semantica(buf)
                if semi:
                    net['cor']=list(semi)
                    self._flash(f"Cor semântica aplicada: {buf.upper()}",cor=semi,dur=2.0)
                if net.get('uid'): self._sincronizar_net(net)
                self._marcar_dirty()
        self.inline_input_active=False; self.inline_input_field=''; self.inline_input_buffer=''; self.inline_input_target_id=None; self.inline_input_rect=None
        if self.right_mode=='edit' and self.selected is not None: self._iniciar_edicao(self.selected,reentrar=True)
        elif self.right_mode=='componentes' and self.comp_selected is not None: self._refresh_comp_field_labels()
    def _cancel_inline_input(self):
        field=self.inline_input_field; target=self.inline_input_target_id
        if field=='anotacao' and target is not None:
            a=self._anotacao_por_id(target)
            if a and not a.get('text'):
                self.anotacoes=[x for x in self.anotacoes if x.get('id')!=target]
                if self.anot_selected==target: self.anot_selected=None
                self._marcar_dirty()
        self.inline_input_active=False; self.inline_input_field=''; self.inline_input_buffer=''; self.inline_input_target_id=None; self.inline_input_rect=None; self._ir_para_navegar()
    def _snapshot(self):
        sel_id=self._selected_id(); return {"pads":copy.deepcopy(self.pads),"measurements":copy.deepcopy(self.measurements),"nets":copy.deepcopy(self.nets),"next_id":self.next_id,"next_net_id":self.next_net_id,"estado_placa":self.estado_placa,"tab":self.tab,"selected_id":sel_id,"filter_familia_id":self.filter_familia_id,"componentes":copy.deepcopy(self.componentes),"next_comp_id":self.next_comp_id,"comp_selected":self.comp_selected,"anotacoes":copy.deepcopy(self.anotacoes),"next_anot_id":self.next_anot_id,"anot_selected":self.anot_selected,"views":copy.deepcopy(self.views_store),"_uid":time.time_ns()}
    def _push_undo(self):
        snap=self._snapshot(); self.undo_stack.append(snap)
        if len(self.undo_stack)>60: self.undo_stack.pop(0)
        self.redo_stack.clear(); return snap["_uid"]
    def _apply_snapshot(self,snap):
        self.pads=snap["pads"]; self.measurements=snap["measurements"]; self.nets=snap["nets"]; self.next_id=snap.get("next_id",self.next_id); self.next_net_id=snap.get("next_net_id",self.next_net_id); self.estado_placa=snap.get("estado_placa",self.estado_placa); self.filter_familia_id=snap.get("filter_familia_id",None); self.componentes=copy.deepcopy(snap.get("componentes",[])); self.next_comp_id=snap.get("next_comp_id",self.next_comp_id); self.comp_selected=snap.get("comp_selected",None); self.anotacoes=copy.deepcopy(snap.get("anotacoes",[])); self.next_anot_id=snap.get("next_anot_id",max((a.get("id",0) for a in self.anotacoes),default=0)+1); self.anot_selected=snap.get("anot_selected"); self._anot_drag=None; self._anot_draft=None
        # FIX v11.4: restore o store das outras visoes para o undo reverte marcas
        # propagadas (pino/GND/link) que _propagar_* escreveu direto no store
        vs=snap.get("views")
        if isinstance(vs,dict) and vs: self.views_store=copy.deepcopy(vs); self.views_store[self.view_atual]=self._snapshot_view()
        sel_id=snap.get("selected_id"); self.selected=self._idx_from_id(sel_id) if sel_id is not None else None; self.pending_connection=None; self.drag_mode=None; self.drag_source=None; self._clamp_familia_scroll(); self._invalidar_cache_visiveis(); self._rebuild_pad_to_net()
    def _undo(self):
        if not self.undo_stack: return
        self.redo_stack.append(self._snapshot()); snap=self.undo_stack.pop(); self._apply_snapshot(snap)
    def _redo(self):
        if not self.redo_stack: return
        self.undo_stack.append(self._snapshot()); snap=self.redo_stack.pop(); self._apply_snapshot(snap)
    def _detectar(self,preservar_manuais=True,modo=None):
        p=self._params_from_sliders(); manuais=[x for x in self.pads if x.get("manual")] if preservar_manuais else []
        modo=modo or self.detector_modo
        t0=time.perf_counter()
        if modo=='ia':
            if not self._garantir_modelo_ia():
                modo='smart'
                self._flash("Modelo IA nao encontrado - treine (tools/treinar_pads.py) e salve models/pads.onnx",cor=(255,180,0),dur=4.0)
            else:
                conf_ia=max(0.20,min(0.90,self.smart_sens))
                if 'baseline' in os.path.basename(self.modelo_ia).lower(): conf_ia=min(conf_ia,0.05)
                pads_auto,mask=self.detector_ia.detectar(self.img,conf=conf_ia,nms=p['nms_dist'],area_min=p['area_min'],area_max=max(p['area_max'],3000))
        if modo=='smart':
            pads_auto,mask=detectar_pads_smart(self.img,escala=p["scale"],sensibilidade=self.smart_sens,area_min=p["area_min"],area_max=max(p["area_max"],1500),nms=p["nms_dist"],rejeitar_vias=p.get("reject_vias",True),usar_gpu=self.gpu_ativo)
        elif modo=='classico':
            pads_auto,mask=detectar_pads_com_mascara_v84(self.img,scale=p["scale"],brilho_min=p["brilho_min"],brilho_max=p["brilho_max"],sat_max=p["sat_max"],area_min=p["area_min"],area_max=p["area_max"],nms_dist=p["nms_dist"],reject_vias=p.get("reject_vias",True),usar_gpu=self.gpu_ativo)
        self.last_detect_ms=(time.perf_counter()-t0)*1000.0
        self.mask_preview=mask; new_pads=[]
        for pp in pads_auto:
            novo={'id':self.next_id,'cx':pp["cx"],'cy':pp["cy"],'x':pp["cx"],'y':pp["cy"],'w':pp["w"],'h':pp["h"],'area':pp["area"],'manual':False}
            if pp.get('score') is not None: novo['score']=pp['score']
            if pp.get('forma'): novo['forma']=pp['forma']
            new_pads.append(novo); self.next_id+=1
        if preservar_manuais:
            filtrados=[m for m in manuais if not any(np.hypot(m["cx"]-a["cx"],m["cy"]-a["cy"])<p["nms_dist"]*2 for a in pads_auto)]; self.pads=new_pads+filtrados
        else: self.pads=new_pads; self.nets=[]; self.next_net_id=1; self.filter_familia_id=None; self._clamp_familia_scroll()
        self._recalc_next_id(); self.pads.sort(key=lambda pp:(pp["cy"]//80,pp["cx"])); self.selected=None; self.drag_mode=None; self.drag_source=None; self._invalidar_cache_visiveis(); self._marcar_dirty()
        via="GPU" if self.gpu_ativo else "CPU"
        nome_modo={'smart':'SMART','classico':'CLASSICO','ia':'IA'}.get(modo,'SMART')
        extra=''
        if modo=='ia':
            nome_modelo=os.path.basename(getattr(self,'modelo_ia','') or '')
            if 'baseline' in nome_modelo.lower(): extra=' | baseline de teste (fraco): treine para melhorar'
            else: extra=f' | {nome_modelo}'
        self._flash(f"{nome_modo}: {len(pads_auto)} pads · {via} {self.last_detect_ms:.0f} ms (anti-via {'ON' if p.get('reject_vias') else 'OFF'}){extra}",cor=(0,220,100),dur=4.0 if extra else 2.5)
        self.plugin_mgr.on_pad_detectado(self, self.pads)

    def _modo_detector_alternar(self):
        self.detector_modo='classico' if self.detector_modo=='smart' else 'smart'
        self._salvar_prefs()
        self._flash(f"Detector: {self.detector_modo.upper()} (sens {self.smart_sens:.2f})",cor=(0,200,255),dur=2.0)

    def _ajustar_sens_smart(self,delta):
        self.smart_sens=max(0.30,min(0.90,self.smart_sens+delta))
        self._salvar_prefs()
        self._flash(f"Sensibilidade smart: {self.smart_sens:.2f}",cor=(0,200,255),dur=1.8)

    def _detectar_exemplo(self):
        if self.selected is None or self.selected>=len(self.pads):
            self._flash("Selecione um pad de referencia (clique nele) e tente de novo",cor=(255,180,0),dur=3.0); return
        p=self.pads[self.selected]
        t0=time.perf_counter()
        pads,_=detectar_por_exemplo(self.img,p['cx'],p['cy'],max(6,p.get('w',12)),max(6,p.get('h',12)),sensibilidade=max(0.68,min(0.90,self.smart_sens+0.23)))
        dt=(time.perf_counter()-t0)*1000.0
        if not pads:
            self._flash("Nenhum pad parecido encontrado (tente outro pad/limiar)",cor=(255,120,0),dur=3.0); return
        self._push_undo(); self.pads=[]; self.next_id=1
        for pp in pads:
            self.pads.append({'id':self.next_id,'cx':pp['cx'],'cy':pp['cy'],'x':pp['cx'],'y':pp['cy'],'w':pp['w'],'h':pp['h'],'area':pp['area'],'manual':False,'score':pp.get('score')}); self.next_id+=1
        self.nets=[]; self.measurements={}; self.next_net_id=1; self.filter_familia_id=None
        self.selected=None; self._recalc_next_id(); self.pads.sort(key=lambda pp:(pp['cy']//80,pp['cx']))
        self._invalidar_cache_visiveis(); self._marcar_dirty()
        self._flash(f"Por exemplo: {len(self.pads)} pads · {dt:.0f} ms (score {self.smart_sens+0.23:.2f})",cor=(0,220,100),dur=3.0)

    def _garantir_modelo_ia(self):
        if self.detector_ia is not None:
            return True
        try:
            from core.detector_ia import DetectorIA
        except Exception as e:
            self._flash(f"Detector IA indisponivel: {e}",cor=(255,0,0),dur=2.5); return False
        cands = []
        if self.modelo_ia: cands.append(self.modelo_ia)
        exe_dir = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else ''
        pastas=[exe_dir,ROOT,os.path.dirname(ROOT),os.getcwd(),os.path.abspath(self.out_dir)]
        for d in pastas:
            if not d: continue
            for nome in ('pads.onnx','pads_baseline.onnx'):
                cands.append(os.path.join(d,'models',nome))
            cands.append(os.path.join(d,'pads.onnx'))
        cands += [os.path.join(ROOT,'runs','pads_rapido','weights','best.onnx'),
                  os.path.join(ROOT,'runs','pads','weights','best.onnx')]
        vistos=set()
        for c in cands:
            try:
                if not c or c in vistos: continue
                vistos.add(c)
                if os.path.exists(c):
                    self.detector_ia = DetectorIA(c)
                    self.modelo_ia = c
                    self.prefs['modelo_ia'] = c
                    self._salvar_prefs()
                    return True
            except Exception:
                continue
        return False

    def _modo_detector_ia(self):
        if not self._garantir_modelo_ia():
            self._flash("Sem modelo IA: Menu > DETECCAO > Escolher modelo ONNX (ou treine com tools/treinar_pads.py)",cor=(255,180,0),dur=5.0)
            self.right_mode='menu'
            return
        self.detector_modo = 'ia'
        self._salvar_prefs()
        baseline='baseline' in os.path.basename(self.modelo_ia).lower()
        aviso=' (modelo baseline: acuracia baixa)' if baseline else ''
        self._flash(f"Detector IA: {os.path.basename(self.modelo_ia)}{aviso} - rodando...",cor=(0,220,120),dur=3.0)
        self._detectar(True, modo='ia')

    def _escolher_modelo_ia(self):
        """Permite apontar qualquer .onnx exportado (YOLO) sem renomear arquivos."""
        inicial=os.path.join(ROOT,'models')
        caminho=dialogs_lib.escolher_arquivo(
            'Escolher modelo IA (.onnx)',
            initialdir=inicial if os.path.isdir(inicial) else ROOT,
            filetypes=[('Modelo ONNX','*.onnx'),('Todos','*.*')],
        )
        if not caminho: return
        try:
            from core.detector_ia import DetectorIA
            self.detector_ia=DetectorIA(caminho)
            self.modelo_ia=caminho
            self.detector_modo='ia'
            self.prefs['modelo_ia']=caminho; self.prefs['detector_modo']='ia'; self._salvar_prefs()
            self._flash(f"Modelo IA carregado: {os.path.basename(caminho)} (backend {self.detector_ia.backend})",cor=(0,220,120),dur=4.0)
        except Exception as e:
            self._flash(f"Falha ao carregar modelo IA: {e}",cor=(255,0,0),dur=4.0)

    def _exportar_dataset(self):
        destino = dialogs_lib.escolher_pasta("Pasta onde criar o dataset YOLO", initialdir=os.path.abspath(self.out_dir))
        todos = False
        if destino:
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
                todos = messagebox.askyesno("Dataset", "Incluir TODOS os projetos encontrados?\n\nSim = todos | Nao = somente o projeto atual")
                root.destroy()
            except Exception:
                todos = False
        if not destino:
            return
        from core import dataset as ds
        pastas = [os.path.abspath(self.out_dir)]
        if todos:
            pastas = [p['pasta'] for p in self._listar_projetos()] or pastas
        saida = os.path.join(destino, 'dataset_yolo')
        stats = ds.exportar_projetos(pastas, saida, progresso=lambda m: print(m, flush=True))
        self._flash(f"Dataset: {stats['tiles']} tiles de {stats['imagens']} imagem(ns) - {saida}",cor=(0,220,120),dur=4.0)

    def _pre_anotar_album(self):
        pasta = dialogs_lib.escolher_pasta("Pasta com o album de fotos")
        ok = False
        if pasta:
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
                ok = messagebox.askyesno("Pre-anotar album", "Isso roda o detector smart em todas as fotos e pode demorar varios minutos.\n\nPara 500+ fotos, prefira o script:\n tools/exportar_dataset.py album\n\nContinuar agora?")
                root.destroy()
            except Exception:
                ok = False
        if not pasta or not ok:
            return
        from core import dataset as ds
        saida = os.path.join(pasta, 'dataset_yolo')
        stats = ds.pre_anotar_album(pasta, saida, escala=0.7, sensibilidade=self.smart_sens,
                                   usar_gpu=self.gpu_ativo, progresso=lambda m: print(m, flush=True))
        self._flash(f"Album: {stats['imagens']} fotos, {stats['tiles']} tiles, {stats['pads']} pads - {saida}",cor=(0,220,120),dur=4.0)

    def _abrir_imagem_dialog(self):
        path = dialogs_lib.escolher_arquivo("Abrir Imagem da Placa", filetypes=[("Imagens","*.jpg *.jpeg *.png *.bmp *.tiff"),("Todos","*.*")])
        if path and os.path.exists(path): self._carregar_nova_imagem(path)
    def _carregar_nova_imagem(self,path):
        img=ler_imagem(path)
        if img is None: self._flash("Imagem inválida",cor=(255,0,0)); return
        if getattr(self,'dirty',False):
            try: self._salvar_csvs()
            except Exception: pass
        self.img=img; self.img_path_original=path; self.h0,self.w0=img.shape[:2]
        base=os.path.splitext(os.path.basename(path))[0]; path_hash=hashlib.md5(os.path.abspath(path).encode()).hexdigest()[:6]
        self.out_dir=f"saida_pads_{base}_{path_hash}"; os.makedirs(self.out_dir,exist_ok=True); self.session_path=f"{self.out_dir}/sessao_v87.json"
        self.pads=[]; self.measurements={}; self.nets=[]; self.next_id=1; self.next_net_id=1; self.selected=None
        self.componentes=[]; self.next_comp_id=1; self.comp_selected=None
        self.filter_status=None; self.filter_tipo=None; self.search_id=None; self.filter_familia_id=None
        self.undo_stack.clear(); self.redo_stack.clear()
        self._pad_to_net={}
        self.views_store={}; self.view_atual='frente'; self._thumbs={}
        self._recalc_view()
        self._detectar(False)
        self.views_store={'frente':self._snapshot_view()}
        self._flash(f"Imagem carregada: {os.path.basename(path)}",cor=(0,200,255),dur=2.0); self._marcar_dirty()
    def _recalc_view(self):
        """Reajusta zoom/pan para o enquadramento inicial da imagem atual."""
        self.zoom=1.0
        self.base_scale=min((self.view_h-160)/max(1,self.h0),self._canvas_w()/max(1,self.w0))
        self.base_scale=max(0.05,self.base_scale)
        self._centrar_imagem()
        self._invalidar_cache_visiveis()

    def _centrar_imagem(self):
        """Centraliza a placa na area de desenho (margens iguais)."""
        disp_w=self.w0*self.base_scale*self.zoom; disp_h=self.h0*self.base_scale*self.zoom
        self.pan_x=(self._canvas_w()-disp_w)/2.0
        area_h=self.view_h-40-self._oy_off()
        self.pan_y=max(0.0,(area_h-disp_h)/2.0)

    def _resolver_img_sessao(self,img_salva,pasta):
        """Resolve img_path salvo na sessão (delegado ao storage.loader)."""
        return _loader_resolver_img(img_salva,pasta)

    def _procurar_imagem_projeto(self,pasta):
        """Procura a foto da placa perto do projeto (delegado ao storage.loader)."""
        return _loader_procurar_img(pasta)

    def _perguntar_imagem_projeto(self,pasta):
        path = dialogs_lib.escolher_arquivo(
            "Projeto sem imagem associada - escolha a foto da placa",
            initialdir=pasta,
            filetypes=[("Imagens","*.jpg *.jpeg *.png *.bmp *.tiff"),("Todos","*.*")],
        )
        return path if path and os.path.exists(path) else None

    def _abrir_projeto(self,pasta):
        """Abre um projeto de placa: sessão JSON (ou CSVs), imagem associada e estado completo."""
        pasta=os.path.abspath(pasta)
        if not os.path.isdir(pasta):
            self._flash("Pasta de projeto inválida",cor=(255,0,0),dur=2.5); return False
        # salva alterações pendentes do projeto atual antes de trocar
        if getattr(self,'dirty',False):
            try: self._salvar_csvs()
            except Exception: pass
        self.views_store={}; self.view_atual='frente'; self._thumbs={}
        sess=None; data=None
        cands=sorted(glob.glob(os.path.join(pasta,'**','sessao_*.json'),recursive=True),
                     key=lambda p:os.path.getmtime(p) if os.path.exists(p) else 0,reverse=True)
        for cand in cands:
            try:
                with open(cand,'r',encoding='utf-8') as f: data=json.load(f)
                sess=cand; break
            except Exception: continue
        if data is not None:
            self.pads=data.get('pads',[])
            self.measurements={int(k):v for k,v in (data.get('measurements') or {}).items()}
            self.nets=data.get('nets',[])
            self.componentes=data.get('componentes',data.get('componentes_v8',[]))
            self.next_id=data.get('next_id') or max((p.get('id',0) for p in self.pads),default=0)+1
            self.next_net_id=data.get('next_net_id') or max((n.get('id',0) for n in self.nets),default=0)+1
            self.next_comp_id=data.get('next_comp_id') or max((c.get('id',0) for c in self.componentes),default=0)+1
            # FIX v11.4: sessoes antigas sem 'views' tinham anotacoes no top-level
            anot_legado=data.get('anotacoes') or []
            next_anot_legado=data.get('next_anot_id') or max((a.get('id',0) for a in anot_legado),default=0)+1
            self.preset_selected_key=data.get('preset_key','preset_smd')
            self.estado_placa=data.get('estado_placa','desligada')
            self.filter_familia_id=data.get('filter_familia_id')
            for i,v in enumerate(data.get('sliders') or []):
                if i<len(self.sliders):
                    s=self.sliders[i]; s.val=max(s.min_v,min(s.max_v,v))
            # Visões do projeto (frente/verso/conector) - retrocompatível
            views=data.get('views') if isinstance(data.get('views'),dict) else None
            if views:
                self.views_store={k:copy.deepcopy(v) for k,v in views.items() if isinstance(v,dict)}
                va=data.get('view_atual')
                self.view_atual=va if va in self.views_store else next(iter(self.views_store))
                self._aplicar_view_runtime(self.views_store[self.view_atual],aplicar_imagem=False)
            else:
                # FIX v11.4: restaurar anotacoes da sessao legada; antes, o snapshot
                # copiava as anotacoes do projeto aberto anterior e depois sobrescrevia o JSON
                self.view_atual='frente'
                self.anotacoes=copy.deepcopy(anot_legado); self.anot_selected=None
                self.next_anot_id=next_anot_legado
                self.views_store={'frente':self._snapshot_view()}
            self._aplicar_gpu_sessao(data)
            self.out_dir=pasta; self.session_path=sess
        else:
            pads_alt=self._carregar_pads_alternativo(pasta)
            if not pads_alt:
                return self._novo_projeto_em_pasta(pasta)
            self.pads=pads_alt
            self.next_id=max((p['id'] for p in self.pads),default=0)+1
            self.measurements={}; self.nets=[]; self.componentes=[]
            self.next_net_id=1; self.next_comp_id=1
            med_csv=os.path.join(pasta,'medicoes_final.csv')
            comp_csv=os.path.join(pasta,'componentes_final.csv')
            if os.path.exists(med_csv):
                self.measurements,self.nets=carregar_medicoes_e_nets(med_csv)
                self.next_net_id=max([n['id'] for n in self.nets],default=0)+1 if self.nets else 1
            if os.path.exists(comp_csv):
                self.componentes=carregar_componentes_csv(comp_csv)
                self.next_comp_id=max([c['id'] for c in self.componentes],default=0)+1 if self.componentes else 1
            self.out_dir=pasta; self.session_path=os.path.join(pasta,'sessao_v87.json')
        # imagem do projeto: caminho salvo (da visão atual) -> busca na pasta -> pergunta ao usuário
        aviso_img=""
        vd_atual=self.views_store.get(self.view_atual) or {}
        img_salva=vd_atual.get('img_path') or ((data or {}).get('img_path'))
        img_nova=self._resolver_img_sessao(img_salva,pasta) if img_salva else None
        if not img_nova: img_nova=self._procurar_imagem_projeto(pasta)
        if not img_nova:
            img_nova=self._perguntar_imagem_projeto(pasta)
            if not img_nova: aviso_img=" (imagem não encontrada - mantendo a atual)"
        if img_nova:
            img=ler_imagem(img_nova)
            if img is not None:
                self.img=img; self.img_path_original=img_nova; self.h0,self.w0=img.shape[:2]; self._recalc_view()
            else: aviso_img=" (falha ao ler a imagem)"
        # estado transiente zerado
        self.selected=None; self.comp_selected=None; self.pending_connection=None
        self.drag_mode=None; self.drag_source=None; self._drag_pad_orig=None
        self.filter_status=None; self.filter_tipo=None; self.search_id=None
        self.undo_stack.clear(); self.redo_stack.clear()
        self._rebuild_pad_to_net(); self._recalc_next_id(); self._clamp_familia_scroll()
        self._invalidar_cache_visiveis(); self.dirty=False
        snap=self._snapshot_view()
        if not img_nova: snap['img_path']=None
        self.views_store[self.view_atual]=snap
        if getattr(self,'auto_vincular',True):
            try: self._auto_vincular_todas_visoes()
            except Exception: pass
        prefs_lib.adicionar_recente(self.prefs,pasta)
        nome=os.path.basename(pasta)
        extra=f" | {len(self.componentes)} comp" if self.componentes else ""
        img_nome=os.path.basename(self.img_path_original) if self.img_path_original else "?"
        self._flash(f"Projeto aberto: {nome} | {len(self.pads)} pads | {len(self.nets)} famílias{extra} | img: {img_nome}{aviso_img}",cor=(0,220,120),dur=3.0)
        print(f"Projeto aberto: {pasta} | {len(self.pads)} pads | {len(self.nets)} famílias | img: {self.img_path_original}")
        return True

    # ------------------------------------------------------------------
    # VISÕES DO PROJETO: frente / verso / conector
    # ------------------------------------------------------------------
    def _snapshot_view(self):
        return {"img_path":self.img_path_original,"pads":copy.deepcopy(self.pads),
                "measurements":copy.deepcopy(self.measurements),"nets":copy.deepcopy(self.nets),
                "componentes":copy.deepcopy(self.componentes),"next_id":self.next_id,
                "next_net_id":self.next_net_id,"next_comp_id":self.next_comp_id,
                "anotacoes":copy.deepcopy(self.anotacoes),"next_anot_id":self.next_anot_id,
                "sliders":[s.val for s in self.sliders],"preset_key":self.preset_selected_key,
                "estado_placa":self.estado_placa,"filter_familia_id":self.filter_familia_id,
                "zoom":self.zoom,"pan_x":self.pan_x,"pan_y":self.pan_y}

    def _salvar_view_atual(self):
        self.views_store[self.view_atual]=self._snapshot_view()

    def _aplicar_view_runtime(self,vd,aplicar_imagem=True):
        vd=vd or {}
        self.pads=copy.deepcopy(vd.get('pads') or [])
        self.measurements={int(k):v for k,v in (vd.get('measurements') or {}).items()}
        self.nets=copy.deepcopy(vd.get('nets') or [])
        self.componentes=copy.deepcopy(vd.get('componentes') or [])
        self.anotacoes=copy.deepcopy(vd.get('anotacoes') or [])
        self.next_id=vd.get('next_id') or max((p.get('id',0) for p in self.pads),default=0)+1
        self.next_net_id=vd.get('next_net_id') or max((n.get('id',0) for n in self.nets),default=0)+1
        self.next_comp_id=vd.get('next_comp_id') or max((c.get('id',0) for c in self.componentes),default=0)+1
        self.next_anot_id=vd.get('next_anot_id') or max((a.get('id',0) for a in self.anotacoes),default=0)+1
        self.preset_selected_key=vd.get('preset_key',self.preset_selected_key)
        self.estado_placa=vd.get('estado_placa',self.estado_placa)
        self.filter_familia_id=vd.get('filter_familia_id')
        self.familia_selected=None; self.comp_scroll=0
        self._confirm_action=None
        for i,v in enumerate(vd.get('sliders') or []):
            if i<len(self.sliders):
                s=self.sliders[i]; s.val=max(s.min_v,min(s.max_v,v))
        self.zoom=vd.get('zoom',1.0) or 1.0
        self.pan_x=vd.get('pan_x',0) or 0; self.pan_y=vd.get('pan_y',0) or 0
        if aplicar_imagem:
            caminho=vd.get('img_path')
            if caminho: caminho=self._resolver_img_sessao(caminho,self.out_dir)
            if caminho and os.path.exists(caminho):
                img=ler_imagem(caminho)
                if img is not None:
                    self.img=img; self.img_path_original=caminho; self.h0,self.w0=img.shape[:2]
            self.base_scale=min((self.view_h-160)/max(1,self.h0),self._canvas_w()/max(1,self.w0)); self.base_scale=max(0.05,self.base_scale)
        self.selected=None; self.comp_selected=None; self.pending_connection=None
        self.anot_selected=None; self._anot_draft=None; self._anot_drag=None
        self.drag_mode=None; self.drag_source=None; self._drag_pad_orig=None
        self.filter_status=None; self.filter_tipo=None; self.search_id=None
        self.undo_stack.clear(); self.redo_stack.clear()
        self._rebuild_pad_to_net(); self._recalc_next_id(); self._clamp_familia_scroll(); self._invalidar_cache_visiveis()

    _TOKENS_VIEW={'frente':('frente','front','top','superior','src'),
                  'verso':('verso','back','bottom','inferior','tras','traseira'),
                  'conector':('conector','connector','conn','pin','header','plug')}

    def _pastas_busca_imagem(self):
        pastas=[]
        for p in (self.out_dir,os.path.dirname(os.path.abspath(self.img_path_original or '')),os.getcwd(),ROOT):
            if p and os.path.isdir(p):
                rp=os.path.realpath(p)
                if all(os.path.normcase(rp)!=os.path.normcase(x) for x in pastas): pastas.append(rp)
        for p in list(pastas):
            for sub in ('imagens','images'):
                d=os.path.join(p,sub)
                if os.path.isdir(d):
                    rp=os.path.realpath(d)
                    if all(os.path.normcase(rp)!=os.path.normcase(x) for x in pastas): pastas.append(rp)
        return pastas

    def _auto_imagem_view(self,view):
        tokens=self._TOKENS_VIEW.get(view,())
        if not tokens: return None
        for pasta in self._pastas_busca_imagem():
            try: nomes=os.listdir(pasta)
            except Exception: continue
            for n in nomes:
                low=n.lower()
                if not low.endswith(('.jpg','.jpeg','.png','.bmp','.tif','.tiff')): continue
                if any(t in low for t in tokens):
                    cand=os.path.join(pasta,n)
                    if os.path.isfile(cand): return cand
        return None

    def _perguntar_imagem_view(self,view):
        label=next((r for c,r,_ in self.views_disponiveis if c==view),view.upper())
        inicial=self.out_dir if os.path.isdir(self.out_dir) else os.getcwd()
        path = dialogs_lib.escolher_arquivo(
            f"Visão {label} - escolha a foto da placa",
            initialdir=inicial,
            filetypes=[("Imagens","*.jpg *.jpeg *.png *.bmp *.tiff"),("Todos","*.*")],
        )
        return path if path and os.path.exists(path) else None

    def _thumb_view(self,view):
        vd=self.views_store.get(view) or {}
        caminho=self.img_path_original if view==self.view_atual else vd.get('img_path')
        if caminho: caminho=self._resolver_img_sessao(caminho,self.out_dir)
        if not caminho or not os.path.exists(caminho):
            caminho=self._auto_imagem_view(view)
        if not caminho or not os.path.exists(caminho): return None
        try: chave=(os.path.normcase(caminho),os.path.getmtime(caminho))
        except Exception: chave=(caminho,0)
        if chave in self._thumbs: return self._thumbs[chave]
        try:
            img=ler_imagem(caminho)
            if img is None: return None
            h,w=img.shape[:2]; tw=300; th=max(50,int(h*tw/max(1,w)))
            if th>190:
                th=190; tw=max(60,int(w*th/max(1,h)))
            thumb=cv2.resize(img,(tw,th),interpolation=cv2.INTER_AREA)
            self._thumbs[chave]=thumb
            if len(self._thumbs)>12: self._thumbs.clear(); self._thumbs[chave]=thumb
            return thumb
        except Exception: return None

    def _trocar_view(self,nova):
        if nova not in [c for c,_,_ in self.views_disponiveis] or nova==self.view_atual: return
        # FIX v11.4: inline input e confirmacao de reset NAO podem sobreviver a troca de
        # visao (evita digitacao confirmada na visao errada e anotacao vazia perdida)
        self._confirm_action=None
        self._cancel_inline_input()
        if getattr(self,'auto_vincular',True):
            try: self._auto_vincular_com(nova)
            except Exception: pass
        self._salvar_view_atual()
        vd=self.views_store.get(nova)
        img_alvo=None
        if vd and vd.get('img_path'): img_alvo=self._resolver_img_sessao(vd.get('img_path'),self.out_dir)
        if not img_alvo: img_alvo=self._auto_imagem_view(nova)
        if not img_alvo:
            img_alvo=self._perguntar_imagem_view(nova)
            if not img_alvo:
                label=next((r for c,r,_ in self.views_disponiveis if c==nova),nova.upper())
                self._flash(f"Visão {label}: sem imagem definida (use [6] Foto da Visão)",cor=(255,180,0),dur=2.5)
                return
        primeira_vez=vd is None
        if primeira_vez:
            vd={'img_path':img_alvo,'pads':[],'measurements':{},'nets':[],'componentes':[],
                'anotacoes':[],'next_anot_id':1,
                'sliders':[s.val for s in self.sliders],'preset_key':self.preset_selected_key,
                'estado_placa':self.estado_placa,'filter_familia_id':None,'zoom':1.0,'pan_x':0,'pan_y':0}
            self.views_store[nova]=vd
        else:
            vd['img_path']=img_alvo
        self.view_atual=nova
        self._aplicar_view_runtime(vd)
        self.plugin_mgr.on_view_change(self, self.view_atual, nova)
        if primeira_vez and not self.pads and self.img is not None:
            self._detectar(False)
        self._salvar_view_atual(); self._salvar_sessao()
        label=next((r for c,r,_ in self.views_disponiveis if c==nova),nova.upper())
        self._flash(f"Visão {label} | {len(self.pads)} pads | {len(self.nets)} famílias",cor=(0,220,120),dur=2.2)

    def _definir_imagem_view(self):
        caminho=self._perguntar_imagem_view(self.view_atual)
        if not caminho: return
        img=ler_imagem(caminho)
        if img is None:
            self._flash("Imagem inválida",cor=(255,0,0),dur=2.0); return
        self._push_undo()
        self.img=img; self.img_path_original=caminho; self.h0,self.w0=img.shape[:2]
        self.pads=[]; self.measurements={}; self.nets=[]; self.componentes=[]
        self.anotacoes=[]; self.next_anot_id=1; self.anot_selected=None
        self.next_id=1; self.next_net_id=1; self.next_comp_id=1
        self.selected=None; self.comp_selected=None; self.pending_connection=None
        self._pad_to_net={}; self.undo_stack.clear(); self.redo_stack.clear()
        self._recalc_view()
        self._detectar(False)
        self._salvar_view_atual(); self._salvar_sessao()
        self._flash(f"Imagem da visão atual: {os.path.basename(caminho)}",cor=(0,200,255),dur=2.0)

    def _alternar_gpu(self):
        self.gpu_ativo=not self.gpu_ativo
        self.gpu_info=gpu_lib.ativar(self.gpu_ativo)
        self.gpu_ativo=gpu_lib.usando_gpu()
        self._gpu_pref_carregada=True
        # escolha manual: passa a ser respeitada nas proximas aberturas
        self.prefs['gpu_manual']=True; self._salvar_prefs()
        estado="GPU ON" if self.gpu_ativo else "GPU OFF (CPU)"
        self._flash(f"{estado} - {self.gpu_info.get('device','CPU')}",cor=(0,220,120) if self.gpu_ativo else (255,180,0),dur=2.5)
        self._marcar_dirty(); self._salvar_prefs()

    def _escolher_imagem_pasta(self,pasta,imgs):
        if not imgs:
            return None
        if dialogs_lib._disponivel():
            import tkinter as tk
            root=tk.Tk(); root.title("Nova placa - escolha a foto principal (FRENTE)")
            root.attributes('-topmost',True)
            tk.Label(root,text="Fotos encontradas na pasta do projeto:",anchor='w').pack(fill='x',padx=10,pady=(10,2))
            lb=tk.Listbox(root,width=80,height=min(12,len(imgs)),font=('Consolas',9))
            for f in imgs: lb.insert('end',os.path.relpath(f,pasta))
            lb.selection_set(0); lb.pack(padx=10,pady=6)
            escolha={'p':None}
            def ok():
                sel=lb.curselection()
                if sel: escolha['p']=imgs[sel[0]]; root.destroy()
            tk.Button(root,text="Abrir como FRENTE",width=20,default='active',command=ok).pack(pady=8)
            lb.bind('<Double-Button-1>',lambda e: ok())
            root.bind('<Return>',lambda e: ok()); root.bind('<Escape>',lambda e: root.destroy())
            root.mainloop()
            return escolha['p']
        # Fallback sem tkinter (console)
        print(f"\n=== ESCOLHER FOTO PRINCIPAL ===")
        print(f"Pasta: {pasta}")
        for i, f in enumerate(imgs, 1):
            print(f"  {i}. {os.path.relpath(f, pasta)}")
        print("  q. Cancelar")
        try:
            escolha = input("Escolha um número: ").strip()
        except EOFError:
            return None
        if escolha.lower() in ('q', ''):
            return None
        try:
            idx = int(escolha) - 1
            if 0 <= idx < len(imgs):
                return imgs[idx]
        except ValueError:
            pass
        self._flash("Escolha invalida", cor=(255, 180, 0), dur=2.0)
        return None

    def _novo_projeto_em_pasta(self,pasta):
        exts=('.jpg','.jpeg','.png','.bmp','.tif','.tiff','.heic','.heif')
        imgs=[]
        for raiz,dirs,files in os.walk(pasta):
            if os.path.normcase(os.path.abspath(raiz))!=os.path.normcase(os.path.abspath(pasta)):
                if os.path.basename(raiz).lower() not in ('imagens','images','fotos'):
                    continue
            for f in files:
                if f.lower().endswith(exts): imgs.append(os.path.join(raiz,f))
        imgs.sort()
        if not imgs:
            self._flash("Sem sessao/CSV e sem fotos nesta pasta",cor=(255,100,0),dur=3.0); return False
        escolhida=imgs[0] if len(imgs)==1 else self._escolher_imagem_pasta(pasta,imgs)
        if not escolhida: return False
        img=ler_imagem(escolhida)
        if img is None:
            self._flash("Falha ao ler a imagem escolhida",cor=(255,0,0),dur=2.5); return False
        self.out_dir=os.path.abspath(pasta)
        self.session_path=os.path.join(self.out_dir,'sessao_v87.json')
        self.img=img; self.img_path_original=escolhida; self.h0,self.w0=img.shape[:2]
        self.pads=[]; self.measurements={}; self.nets=[]; self.componentes=[]
        self.next_id=1; self.next_net_id=1; self.next_comp_id=1
        self.selected=None; self.comp_selected=None; self.pending_connection=None
        self.views_store={}; self.view_atual='frente'; self._thumbs={}
        self.undo_stack.clear(); self.redo_stack.clear(); self._pad_to_net={}
        self._recalc_view(); self._detectar(False)
        self.views_store={'frente':self._snapshot_view()}
        self.dirty=False
        prefs_lib.adicionar_recente(self.prefs,self.out_dir)
        self.prefs['ultima_pasta']=self.out_dir; self._salvar_prefs()
        self._salvar_sessao()
        extra=f" | {len(imgs)} fotos na pasta" if len(imgs)>1 else ""
        self._flash(f"Projeto novo em {os.path.basename(self.out_dir)} | {len(self.pads)} pads{extra}",cor=(0,220,120),dur=4.0)
        print(f"Projeto novo: {self.out_dir} | imagem: {escolhida} | {len(self.pads)} pads")
        return True

    # ------------------------------------------------------------------
    # VÍNCULO ENTRE VISÕES (frente/verso/conector)
    # ------------------------------------------------------------------
    def _novo_uid(self, pref='lk'):
        return f"{pref}_{uuid.uuid4().hex[:12]}"

    def _iter_views_dados(self):
        """Gera (view, pads, nets, vd) para a visão atual e as demais."""
        vd_cur=self.views_store.get(self.view_atual)
        if not isinstance(vd_cur,dict) or 'pads' not in vd_cur:
            # FIX v11.4: store parcial {'img_path':...} causava gravacoes de
            # next_net_id/nets em dict incompleto; snapshot completo e consistente
            vd_cur=self._snapshot_view()
            self.views_store[self.view_atual]=vd_cur
        yield self.view_atual,self.pads,self.nets,vd_cur
        vistos={self.view_atual}
        for nome,vd in self.views_store.items():
            if nome in vistos: continue
            pads=vd.setdefault('pads',[]); nets=vd.setdefault('nets',[])
            yield nome,pads,nets,vd

    def _net_uid_em(self,nets,uid):
        return next((n for n in nets if n.get('uid')==uid),None)

    def _garantir_net_uid(self,net):
        if not net.get('uid'): net['uid']=self._novo_uid('net')
        return net['uid']

    def _propagar_todos(self):
        """Sincroniza famílias com mesmo UID e pads com mesmo link em todas as visões."""
        dados=list(self._iter_views_dados())
        info={}
        for view,pads,nets,vd in dados:
            for n in nets:
                uid=n.get('uid')
                if not uid: continue
                links={p.get('link') for p in pads if p.get('id') in n.get('pads',[]) and p.get('link')}
                info.setdefault(uid,{}).setdefault(view,set()).update(links)
        if not info:
            return
        modelos={}
        for uid in info:
            nome=''; cor=None
            for view,pads,nets,vd in dados:
                n=self._net_uid_em(nets,uid)
                if n:
                    if n.get('nome'): nome=n['nome']
                    if n.get('cor'): cor=list(n['cor'])
            modelos[uid]=(nome,cor)
        for uid,por_view in info.items():
            todos=set()
            for s in por_view.values(): todos|=s
            nome,cor=modelos[uid]
            for view,pads,nets,vd in dados:
                n=self._net_uid_em(nets,uid)
                if n is None:
                    nid=vd.get('next_net_id') or (max((x.get('id',0) for x in nets),default=0)+1)
                    n={'id':nid,'pads':[],'nome':nome,'cor':cor or [80,140,255],'uid':uid}
                    nets.append(n); vd['next_net_id']=nid+1
                for p in pads:
                    if p.get('link') in todos and p.get('id') not in n['pads']:
                        n['pads'].append(p.get('id'))
                if nome: n['nome']=nome
                if cor: n['cor']=list(cor)
        self._marcar_dirty()

    def _remover_link_de_net(self,uid,link):
        if not uid or not link: return
        for view,pads,nets,vd in self._iter_views_dados():
            alvo=self._net_uid_em(nets,uid)
            if not alvo: continue
            ids_remover={p.get('id') for p in pads if p.get('link')==link}
            alvo['pads']=[pid for pid in alvo['pads'] if pid not in ids_remover]
        self._marcar_dirty()

    def _sincronizar_net(self,net):
        uid=net.get('uid')
        if not uid: return
        for view,pads,nets,vd in self._iter_views_dados():
            if view==self.view_atual: continue
            alvo=self._net_uid_em(nets,uid)
            if alvo:
                alvo['nome']=net.get('nome','')
                alvo['cor']=list(net.get('cor',alvo.get('cor',[80,140,255])))
        self._marcar_dirty()

    def _alvos_do_link(self,link):
        alvos=[]
        for nome,pads,_,_ in self._iter_views_dados():
            if nome==self.view_atual: continue
            for p in pads:
                if p.get('link')==link and p.get('link'):
                    alvos.append(f"{nome.upper()} #{p.get('id')}")
        return alvos

    def _ciclar_view(self,delta):
        ordem=[c for c,_,_ in self.views_disponiveis]
        if self.view_atual not in ordem: return
        i=(ordem.index(self.view_atual)+delta)%len(ordem)
        self._trocar_view(ordem[i])

    def _auto_vincular_com(self, view):
        """Reconhece pads passantes (mesmo furo/pad) entre a visão atual e outra."""
        if view==self.view_atual or not self.pads:
            return 0
        vd=self.views_store.get(view) or {}
        if not vd.get('img_path'):
            return 0
        pads_b=vd.get('pads') or []
        if not pads_b:
            return 0
        links_atuais={p.get('link') for p in self.pads if p.get('link')}
        if links_atuais and any(q.get('link') in links_atuais for q in pads_b):
            return 0
        img_b=ler_imagem(self._resolver_img_sessao(vd.get('img_path'),self.out_dir))
        if img_b is None:
            return 0
        H,mirror,score=transform_lib.alinhar_melhor(self.img,img_b)
        if H is None or score<10:
            return 0
        wb=img_b.shape[1]
        pts=transform_lib.aplicar_h(H,[(p.get('cx',0),p.get('cy',0)) for p in self.pads])
        if mirror:
            pts=[(wb-x,y) for x,y in pts]
        dists=[]
        for i,(x,y) in enumerate(pts):
            for j,q in enumerate(pads_b):
                dists.append((((x-q.get('cx',0))**2+(y-q.get('cy',0))**2)**0.5,i,j))
        dists.sort(key=lambda t:t[0])
        usados_a=set(); usados_b=set(); pares=[]
        for d,i,j in dists:
            if i in usados_a or j in usados_b: continue
            p=self.pads[i]; q=pads_b[j]
            tol=max(12.0,max(p.get('w',12),q.get('w',12),p.get('h',12),q.get('h',12)))
            if d>tol: continue
            pares.append((p,q)); usados_a.add(i); usados_b.add(j)
        if not pares:
            return 0
        for p,q in pares:
            uid=self._novo_uid('lk')
            p['link']=uid; q['link']=uid
        for p,q in pares:
            neta=next((n for n in self.nets if p.get('id') in n.get('pads',[])),None)
            netb=next((n for n in (vd.get('nets') or []) if q.get('id') in n.get('pads',[])),None)
            if neta and netb:
                uid=neta.get('uid') or netb.get('uid') or self._novo_uid('net')
                neta['uid']=uid; netb['uid']=uid
        self.views_store[self.view_atual]=self._snapshot_view()
        self._propagar_todos()
        self._marcar_dirty(); self._salvar_sessao()
        self._flash(f"Pads passantes: {len(pares)} vinculados com {view.upper()}",cor=(0,220,120),dur=2.5)
        return len(pares)

    def _auto_vincular_todas_visoes(self):
        n=0
        for c,_,_ in self.views_disponiveis:
            if c!=self.view_atual and (self.views_store.get(c) or {}).get('img_path'):
                try: n+=self._auto_vincular_com(c)
                except Exception: pass
        return n

    def _vincular_pads_auto(self):
        opcoes=[(c,r) for c,r,_ in self.views_disponiveis if c!=self.view_atual and (self.views_store.get(c,{}) or {}).get('img_path')]
        if not opcoes:
            self._flash("Cadastre as imagens das outras visoes primeiro (tecla 6)",cor=(255,180,0),dur=3.0); return
        alvo_view=opcoes[0][0]
        if len(opcoes)>1:
            if dialogs_lib._disponivel():
                import tkinter as tk
                root=tk.Tk(); root.title("Vincular com qual visao?"); root.attributes('-topmost',True)
                lb=tk.Listbox(root,width=42,height=4,font=('Consolas',10))
                for c,r in opcoes: lb.insert('end',f"{r}")
                lb.selection_set(0); lb.pack(padx=10,pady=10)
                escolha={'v':None}
                def ok():
                    sel=lb.curselection()
                    if sel: escolha['v']=opcoes[sel[0]][0]; root.destroy()
                tk.Button(root,text="Vincular",command=ok).pack(pady=6)
                root.bind('<Return>',lambda e: ok()); root.mainloop()
                if not escolha['v']: return
                alvo_view=escolha['v']
            else:
                print("\n=== VINCULAR COM QUAL VISÃO? ===")
                for i,(c,r) in enumerate(opcoes,1):
                    print(f"  {i}. {r} ({c})")
                print("  q. Cancelar (usa a primeira)")
                try:
                    escolha = input("Escolha um número: ").strip()
                except EOFError:
                    escolha = ''
                if escolha.lower() not in ('q',''):
                    try:
                        idx=int(escolha)-1
                        if 0<=idx<len(opcoes):
                            alvo_view=opcoes[idx][0]
                    except ValueError:
                        pass
        vd_alvo=self.views_store.get(alvo_view) or {}
        img_alvo=ler_imagem(self._resolver_img_sessao(vd_alvo.get('img_path'),self.out_dir))
        if img_alvo is None:
            self._flash("Imagem da visao alvo nao encontrada",cor=(255,0,0),dur=2.5); return
        H,mirror,score=transform_lib.alinhar_melhor(self.img,img_alvo)
        if H is None or score<10:
            self._flash("Alinhamento fraco - use o vinculo manual (2 cliques)",cor=(255,120,0),dur=3.5); return
        w_alvo=img_alvo.shape[1]
        pts=transform_lib.aplicar_h(H,[(p.get('cx',0),p.get('cy',0)) for p in self.pads])
        if mirror: pts=[(w_alvo-x,y) for x,y in pts]
        alvo_pads=vd_alvo.get('pads') or []
        dists=[]
        for i,(x,y) in enumerate(pts):
            for j,q in enumerate(alvo_pads):
                d=((x-q.get('cx',0))**2+(y-q.get('cy',0))**2)**0.5
                dists.append((d,i,j))
        dists.sort(key=lambda t:t[0])
        usados_a=set(); usados_b=set(); pares=[]
        for d,i,j in dists:
            if i in usados_a or j in usados_b: continue
            p=self.pads[i]; q=alvo_pads[j]
            tol=max(12.0,1.0*max(p.get('w',12),q.get('w',12),p.get('h',12),q.get('h',12)))
            if d>tol: continue
            pares.append((p,q,d)); usados_a.add(i); usados_b.add(j)
        if not pares:
            self._flash("Nenhum pad correspondente encontrado (ajuste/alinhe as fotos)",cor=(255,120,0),dur=3.5); return
        for p,q,d in pares:
            uid=p.get('link') or q.get('link') or self._novo_uid('lk')
            if p.get('link') and q.get('link') and p['link']!=q['link']:
                antigo=q['link']
                for view,pads,_,_ in self._iter_views_dados():
                    for pp in pads:
                        if pp.get('link')==antigo: pp['link']=uid
            p['link']=uid; q['link']=uid
        # unifica familias quando os dois pads ja estao em familias
        for p,q,d in pares:
            neta=next((n for n in self.nets if p.get('id') in n.get('pads',[])),None)
            netb=next((n for n in (vd_alvo.get('nets') or []) if q.get('id') in n.get('pads',[])),None)
            if neta and netb:
                uid=neta.get('uid') or netb.get('uid') or self._novo_uid('net')
                neta['uid']=uid; netb['uid']=uid
        self.views_store[self.view_atual]=self._snapshot_view()
        self._propagar_todos()
        self._marcar_dirty(); self._salvar_sessao()
        self._flash(f"Vinculados {len(pares)} pads com {alvo_view.upper()} (inliers {score}{' + espelho' if mirror else ''})",cor=(0,220,120),dur=3.5)

    def _vincular_pad_manual(self):
        if self.selected is None or self.selected>=len(self.pads):
            self._flash("Selecione um pad nesta visao primeiro",cor=(255,180,0),dur=3.0); return
        p=self.pads[self.selected]; pid=p.get('id')
        pend=getattr(self,'_link_pendente',None)
        if pend is None:
            self._link_pendente=(self.view_atual,pid)
            self.views_store[self.view_atual]=self._snapshot_view()
            self._flash(f"Pad #{pid} marcado - troque de visao, selecione o equivalente e use de novo",cor=(0,200,255),dur=4.0)
            return
        view_a,pid_a=pend
        if view_a==self.view_atual:
            self._flash("Troque de visao antes do segundo clique",cor=(255,180,0),dur=2.5); return
        vd_a=self.views_store.get(view_a) or {}
        pa=next((x for x in (vd_a.get('pads') or []) if x.get('id')==pid_a),None)
        if not pa:
            self._link_pendente=None; self._flash("Pad de origem nao encontrado",cor=(255,0,0),dur=2.5); return
        uid=pa.get('link') or p.get('link') or self._novo_uid('lk')
        pa['link']=uid; p['link']=uid
        self._link_pendente=None
        self.views_store[self.view_atual]=self._snapshot_view()
        self._propagar_todos()
        self._marcar_dirty(); self._salvar_sessao()
        self._flash(f"Vinculado: {view_a.upper()} #{pid_a} <-> {self.view_atual.upper()} #{pid}",cor=(0,220,120),dur=3.5)

    # ------------------------------------------------------------------
    # v11.2: produtividade de bancada
    # ------------------------------------------------------------------
    def _progresso(self):
        total=len(self.pads); med=0; falhas=0
        for p in self.pads:
            m=self.measurements.get(p.get('id')) or {}
            st=m.get('status') if isinstance(m,dict) else None
            if st in ('OK','SUSP','FALHA'): med+=1
            if st=='FALHA': falhas+=1
        pct=0 if total==0 else int(100*med/total)
        return med,total,pct,falhas

    def _proximo_sem_medir(self,salvar=False):
        if salvar and self.right_mode=='edit': self._salvar_edicao()
        if not self.pads: return
        n=len(self.pads); ini=((self.selected+1) if self.selected is not None else 0)
        def pendente(i):
            m=self.measurements.get(self.pads[i].get('id')) or {}
            return not (isinstance(m,dict) and m.get('status'))
        vis=self._pads_visiveis_idx()
        ordem=[(ini+k)%n for k in range(n)]
        cand=[i for i in ordem if pendente(i) and i in vis] or [i for i in ordem if pendente(i)]
        if not cand:
            self._flash("Todos os pads já medidos!",cor=(0,220,120),dur=2.0); return
        if self.tab!='anotar': self._trocar_aba('anotar')
        self.selected=cand[0]; self._iniciar_edicao(self.selected)
        pid=self.pads[self.selected].get('id')
        self._flash(f"Pad #{pid} - [Enter] salva | [Ctrl+N] salva e vai ao próximo",cor=(0,200,255),dur=3.0)

    def _alternar_camada(self,chave):
        if chave in self.layers:
            self.layers[chave]=not self.layers[chave]
            self._invalidar_cache_visiveis(); self._salvar_prefs()
            self._flash(f"Camada {chave}: {'ON' if self.layers[chave] else 'OFF'}",cor=(0,200,255),dur=1.5)

    def _comandos_lista(self):
        base=[
            ("Salvar projeto", 'salvar'),
            ("Abrir projeto [L]", 'abrir_proj'),
            ("Abrir imagem [O]", 'abrir_img'),
            ("Detectar pads [D]", 'detectar'),
            ("Detectar smart (auto+via+forma)", 'detectar_smart'),
            ("Detectar por exemplo (pad selecionado)", 'detectar_exemplo'),
            ("Alternar detector smart/classico", 'modo_detector'),
            ("Detector IA (modelo ONNX)", 'modo_detector_ia'),
            ("Escolher modelo IA (ONNX)...", 'modelo_ia_escolher'),
            ("Exportar dataset YOLO (projeto atual)", 'exportar_dataset'),
            ("Pre-anotar album de fotos (YOLO)", 'pre_anotar_album'),
            ("Vincular pads entre visoes (auto)", 'vincular_views'),
            ("Vincular pad manual (2 cliques)", 'vincular_manual'),
            ("Auto-vincular pads passantes (on/off)", 'toggle_auto_vincular'),
            ("Visao anterior (,)", 'view_ant'),
            ("Proxima visao (.)", 'view_prox'),
            ("Sensibilidade smart +", 'smart_sens_mais'),
            ("Sensibilidade smart -", 'smart_sens_menos'),
            ("Detectar por tiles (placas grandes)", 'detectar_tiles'),
            ("Relatório HTML do projeto", 'relatorio'),
            ("Comparar com placa ouro", 'comparar_ouro'),
            ("Capturar da câmera", 'camera'),
            ("Transferir anotações para nova foto", 'transferir'),
            ("Importar centroides (CSV/KiCad)", 'importar_centroides'),
            ("Exportar KiCad PCB (.kicad_pcb)", 'export_kicad'),
            ("Exportar Gerber (cobre)", 'export_gerber'),
            ("Importar KiCad / Eagle / Gerber", 'import_pcb'),
            ("Régua / calibrar escala mm-por-px", 'regua'),
            ("Camadas (visibilidade)", 'camadas'),
            ("Próximo pad sem medir", 'prox_pendente'),
            ("Painel de famílias", 'familias'),
            ("Painel de componentes", 'comp_painel'),
            ("Novo componente (desenhar)", 'comp_nova'),
            ("Reconhecer tipo do componente", 'comp_reconhecer'),
            ("Auto pino 1 do componente", 'comp_auto_pino1'),
            ("Buscar datasheet (componente ou part number)", 'comp_datasheet'),
            ("Buscar datasheet por part number", 'datasheet_livre'),
            ("Abrir pasta de datasheets", 'datasheets_pasta'),
            ("Exportar pinagem CSV", 'comp_pinagem'),
            ("Buscar datasheet do componente", 'comp_datasheet'),
            ("Definir pino 1 (pad selecionado)", 'comp_pino1'),
            ("Excluir componente selecionado", 'comp_excluir'),
            ("Anotar na placa [Y]", 'modo_anot'),
            ("Nomear pino do pad [I]", 'modo_pino'),
            ("Marcar/desmarcar GND [U]", 'modo_gnd'),
            ("Numerar pinos do componente", 'pin_numerar'),
            ("Mira de precisao (on/off)", 'toggle_mira'),
            ("Limpar anotacoes da visao", 'anot_limpar'),
            ("Abrir/fechar menu lateral", 'sidebar'),
            ("Alternar IDs [T]", 'toggle_ids'),
            ("Alternar GPU [J]", 'toggle_gpu'),
            ("Centralizar / Fit [0]", 'fit'),
            ("Alternar máscara [H]", 'mascara'),
            ("Recuperar última sessão salva", 'recuperar_ultimo'),
        ]
        for p in (self.prefs.get('recentes') or [])[:4]:
            base.append((f"Recente: {os.path.basename(str(p))}", f"recente:{p}"))
        return base

    def _atualizar_paleta(self):
        q=_ascii(self.paleta_cmd.get('query') or '').lower()
        itens=[(lab,key) for lab,key in self._comandos_lista() if q in _ascii(lab).lower()]
        self.paleta_cmd['itens']=itens
        self.paleta_cmd['sel']=0 if itens else -1

    def _abrir_paleta(self):
        self.paleta_cmd={'active':True,'query':'','sel':0,'itens':[]}
        self._atualizar_paleta()

    def _executar_paleta(self):
        it=self.paleta_cmd.get('itens') or []
        sel=self.paleta_cmd.get('sel',0)
        if not (0<=sel<len(it)): self.paleta_cmd['active']=False; return
        key=it[sel][1]; self.paleta_cmd['active']=False
        if key.startswith('recente:'):
            self._abrir_projeto(key.split('recente:',1)[1]); return
        self._on_button(key)

    def _gerar_relatorio(self):
        self._salvar_view_atual()
        ts=time.strftime('%Y%m%d_%H%M%S')
        destino=os.path.join(os.path.abspath(self.out_dir),f"relatorio_{ts}.html")
        os.makedirs(os.path.dirname(destino),exist_ok=True)
        est={'projeto_nome':os.path.basename(os.path.abspath(self.out_dir))}
        r=report_lib.gerar_html(destino,os.path.abspath(self.out_dir),self.views_store,est,self.mm_por_px)
        if r:
            try: webbrowser.open('file:///'+os.path.abspath(r).replace('\\','/'))
            except Exception: pass
            self._flash(f"Relatório: {os.path.basename(r)}",cor=(0,220,120),dur=3.0)
        else:
            self._flash("Falha ao gerar relatório",cor=(255,0,0),dur=2.0)

    def _capturar_camera(self):
        cap=None
        try:
            cap=cv2.VideoCapture(0,cv2.CAP_DSHOW)
            if not cap.isOpened(): cap=cv2.VideoCapture(0)
            if not cap or not cap.isOpened():
                self._flash("Câmera não encontrada",cor=(255,100,0),dur=2.0); return
            win="Camera - SPACE captura / ESC cancela"
            cv2.namedWindow(win,cv2.WINDOW_NORMAL); cv2.resizeWindow(win,900,520)
            frame=None
            while True:
                ok,fr=cap.read()
                if not ok: break
                cv2.imshow(win,fr); k=cv2.waitKey(15)&0xFF
                if k==27: break
                if k==32: frame=fr.copy(); break
            try: cv2.destroyWindow(win)
            except Exception: pass
            cap.release()
            if frame is None: return
            pasta=os.path.join(os.path.abspath(self.out_dir),'capturas'); os.makedirs(pasta,exist_ok=True)
            caminho=os.path.join(pasta,f"captura_{time.strftime('%Y%m%d_%H%M%S')}.jpg")
            imwrite_u(caminho,frame)
            self._push_undo()
            self.img=frame; self.img_path_original=caminho; self.h0,self.w0=frame.shape[:2]
            self.pads=[]; self.measurements={}; self.nets=[]; self.componentes=[]
            self.anotacoes=[]; self.next_anot_id=1; self.anot_selected=None
            self.next_id=1; self.next_net_id=1; self.next_comp_id=1; self.selected=None
            self._pad_to_net={}; self.undo_stack.clear(); self.redo_stack.clear()
            self._recalc_view(); self._detectar(False)
            self._salvar_view_atual(); self._salvar_sessao()
            self._flash(f"Captura salva: {os.path.basename(caminho)}",cor=(0,220,120),dur=2.5)
        except Exception as e:
            self._flash(f"Erro câmera: {e}",cor=(255,0,0),dur=2.5)
        finally:
            try:
                if cap: cap.release()
            except Exception: pass

    def _transferir_anotacoes(self):
        inicial=os.path.abspath(self.out_dir) if os.path.isdir(self.out_dir) else os.getcwd()
        path = dialogs_lib.escolher_arquivo(
            "Nova foto da MESMA visão (anotações serão transferidas)",
            initialdir=inicial,
            filetypes=[("Imagens","*.jpg *.jpeg *.png *.bmp *.tiff"),("Todos","*.*")],
        )
        if not path or not os.path.exists(path): return
        novo=ler_imagem(path)
        if novo is None: self._flash("Imagem inválida",cor=(255,0,0),dur=2.0); return
        H=transform_lib.alinhar(self.img,novo)
        if H is None:
            self._flash("Não foi possível alinhar as imagens (poucos pontos em comum)",cor=(255,0,0),dur=3.0); return
        self._push_undo()
        self.pads=transform_lib.transferir_pads(self.pads,H)
        self.componentes=transform_lib.transferir_componentes(self.componentes,H)
        if self.anotacoes:
            pts=transform_lib.aplicar_h(H,[(a.get('x',0),a.get('y',0)) for a in self.anotacoes])
            for a,(nx,ny) in zip(self.anotacoes,pts):
                a['x']=int(round(nx)); a['y']=int(round(ny))
        self.img=novo; self.img_path_original=path; self.h0,self.w0=novo.shape[:2]
        self._recalc_view(); self._rebuild_pad_to_net(); self._salvar_view_atual(); self._marcar_dirty()
        self._flash(f"Transferido: {len(self.pads)} pads, {len(self.componentes)} componentes",cor=(0,220,120),dur=3.0)

    def _importar_centroides(self):
        path = dialogs_lib.escolher_arquivo(
            "CSV de centroides (KiCad pos / genérico)",
            initialdir=os.path.abspath(self.out_dir),
            filetypes=[("CSV","*.csv *.txt"),("Todos","*.*")],
        )
        if not path or not os.path.exists(path): return
        linhas=transform_lib.ler_centroides_csv(path)
        if not linhas:
            self._flash("CSV sem centroides reconhecíveis",cor=(255,100,0),dur=2.5); return
        pts=transform_lib.encaixar_centroides(linhas,self.w0,self.h0,self.mm_por_px)
        self._push_undo()
        for p in pts:
            self.pads.append({'id':self.next_id,'cx':p['x'],'cy':p['y'],'x':p['x'],'y':p['y'],'w':12,'h':12,'area':100,'manual':False,'ref':p.get('ref','')})
            self.next_id+=1
        self.pads.sort(key=lambda pp:(pp['cy']//80,pp['cx']))
        self._invalidar_cache_visiveis(); self._marcar_dirty()
        self._salvar_view_atual(); self._salvar_sessao()
        self._flash(f"{len(pts)} centroides importados",cor=(0,220,120),dur=2.5)

    # ==================== IMPORT/EXPORT PCB (KiCad / Eagle / Gerber) ====================

    def _lado_da_view(self):
        return 'verso' if self.view_atual=='verso' else 'frente'

    def _nome_base_export(self):
        base=os.path.basename(os.path.abspath(self.out_dir)) or 'placa'
        return f"{base}_{self.view_atual}"

    def _exportar_kicad(self):
        if self.tab=='anotar' and self.right_mode=='edit': self._salvar_edicao()
        self._salvar_view_atual()
        path = dialogs_lib.salvar_arquivo(
            "Exportar KiCad PCB",
            initialdir=os.path.abspath(self.out_dir),
            initialfile=self._nome_base_export()+'.kicad_pcb',
            defaultextension='.kicad_pcb',
            filetypes=[("KiCad PCB","*.kicad_pcb"),("Todos","*.*")],
        )
        if not path: return
        try:
            res=kicad_lib.exportar_kicad(self.pads,self.componentes,self.nets,path,
                                         self.mm_por_px,self._lado_da_view(),self.w0,self.h0)
        except Exception as e:
            self._flash(f"KiCad: falha ao exportar ({e})",cor=(255,0,0),dur=3.5); return
        msg=f"KiCad: {res['pads']} pads, {res['nets']} nets -> {os.path.basename(res['caminho'])}"
        if res['avisos']: msg+=f" | {res['avisos'][0]}"
        self._flash(msg,cor=(0,220,120) if res['pads'] else (255,180,0),dur=5.0)
        self.plugin_mgr.on_exportar_pcb(self, 'kicad', path)

    def _exportar_gerber(self):
        if self.tab=='anotar' and self.right_mode=='edit': self._salvar_edicao()
        self._salvar_view_atual()
        pasta=os.path.join(os.path.abspath(self.out_dir),'gerber')
        try:
            os.makedirs(pasta,exist_ok=True)
        except Exception:
            pass
        path = dialogs_lib.salvar_arquivo(
            "Exportar Gerber (cobre)",
            initialdir=pasta,
            initialfile=self._nome_base_export()+'.gbr',
            defaultextension='.gbr',
            filetypes=[("Gerber","*.gbr *.gtl *.gbl *.ger"),("Todos","*.*")],
        )
        if not path: return
        try:
            res=kicad_lib.exportar_gerber(self.pads,path,self.mm_por_px,self.w0,self.h0,self._lado_da_view())
        except Exception as e:
            self._flash(f"Gerber: falha ao exportar ({e})",cor=(255,0,0),dur=3.5); return
        msg=f"Gerber: {res['pads']} pads, {res['aperturas']} aperturas -> {os.path.basename(res['caminho'])}"
        if res['avisos']: msg+=f" | {res['avisos'][0]}"
        self._flash(msg,cor=(0,220,120) if res['pads'] else (255,180,0),dur=5.0)
        self.plugin_mgr.on_exportar_pcb(self, 'gerber', path)

    def _importar_pcb(self):
        path = dialogs_lib.escolher_arquivo(
            "Importar KiCad / Eagle / Gerber",
            initialdir=os.path.abspath(self.out_dir),
            filetypes=[("PCB (KiCad/Eagle/Gerber)","*.kicad_pcb *.brd *.gbr *.ger *.gtl *.gbl *.art"),
                       ("KiCad","*.kicad_pcb"),("Eagle","*.brd"),("Gerber","*.gbr *.ger *.gtl *.gbl *.art"),
                       ("Todos","*.*")],
        )
        if not path or not os.path.exists(path): return
        try:
            res=kicad_lib.importar_arquivo(path,self.w0,self.h0,self.mm_por_px)
        except Exception as e:
            self._flash(f"Importar: falha ({e})",cor=(255,0,0),dur=3.5); return
        if not res['pads']:
            aviso=res['avisos'][0] if res['avisos'] else 'nenhum pad encontrado'
            self._flash(f"Importar: {aviso}",cor=(255,180,0),dur=4.5); return
        self._push_undo()
        ids=[]
        for p in res['pads']:
            novo={'id':self.next_id,'cx':p['cx'],'cy':p['cy'],'x':p['cx'],'y':p['cy'],
                  'w':p['w'],'h':p['h'],'area':p['area'],'manual':False,'forma':p.get('forma','retangulo')}
            if p.get('pino'): novo['pino']=p['pino']
            if p.get('ref'): novo['ref']=p['ref']
            self.pads.append(novo); ids.append(self.next_id); self.next_id+=1
        for c in res['componentes']:
            comp={'id':self.next_comp_id,'nome':c['nome'],'tipo':c.get('tipo','ci'),
                  'forma':c.get('forma','retangulo_h'),'cor':list(c.get('cor') or [80,140,255]),
                  'pads':[ids[i] for i in (c.get('pads') or []) if 0<=i<len(ids)],
                  'x1':c.get('x1',0),'y1':c.get('y1',0),'x2':c.get('x2',0),'y2':c.get('y2',0),
                  'valor':'','tensao':'','obs':'','pino1':None}
            if comp['pads']: comp['pino1']=comp['pads'][0]
            self.componentes.append(comp); self.next_comp_id+=1
        for n in res['nets']:
            membros=[ids[i] for i in (n.get('pads') or []) if 0<=i<len(ids)]
            if not membros: continue
            self.nets.append({'id':self.next_net_id,'nome':n['nome'],
                              'cor':list(n.get('cor') or [80,140,255]),'pads':membros})
            self.next_net_id+=1
        self.pads.sort(key=lambda pp:(pp['cy']//80,pp['cx']))
        self._rebuild_pad_to_net(); self._invalidar_cache_visiveis(); self._marcar_dirty()
        self._salvar_view_atual(); self._salvar_sessao()
        extra=f", {len(res['componentes'])} comps, {len(res['nets'])} nets" if res['componentes'] else ''
        self._flash(f"{res['formato'].upper()}: {len(ids)} pads importados{extra}",cor=(0,220,120),dur=4.5)

    # ==================== DIFF VIEWER (frente x verso) ====================

    def _tem_duas_visoes_com_imagem(self):
        """Retorna True se pelo menos 2 visões têm imagem definida."""
        cont=0
        for c,_,_ in self.views_disponiveis:
            vd=self.views_store.get(c) or {}
            caminho=vd.get('img_path')
            if caminho:
                caminho=self._resolver_img_sessao(caminho,self.out_dir)
                if caminho and os.path.exists(caminho):
                    cont+=1
        return cont>=2

    def _carregar_imagem_view(self, view):
        """Carrega a imagem de uma visão (frente/verso/conector) e retorna (img, caminho)."""
        vd=self.views_store.get(view) or {}
        caminho=vd.get('img_path')
        if not caminho:
            caminho=self._auto_imagem_view(view)
        if not caminho:
            caminho=self._perguntar_imagem_view(view)
        if not caminho or not os.path.exists(caminho):
            return None, None
        caminho=self._resolver_img_sessao(caminho, self.out_dir)
        img=ler_imagem(caminho)
        return img, caminho

    def _obter_pads_view(self, view):
        """Retorna os pads de uma visão (lista) ou []."""
        vd=self.views_store.get(view) or {}
        return vd.get('pads') or []

    def _toggle_diff(self):
        """Ativa/desativa o modo diff viewer."""
        if not self._tem_duas_visoes_com_imagem():
            self._flash("Diff precisa de 2 visões com imagem (ex: frente + verso). Use [6] Foto da Visão.",cor=(255,180,0),dur=4.0)
            return
        self.modo_diff=not self.modo_diff
        if self.modo_diff:
            self.right_mode='menu'  # fecha painéis laterais para focar no canvas
            self._recalcular_diff()
            self._flash("DIFF ligado: comparando frente x verso",cor=(0,220,120),dur=3.0)
        else:
            self._flash("DIFF desligado",cor=(160,160,170),dur=2.0)

    def _toggle_diff_lado_a_lado(self):
        self.diff_side_by_side=True
        self.diff_precisa_recalcular=False
        self._flash("Diff: lado a lado",cor=(0,200,255),dur=2.0)

    def _toggle_diff_sobreposto(self):
        self.diff_side_by_side=False
        self.diff_precisa_recalcular=False
        self._flash("Diff: sobreposto",cor=(0,200,255),dur=2.0)

    def _recalcular_diff(self):
        """Recalcula o diff entre a visão de referência e a alvo."""
        if not self._tem_duas_visoes_com_imagem():
            self._flash("Diff: defina imagem em 2 visões antes",cor=(255,180,0),dur=3.0); return
        img_a, _ = self._carregar_imagem_view(self.diff_view_ref)
        img_b, _ = self._carregar_imagem_view(self.diff_view_alvo)
        if img_a is None or img_b is None:
            self._flash("Diff: não foi possível carregar as imagens",cor=(255,0,0),dur=3.0); return
        try:
            self.diff_result=diff_lib.calcular_diff(img_a, img_b, threshold=self.diff_threshold,
                                                    escala_mm_por_px=self.mm_por_px)
            self.diff_precisa_recalcular=False
            r=self.diff_result
            self._flash(f"Diff calculado: {r.pct_diff:.1f}% diferente | inliers: {r.score} | espelhado: {'sim' if r.espelhado else 'não'}",cor=(0,220,120),dur=4.0)
        except Exception as e:
            self._flash(f"Diff: falha ao calcular ({e})",cor=(255,0,0),dur=3.5)

    def _render_diff(self, canvas):
        """Desenha o diff viewer no canvas (substitui a imagem simples)."""
        if self.diff_precisa_recalcular or self.diff_result is None:
            self._recalcular_diff()
        res=self.diff_result
        if res is None:
            return
        pads_a=self._obter_pads_view(self.diff_view_ref)
        pads_b=self._obter_pads_view(self.diff_view_alvo)
        w_max=self._canvas_w()-40
        if self.diff_side_by_side:
            img_diff=diff_lib.desenhar_diff_lado_a_lado(res, pads_a, pads_b, w_max=w_max)
        else:
            img_diff=diff_lib.desenhar_diff_sobreposto(res, pads_a, pads_b, alpha=self.diff_alpha, w_max=w_max)
        # Centraliza o diff no canvas (área de desenho, abaixo da toolbar)
        canvas_w=self._canvas_w()
        canvas_h=self.view_h-40
        dh, dw = img_diff.shape[:2]
        escala=min(canvas_w/dw, canvas_h/dh, 1.0)
        nw, nh=max(1,int(dw*escala)), max(1,int(dh*escala))
        pequena=cv2.resize(img_diff,(nw,nh),interpolation=cv2.INTER_AREA)
        x0=(canvas_w-nw)//2+self._cx0()
        y0=(canvas_h-nh)//2+40
        if 0<=y0 and y0+nh<=self.view_h and 0<=x0 and x0+nw<=self.view_w:
            canvas[y0:y0+nh, x0:x0+nw]=pequena
            # barra de status do diff
            txt=f"DIFF {self.diff_view_ref.upper()} vs {self.diff_view_alvo.upper()} | {res.pct_diff:.1f}% diferente | inliers {res.score} | limiar {self.diff_threshold}"
            cv2.putText(canvas,_ascii(txt),(self._cx0()+8, y0+nh+20),cv2.FONT_HERSHEY_SIMPLEX,0.4,(0,255,255),1,cv2.LINE_AA)
        else:
            self._flash("Diff: canvas muito pequeno para exibir",cor=(255,180,0),dur=2.5)

    def _atualizar_estado_botoes_diff(self):
        """Marca os botões DIFF ativos de acordo com o estado atual."""
        for b in self.botoes_toolbar:
            if b.key=='modo_diff':
                b.ativo=self.modo_diff
            elif b.key=='diff_lado_a_lado':
                b.ativo=self.diff_side_by_side
            elif b.key=='diff_sobreposto':
                b.ativo=not self.diff_side_by_side
        # Botoes de plugin: marca ativo conforme estado do plugin (se houver chave correspondente)
        for b in self.botoes_toolbar:
            if b.key and b.key.startswith('plugin_'):
                # Plugins nao tem estado de toggle persistente por padrao; mantem inativo (acao direta)
                b.ativo=False

    def _executar_botao_plugin(self, key: str) -> None:
        """Executa a acao de um botao de plugin (chave no formato plugin_<nome>_<acao>)."""
        partes=key.split('_',2)
        if len(partes)<3:
            self._flash("Plugin: chave de botao invalida",cor=(255,180,0),dur=2.5); return
        nome_plugin=partes[1]
        chave_acao=partes[2]
        plugin=self.plugin_mgr.obter(nome_plugin)
        if plugin is None:
            self._flash(f"Plugin '{nome_plugin}' nao encontrado",cor=(255,0,0),dur=3.0); return
        # Procura por um metodo no plugin que corresponda à chave da acao
        metodos_possiveis=[f"btn_{chave_acao}", f"acao_{chave_acao}", chave_acao]
        metodo=None
        for m in metodos_possiveis:
            if hasattr(plugin,m) and callable(getattr(plugin,m)):
                metodo=getattr(plugin,m)
                break
        if metodo is None:
            self._flash(f"Plugin '{nome_plugin}' nao tem acao '{chave_acao}'",cor=(255,180,0),dur=3.0); return
        try:
            metodo(self)
            self._flash(f"Plugin '{nome_plugin}': {chave_acao} executado",cor=(0,220,120),dur=3.0)
        except Exception as e:
            self._flash(f"Plugin '{nome_plugin}' falhou: {e}",cor=(255,0,0),dur=3.5)


    def _detectar_tiles(self):
        p=self._params_from_sliders()
        t0=time.perf_counter()
        params=dict(brilho_min=p['brilho_min'],brilho_max=p['brilho_max'],sat_max=p['sat_max'],area_min=p['area_min'],area_max=p['area_max'],nms_dist=p['nms_dist'],reject_vias=p.get('reject_vias',True))
        pads=detectar_pads_tiles(self.img,tile=1800,overlap=220,usar_gpu=self.gpu_ativo,**params)
        dt=(time.perf_counter()-t0)*1000.0
        self._push_undo(); self.pads=[]
        for pp in pads:
            self.pads.append({'id':self.next_id,'cx':pp['cx'],'cy':pp['cy'],'x':pp['cx'],'y':pp['cy'],'w':pp['w'],'h':pp['h'],'area':pp['area'],'manual':False}); self.next_id+=1
        self._recalc_next_id(); self.pads.sort(key=lambda pp:(pp['cy']//80,pp['cx']))
        self.nets=[]; self.next_net_id=1; self.filter_familia_id=None
        self.selected=None; self._invalidar_cache_visiveis(); self._marcar_dirty()
        via="GPU" if self.gpu_ativo else "CPU"
        self._flash(f"Tiles: {len(self.pads)} pads · {via} {dt:.0f} ms",cor=(0,220,100),dur=3.0)

    def _iniciar_regua(self):
        self.regua_modo=not self.regua_modo; self.regua_pts=[]
        if self.regua_modo:
            self._flash("Régua: clique 2 pontos da placa; informe a medida real (mm)",cor=(0,200,255),dur=3.0)
        else:
            self._flash("Régua desligada",cor=(160,160,170),dur=1.5)

    def _comparar_ouro(self):
        vd=self.views_store.get(self.view_atual) or {}
        inicial=vd.get('ouro_path') or (os.path.dirname(self.img_path_original) if self.img_path_original else os.getcwd())
        ouro = dialogs_lib.escolher_arquivo(
            "Placa de referência (ouro)",
            initialdir=inicial if os.path.isdir(str(inicial)) else os.getcwd(),
            filetypes=[("Imagens","*.jpg *.jpeg *.png *.bmp *.tiff")],
        )
        if not ouro or not os.path.exists(ouro): return
        vd['ouro_path']=ouro; self.views_store[self.view_atual]=vd
        try:
            res=executar_comparacao(ouro,self.img_path_original,os.path.join(os.path.abspath(self.out_dir),'anomalias'))
        except Exception as e:
            self._flash(f"Comparação falhou: {e}",cor=(255,0,0),dur=3.0); return
        qtd=0
        if isinstance(res,dict):
            for k in ('anomalias','anomalies','diferencas','pontos'):
                v=res.get(k)
                if isinstance(v,list): qtd=len(v); break
        self._flash(f"Comparação com ouro: {qtd} anomalia(s) - veja saida/anomalias",cor=(0,220,120),dur=3.5)

    def _pads_do_componente(self,comp):
        ids=set(comp.get('pads') or []); idd={p.get('id'):p for p in self.pads}
        return [idd[i] for i in ids if i in idd]

    def _pinagem_conector(self,comp):
        pads=self._pads_do_componente(comp)
        p1=comp.get('pino1')
        if pads and p1 is not None and any(p.get('id')==p1 for p in pads):
            import math
            start=next(p for p in pads if p.get('id')==p1)
            cx=(comp.get('x1',0)+comp.get('x2',0))/2.0; cy=(comp.get('y1',0)+comp.get('y2',0))/2.0
            a0=math.atan2(start.get('cy',0)-cy,start.get('cx',0)-cx)
            def ang(p):
                return (math.atan2(p.get('cy',0)-cy,p.get('cx',0)-cx)-a0)%(2*math.pi)
            pads=[start]+sorted([p for p in pads if p is not start],key=ang)
        else:
            pads.sort(key=lambda p:(p['cy']//25,p['cx']))
        linhas=[]
        for i,p in enumerate(pads,1):
            pid=p.get('id'); m=self.measurements.get(pid) or {}
            fam=self._get_familia_do_pad(pid)
            linhas.append({'pino':i,'pad':pid,'x':p['cx'],'y':p['cy'],
                           'familia':(fam.get('nome','') if fam else ''),
                           'nome_pino':str(p.get('pino') or ''),
                           'gnd':bool(p.get('gnd')),
                           'status':(m.get('status') if isinstance(m,dict) else '') or ''})
        return linhas

    def _exportar_pinagem(self,comp):
        linhas=self._pinagem_conector(comp)
        if not linhas:
            self._flash("Conector sem pads vinculados",cor=(255,100,0),dur=2.0); return
        nome=f"pinagem_{comp.get('nome','conector')}.csv"
        destino = dialogs_lib.salvar_arquivo(
            "Salvar pinagem CSV",
            initialdir=os.path.abspath(self.out_dir),
            initialfile=nome,
            defaultextension='.csv',
            filetypes=[("CSV","*.csv")],
        )
        if not destino: return
        try:
            import csv as _csv
            with open(destino,'w',newline='',encoding='utf-8') as f:
                w=_csv.writer(f); w.writerow(['pino','nome_pino','gnd','pad','familia','status','x','y'])
                for l in linhas: w.writerow([l['pino'],l.get('nome_pino',''),'SIM' if l.get('gnd') else '',l['pad'],l['familia'],l['status'],l['x'],l['y']])
            self._flash(f"Pinagem exportada: {os.path.basename(destino)}",cor=(0,220,120),dur=3.0)
        except Exception as e:
            self._flash(f"Erro ao salvar: {e}",cor=(255,0,0),dur=2.5)

    # ==================== ACTIVE LEARNING METHODS ====================

    def _gerar_pseudo_labels(self):
        """Gera pseudo-labels para detecções de alta confiança."""
        from core.active_learning import PseudoLabeler, ActiveLearningConfig, DetectionResult
        
        # Filtrar pads automáticos com alta confiança
        pads_auto = [p for p in self.pads if not p.get('manual', False) and p.get('score', 0) >= 0.8]
        
        if not pads_auto:
            self._flash("Nenhum pad automático com confiança >= 0.8",cor=(255,180,0),dur=3.0)
            return
        
        config = ActiveLearningConfig(pseudo_label_confidence=0.8)
        labeler = PseudoLabeler(config)
        
        # Converter pads para DetectionResult
        preds = []
        for p in pads_auto:
            pred = type('obj', (object,), {
                'bbox': (p['cx'], p['cy'], p['w'], p['h']),
                'confidence': p.get('score', 0.5),
                'class_id': p.get('class_id', 0),
                'uncertainty': 1.0 - p.get('score', 0.5),
                'uncertainties_per_class': np.array([]),
                'entropy': 1.0 - p.get('score', 0.5),
                'margin': p.get('score', 0.5),
                'image_path': self.img_path_original,
                'image_shape': (self.h0, self.w0)
            })()
            preds.append(pred)
        
        pseudo_labels = labeler.generate(preds, [])
        
        if not pseudo_labels:
            self._flash("Nenhum pseudo-label gerado (confiança < 0.8)",cor=(255,180,0),dur=3.0)
            return
        
        # Converter pseudo-labels para anotações
        from core.active_learning import LabeledSample
        count = 0
        for pl in pseudo_labels:
            # Verificar se já existe anotação próxima
            existe = False
            for a in self.anotacoes:
                if abs(a['x'] - pl.bbox[0]*self.w0) < 20 and abs(a['y'] - pl.bbox[1]*self.h0) < 20:
                    existe = True
                    break
            if not existe:
                self.anotacoes.append({
                    'id': self.next_anot_id,
                    'x': int(pl.bbox[0] * self.w0),
                    'y': int(pl.bbox[1] * self.h0),
                    'text': "AL:%d:%.2f" % (pl.class_id, pl.confidence),
                    'cor': (255, 200, 0)
                })
                self.next_anot_id += 1
                count += 1
        
        self._marcar_dirty()
        self._flash("Pseudo-labels gerados: %d" % count,cor=(0,220,120),dur=3.0)

    def _treinar_modelo_al(self):
        """Inicia fine-tuning LoRA com dados rotulados (humanos + pseudo)."""
        if not hasattr(self, 'labeled_samples') or not self.labeled_samples:
            # Coletar labels das anotações existentes
            self._coletar_labels_anotacoes()
        
        if not hasattr(self, 'labeled_samples') or len(self.labeled_samples) < 5:
            self._flash("Poucos dados rotulados (min 5). Gere pseudo-labels ou anote manualmente.",cor=(255,180,0),dur=4.0)
            return
        
        try:
            import random
            from core.active_learning import TORCH_AVAILABLE, LoRAFineTuner, ActiveLearningConfig
            if not TORCH_AVAILABLE:
                self._flash("Fine-tuning precisa de PyTorch (pip install torch). No EXE use os pseudo-labels.",cor=(255,180,0),dur=4.5)
                return
            config = ActiveLearningConfig(finetune_epochs=5)
            tuner = LoRAFineTuner(config)
            
            # Preparar dados
            train_samples = self.labeled_samples
            random.shuffle(train_samples)
            split = int(0.9 * len(train_samples))
            train_data = train_samples[:split]
            val_data = train_samples[split:]
            
            self._flash("Iniciando fine-tuning LoRA...",cor=(0,200,255),dur=3.0)
            
            def progress_cb(epoch, loss, metrics):
                self._flash(f"Epoch {epoch+1}: loss={loss:.4f}, val_loss={metrics.get('val_loss', 0):.4f}",cor=(0,200,255),dur=2.0)
            
            new_model = tuner.train(
                self.modelo_ia or 'models/pads.onnx',
                train_data, val_data,
                progress_callback=progress_cb
            )
            
            if new_model:
                self.modelo_ia = new_model
                self.detector_modo = 'ia'
                self._flash(f"Modelo atualizado: {os.path.basename(new_model)}",cor=(0,220,120),dur=3.0)
            else:
                self._flash("Fine-tuning falhou",cor=(255,0,0),dur=3.0)
                
        except Exception as e:
            self._flash(f"Erro no fine-tuning: {e}",cor=(255,0,0),dur=4.0)

    def _coletar_labels_anotacoes(self):
        """Converte anotações em LabeledSample para treino."""
        from core.active_learning import LabeledSample
        self.labeled_samples = []
        for a in self.anotacoes:
            if a.get('text', '').startswith('AL:'):
                # Pseudo-label
                parts = a['text'][3:].split(':')
                if len(parts) >= 2:
                    try:
                        class_id = int(parts[0])
                        conf = float(parts[1])
                        self.labeled_samples.append(LabeledSample(
                            image_path=self.img_path_original,
                            bbox=(a['x']/self.w0, a['y']/self.h0, 0.1, 0.1),
                            class_id=class_id,
                            is_pseudo=True,
                            confidence=conf,
                            annotator="pseudo"
                        ))
                    except:
                        pass
            else:
                # Anotação manual
                self.labeled_samples.append(LabeledSample(
                    image_path=self.img_path_original,
                    bbox=(a['x']/self.w0, a['y']/self.h0, 0.1, 0.1),
                    class_id=0,
                    is_pseudo=False,
                    confidence=1.0,
                    annotator="human"
                ))

    def _girar_componente(self,comp):
        x1,y1,x2,y2=comp['x1'],comp['y1'],comp['x2'],comp['y2']
        cx=(x1+x2)/2.0; cy=(y1+y2)/2.0; w=abs(x2-x1); h=abs(y2-y1)
        comp['x1']=int(cx-h/2); comp['x2']=int(cx+h/2); comp['y1']=int(cy-w/2); comp['y2']=int(cy+w/2)
        if comp.get('forma')=='retangulo_h': comp['forma']='retangulo_v'
        elif comp.get('forma')=='retangulo_v': comp['forma']='retangulo_h'
        self._marcar_dirty()

    def _draw_paleta_cmd(self,canvas,oy_off):
        st=self.paleta_cmd
        if not st.get('active'): return
        itens=st.get('itens') or []
        W=470; X=max(self._cx0()+10,(self._cx0()+self._canvas_w()-W)//2); Y=oy_off+30
        linhas=min(10,max(1,len(itens)))
        H=70+linhas*22
        cv2.rectangle(canvas,(X+3,Y+4),(X+W+3,Y+H+4),THEME['shadow'],-1)
        draw_rounded_rect(canvas,X,Y,W,H,10,THEME['card'],-1)
        draw_rounded_rect(canvas,X,Y,W,H,10,(0,0,0),1,THEME['accent'])
        cv2.putText(canvas,"COMANDOS  (digite para filtrar | Enter executa | Esc fecha)",(X+12,Y+20),cv2.FONT_HERSHEY_SIMPLEX,0.30,THEME['accent'],1)
        draw_rounded_rect(canvas,X+10,Y+28,W-20,24,6,THEME['field'],-1)
        q=st.get('query','')+("|" if (self.cursor_blink//15)%2==0 else " ")
        cv2.putText(canvas,_ascii(q)[:60],(X+18,Y+45),cv2.FONT_HERSHEY_SIMPLEX,0.34,THEME['text_main'],1)
        y=Y+64
        for i,(lab,key) in enumerate(itens[:10]):
            sel=(i==st.get('sel',0))
            if sel: draw_rounded_rect(canvas,X+8,y-13,W-16,20,5,THEME['accent_soft'],-1)
            cv2.putText(canvas,_ascii(lab)[:64],(X+16,y),cv2.FONT_HERSHEY_SIMPLEX,0.30,THEME['accent'] if sel else THEME['text_main'],1)
            y+=22

    def _carregar_pads_alternativo(self,pasta):
        """Fallback para projetos antigos: pads.json, pads_v2.json, pads_final.csv, pads.csv, pads_v2.csv."""
        def _norm(pid,x,y,w,h):
            w=int(w or 12); h=int(h or 12)
            return {'id':int(pid),'cx':int(x),'cy':int(y),'x':int(x),'y':int(y),'w':w,'h':h,'area':w*h,'manual':False}
        for nome in ('pads.json','pads_v2.json'):
            p=os.path.join(pasta,nome)
            if os.path.exists(p):
                try:
                    with open(p,'r',encoding='utf-8') as f: arr=json.load(f)
                    out=[]
                    for e in (arr if isinstance(arr,list) else []):
                        try: out.append(_norm(e.get('id',len(out)+1),e.get('x',e.get('cx')),e.get('y',e.get('cy')),e.get('w',e.get('bbox_w',12)),e.get('h',e.get('bbox_h',12))))
                        except Exception: continue
                    if out: return out
                except Exception: pass
        import csv as _csv
        for nome in ('pads_final.csv','pads.csv','pads_v2.csv'):
            p=os.path.join(pasta,nome)
            if not os.path.exists(p): continue
            try:
                out=[]
                with open(p,'r',encoding='utf-8') as f:
                    for row in _csv.DictReader(f):
                        x=row.get('x') or row.get('cx'); y=row.get('y') or row.get('cy')
                        if x is None or y is None: continue
                        try: out.append(_norm(row.get('id',len(out)+1),x,y,row.get('w') or row.get('bbox_w') or 12,row.get('h') or row.get('bbox_h') or 12))
                        except Exception: continue
                if out: return out
            except Exception: continue
        return None

    def _sentinel_projeto(self,pasta):
        try: nomes=os.listdir(pasta)
        except Exception: return None
        js=[os.path.join(pasta,n) for n in nomes if n.lower().startswith('sessao_') and n.lower().endswith('.json')]
        if js:
            js.sort(key=lambda p:os.path.getmtime(p),reverse=True)
            return js[0]
        for csvn in ('pads_final.csv','pads.csv','pads_v2.csv','medicoes_final.csv'):
            p=os.path.join(pasta,csvn)
            if os.path.exists(p): return p
        for jsonn in ('pads.json','pads_v2.json'):
            p=os.path.join(pasta,jsonn)
            if os.path.exists(p): return p
        return None

    def _resumo_projeto(self,pasta,sentinel):
        data=None
        if sentinel.lower().endswith('.json'):
            try:
                with open(sentinel,'r',encoding='utf-8') as f: data=json.load(f)
            except Exception: data=None
        try: dt=time.strftime('%d/%m/%Y %H:%M',time.localtime(os.path.getmtime(sentinel)))
        except Exception: dt='?'
        if isinstance(data,dict):
            pads=len(data.get('pads') or []); nets=len(data.get('nets') or [])
            comps=len(data.get('componentes') or data.get('componentes_v8') or [])
            return f"{pads} pads · {nets} famílias · {comps} comp · {dt}"
        if isinstance(data,list):
            return f"{len(data)} pads · {dt}"
        if sentinel.lower().endswith('.csv'):
            try:
                with open(sentinel,'r',encoding='utf-8') as f: n=max(0,sum(1 for _ in f)-1)
                return f"{n} pads · {dt}"
            except Exception: pass
        return f"CSV · {dt}"

    def _listar_projetos(self):
        """Varre cwd, raiz do app, pasta de projetos e pasta atual atrás de projetos."""
        bases=[]
        for b in (self.pasta_projetos,os.getcwd(),ROOT,os.path.dirname(os.path.abspath(self.out_dir))):
            if b and os.path.isdir(b):
                rb=os.path.realpath(b)
                if all(os.path.normcase(rb)!=os.path.normcase(x) for x in bases): bases.append(rb)
        exts_img=('.jpg','.jpeg','.png','.bmp','.tif','.tiff','.heic','.heif')
        vistos=set(); projetos=[]; visitados=0
        for base in bases:
            for root,dirs,files in os.walk(base):
                visitados+=1
                if visitados>4000: break
                rel=os.path.relpath(root,base)
                prof=0 if rel=='.' else rel.count(os.sep)+1
                dirs[:]=[d for d in dirs if not d.startswith('.') and d!='__pycache__' and d.lower()!='node_modules']
                sent=self._sentinel_projeto(root)
                if sent:
                    dirs[:]=[]
                    key=os.path.normcase(os.path.realpath(root))
                    if key in vistos: continue
                    vistos.add(key)
                    try: rot=os.path.relpath(root,base)
                    except Exception: rot=root
                    if rot=='.': rot=os.path.basename(root) or root
                    projetos.append({'pasta':root,'base':base,'rotulo':rot,'info':self._resumo_projeto(root,sent),'mtime':os.path.getmtime(sent)})
                elif prof>=1 and self.pasta_projetos and os.path.normcase(os.path.realpath(base))==os.path.normcase(os.path.realpath(self.pasta_projetos)):
                    imgs=[f for f in files if f.lower().endswith(exts_img)]
                    if imgs:
                        dirs[:]=[]
                        key=os.path.normcase(os.path.realpath(root))
                        if key in vistos: continue
                        vistos.add(key)
                        try: rot=os.path.relpath(root,base)
                        except Exception: rot=root
                        try: mt=max(os.path.getmtime(os.path.join(root,f)) for f in imgs)
                        except Exception: mt=0
                        projetos.append({'pasta':root,'base':base,'rotulo':rot,'info':f"{len(imgs)} fotos · novo projeto",'mtime':mt,'novo':True})
                elif prof>=2:
                    dirs[:]=[]
        projetos.sort(key=lambda p:p['mtime'],reverse=True)
        return projetos

    def _abrir_projeto_dialog(self):
        """Janela com a lista de projetos de placa encontrados + escolha de pasta manual."""
        projetos = self._listar_projetos()
        recentes = [os.path.abspath(p) for p in (self.prefs.get('recentes') or []) if os.path.isdir(str(p))]

        def _ordem_recente(p):
            rp = os.path.normcase(os.path.abspath(p['pasta']))
            for i, r in enumerate(recentes):
                if os.path.normcase(r) == rp:
                    return (0, i)
            return (1, 0)
        projetos.sort(key=_ordem_recente)

        if dialogs_lib._disponivel():
            import tkinter as tk
            from tkinter import filedialog
            escolhido = {'pasta': None}
            root = tk.Tk(); root.title("Abrir Projeto de Placa"); root.attributes('-topmost', True); root.resizable(False, False)
            w, h = 780, 440
            try:
                sx, sy = root.winfo_screenwidth(), root.winfo_screenheight()
                root.geometry(f"{w}x{h}+{max(0, (sx - w) // 2)}+{max(0, (sy - h) // 3)}")
            except Exception:
                root.geometry(f"{w}x{h}")
            tk.Label(root, text=f"Projetos em: {self.pasta_projetos or os.getcwd()}   (★ recente · [NOVO] = pasta com fotos)", anchor='w').pack(fill='x', padx=10, pady=(10, 2))
            frame = tk.Frame(root); frame.pack(fill='both', expand=True, padx=10)
            sb = tk.Scrollbar(frame, orient='vertical')
            lb = tk.Listbox(frame, yscrollcommand=sb.set, activestyle='dotbox', font=('Consolas', 10)); sb.config(command=lb.yview)
            lb.pack(side='left', fill='both', expand=True); sb.pack(side='right', fill='y')
            if projetos:
                for p in projetos:
                    rp = os.path.normcase(os.path.abspath(p['pasta']))
                    estrela = '★ ' if any(os.path.normcase(r) == rp for r in recentes) else '  '
                    novo = '[NOVO] ' if p.get('novo') else ''
                    lb.insert('end', f"{estrela}{novo}{p['rotulo']}   |   {p['info']}")
                lb.selection_set(0)
            else:
                lb.insert('end', '(nenhum projeto encontrado - use "Escolher pasta...")')
            def abrir():
                sel = lb.curselection()
                if not sel or not projetos:
                    return
                escolhido['pasta'] = projetos[sel[0]]['pasta']; root.destroy()
            def escolher_pasta():
                d = filedialog.askdirectory(parent=root, title="Escolher pasta do projeto (sessão JSON, CSVs ou fotos)", initialdir=self.pasta_projetos or os.path.abspath(self.out_dir))
                if d:
                    escolhido['pasta'] = d; root.destroy()
            def definir_pasta():
                d = filedialog.askdirectory(parent=root, title="Pasta de projetos (workspace)", initialdir=self.pasta_projetos or os.getcwd())
                if d:
                    self.pasta_projetos = os.path.abspath(d)
                    self.prefs['pasta_projetos'] = self.pasta_projetos; self._salvar_prefs()
                    root.destroy()
                    self._flash(f"Pasta de projetos: {self.pasta_projetos}", cor=(0, 220, 120), dur=2.5)
                    self._abrir_projeto_dialog()
            bar = tk.Frame(root); bar.pack(fill='x', padx=10, pady=10)
            tk.Button(bar, text="Abrir", width=12, default='active', command=abrir).pack(side='left')
            tk.Button(bar, text="Escolher pasta...", width=16, command=escolher_pasta).pack(side='left', padx=8)
            tk.Button(bar, text="Pasta de projetos...", width=18, command=definir_pasta).pack(side='left')
            tk.Button(bar, text="Cancelar", width=10, command=root.destroy).pack(side='right')
            lb.bind('<Double-Button-1>', lambda e: abrir())
            root.bind('<Return>', lambda e: abrir())
            root.bind('<Escape>', lambda e: root.destroy())
            root.mainloop()
            if escolhido['pasta']:
                self._abrir_projeto(escolhido['pasta'])
            return

        # --- Fallback sem tkinter (console) ---
        print(f"\n=== ABRIR PROJETO (tkinter indisponível) ===")
        print(f"Projetos em: {self.pasta_projetos or os.getcwd()}")
        if projetos:
            for i, p in enumerate(projetos, 1):
                estrela = '★ ' if any(os.path.normcase(r) == os.path.normcase(os.path.abspath(p['pasta'])) for r in recentes) else '  '
                novo = '[NOVO] ' if p.get('novo') else ''
                print(f"  {i}. {estrela}{novo}{p['rotulo']}  |  {p['info']}  |  {p['pasta']}")
        else:
            print("  (nenhum projeto encontrado)")
        print("  0. Escolher pasta manualmente")
        print("  q. Cancelar")
        try:
            escolha = input("Escolha um número: ").strip()
        except EOFError:
            return
        if escolha.lower() in ('q', ''):
            return
        if escolha == '0':
            d = dialogs_lib.escolher_pasta("Escolher pasta do projeto", initialdir=self.pasta_projetos or os.path.abspath(self.out_dir))
            if d:
                self._abrir_projeto(d)
            return
        try:
            idx = int(escolha) - 1
            if 0 <= idx < len(projetos):
                self._abrir_projeto(projetos[idx]['pasta'])
        except ValueError:
            self._flash("Escolha invalida", cor=(255, 180, 0), dur=2.0)

    def _abrir_pasta_saida(self):
        try:
            import subprocess, platform
            path=os.path.abspath(self.out_dir)
            if platform.system()=="Windows": os.startfile(path)
            elif platform.system()=="Darwin": subprocess.Popen(["open",path])
            else: subprocess.Popen(["xdg-open",path])
        except Exception as e: self._flash(f"Erro abrir pasta: {e}",cor=(255,0,0))

    def _orig_to_disp(self,ox,oy): return (int(ox*self.base_scale*self.zoom+self.pan_x+self._cx0()),int(oy*self.base_scale*self.zoom+self.pan_y))
    def _disp_to_orig(self,dx,dy): bs=self.base_scale if self.base_scale>0.01 else 0.15; return (int((dx-self.pan_x-self._cx0())/(bs*self.zoom)),int((dy-self.pan_y)/(bs*self.zoom)))
    def _pads_visiveis_idx(self):
        if not self._cache_visiveis_dirty:
            return self._visiveis
        vis=set(); familia_pads=set()
        if self.filter_familia_id is not None:
            net=next((n for n in self.nets if n['id']==self.filter_familia_id),None)
            if net: familia_pads=set(net['pads'])
        for i,p in enumerate(self.pads):
            pid=p.get('id',0)
            if self.search_id is not None and pid!=self.search_id: continue
            if self.filter_familia_id is not None and pid not in familia_pads: continue
            if self.tab=='calibrar':
                if self.filter_tipo=='auto' and p.get("manual"): continue
                if self.filter_tipo=='manual' and not p.get("manual"): continue
            else:
                if self.filter_status:
                    m=self.measurements.get(pid,{}) if isinstance(self.measurements,dict) else {}; st=m.get('status') if isinstance(m,dict) else None
                    if self.filter_status=='VAZIO' and st is not None: continue
                    if self.filter_status in ('OK','SUSP','FALHA') and st!=self.filter_status: continue
            vis.add(i)
        self._visiveis=vis; self._cache_visiveis_dirty=False; return vis
    def _pad_no_ponto(self,ox,oy,raio=None):
        if raio is None: raio=int(40/max(0.3,self.zoom))+20; raio=max(25,min(60,raio))
        vis=self._pads_visiveis_idx(); best,best_d=None,raio
        for i in vis:
            if i>=len(self.pads): continue
            p=self.pads[i]; d=np.hypot(p["cx"]-ox,p["cy"]-oy)
            if d<best_d: best_d=d; best=i
        return best
    def _cor_familia(self,net):
        if 'cor' in net and net['cor']:
            return tuple(net['cor'])
        # FIX v11: 32 cores + geração infinita HSV
        if len(PALETA_32) > 0:
            idx = (net['id']-1) % len(PALETA_32)
            if idx < len(PALETA_32):
                return tuple(PALETA_32[idx][1])
        # fallback golden ratio
        import colorsys
        h = (net['id'] * 0.618033988749895) % 1.0
        r,g,b = colorsys.hsv_to_rgb(h, 0.75, 0.9)
        return (int(b*255), int(g*255), int(r*255))
    def _proxima_cor_familia(self):
        """Cor nova para família: primeira cor não usada (Okabe-Ito primeiro)."""
        usadas={}
        for n in self.nets:
            c=tuple(n.get('cor') or ())
            usadas[c]=usadas.get(c,0)+1
        for _,cor in PALETA_32:
            c=tuple(cor)
            if usadas.get(c,0)==0: return [int(x) for x in c]
        return [int(x) for x in PALETA_32[0][1]]
    def _rebuild_pad_to_net(self):
        self._pad_to_net={}
        for net in self.nets:
            for pid in net.get('pads',[]):
                self._pad_to_net[pid]=net
    def _carregar_sessao(self):
        if not os.path.exists(self.session_path): return
        try:
            with open(self.session_path,'r',encoding='utf-8') as f: data=json.load(f)
            self._aplicar_payload(data)
        except Exception as e:
            # FIX v11.4: sessao corrompida nao pode ser engolida e sobrescrita ao fechar.
            # Preserva o arquivo original e bloqueia o save no final da execucao.
            try:
                bak=f"{self.session_path}.corrompida_bak"
                if not os.path.exists(bak):
                    os.rename(self.session_path,bak)
                else:
                    bak=f"{self.session_path}.{time.strftime('%Y%m%d_%H%M%S')}.corrompida_bak"
                    os.rename(self.session_path,bak)
                print(f"AVISO: sessao corrompida preservada em: {bak} ({e})")
                self._sessao_ruim=True
            except Exception as e2:
                print(f"Erro preservando sessao corrompida: {e2}")
                self._sessao_ruim=True
    def _aplicar_payload(self,data):
        if not isinstance(data,dict): return
        self._aplicar_gpu_sessao(data)
        views=data.get('views') if isinstance(data.get('views'),dict) else None
        if views:
            self.views_store={k:copy.deepcopy(v) for k,v in views.items() if isinstance(v,dict)}
            va=data.get('view_atual')
            self.view_atual=va if va in self.views_store else next(iter(self.views_store))
            self._aplicar_view_runtime(self.views_store[self.view_atual])
        else:
            vd={"img_path":data.get('img_path'),"pads":data.get('pads',[]),
                "measurements":data.get('measurements',{}),"nets":data.get('nets',[]),
                "componentes":data.get('componentes',data.get('componentes_v8',[])),
                "next_id":data.get('next_id'),"next_net_id":data.get('next_net_id'),
                "next_comp_id":data.get('next_comp_id'),"sliders":data.get('sliders'),
                "anotacoes":data.get('anotacoes',[]),"next_anot_id":data.get('next_anot_id'),
                "preset_key":data.get('preset_key','preset_smd'),"estado_placa":data.get('estado_placa','desligada'),
                "filter_familia_id":data.get('filter_familia_id'),"zoom":1.0}
            self.view_atual='frente'; self.views_store={'frente':vd}
            self._aplicar_view_runtime(vd)
            self.comp_scroll=data.get('comp_scroll',0)
    def _payload_sessao(self):
        self._salvar_view_atual()
        return {
            "pads":self.pads,"measurements":self.measurements,"nets":self.nets,
            "next_id":self.next_id,"next_net_id":self.next_net_id,
            "sliders":[s.val for s in self.sliders],
            "filter_familia_id":self.filter_familia_id,
            "preset_key":self.preset_selected_key,"estado_placa":self.estado_placa,
            "img_path":self.img_path_original,
            "componentes":self.componentes,"next_comp_id":self.next_comp_id,"comp_scroll":self.comp_scroll,
            "anotacoes":self.anotacoes,"next_anot_id":self.next_anot_id,
            "usar_gpu":bool(self.gpu_ativo),
            "views":self.views_store,"view_atual":self.view_atual,
            "versao":"v11.2-views"
        }
    def _salvar_sessao(self):
        try:
            payload=self._payload_sessao()
            # Hook M1: plugins podem modificar o payload antes de salvar
            self.plugin_mgr.on_salvar_sessao(self, payload)
            tmp=self.session_path+'.tmp'
            with open(tmp,'w',encoding='utf-8') as f: json.dump(payload,f,indent=2,ensure_ascii=False)
            os.replace(tmp,self.session_path)
            # C1: backup rotativo da sessão
            try:
                from storage.session import _backup_sessao
                _backup_sessao(self.session_path)
            except Exception: pass
        except Exception as e: print(f"AVISO: {e}")
    def _autosave(self):
        try:
            prefs_lib.salvar_autosave(self.out_dir,self._payload_sessao())
        except Exception:
            pass
    def _detectar_pasta_projetos(self):
        pref=str(self.prefs.get('pasta_projetos') or '')
        if pref and os.path.isdir(pref):
            return os.path.abspath(pref)
        base=os.path.dirname(ROOT)
        for raiz in (base,os.getcwd()):
            try: nomes=os.listdir(raiz)
            except Exception: continue
            for nome in nomes:
                if nome.lower() in ('projetos','projects') and os.path.isdir(os.path.join(raiz,nome)):
                    p=os.path.abspath(os.path.join(raiz,nome))
                    self.prefs['pasta_projetos']=p
                    return p
        return ''

    def _salvar_prefs(self):
        try:
            if self.prefs.get('gpu_manual'):
                self.prefs['gpu_ativo']=bool(self.gpu_ativo)
            self.prefs['show_ids']=bool(self.show_ids)
            self.prefs['layers']=dict(self.layers)
            self.prefs['mm_por_px']=float(self.mm_por_px or 0.0)
            self.prefs['preset']=self.preset_selected_key
            self.prefs['detector_modo']=self.detector_modo
            self.prefs['smart_sens']=float(self.smart_sens)
            self.prefs['pasta_projetos']=self.pasta_projetos
            self.prefs['auto_vincular']=bool(self.auto_vincular)
            self.prefs['mostrar_mira']=bool(self.mostrar_mira)
            if self.modelo_ia: self.prefs['modelo_ia']=self.modelo_ia
            prefs_lib.salvar(self.prefs)
        except Exception:
            pass
    def _oferecer_recuperacao(self):
        dados=prefs_lib.carregar_autosave()
        if not dados: return
        projeto=str(dados.get('projeto') or '')
        payload=dados.get('payload') or {}
        try:
            if os.path.normcase(os.path.abspath(projeto))==os.path.normcase(os.path.abspath(self.out_dir)):
                prefs_lib.limpar_autosave(); return
        except Exception:
            pass
        resp=False
        try:
            import tkinter as tk
            from tkinter import messagebox
            root=tk.Tk(); root.withdraw(); root.attributes('-topmost',True)
            resp=messagebox.askyesno("Recuperar sessão","Sessão não salva encontrada:\n\n"+os.path.basename(projeto)+"\n\nDeseja recuperar?")
            root.destroy()
        except Exception:
            resp=False
        if not resp:
            prefs_lib.limpar_autosave(); return
        try:
            self.out_dir=projeto
            self.session_path=os.path.join(projeto,'sessao_v87.json')
            self._aplicar_payload(payload)
            prefs_lib.limpar_autosave()
            self._flash("Sessão recuperada",cor=(0,220,120),dur=3.0)
        except Exception as e:
            self._flash(f"Falha ao recuperar: {e}",cor=(255,0,0),dur=3.0)
    def _salvar_csvs(self): salvar_csvs(self.pads,self.measurements,self.nets,self.out_dir); self._salvar_sessao()
    def _salvar_tudo(self): self._salvar_csvs(); salvar_png(self.pads,self.out_dir,self.img); self.dirty=False
    def _idx_from_id(self,pid):
        if pid is None: return None
        for i,p in enumerate(self.pads):
            if p.get('id')==pid: return i
        return None
    def _selected_id(self):
        if self.selected is None or self.selected>=len(self.pads): return None
        return self.pads[self.selected].get('id')
    def _adicionar_pad(self,ox,oy):
        ox=max(0,min(self.w0-1,ox)); oy=max(0,min(self.h0-1,oy)); sel_id=self._selected_id(); pend_id=None
        if self.pending_connection is not None and self.pending_connection<len(self.pads): pend_id=self.pads[self.pending_connection].get('id')
        self._push_undo(); self.pads.append({"id":self.next_id,"cx":ox,"cy":oy,"x":ox,"y":oy,"w":12,"h":12,"area":100,"manual":True}); self.next_id+=1; self.pads.sort(key=lambda p:(p["cy"]//80,p["cx"])); self.selected=self._idx_from_id(sel_id); self.pending_connection=self._idx_from_id(pend_id); self._invalidar_cache_visiveis(); self._marcar_dirty()
    def _remover_pad(self,idx):
        if idx is None or idx>=len(self.pads): return
        pid=self.pads[idx].get('id',None); sel_id=self._selected_id(); pend_id=None
        if self.pending_connection is not None and self.pending_connection<len(self.pads): pend_id=self.pads[self.pending_connection].get('id')
        self._push_undo()
        if pid is not None:
            novas=[]
            for net in self.nets:
                if pid in net['pads']:
                    net['pads']=[x for x in net['pads'] if x!=pid]
                    if len(net['pads'])>=2: novas.append(net)
                else: novas.append(net)
            self.nets=novas
            # FIX v11.4: remover vestigios (medicao orfa era contada em filtros e
            # componentes mantinham o id; em re-deteccao o id reencarna em outro pad)
            self.measurements.pop(pid,None)
            for c in self.componentes:
                lst=c.get('pads')
                if isinstance(lst,list) and pid in lst: c['pads']=[x for x in lst if x!=pid]
                if c.get('pino1')==pid: c['pino1']=None
        self.pads.pop(idx)
        if sel_id==pid: self.selected=None
        else: self.selected=self._idx_from_id(sel_id)
        if pend_id==pid: self.pending_connection=None
        else: self.pending_connection=self._idx_from_id(pend_id)
        self.drag_mode=None; self.drag_source=None; self._clamp_familia_scroll(); self._rebuild_pad_to_net(); self._invalidar_cache_visiveis(); self._marcar_dirty()
        if self.right_mode=='edit': self.right_mode='inspetor'
    def _duplicar_pad(self,idx):
        if idx is None or idx>=len(self.pads): return
        orig=self.pads[idx]; found=False
        for radius in [30,50,80,120,160]:
            for ang in range(0,360,45):
                ox=int(orig['cx']+radius*np.cos(np.radians(ang))); oy=int(orig['cy']+radius*np.sin(np.radians(ang)))
                if 0<=ox<self.w0 and 0<=oy<self.h0:
                    if not any(np.hypot(p['cx']-ox,p['cy']-oy)<20 for p in self.pads): found=True; break
            if found: break
        if not found: ox=min(self.w0-1,max(0,orig['cx']+30)); oy=min(self.h0-1,max(0,orig['cy']+30))
        self._push_undo(); self.pads.append({"id":self.next_id,"cx":ox,"cy":oy,"x":ox,"y":oy,"w":orig.get('w',12),"h":orig.get('h',12),"area":orig.get('area',100),"manual":True}); new_id=self.next_id; self.next_id+=1; self.pads.sort(key=lambda p:(p["cy"]//80,p["cx"])); self._invalidar_cache_visiveis(); self._marcar_dirty(); self.selected=self._idx_from_id(new_id)
    def _isolar_pad(self,idx):
        if idx is None or idx>=len(self.pads): return
        pid=self.pads[idx].get('id')
        for net in self.nets:
            if pid in net['pads']:
                self.filter_familia_id=net['id']; self.filter_status=None; self.filter_tipo=None; self.search_id=None; self._invalidar_cache_visiveis(); return

    # ------------------------------------------------------------------
    # MARCACAO ESTILO RASTRECURVE: anotacoes, nome de pino e GND
    # ------------------------------------------------------------------
    def _componente_do_pad(self,pid):
        for c in self.componentes:
            if pid in (c.get('pads') or []):
                return c
        return None

    def _propagar_marcas_pad(self,pad,campos=('pino','gnd')):
        """Leva nome de pino e/ou GND para os pads passantes das outras visoes."""
        link=pad.get('link')
        if not link: return 0
        n=0
        for view,pads,nets,vd in self._iter_views_dados():
            if view==self.view_atual: continue
            for q in pads:
                if q.get('link')!=link: continue
                if 'pino' in campos:
                    if pad.get('pino'):
                        q['pino']=pad['pino']
                    else:
                        q.pop('pino',None)
                if 'gnd' in campos:
                    if pad.get('gnd'):
                        q['gnd']=True
                    else:
                        q.pop('gnd',None)
                n+=1
        return n

    def _nomear_pino_pad(self,idx):
        if idx is None or idx>=len(self.pads):
            self._flash("Clique em um pad para nomear o pino",cor=(255,180,0),dur=2.0); return
        pad=self.pads[idx]
        sx,sy=self._orig_to_disp(pad.get('cx',0),pad.get('cy',0)); sy+=self._oy_off()
        rx=max(self._cx0()+2,min(self.left_w-220,sx-80)); ry=max(self._oy_off()+2,min(self.view_h-80,sy-64))
        self._start_inline_input('pino_nome',str(pad.get('pino','')),target_id=pad.get('id'),rect=(rx,ry,210,24))
        self._flash("Digite o nome/numero do pino e pressione Enter",cor=(0,200,255),dur=2.5)

    def _toggle_gnd_pad(self,idx):
        if idx is None or idx>=len(self.pads):
            self._flash("Clique em um pad para marcar/desmarcar GND",cor=(255,180,0),dur=2.0); return
        self._push_undo()
        pad=self.pads[idx]
        pad['gnd']=not bool(pad.get('gnd'))
        n=self._propagar_marcas_pad(pad,('gnd',))
        self._marcar_dirty()
        estado='GND MARCADO' if pad.get('gnd') else 'GND removido'
        extra=f" (+{n} passante(s))" if n else ""
        self._flash(f"{estado} no pad #{pad.get('id')}{extra}",cor=(0,220,120) if pad.get('gnd') else (180,180,190),dur=2.2)

    def _numerar_pinos_componente(self,comp=None):
        if comp is None:
            comp=next((c for c in self.componentes if c.get('id')==self.comp_selected),None)
        if comp is None and self.selected is not None and self.selected<len(self.pads):
            comp=self._componente_do_pad(self.pads[self.selected].get('id'))
        if not comp:
            self._flash("Selecione um componente (ou um pad dele) para numerar",cor=(255,180,0),dur=2.5); return
        linhas=self._pinagem_conector(comp)
        if not linhas:
            self._flash("Componente sem pads vinculados",cor=(255,100,0),dur=2.0); return
        self._push_undo()
        for l in linhas:
            idx=self._idx_from_id(l.get('pad'))
            if idx is None: continue
            pad=self.pads[idx]
            pad['pino']=str(l.get('pino'))
            self._propagar_marcas_pad(pad,('pino',))
        self.comp_selected=comp.get('id')
        self._marcar_dirty()
        self._flash(f"{len(linhas)} pino(s) numerados em {comp.get('nome','componente')}",cor=(0,220,120),dur=2.6)

    def _anot_display_rect(self,a):
        ax,ay=self._orig_to_disp(a.get('x',0),a.get('y',0)); ay+=self._oy_off()
        txt=_ascii(a.get('text') or 'Nova anotacao')
        fs=0.32
        (tw,th),_=cv2.getTextSize(txt,cv2.FONT_HERSHEY_SIMPLEX,fs,1)
        w=int(max(74,tw+16)); h=int(max(24,th+12))
        x=max(2,min(self.left_w-w-4,int(ax)+8))
        y=max(self._oy_off()+2,min(self.view_h-44-h,int(ay)+8))
        return x,y,w,h

    def _anotacao_at(self,mx,my):
        for a in reversed(self.anotacoes):
            ax,ay,aw,ah=self._anot_display_rect(a)
            if ax-3<=mx<=ax+aw+3 and ay-3<=my<=ay+ah+3:
                return a
        return None

    def _anotacao_por_id(self,aid):
        return next((a for a in self.anotacoes if a.get('id')==aid),None)

    def _iniciar_drag_anotacao(self,a,x,y):
        if not a: return
        self.anot_selected=a.get('id')
        self._anot_undo_feito=False
        self._anot_drag=(a['id'],x,y,a.get('x',0),a.get('y',0))
        self.drag_mode='anot'; self.drag_source='L'; self.drag_start=(x,y)

    def _criar_anotacao(self,ox,oy,texto=''):
        self._push_undo()
        a={'id':self.next_anot_id,'x':int(ox),'y':int(oy),'text':texto or '','cor':[0,220,255]}
        self.next_anot_id+=1
        self.anotacoes.append(a)
        self.anot_selected=a['id']
        self._marcar_dirty()
        sx,sy=self._orig_to_disp(a['x'],a['y']); sy+=self._oy_off()
        rx=max(self._cx0()+2,min(self.left_w-200,sx)); ry=max(self._oy_off()+2,min(self.view_h-80,sy+26))
        self._start_inline_input('anotacao',texto,target_id=a['id'],rect=(rx,ry,190,22))
        self._flash("Digite a anotacao e pressione Enter (vazio cancela)",cor=(0,200,255),dur=2.5)
        return a

    def _editar_anotacao(self,a):
        if not a: return
        self.anot_selected=a.get('id')
        self._anot_drag=None; self.drag_mode=None; self.drag_source=None
        self._push_undo()
        sx,sy=self._orig_to_disp(a.get('x',0),a.get('y',0)); sy+=self._oy_off()
        rx=max(self._cx0()+2,min(self.left_w-200,sx)); ry=max(self._oy_off()+2,min(self.view_h-80,sy+26))
        self._start_inline_input('anotacao',a.get('text',''),target_id=a.get('id'),rect=(rx,ry,190,22))

    def _remover_anotacao(self,aid=None):
        aid=aid if aid is not None else self.anot_selected
        if aid is None: return
        a=self._anotacao_por_id(aid)
        if not a: return
        self._push_undo()
        self.anotacoes=[x for x in self.anotacoes if x.get('id')!=aid]
        if self.anot_selected==aid: self.anot_selected=None
        self._marcar_dirty()
        self._flash("Anotacao removida",cor=(200,200,210),dur=1.5)

    def _limpar_anotacoes(self):
        if not self.anotacoes:
            self._flash("Nao ha anotacoes nesta visao",cor=(180,180,190),dur=1.8); return
        self._push_undo()
        n=len(self.anotacoes)
        self.anotacoes=[]; self.anot_selected=None; self.next_anot_id=1
        self._marcar_dirty()
        self._flash(f"{n} anotacao(oes) removida(s) - Undo [Z] restaura",cor=(200,200,210),dur=2.2)

    def _cor_semantica_familia(self, nome):
        if not nome: return None
        n=nome.strip().upper()
        for key,cor in CORES_SEMANTICAS.items():
            if key in n or n==key: return cor
        return None

    def _sugerir_tipo_componente(self, comp):
        """Reconhecimento heuristico por nome, marcacao, valor, forma, pinos e familias.

        Retorna (tipo, motivo, confianca 0-100, valor_sugerido). Nao altera o componente.
        """
        scores={}; razoes={}
        def add(tipo,pts,motivo):
            if not tipo: return
            scores[tipo]=scores.get(tipo,0)+pts
            razoes.setdefault(tipo,[]).append(motivo)

        nome=_ascii(comp.get('nome') or '').upper().strip()
        marc=_ascii(comp.get('marcacao') or '').upper().strip()
        valor=_ascii(comp.get('valor') or '').upper().strip()
        forma=str(comp.get('forma') or '').lower()
        pads_n=len(comp.get('pads') or [])

        # 1) prefixo do nome (C12, R5, U3, J1, Q2, D1, Y1, LED3...)
        m=re.match(r'^([A-Z]{1,3})',nome)
        if m:
            pref=m.group(1)
            mapa_pref={'C':'capacitor','R':'resistor','FB':'resistor','F':'resistor',
                       'U':'ci','IC':'ci','J':'conector','P':'conector','CN':'conector',
                       'D':'diodo','CR':'diodo','Q':'transistor','T':'transistor',
                       'Y':'cristal','X':'cristal','L':'led','LED':'led'}
            if pref in mapa_pref:
                add(mapa_pref[pref],40,f"nome {pref}")
            elif pref[:1] in mapa_pref:
                add(mapa_pref[pref[:1]],28,f"nome {pref[:1]}")

        # 2) marcacao impressa no componente
        padroes=[
            (r'^(LM|NE|TDA|TLE|TL|CD4|MC|STM|ATM|PIC|ESP|MCP|MAX|LT|AD|OP|ULN|L29|IR2|74HC|74LS|PCF|DS|RTC|AMS|XC|CH34|CP21|FT23)', 'ci', 68, 'marcacao de CI'),
            (r'^(BC|BD|2N|2S[CAK]|TIP|MJE|IRF|IRL|MOS|PNP|NPN)', 'transistor', 62, 'marcacao de transistor'),
            (r'^(1N|BAT|SS|MBR|UF|HER|BY|FR|S[0-9])', 'diodo', 58, 'marcacao de diodo'),
            (r'^(LED|WS28)', 'led', 62, 'marcacao de LED'),
        ]
        for pat,tipo,pts,motivo in padroes:
            if marc and re.match(pat,marc):
                add(tipo,pts,motivo); break

        # 3) valor com unidade eletrica
        if re.search(r'\d\s*(UF|NF|PF|MF|F)\b',valor): add('capacitor',52,'valor de capacitor')
        if re.search(r'\d\s*(K|M|R|OHM)\b',valor): add('resistor',52,'valor de resistor')
        if re.search(r'\d\s*(MHZ|KHZ)\b',valor): add('cristal',52,'frequencia de cristal')

        # 4) forma desenhada
        mapa_forma={'circulo':'capacitor','quadrado':'resistor','retangulo_h':'ci',
                    'retangulo_v':'conector','triangulo':'diodo','losango':'cristal','hexagono':'transistor'}
        if forma in mapa_forma: add(mapa_forma[forma],32,f"forma {forma}")

        # 5) quantidade de pinos
        if pads_n==2:
            add('capacitor',6,'2 pinos'); add('resistor',6,'2 pinos'); add('diodo',4,'2 pinos')
        elif pads_n==3:
            add('transistor',14,'3 pinos')
        elif pads_n>=8:
            add('ci',22,f'{pads_n} pinos')
        elif pads_n>=5:
            add('ci',10,f'{pads_n} pinos'); add('conector',8,f'{pads_n} pinos')

        # 6) familias conectadas (contexto de medicao)
        nets=[]
        for pid in comp.get('pads',[]):
            fam=self._get_familia_do_pad(pid)
            if fam and fam.get('nome'): nets.append(_ascii(fam.get('nome','')).strip().upper())
        nets_set=set(nets)
        alimentacao=bool(nets_set & {'VCC','VDD','5V','3V3','3.3V','12V','VBAT','VIN'})
        if 'GND' in nets_set and alimentacao and pads_n==2: add('capacitor',28,'GND + alimentacao')
        elif 'GND' in nets_set and pads_n==2 and len(nets_set)==2: add('capacitor',16,'filtro GND')
        if alimentacao and len(nets_set)==2 and pads_n==2: add('resistor',16,'pull-up VCC')

        if not scores: return (None,'',0,'')
        tipo,score=max(scores.items(),key=lambda kv:kv[1])
        if score<25: return (None,'',0,'')
        conf=max(40,min(96,int(45+score*0.7)))
        motivo=' + '.join(razoes.get(tipo,[])[:3])
        valor_sug=''
        if not valor:
            if tipo=='capacitor': valor_sug='100nF 16V'
            elif tipo=='resistor': valor_sug='10k'
        return (tipo,motivo,conf,valor_sug)

    def _componente_para_acao(self):
        """Componente selecionado, do pad selecionado, sob o mouse ou unico da lista."""
        comp=next((c for c in self.componentes if c.get('id')==self.comp_selected),None)
        if comp: return comp
        if self.selected is not None and self.selected<len(self.pads):
            comp=self._componente_do_pad(self.pads[self.selected].get('id'))
            if comp:
                self.comp_selected=comp.get('id'); return comp
        if self._cx0()<=self.mouse_x<self.left_w and self.mouse_y>=self._oy_off():
            try:
                ox,oy=self._disp_to_orig(self.mouse_x,self.mouse_y-self._oy_off())
                comp=self._get_componente_at(ox,oy)
                if comp:
                    self.comp_selected=comp.get('id'); return comp
            except Exception:
                pass
        if len(self.componentes)==1:
            self.comp_selected=self.componentes[0].get('id'); return self.componentes[0]
        return None

    def _reconhecer_componente(self, comp=None):
        comp=comp or self._componente_para_acao()
        if not comp:
            self.right_mode='componentes'
            self._flash("Selecione/clique num componente e use Reconhecer tipo",cor=(255,180,0),dur=3.0)
            return
        tipo,motivo,conf,valor_sug=self._sugerir_tipo_componente(comp)
        if not tipo:
            self._iniciar_edicao_componente(comp.get('id'))
            self._flash("Sem dados para reconhecer: preencha marcacao/valor, nome (C12, U3) ou familias",cor=(255,180,0),dur=4.0)
            return
        info=COMPONENTES_TIPOS.get(tipo,COMPONENTES_TIPOS['capacitor'])
        self._push_undo()
        comp['tipo']=tipo; comp['simbolo']=info['simbolo']; comp['cor']=list(info['cor'])
        if valor_sug and not (comp.get('valor') or '').strip(): comp['valor']=valor_sug
        comp['sugestao']=f"{motivo} ({conf}%)"
        self.comp_selected=comp.get('id'); self._marcar_dirty()
        self._iniciar_edicao_componente(comp.get('id'))
        self._flash(f"Reconhecido: {info['nome']} ({conf}%) | {motivo}",cor=tuple(info['cor']),dur=4.0)

    def _auto_pino1_componente(self, comp=None):
        comp=comp or self._componente_para_acao()
        if not comp:
            self.right_mode='componentes'
            self._flash("Selecione um componente para detectar o pino 1",cor=(255,180,0),dur=3.0)
            return
        pads=self._pads_do_componente(comp)
        if not pads:
            self._flash("Componente sem pads vinculados",cor=(255,100,0),dur=2.0); return
        x1,y1,x2,y2=comp.get('x1',0),comp.get('y1',0),comp.get('x2',0),comp.get('y2',0)
        larg=max(1,abs(x2-x1)); alt=max(1,abs(y2-y1)); vertical=alt>=larg
        def score(p):
            s=0.0
            forma=str(p.get('forma') or '').lower()
            if forma in ('retangulo','quadrado'): s+=3.0
            if p.get('gnd'): s-=1.5
            if vertical: s-=(p.get('cy',0)-min(y1,y2))/alt*4.0
            else: s-=(p.get('cx',0)-min(x1,x2))/larg*4.0
            return s
        melhor=max(pads,key=score)
        self._push_undo()
        comp['pino1']=melhor.get('id'); self.comp_selected=comp.get('id'); self._marcar_dirty()
        self._iniciar_edicao_componente(comp.get('id'))
        self._flash(f"Pino 1 heuristico: pad #{melhor.get('id')} (ajuste manualmente se necessario)",cor=(0,220,120),dur=4.0)

    def _datasheet_livre(self):
        comp=self._componente_para_acao()
        if comp:
            self._buscar_datasheet_componente(comp); return
        self._start_inline_input('datasheet_termo','',rect=None)
        self._flash("Digite a marcacao/part number (ex: BC547, LM358) e Enter",cor=(0,200,255),dur=3.5)

    def _abrir_pasta_datasheets(self):
        pasta=os.path.join(os.path.abspath(self.out_dir),'datasheets')
        try:
            os.makedirs(pasta,exist_ok=True)
            os.startfile(pasta)
            self._flash(f"Datasheets: {pasta}",cor=(0,220,120),dur=2.5)
        except Exception as e:
            self._flash(f"Pasta de datasheets: {pasta} ({e})",cor=(255,180,0),dur=3.0)


    def _criar_componente(self, x1, y1, x2, y2, forma=None):
        forma=forma or self.comp_forma_atual
        x_min=min(x1,x2); x_max=max(x1,x2); y_min=min(y1,y2); y_max=max(y1,y2)
        if abs(x2-x1)<6 or abs(y2-y1)<6: return None # FIX v11: era 12, muito grande
        pads_dentro=[p.get('id') for p in self.pads if x_min<=p['cx']<=x_max and y_min<=p['cy']<=y_max]
        if not pads_dentro: self._flash("Nenhum pad dentro",cor=(255,100,100)); return None
        mapa={'circulo':'capacitor','quadrado':'resistor','retangulo_h':'ci','retangulo_v':'conector','triangulo':'diodo','losango':'cristal','hexagono':'transistor'}
        tipo=mapa.get(forma,'capacitor')
        info=COMPONENTES_TIPOS.get(tipo, COMPONENTES_TIPOS['capacitor'])
        self._push_undo()
        comp={'id':self.next_comp_id,'nome':f"{info['simbolo']}{self.next_comp_id}",'tipo':tipo,'simbolo':info['simbolo'],'forma':forma,'x1':x_min,'y1':y_min,'x2':x_max,'y2':y_max,'cor':list(info['cor']),'pads':pads_dentro,'valor':'','tensao':'','obs':'','marcacao':'','datasheet':'','pino1':None}
        sug=self._sugerir_tipo_componente(comp)
        if sug[0] and sug[2]>=70:
            tipo_sug=sug[0]; info_sug=COMPONENTES_TIPOS.get(tipo_sug,info)
            comp['tipo']=tipo_sug; comp['simbolo']=info_sug['simbolo']; comp['cor']=list(info_sug['cor']); info=info_sug
        if sug[0] and sug[2]>=60:
            comp['sugestao']=f"{sug[1]} ({sug[2]}%) {sug[3]}"
            if sug[3] and not comp['valor']: comp['valor']=sug[3]
        self.componentes.append(comp); self.next_comp_id+=1; self.comp_selected=comp['id']; self._marcar_dirty()
        msg=f"{comp['nome']} {info['nome']} {len(pads_dentro)}p"
        if 'sugestao' in comp: msg+=f" | {comp['sugestao']}"
        self._flash(msg,cor=tuple(info['cor']),dur=3.0)
        return comp

    def _remover_componente(self, comp_id):
        self._push_undo(); self.componentes=[c for c in self.componentes if c['id']!=comp_id]
        if self.comp_selected==comp_id: self.comp_selected=None
        self._marcar_dirty()

    def _get_componente_at(self, ox, oy):
        for c in reversed(self.componentes):
            if c['x1']<=ox<=c['x2'] and c['y1']<=oy<=c['y2']: return c
        return None

    def _iniciar_edicao_componente(self, comp_id):
        comp=next((c for c in self.componentes if c['id']==comp_id),None)
        if not comp: return
        self.comp_selected=comp_id
        self.comp_edit_buf_nome=comp.get('nome',''); self.comp_edit_buf_valor=comp.get('valor',''); self.comp_edit_buf_tensao=comp.get('tensao',''); self.comp_edit_buf_obs=comp.get('obs','')
        self.comp_edit_buf_marcacao=comp.get('marcacao','')
        rw=self.right_w; x0=self.left_w+10; w_full=rw-24; w_half=(w_full-6)//2
        tipo_nome=COMPONENTES_TIPOS.get(comp.get('tipo'),{}).get('nome','?')
        extra=''
        if comp.get('marcacao'): extra+=f" | {comp['marcacao']}"
        if comp.get('datasheet'): extra+=' | DS'
        self.comp_edit_header=(f"EDITAR {comp.get('nome','?')}", f"{tipo_nome} | {len(comp.get('pads',[]))} pinos{extra}")
        y=132
        self.comp_edit_sections=[]
        self.comp_edit_sections.append(("DADOS DO COMPONENTE", y, (0,200,255))); y+=18
        pino1=comp.get('pino1')
        self.comp_edit_field_btns=[
            ButtonV5(x0,y,w_full,26,f"Nome: {comp.get('nome','')[:26] or 'sem nome'}", 'comp_field_nome','toggle'),
            ButtonV5(x0,y+30,w_full,26,f"Valor: {comp.get('valor','')[:26] or 'ex: 10k / 100nF'}", 'comp_field_valor','toggle'),
            ButtonV5(x0,y+60,w_full,26,f"Tensao: {comp.get('tensao','')[:24] or 'ex: 16V'}", 'comp_field_tensao','toggle'),
            ButtonV5(x0,y+90,w_full,26,f"Marcacao: {comp.get('marcacao','')[:24] or 'codigo impresso (ex: BC547)'}", 'comp_field_marcacao','toggle'),
            ButtonV5(x0,y+120,w_half,26,f"Pinos: {','.join(str(p) for p in comp.get('pads',[]))[:14] or 'nenhum'}", 'comp_field_pinos','action'),
            ButtonV5(x0+w_half+6,y+120,w_half,26,f"Pino 1: {pino1 if pino1 is not None else '-'}", 'comp_pino1','action'),
            ButtonV5(x0,y+150,w_full,26,f"Obs: {comp.get('obs','')[:28] or 'vazio'}", 'comp_field_obs','toggle'),
        ]
        y+=190
        self.comp_edit_sections.append(("TIPO DO COMPONENTE", y, (0,200,255))); y+=20
        tipos=list(COMPONENTES_TIPOS.items()); cols=2; cw=(w_full-6)//2; ch=26
        self.comp_edit_tipo_btns=[]
        for i,(k,v) in enumerate(tipos):
            bx=x0+(i%cols)*(cw+6); by=y+(i//cols)*(ch+6)
            sel=(comp.get('tipo')==k)
            btn=ButtonV5(bx,by,cw,ch,f"{v['simbolo']} {v['nome']}",f"comp_tipo_{k}",kind='filter' if sel else 'default',cor=v['cor'] if sel else None,tooltip=f"{v['nome']}")
            btn.ativo=sel; self.comp_edit_tipo_btns.append(btn)
        y+=((len(tipos)+cols-1)//cols)*(ch+6)+6
        self.comp_edit_actions_y=y
        self.comp_edit_action_btns=[
            ButtonV5(x0,y,140,28,"SALVAR",'comp_salvar','success'),
            ButtonV5(x0+146,y,140,28,"CANCELAR",'comp_cancelar','danger'),
            ButtonV5(x0,y+32,116,26,"DATASHEET",'comp_datasheet','action'),
            ButtonV5(x0+122,y+32,84,26,"PINAGEM",'comp_pinagem','action'),
            ButtonV5(x0+212,y+32,72,26,"GIRAR",'comp_girar','toggle'),
            ButtonV5(x0,y+64,142,26,"RECONHECER TIPO",'comp_reconhecer','success'),
            ButtonV5(x0+148,y+64,136,26,"AUTO PINO 1",'comp_auto_pino1','action'),
        ]
        self.right_mode='componentes'

    def _refresh_comp_field_labels(self):
        comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
        if not comp: return
        pino1=comp.get('pino1')
        for b in self.comp_edit_field_btns:
            k=b.key
            if k=='comp_field_nome': b.label=f"Nome: {(self.comp_edit_buf_nome or 'sem nome')[:26]}"
            elif k=='comp_field_valor': b.label=f"Valor: {(self.comp_edit_buf_valor or 'ex: 10k / 100nF')[:26]}"
            elif k=='comp_field_tensao': b.label=f"Tensao: {(self.comp_edit_buf_tensao or 'ex: 16V')[:24]}"
            elif k=='comp_field_marcacao': b.label=f"Marcacao: {(self.comp_edit_buf_marcacao or 'codigo impresso (ex: BC547)')[:24]}"
            elif k=='comp_field_pinos': b.label=f"Pinos: {','.join(str(p) for p in comp.get('pads',[]))[:14] or 'nenhum'}"
            elif k=='comp_pino1': b.label=f"Pino 1: {pino1 if pino1 is not None else '-'}"
            elif k=='comp_field_obs': b.label=f"Obs: {(self.comp_edit_buf_obs or 'vazio')[:28]}"

    def _handle_comp_edit(self, key):
        if key.startswith('comp_field_'):
            f=key.replace('comp_field_','')
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if not comp: return
            if f=='nome': self._start_inline_input('comp_nome', comp.get('nome',''), rect=None)
            elif f=='valor': self._start_inline_input('comp_valor', comp.get('valor',''), rect=None)
            elif f=='tensao': self._start_inline_input('comp_tensao', comp.get('tensao',''), rect=None)
            elif f=='marcacao': self._start_inline_input('comp_marcacao', comp.get('marcacao',''), rect=None)
            elif f=='obs': self._start_inline_input('comp_obs', comp.get('obs',''), rect=None)
            elif f in ('pinos','pads'): self._start_inline_input('comp_pinos', ','.join(str(p) for p in comp.get('pads',[])), rect=None)
        elif key.startswith('comp_tipo_'):
            t=key.replace('comp_tipo_','')
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp and t in COMPONENTES_TIPOS:
                self._push_undo(); comp['tipo']=t; comp['simbolo']=COMPONENTES_TIPOS[t]['simbolo']; comp['cor']=list(COMPONENTES_TIPOS[t]['cor']); self._marcar_dirty(); self._iniciar_edicao_componente(comp['id'])
        elif key=='comp_pino1':
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if not comp: return
            pid=self._selected_id()
            if next((p for p in self.pads if p.get('id')==pid), None) is None:
                # FIX v11.4: sem pad selecionado, o pino 1 e o pad mais proximo do clique
                # (antes, um pad velho de outra selecao era marcado sem aviso)
                cand=comp.get('pads') or []
                pads_comp=[p for p in self.pads if p.get('id') in cand]
                try:
                    ox0,oy0=self._disp_to_orig(self.mouse_x,self.mouse_y-self._oy_off())
                except Exception:
                    ox0,oy0=0,0
                if pads_comp:
                    melhor=min(pads_comp,key=lambda p:(p.get('cx',p.get('x',0))-ox0)**2+(p.get('cy',p.get('y',0))-oy0)**2)
                    pid=melhor.get('id'); self.selected=self._idx_from_id(pid)
                    self._flash(f"Pino 1 = pad mais proximo do clique (#{pid}); clique num pad para escolher outro",cor=(0,200,255),dur=3.0)
                else:
                    self._flash("Selecione o pad que eh o pino 1 (clique nele) e tente de novo",cor=(255,180,0),dur=3.0); return
            comp['pino1']=pid
            self._marcar_dirty()
            self._flash(f"Pino 1 do {comp.get('nome','?')} = pad #{pid}",cor=(0,220,120),dur=2.5)
            self._refresh_comp_field_labels()
        elif key=='comp_datasheet':
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp: self._buscar_datasheet_componente(comp)
        elif key=='comp_salvar':
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp:
                self._push_undo(); comp['nome']=self.comp_edit_buf_nome or comp['nome']; comp['valor']=self.comp_edit_buf_valor; comp['tensao']=self.comp_edit_buf_tensao; comp['marcacao']=self.comp_edit_buf_marcacao; comp['obs']=self.comp_edit_buf_obs; self._marcar_dirty(); self._flash(f"{comp['nome']} salvo",cor=tuple(comp['cor']))
            self.comp_selected=None; self.right_mode='componentes'
        elif key=='comp_cancelar': self.comp_selected=None; self.right_mode='componentes'
        elif key=='comp_reconhecer':
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp: self._reconhecer_componente(comp)
        elif key=='comp_auto_pino1':
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp: self._auto_pino1_componente(comp)
        elif key=='comp_excluir':
            if self.comp_selected is not None: self._remover_componente(self.comp_selected)
        elif key=='comp_editar':
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp: self._iniciar_edicao_componente(comp['id'])
        elif key=='comp_girar':
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp: self._girar_componente(comp); self._iniciar_edicao_componente(comp['id'])
        elif key=='comp_pinagem':
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp: self._exportar_pinagem(comp)

    def _buscar_datasheet_componente(self, comp):
        from core import datasheet as ds_lib
        termo=(comp.get('marcacao') or comp.get('valor') or comp.get('nome') or '').strip()
        if not termo:
            self._flash("Preencha a marcacao do componente (ex: BC547)",cor=(255,180,0),dur=3.0); return
        atual=comp.get('datasheet') or ''
        if atual:
            resp=False
            try:
                import tkinter as tk
                from tkinter import messagebox
                root=tk.Tk(); root.withdraw(); root.attributes('-topmost',True)
                resp=messagebox.askyesno("Datasheet", f"Abrir datasheet salvo?\n\n{atual}\n\nNao = buscar novamente")
                root.destroy()
            except Exception:
                resp=False
            if resp:
                try: webbrowser.open(('file:///'+os.path.abspath(atual).replace('\\','/')) if os.path.exists(atual) else atual)
                except Exception: pass
                return
        self._flash(f"Buscando datasheet: {termo}...",cor=(0,200,255),dur=2.0)
        self._render()
        resultados=ds_lib.buscar_datasheet(termo,limite=8)
        if not resultados:
            self._flash("Nenhum datasheet encontrado (conexao/termo)",cor=(255,100,0),dur=3.0); return
        escolhido={'url':None,'baixar':False}
        if dialogs_lib._disponivel():
            import tkinter as tk
            root=tk.Tk(); root.title(f"Datasheet - {termo}"); root.attributes('-topmost',True); root.resizable(False,False)
            root.geometry("860x380")
            tk.Label(root,text=f"Resultados para {termo} (duplo clique abre):",anchor='w').pack(fill='x',padx=10,pady=(10,2))
            frame=tk.Frame(root); frame.pack(fill='both',expand=True,padx=10)
            sb=tk.Scrollbar(frame,orient='vertical')
            lb=tk.Listbox(frame,yscrollcommand=sb.set,activestyle='dotbox',font=('Consolas',9)); sb.config(command=lb.yview)
            lb.pack(side='left',fill='both',expand=True); sb.pack(side='right',fill='y')
            for r in resultados:
                lb.insert('end',('PDF  ' if r['pdf'] else 'WEB  ')+r['url'])
            lb.selection_set(0)
            def abrir():
                sel=lb.curselection()
                if sel:
                    escolhido['url']=resultados[sel[0]]['url']; root.destroy()
            def baixar():
                sel=lb.curselection()
                if sel:
                    escolhido['url']=resultados[sel[0]]['url']; escolhido['baixar']=True; root.destroy()
            bar=tk.Frame(root); bar.pack(fill='x',padx=10,pady=10)
            tk.Button(bar,text="Abrir no navegador",width=20,default='active',command=abrir).pack(side='left')
            tk.Button(bar,text="Baixar PDF",width=14,command=baixar).pack(side='left',padx=8)
            tk.Button(bar,text="Cancelar",width=10,command=root.destroy).pack(side='right')
            lb.bind('<Double-Button-1>',lambda e: abrir())
            root.mainloop()
        else:
            print(f"\n=== DATASHEET: {termo} ===")
            for i, r in enumerate(resultados, 1):
                tipo = 'PDF' if r['pdf'] else 'WEB'
                print(f"  {i}. [{tipo}] {r['url']}")
            print("  q. Cancelar / não baixar")
            try:
                escolha = input("Escolha um número para abrir (ou Enter p/ cancelar): ").strip()
            except EOFError:
                return
            if escolha.lower() in ('q', ''):
                return
            try:
                idx = int(escolha) - 1
                if 0 <= idx < len(resultados):
                    escolhido['url'] = resultados[idx]['url']
                    escolhido['baixar'] = False  # no console, apenas abre
            except ValueError:
                self._flash("Escolha invalida", cor=(255, 180, 0), dur=2.0)
                return
        if not escolhido['url']: return
        if escolhido['baixar']:
            import re as _re
            pasta=os.path.join(os.path.abspath(self.out_dir),'datasheets')
            nome=_re.sub(r'[^A-Za-z0-9._-]+','_',termo)+'.pdf'
            caminho=ds_lib.baixar_pdf(escolhido['url'],pasta,nome=nome)
            if not caminho:
                for r in resultados:
                    if not r['pdf'] or r['url']==escolhido['url']: continue
                    caminho=ds_lib.baixar_pdf(r['url'],pasta,nome=nome)
                    if caminho: break
            if caminho:
                comp['datasheet']=caminho; self._marcar_dirty()
                try: webbrowser.open('file:///'+os.path.abspath(caminho).replace('\\','/'))
                except Exception: pass
                self._flash(f"Datasheet salvo: {os.path.basename(caminho)}",cor=(0,220,120),dur=3.0)
            else:
                self._flash("Falha ao baixar PDF (todos os sites bloquearam)",cor=(255,100,0),dur=3.0)
        else:
            comp['datasheet']=escolhido['url']; self._marcar_dirty()
            try: webbrowser.open(escolhido['url'])
            except Exception: pass
        self._iniciar_edicao_componente(comp['id'])

    def _draw_componente_shape(self, canvas, comp, oy_off=0):
        """Desenha o componente com a forma real (circulo, triangulo, losango, hexagono...)."""
        x1,y1=self._orig_to_disp(comp.get('x1',0),comp.get('y1',0)); x2,y2=self._orig_to_disp(comp.get('x2',0),comp.get('y2',0)); y1+=oy_off; y2+=oy_off
        x1,x2=sorted((x1,x2)); y1,y2=sorted((y1,y2))
        w=max(10,x2-x1); h=max(10,y2-y1); cx,cy=x1+w//2,y1+h//2
        if not (x2>0 and x1<self.left_w and y2>oy_off and y1<self.view_h-40): return
        cor=tuple(comp.get('cor',(80,140,255))); forma=comp.get('forma','retangulo_h')
        sel=(self.comp_selected==comp.get('id'))
        tipo=COMPONENTES_TIPOS.get(comp.get('tipo'),{})
        simbolo=comp.get('simbolo') or tipo.get('simbolo','?')
        x1,y1=self._orig_to_disp(comp.get('x1',0),comp.get('y1',0)); x2,y2=self._orig_to_disp(comp.get('x2',0),comp.get('y2',0)); y1+=oy_off; y2+=oy_off
        x1,x2=sorted((x1,x2)); y1,y2=sorted((y1,y2))
        w=max(10,x2-x1); h=max(10,y2-y1)
        if x2<=0 or x1>=self.left_w or y2<=oy_off or y1>=self.view_h-40: return
        cor=tuple(comp.get('cor',(80,140,255))); forma=comp.get('forma','retangulo_h')
        sel=(self.comp_selected==comp.get('id'))
        tipo=COMPONENTES_TIPOS.get(comp.get('tipo'),{})
        simbolo=comp.get('simbolo') or tipo.get('simbolo','?')

        def geometria(px1,py1,px2,py2):
            ww=px2-px1; hh=py2-py1; ccx,ccy=px1+ww//2,py1+hh//2
            if forma=='circulo':
                return [('ellipse',(ccx,ccy,ww//2,hh//2))]
            if forma=='quadrado':
                lado=min(ww,hh); qx1,qx2=ccx-lado//2,ccx+lado//2; qy1,qy2=ccy-lado//2,ccy+lado//2
                return [('rect',(qx1,qy1,qx2,qy2))]
            if forma=='triangulo':
                return [('poly',[(ccx,py1),(px2,py2),(px1,py2)])]
            if forma=='losango':
                return [('poly',[(ccx,py1),(px2,ccy),(ccx,py2),(px1,ccy)])]
            if forma=='hexagono':
                import math
                pts=[(ww/2*math.cos(math.radians(a)),hh/2*math.sin(math.radians(a))) for a in (0,60,120,180,240,300)]
                return [('poly',[(ccx+int(dx),ccy+int(dy)) for dx,dy in pts])]
            # retangulo_h | retangulo_v | default
            return [('rect',(px1,py1,px2,py2))]

        # preenchimento translucido apenas na regiao do componente
        m=18
        rx1=max(0,x1-m); ry1=max(0,y1-m-22); rx2=min(canvas.shape[1],x2+m); ry2=min(canvas.shape[0],y2+m)
        if rx2>rx1 and ry2>ry1:
            roi=canvas[ry1:ry2,rx1:rx2]; ov=roi.copy()
            for tipo_s,geo in geometria(x1-rx1,y1-ry1,x2-rx1,y2-ry1):
                if tipo_s=='ellipse': cv2.ellipse(ov,(geo[0],geo[1]),(max(1,geo[2]),max(1,geo[3])),0,0,360,cor,-1)
                elif tipo_s=='rect': cv2.rectangle(ov,geo[0:2],geo[2:4],cor,-1)
                else: cv2.fillPoly(ov,[np.array(geo,np.int32)],cor)
            cv2.addWeighted(ov,0.28,roi,0.72,0,roi)
        # contorno
        esp=3 if sel else 2
        for tipo_s,geo in geometria(x1,y1,x2,y2):
            if tipo_s=='ellipse': cv2.ellipse(canvas,(geo[0],geo[1]),(max(1,geo[2]),max(1,geo[3])),0,0,360,cor,esp,cv2.LINE_AA)
            elif tipo_s=='rect': cv2.rectangle(canvas,geo[0:2],geo[2:4],cor,esp,cv2.LINE_AA)
            else: cv2.polylines(canvas,[np.array(geo,np.int32)],True,cor,esp,cv2.LINE_AA)
        # pinos: linha ate os pads vinculados
        for pid in comp.get('pads',[]):
            idx=self._idx_from_id(pid)
            if idx is None or idx>=len(self.pads): continue
            px,py=self._orig_to_disp(self.pads[idx]['cx'],self.pads[idx]['cy']); py+=oy_off
            cv2.line(canvas,(x1+w//2,y1+h//2),(px,py),tuple(int(c*0.55) for c in cor),1,cv2.LINE_AA)
            cv2.circle(canvas,(px,py),3,cor,1,cv2.LINE_AA)
        # selecao: alças nos cantos
        if sel:
            for hx,hy in ((x1,y1),(x2,y1),(x1,y2),(x2,y2)):
                cv2.rectangle(canvas,(hx-4,hy-4),(hx+4,hy+4),(255,255,255),-1)
                cv2.rectangle(canvas,(hx-4,hy-4),(hx+4,hy+4),THEME['accent'],1)
        # etiqueta profissional
        rotulo=f"{simbolo} {comp.get('nome','C?')}"
        valor=str(comp.get('valor','') or '')
        txt=rotulo+(f"  {valor}" if valor else "")
        txt=_ascii(txt)[:30]
        (tw,th),_=cv2.getTextSize(txt,cv2.FONT_HERSHEY_SIMPLEX,0.34,1)
        lx=max(2,min(self.left_w-tw-12,x1)); ly=max(oy_off+2,y1-th-12)
        draw_rounded_rect(canvas,lx-4,ly-3,tw+10,th+10,5,(18,20,26),-1)
        draw_rounded_rect(canvas,lx-4,ly-3,tw+10,th+10,5,(0,0,0),1,cor if not sel else THEME['accent'])
        cv2.putText(canvas,txt,(lx+2,ly+th+1),cv2.FONT_HERSHEY_SIMPLEX,0.34,(240,240,245),1,cv2.LINE_AA)
        # marcador de PINO 1 (pad definido pelo usuario)
        p1=comp.get('pino1')
        if p1 is not None:
            idx=self._idx_from_id(p1)
            if idx is not None and idx < len(self.pads):
                px,py=self._orig_to_disp(self.pads[idx]['cx'],self.pads[idx]['cy']); py+=oy_off
                cv2.circle(canvas,(px,py),8,(255,255,255),-1,cv2.LINE_AA)
                cv2.circle(canvas,(px,py),8,(0,0,0),1,cv2.LINE_AA)
                cv2.putText(canvas,"1",(px-3,py+4),cv2.FONT_HERSHEY_SIMPLEX,0.34,(20,20,20),1,cv2.LINE_AA)
                cv2.line(canvas,(lx+4,ly+th+2),(px,py),(255,255,255),1,cv2.LINE_AA)


    def _iniciar_edicao(self,idx_real,reentrar=False):
        if idx_real is None or idx_real>=len(self.pads): return
        if reentrar:
            if self.edit_sliders and self.edit_field_btns and len(self.edit_sliders)==5:
                for b in self.edit_field_btns:
                    if b.key=='edit_field_forma': b.label=f"Forma de onda: {self.edit_forma[:22] or 'vazio'}"
                    elif b.key=='edit_field_cont': b.label=f"Continuidade: {self.edit_cont[:20] or 'vazio'}"
                    elif b.key=='edit_field_obs_lig': b.label=f"Obs ligada: {self.edit_obs_lig[:30] or 'vazio'}"
                    elif b.key=='edit_field_obs_des': b.label=f"Obs desligada: {self.edit_obs_des[:30] or 'vazio'}"
                return
            # Fix R3 - se reentrar chamado mas listas foram limpas (ESC), cai no fluxo normal
        pad=self.pads[idx_real]; pid=pad.get('id',0); atual=self.measurements.get(pid,{})
        def gf(d,k,defa=0):
            try: return float((d or {}).get(k,'') or defa)
            except Exception: return defa
        lig=atual.get('ligada') or {}; des=atual.get('desligada') or {}
        rw=self.right_w; x0=self.left_w+14; w_full=rw-28
        fam=self._get_familia_do_pad(pid)
        fam_txt=(fam.get('nome','') or f"Fam {fam['id']}") if fam else "sem família"
        self.edit_header=(f"EDITAR PAD #{pid}", f"{'MANUAL' if pad.get('manual') else 'AUTO'} · X={pad.get('cx')} Y={pad.get('cy')} · área {pad.get('area')} px · {fam_txt}")
        self.edit_forma=lig.get('forma',''); self.edit_cont=des.get('continuidade',''); self.edit_obs_lig=lig.get('obs',''); self.edit_obs_des=des.get('obs','')
        self.edit_status_idx={'':0,'OK':1,'SUSP':2,'FALHA':3}.get(atual.get('status') or '',0)
        y=self._panel_top()+64
        self.edit_sections=[]
        self.edit_sections.append(("STATUS DA MEDIÇÃO", y, (0,200,255))); y+=18
        self.edit_status_btns=[ButtonV5(x0,y,64,24,"VAZIO",'st_0','filter'), ButtonV5(x0+70,y,52,24,"OK",'st_1','success'), ButtonV5(x0+128,y,58,24,"SUSP",'st_2','default'), ButtonV5(x0+192,y,58,24,"FALHA",'st_3','danger')]
        for i,b in enumerate(self.edit_status_btns): b.ativo=(i==self.edit_status_idx)
        y+=32
        self.edit_sections.append(("PLACA LIGADA - tensão / frequência", y, (0,200,120))); y+=18
        self.edit_sliders=[
            CustomSlider(0,y,rw-40,26,"Tensao",0,20,gf(lig,'tensao',0),"V","{:.2f}"),
            CustomSlider(0,y+30,rw-40,26,"Frequencia",0,100000,gf(lig,'frequencia',0),"Hz","{:.0f}"),
        ]
        y+=68
        self.edit_field_btns=[
            ButtonV5(x0,y,w_full,26,f"Forma de onda: {self.edit_forma[:22] or 'vazio'}",'edit_field_forma','toggle'),
            ButtonV5(x0,y+32,w_full,26,f"Obs ligada: {self.edit_obs_lig[:30] or 'vazio'}",'edit_field_obs_lig','toggle'),
        ]
        y+=64
        self.edit_sections.append(("PLACA DESLIGADA - resistência / capacitância / diodo", y, (0,170,255))); y+=18
        self.edit_sliders.append(CustomSlider(0,y,rw-40,26,"Resistencia",0,200000,gf(des,'resistencia',0),"Ohm","{:.0f}"))
        self.edit_sliders.append(CustomSlider(0,y+30,rw-40,26,"Capacitancia",0,10000,gf(des,'capacitancia',0),"uF","{:.0f}"))
        self.edit_sliders.append(CustomSlider(0,y+60,rw-40,26,"Diodo Vf",0,2,gf(des,'diodo',0),"V","{:.3f}"))
        y+=94
        self.edit_field_btns.append(ButtonV5(x0,y,w_full,26,f"Continuidade: {self.edit_cont[:20] or 'vazio'}",'edit_field_cont','toggle'))
        self.edit_field_btns.append(ButtonV5(x0,y+32,w_full,26,f"Obs desligada: {self.edit_obs_des[:30] or 'vazio'}",'edit_field_obs_des','toggle'))
        y+=68
        self.edit_action_btns=[
            ButtonV5(x0,y,106,30,"SALVAR",'edit_salvar','success'),
            ButtonV5(x0+112,y,94,30,"CANCELAR",'edit_cancelar','danger'),
            ButtonV5(x0+212,y,72,30,"LIMPAR",'edit_limpar','default'),
        ]
        self.right_mode='edit'

    def _salvar_edicao(self):
        if self.selected is None or self.selected>=len(self.pads): return
        pid=self.pads[self.selected].get('id',0); st=[None,'OK','SUSP','FALHA'][self.edit_status_idx]
        # Fix R1 - preservar vazio vs zero: só salva se slider foi tocado (>0) ou campo texto preenchido
        # Isso mantém compatibilidade com CSV antigo onde vazio = não medido
        def fmt(v, spec):
            return (spec % v) if v>0 else ''
        res={'status':st,'ligada':{'tensao':fmt(self.edit_sliders[0].val,"%.2f"),'frequencia':fmt(self.edit_sliders[1].val,"%.0f"),'forma':self.edit_forma,'obs':self.edit_obs_lig},'desligada':{'resistencia':fmt(self.edit_sliders[2].val,"%.0f"),'continuidade':self.edit_cont,'capacitancia':fmt(self.edit_sliders[3].val,"%.0f"),'diodo':fmt(self.edit_sliders[4].val,"%.3f"),'obs':self.edit_obs_des}}
        self._push_undo(); self.measurements[pid]=res
        self._propagar_medicao(pid,res)
        self._marcar_dirty(); self.right_mode='inspetor'

    def _propagar_medicao(self,pid,res):
        p=next((x for x in self.pads if x.get('id')==pid),None)
        if not p or not p.get('link'): return 0
        link=p['link']; n=0
        for view,pads,nets,vd in self._iter_views_dados():
            if view==self.view_atual: continue
            for q in pads:
                if q.get('link')==link:
                    vd.setdefault('measurements',{})[q.get('id')]=copy.deepcopy(res)
                    n+=1
        if n:
            self._marcar_dirty()
            self._flash(f"Medicao propagada para {n} pad(s) passante(s)",cor=(0,220,120),dur=2.0)
        return n
    def _conectar(self,a_idx,b_idx):
        if a_idx>=len(self.pads) or b_idx>=len(self.pads): return
        a_id=self.pads[a_idx].get('id',a_idx+1); b_id=self.pads[b_idx].get('id',b_idx+1)
        if a_id==b_id: return
        for net in self.nets:
            if a_id in net['pads'] and b_id in net['pads']: return
        self._push_undo(); nets_a=[n for n in self.nets if a_id in n['pads']]; nets_b=[n for n in self.nets if b_id in n['pads']]
        alvo=None
        if nets_a and nets_b:
            main=nets_a[0]; alvo=main
            for other in nets_a[1:]+nets_b:
                if other is main: continue
                for pid in other['pads']:
                    if pid not in main['pads']: main['pads'].append(pid)
                if other in self.nets: self.nets.remove(other)
        elif nets_a: alvo=nets_a[0]; alvo['pads'].append(b_id)
        elif nets_b: alvo=nets_b[0]; alvo['pads'].append(a_id)
        else:
            alvo={'id':self.next_net_id,'pads':[a_id,b_id],'nome':'','cor':self._proxima_cor_familia()}; self.nets.append(alvo); self.next_net_id+=1
        if alvo is not None:
            self._garantir_net_uid(alvo)
            self._propagar_todos()
        self._clamp_familia_scroll(); self._rebuild_pad_to_net(); self._marcar_dirty(); self.pending_connection=None; self._ir_para_navegar()
    def _desconectar(self,idx):
        if idx>=len(self.pads): return
        pid=self.pads[idx].get('id',idx+1); self._push_undo(); novos=[]
        pad=self.pads[idx] if idx<len(self.pads) else {}
        removidos=[]
        for net in self.nets:
            if pid in net['pads']:
                if net.get('uid') and pad.get('link'): removidos.append((net['uid'],pad['link']))
                net['pads']=[x for x in net['pads'] if x!=pid]
                if len(net['pads'])>=2: novos.append(net)
            else: novos.append(net)
        self.nets=novos
        for uid,link in removidos: self._remover_link_de_net(uid,link)
        self._clamp_familia_scroll(); self._rebuild_pad_to_net(); self._marcar_dirty(); self._ir_para_navegar()

    @staticmethod
    def _decode_wheel_delta(flags):
        # FIX v11.3: zoom robusto para todos backends
        # Qt: delta em high word
        qt_delta=(flags>>16)&0xFFFF
        if qt_delta:
            if qt_delta&0x8000: qt_delta-=0x10000
            if qt_delta!=0: 
                return 1 if qt_delta>0 else -1
        # Win32: low word
        raw=flags&0xFFFF
        if raw:
            if raw&0x8000: raw-=0x10000
            if raw!=0:
                return 1 if raw>0 else -1
        # Fallback: usa flags direto
        if flags>0: return 1
        if flags<0: return -1
        return 1  # se evento disparou, assume zoom in por padrão

    def _on_mouse(self,event,x,y,flags,param):
        self.mouse_x=x; self.mouse_y=y
        # Menus contextuais: tratados antes de qualquer outra acao
        menus=[getattr(self,'context_menu_pad',None),getattr(self,'context_menu_comp',None),
               getattr(self,'context_menu_familia',None),getattr(self,'context_menu_anot',None)]
        menus=[m for m in menus if m is not None]
        if event==cv2.EVENT_LBUTTONDOWN:
            menus_abertos=False
            for menu in menus:
                if not menu.visible: continue
                menus_abertos=True
                rx,ry,rw,rh=menu.rect
                dentro=(rx<=x<=rx+rw and ry<=y<=ry+rh)
                act=menu.hit(x,y)
                menu.hide()
                if act:
                    if menu is self.context_menu_pad: self._handle_pad_menu(act)
                    elif menu is self.context_menu_comp:
                        if act=='comp_numerar': self._numerar_pinos_componente()
                        else: self._handle_comp_edit(act)
                    elif menu is self.context_menu_anot: self._handle_anot_menu(act)
                    else: self._handle_familia_btn(act)
                    return
            if menus_abertos:
                # FIX v11.4: o clique que FECHA o menu nao vaza para o canvas -
                # antes ele criava anotacao/GND ou iniciava drag no ponto clicado
                return
            # botoes flutuantes de zoom (estilo visualizador de fotos)
            for zkey,(zx,zy,zw,zh) in getattr(self,'zoom_btns',[]):
                if zx<=x<=zx+zw and zy<=y<=zy+zh:
                    self._acao_zoom(zkey); self.tooltip_shown=False; return
            # rail vertical de ferramentas
            if x<self._cx0() and y>=self._toolbar_h() and y<self.view_h-40:
                key=self._rail_hit(x,y)
                if key: self._on_button(key); self.tooltip_shown=False; return
        elif event==cv2.EVENT_RBUTTONDOWN:
            for menu in menus: menu.hide()
            # FIX v11.4: clique direito durante arraste cancela o arraste (nao
            # seleciona e move outro pad no proximo MOUSEMOVE)
        elif event==cv2.EVENT_MOUSEMOVE:
            for menu in menus: menu.update_hover(x,y)
            self._zoom_hover=None
            for zkey,(zx,zy,zw,zh) in getattr(self,'zoom_btns',[]):
                if zx<=x<=zx+zw and zy<=y<=zy+zh: self._zoom_hover=zkey; break
        if event in (cv2.EVENT_MBUTTONDOWN,cv2.EVENT_MBUTTONDBLCLK): self.drag_mode='pan'; self.drag_source='M'; self.drag_start=(x,y); self.tooltip_shown=False; return
        if event==cv2.EVENT_MBUTTONUP:
            if self.drag_source=='M': self.drag_mode=None; self.drag_source=None
            return
        if self.drag_mode=='pan' and self.drag_source=='M':
            # nao cancela por ausencia de flag: alguns backends nao informam o bit
            # do botao no MOUSEMOVE; o MBUTTONUP encerra o arraste
            pass
        if event==cv2.EVENT_MOUSEMOVE:
            for s in self.sliders:
                if s.dragging: s.set_from_x(x-self.left_w-10); self._invalidar_cache_visiveis(); self.tooltip_shown=False; return
            for s in self.edit_sliders:
                if s.dragging: s.set_from_x(x-self.left_w-10); self.tooltip_shown=False; return
            if self.drag_mode=='pan': self.tooltip_shown=False
        if event==cv2.EVENT_LBUTTONUP:
            for s in self.sliders: s.dragging=False
            for s in self.edit_sliders: s.dragging=False
        for b in self.botoes_menu+self.botoes_tab+self.botoes_view+self.botoes_toolbar+self.botoes_filtro: b.hover=b.hit(x,y)
        for b in self.edit_field_btns: b.hover=b.hit(x,y)
        for b in self.edit_status_btns+self.edit_action_btns+self.familia_botoes: b.hover=b.hit(x,y)
        if self.preset_dropdown:
            if self.preset_dropdown.expanded:
                self.preset_dropdown.hover_idx=-1
                for i,key in enumerate(PRESETS_BANCADA_V84.keys()):
                    dx,dy=self.preset_dropdown.rect[0], self.preset_dropdown.rect[1]+self.preset_dropdown.rect[3]+2+i*44
                    if dx<=x<=dx+self.preset_dropdown.rect[2] and dy<=y<=dy+40: self.preset_dropdown.hover_idx=i; break
        if self.show_minimap:
            mw,mh=self.minimap_w,self.minimap_h; mx=self.left_w-mw-12; my=self._toolbar_h()+8
            if mx<=x<=mx+mw and my<=y<=my+mh:
                self.minimap_hover=True
                if event==cv2.EVENT_LBUTTONDOWN:
                    rx=(x-mx)/mw; ry=(y-my)/mh
                    self.pan_x=self._cx0()+self._canvas_w()/2 - rx*self.w0*self.base_scale*self.zoom
                    self.pan_y=self._oy_off()+ (self.view_h-40-self._oy_off())/2 - ry*self.h0*self.base_scale*self.zoom
                    self.tooltip_shown=False; return
            else: self.minimap_hover=False
        if x>=self.left_w:
            if self.right_mode=='menu':
                self.sidebar.layout(self.left_w,60,self.right_w,self.view_h-36-60,self.font_scale)
                if event==cv2.EVENT_MOUSEMOVE:
                    self.sidebar.handle_motion(x,y,time.time()); return
                if event==cv2.EVENT_LBUTTONDOWN:
                    act=self.sidebar.handle_click(x,y)
                    if act: self._on_button(act)
                    self.tooltip_shown=False; return
                if event in (cv2.EVENT_MOUSEWHEEL,cv2.EVENT_MOUSEHWHEEL):
                    self.sidebar.handle_scroll(self._decode_wheel_delta(flags)); return
                if event==cv2.EVENT_LBUTTONUP: return
                return
            if event==cv2.EVENT_MOUSEMOVE and self.drag_mode=='pan': self.drag_start=(x,y); return
            if event==cv2.EVENT_LBUTTONUP and self.drag_mode: self.drag_mode=None; self.drag_source=None; return
            if self.right_mode=='calib':
                if event==cv2.EVENT_LBUTTONDOWN:
                    if self.preset_dropdown:
                        k=self.preset_dropdown.hit_item(x,y)
                        if k: self._aplicar_preset(k); self.tooltip_shown=False; return
                        if self.preset_dropdown.hit(x,y): self.preset_dropdown.expanded=not self.preset_dropdown.expanded; self.tooltip_shown=False; return
                elif event==cv2.EVENT_MOUSEMOVE:
                    for s in self.sliders:
                        if s.dragging: s.set_from_x(x-self.left_w-10); return
                elif event==cv2.EVENT_LBUTTONUP:
                    for s in self.sliders:
                        if s.dragging: s.dragging=False; self._invalidar_cache_visiveis(); return
                if event==cv2.EVENT_LBUTTONDOWN and self.preset_dropdown and self.preset_dropdown.expanded:
                    if not self.preset_dropdown.hit(x,y) and self.preset_dropdown.hit_item(x,y) is None: self.preset_dropdown.expanded=False
                return
            elif self.right_mode=='edit':
                if event==cv2.EVENT_LBUTTONDBLCLK:
                    for i,s in enumerate(self.edit_sliders):
                        if s.hit_track(x-self.left_w-10,y):
                            self._start_inline_input(f'edit_num_{i}', f"{s.val:.4g}")
                            return
                if event==cv2.EVENT_LBUTTONDOWN:
                    for b in self.edit_field_btns:
                        if b.hit(x,y):
                            rect=b.rect
                            if b.key=='edit_field_forma': self._start_inline_input('forma',self.edit_forma, target_id=None, rect=rect)
                            elif b.key=='edit_field_cont': self._start_inline_input('cont',self.edit_cont, rect=rect)
                            elif b.key=='edit_field_obs_lig': self._start_inline_input('obs_lig',self.edit_obs_lig, rect=rect)
                            elif b.key=='edit_field_obs_des': self._start_inline_input('obs_des',self.edit_obs_des, rect=rect)
                            return
                    lig_on=(self.estado_placa=='ligada')
                    for i,s in enumerate(self.edit_sliders):
                        enabled=lig_on if i<2 else (not lig_on)
                        if enabled and s.hit_track(x-self.left_w-10,y):
                            s.dragging=True; s.set_from_x(x-self.left_w-10); return
                    for b in self.edit_status_btns+self.edit_action_btns:
                        if b.hit(x,y):
                            if b.key.startswith('st_'): self.edit_status_idx=int(b.key.split('_')[1])
                            elif b.key=='edit_salvar': self._salvar_edicao()
                            elif b.key=='edit_cancelar': self._ir_para_navegar()
                            elif b.key=='edit_limpar':
                                for s in self.edit_sliders: s.val=0
                                self.edit_status_idx=0; self.edit_forma=''; self.edit_cont=''; self.edit_obs_lig=''; self.edit_obs_des=''
                            for i,bb in enumerate(self.edit_status_btns): bb.ativo=(i==self.edit_status_idx)
                            return
                elif event==cv2.EVENT_MOUSEMOVE:
                    for s in self.edit_sliders:
                        if s.dragging: s.set_from_x(x-self.left_w-10); return
                return
            elif self.right_mode=='familias':
                if event==cv2.EVENT_LBUTTONDOWN:
                    if self.paleta_dropdown and self.paleta_dropdown.expanded:
                        k=self.paleta_dropdown.hit_item(x,y)
                        if k is not None:
                            net=next((n for n in self.nets if n['id']==self.familia_selected),None) if self.familia_selected is not None else None
                            if net and 0<=k<len(PALETA_32): net['cor']=list(PALETA_32[k][1]); self._marcar_dirty()
                            self.paleta_dropdown.selected_idx=k; self.paleta_dropdown.expanded=False
                            return
                        if not self.paleta_dropdown.hit(x,y): self.paleta_dropdown.expanded=False
                        return
                    if self.paleta_dropdown and self.paleta_dropdown.hit(x,y) and self.familia_selected is not None:
                        self.paleta_dropdown.expanded=True; return
                    for b in self.familia_botoes:
                        if b.hit(x,y): self._handle_familia_btn(b.key); return
                elif event==cv2.EVENT_MOUSEMOVE:
                    if self.paleta_dropdown and self.paleta_dropdown.expanded:
                        h=self.paleta_dropdown.hit_item(x,y); self.paleta_dropdown.hover_idx=h if h is not None else -1
                return
            elif self.right_mode=='camadas':
                if event==cv2.EVENT_LBUTTONDOWN:
                    for b in self.familia_botoes:
                        if b.hit(x,y): self._handle_familia_btn(b.key); return
                return
            elif self.right_mode=='componentes':
                editando=(self.comp_selected is not None and bool(self.comp_edit_field_btns))
                if event==cv2.EVENT_MOUSEMOVE:
                    botoes=(self.comp_edit_field_btns+self.comp_edit_tipo_btns+self.comp_edit_action_btns) if editando else self.familia_botoes
                    for b in botoes: b.hover=b.hit(x,y)
                    return
                if event==cv2.EVENT_LBUTTONDOWN:
                    if editando:
                        for b in self.comp_edit_field_btns+self.comp_edit_tipo_btns+self.comp_edit_action_btns:
                            if b.hit(x,y):
                                self._handle_comp_edit(b.key); self.tooltip_shown=False; return
                        return
                    for b in self.familia_botoes:
                        if b.hit(x,y):
                            if b.key=='fam_voltar': self._handle_familia_btn(b.key)
                            else: self._on_button(b.key)
                            self.tooltip_shown=False; return
                    toolbar_h=self._toolbar_h(); y0=toolbar_h+58
                    for i,c in enumerate(self.componentes[self.comp_scroll:self.comp_scroll+9]):
                        yy=y0+i*30
                        if yy<=y<=yy+28 and x>=self.left_w:
                            self.comp_selected=c.get('id'); self._iniciar_edicao_componente(c.get('id')); self.tooltip_shown=False; return
                    return
                return
            if self.right_mode=='inspetor':
                if event==cv2.EVENT_LBUTTONDOWN:
                    if self.selected is not None and self.selected<len(self.pads): self._iniciar_edicao(self.selected)
                return
        if y<28:
            if event==cv2.EVENT_LBUTTONDOWN:
                for b in self.botoes_menu:
                    if b.hit(x,y): self._on_button(b.key); self.tooltip_shown=False; return
            return
        if y<58:
            if event==cv2.EVENT_LBUTTONDOWN:
                for b in self.botoes_view:
                    if b.hit(x,y):
                        if b.key=='view_ant': self._ciclar_view(-1)
                        elif b.key=='view_prox': self._ciclar_view(1)
                        else: self._trocar_view(b.key.replace('view_',''))
                        self.tooltip_shown=False; return
                for b in self.botoes_tab:
                    if b.hit(x,y): nova='calibrar' if b.key=='tab_calibrar' else 'anotar'; self._trocar_aba(nova); self.tooltip_shown=False; return
            return
        toolbar_bottom=(self.botoes_filtro[-1].rect[1]+40) if self.botoes_filtro else 110
        if y<toolbar_bottom:
            if event==cv2.EVENT_LBUTTONDOWN:
                for b in self.botoes_toolbar+self.botoes_filtro:
                    if b.hit(x,y): self._on_button(b.key); self.tooltip_shown=False; return
            return
        oy_off=self._oy_off(); ox,oy=self._disp_to_orig(x,y-oy_off); idx=self._pad_no_ponto(ox,oy)
        if self.regua_modo and event==cv2.EVENT_LBUTTONDOWN and self._cx0()<=x<self.left_w and y>oy_off:
            self.regua_pts.append((x,y))
            if len(self.regua_pts)>=2:
                (ax,ay),(bx,by)=self.regua_pts[-2],self.regua_pts[-1]
                px=((bx-ax)**2+(by-ay)**2)**0.5
                if self.mm_por_px>0:
                    self._flash(f"Distancia: {px*self.mm_por_px:.2f} mm ({px:.0f} px)",cor=(0,220,120),dur=3.0)
                else:
                    self._regua_px=px
                    self._start_inline_input('escala_mm','',rect=None)
                    self._flash(f"{px:.0f} px - digite a medida real em mm",cor=(0,200,255),dur=3.5)
                self.regua_pts=[]
            else:
                self._flash("Regua: clique o 2o ponto",cor=(0,200,255),dur=2.0)
            return
        if event==cv2.EVENT_MOUSEMOVE:
            self.hover_idx=idx if idx is not None else -1
            if self.drag_mode=='pan':
                dx=x-self.drag_start[0]; dy=y-self.drag_start[1]; self.drag_start=(x,y)
                new_pan_x=self.pan_x+dx; new_pan_y=self.pan_y+dy
                img_w_screen=self.w0*self.base_scale*self.zoom; img_h_screen=self.h0*self.base_scale*self.zoom
                min_pan_x=min(0,self._canvas_w()-img_w_screen); max_pan_x=max(0,self._canvas_w()-img_w_screen); min_pan_y=min(0,(self.view_h-40)-img_h_screen); max_pan_y=max(0,(self.view_h-40)-img_h_screen)
                self.pan_x=max(min_pan_x,min(max_pan_x,new_pan_x)); self.pan_y=max(min_pan_y,min(max_pan_y,new_pan_y)); return
            if self.drag_mode=='compmove' and self.comp_drag_orig:
                comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
                if not comp: return
                dx=x-self.comp_drag_orig[0]; dy=y-self.comp_drag_orig[1]
                bs=max(0.01,self.base_scale*self.zoom)
                ddx=int(dx/bs); ddy=int(dy/bs)
                ox1,oy1,ox2,oy2=self.comp_drag_orig[2:]
                kind=self.comp_drag_kind or 'move'
                if kind=='move':
                    comp['x1']=ox1+ddx; comp['x2']=ox2+ddx; comp['y1']=oy1+ddy; comp['y2']=oy2+ddy
                else:
                    hnd=kind.split(':')[1] if ':' in kind else ''
                    if 'l' in hnd: comp['x1']=ox1+ddx
                    if 'r' in hnd: comp['x2']=ox2+ddx
                    if 't' in hnd: comp['y1']=oy1+ddy
                    if 'b' in hnd: comp['y2']=oy2+ddy
                return
            if self.drag_mode=='comp' and self.comp_drawing:
                # FIX v11.2: atualiza preview do componente durante drag
                self.comp_drag_end = (ox,oy)
                return
            if self.drag_mode=='pad' and self.drag_source=='L':
                if self.tab=='calibrar' and self.mode=='mover' and self.selected is not None and self.selected<len(self.pads):
                    ox=max(0,min(self.w0-1,ox)); oy=max(0,min(self.h0-1,oy))
                    self.pads[self.selected]['cx']=ox; self.pads[self.selected]['cy']=oy; self.pads[self.selected]['x']=ox; self.pads[self.selected]['y']=oy; self._drag_pad_moved=True; self._invalidar_cache_visiveis()
                return
            if self.drag_mode=='anot' and self._anot_drag:
                aid,x0,y0,ax,ay=self._anot_drag
                a=self._anotacao_por_id(aid)
                if a:
                    if not getattr(self,'_anot_undo_feito',False):
                        self._push_undo(); self._anot_undo_feito=True
                    bs=max(0.01,self.base_scale*self.zoom)
                    a['x']=int(max(0,min(self.w0-1,ax+(x-x0)/bs)))
                    a['y']=int(max(0,min(self.h0-1,ay+(y-y0)/bs)))
                return
        elif event==cv2.EVENT_LBUTTONUP:
            if self.drag_mode=='anot':
                if self._anot_drag:
                    aid,x0,y0,ax,ay=self._anot_drag
                    a=self._anotacao_por_id(aid)
                    if a and (a.get('x')!=int(ax) or a.get('y')!=int(ay)): self._marcar_dirty()
                self.drag_mode=None; self.drag_source=None; self._anot_drag=None; self._anot_undo_feito=False
                return
            if self.drag_mode=='compmove':
                self.drag_mode=None; self.drag_source=None; self.comp_drag_kind=None; self.comp_drag_orig=None
                self._marcar_dirty()
                comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
                if comp: self._iniciar_edicao_componente(comp['id'])
                return
            if self.drag_mode=='comp' and self.comp_drawing:
                # FIX v11.2: finaliza criação de componente
                if self.comp_drag_start and self.comp_drag_end:
                    x1,y1 = self.comp_drag_start
                    x2,y2 = self.comp_drag_end
                    if abs(x2-x1)>=6 and abs(y2-y1)>=6:
                        comp = self._criar_componente(x1,y1,x2,y2, self.comp_forma_atual)
                        if comp:
                            print(f"Componente criado: {comp['nome']}")
                self.comp_drawing=False
                self.comp_drag_start=None
                self.comp_drag_end=None
                self.drag_mode=None
                self.drag_source=None
                return
            if self.drag_mode=='pad' and self.drag_source=='L':
                if self._drag_pad_moved and self.selected is not None: self._marcar_dirty()
                elif not self._drag_pad_moved:
                    if self.undo_stack and self._drag_snapshot_id is not None:
                        if self.undo_stack[-1].get("_uid")==self._drag_snapshot_id: self.undo_stack.pop()
                self.drag_mode=None; self.drag_source=None; self._drag_pad_orig=None; self._drag_pad_moved=False; self._drag_snapshot_id=None; return
            if self.drag_mode=='pan' and self.drag_source=='L':
                # FIX v11.4: soltar o botao esquerdo encerra o pan (antes ficava chocado
                # e a imagem continuava se movendo sem botao pressionado)
                self.drag_mode=None; self.drag_source=None; return
        elif event==cv2.EVENT_MOUSEWHEEL:
            delta=self._decode_wheel_delta(flags)
            if delta==0: delta=1  # fallback - evento disparou, faz zoom
            zoom_in=delta>0
            # FIX v11.3: zoom centrado no mouse, range 0.1-20x, fator 1.15 suave
            factor = 1.15 if zoom_in else 1/1.15
            new_z = max(0.1, min(20.0, self.zoom*factor))
            f=new_z/self.zoom if self.zoom!=0 else 1.0
            vx=(x-self._cx0())-self.pan_x; vy=(y-oy_off)-self.pan_y
            self.pan_x=(x-self._cx0())-vx*f; self.pan_y=(y-oy_off)-vy*f
            self.zoom=new_z
            self._invalidar_cache_visiveis()
            self.tooltip_shown=False
            return
        elif event==cv2.EVENT_MOUSEHWHEEL:
            # Horizontal wheel também faz zoom
            raw=self._decode_wheel_delta(flags)
            if raw==0: raw=1
            zoom_in=raw>0
            factor = 1.15 if zoom_in else 1/1.15
            new_z = max(0.1, min(20.0, self.zoom*factor))
            f=new_z/self.zoom if self.zoom!=0 else 1.0
            vx=(x-self._cx0())-self.pan_x; vy=(y-oy_off)-self.pan_y
            self.pan_x=(x-self._cx0())-vx*f; self.pan_y=(y-oy_off)-vy*f
            self.zoom=new_z
            self._invalidar_cache_visiveis()
            self.tooltip_shown=False
            return
        elif event==cv2.EVENT_LBUTTONDBLCLK:
            if self.inline_input_active: return
            a=self._anotacao_at(x,y)
            if a:
                self.anot_selected=a['id']; self._editar_anotacao(a); return
            if idx is not None and idx<len(self.pads):
                self.selected=idx
                if self.mode=='pino': self._nomear_pino_pad(idx); return
                if self.tab=='anotar' and self.mode not in ('gnd','anotacao'):
                    self._iniciar_edicao(idx); return
            return
        elif event==cv2.EVENT_LBUTTONDOWN:
            if self.inline_input_active:
                if self.inline_input_field in ('anotacao','pino_nome') and self.inline_input_buffer.strip():
                    self._confirm_inline_input()
                else:
                    self._cancel_inline_input()
                return
            if self.preset_dropdown and self.preset_dropdown.expanded: self.preset_dropdown.expanded=False
            # Marcacao estilo RastreCurve: anotacao livre, nome de pino e GND
            if self.mode=='anotacao':
                a=self._anotacao_at(x,y)
                if a:
                    self._iniciar_drag_anotacao(a,x,y)
                    return
                self._criar_anotacao(ox,oy,''); return
            if self.tab=='anotar' and self.mode not in ('pino','gnd','remover','adicionar','medir','conectar','desconectar','componente'):
                a_hit=self._anotacao_at(x,y)
                if a_hit:
                    self._iniciar_drag_anotacao(a_hit,x,y)
                    return
            if self.mode=='pino':
                if idx is not None: self.selected=idx; self._nomear_pino_pad(idx)
                else: self._flash("PINO: clique em um pad da placa",cor=(255,180,0),dur=2.0)
                return
            if self.mode=='gnd':
                if idx is not None: self.selected=idx; self._toggle_gnd_pad(idx)
                else: self._flash("GND: clique em um pad da placa",cor=(255,180,0),dur=2.0)
                return
            # FIX v11.2: Criação de componentes - arraste para criar
            if self.mode=='componente':
                # clicar num componente existente: mover/redimensionar (duplo clique edita)
                comp_at = self._get_componente_at(ox,oy)
                if comp_at:
                    self.comp_selected = comp_at['id']
                    handle=self._comp_handle_at(comp_at,x,y)
                    self._push_undo()
                    self.comp_drag_orig=(x,y,comp_at['x1'],comp_at['y1'],comp_at['x2'],comp_at['y2'])
                    self.comp_drag_kind=('resize:'+handle) if handle else 'move'
                    self.drag_mode='compmove'; self.drag_source='L'; self.drag_start=(x,y)
                    return
                # Senão inicia drag de novo componente
                self.comp_drawing = True
                self.comp_drag_start = (ox,oy)
                self.comp_drag_end = (ox,oy)
                self.drag_mode = 'comp'
                self.drag_source = 'L'
                self.drag_start = (x,y)
                return
            if self.mode=='mover' and self.tab=='calibrar':
                if idx is not None:
                    uid=self._push_undo(); self._drag_snapshot_id=uid; self.selected=idx; self.drag_mode='pad'; self.drag_source='L'; self.drag_start=(x,y); self._drag_pad_orig=(self.pads[idx]['cx'],self.pads[idx]['cy']); self._drag_pad_moved=False
                else: self.drag_mode='pan'; self.drag_source='L'; self.drag_start=(x,y); self.selected=None
                return
            if self.mode=='adicionar': self._adicionar_pad(ox,oy); return
            if self.mode=='remover':
                if idx is not None: self._remover_pad(idx)
                return
            if idx is None: self.selected=None; self.anot_selected=None
            else:
                self.selected=idx; self.anot_selected=None
                if self.tab=='anotar':
                    if self.mode=='medir': self._iniciar_edicao(idx)
                    elif self.mode=='conectar':
                        if self.pending_connection is None: self.pending_connection=idx
                        else: self._conectar(self.pending_connection,idx)
                    elif self.mode=='desconectar': self._desconectar(idx)
                    else: self.right_mode='inspetor'
        elif event==cv2.EVENT_RBUTTONDOWN:
            # Menu contextual estilo RastreCurve: anotacao > componente > pad
            for menu in menus: menu.hide()
            if self.drag_mode or self.drag_source:
                self.drag_mode=None; self.drag_source=None
                if self.selected is not None and not self._drag_pad_moved:
                    pass
            self._drag_pad_orig=None; self._drag_pad_moved=False; self._drag_snapshot_id=None
            bounds=(self.view_w,self.view_h)
            for menu in menus: menu.bounds=bounds
            a=self._anotacao_at(x,y)
            if a:
                self.anot_selected=a['id']
                self.context_menu_anot.show(x,y,self.context_menu_anot.items)
                return
            if idx is not None and idx<len(self.pads):
                self.selected=idx
                self.context_menu_pad.show(x,y,self.context_menu_pad.items)
                return
            comp_at=self._get_componente_at(ox,oy)
            if comp_at:
                self.comp_selected=comp_at['id']
                self.context_menu_comp.show(x,y,self.context_menu_comp.items)
                return
            self.selected=None; self.anot_selected=None

    def _handle_pad_menu(self,key):
        idx=self.selected
        if idx is None or idx>=len(self.pads):
            self._flash("Nenhum pad selecionado",cor=(255,180,0),dur=1.8); return
        pad=self.pads[idx]; pid=pad.get('id')
        if key=='editar': self._iniciar_edicao(idx); return
        if key=='conectar':
            self.mode='conectar'; self.pending_connection=idx; self.right_mode='inspetor'
            self._flash(f"Pad #{pid} marcado - clique no segundo pad",cor=(0,200,255),dur=2.5); return
        if key=='desconectar': self._desconectar(idx); return
        if key=='duplicar': self._duplicar_pad(idx); return
        if key=='isolar': self._isolar_pad(idx); return
        if key=='remover': self._remover_pad(idx); return
        if key=='pino_nomear': self._nomear_pino_pad(idx); return
        if key=='gnd_toggle': self._toggle_gnd_pad(idx); return
        if key=='anotar_pad':
            ox=max(0,min(self.w0-1,pad.get('cx',0)+18)); oy=max(0,min(self.h0-1,pad.get('cy',0)+18))
            self._criar_anotacao(ox,oy,''); return
        if key=='comp_numerar':
            comp=self._componente_do_pad(pid)
            if comp: self._numerar_pinos_componente(comp)
            else: self._flash("Este pad nao pertence a um componente",cor=(255,180,0),dur=2.2)
            return
        if key=='status_ciclo':
            cur=(self.measurements.get(pid) or {}).get('status') if isinstance(self.measurements.get(pid),dict) else None
            cycle={None:'OK','OK':'SUSP','SUSP':'FALHA','FALHA':None}
            novo=cycle.get(cur)
            self._push_undo(); m=self.measurements.setdefault(pid,{}); m['status']=novo; self._marcar_dirty()
            self._flash(f"Status pad #{pid}: {novo or 'VAZIO'}",cor=(0,220,120) if novo else (180,180,190),dur=1.8); return
        if key=='comp_pino1':
            comp=self._componente_do_pad(pid)
            if not comp:
                self._flash("Este pad nao pertence a um componente",cor=(255,180,0),dur=2.2); return
            comp['pino1']=pid; self._marcar_dirty()
            self._flash(f"Pino 1 de {comp.get('nome','?')} = pad #{pid}",cor=(0,220,120),dur=2.4); return
        if key=='comp_datasheet':
            comp=self._componente_do_pad(pid)
            if comp: self._buscar_datasheet_componente(comp)
            else: self._flash("Este pad nao pertence a um componente",cor=(255,180,0),dur=2.2)
            return

    def _handle_anot_menu(self,key):
        if key=='anot_editar':
            a=self._anotacao_por_id(self.anot_selected)
            if a: self._editar_anotacao(a)
        elif key=='anot_excluir':
            self._remover_anotacao()

    def _handle_familia_btn(self,key):
        if key.startswith('layer_'): self._alternar_camada(key.replace('layer_','')); return
        if key=='fam_voltar': self._ir_para_navegar(); return
        if key=='fam_up': self.familia_scroll=max(0,self.familia_scroll-1); return
        if key=='fam_down': self.familia_scroll=min(max(0,len(self.nets)-9),self.familia_scroll+1); return
        if key.startswith('pal_') and self.familia_selected is not None:
            idx=int(key.split('_')[1]); net=next((n for n in self.nets if n['id']==self.familia_selected),None)
            if net and 0<=idx<len(PALETA_32):
                net['cor']=list(PALETA_32[idx][1]); self._marcar_dirty()
                if net.get('uid'): self._sincronizar_net(net)
                return
        if key.startswith('fam_sel_'): self.familia_selected=int(key.split('_')[2]); return
        if key=='fam_nova_cor' and self.familia_selected is not None:
            net=next((n for n in self.nets if n['id']==self.familia_selected),None)
            if net:
                cur=tuple(net.get('cor',PALETA_32[0][1])); j=0
                for k,(_,c) in enumerate(PALETA_32):
                    if tuple(c)==cur: j=k; break
                j=(j+1)%len(PALETA_32); net['cor']=list(PALETA_32[j][1]); self._marcar_dirty()
                if net.get('uid'): self._sincronizar_net(net)
            return
        if key=='fam_rename' and self.familia_selected is not None:
            net=next((n for n in self.nets if n['id']==self.familia_selected),None)
            if net: self._start_inline_input('rename_familia',net.get('nome',''),net['id'])
            return

    def _on_button(self,key):
        if self.inline_input_active and key not in ('buscar',): self._cancel_inline_input()
        self.drag_mode=None; self.drag_source=None
        for s in self.sliders: s.dragging=False
        for s in self.edit_sliders: s.dragging=False
        if key=='modo_comp': self.mode='componente'; self.right_mode='componentes'; self._flash(f"Modo Comp: {self.comp_forma_atual} - arraste para criar", cor=(80,140,255), dur=3.0)
        elif key=='abrir_img': self._abrir_imagem_dialog()
        elif key=='abrir_proj': self._abrir_projeto_dialog()
        elif key=='abrir_pasta': self._abrir_pasta_saida()
        elif key=='toggle_minimap': self.show_minimap=not self.show_minimap
        elif key=='toggle_gpu': self._alternar_gpu()
        elif key=='prox_pendente': self._proximo_sem_medir()
        elif key=='camadas':
            self.right_mode='camadas' if self.right_mode!='camadas' else ('inspetor' if self.tab=='anotar' else 'calib')
        elif key=='relatorio': self._gerar_relatorio()
        elif key=='camera': self._capturar_camera()
        elif key=='transferir': self._transferir_anotacoes()
        elif key=='importar_centroides': self._importar_centroides()
        elif key=='export_kicad': self._exportar_kicad()
        elif key=='export_gerber': self._exportar_gerber()
        elif key=='import_pcb': self._importar_pcb()
        elif key=='modo_diff': self._toggle_diff()
        elif key=='diff_lado_a_lado': self._toggle_diff_lado_a_lado()
        elif key=='diff_sobreposto': self._toggle_diff_sobreposto()
        elif key=='diff_recalcular': self._recalcular_diff()
        # --- Botoes de plugins (M1) ---
        elif key and key.startswith('plugin_'):
            self._executar_botao_plugin(key)
        elif key=='detectar_tiles': self._detectar_tiles()
        elif key=='regua': self._iniciar_regua()
        elif key=='comparar_ouro': self._comparar_ouro()
        elif key=='paleta': self._abrir_paleta()
        elif key.startswith('layer_'): self._alternar_camada(key.replace('layer_',''))
        elif key=='comp_girar':
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp: self._girar_componente(comp); self._iniciar_edicao_componente(comp['id'])
        elif key=='comp_pinagem':
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp: self._exportar_pinagem(comp)
        elif key=='recuperar_ultimo':
            ultimo=self.prefs.get('ultimo_projeto') or ''
            if ultimo and os.path.isdir(ultimo): self._abrir_projeto(ultimo)
            else: self._flash("Nenhum projeto recente",cor=(255,180,0),dur=2.0)
        elif key=='comp_up': self.comp_scroll=max(0,self.comp_scroll-1)
        elif key=='comp_down': self.comp_scroll=min(max(0,len(self.componentes)-9),self.comp_scroll+1)
        elif key=='comp_nova': self.mode='componente'; self.right_mode='componentes'; self._flash("Modo Componente: arraste na placa para desenhar",cor=(80,140,255),dur=2.5)
        elif key=='comp_painel':
            self.mode='navegar'; self.right_mode='componentes'; self._flash("Painel de componentes: clique num componente ou use NOVO",cor=(0,200,255),dur=3.0)
        elif key=='comp_reconhecer': self._reconhecer_componente()
        elif key=='comp_auto_pino1': self._auto_pino1_componente()
        elif key=='datasheet_livre': self._datasheet_livre()
        elif key=='datasheets_pasta': self._abrir_pasta_datasheets()
        elif key=='comp_datasheet':
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp: self._buscar_datasheet_componente(comp)
            else: self._datasheet_livre()
        elif key in ('comp_pino1','comp_girar','comp_pinagem','comp_excluir'):
            comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
            if comp: self._handle_comp_edit(key)
            else: self._flash("Selecione um componente primeiro",cor=(255,180,0),dur=2.0)
        elif key=='toggle_ids': self.show_ids=not self.show_ids; self._salvar_prefs(); self._flash(f"IDs {'ON' if self.show_ids else 'OFF'} (zoom 1.2x mostra todos)",cor=(0,200,255),dur=1.8)
        elif key=='view_img': self._definir_imagem_view()
        elif key=='view_ant': self._ciclar_view(-1)
        elif key=='view_prox': self._ciclar_view(1)
        elif key.startswith('view_'): self._trocar_view(key.replace('view_',''))
        elif key=='vincular_views': self._vincular_pads_auto()
        elif key=='vincular_manual': self._vincular_pad_manual()
        elif key=='toggle_auto_vincular':
            self.auto_vincular=not self.auto_vincular; self._salvar_prefs()
            self._flash(f"Auto-vincular passantes: {'ON' if self.auto_vincular else 'OFF'}",cor=(0,200,255),dur=2.0)
        elif key=='tab_calibrar': self._trocar_aba('calibrar')
        elif key=='tab_anotar': self._trocar_aba('anotar')
        elif key=='modo_nav': self.mode='navegar'
        elif key=='modo_add': self.mode='adicionar'
        elif key=='modo_move': self.mode='mover'
        elif key=='modo_del': self.mode='remover'
        elif key=='modo_med': self.mode='medir'
        elif key=='modo_con': self.mode='conectar'; self.pending_connection=None
        elif key=='modo_descon': self.mode='desconectar'
        elif key=='modo_anot':
            self.mode='anotacao'; self.right_mode='inspetor'
            self._flash("ANOTAR: clique na placa para criar; arraste para mover; duplo clique edita; Del apaga",cor=(0,220,255),dur=3.5)
        elif key=='modo_pino':
            self.mode='pino'; self.right_mode='inspetor'
            self._flash("PINO: clique num pad e digite o nome/numero (ex: 1, A3, VCC)",cor=(0,220,255),dur=3.0)
        elif key=='modo_gnd':
            self.mode='gnd'; self.right_mode='inspetor'
            self._flash("GND: clique num pad para marcar/desmarcar o terra",cor=(0,220,120),dur=3.0)
        elif key=='pin_numerar': self._numerar_pinos_componente()
        elif key=='modo_al_validar':
            self.mode='validar_al'; self.right_mode='inspetor'
            self._flash("VALIDAR AL: clique em pseudo-label para aprovar/rejeitar; clique em vazio para criar novo",cor=(0,220,255),dur=3.5)
        elif key=='al_pseudo':
            self._gerar_pseudo_labels()
        elif key=='al_train':
            self._treinar_modelo_al()
        elif key=='anot_limpar': self._limpar_anotacoes()
        elif key=='sidebar':
            if self.right_mode=='menu':
                self.right_mode='inspetor' if self.tab=='anotar' else 'calib'
            else:
                self.right_mode='menu'; self.sidebar.scroll=0
            self.tooltip_shown=False
        elif key=='status_ciclo':
            if self.selected is not None: self._handle_pad_menu('status_ciclo')
        elif key=='detectar': self._push_undo(); self._detectar(True)
        elif key=='detectar_smart': self._push_undo(); self._detectar(True,modo='smart')
        elif key=='detectar_exemplo': self._detectar_exemplo()
        elif key=='modo_detector': self._modo_detector_alternar()
        elif key=='modo_detector_ia': self._modo_detector_ia()
        elif key=='modelo_ia_escolher': self._escolher_modelo_ia()
        elif key=='exportar_dataset': self._exportar_dataset()
        elif key=='pre_anotar_album': self._pre_anotar_album()
        elif key=='smart_sens_mais': self._ajustar_sens_smart(+0.05)
        elif key=='smart_sens_menos': self._ajustar_sens_smart(-0.05)
        elif key=='reset': self._confirm_action='reset'; self._start_inline_input('reset_confirm',''); self.inline_input_buffer=''
        elif key=='mascara': self.show_mask=not self.show_mask
        elif key=='fit': self._reset_zoom_fit()
        elif key=='salvar': self._salvar_tudo()
        elif key=='undo': self._undo()
        elif key=='redo': self._redo()
        elif key=='editar':
            if self.selected is not None and self.selected<len(self.pads): self._iniciar_edicao(self.selected)
            else: self._flash("Clique num pad da placa para editar a medicao",cor=(255,180,0),dur=2.2)
        elif key=='duplicar': self._duplicar_pad(self.selected)
        elif key=='isolar': self._isolar_pad(self.selected)
        elif key=='familias': self.right_mode='familias'; self.familia_scroll=0; self._clamp_familia_scroll()
        elif key=='toggle_estado': self.estado_placa='ligada' if self.estado_placa=='desligada' else 'desligada'
        elif key in ('f_todos','f_auto','f_manual','f_ok','f_susp','f_falha','f_vazio'):
            if key=='f_todos': self.filter_status=None; self.filter_tipo=None; self.search_id=None; self.filter_familia_id=None
            elif key=='f_auto': self.filter_tipo='auto'; self.filter_status=None; self.filter_familia_id=None
            elif key=='f_manual': self.filter_tipo='manual'; self.filter_status=None; self.filter_familia_id=None
            elif key=='f_ok': self.filter_status='OK'
            elif key=='f_susp': self.filter_status='SUSP'
            elif key=='f_falha': self.filter_status='FALHA'
            elif key=='f_vazio': self.filter_status='VAZIO'
            self._invalidar_cache_visiveis()
        elif key=='buscar': self._start_inline_input('buscar',str(self.search_id) if self.search_id else "")
        elif key=='anomalias': self._executar_anomalias()

    def _executar_anomalias(self):
        """
        Abre diálogo para selecionar a placa de referência (ouro) e compara
        com a imagem atualmente carregada usando detector_anomalias.
        """
        if self.img is None:
            self._flash("Carregue uma imagem primeiro", cor=(255,100,0), dur=2.0)
            return
        ouro = dialogs_lib.escolher_arquivo(
            "Selecione a PLACA OURO (referência boa)",
            filetypes=[("Imagens","*.jpg *.jpeg *.png *.bmp *.tiff"),("Todos","*.*")],
        )
        if not ouro:
            return
        try:
            teste_path=self.img_path_original
            if not teste_path or not os.path.exists(teste_path):
                self._flash("Imagem atual não encontrada em disco", cor=(255,0,0), dur=2.0)
                return
            self._flash("Comparando placas... aguarde", cor=(0,200,255), dur=3.0)
            cv2.waitKey(1)
            res=executar_comparacao(
                caminho_ouro=ouro,
                caminho_teste=teste_path,
                dir_saida=os.path.join(self.out_dir, "analise_anomalias"),
                salvar_visualizacao=True,
            )
            msg=(f"Anomalias: {res['total_anomalias']} | "
                 f"Similaridade: {res['score_global']:.2%} | "
                 f"Severidade: {res['por_severidade']}")
            self._flash(msg, cor=(0,255,0) if res['total_anomalias']==0 else (0,200,255), dur=5.0)
            print(f"📄 Relatório de anomalias: {res['json_path']}")
        except Exception as e:
            import traceback; traceback.print_exc()
            self._flash(f"Erro na análise: {e}", cor=(255,0,0), dur=3.0)

    def _rebuild_cache_linhas(self):
        """Cache com TODAS as linhas (usado quando nenhum pad está selecionado)."""
        if not self._cache_linhas_dirty: return
        self._cache_linhas=[]; id_to_pad={p.get('id'):p for p in self.pads}
        for net in self.nets:
            cor=self._cor_familia(net); pads_net=[pid for pid in net['pads'] if pid in id_to_pad]
            if len(pads_net)<2: continue
            for i,pid_a in enumerate(pads_net):
                for pid_b in pads_net[i+1:]:
                    pa=id_to_pad.get(pid_a); pb=id_to_pad.get(pid_b)
                    if pa and pb: self._cache_linhas.append((pa['cx'],pa['cy'],pb['cx'],pb['cy'],cor))
        self._cache_linhas_dirty=False

    def _get_familia_do_pad(self, pid):
        """Retorna o net (familia) ao qual o pad pertence, ou None - Fix BUG #15 cache O(1)"""
        if hasattr(self,'_pad_to_net') and self._pad_to_net:
            return self._pad_to_net.get(pid)
        for net in self.nets:
            if pid in net.get('pads',[]):
                return net
        return None


    def _pad_id_in_familia(self, linha, pads_fam):
        # linha = ox1,oy1,ox2,oy2,cor - precisa mapear via pad id
        # simplificado: verifica se linha pertence a família via proximidade, aqui só retorna True se filtro ativo
        return True

    def _remover_componente(self, comp_id):
        if comp_id is None:
            return
        self._push_undo()
        self.componentes = [c for c in self.componentes if c.get('id')!=comp_id]
        self.comp_selected = None
        self._marcar_dirty()
        self._flash(f"Componente {comp_id} removido", cor=(255,100,100))

    def _get_linhas_focadas(self):
        """
        v11.2: Linhas OCULTAS por padrão - FIX solicitado
        - Sem seleção e sem filtro familia → [] (limpo)
        - Filtro familia ativo → mostra só familia filtrada
        - Pad com familia selecionado → só arestas do pad
        """
        if self.selected is None or self.selected >= len(self.pads):
            # Se tem filtro de familia, mostra familia filtrada
            if self.filter_familia_id is not None:
                self._rebuild_cache_linhas()
                # Filtra só linhas da familia filtrada
                fam = next((n for n in self.nets if n['id']==self.filter_familia_id), None)
                if not fam:
                    return []
                pads_fam = set(fam.get('pads',[]))
                id_to_pad = {p.get('id'): p for p in self.pads}
                # Reconstrói só com pads da familia
                linhas = []
                cor = self._cor_familia(fam)
                pads_list = [pid for pid in fam['pads'] if pid in id_to_pad]
                for i, pid_a in enumerate(pads_list):
                    for pid_b in pads_list[i+1:]:
                        pa = id_to_pad.get(pid_a); pb = id_to_pad.get(pid_b)
                        if pa and pb:
                            linhas.append((pa['cx'],pa['cy'],pb['cx'],pb['cy'],cor))
                return linhas
            return []  # FIX: oculto por padrão
        sel_pid = self.pads[self.selected].get('id')
        nets_sel = [n for n in self.nets if sel_pid in n['pads']]
        if not nets_sel:
            return []
        linhas = []
        id_to_pad = {p.get('id'): p for p in self.pads}
        for net in nets_sel:
            cor = self._cor_familia(net)
            for other in net['pads']:
                if other == sel_pid:
                    continue
                pa = id_to_pad.get(sel_pid)
                pb = id_to_pad.get(other)
                if pa and pb:
                    linhas.append((pa['cx'], pa['cy'], pb['cx'], pb['cy'], cor))
        return linhas

    def _render(self):
        self._visiveis=self._pads_visiveis_idx(); self.cursor_blink+=1
        if self._flash_msg and time.time()>=self._flash_until: self._flash_msg=""; self._flash_until=0
        canvas=np.full((self.view_h,self.view_w,3),THEME['bg'],dtype=np.uint8)
        cv2.rectangle(canvas,(0,0),(self.view_w,29),THEME['panel_toolbar'],-1)
        cv2.line(canvas,(0,29),(self.view_w,29),THEME['border'],1)
        for b in self.botoes_menu:
            if b.key=='toggle_gpu':
                b.label='GPU ON [J]' if self.gpu_ativo else 'GPU OFF [J]'
                b.ativo=self.gpu_ativo
            if b.key=='sidebar': b.ativo=(self.right_mode=='menu')
            b.draw(canvas,self.font_scale)
        cv2.rectangle(canvas,(0,30),(self.view_w,60),THEME['panel_tab'],-1)
        cv2.line(canvas,(0,60),(self.view_w,60),THEME['border'],1)
        for b in self.botoes_tab: b.draw(canvas,self.font_scale)
        for b in self.botoes_view:
            b.ativo=(self.view_atual==b.key.replace('view_',''))
            b.draw(canvas,self.font_scale)
        # dica contextual na area livre entre as abas e as visoes (explica o modo ativo)
        try:
            x_ini=self.botoes_tab[-1].rect[0]+self.botoes_tab[-1].rect[2]+22
            x_fim=min(b.rect[0] for b in self.botoes_view)-14
            if x_fim-x_ini>150:
                hint=_ascii(self._hint_modo())
                max_chars=max(16,int((x_fim-x_ini)/5.7))
                if len(hint)>max_chars: hint=hint[:max_chars-3].rstrip()+'...'
                cv2.putText(canvas,'i  '+hint,(x_ini,50),cv2.FONT_HERSHEY_SIMPLEX,0.27,THEME['text_dim'],1,cv2.LINE_AA)
        except Exception:
            pass
        n_ok=sum(1 for m in self.measurements.values() if isinstance(m,dict) and m.get('status')=='OK')
        # dica: estatísticas ficam na barra de status (evita sobrepor abas de visão)
        toolbar_h=self._toolbar_h(); cv2.rectangle(canvas,(0,60),(self.left_w,toolbar_h),THEME['card_alt'],-1)
        cv2.line(canvas,(0,toolbar_h),(self.left_w,toolbar_h),THEME['border'],1)
        # cartoes de grupo com legenda (contexto visivel de cada bloco)
        for titulo,(gx,gy,gw,gh) in getattr(self,'toolbar_groups',[]):
            draw_rounded_rect(canvas,gx,gy,gw,gh,7,THEME['card'],-1)
            draw_rounded_rect(canvas,gx,gy,gw,gh,7,(0,0,0),1,THEME['border'])
            cv2.putText(canvas,_ascii(titulo),(gx+8,gy+12),cv2.FONT_HERSHEY_SIMPLEX,0.24,THEME['text_dim'],1,cv2.LINE_AA)
        for b in self.botoes_toolbar+self.botoes_filtro:
            b.ativo=False
            if b.key=='detectar_smart': b.ativo=(self.detector_modo=='smart')
            if b.key=='modo_detector_ia': b.ativo=(self.detector_modo=='ia')
            if b.key=='modo_comp' and self.mode=='componente': b.ativo=True
            if b.key=='modo_nav' and self.mode=='navegar': b.ativo=True
            if b.key=='modo_add' and self.mode=='adicionar': b.ativo=True
            if b.key=='modo_move' and self.mode=='mover': b.ativo=True
            if b.key=='modo_del' and self.mode=='remover': b.ativo=True
            if b.key=='modo_med' and self.mode=='medir': b.ativo=True
            if b.key=='modo_con' and self.mode=='conectar': b.ativo=True
            if b.key=='modo_descon' and self.mode=='desconectar': b.ativo=True
            if b.key=='modo_anot' and self.mode=='anotacao': b.ativo=True
            if b.key=='modo_pino' and self.mode=='pino': b.ativo=True
            if b.key=='modo_gnd' and self.mode=='gnd': b.ativo=True
            if b.key=='toggle_mira': b.ativo=self.mostrar_mira
            if b.key=='mascara' and self.show_mask: b.ativo=True
            if b.key=='familias' and self.right_mode=='familias': b.ativo=True
            if b.key=='f_todos' and self.filter_status is None and self.filter_tipo is None and self.search_id is None and self.filter_familia_id is None: b.ativo=True
            if b.key=='f_ok' and self.filter_status=='OK': b.ativo=True
            if b.key=='f_susp' and self.filter_status=='SUSP': b.ativo=True
            if b.key=='f_falha' and self.filter_status=='FALHA': b.ativo=True
            if b.key=='f_vazio' and self.filter_status=='VAZIO': b.ativo=True
            if b.key=='f_auto' and self.filter_tipo=='auto': b.ativo=True
            if b.key=='f_manual' and self.filter_tipo=='manual': b.ativo=True
            if b.key=='toggle_estado': b.ativo=(self.estado_placa=='ligada')
            b.draw(canvas,self.font_scale)
        self._atualizar_estado_botoes_diff()
        # rail vertical de ferramentas (estilo editor de imagens)
        self._layout_rail(); self._draw_rail(canvas)
        # FIX v11: base_scale não recalcula todo frame - preserva zoom
        s_fit=self.base_scale # mantem base
        oy_off=self._oy_off()
        ox0=max(0,int(-self.pan_x/(self.base_scale*self.zoom))); oy0=max(0,int(-self.pan_y/(self.base_scale*self.zoom))); ox1=min(self.w0,int((self._canvas_w()-self.pan_x)/(self.base_scale*self.zoom))+1); oy1=min(self.h0,int((self.view_h-40-oy_off-self.pan_y)/(self.base_scale*self.zoom))+1)
        # -------------------- MODO DIFF (frente x verso) --------------------
        if self.modo_diff and self.diff_result is not None:
            self._render_diff(canvas)
        elif ox1>ox0 and oy1>oy0:
            crop=self.img[oy0:oy1,ox0:ox1]; tw=int((ox1-ox0)*self.base_scale*self.zoom); th=int((oy1-oy0)*self.base_scale*self.zoom)
            if tw>0 and th>0:
                scaled=cv2.resize(crop,(tw,th),interpolation=cv2.INTER_AREA); px=max(self._cx0(),int(ox0*self.base_scale*self.zoom+self.pan_x+self._cx0())); py=max(oy_off,int(oy0*self.base_scale*self.zoom+self.pan_y+oy_off)); cw=min(tw,self.left_w-px); ch=min(th,self.view_h-40-py)
                if cw>0 and ch>0:
                    if self.show_mask and self.layers.get('mascara',True) and self.mask_preview is not None and self.tab=='calibrar':
                        mask_crop=self.mask_preview[oy0:oy1,ox0:ox1]; mask_scaled=cv2.resize(mask_crop,(tw,th),interpolation=cv2.INTER_NEAREST)[:ch,:cw]; overlay=scaled[:ch,:cw].copy(); overlay[mask_scaled>0]=(0,255,0); blended=cv2.addWeighted(scaled[:ch,:cw],0.6,overlay,0.4,0); canvas[py:py+ch,px:px+cw]=blended
                    else: canvas[py:py+ch,px:px+cw]=scaled[:ch,:cw]
        if self.tab=='anotar' and self.layers.get('linhas',True):
            # v8.7: linhas focadas só do pad selecionado (ou todas se nenhum selecionado)
            linhas = self._get_linhas_focadas()
            for ox1,oy1,ox2,oy2,cor in linhas:
                ax,ay=self._orig_to_disp(ox1,oy1); bx,by=self._orig_to_disp(ox2,oy2); ay+=oy_off; by+=oy_off
                if self._cx0()<=ax<self.left_w and oy_off<=ay<self.view_h and self._cx0()<=bx<self.left_w and oy_off<=by<self.view_h:
                    cv2.line(canvas,(ax,ay),(bx,by),cor,2,cv2.LINE_AA)
        # ---------- PADS: desenho profissional (forma real, cor da familia, status) ----------
        bs=self.base_scale*self.zoom
        mostrar_ids=getattr(self,'show_ids',True)
        def _pad_geo(p):
            rw=max(3,min(30,int((p.get('w',12) or 12)*bs*0.5)))
            rh=max(3,min(30,int((p.get('h',12) or 12)*bs*0.5)))
            return rw,rh
        def _pad_cor(p,pid):
            fam=self._get_familia_do_pad(pid) if (self.tab=='anotar' and self.layers.get('familias',True)) else None
            if fam is not None: return self._cor_familia(fam),True
            return ((0,165,255) if p.get('manual') else (225,225,225)),False
        # 1) preenchimentos translucidos
        desenhar_pads=self.layers.get('pads',True)
        bolha=canvas.copy()
        for real_idx in self._visiveis:
            if not desenhar_pads: break
            if real_idx>=len(self.pads): continue
            p=self.pads[real_idx]; sx,sy=self._orig_to_disp(p["cx"],p["cy"]); sy+=oy_off
            if not (self._cx0()<=sx<self.left_w and oy_off<=sy<self.view_h-40): continue
            cor_pad,tem_fam=_pad_cor(p,p.get('id',0)); rw,rh=_pad_geo(p)
            if not tem_fam and self.zoom<1.2 and real_idx not in (self.selected,self.hover_idx): continue
            cv2.ellipse(bolha,(sx,sy),(rw,rh),0,0,360,cor_pad,-1)
        cv2.addWeighted(bolha,0.18,canvas,0.82,0,canvas)
        # 2) contornos, status, selecao e IDs
        for real_idx in self._visiveis:
            if not desenhar_pads: break
            if real_idx>=len(self.pads): continue
            p=self.pads[real_idx]; sx,sy=self._orig_to_disp(p["cx"],p["cy"]); sy+=oy_off
            if not (self._cx0()<=sx<self.left_w and oy_off<=sy<self.view_h-40): continue
            pid=p.get('id',0); m=self.measurements.get(pid,{}) if self.tab=='anotar' else {}; status=m.get('status') if isinstance(m,dict) else None
            cor_pad,tem_fam=_pad_cor(p,pid); rw,rh=_pad_geo(p)
            sel=(real_idx==self.selected); hov=(real_idx==self.hover_idx)
            lod_simples=(self.zoom<1.2 and not sel and not hov and not tem_fam)
            if lod_simples:
                cv2.circle(canvas,(sx,sy),1,cor_pad,-1,cv2.LINE_AA)
            else:
                esp=3 if sel else (1 if max(rw,rh)<5 else 2)
                cv2.ellipse(canvas,(sx,sy),(rw,rh),0,0,360,cor_pad,esp,cv2.LINE_AA)
                cv2.circle(canvas,(sx,sy),1 if not sel else 2,cor_pad,-1,cv2.LINE_AA)
            if p.get('manual'): cv2.drawMarker(canvas,(sx-rw-3,sy-rh-3),(0,165,255),cv2.MARKER_DIAMOND,7,1,cv2.LINE_AA)
            if p.get('link'):
                cv2.drawMarker(canvas,(sx+rw+3,sy+rh+3),(255,255,255),cv2.MARKER_DIAMOND,6,1,cv2.LINE_AA)
            if self.tab=='anotar' and status:
                cor_status=self.CORES_STATUS.get(status,self.CORES_STATUS[None])
                rr=max(rw,rh,4)+2
                cv2.ellipse(canvas,(sx,sy),(rr,rr),0,0,360,cor_status,2,cv2.LINE_AA)
            if sel:
                cv2.ellipse(canvas,(sx,sy),(rw+6,rh+6),0,0,360,(255,255,255),1,cv2.LINE_AA)
                cv2.ellipse(canvas,(sx,sy),(rw+9,rh+9),0,0,360,THEME['accent'],1,cv2.LINE_AA)
                guia=(65,75,95)
                cv2.line(canvas,(self._cx0(),sy),(self.left_w,sy),guia,1)
                cv2.line(canvas,(sx,oy_off),(sx,self.view_h-40),guia,1)
            elif hov:
                cv2.ellipse(canvas,(sx,sy),(rw+4,rh+4),0,0,360,(0,255,255),1,cv2.LINE_AA)
            if self.pending_connection is not None and real_idx==self.pending_connection:
                cv2.ellipse(canvas,(sx,sy),(rw+10,rh+10),0,0,360,(0,255,255),2,cv2.LINE_AA)
            if mostrar_ids and self.layers.get('ids',True) and (self.zoom>=1.2 or sel or hov):
                txt=str(pid); fs=0.30 if not sel else 0.36
                (tw,th),_=cv2.getTextSize(txt,cv2.FONT_HERSHEY_SIMPLEX,fs,1)
                bx=sx+rw+3; by=sy-rh-th-4
                borda=cor_pad if (self.tab=='anotar' and tem_fam) else THEME['border']
                draw_rounded_rect(canvas,bx,by,tw+8,th+7,4,(14,15,19),-1)
                draw_rounded_rect(canvas,bx,by,tw+8,th+7,4,(0,0,0),1,borda)
                cv2.putText(canvas,txt,(bx+4,by+th+3),cv2.FONT_HERSHEY_SIMPLEX,fs,(235,235,240),1,cv2.LINE_AA)
        # ---------- MARCACOES: pino, GND e anotacoes ----------
        if self.layers.get('pinos',True):
            ocupados=[]
            def _colide(r):
                x,y,w,h=r
                if x<2 or x+w>self.left_w-4 or y<oy_off+2 or y+h>self.view_h-42: return True
                for ox,oy,ow,oh in ocupados:
                    if x<ox+ow+3 and x+w+3>ox and y<oy+oh+3 and y+h+3>oy: return True
                return False
            def _badge(txt,cor,centros,force=False,gnd=False):
                (tw,th),_=cv2.getTextSize(txt,cv2.FONT_HERSHEY_SIMPLEX,0.26,1)
                extra=12 if gnd else 0
                bw,bh=tw+8+extra,th+8
                for cx,cy in centros:
                    x=int(cx-bw/2); y=int(cy-bh/2)
                    if force or not _colide((x,y,bw,bh)):
                        draw_rounded_rect(canvas,x,y,bw,bh,4,(14,18,22),-1)
                        draw_rounded_rect(canvas,x,y,bw,bh,4,(0,0,0),1,cor)
                        if gnd:
                            gx=x+7; gy=y+bh//2-3
                            cv2.line(canvas,(gx-4,gy),(gx+4,gy),cor,1,cv2.LINE_AA)
                            cv2.line(canvas,(gx-2,gy+3),(gx+2,gy+3),cor,1,cv2.LINE_AA)
                            cv2.line(canvas,(gx-1,gy+6),(gx+1,gy+6),cor,1,cv2.LINE_AA)
                        cv2.putText(canvas,txt,(x+4+extra,y+th+3),cv2.FONT_HERSHEY_SIMPLEX,0.26,cor,1,cv2.LINE_AA)
                        ocupados.append((x,y,bw,bh))
                        return (x,y,bw,bh)
                return None
            for real_idx in self._visiveis:
                if real_idx>=len(self.pads): continue
                p=self.pads[real_idx]
                if not (p.get('pino') or p.get('gnd')): continue
                sx,sy=self._orig_to_disp(p.get('cx',0),p.get('cy',0)); sy+=oy_off
                if not (self._cx0()<=sx<self.left_w and oy_off<=sy<self.view_h-40): continue
                sel=(real_idx==self.selected); hov=(real_idx==self.hover_idx)
                if self.base_scale*self.zoom<0.35 and not (sel or hov): continue
                rw,rh=_pad_geo(p); force=sel or hov
                if p.get('pino'):
                    txt=_ascii(str(p.get('pino')))[:10]
                    _badge(txt,(0,210,255),[(sx,sy-rh-12),(sx,sy+rh+16),(sx+rw+22,sy),(sx-rw-22,sy)],force)
                if p.get('gnd'):
                    _badge('GND',(80,220,120),[(sx,sy+rh+16),(sx,sy-rh-12),(sx-rw-26,sy),(sx+rw+26,sy)],force,gnd=True)
        if self.layers.get('anotacoes',True):
            for a in self.anotacoes:
                ax,ay=self._orig_to_disp(a.get('x',0),a.get('y',0)); ay+=oy_off
                bx,by,bw,bh=self._anot_display_rect(a)
                if not (self._cx0()<=bx<self.left_w and oy_off<=by<self.view_h-40): continue
                sel=(a.get('id')==self.anot_selected)
                cor_borda=(255,255,255) if sel else (0,200,255)
                cv2.line(canvas,(ax,ay),(bx,by),(0,200,255),1,cv2.LINE_AA)
                cv2.circle(canvas,(ax,ay),3,(0,200,255),-1,cv2.LINE_AA)
                cv2.circle(canvas,(ax,ay),5,(255,255,255),1,cv2.LINE_AA)
                draw_rounded_rect(canvas,bx,by,bw,bh,6,(26,31,40) if not sel else (38,48,62),-1)
                draw_rounded_rect(canvas,bx,by,bw,bh,6,(0,0,0),1,cor_borda)
                cv2.rectangle(canvas,(bx+1,by+1),(bx+3,by+bh-2),(0,200,255),-1)
                txt=_ascii(a.get('text') or 'Nova anotacao')[:40]
                cv2.putText(canvas,txt,(bx+7,by+bh-8),cv2.FONT_HERSHEY_SIMPLEX,0.30,(240,245,250),1,cv2.LINE_AA)
                if sel:
                    for hx,hy in ((bx,by),(bx+bw,by),(bx,by+bh),(bx+bw,by+bh)):
                        cv2.rectangle(canvas,(hx-3,hy-3),(hx+3,hy+3),(255,255,255),-1)
                        cv2.rectangle(canvas,(hx-3,hy-3),(hx+3,hy+3),(0,120,180),1)

        # ---------- COMPONENTES: formas reais por cima dos pads ----------
        if self.layers.get('componentes',True):
            for comp in self.componentes:
                self._draw_componente_shape(canvas,comp,oy_off)
        # preview ao arrastar para criar componente
        if self.comp_drawing and self.comp_drag_start and self.comp_drag_end:
            px1,py1=self._orig_to_disp(*self.comp_drag_start); px2,py2=self._orig_to_disp(*self.comp_drag_end)
            py1+=oy_off; py2+=oy_off
            cor=(80,140,255)
            cv2.rectangle(canvas,(min(px1,px2),min(py1,py2)),(max(px1,px2),max(py1,py2)),cor,1,cv2.LINE_AA)
            cv2.putText(canvas,_ascii(f"Novo {self.comp_forma_atual} - solte para criar"),(min(px1,px2)+2,min(py1,py2)-6),cv2.FONT_HERSHEY_SIMPLEX,0.26,cor,1,cv2.LINE_AA)
        self._render_right_panel(canvas,toolbar_h)
        if self.show_minimap:
            mw,mh=self.minimap_w,self.minimap_h; mx=self.left_w-mw-12; my=toolbar_h+8
            cv2.rectangle(canvas,(mx-3,my-3),(mx+mw+3,my+mh+3),THEME['shadow'],-1)
            cv2.rectangle(canvas,(mx-1,my-1),(mx+mw+1,my+mh+1), THEME['card'], -1)
            cv2.rectangle(canvas,(mx-1,my-1),(mx+mw+1,my+mh+1), THEME['border'] if not self.minimap_hover else THEME['accent'], 1 if not self.minimap_hover else 2)
            try:
                mini=cv2.resize(self.img,(mw,mh),interpolation=cv2.INTER_AREA); canvas[my:my+mh,mx:mx+mw]=mini
                vx0=int((-self.pan_x)/(self.w0*self.base_scale*self.zoom)*mw); vy0=int((-self.pan_y)/(self.h0*self.base_scale*self.zoom)*mh)
                vx1=int(vx0 + (self._canvas_w())/(self.w0*self.base_scale*self.zoom)*mw); vy1=int(vy0 + (self.view_h-40-oy_off)/(self.h0*self.base_scale*self.zoom)*mh)
                vx0=max(0,min(mw,vx0)); vy0=max(0,min(mh,vy0)); vx1=max(0,min(mw,vx1)); vy1=max(0,min(mh,vy1))
                cv2.rectangle(canvas,(mx+vx0,my+vy0),(mx+vx1,my+vy1), (0,255,255),1)
                cv2.putText(canvas,"MINI [V]",(mx+4,my+12),cv2.FONT_HERSHEY_SIMPLEX,0.30,(255,255,255),1,cv2.LINE_AA)
            except: pass
        # ---------- controles de zoom flutuantes (estilo visualizador de fotos) ----------
        zw,zh=184,34
        zx=max(8,self.left_w-zw-14); zy=self.view_h-40-zh-10
        cv2.rectangle(canvas,(zx+2,zy+3),(zx+zw+2,zy+zh+3),THEME['shadow'],-1)
        draw_rounded_rect(canvas,zx,zy,zw,zh,10,THEME['card'],-1)
        draw_rounded_rect(canvas,zx,zy,zw,zh,10,(0,0,0),1,THEME['border'])
        self.zoom_btns=[]
        for key,bx,by,bw,bh,lab in (('out',zx+4,zy+4,34,26,'-'),('fit',zx+42,zy+4,100,26,f"{int(round(self.zoom*100))}%"),('in',zx+146,zy+4,34,26,'+')):
            if getattr(self,'_zoom_hover',None)==key: draw_rounded_rect(canvas,bx,by,bw,bh,7,(250,242,236),-1)
            (tw,th),_=cv2.getTextSize(lab,cv2.FONT_HERSHEY_SIMPLEX,0.38,1)
            cv2.putText(canvas,lab,(bx+(bw-tw)//2,by+(bh+th)//2),cv2.FONT_HERSHEY_SIMPLEX,0.38,THEME['text_main'],1,cv2.LINE_AA)
            self.zoom_btns.append((key,(bx,by,bw,bh)))
        cv2.line(canvas,(zx+40,zy+8),(zx+40,zy+zh-8),THEME['border'],1)
        cv2.line(canvas,(zx+144,zy+8),(zx+144,zy+zh-8),THEME['border'],1)
        bar_y=self.view_h-36
        cv2.rectangle(canvas,(0,bar_y),(self.view_w,self.view_h),THEME['panel_status'],-1)
        cv2.line(canvas,(0,bar_y),(self.view_w,bar_y),THEME['border'],1)
        fsb=max(0.34,0.30*self.font_scale)
        proj=f"{os.path.basename(os.path.abspath(self.out_dir))}{' *' if self.dirty else ''}"
        cv2.putText(canvas,_ascii(proj)[:34],(12,self.view_h-13),cv2.FONT_HERSHEY_SIMPLEX,fsb,THEME['accent'] if self.dirty else THEME['text_main'],1,cv2.LINE_AA)
        # chip GPU/CPU à direita
        gpu_label=gpu_lib.descricao(self.gpu_info) if self.gpu_ativo else 'CPU'
        (gw,gh),_=cv2.getTextSize(gpu_label,cv2.FONT_HERSHEY_SIMPLEX,fsb,1)
        chip_x=self.view_w-gw-30; chip_y=bar_y+7
        draw_rounded_rect(canvas,chip_x-8,chip_y,gw+16,22,7,(226,243,232) if self.gpu_ativo else THEME['field'],-1)
        draw_rounded_rect(canvas,chip_x-8,chip_y,gw+16,22,7,(0,0,0),1,(160,210,175) if self.gpu_ativo else THEME['border'])
        cv2.putText(canvas,gpu_label,(chip_x,bar_y+22),cv2.FONT_HERSHEY_SIMPLEX,fsb,(55,135,60) if self.gpu_ativo else THEME['text_dim'],1,cv2.LINE_AA)
        # estatísticas + dicas no centro
        iso_txt=f" | ISO Fam {self.filter_familia_id}" if self.filter_familia_id else ""
        med,total,pct,fal=self._progresso()
        esc=f" | {self.mm_por_px:.3f} mm/px" if self.mm_por_px>0 else ""
        meio=f"{self.view_atual.upper()} | MED {med}/{total} ({pct}%) F{fal} | Pads {len(self._visiveis)}/{len(self.pads)} | Fam {len(self.nets)} | Zoom {self.zoom:.1f}x{esc}{iso_txt} | {self.mode.upper()}"
        (mw,_),_=cv2.getTextSize(meio,cv2.FONT_HERSHEY_SIMPLEX,fsb,1)
        mx=max(12+34*8+24,int(self.view_w*0.28))
        if mx+mw>chip_x-20: meio=meio[:max(10,int((chip_x-20-mx)/8))]+"..."
        cv2.putText(canvas,_ascii(meio),(mx,self.view_h-13),cv2.FONT_HERSHEY_SIMPLEX,fsb,THEME['text_dim'],1,cv2.LINE_AA)
        if time.time()<self._flash_until and self._flash_msg:
            msg=_ascii(self._flash_msg)
            (fw,fh),_=cv2.getTextSize(msg,cv2.FONT_HERSHEY_SIMPLEX,0.55,2); fx=self._cx0()+self._canvas_w()//2-fw//2; fy=toolbar_h+40; cv2.rectangle(canvas,(fx-16,fy-25),(fx+fw+16,fy+11),THEME['shadow'],-1); draw_rounded_rect(canvas,fx-15,fy-25,fw+30,35,8,THEME['card'],-1); draw_rounded_rect(canvas,fx-15,fy-25,fw+30,35,8,(0,0,0),2,self._flash_cor); cv2.putText(canvas,msg,(fx,fy),cv2.FONT_HERSHEY_SIMPLEX,0.55,_tinta(self._flash_cor),2,cv2.LINE_AA)
        # TOOLTIP (com pré-visualização para abas de visão)
        if self.tooltip_shown and self.tooltip_title:
            preview=None
            if self.tooltip_target and self.tooltip_target.startswith('view_'):
                preview=self._thumb_view(self.tooltip_target.replace('view_',''))
            line_h=14; title_h=20; box_w=320
            pw=ph=0
            if preview is not None:
                pw=min(preview.shape[1],box_w-20); ph=min(preview.shape[0],180)
            box_h=title_h + ((ph+16) if ph else 0) + len(self.tooltip_lines)*line_h + 20
            bx,by=self._get_tooltip_position(self.mouse_x, self.mouse_y, box_w, box_h)
            cv2.rectangle(canvas,(bx+2,by+3),(bx+box_w+2,by+box_h+3),THEME['shadow'],-1)
            draw_rounded_rect(canvas,bx,by,box_w,box_h,8,THEME['card'],-1); draw_rounded_rect(canvas,bx,by,box_w,box_h,8,(0,0,0),1,THEME['accent'])
            cv2.rectangle(canvas,(bx+1,by+1),(bx+box_w-1,by+title_h+4),THEME['field'],-1)
            cv2.putText(canvas,_ascii(self.tooltip_title)[:42],(bx+8,by+14),cv2.FONT_HERSHEY_SIMPLEX,0.36,THEME['accent'],1,cv2.LINE_AA)
            y_text=by+title_h+14
            if preview is not None and pw>0 and ph>0:
                thumb=cv2.resize(preview,(pw,ph),interpolation=cv2.INTER_AREA)
                px,py=bx+10,by+title_h+6
                canvas[py:py+ph,px:px+pw]=thumb
                cv2.rectangle(canvas,(px-1,py-1),(px+pw+1,py+ph+1),THEME['border'],1)
                y_text=py+ph+16
            for line in self.tooltip_lines[:12]:
                cv2.putText(canvas,_ascii(line)[:52],(bx+8,y_text),cv2.FONT_HERSHEY_SIMPLEX,0.28,THEME['text_dim'],1,cv2.LINE_AA); y_text+=line_h
        # INLINE INPUT - agora na posição do campo
        if self.inline_input_active:
            if self.inline_input_rect:
                rx,ry,rw,rh=self.inline_input_rect
                ix=rx; iy=ry+rh+4
                # se sair da tela, coloca acima
                if iy+30 > self.view_h-40: iy=ry-34
                bx,by=ix,iy; bw=rw; bh=30
                draw_rounded_rect(canvas,bx,by,bw,bh,6,THEME['card'],-1); draw_rounded_rect(canvas,bx,by,bw,bh,6,(0,0,0),2,THEME['accent'])
                cursor="|" if (self.cursor_blink//15)%2==0 else " "; txt=self.inline_input_buffer+cursor
                cv2.putText(canvas,txt[:36],(bx+8,by+19),cv2.FONT_HERSHEY_SIMPLEX,0.38,THEME['text_main'],1,cv2.LINE_AA)
            else:
                # fallback antigo
                x0=self.left_w+14; draw_rounded_rect(canvas,x0,self.view_h-70,self.right_w-30,28,8,THEME['card'],-1); draw_rounded_rect(canvas,x0,self.view_h-70,self.right_w-30,28,8,(0,0,0),1,THEME['accent'])
                cursor="|" if (self.cursor_blink//15)%2==0 else " "; txt=self.inline_input_buffer+cursor
                cv2.putText(canvas,txt[-34:],(x0+8,self.view_h-52),cv2.FONT_HERSHEY_SIMPLEX,0.38,THEME['text_main'],1,cv2.LINE_AA)
        if self.regua_modo:
            hint_r="REGUA: clique 2 pontos"+(f" | {self.mm_por_px:.3f} mm/px" if self.mm_por_px>0 else " | informe a medida em mm")
            cv2.putText(canvas,_ascii(hint_r),(12,self.view_h-52),cv2.FONT_HERSHEY_SIMPLEX,0.30,THEME['accent'],1,cv2.LINE_AA)
            if self.regua_pts:
                ax,ay=self.regua_pts[-1]
                cv2.line(canvas,(ax,ay),(self.mouse_x,self.mouse_y),(0,255,255),1)
                cv2.circle(canvas,(ax,ay),4,(0,255,255),-1)
                if self.mm_por_px>0:
                    d=((self.mouse_x-ax)**2+(self.mouse_y-ay)**2)**0.5*self.mm_por_px
                    cv2.putText(canvas,f"{d:.2f} mm",(self.mouse_x+8,self.mouse_y-8),cv2.FONT_HERSHEY_SIMPLEX,0.32,(0,255,255),1)
        self._draw_paleta_cmd(canvas,oy_off)
        # ---------- MIRA DE PRECISAO ----------
        if self.mostrar_mira and self._cx0()<=self.mouse_x<self.left_w and oy_off<=self.mouse_y<self.view_h-40 and not self.paleta_cmd.get('active'):
            mx,my=self.mouse_x,self.mouse_y
            modo_marq=self.mode in ('anotacao','pino','gnd')
            cor=(0,220,120) if self.mode=='gnd' else ((0,200,255) if self.mode in ('anotacao','pino') else (185,195,210))
            gap=5; arm=16 if modo_marq else 9
            for x1,y1,x2,y2 in ((mx-arm,my,mx-gap,my),(mx+gap,my,mx+arm,my),(mx,my-arm,mx,my-gap),(mx,my+gap,mx,my+arm)):
                cv2.line(canvas,(x1,y1),(x2,y2),cor,1,cv2.LINE_AA)
            cv2.circle(canvas,(mx,my),2,cor,-1,cv2.LINE_AA)
            if modo_marq:
                cv2.circle(canvas,(mx,my),arm+2,cor,1,cv2.LINE_AA)
                rot={'anotacao':'ANOTAR','pino':'NOMEAR PINO','gnd':'MARCAR GND'}.get(self.mode,'')
                if rot:
                    (tw,th),_=cv2.getTextSize(rot,cv2.FONT_HERSHEY_SIMPLEX,0.28,1)
                    tx=min(self.left_w-tw-14,mx+18); ty=max(oy_off+th+8,my-18)
                    draw_rounded_rect(canvas,tx-5,ty-th-4,tw+10,th+10,4,(14,18,22),-1)
                    draw_rounded_rect(canvas,tx-5,ty-th-4,tw+10,th+10,4,(0,0,0),1,cor)
                    cv2.putText(canvas,rot,(tx,ty),cv2.FONT_HERSHEY_SIMPLEX,0.28,cor,1,cv2.LINE_AA)
        # ---------- MENUS CONTEXTUAIS (por cima de tudo) ----------
        for menu in (self.context_menu_pad,self.context_menu_comp,self.context_menu_familia,self.context_menu_anot):
            menu.draw(canvas)
        return canvas
    def _draw_inline_box(self,canvas,x,y,text):
        cursor="|" if (self.cursor_blink//15)%2==0 else " "; full=text+cursor; visible=full[-34:]
        draw_rounded_rect(canvas,x,y,self.right_w-30,28,8,THEME['card'],-1); draw_rounded_rect(canvas,x,y,self.right_w-30,28,8,(0,0,0),2,THEME['accent']); cv2.putText(canvas,visible,(x+8,y+18),cv2.FONT_HERSHEY_SIMPLEX,0.38,THEME['text_main'],1,cv2.LINE_AA)
    def _draw_panel_section(self,canvas,x,y,w,texto,cor):
        cv2.line(canvas,(x,y-14),(x+w,y-14),THEME['border'],1)
        cv2.putText(canvas,_ascii(texto),(x,y),cv2.FONT_HERSHEY_SIMPLEX,0.30,_tinta(cor,0.58),1,cv2.LINE_AA)
    def _badge(self,canvas,x,y,texto,cor,bg=None,fs=0.26,h=18,pad=7):
        texto=_ascii(texto); (tw,th),_=cv2.getTextSize(texto,cv2.FONT_HERSHEY_SIMPLEX,fs,1)
        w=tw+pad*2
        fundo=bg or tuple(min(255,int(c*0.22+225)) for c in cor)
        draw_rounded_rect(canvas,x,y,w,h,6,fundo,-1)
        cv2.putText(canvas,texto,(x+pad,y+h-5),cv2.FONT_HERSHEY_SIMPLEX,fs,_tinta(cor,0.62),1,cv2.LINE_AA)
        return w
    def _kv(self,canvas,x,y,w,k,v,cor_val=THEME['text_main'],cor_k=THEME['text_dim']):
        cv2.putText(canvas,_ascii(k),(x,y),cv2.FONT_HERSHEY_SIMPLEX,0.30,cor_k,1,cv2.LINE_AA)
        txt=_ascii(str(v) if v not in (None,'') else '-')
        (tw,_),_=cv2.getTextSize(txt,cv2.FONT_HERSHEY_SIMPLEX,0.30,1)
        cv2.putText(canvas,txt,(x+w-tw,y),cv2.FONT_HERSHEY_SIMPLEX,0.30,cor_val,1,cv2.LINE_AA)
    def _status_conta_net(self,net):
        n={'OK':0,'SUSP':0,'FALHA':0,'VAZIO':0}
        for pid in net.get('pads',[]):
            m=self.measurements.get(pid) or {}
            st=m.get('status') if isinstance(m,dict) else None
            if st in ('OK','SUSP','FALHA'): n[st]+=1
            else: n['VAZIO']+=1
        return n
    def _sync_sidebar_estado(self):
        sb=getattr(self,'sidebar',None)
        if sb is None: return
        estados={
            'toggle_gpu':self.gpu_ativo,
            'toggle_minimap':self.show_minimap,
            'toggle_ids':self.show_ids,
            'mascara':self.show_mask,
            'toggle_auto_vincular':self.auto_vincular,
            'toggle_mira':self.mostrar_mira,
            'camadas':self.right_mode=='camadas',
            'modo_anot':self.mode=='anotacao',
            'modo_pino':self.mode=='pino',
            'modo_gnd':self.mode=='gnd',
            'modo_detector':self.detector_modo=='smart',
            'view_frente':self.view_atual=='frente',
            'view_verso':self.view_atual=='verso',
            'view_conector':self.view_atual=='conector',
        }
        for acao,ativo in estados.items(): sb.set_active(acao,ativo)
        for b in sb.buttons:
            if b.action=='modo_detector': b.label='Smart (auto)' if self.detector_modo=='smart' else 'Classico'
            elif b.action=='toggle_mira': b.label='Mira ON' if self.mostrar_mira else 'Mira OFF'
            elif b.action=='toggle_gpu': b.label='GPU ON' if self.gpu_ativo else 'GPU OFF'

    def _render_right_panel(self,canvas,toolbar_h):
        # v11.5: painel comeca abaixo das abas (barra superior continua visivel)
        x0=self.left_w; cv2.rectangle(canvas,(x0,60),(self.view_w,self.view_h),THEME['panel_inspector'],-1); cv2.line(canvas,(x0,60),(x0,self.view_h),THEME['border'],1)
        toolbar_h=self._panel_top()
        if self.right_mode=='menu':
            self.sidebar.layout(x0,60,self.right_w,self.view_h-36-60,self.font_scale)
            self._sync_sidebar_estado()
            self.sidebar.draw(canvas,now=time.time())
            return
        if self._confirm_action=='reset' and self.inline_input_active and self.inline_input_field=='reset_confirm':
            draw_rounded_rect(canvas,x0+6,toolbar_h+10,self.right_w-16,80,8,THEME['card'],-1)
            draw_rounded_rect(canvas,x0+6,toolbar_h+10,self.right_w-16,80,8,(0,0,0),2,(38,38,220))
            cv2.putText(canvas,"CONFIRMAR RESET",(x0+14,toolbar_h+30),cv2.FONT_HERSHEY_SIMPLEX,0.42,(38,38,200),1)
            cv2.putText(canvas,"Isso apaga TODOS os pads!",(x0+14,toolbar_h+48),cv2.FONT_HERSHEY_SIMPLEX,0.32,THEME['text_dim'],1)
            if self.inline_input_rect is None: self._draw_inline_box(canvas,x0+10,toolbar_h+56,f"Digite SIM: {self.inline_input_buffer}")
            return
        if self.right_mode=='calib':
            cv2.putText(canvas,_ascii(f"CALIBRAGEM - {self.view_atual.upper()}"),(x0+10,toolbar_h+22),cv2.FONT_HERSHEY_DUPLEX,0.42,THEME['text_main'],1)
            if self.preset_dropdown is None:
                self.preset_dropdown=DropdownPreset(x0+10, toolbar_h+32, self.right_w-24, 36)
                self.preset_dropdown.selected_key=self.preset_selected_key
            else: self.preset_dropdown.rect=(x0+10, toolbar_h+32, self.right_w-24, 36)
            self.preset_dropdown.draw(canvas)
            offset_y= 50 + (len(PRESETS_BANCADA_V84)*44+10 if self.preset_dropdown.expanded else 0)
            for s in self.sliders:
                s.y=toolbar_h+32+offset_y + (self.sliders.index(s)*50)
                s.draw(canvas,x0+10,self.font_scale)
            y_txt=toolbar_h+32+offset_y+ 7*50 +10
            cv2.putText(canvas,f"Preset: {PRESETS_BANCADA_V84[self.preset_selected_key]['label']} | Tooltip 1s ON",(x0+10,y_txt),cv2.FONT_HERSHEY_SIMPLEX,0.30,THEME['accent'],1)
            escala_txt=(f"Escala: {self.mm_por_px:.4f} mm/px" if self.mm_por_px>0 else "Escala: nao calibrada — [R] regua 2 pontos")
            cv2.putText(canvas,_ascii(escala_txt),(x0+10,y_txt+18),cv2.FONT_HERSHEY_SIMPLEX,0.28,THEME['text_dim'],1)
            det_txt=f"Detector: {self.detector_modo.upper()} (sens {self.smart_sens:.2f}) — paleta p/ alternar"
            cv2.putText(canvas,_ascii(det_txt),(x0+10,y_txt+34),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['accent'],1)
        elif self.right_mode=='inspetor':
            if self.selected is None or self.selected>=len(self.pads):
                cv2.putText(canvas,"INSPETOR",(x0+12,toolbar_h+24),cv2.FONT_HERSHEY_DUPLEX,0.44,THEME['text_main'],1)
                draw_rounded_rect(canvas,x0+10,toolbar_h+44,self.right_w-20,80,8,THEME['card'],-1)
                draw_rounded_rect(canvas,x0+10,toolbar_h+44,self.right_w-20,80,8,(0,0,0),1,THEME['border'])
                cv2.putText(canvas,"Nenhum pad selecionado",(x0+22,toolbar_h+72),cv2.FONT_HERSHEY_SIMPLEX,0.32,THEME['text_dim'],1)
                cv2.putText(canvas,"Clique num pad da placa para",(x0+22,toolbar_h+94),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['text_dim'],1)
                cv2.putText(canvas,"ver detalhes e medir [E]",(x0+22,toolbar_h+110),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['text_dim'],1)
                med,total,pct,fal=self._progresso()
                yb=toolbar_h+140
                draw_rounded_rect(canvas,x0+10,yb,self.right_w-20,46,8,THEME['card'],-1)
                draw_rounded_rect(canvas,x0+10,yb,self.right_w-20,46,8,(0,0,0),1,THEME['border'])
                cv2.putText(canvas,"PROGRESSO",(x0+22,yb+16),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['accent'],1)
                bw=self.right_w-44; fw=int(bw*pct/100.0)
                cv2.rectangle(canvas,(x0+22,yb+22),(x0+22+bw,yb+30),(232,234,238),-1)
                cv2.rectangle(canvas,(x0+22,yb+22),(x0+22+max(0,fw),yb+30),THEME['success'],-1)
                cv2.putText(canvas,_ascii(f"{med}/{total} medidos ({pct}%) | falhas {fal}"),(x0+22,yb+42),cv2.FONT_HERSHEY_SIMPLEX,0.24,THEME['text_dim'],1)
                return
            p=self.pads[self.selected]; pid=p.get('id',0); m=self.measurements.get(pid,{}) if isinstance(self.measurements.get(pid,{}),dict) else {}
            lig=m.get('ligada',{}) if isinstance(m.get('ligada'),dict) else {}; des=m.get('desligada',{}) if isinstance(m.get('desligada'),dict) else {}
            status=m.get('status') if isinstance(m,dict) else None
            fam=self._get_familia_do_pad(pid)
            cor_st=self.CORES_STATUS.get(status,self.CORES_STATUS[None]); cor_fam=self._cor_familia(fam) if fam else (110,110,110)
            # cartao de titulo
            cy0=toolbar_h+12
            draw_rounded_rect(canvas,x0+10,cy0,self.right_w-20,58,8,THEME['card'],-1)
            draw_rounded_rect(canvas,x0+10,cy0,self.right_w-20,58,8,(0,0,0),1,THEME['border'])
            cv2.putText(canvas,f"PAD #{pid}",(x0+22,cy0+28),cv2.FONT_HERSHEY_DUPLEX,0.52,THEME['text_main'],1)
            tag="MANUAL" if p.get('manual') else "AUTO"
            self._badge(canvas,x0+self.right_w-22-(len(tag)*8+18),cy0+9,tag,(0,165,255) if p.get('manual') else (0,190,90))
            mm_txt=f"   {p.get('w',0)*self.mm_por_px:.1f}x{p.get('h',0)*self.mm_por_px:.1f} mm" if self.mm_por_px>0 else ""
            cv2.putText(canvas,_ascii(f"X {p.get('cx')}   Y {p.get('cy')}   area {p.get('area')} px{mm_txt}"),(x0+22,cy0+47),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['text_dim'],1)
            # linha de estado + familia
            y=cy0+78
            cv2.putText(canvas,"Status",(x0+14,y),cv2.FONT_HERSHEY_SIMPLEX,0.28,THEME['text_dim'],1)
            self._badge(canvas,x0+70,y-14,status or 'SEM MEDIR',cor_st)
            y+=24
            cv2.putText(canvas,"Familia",(x0+14,y),cv2.FONT_HERSHEY_SIMPLEX,0.28,THEME['text_dim'],1)
            draw_rounded_rect(canvas,x0+70,y-9,10,10,3,cor_fam,-1); draw_rounded_rect(canvas,x0+70,y-9,10,10,3,(0,0,0),1,THEME['border'])
            fam_txt=(fam.get('nome','') or f"Fam {fam['id']}") if fam else "sem familia"
            cv2.putText(canvas,_ascii(fam_txt[:20]),(x0+86,y),cv2.FONT_HERSHEY_SIMPLEX,0.30,THEME['text_main'],1)
            y+=22
            if p.get('link'):
                alvos=self._alvos_do_link(p['link'])
                cv2.putText(canvas,"Passante",(x0+14,y),cv2.FONT_HERSHEY_SIMPLEX,0.28,THEME['text_dim'],1)
                cv2.putText(canvas,_ascii(", ".join(alvos) if alvos else "sim"),(x0+80,y),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['accent'],1)
                y+=18
            # secao ligada
            self._draw_panel_section(canvas,x0+14,y,self.right_w-28,"PLACA LIGADA",(0,200,120)); y+=18
            self._kv(canvas,x0+18,y,self.right_w-40,"Tensao",(str(lig.get('tensao',''))+' V') if lig.get('tensao','') else ''); y+=18
            self._kv(canvas,x0+18,y,self.right_w-40,"Frequencia",(str(lig.get('frequencia',''))+' Hz') if lig.get('frequencia','') else ''); y+=18
            self._kv(canvas,x0+18,y,self.right_w-40,"Forma",lig.get('forma','')); y+=18
            self._kv(canvas,x0+18,y,self.right_w-40,"Obs",lig.get('obs','')); y+=24
            self._draw_panel_section(canvas,x0+14,y,self.right_w-28,"PLACA DESLIGADA",(0,170,255)); y+=18
            self._kv(canvas,x0+18,y,self.right_w-40,"Resistencia",(str(des.get('resistencia',''))+' Ohm') if des.get('resistencia','') else ''); y+=18
            self._kv(canvas,x0+18,y,self.right_w-40,"Continuidade",des.get('continuidade','')); y+=18
            self._kv(canvas,x0+18,y,self.right_w-40,"Capacitancia",(str(des.get('capacitancia',''))+' uF') if des.get('capacitancia','') else ''); y+=18
            self._kv(canvas,x0+18,y,self.right_w-40,"Diodo Vf",(str(des.get('diodo',''))+' V') if des.get('diodo','') else ''); y+=18
            self._kv(canvas,x0+18,y,self.right_w-40,"Obs",des.get('obs','')); y+=26
            draw_rounded_rect(canvas,x0+12,y-14,self.right_w-24,30,7,THEME['field'],-1)
            cv2.putText(canvas,"[E] Editar   [Enter] Abrir editor   [Del] Remover",(x0+20,y+5),cv2.FONT_HERSHEY_SIMPLEX,0.24,THEME['accent'],1)
        elif self.right_mode=='edit':
            if self.selected is None or self.selected>=len(self.pads): self.right_mode='inspetor'; return
            titulo,meta=self.edit_header
            cv2.putText(canvas,_ascii(titulo),(x0+12,toolbar_h+24),cv2.FONT_HERSHEY_DUPLEX,0.42,THEME['text_main'],1)
            cv2.putText(canvas,_ascii(meta),(x0+12,toolbar_h+42),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['text_dim'],1)
            for label,yy,cor in self.edit_sections: self._draw_panel_section(canvas,x0+12,yy,self.right_w-26,label,cor)
            for b in self.edit_status_btns: b.draw(canvas,self.font_scale)
            lig_on=(self.estado_placa=='ligada')
            for i,s in enumerate(self.edit_sliders): enabled=lig_on if i<2 else (not lig_on); s.draw(canvas,x0+10,self.font_scale,enabled=enabled)
            for b in self.edit_field_btns:
                x,y,w,h=b.rect
                bg=(250,242,236) if b.hover else THEME['card']
                draw_rounded_rect(canvas,x,y,w,h,6,bg,-1); draw_rounded_rect(canvas,x,y,w,h,6,(0,0,0),1,THEME['accent'] if b.hover else THEME['border'])
                cv2.putText(canvas,_ascii(b.label),(x+8,y+18),cv2.FONT_HERSHEY_SIMPLEX,0.30,THEME['text_main'],1,cv2.LINE_AA)
            for b in self.edit_action_btns: b.draw(canvas,self.font_scale)
            cv2.putText(canvas,"Duplo clique no slider p/ digitar (10k, 4.7u, 3V3)",(x0+12,self.edit_action_btns[0].rect[1]+46),cv2.FONT_HERSHEY_SIMPLEX,0.22,THEME['text_dim'],1)
        elif self.right_mode=='componentes':
            # v10.1 - painel componentes com scroll
            if self.comp_selected is not None and self.comp_edit_field_btns:
                comp=next((c for c in self.componentes if c['id']==self.comp_selected),None)
                if comp is None:
                    self.comp_selected=None
                else:
                    x0=self.left_w; toolbar_h=self._toolbar_h()
                    titulo,meta=self.comp_edit_header
                    cv2.putText(canvas,_ascii(titulo),(x0+10,76),cv2.FONT_HERSHEY_DUPLEX,0.38,THEME['text_main'],1)
                    cv2.putText(canvas,_ascii(meta),(x0+10,94),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['text_dim'],1)
                    sug_tipo,sug_desc,conf,sug_val=self._sugerir_tipo_componente(comp)
                    if sug_tipo:
                        nome_sug=COMPONENTES_TIPOS.get(sug_tipo,{}).get('nome',sug_tipo)
                        sug_txt=f"Sugestao: {nome_sug} {conf}% | {sug_desc.split(' + ')[0]}"
                    else:
                        sug_txt="Sugestao: preencha marcacao/valor ou use Reconhecer"
                    cv2.putText(canvas,_ascii(sug_txt)[:48],(x0+10,110),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['accent'] if sug_tipo else THEME['text_dim'],1)
                    for label,yy,cor in self.comp_edit_sections: self._draw_panel_section(canvas,x0+10,yy,self.right_w-24,label,cor)
                    for b in self.comp_edit_field_btns:
                        x,y,w,h=b.rect; bg=(250,242,236) if b.hover else THEME['card']
                        draw_rounded_rect(canvas,x,y,w,h,6,bg,-1); draw_rounded_rect(canvas,x,y,w,h,6,(0,0,0),1,THEME['accent'] if b.hover else THEME['border'])
                        cv2.putText(canvas,_ascii(b.label),(x+8,y+18),cv2.FONT_HERSHEY_SIMPLEX,0.28,THEME['text_main'],1,cv2.LINE_AA)
                    for b in self.comp_edit_tipo_btns: b.draw(canvas,self.font_scale)
                    for b in self.comp_edit_action_btns: b.draw(canvas,self.font_scale)
                    if comp.get('tipo')=='conector':
                        lin=self._pinagem_conector(comp)[:4]
                        resumo=' | '.join(f"{l['pino']}->P{l['pad']}" for l in lin) or 'sem pads'
                        cv2.putText(canvas,_ascii(f"PINAGEM: {resumo}"),(x0+10,self.comp_edit_actions_y+66),cv2.FONT_HERSHEY_SIMPLEX,0.22,THEME['accent'],1)
                    return
            x0=self.left_w; toolbar_h=self._toolbar_h()
            cv2.putText(canvas,"COMPONENTES",(x0+12,toolbar_h+22),cv2.FONT_HERSHEY_DUPLEX,0.44,THEME['text_main'],1)
            cv2.putText(canvas,_ascii(f"{len(self.componentes)} componentes | [G] desenhar | [C] forma"),(x0+12,toolbar_h+38),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['text_dim'],1)
            y=toolbar_h+58
            vis_comps=self.componentes[self.comp_scroll:self.comp_scroll+9]
            for i,comp in enumerate(vis_comps):
                sel=(self.comp_selected==comp['id'])
                bg=THEME['accent_soft'] if sel else (THEME['card'] if i%2==0 else THEME['card_alt'])
                cv2.rectangle(canvas,(x0+6,y),(self.view_w-8,y+28),bg,-1)
                if sel: cv2.rectangle(canvas,(x0+6,y),(x0+9,y+28),THEME['accent'],-1)
                cor=tuple(comp.get('cor',(80,140,255)))
                tipo=COMPONENTES_TIPOS.get(comp.get('tipo'),{})
                simbolo=comp.get('simbolo') or tipo.get('simbolo','?')
                draw_rounded_rect(canvas,x0+14,y+6,18,16,4,THEME['card'],-1)
                draw_rounded_rect(canvas,x0+14,y+6,18,16,4,(0,0,0),1,cor)
                (tw,_),_=cv2.getTextSize(simbolo,cv2.FONT_HERSHEY_SIMPLEX,0.30,1)
                cv2.putText(canvas,simbolo,(x0+23-tw//2,y+18),cv2.FONT_HERSHEY_SIMPLEX,0.30,_tinta(cor,0.75),1,cv2.LINE_AA)
                cv2.putText(canvas,_ascii(comp.get('nome','')[:10]),(x0+38,y+13),cv2.FONT_HERSHEY_SIMPLEX,0.30,THEME['text_main'],1)
                cv2.putText(canvas,_ascii(f"{(tipo.get('nome','') or comp.get('tipo',''))[:9]} | {len(comp.get('pads',[]))}p" + (f" | {str(comp.get('marcacao'))[:7]}" if comp.get('marcacao') else "")),(x0+38,y+25),cv2.FONT_HERSHEY_SIMPLEX,0.22,THEME['text_dim'],1)
                if comp.get('datasheet'):
                    cv2.putText(canvas,"DS",(x0+self.right_w-96,y+13),cv2.FONT_HERSHEY_SIMPLEX,0.24,THEME['accent'],1)
                valor=str(comp.get('valor','') or '')
                if valor:
                    valor=valor[:11]
                    (vw,_),_=cv2.getTextSize(valor,cv2.FONT_HERSHEY_SIMPLEX,0.26,1)
                    cv2.putText(canvas,_ascii(valor),(self.view_w-16-vw,y+18),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['text_main'],1)
                y+=30
            if not self.componentes:
                cv2.putText(canvas,"Nenhum componente ainda.",(x0+14,toolbar_h+86),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['text_dim'],1)
                cv2.putText(canvas,"Use [G] e arraste na placa para desenhar.",(x0+14,toolbar_h+102),cv2.FONT_HERSHEY_SIMPLEX,0.24,THEME['text_dim'],1)
            by=self.view_h-92
            self.familia_botoes=[]
            self.familia_botoes.append(ButtonV5(x0+10,by,68,24,"Subir",'comp_up'))
            self.familia_botoes.append(ButtonV5(x0+84,by,68,24,"Descer",'comp_down'))
            self.familia_botoes.append(ButtonV5(x0+158,by,68,24,"Nova",'comp_nova','action'))
            self.familia_botoes.append(ButtonV5(x0+232,by,68,24,"Voltar",'fam_voltar','success'))
            for b in self.familia_botoes: b.draw(canvas,self.font_scale)
            return
        elif self.right_mode=='familias':
            x0=self.left_w; toolbar_h=self._toolbar_h()
            if self.paleta_dropdown is None:
                self.paleta_dropdown=DropdownPaleta(x0+10, toolbar_h+44, self.right_w-20, 24)
            visiveis=9
            vis_nets=self.nets[self.familia_scroll:self.familia_scroll+visiveis]
            self.familia_botoes=[]
            for i,net in enumerate(vis_nets):
                self.familia_botoes.append(ButtonV5(x0+6,toolbar_h+96+i*30,self.right_w-16,28,"",f"fam_sel_{net['id']}",kind='default'))
            by_base=self.view_h-160
            self.familia_botoes.append(ButtonV5(x0+10,by_base,120,22,"Subir",'fam_up'))
            self.familia_botoes.append(ButtonV5(x0+136,by_base,120,22,"Descer",'fam_down'))
            self.familia_botoes.append(ButtonV5(x0+10,by_base+28,120,22,"Nova cor",'fam_nova_cor','action'))
            self.familia_botoes.append(ButtonV5(x0+136,by_base+28,120,22,"Renomear",'fam_rename','toggle'))
            self.familia_botoes.append(ButtonV5(x0+10,by_base+56,self.right_w-20,26,"VOLTAR [ESC]",'fam_voltar','success'))
            # cabeçalho
            cv2.putText(canvas,"FAMILIAS",(x0+12,toolbar_h+22),cv2.FONT_HERSHEY_DUPLEX,0.44,THEME['text_main'],1)
            total_pads=sum(len(n['pads']) for n in self.nets)
            faixa=f"{self.familia_scroll+1 if self.nets else 0}-{self.familia_scroll+len(vis_nets)} de {len(self.nets)}"
            med_d,total_d,pct_d,_=self._progresso()
            cv2.putText(canvas,_ascii(f"{len(self.nets)} nets | {total_pads} pads | {faixa} | {pct_d}% medidos"),(x0+12,toolbar_h+38),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['text_dim'],1)
            # seletor de cor (barra)
            if self.familia_selected is not None:
                net_sel=next((n for n in self.nets if n['id']==self.familia_selected),None)
                if net_sel:
                    cor_atual=tuple(net_sel.get('cor',PALETA_32[0][1]))
                    for idx,(_,c) in enumerate(PALETA_32):
                        if tuple(c)==cor_atual:
                            self.paleta_dropdown.selected_idx=idx
                            break
                    self.paleta_dropdown.rect=(x0+10, toolbar_h+46, self.right_w-20, 24)
                    self.paleta_dropdown.draw(canvas)
            # linhas com contadores de status
            y=toolbar_h+96
            for i,net in enumerate(vis_nets):
                btn=self.familia_botoes[i]; hover=btn.hover
                sel=(self.familia_selected==net['id'])
                bg=THEME['accent_soft'] if sel else (THEME['card'] if i%2==0 else THEME['card_alt'])
                if hover and not sel: bg=(250,242,236)
                cv2.rectangle(canvas,(x0+6,y),(self.view_w-8,y+28),bg,-1)
                if sel: cv2.rectangle(canvas,(x0+6,y),(x0+9,y+28),THEME['accent'],-1)
                cor=self._cor_familia(net)
                draw_rounded_rect(canvas,x0+16,y+9,10,10,3,cor,-1); draw_rounded_rect(canvas,x0+16,y+9,10,10,3,(0,0,0),1,THEME['border'])
                nome=net.get('nome','') or f"Fam {net['id']}"
                cv2.putText(canvas,_ascii(f"#{net['id']:02d}"),(x0+34,y+18),cv2.FONT_HERSHEY_SIMPLEX,0.24,THEME['text_dim'],1)
                cv2.putText(canvas,_ascii(nome[:12]),(x0+62,y+16),cv2.FONT_HERSHEY_SIMPLEX,0.30,THEME['text_main'],1)
                nst=self._status_conta_net(net)
                bx=self.view_w-46
                for sigla,chave,corst in (('F','FALHA',(0,0,220)),('S','SUSP',(0,200,255)),('OK','OK',(0,190,90))):
                    qtd=nst.get(chave,0)
                    if qtd==0: continue
                    txt=f"{sigla}{qtd}"; (tw,_),_=cv2.getTextSize(txt,cv2.FONT_HERSHEY_SIMPLEX,0.22,1)
                    bx-=tw+10
                    cv2.putText(canvas,txt,(bx,y+24),cv2.FONT_HERSHEY_SIMPLEX,0.22,_tinta(corst,0.72),1,cv2.LINE_AA)
                cv2.putText(canvas,f"{len(net['pads'])}p",(self.view_w-44,y+13),cv2.FONT_HERSHEY_SIMPLEX,0.24,THEME['text_dim'],1)
                y+=30
            dica="Clique numa familia para trocar cor/renomear" if self.nets else "Sem familias - conecte pads na aba ANOTAR [C]"
            cv2.putText(canvas,_ascii(dica),(x0+12,toolbar_h+96+len(vis_nets)*30+16),cv2.FONT_HERSHEY_SIMPLEX,0.24,THEME['text_dim'],1)
            if not (self.paleta_dropdown and self.paleta_dropdown.expanded):
                for b in self.familia_botoes[len(vis_nets):]: b.draw(canvas,self.font_scale)
        elif self.right_mode=='camadas':
            x0=self.left_w; tb=self._toolbar_h()
            cv2.putText(canvas,"CAMADAS",(x0+12,tb+22),cv2.FONT_HERSHEY_DUPLEX,0.44,THEME['text_main'],1)
            cv2.putText(canvas,"Clique para ligar/desligar a visibilidade",(x0+12,tb+38),cv2.FONT_HERSHEY_SIMPLEX,0.24,THEME['text_dim'],1)
            itens=[('pads','Pads (contornos)'),('ids','IDs dos pads'),('familias','Cores das familias'),('componentes','Componentes'),('linhas','Linhas de conexao'),('mascara','Mascara de deteccao'),('pinos','Pinos e GND'),('anotacoes','Anotacoes')]
            y=tb+58; self.familia_botoes=[]
            for chave,rotulo in itens:
                b=ButtonV5(x0+10,y,self.right_w-20,26,f"{'[X]' if self.layers.get(chave,True) else '[  ]'} {rotulo}",f"layer_{chave}",'filter')
                b.ativo=self.layers.get(chave,True)
                self.familia_botoes.append(b); b.draw(canvas,self.font_scale); y+=32
            b=ButtonV5(x0+10,self.view_h-84,self.right_w-20,26,"VOLTAR [ESC]",'fam_voltar','success'); b.draw(canvas,self.font_scale)

    def iniciar(self):
        cv2.namedWindow(self.JANELA,cv2.WINDOW_NORMAL); cv2.resizeWindow(self.JANELA,self.view_w,self.view_h); cv2.moveWindow(self.JANELA,10,10); cv2.setMouseCallback(self.JANELA,self._on_mouse); self._rebuild_toolbar(); self.botoes_tab[0].ativo=True
        self._oferecer_recuperacao()
        print(f"\nOK v11.2 - {self.view_w}x{self.view_h} Backend:{self.backend_info} | Visao:{self.view_atual.upper()} | GPU:{'ON' if self.gpu_ativo else 'OFF'} | Ctrl+K comandos | feche pela janela (X)")
        self.plugin_mgr.on_app_start(self)
        try:
            while True:
                now=time.time()
                if now-self.autosave_t>60:
                    self._autosave(); self.autosave_t=now
                self._update_tooltip(self.mouse_x, self.mouse_y, now)
                canvas=self._render(); cv2.imshow(self.JANELA,canvas)
                if cv2.getWindowProperty(self.JANELA,cv2.WND_PROP_VISIBLE)<1: break
                try: key_raw=cv2.waitKeyEx(30)
                except AttributeError: key_raw=cv2.waitKey(30)
                if key_raw==-1: continue
                key=key_raw&0xFF
                ctrl_z=(key_raw==26) or (key==26); ctrl_y=(key_raw==25) or (key==25)
                if self.paleta_cmd.get('active'):
                    itens=self.paleta_cmd.get('itens') or []
                    if key==27: self.paleta_cmd['active']=False
                    elif key in (13,10): self._executar_paleta()
                    elif key_raw in (2490368,2424832): self.paleta_cmd['sel']=max(0,self.paleta_cmd.get('sel',0)-1)
                    elif key_raw in (2621440,2555904): self.paleta_cmd['sel']=min(len(itens)-1,self.paleta_cmd.get('sel',0)+1)
                    elif key in (8,127): self.paleta_cmd['query']=(self.paleta_cmd.get('query') or '')[:-1]; self._atualizar_paleta()
                    elif 32<=key<=126:
                        self.paleta_cmd['query']=(self.paleta_cmd.get('query') or '')+chr(key); self._atualizar_paleta()
                    continue
                if key==11:
                    self._abrir_paleta(); continue
                if key==14:
                    self._proximo_sem_medir(salvar=True); continue
                if key==12:
                    self._on_button('camadas'); continue
                if self.inline_input_active:
                    if key==13:
                        if self._confirm_action=='reset':
                            if self.inline_input_buffer.strip().upper()=='SIM':
                                self._confirm_action=None; self.inline_input_active=False; self.inline_input_field=''; self.inline_input_buffer=''; self._push_undo(); self._detectar(False)
                            else: self._confirm_action=None; self._cancel_inline_input()
                        else: self._confirm_inline_input()
                    elif key==27: self._confirm_action=None; self._cancel_inline_input()
                    elif key==8 or key==127: self.inline_input_buffer=self.inline_input_buffer[:-1]
                    elif 32<=key<=255:
                        if len(self.inline_input_buffer)<80: self.inline_input_buffer+=chr(key)
                    continue
                if key==255: continue
                if key==27:
                    if self.tooltip_shown: self.tooltip_shown=False; self.tooltip_target=None; continue
                    if any(m.visible for m in (self.context_menu_pad,self.context_menu_comp,self.context_menu_familia,self.context_menu_anot)):
                        for m in (self.context_menu_pad,self.context_menu_comp,self.context_menu_familia,self.context_menu_anot): m.hide()
                        continue
                    if self.preset_dropdown and self.preset_dropdown.expanded: self.preset_dropdown.expanded=False; continue
                    if self.anot_selected is not None: self.anot_selected=None; continue
                    if self.mode in ('anotacao','pino','gnd'): self._ir_para_navegar(); continue
                    if self.search_id is not None and not self.inline_input_active: self.search_id=None; self.filter_familia_id=None; self._invalidar_cache_visiveis()
                    self._ir_para_navegar(); continue
                if ctrl_z or key==ord('['): self._undo(); continue
                elif ctrl_y or key==ord(']'): self._redo(); continue
                elif key==ord('o') or key==ord('O'): self._abrir_imagem_dialog()
                elif key==ord('l') or key==ord('L'): self._abrir_projeto_dialog()
                elif key==ord('k') or key==ord('K'): self._abrir_pasta_saida()
                elif key==ord('g') or key==ord('G'):
                    if self.tab=='anotar': self._on_button('modo_comp')
                elif key==ord('v') or key==ord('V'): self.show_minimap=not self.show_minimap
                elif key==ord('y') or key==ord('Y'): self._on_button('modo_anot')
                elif key==ord('i') or key==ord('I'): self._on_button('modo_pino')
                elif key==ord('u') or key==ord('U'): self._on_button('modo_gnd')
                elif key==ord('n') or key==ord('N'): self._on_button('modo_nav')
                elif key==ord('a') or key==ord('A'): self._on_button('modo_add')
                elif key==ord('m') or key==ord('M'):
                    if self.tab=='calibrar': self._on_button('modo_move')
                    else: self._on_button('modo_med')
                elif key==ord('c') or key==ord('C'):
                    if self.tab=='anotar':
                        if self.mode=='componente':
                            formas=[f[0] for f in FORMAS_COMPONENTE]
                            idx=formas.index(self.comp_forma_atual) if self.comp_forma_atual in formas else 0
                            self.comp_forma_atual=formas[(idx+1)%len(formas)]
                            self._flash(f"Forma: {self.comp_forma_atual}", cor=(0,200,255))
                        else:
                            self._on_button('modo_con')
                elif key==ord('x') or key==ord('X'):
                    if self.tab=='anotar': self._on_button('modo_descon')
                elif key==ord('e') or key==ord('E'):
                    if self.tab=='anotar' and self.selected is not None: self._iniciar_edicao(self.selected)
                elif key==ord('d') or key==ord('D'):
                    if self.tab=='calibrar': self._push_undo(); self._detectar(True)
                    else: self._on_button('comp_datasheet')
                elif key==ord('h') or key==ord('H'): self.show_mask=not self.show_mask
                elif key==ord('s') or key==ord('S'): self._salvar_tudo()
                elif key==ord('p') or key==ord('P'):
                    try: ts=time.strftime("%Y%m%d_%H%M%S"); path=f"{self.out_dir}/screenshot_{ts}.png"; imwrite_u(path,canvas); self._flash(f"Snap: {os.path.basename(path)}",cor=(0,200,0))
                    except Exception as e: self._flash(f"Snap falhou: {e}",cor=(255,0,0))
                elif key==ord('f') or key==ord('F'): self._on_button('buscar')
                elif key==ord('7'): self._gerar_relatorio()
                elif key==ord('8'): self._capturar_camera()
                elif key==ord('9'): self._comparar_ouro()
                elif key==ord('r') or key==ord('R'): self._iniciar_regua()
                elif key==ord('0'): self._reset_zoom_fit()
                elif key==ord('+') or key==ord('=') or key==43: # + zoom in
                    self.zoom=min(20.0,self.zoom*1.2); self._invalidar_cache_visiveis()
                elif key==ord('-') or key==95 or key==45: # - zoom out
                    self.zoom=max(0.1,self.zoom/1.2); self._invalidar_cache_visiveis()
                elif key==ord('w') or key==ord('W'): # W também zoom in (alternativa)
                    self.zoom=min(20.0,self.zoom*1.2); self._invalidar_cache_visiveis()
                elif (key in (8,127)) or (key_raw in (3014656, 0x2E0000, 65535)):
                    # FIX v11.4: DEL apenas de verdade. key==0 (byte baixo de teclas
                    # estendidas no Windows: setas/Home/F1..F12) e 83 ('S' de Shift+S)
                    # NAO podem apagar pad/anotacao selecionados.
                    if self.anot_selected is not None:
                        self._remover_anotacao()
                    elif self.selected is not None and self.selected<len(self.pads):
                        self._remover_pad(self.selected)
                    elif self.comp_selected is not None:
                        self._remover_componente(self.comp_selected)
                elif key==ord('\t'): self._trocar_aba('anotar' if self.tab=='calibrar' else 'calibrar')
                elif key==ord('1'): self._trocar_aba('calibrar')
                elif key==ord('2'): self._trocar_aba('anotar')
                elif key==ord('3'): self._trocar_view('frente')
                elif key==ord('4'): self._trocar_view('verso')
                elif key==ord('5'): self._trocar_view('conector')
                elif key==ord('6'): self._definir_imagem_view()
                elif key==ord('j') or key==ord('J'): self._alternar_gpu()
                elif key==ord(','): self._ciclar_view(-1)
                elif key==ord('.'): self._ciclar_view(1)
                elif key==ord('t') or key==ord('T'):
                    self.show_ids=not self.show_ids; self._flash(f"IDs {'ON' if self.show_ids else 'OFF'} (zoom 1.2x mostra todos)",cor=(0,200,255),dur=1.8)
                elif key in (13,10):
                    if self.tab=='anotar' and self.selected is not None and self.right_mode!='edit' and self.selected<len(self.pads): self._iniciar_edicao(self.selected)
                    elif self.right_mode=='edit': self._salvar_edicao()
        finally:
            self.plugin_mgr.on_app_exit(self)
            cv2.destroyAllWindows()
            try:
                if getattr(self,'_sessao_ruim',False):
                    print("Sessao corrompida no inicio: save final BLOQUEADO (projeto original preservado)")
                else: self._salvar_sessao(); self._salvar_csvs(); salvar_png(self.pads,self.out_dir,self.img)
            except Exception as e: print(f"Erro final: {e}")
            try: self._salvar_prefs(); prefs_lib.limpar_autosave()
            except Exception: pass
            print("\nOK - Encerrado v11.2 - Projeto salvo compativel")


