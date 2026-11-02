"""Diálogos de arquivo com fallback para console quando tkinter não está disponível.

O instalador oficial do Python no Windows às vezes não inclui o tkinter
(especialmente em distribuições minimalistas/embedded). Como o AnotadorPad
é distribuído como EXE one-file, precisamos de um caminho que não quebre
a aplicação quando tkinter falta.

Tenta tkinter primeiro; se falhar, pede o caminho via input() no console
(que permanece visível graças ao try/except no ponto de entrada do EXE).
"""
from __future__ import annotations

import os
from typing import List, Optional, Tuple

_TK = None
_TK_ERRO: Optional[str] = None


def _disponivel() -> bool:
    global _TK, _TK_ERRO
    if _TK is not None:
        return _TK is not None
    try:
        import tkinter as tk  # noqa: F401
        from tkinter import filedialog  # noqa: F401
        _TK = True
        return True
    except Exception as e:  # tkinter não instalado neste Python
        _TK = None
        _TK_ERRO = str(e)
        return False


def _mensagem_erro() -> str:
    return _TK_ERRO or "tkinter não disponível"


def escolher_arquivo(
    titulo: str = "Selecionar arquivo",
    initialdir: Optional[str] = None,
    filetypes: Optional[List[Tuple[str, str]]] = None,
) -> Optional[str]:
    """Abre um diálogo para escolher um arquivo. Retorna o caminho ou None."""
    if not _disponivel():
        print(f"[AnotadorPad] Tkinter indisponível: {_mensagem_erro()}")
        print(f"    {titulo}")
        if initialdir:
            print(f"    Pasta sugerida: {initialdir}")
        try:
            caminho = input("    Digite o caminho do arquivo (ou Enter para cancelar): ").strip()
        except EOFError:
            return None
        if not caminho:
            return None
        caminho = caminho.strip().strip('"')
        return caminho if os.path.exists(caminho) else None
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
    try:
        if initialdir and os.path.isdir(initialdir):
            root.initialdir = initialdir
    except Exception:
        pass
    try:
        caminho = filedialog.askopenfilename(title=titulo, initialdir=initialdir or os.getcwd(),
                                             filetypes=filetypes or [("Todos", "*.*")])
    finally:
        try: root.destroy()
        except Exception: pass
    return caminho or None


def escolher_pasta(
    titulo: str = "Selecionar pasta",
    initialdir: Optional[str] = None,
) -> Optional[str]:
    """Abre um diálogo para escolher uma pasta. Retorna o caminho ou None."""
    if not _disponivel():
        print(f"[AnotadorPad] Tkinter indisponível: {_mensagem_erro()}")
        print(f"    {titulo}")
        if initialdir:
            print(f"    Pasta sugerida: {initialdir}")
        try:
            caminho = input("    Digite o caminho da pasta (ou Enter para cancelar): ").strip()
        except EOFError:
            return None
        if not caminho:
            return None
        caminho = caminho.strip().strip('"')
        return caminho if os.path.isdir(caminho) else None
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
    try:
        caminho = filedialog.askdirectory(title=titulo, initialdir=initialdir or os.getcwd())
    finally:
        try: root.destroy()
        except Exception: pass
    return caminho or None


def salvar_arquivo(
    titulo: str = "Salvar arquivo",
    initialdir: Optional[str] = None,
    initialfile: Optional[str] = None,
    defaultextension: str = "",
    filetypes: Optional[List[Tuple[str, str]]] = None,
) -> Optional[str]:
    """Abre um diálogo para salvar um arquivo. Retorna o caminho ou None."""
    if not _disponivel():
        print(f"[AnotadorPad] Tkinter indisponível: {_mensagem_erro()}")
        print(f"    {titulo}")
        sugerido = os.path.join(initialdir or os.getcwd(), initialfile or "saida")
        print(f"    Arquivo sugerido: {sugerido}")
        try:
            caminho = input("    Digite o caminho de destino (ou Enter para cancelar): ").strip()
        except EOFError:
            return None
        if not caminho:
            return None
        caminho = caminho.strip().strip('"')
        return caminho
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
    try:
        caminho = filedialog.asksaveasfilename(title=titulo, initialdir=initialdir or os.getcwd(),
                                               initialfile=initialfile or "",
                                               defaultextension=defaultextension,
                                               filetypes=filetypes or [("Todos", "*.*")])
    finally:
        try: root.destroy()
        except Exception: pass
    return caminho or None
