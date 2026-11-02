"""Busca datasheet de um componente na internet.

Exemplos:
  py -3.11 tools/buscar_datasheet.py --termo BC547
  py -3.11 tools/buscar_datasheet.py --termo TL072 --baixar C:\\PCB_Painel\\datasheets
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.datasheet import buscar_datasheet, baixar_pdf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--termo', required=True, help='Marcação/part number (ex: BC547)')
    ap.add_argument('--limite', type=int, default=8)
    ap.add_argument('--baixar', default='', help='Pasta para baixar o primeiro PDF')
    args = ap.parse_args()

    resultados = buscar_datasheet(args.termo, limite=args.limite)
    if not resultados:
        print('Nenhum resultado. Verifique conexão/termo.')
        sys.exit(1)
    for i, r in enumerate(resultados, 1):
        print(f"{i}. [{'PDF' if r['pdf'] else 'WEB'}] {r['url']}")
    if args.baixar:
        pdfs = [r for r in resultados if r['pdf']]
        if not pdfs:
            print('Nenhum PDF encontrado para baixar')
            sys.exit(2)
        caminho = None
        for r in pdfs:
            caminho = baixar_pdf(r['url'], args.baixar, nome=args.termo + '.pdf')
            if caminho:
                print('Fonte:', r['url'])
                break
        print('Baixado:', caminho or 'falhou (sites bloquearam)')


if __name__ == '__main__':
    main()
