import sys
import os
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.app import AppV101
from storage.loader import achar_imagem_projeto

USO = """AnotadorPad v11.2 Modular

Uso:
  python main.py <imagem> [pasta_projeto]
  python main.py --projeto <pasta> [--imagem <imagem>]
  python main.py <pasta>                      (abre o projeto direto)
  python main.py                              (abre o ultimo projeto usado)

Exemplos:
  python main.py imagens/placa_teste.jpg
  python main.py --projeto saida_pads_placa_teste_293a4f

Dentro do app:
  [L] projetos (recentes com *)     [3][4][5] visoes frente/verso/conector
  [6] foto da visao                 [O] imagem (projeto novo)
  [J] GPU on/off                    [T] IDs dos pads
  [Ctrl+K] paleta de comandos       [Ctrl+N] salvar e proximo sem medir
  [R] regua / escala mm-por-px      [7] relatorio HTML
  [8] camera                        [9] comparar com placa ouro
  [Ctrl+L] camadas                  [S] salvar   (fechar: X da janela)

Formatos de projeto aceitos:
  sessao_*.json (pega a mais recente), pads_final.csv + medicoes_final.csv,
  pads.json, pads.csv, pads_v2.json / pads_v2.csv
"""


def _resolver(caminho):
    """Aceita caminho relativo ao cwd ou à pasta do anotador-modular."""
    if not caminho or os.path.exists(caminho):
        return caminho
    alt = os.path.join(ROOT, caminho)
    if os.path.exists(alt):
        return alt
    alt2 = os.path.join(os.path.dirname(ROOT), caminho)
    if os.path.exists(alt2):
        return alt2
    return caminho


def _abrir_por_projeto(projeto, imagem=None):
    pasta = _resolver(projeto)
    if not os.path.isdir(pasta):
        print(f"Projeto nao encontrado: {projeto}")
        sys.exit(1)
    img = _resolver(imagem) if imagem else achar_imagem_projeto(pasta)
    if not img or not os.path.exists(img):
        print(f"Projeto: {pasta}")
        print("Imagem do projeto nao encontrada automaticamente.")
        print("Informe manualmente:  python main.py --projeto <pasta> --imagem <imagem>")
        sys.exit(1)
    print("AnotadorPad v11 Modular - abrindo projeto")
    print(f"Projeto: {pasta}")
    print(f"Imagem:  {img}")
    print("Dica: tecla [L] no app abre a lista de projetos salvos")
    app = AppV101(img, pasta)
    app._abrir_projeto(pasta)
    app.iniciar()


def main():
    try:
        _main()
    except Exception:
        traceback.print_exc()
        # No EXE congelado o console fecha sozinho; deixa visível por 10 s.
        if getattr(sys, 'frozen', False):
            import time as _t
            print("\n--- Pressione Enter para sair (ou aguarde 10s) ---")
            try:
                import msvcrt
                _t.sleep(10)
            except Exception:
                _t.sleep(10)
        raise


def _main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help', '/?', '/help'):
        if not args:
            try:
                from core.prefs import carregar
                cfg = carregar()
                ultimo = cfg.get('ultimo_projeto') or ''
                if ultimo and os.path.isdir(ultimo):
                    print(f"AnotadorPad v11.2 - abrindo ultimo projeto: {ultimo}")
                    _abrir_por_projeto(ultimo)
                    return
            except Exception:
                pass
        print(USO)
        sys.exit(0 if args else 1)

    projeto = None
    imagem = None
    pos = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ('--projeto', '--project', '-p'):
            if i + 1 >= len(args):
                print("Faltou o caminho depois de --projeto\n"); print(USO); sys.exit(1)
            projeto = args[i + 1]; i += 2; continue
        if a in ('--imagem', '--image', '-i'):
            if i + 1 >= len(args):
                print("Faltou o caminho depois de --imagem\n"); print(USO); sys.exit(1)
            imagem = args[i + 1]; i += 2; continue
        pos.append(a); i += 1

    if imagem is None and pos:
        imagem = pos.pop(0)

    # Se o primeiro argumento é uma pasta, trata como projeto
    if projeto is None and imagem and os.path.isdir(_resolver(imagem)):
        projeto = imagem
        imagem = None

    if projeto:
        _abrir_por_projeto(projeto, imagem)
        return

    if not imagem:
        print(USO)
        sys.exit(1)

    img_path = _resolver(imagem)
    if not os.path.exists(img_path):
        print(f"Imagem nao encontrada: {imagem}")
        sys.exit(1)

    csv_path = None
    if pos:
        csv_path = _resolver(pos[0])
        if not os.path.exists(csv_path):
            csv_path = None

    print("AnotadorPad v11 Modular - 78% imagem | Zoom 0.1-20x | IDs 0.32 | Pads 50% menor")
    print(f"Imagem: {img_path}")
    if csv_path:
        print(f"Projeto: {csv_path}")
    print("Dica: dentro do app, tecla [L] abre a lista de projetos de placas salvos")

    app = AppV101(img_path, csv_path)
    app.iniciar()


if __name__ == "__main__":
    main()
