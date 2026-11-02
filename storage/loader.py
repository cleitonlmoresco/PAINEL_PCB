import csv
import os
import json
import glob
import re
import hashlib
from pathlib import Path

from core.presets import PALETA


def _hash_sessao(data: dict) -> str:
    """Calcula SHA256 dos dados essenciais da sessão (sem campos voláteis)."""
    essencial = {k: data.get(k) for k in ('pads','measurements','nets','componentes','views','view_atual','next_id','next_net_id','next_comp_id','next_anot_id') if k in data}
    txt = json.dumps(essencial, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(txt.encode('utf-8')).hexdigest()


def _validar_sessao(data: dict, esperado_hash: str = None) -> tuple[bool, str]:
    """Valida integridade da sessão. Retorna (ok, mensagem)."""
    if not isinstance(data, dict):
        return False, "JSON não é objeto"
    # campos mínimos esperados
    for k in ('pads', 'measurements', 'nets', 'componentes'):
        if k not in data:
            return False, f"Campo obrigatório ausente: {k}"
    if 'views' in data and not isinstance(data['views'], dict):
        return False, "'views' deve ser objeto"
    if 'view_atual' in data and data['view_atual'] not in data.get('views', {}):
        return False, f"view_atual '{data['view_atual']}' não existe em views"
    # checksum se fornecido
    if esperado_hash:
        real = _hash_sessao(data)
        if real != esperado_hash:
            return False, f"Checksum inválido (esperado {esperado_hash[:16]}..., real {real[:16]}...)"
    return True, "OK"

def _linha_ok(row):
    """DictReader pode preencher campos faltantes com None; normaliza para ''."""
    return {k: (v if v is not None else '') for k, v in row.items() if k is not None}


def _int_ou(txt, padrao=None):
    try:
        return int(float(str(txt).strip().replace(',', '.')))
    except Exception:
        return padrao


def carregar_pads_csv(csv_path):
    pads=[]; descartadas=0
    with open(csv_path,'r',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        colunas=reader.fieldnames or []
        for row in reader:
            try:
                row=_linha_ok(row)
                pid=_int_ou(row.get('id'))
                x=_int_ou(row.get('x')); y=_int_ou(row.get('y'))
                if pid is None or x is None or y is None:
                    descartadas+=1; continue
                w=_int_ou(row.get('w'), 12); h=_int_ou(row.get('h'), 12)
                # CSV antigo sem coluna manual: NAO marcar tudo como manual
                if 'manual' in colunas:
                    manual=str(row.get('manual') or 'N').strip().upper() in ('S','SIM','1','TRUE','X')
                else:
                    manual=False
                pad={'id':pid,'x':x,'y':y,'w':w,'h':h,'manual':manual,'cx':x,'cy':y,'area':w*h}
                pino=str(row.get('pino') or '').strip()
                if pino: pad['pino']=pino
                if str(row.get('gnd') or '').strip().upper() in ('S','SIM','YES','Y','ON','1','TRUE','X'): pad['gnd']=True
                link=str(row.get('link') or '').strip()
                if link: pad['link']=link
                pads.append(pad)
            except Exception:
                descartadas+=1; continue
    if descartadas:
        print(f"aviso: {descartadas} linha(s) invalida(s) descartada(s) em {os.path.basename(csv_path)}")
    return pads


def carregar_medicoes_e_nets(csv_path):
    # v10.3 COMPATIVEL - carrega medicoes_final.csv e reconstrói nets/familias a partir de familia_id
    measurements={}
    nets_dict={}
    try:
        with open(csv_path,'r',encoding='utf-8-sig') as f:
            reader=csv.DictReader(f)
            for row in reader:
                try:
                    row=_linha_ok(row)
                    pid=_int_ou(row.get('id'))
                    if pid is None:
                        continue
                    # medicoes
                    m={'status':row.get('status',''),'ligada':{'tensao':row.get('V',''),'frequencia':row.get('Hz',''),'forma':row.get('forma',''),'obs':row.get('obs_ligada','')},'desligada':{'resistencia':row.get('R_ohm',''),'continuidade':row.get('continuidade',''),'capacitancia':row.get('capacitancia',''),'diodo':row.get('diodo_Vf',''),'obs':row.get('obs_desligada','')}}
                    measurements[pid]=m
                    # nets - agrupa por familia_id
                    fam_id=str(row.get('familia_id') or '').strip()
                    fam_nome=str(row.get('familia_nome') or '').strip()
                    if fam_id and fam_id.isdigit():
                        fid=int(fam_id)
                        if fid not in nets_dict:
                            nets_dict[fid]={'id':fid,'nome':fam_nome or f'Familia {fid}','cor':PALETA[fid%len(PALETA)][1],'pads':[]}
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
        with open(csv_path,'r',encoding='utf-8-sig') as f:
            reader=csv.DictReader(f)
            for row in reader:
                try:
                    row=_linha_ok(row)
                    cid=_int_ou(row.get('id'), 0) or 0
                    pads_str=row.get('pads','')
                    pads=[]
                    if pads_str:
                        import re
                        pads=[int(x) for x in re.findall(r'\d+', pads_str)]
                    # FIX BUG: ler TODOS os campos que o saver grava (datasheet, marcacao, pino1, cor)
                    cor_str=str(row.get('cor') or '').strip()
                    try:
                        rgb=[int(c) for c in re.split(r'[;,\s]+', cor_str) if c.strip()!=''][:3] if cor_str else []
                    except Exception:
                        rgb=[]
                    if len(rgb)==3:
                        cor=rgb
                    else:
                        cor=[80,140,255]
                    pino1=row.get('pino1','')
                    try: pino1=int(pino1) if str(pino1).strip() not in ('','None') else None
                    except Exception: pino1=None
                    comps.append({'id':cid,'nome':row.get('nome') or f'C{cid}','tipo':row.get('tipo','capacitor'),'forma':row.get('forma','circulo'),'cor':cor,'pads':pads,'valor':row.get('valor',''),'tensao':row.get('tensao',''),'obs':row.get('obs',''),'marcacao':row.get('marcacao',''),'datasheet':row.get('datasheet',''),'pino1':pino1,'sugestao':row.get('sugestao','')})
                except Exception:
                    continue
    except Exception:
        pass
    return comps




def carregar_projeto_universal(pasta_ou_csv):
    """
    Compatibilidade total v84..v10.3
    - Procura JSONs (sessao_v10_3, v10_2, v10, v87, v86...)
    - Fallback CSVs
    """
    pads=[]; meas={}; nets=[]; comps=[]
    path=Path(pasta_ou_csv)
    pasta = path if path.is_dir() else path.parent

    # Tenta JSON mais recente por mtime
    candidatos = list(pasta.glob("sessao_*.json")) + list(pasta.glob("**/sessao_*.json"))
    candidatos.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    for cand in candidatos[:5]:
        try:
            data=json.loads(cand.read_text(encoding='utf-8'))
            # C2: validação de integridade da sessão
            ok, msg = _validar_sessao(data)
            if not ok:
                print(f"Sessão inválida ({cand.name}): {msg}")
                continue
            pads=data.get('pads',[])
            # medidas podem vir como dict com chaves str; ignora chaves nao numericas sem abortar o JSON
            meas_raw=data.get('measurements',{})
            meas={int(k):v for k,v in meas_raw.items() if str(k).lstrip('+').lstrip('-').isdigit()}
            # FIX BUG: suporta sessoes novas com views (cada view tem pads proprios)
            views=data.get('views') or {}
            if isinstance(views,dict) and views:
                val=str(data.get('view_atual') or 'frente')
                vd=views.get(val) or next(iter(views.values()))
                if isinstance(vd,dict):
                    if isinstance(vd.get('pads'),list) and vd['pads']:
                        pads=vd['pads']
                    if isinstance(vd.get('measurements'),dict) and vd['measurements']:
                        meas_raw_vd=vd['measurements']
                        meas={int(k):v for k,v in meas_raw_vd.items() if str(k).lstrip('-').isdigit()}
                    nets=vd.get('nets') or nets
                    comps=vd.get('componentes') or comps
            nets=data.get('nets') or nets
            comps=data.get('componentes', data.get('componentes_final')) or comps
            return pads, meas, nets, comps, str(cand)
        except Exception as e:
            continue

    # Fallback CSV
    pads_csv = pasta/"pads_final.csv"
    med_csv = pasta/"medicoes_final.csv"
    comp_csv = pasta/"componentes_final.csv"
    if pads_csv.exists():
        raw = carregar_pads_csv(str(pads_csv))
        # FIX BUG: preservar pino/gnd/link do CSV (antes eram descartados)
        pads=[dict(p) for p in raw]
        if med_csv.exists():
            meas, nets = carregar_medicoes_e_nets(str(med_csv))
        if comp_csv.exists():
            comps = carregar_componentes_csv(str(comp_csv))
    return pads, meas, nets, comps, None


# ---------------------------------------------------------------------------
# Localização da imagem de um projeto de placa
# (usado pelo app ao abrir projetos e pelo main.py via linha de comando)
# ---------------------------------------------------------------------------
def _imgs_em(d):
    try: nomes = os.listdir(d)
    except Exception: return []
    exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')
    return [os.path.join(d, n) for n in nomes if n.lower().endswith(exts) and os.path.isfile(os.path.join(d, n))]


def resolver_img_sessao(img_salva, pasta):
    """Resolve o img_path salvo na sessão (absoluto ou relativo a pasta/pasta-pai/cwd)."""
    if not img_salva:
        return None
    img_salva = str(img_salva).replace('\\', os.sep)
    if os.path.isabs(img_salva):
        return img_salva if os.path.exists(img_salva) else None
    for b in (pasta, os.path.dirname(pasta), os.getcwd()):
        try: cand = os.path.normpath(os.path.join(b, img_salva))
        except Exception: continue
        if os.path.exists(cand):
            return cand
    return None


def procurar_imagem_projeto(pasta):
    """Procura a foto da placa perto do projeto: subpasta imagens/ ou nome placa*/imagem*/board*/foto*."""
    pasta = os.path.abspath(pasta)
    prefixos = ('placa', 'board', 'imagem', 'foto')
    for base in (pasta, os.path.dirname(pasta)):
        for sub in ('imagens', 'images'):
            d = os.path.join(base, sub)
            if os.path.isdir(d):
                imgs = _imgs_em(d)
                imgs.sort(key=lambda p: (not os.path.basename(p).lower().startswith(prefixos), p))
                if imgs:
                    return imgs[0]
    imgs = [p for p in _imgs_em(pasta) if os.path.basename(p).lower().startswith(prefixos)]
    imgs.sort()
    return imgs[0] if imgs else None


def achar_imagem_projeto(pasta):
    """Imagem do projeto: img_path da sessão mais recente e, se falhar, busca por convenção."""
    cands = []
    try:
        cands = sorted(glob.glob(os.path.join(pasta, '**', 'sessao_*.json'), recursive=True),
                       key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)
    except Exception:
        cands = []
    for c in cands:
        try:
            with open(c, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
        r = resolver_img_sessao(data.get('img_path'), pasta)
        if r:
            return r
        break
    return procurar_imagem_projeto(pasta)
