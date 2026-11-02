"""Cria um subconjunto equilibrado do dataset para treino rápido em CPU.

Exemplo:
  py -3.11 tools/preparar_subset.py --dataset C:\\PCB_Painel\\dataset_placas \
      --saida C:\\PCB_Painel\\dataset_rapido --train 800 --val 200
"""
import argparse
import os
import random
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _listar(split, dataset):
    pasta_lab = os.path.join(dataset, 'labels', split)
    itens = []
    try:
        nomes = sorted(os.listdir(pasta_lab))
    except Exception:
        return []
    for lab in nomes:
        if not lab.endswith('.txt'):
            continue
        caminho_lab = os.path.join(pasta_lab, lab)
        try:
            tem = any(l.strip() for l in open(caminho_lab, encoding='utf-8'))
        except Exception:
            continue
        base = os.path.splitext(lab)[0]
        img = None
        for ext in ('.jpg', '.png', '.jpeg', '.bmp'):
            cand = os.path.join(dataset, 'images', split, base + ext)
            if os.path.exists(cand):
                img = cand
                break
        if img:
            itens.append((img, caminho_lab, tem))
    return itens


def _selecionar(itens, n, frac_vazios, rng):
    pos = [i for i in itens if i[2]]
    vaz = [i for i in itens if not i[2]]
    rng.shuffle(pos); rng.shuffle(vaz)
    nvaz = min(len(vaz), int(round(n * frac_vazios)))
    npos = min(len(pos), max(0, n - nvaz))
    escolhidos = pos[:npos] + vaz[:nvaz]
    rng.shuffle(escolhidos)
    return escolhidos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', required=True)
    ap.add_argument('--saida', required=True)
    ap.add_argument('--train', type=int, default=800)
    ap.add_argument('--val', type=int, default=200)
    ap.add_argument('--vazios', type=float, default=0.20, help='fração de tiles vazios')
    ap.add_argument('--seed', type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    for sub in ('images/train', 'images/val', 'labels/train', 'labels/val'):
        os.makedirs(os.path.join(args.saida, sub), exist_ok=True)

    total = 0
    for split, n in (('train', args.train), ('val', args.val)):
        itens = _listar(split, args.dataset)
        escolhidos = _selecionar(itens, n, args.vazios, rng)
        for img, lab, _ in escolhidos:
            base = os.path.basename(img)
            shutil.copyfile(img, os.path.join(args.saida, 'images', split, base))
            shutil.copyfile(lab, os.path.join(args.saida, 'labels', split, os.path.splitext(base)[0] + '.txt'))
            total += 1
        print(f'{split}: {len(escolhidos)} de {len(itens)} tiles')

    yml = f"""path: {os.path.abspath(args.saida).replace(chr(92), '/')}
train: images/train
val: images/val
names:
  0: pad
"""
    with open(os.path.join(args.saida, 'data.yaml'), 'w', encoding='utf-8') as f:
        f.write(yml)
    print('Subset em:', os.path.abspath(args.saida), '| tiles:', total)


if __name__ == '__main__':
    main()
