import json
import os
import shutil
from datetime import datetime


def _backup_sessao(caminho):
    if not os.path.exists(caminho):
        return
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    base, ext = os.path.splitext(caminho)
    bak = f"{base}.{ts}{ext}.bak"
    try:
        shutil.copy2(caminho, bak)
        baks = sorted([f for f in os.listdir(os.path.dirname(caminho) or '.') 
                       if f.startswith(os.path.basename(base)+'.') and f.endswith('.bak')])
        for old in baks[:-5]:
            try: os.remove(os.path.join(os.path.dirname(caminho) or '.', old))
            except Exception: pass
    except Exception:
        pass


def carregar_sessao(session_path):
    if not os.path.exists(session_path):
        return None
    try:
        with open(session_path,'r',encoding='utf-8') as f:
            data=json.load(f)
        # compat: converte chaves str -> int (ignora chaves nao numericas sem abortar)
        meas_raw=data.get('measurements',{})
        data['measurements']={int(k):v for k,v in meas_raw.items() if str(k).lstrip('-').isdigit()} if meas_raw else {}
        return data
    except Exception as e:
        print(f"Sessao load erro: {e}")
        return None

def salvar_sessao(session_path, pads, measurements, nets, componentes, next_id, next_net_id, next_comp_id, sliders, filter_familia_id, preset_key, estado_placa):
    """Nota: o app usa _salvar_sessao() proprio com views; esta rotina e o contratado
    antigo (v11 flat). Escrita atomica + backup rotativo para nao corromper a sessao em queda de luz."""
    _backup_sessao(session_path)
    tmp=session_path+'.tmp'
    try:
        with open(tmp,'w',encoding='utf-8') as f:
            json.dump({
                "pads":pads,
                "measurements":measurements,
                "nets":nets,
                "componentes":componentes,
                "next_id":next_id,
                "next_net_id":next_net_id,
                "next_comp_id":next_comp_id,
                "sliders":[s.val for s in sliders],
                "filter_familia_id":filter_familia_id,
                "preset_key":preset_key,
                "estado_placa":estado_placa,
                "version":"v11-modular"
            },f,indent=2,ensure_ascii=False)
        os.replace(tmp,session_path)
    except Exception as e:
        print(f"Salvar sessao erro: {e}")
        try: os.remove(tmp)
        except Exception: pass
