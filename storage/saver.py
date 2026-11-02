import csv
import os
import cv2
import shutil
from datetime import datetime


def _concluir(f, caminho):
    f.close()
    os.replace(caminho+'.tmp', caminho)


def _backup_existente(caminho):
    """Cria backup rotativo (mantém últimos 5) antes de sobrescrever."""
    if not os.path.exists(caminho):
        return
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    base, ext = os.path.splitext(caminho)
    bak = f"{base}.{ts}{ext}.bak"
    try:
        shutil.copy2(caminho, bak)
        # rotação: mantém só 5 mais recentes
        baks = sorted([f for f in os.listdir(os.path.dirname(caminho) or '.') 
                       if f.startswith(os.path.basename(base)+'.') and f.endswith('.bak')])
        for old in baks[:-5]:
            try: os.remove(os.path.join(os.path.dirname(caminho) or '.', old))
            except Exception: pass
    except Exception:
        pass


def salvar_csvs(pads,measurements,nets,out_dir):
    os.makedirs(out_dir,exist_ok=True)
    # C1: backup antes de sobrescrever
    for nome in ('pads_final.csv','medicoes_final.csv'):
        _backup_existente(os.path.join(out_dir, nome))
    try:
        f=open(os.path.join(out_dir,'pads_final.csv.tmp'),"w",newline="",encoding="utf-8")
        w=csv.writer(f); w.writerow(["id","x","y","w","h","area","manual","pino","gnd","link"])
        for p in pads: w.writerow([p.get('id',0),p.get('x',p.get('cx',0)),p.get('y',p.get('cy',0)),p.get('w',12),p.get('h',12),p.get('area',100),'S' if p.get('manual') else 'N',p.get('pino','') or '','S' if p.get('gnd') else 'N',p.get('link','') or ''])
        _concluir(f,os.path.join(out_dir,'pads_final.csv'))
    except Exception as e:
        print(f"csv pads erro: {e}")
    pad_nets={}
    for net in nets:
        for pid in net.get('pads',[]): pad_nets.setdefault(pid,[]).append(net.get('id'))
    try:
        f=open(os.path.join(out_dir,'medicoes_final.csv.tmp'),"w",newline="",encoding="utf-8")
        w=csv.writer(f); w.writerow(['id','x','y','manual','status','familia_id','familia_nome','V','Hz','forma','obs_ligada','R_ohm','continuidade','capacitancia','diodo_Vf','obs_desligada','net_ids','conecta_com'])
        for p in pads:
            pid=p.get('id',0); m=measurements.get(pid,{}) if isinstance(measurements,dict) else {}; lig=m.get('ligada',{}) or {}; des=m.get('desligada',{}) or {}; nets_do_pad=pad_nets.get(pid,[]); conecta=[]
            for net in nets:
                if pid in net.get('pads',[]): conecta.extend(str(x) for x in net.get('pads',[]) if x!=pid)
            fam_id=nets_do_pad[0] if nets_do_pad else ''; fam_nome=''
            if nets_do_pad:
                net=next((n for n in nets if n.get('id')==nets_do_pad[0]),None)
                if net: fam_nome=net.get('nome',f"Familia {net.get('id')}")
            x=p.get('x',p.get('cx',0)); y=p.get('y',p.get('cy',0))
            w.writerow([pid,x,y,'S' if p.get('manual') else 'N',m.get('status','') or '',fam_id,fam_nome,lig.get('tensao',''),lig.get('frequencia',''),lig.get('forma',''),lig.get('obs',''),des.get('resistencia',''),des.get('continuidade',''),des.get('capacitancia',''),des.get('diodo',''),des.get('obs',''),','.join(str(n) for n in nets_do_pad),','.join(conecta)])
        _concluir(f,os.path.join(out_dir,'medicoes_final.csv'))
    except Exception as e:
        print(f"csv medicoes erro: {e}")



def salvar_png(pads,out_dir,img):
    try:
        from core.imgio import imwrite
        vis=img.copy()
        for p in pads:
            x=p.get('x',p.get('cx',0)); y=p.get('y',p.get('cy',0)); cor=(0,165,255) if p.get('manual') else (0,220,0)
            cv2.circle(vis,(x,y),10,cor,2); cv2.circle(vis,(x,y),2,(0,0,255),-1); cv2.putText(vis,str(p.get('id',0)),(x+7,y-4),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,255),1)
        imwrite(f"{out_dir}/pads_numerados.png",vis)
    except Exception as e: print(f"PNG erro: {e}")



def salvar_componentes_csv(componentes, out_dir):
    """FIX: salva cor real + sugestao (round-trip completo com o loader)"""
    os.makedirs(out_dir, exist_ok=True)
    _backup_existente(os.path.join(out_dir, 'componentes_final.csv'))
    try:
        f=open(os.path.join(out_dir,'componentes_final.csv.tmp'),"w",newline="",encoding="utf-8")
        w=csv.writer(f)
        w.writerow(["id","nome","tipo","forma","x1","y1","x2","y2","pads","valor","tensao","obs","cor","marcacao","datasheet","pino1","sugestao"])
        for c in componentes:
            pads_str=";".join(str(p) for p in c.get('pads',[]))
            cor=c.get('cor',[80,140,255])
            cor_str=f"{cor[0]};{cor[1]};{cor[2]}" if isinstance(cor,(list,tuple)) else str(cor)
            pino1=c.get('pino1')
            w.writerow([c.get('id'),c.get('nome'),c.get('tipo'),c.get('forma'),c.get('x1'),c.get('y1'),c.get('x2'),c.get('y2'),pads_str,c.get('valor',''),c.get('tensao',''),c.get('obs',''),cor_str,c.get('marcacao',''),c.get('datasheet',''),'' if pino1 is None else pino1,c.get('sugestao','')])
        _concluir(f,os.path.join(out_dir,'componentes_final.csv'))
    except Exception as e:
        print(f"csv componentes erro: {e}")


def salvar_png(pads,out_dir,img):
    try:
        from core.imgio import imwrite
        vis=img.copy()
        for p in pads:
            x=p.get('x',p.get('cx',0)); y=p.get('y',p.get('cy',0)); cor=(0,165,255) if p.get('manual') else (0,220,0)
            cv2.circle(vis,(x,y),10,cor,2); cv2.circle(vis,(x,y),2,(0,0,255),-1); cv2.putText(vis,str(p.get('id',0)),(x+7,y-4),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,255),1)
        _backup_existente(os.path.join(out_dir,'pads_numerados.png'))
        imwrite(os.path.join(out_dir,'pads_numerados.png'),vis)
    except Exception as e: print(f"PNG erro: {e}")
