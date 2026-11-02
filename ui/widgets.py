import cv2
import numpy as np
import unicodedata
from .theme import THEME
# Importa PALETA_32 para dropdown
from core.presets import PALETA_32


def _ascii(t):
    if not isinstance(t, str):
        return t
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode('ascii')
    return t.replace('—', '-').replace('·', '|').replace('…', '...')

def draw_rounded_rect(img,x,y,w,h,r,color,thickness=-1,border_color=None):
    if thickness==-1:
        cv2.rectangle(img,(x+r,y),(x+w-r,y+h),color,-1, cv2.LINE_AA)
        cv2.rectangle(img,(x,y+r),(x+w,y+h-r),color,-1, cv2.LINE_AA)
        cv2.circle(img,(x+r,y+r),r,color,-1, cv2.LINE_AA)
        cv2.circle(img,(x+w-r,y+r),r,color,-1, cv2.LINE_AA)
        cv2.circle(img,(x+r,y+h-r),r,color,-1, cv2.LINE_AA)
        cv2.circle(img,(x+w-r,y+h-r),r,color,-1, cv2.LINE_AA)
    else:
        bc=border_color or color
        # borda: apenas os trechos retos + arcos dos cantos (sem retangulos internos)
        cv2.line(img,(x+r,y),(x+w-r,y),bc,thickness,cv2.LINE_AA)
        cv2.line(img,(x+r,y+h),(x+w-r,y+h),bc,thickness,cv2.LINE_AA)
        cv2.line(img,(x,y+r),(x,y+h-r),bc,thickness,cv2.LINE_AA)
        cv2.line(img,(x+w,y+r),(x+w,y+h-r),bc,thickness,cv2.LINE_AA)
        cv2.ellipse(img,(x+r,y+r),(r,r),0,180,270,bc,thickness,cv2.LINE_AA)
        cv2.ellipse(img,(x+w-r,y+r),(r,r),0,270,360,bc,thickness,cv2.LINE_AA)
        cv2.ellipse(img,(x+w-r,y+h-r),(r,r),0,0,90,bc,thickness,cv2.LINE_AA)
        cv2.ellipse(img,(x+r,y+h-r),(r,r),0,90,180,bc,thickness,cv2.LINE_AA)

