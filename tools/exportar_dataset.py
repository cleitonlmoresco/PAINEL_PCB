"""Exporta dataset YOLO de pads a partir de projetos anotados ou de um álbum de fotos.

Exemplos:
  py -3.11 tools/exportar_dataset.py projetos --pastas C:\\PCB_Painel --saida C:\\PCB_Painel\\dataset_projetos
  py -3.11 tools/exportar_dataset.py album --fotos "C:\\PCB_Painel\\placas eletronicas\\..." --saida C:\\PCB_Painel\\dataset_album --escala 0.7
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.dataset import exportar_projetos, pre_anotar_album


def _progresso(msg):
    print(msg, flush=True)


def main():
    ap = argparse.ArgumentParser(description="Exportador de dataset YOLO de pads")
    sub = ap.add_subparsers(dest='modo', required=True)

    p1 = sub.add_parser('projetos', help='Exporta anotações de projetos (sessões JSON)')
    p1.add_argument('--pastas', nargs='+', required=True, help='Pastas de projetos (ou pasta raiz)')
    p1.add_argument('--saida', required=True)
    p1.add_argument('--tile', type=int, default=1024)
    p1.add_argument('--overlap', type=int, default=128)
    p1.add_argument('--val', type=float, default=0.2)

    p2 = sub.add_parser('album', help='Pré-anota um álbum de fotos com o detector smart')
    p2.add_argument('--fotos', required=True, help='Pasta com as fotos')
    p2.add_argument('--saida', required=True)
    p2.add_argument('--tile', type=int, default=1024)
    p2.add_argument('--overlap', type=int, default=128)
    p2.add_argument('--val', type=float, default=0.2)
    p2.add_argument('--escala', type=float, default=0.7)
    p2.add_argument('--sens', type=float, default=0.55)
    p2.add_argument('--gpu', action='store_true')

    args = ap.parse_args()
    if args.modo == 'projetos':
        stats = exportar_projetos(args.pastas, args.saida, tile=args.tile, overlap=args.overlap,
                                  val_ratio=args.val, progresso=_progresso)
    else:
        stats = pre_anotar_album(args.fotos, args.saida, tile=args.tile, overlap=args.overlap,
                                 val_ratio=args.val, escala=args.escala, sensibilidade=args.sens,
                                 usar_gpu=args.gpu, progresso=_progresso)
    print('\nRESUMO:', stats)
    print('Dataset em:', os.path.abspath(args.saida))
    print('YAML:', os.path.join(os.path.abspath(args.saida), 'data.yaml'))


if __name__ == '__main__':
    main()
