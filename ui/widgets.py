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

def detectar_pads_com_mascara_v84(img_bgr, scale=0.6, brilho_min=110, brilho_max=245, sat_max=75, area_min=30, area_max=900, nms_dist=10, reject_vias=True):
    scale=max(0.05,min(1.0,scale)); h0,w0=img_bgr.shape[:2]
    img_work=cv2.resize(img_bgr,(int(w0*scale),int(h0*scale)),interpolation=cv2.INTER_AREA) if scale!=1.0 else img_bgr.copy()
    img_work_blur=cv2.bilateralFilter(img_work,5,40,40); hsv=cv2.cvtColor(img_work_blur,cv2.COLOR_BGR2HSV); H,S,V=cv2.split(hsv)
    mask_pad=((S<sat_max)&(V>brilho_min)&(V<brilho_max)).astype(np.uint8)*255
    mask_green=cv2.inRange(hsv,np.array([35,25,25]),np.array([85,255,255]))
    kc=max(3,int(25*scale/0.6)); ke=max(3,int(20*scale/0.6))
    k_close=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(kc,kc)); mask_green=cv2.morphologyEx(mask_green,cv2.MORPH_CLOSE,k_close,iterations=4)
    cnts,_=cv2.findContours(mask_green,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    roi=np.zeros(mask_pad.shape,dtype=np.uint8)
    if cnts: maior=max(cnts,key=cv2.contourArea); cv2.drawContours(roi,[maior],-1,255,-1)
    else: roi[:]=255
    k_er=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(ke,ke)); roi=cv2.erode(roi,k_er,iterations=1); mask_pad=cv2.bitwise_and(mask_pad,roi)
    k1=cv2.getStructuringElement(cv2.MORPH_RECT,(2,2)); mask_pad=cv2.morphologyEx(mask_pad,cv2.MORPH_OPEN,k1,iterations=1); mask_pad=cv2.morphologyEx(mask_pad,cv2.MORPH_CLOSE,k1,iterations=1)
    cnts,_=cv2.findContours(mask_pad,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    pads=[]
    for cnt in cnts:
        area=cv2.contourArea(cnt); area_orig=area/(scale*scale)
        if area_orig<area_min or area_orig>area_max: continue
        perim=cv2.arcLength(cnt,True)
        if perim==0: continue
        x,y,w,h=cv2.boundingRect(cnt)
        if w<3 or h<3: continue
        hull=cv2.convexHull(cnt); hull_a=cv2.contourArea(hull); sol=area/hull_a if hull_a>0 else 0; extent=area/(w*h) if w*h>0 else 0; aspect=max(w,h)/max(1,min(w,h))
        if extent<0.4 or sol<0.6 or aspect>4.0: continue
        M=cv2.moments(cnt)
        if M["m00"]==0: continue
        cx_w=int(M["m10"]/M["m00"]); cy_w=int(M["m01"]/M["m00"])
        if reject_vias:
            x1=max(0,cx_w-2); x2=min(V.shape[1],cx_w+3); y1=max(0,cy_w-2); y2=min(V.shape[0],cy_w+3)
            roi_v=V[y1:y2, x1:x2]
            if roi_v.size>0:
                mean_v=np.mean(roi_v); roi_s=S[y1:y2, x1:x2]; mean_s=np.mean(roi_s) if roi_s.size>0 else 0
                if mean_v<75 and mean_s<90: continue
                if w>0 and h>0:
                    circularity=4*np.pi*area/(perim*perim) if perim>0 else 0
                    if circularity>0.65 and mean_v<95: continue
        cx=int(cx_w/scale); cy=int(cy_w/scale)
        pads.append({"cx":cx,"cy":cy,"w":int(w/scale),"h":int(h/scale),"area":int(area_orig),"manual":False})
    pads.sort(key=lambda p:p["area"],reverse=True); keep=[]
    for p in pads:
        if any(np.hypot(p["cx"]-q["cx"],p["cy"]-q["cy"])<nms_dist*2 for q in keep): continue
        keep.append(p)
    keep.sort(key=lambda p:(p["cy"]//80,p["cx"]))
    mask_full=cv2.resize(mask_pad,(w0,h0),interpolation=cv2.INTER_NEAREST)
    return keep,mask_full

def carregar_pads_csv(csv_path):
    pads=[]
    with open(csv_path,'r',encoding='utf-8') as f:
        reader=csv.DictReader(f)
        for row in reader:
            try:
                pid=int(row['id']); manual=(str(row.get('manual','S') or 'S').upper()=='S')
                pads.append({'id':pid,'x':int(row['x']),'y':int(row['y']),'w':int(row.get('w',12)or 12),'h':int(row.get('h',12)or 12),'manual':manual,'cx':int(row['x']),'cy':int(row['y']),'area':int(row.get('w',12)or 12)*int(row.get('h',12)or 12)})
            except: continue
    return pads

def carregar_medicoes_e_nets(csv_path):
    # v10.3 COMPATIVEL - carrega medicoes_final.csv e reconstrói nets/familias a partir de familia_id
    measurements={}
    nets_dict={}
    try:
        with open(csv_path,'r',encoding='utf-8') as f:
            reader=csv.DictReader(f)
            for row in reader:
                try:
                    pid=int(row['id'])
                    # medicoes
                    m={'status':row.get('status',''),'ligada':{'tensao':row.get('V',''),'frequencia':row.get('Hz',''),'forma':row.get('forma',''),'obs':row.get('obs_ligada','')},'desligada':{'resistencia':row.get('R_ohm',''),'continuidade':row.get('continuidade',''),'capacitancia':row.get('capacitancia',''),'diodo':row.get('diodo_Vf',''),'obs':row.get('obs_desligada','')}}
                    measurements[pid]=m
                    # nets - agrupa por familia_id
                    fam_id=row.get('familia_id','').strip()
                    fam_nome=row.get('familia_nome','').strip()
                    if fam_id and fam_id.isdigit():
                        fid=int(fam_id)
                        if fid not in nets_dict:
                            nets_dict[fid]={'id':fid,'nome':fam_nome or f'Familia {fid}','cor':list(PALETA[fid%len(PALETA)][1]) if 'PALETA' in globals() else [80,140,255],'pads':[]}
                        nets_dict[fid]['pads'].append(pid)
                except Exception:
                    continue
    except Exception as e:
        print(f"medicoes load erro: {e}")
    nets=list(nets_dict.values())
    return measurements, nets

def carregar_componentes_csv(csv_path):
    comps=[]
    try:
        with open(csv_path,'r',encoding='utf-8') as f:
            reader=csv.DictReader(f)
            for row in reader:
                try:
                    cid=int(row.get('id',0) or 0)
                    pads_str=row.get('pads','')
                    pads=[]
                    if pads_str:
                        import re
                        pads=[int(x) for x in re.findall(r'\d+', pads_str)]
                    comps.append({'id':cid,'nome':row.get('nome',f'C{cid}'),'tipo':row.get('tipo','capacitor'),'forma':row.get('forma','circulo'),'cor':[80,140,255],'pads':pads,'valor':row.get('valor',''),'tensao':row.get('tensao',''),'obs':row.get('obs',''),'sugestao':row.get('sugestao','')})
                except Exception:
                    continue
    except Exception:
        pass
    return comps


def salvar_csvs(pads,measurements,nets,out_dir):
    os.makedirs(out_dir,exist_ok=True)
    with open(f"{out_dir}/pads_final.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["id","x","y","w","h","area","manual"])
        for p in pads: w.writerow([p.get('id',0),p.get('x',p.get('cx',0)),p.get('y',p.get('cy',0)),p.get('w',12),p.get('h',12),p.get('area',100),'S' if p.get('manual') else 'N'])
    pad_nets={}
    for net in nets:
        for pid in net['pads']: pad_nets.setdefault(pid,[]).append(net['id'])
    with open(f"{out_dir}/medicoes_final.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(['id','x','y','manual','status','familia_id','familia_nome','V','Hz','forma','obs_ligada','R_ohm','continuidade','capacitancia','diodo_Vf','obs_desligada','net_ids','conecta_com'])
        for p in pads:
            pid=p.get('id',0); m=measurements.get(pid,{}) if isinstance(measurements,dict) else {}; lig=m.get('ligada',{}) or {}; des=m.get('desligada',{}) or {}; nets_do_pad=pad_nets.get(pid,[]); conecta=[]
            for net in nets:
                if pid in net['pads']: conecta.extend(str(x) for x in net['pads'] if x!=pid)
            fam_id=nets_do_pad[0] if nets_do_pad else ''; fam_nome=''
            if nets_do_pad:
                net=next((n for n in nets if n['id']==nets_do_pad[0]),None)
                if net: fam_nome=net.get('nome',f"Familia {net['id']}")
            x=p.get('x',p.get('cx',0)); y=p.get('y',p.get('cy',0))
            w.writerow([pid,x,y,'S' if p.get('manual') else 'N',m.get('status','') or '',fam_id,fam_nome,lig.get('tensao',''),lig.get('frequencia',''),lig.get('forma',''),lig.get('obs',''),des.get('resistencia',''),des.get('continuidade',''),des.get('capacitancia',''),des.get('diodo',''),des.get('obs',''),','.join(str(n) for n in nets_do_pad),','.join(conecta)])

def salvar_png(pads,out_dir,img):
    try:
        vis=img.copy()
        for p in pads:
            x=p.get('x',p.get('cx',0)); y=p.get('y',p.get('cy',0)); cor=(0,165,255) if p.get('manual') else (0,220,0)
            cv2.circle(vis,(x,y),10,cor,2); cv2.circle(vis,(x,y),2,(0,0,255),-1); cv2.putText(vis,str(p.get('id',0)),(x+7,y-4),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,255),1)
        cv2.imwrite(f"{out_dir}/pads_numerados.png",vis)
    except Exception as e: print(f"PNG erro: {e}")