def put_text_center(img,text,x,y,w,h,font,scale,color,thick=1):
    # FIX v11.4: trunca rotulos maiores que a caixa (nao estoura o painel)
    texto=_ascii(str(text))
    (tw,th),_=cv2.getTextSize(texto,font,scale,thick)
    while tw>w-8 and len(texto)>3:
        texto=texto[:-2]
        (tw,th),_=cv2.getTextSize(texto,font,scale,thick)
    cv2.putText(img,texto,(x+(w-tw)//2,y+(h+th)//2),font,scale,color,thick,cv2.LINE_AA)

class DropdownPaleta:
    def __init__(self,x,y,w,h):
        self.rect=(x,y,w,h); self.expanded=False; self.selected_idx=0; self.hover_idx=-1
    def hit(self,px,py):
        x,y,w,h=self.rect; return x<=px<=x+w and y<=py<=y+h
    def hit_item(self,px,py):
        if not self.expanded: return None
        x,y,w,h=self.rect; cols=4; start_y=y+h+4
        for i in range(len(PALETA_32)):
            c=i%cols; r=i//cols
            ix=x+c*(w//cols); iy=start_y+r*28
            if ix<=px<=ix+(w//cols)-4 and iy<=py<=iy+24: return i
        return None
    def draw(self,canvas):
        x,y,w,h=self.rect
        nome,cor=PALETA_32[self.selected_idx]
        bg=THEME['card']
        draw_rounded_rect(canvas,x,y,w,h,8,bg,-1)
        draw_rounded_rect(canvas,x,y,w,h,8,(0,0,0),1,THEME['accent'] if self.expanded else THEME['border'])
        cv2.circle(canvas,(x+12,y+h//2),8,cor,-1); cv2.circle(canvas,(x+12,y+h//2),8,(0,0,0),1)
        arrow="^" if self.expanded else "v"
        cv2.putText(canvas,_ascii(f"{nome} {arrow}"),(x+28,y+18),cv2.FONT_HERSHEY_SIMPLEX,0.36,THEME['text_main'],1,cv2.LINE_AA)
        if not self.expanded: return 0
        cols=4; rows=(len(PALETA_32)+cols-1)//cols; dh=rows*28+8
        draw_rounded_rect(canvas,x,y+h+2,w,dh,8,THEME['card'],-1)
        draw_rounded_rect(canvas,x,y+h+2,w,dh,8,(0,0,0),1,THEME['border'])
        for i,(nome_i,cor_i) in enumerate(PALETA_32):
            r=i//cols; c=i%cols
            ix=x+4+c*(w//cols); iy=y+h+6+r*28
            is_sel=(i==self.selected_idx); is_hover=(i==self.hover_idx)
            bg_item=THEME['accent_soft'] if is_sel else ((250,242,236) if is_hover else THEME['card_alt'])
            bw=(w//cols)-6
            draw_rounded_rect(canvas,ix,iy,bw,24,6,bg_item,-1)
            draw_rounded_rect(canvas,ix,iy,bw,24,6,(0,0,0),1,THEME['accent'] if is_sel else THEME['border'])
            cv2.circle(canvas,(ix+8,iy+12),6,cor_i,-1)
            cv2.putText(canvas,_ascii(nome_i[:9]),(ix+18,iy+16),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['text_main'],1,cv2.LINE_AA)
        return dh


PRESETS_BANCADA_V84 = {
    'preset_smd': {"scale": 70, "brilho_min": 140, "brilho_max": 255, "sat_max": 50, "area_min": 6, "area_max": 250, "nms_dist": 14, "label":"SMD DENSO", "desc":"Placa verde moderna, pads 0402/0603. Rejeita vias.", "reject_vias": True},
    'preset_ecu': {"scale": 60, "brilho_min": 150, "brilho_max": 255, "sat_max": 70, "area_min": 12, "area_max": 450, "nms_dist": 16, "label":"ECU VERNIZ", "desc":"ECU com verniz brilhante, pads médios.", "reject_vias": True},
    'preset_fenolite': {"scale": 50, "brilho_min": 100, "brilho_max": 225, "sat_max": 85, "area_min": 25, "area_max": 900, "nms_dist": 20, "label":"FENOLITE ANT.", "desc":"Fenolite marrom antiga, pads grandes.", "reject_vias": False},
    'preset_painel': {"scale": 65, "brilho_min": 130, "brilho_max": 250, "sat_max": 60, "area_min": 20, "area_max": 700, "nms_dist": 18, "label":"PAINEL/CONEC.", "desc":"Painel/conector, trilhas largas.", "reject_vias": True},
    'preset_vias_off': {"scale": 70, "brilho_min": 135, "brilho_max": 255, "sat_max": 55, "area_min": 8, "area_max": 300, "nms_dist": 15, "label":"ANTI-VIA", "desc":"Rejeita furos/vias.", "reject_vias": True},
}

DESCRICOES_BOTOES = {
    'abrir_img': ("ABRIR IMAGEM [O]", ["Abre nova foto da placa", "JPG, PNG, BMP, TIFF", "Cria pasta saida_pads_*"]),
    'abrir_proj': ("ABRIR PROJETO [L]", ["Abre projeto salvo", "Carrega pads e medições", "Procura sessao_v87.json"]),
    'abrir_pasta': ("PASTA SAÍDA [K]", ["Abre pasta no Explorer", "CSV + PNG numerado"]),
    'toggle_minimap': ("MINIMAPA [V]", ["Mostra/esconde preview", "Topo-direito da placa", "Clique para navegar"]),
    'tab_calibrar': ("ABA CALIBRAR [1]", ["Detecção automática", "Ajuste filtros", "Presets"]),
    'tab_anotar': ("ABA ANOTAR [2]", ["Medição e anotação", "Conectar famílias"]),
    'modo_nav': ("NAVEGAR [N]", ["Navegação padrão", "Clique seleciona pad", "Meio arrasta = pan"]),
    'modo_add': ("ADICIONAR [A]", ["Adiciona pad manual", "Não apagado por Detectar"]),
    'modo_move': ("MOVER [M]", ["Move pad arrastando", "Só aba CALIBRAR"]),
    'modo_del': ("REMOVER [Del]", ["Remove pad", "Remove de famílias", "Undo [Z]"]),
    'detectar': ("DETECTAR [D]", ["Roda detecção auto", "Preserva manuais", "Rejeita vias"]),
    'reset': ("RESET", ["Apaga TODOS", "Pede SIM"]),
    'mascara': ("MÁSCARA [H]", ["Mostra máscara verde", "O que filtro pega"]),
    'fit': ("FIT [0]", ["Centraliza placa", "Reseta zoom"]),
    'undo': ("UNDO [Z]", ["Desfaz ação", "60 níveis"]),
    'redo': ("REDO [Y]", ["Refaz"]),
    'salvar': ("SALVAR [S]", ["Salva CSV + PNG", "sessão"]),
    'f_todos': ("FILTRO TODOS", ["Mostra todos"]),
    'f_auto': ("FILTRO AUTO", ["Só auto"]),
    'f_manual': ("FILTRO MANUAL", ["Só manual"]),
    'buscar': ("BUSCAR [F]", ["Busca por ID"]),
    'modo_med': ("MEDIR [M]", ["Edita medição", "Clique no pad"]),
    'modo_con': ("CONECTAR [C]", ["Conecta 2 pads", "Mesma família"]),
    'modo_descon': ("DESCONECTAR [X]", ["Remove de família"]),
    'editar': ("EDITAR [E]", ["Edita pad selecionado"]),
    'duplicar': ("DUPLICAR", ["Copia pad"]),
    'isolar': ("ISOLAR", ["Filtra família"]),
    'familias': ("FAMÍLIAS", ["Gerencia famílias"]),
    'f_ok': ("FILTRO OK", ["Só OK"]),
    'f_susp': ("FILTRO SUSP", ["Só SUSP"]),
    'f_falha': ("FILTRO FALHA", ["Só FALHA"]),
    'f_vazio': ("FILTRO SEM MEDIR", ["Sem status"]),
    'toggle_estado': ("PLACA LIG/DESL", ["Alterna V/R", "LIG= V,Hz DESL=R,cap"]),
}

def get_screen_size():
    try:
        import tkinter as tk
        root=tk.Tk(); root.withdraw(); w=root.winfo_screenwidth(); h=root.winfo_screenheight(); root.destroy()
        return min(w,1920), min(h,1080)
    except: return 1366,768

# FIX v11.4: removidas as definicoes DUPLICADAS de draw_rounded_rect/put_text_center
# e as copias mortas de PRESETS_BANCADA_V84/DESCRICOES_BOTOES (a segunda definicao
# sombreava a primeira e o app usa core.presets/ui widgets oficiais).

class ButtonV5:
    def __init__(self,x,y,w,h,label,key,kind='default',tooltip='',cor=None):
        self.rect=(x,y,w,h); self.label=label; self.key=key; self.kind=kind; self.tooltip=tooltip; self.cor_custom=cor; self.ativo=False; self.hover=False; self.enabled=True; self.destaque=False
    def hit(self,px,py): x,y,w,h=self.rect; return x<=px<=x+w and y<=py<=y+h
    def draw(self,canvas,font_scale_factor=1.0):
        x,y,w,h=self.rect
        # Visual claro estilo visualizador de fotos (v11.5)
        if not self.enabled: bg=(246,247,249); fg=(172,177,184); bd=(230,232,236)
        elif self.cor_custom:
            cor=tuple(self.cor_custom)
            bg=tuple(min(255,int(c*0.20+225)) for c in cor); fg=tuple(int(c*0.55) for c in cor); bd=tuple(max(0,int(c*0.72)) for c in cor)
        elif self.kind in ('mode','tab','filter') and self.ativo: bg=THEME['accent']; fg=(255,255,255); bd=THEME['accent']
        elif self.kind=='success': bg=THEME['accent']; fg=(255,255,255); bd=THEME['accent']
        elif self.kind=='danger': bg=(226,226,254); fg=(38,38,170); bd=(165,165,252)
        elif self.kind=='toggle' and self.ativo: bg=THEME['accent_soft']; fg=THEME['accent']; bd=THEME['accent']
        elif self.hover: bg=(250,242,236); fg=THEME['text_main']; bd=(190,200,215)
        else:
            bg=THEME['card']; fg=THEME['text_main']; bd=THEME['border']
            if self.kind=='filter': bg=THEME['field']
            if self.kind=='toggle': bg=THEME['card']
        cv2.rectangle(canvas,(x+1,y+2),(x+w+1,y+h+2),THEME['shadow'],-1, cv2.LINE_AA)
        draw_rounded_rect(canvas,x,y,w,h,8,bg,-1); draw_rounded_rect(canvas,x,y,w,h,8,(0,0,0),3 if self.destaque else 1,bd)
        if self.ativo and self.kind in ('mode','tab'): cv2.rectangle(canvas,(x+8,y+h-3),(x+w-8,y+h-1),(255,255,255),-1, cv2.LINE_AA)
        base=0.42 if len(self.label)<10 else 0.36 if len(self.label)<15 else 0.32
        put_text_center(canvas,self.label,x,y,w,h,cv2.FONT_HERSHEY_SIMPLEX,max(0.40,base*font_scale_factor),fg,1)

class CustomSlider:
    def __init__(self,x,y,w,h,label,min_v,max_v,val,unit,fmt="{:.0f}"):
        self.x,self.y,self.w,self.h=x,y,w,h; self.label=label; self.min_v,self.max_v=min_v,max_v; self.val=val; self.unit=unit; self.fmt=fmt; self.dragging=False
    def hit_track(self,px,py): return self.x<=px<=self.x+self.w and self.y+10<=py<=self.y+40
    def set_from_x(self,px): t=np.clip((px-self.x)/max(1,self.w),0,1); self.val=self.min_v+t*(self.max_v-self.min_v)
    def draw(self,canvas,x_offset=0,font_scale=1.0,enabled=True):
        x=self.x+x_offset; col_txt=THEME['text_main'] if enabled else (170,175,182)
        cv2.putText(canvas,f"{self.label}: {self.fmt.format(self.val)} {self.unit}",(x,self.y+12),cv2.FONT_HERSHEY_SIMPLEX,max(0.42,0.40*font_scale),col_txt,1,cv2.LINE_AA)
        ty=self.y+18; cv2.rectangle(canvas,(x,ty),(x+self.w,ty+12),(232,234,238),-1, cv2.LINE_AA); cv2.rectangle(canvas,(x,ty),(x+self.w,ty+12),(210,213,218),1, cv2.LINE_AA)
        t=(self.val-self.min_v)/max(0.001,self.max_v-self.min_v); fw=int(t*self.w); col=THEME['accent'] if self.dragging else THEME['accent']
        if not enabled: col=(200,203,208)
        cv2.rectangle(canvas,(x,ty),(x+fw,ty+12),col,-1, cv2.LINE_AA); kx=x+fw; cv2.circle(canvas,(kx,ty+6),8,(255,255,255),-1, cv2.LINE_AA); cv2.circle(canvas,(kx,ty+6),8,col,2, cv2.LINE_AA)

class DropdownPreset:
    def __init__(self,x,y,w,h):
        self.rect=(x,y,w,h); self.expanded=False; self.selected_key='preset_smd'; self.hover_idx=-1
    def hit(self,px,py): x,y,w,h=self.rect; return x<=px<=x+w and y<=py<=y+h
    def hit_item(self,px,py):
        if not self.expanded: return None
        x,y,w,h=self.rect
        for i,key in enumerate(PRESETS_BANCADA_V84.keys()):
            iy=y+h+2+i*44
            if x<=px<=x+w and iy<=py<=iy+40: return key
        return None
    def draw(self,canvas):
        x,y,w,h=self.rect
        sel=PRESETS_BANCADA_V84.get(self.selected_key, list(PRESETS_BANCADA_V84.values())[0])
        bg=THEME['card']
        draw_rounded_rect(canvas,x,y,w,h,8,bg,-1); draw_rounded_rect(canvas,x,y,w,h,8,(0,0,0),1,THEME['accent'] if self.expanded else THEME['border'])
        # FIX v11.4: seta invertida (fechado mostrar '^')
        arrow="^" if self.expanded else "v"
        cv2.putText(canvas,_ascii(f"{sel['label']} {arrow}"),(x+10,y+18),cv2.FONT_HERSHEY_SIMPLEX,0.40,THEME['text_main'],1,cv2.LINE_AA)
        cv2.putText(canvas,_ascii(sel['desc'][:32]),(x+10,y+32),cv2.FONT_HERSHEY_SIMPLEX,0.26,THEME['text_dim'],1,cv2.LINE_AA)
        if not self.expanded: return
        for i,(key,preset) in enumerate(PRESETS_BANCADA_V84.items()):
            iy=y+h+2+i*44; is_sel=(key==self.selected_key); is_hover=(i==self.hover_idx)
            bg_item=THEME['accent_soft'] if is_sel else ((250,242,236) if is_hover else THEME['card'])
            draw_rounded_rect(canvas,x,iy,w,40,6,bg_item,-1); draw_rounded_rect(canvas,x,iy,w,40,6,(0,0,0),1,THEME['accent'] if is_sel else THEME['border'])
            cv2.putText(canvas,_ascii(preset['label']),(x+10,iy+16),cv2.FONT_HERSHEY_SIMPLEX,0.36,THEME['text_main'],1,cv2.LINE_AA)
            cv2.putText(canvas,_ascii(preset['desc'][:38]),(x+10,iy+30),cv2.FONT_HERSHEY_SIMPLEX,0.24,THEME['text_dim'],1,cv2.LINE_AA)
