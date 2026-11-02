"""Sidebar moderna com botoes grandes, tooltips e acoes contextuais.

A sidebar e usada como um menu lateral dentro do painel direito. Ela possui
rolagem propria, secoes recolhiveis e botoes com tooltip. Todos os icones sao
ASCII porque o OpenCV nao desenha emojis de forma confiavel.
"""
from __future__ import annotations

import cv2
import numpy as np
from typing import List, Optional, Tuple

from .theme import THEME
from .widgets import draw_rounded_rect, put_text_center


def _ascii(t) -> str:
    """Remove caracteres que o cv2.putText nao desenha (emojis/acentos)."""
    if not isinstance(t, str):
        return str(t)
    out = []
    for ch in t:
        o = ord(ch)
        if o < 128:
            out.append(ch)
        elif ch in 'áàâãä':
            out.append('a')
        elif ch in 'ÁÀÂÃÄ':
            out.append('A')
        elif ch in 'éèêë':
            out.append('e')
        elif ch in 'ÉÈÊË':
            out.append('E')
        elif ch in 'íìîï':
            out.append('i')
        elif ch in 'ÍÌÎÏ':
            out.append('I')
        elif ch in 'óòôõö':
            out.append('o')
        elif ch in 'ÓÒÔÕÖ':
            out.append('O')
        elif ch in 'úùûü':
            out.append('u')
        elif ch in 'ÚÙÛÜ':
            out.append('U')
        elif ch in 'ç':
            out.append('c')
        elif ch in 'Ç':
            out.append('C')
        elif ch in '—–':
            out.append('-')
        elif ch == '·':
            out.append('|')
    return ''.join(out)


class SidebarButton:
    """Botao da sidebar com icone, label, tooltip e estado."""
    def __init__(self, x: int, y: int, w: int, h: int,
                 icon: str, label: str, tooltip: str,
                 action: str, kind: str = 'default',
                 toggle: bool = False, active: bool = False):
        self.rect = (x, y, w, h)
        self.icon = icon          # codigo ASCII curto
        self.label = label        # texto completo
        self.tooltip = tooltip    # descricao longa
        self.action = action      # chave da acao
        self.kind = kind          # 'default', 'success', 'danger', 'primary', 'toggle'
        self.toggle = toggle      # se e botao de ligar/desligar
        self.active = active      # estado ligado
        self.hover = False
        self.enabled = True
        self.show_tooltip = False
        self.tooltip_timer = 0.0

    def hit(self, px: int, py: int) -> bool:
        x, y, w, h = self.rect
        return x <= px <= x + w and y <= py <= y + h

    def draw(self, canvas: np.ndarray, font_scale: float = 1.0, now: float = 0.0):
        x, y, w, h = self.rect
        if not self.enabled:
            bg = (246, 247, 249); fg = (172, 177, 184); bd = (230, 232, 236)
        elif self.kind == 'success':
            bg = THEME['accent']; fg = (255, 255, 255); bd = THEME['accent']
        elif self.kind == 'danger':
            bg = (226, 226, 254); fg = (38, 38, 170); bd = (165, 165, 252)
        elif self.kind == 'primary':
            bg = THEME['accent']; fg = (255, 255, 255); bd = THEME['accent']
        elif self.kind == 'toggle':
            bg = THEME['accent_soft'] if self.active else THEME['card']
            fg = THEME['accent'] if self.active else THEME['text_main']
            bd = THEME['accent'] if self.active else THEME['border']
        else:
            bg = THEME['accent_soft'] if self.active else THEME['card']
            fg = THEME['accent'] if self.active else THEME['text_main']
            bd = THEME['accent'] if self.active else THEME['border']
        if self.hover and self.enabled:
            if self.kind not in ('success', 'primary'):
                bg = (250, 242, 236)
                bd = THEME['accent']

        # sombra sutil
        cv2.rectangle(canvas, (x+1, y+2), (x+w+1, y+h+2), THEME['shadow'], -1, cv2.LINE_AA)
        draw_rounded_rect(canvas, x, y, w, h, 6, bg, -1)
        draw_rounded_rect(canvas, x, y, w, h, 6, (0, 0, 0), 1, bd)

        # indicador ativo (barra lateral esquerda)
        if self.active and self.toggle:
            cv2.rectangle(canvas, (x, y), (x+3, y+h), THEME['accent'], -1, cv2.LINE_AA)

        icon_w = max(26, int(cv2.getTextSize(_ascii(self.icon), cv2.FONT_HERSHEY_SIMPLEX, max(0.32, 0.30 * font_scale), 1)[0][0]) + 12)
        label_font = max(0.30, 0.29 * font_scale)
        y_center = y + h // 2
        cv2.putText(canvas, _ascii(self.icon), (x + 8, y_center + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, max(0.32, 0.30 * font_scale),
                    fg, 1, cv2.LINE_AA)
        cv2.putText(canvas, _ascii(self.label), (x + icon_w + 4, y_center + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, label_font, fg, 1, cv2.LINE_AA)

    def update_hover(self, mx: int, my: int, now: float, tooltip_delay: float = 0.8):
        was_hover = self.hover
        self.hover = self.hit(mx, my) and self.enabled
        if self.hover != was_hover:
            self.tooltip_timer = now if self.hover else 0
        if self.hover:
            if now - self.tooltip_timer >= tooltip_delay:
                self.show_tooltip = True
        else:
            self.show_tooltip = False


class Sidebar:
    """Menu lateral com secoes recolhiveis e rolagem."""
    def __init__(self, x: int, y: int, w: int, h: int, font_scale: float = 1.0):
        self.rect = (x, y, w, h)
        self.font_scale = font_scale
        self.buttons: List[SidebarButton] = []
        self.sections: List[Tuple[str, List[SidebarButton]]] = []
        self.expanded: dict = {}
        self.scroll = 0
        self.max_scroll = 0
        self.content_h = 0
        self.section_rects: dict = {}
        self._build_sections()

    def _build_sections(self):
        def b(icon, label, tooltip, action, kind='default', toggle=False):
            return SidebarButton(0, 0, 0, 30, icon, label, tooltip, action, kind, toggle)

        self.sections.append(('PROJETO', [
            b('[O]', 'Abrir imagem', 'Cria um projeto novo a partir de uma foto (O)', 'abrir_img', 'success'),
            b('[L]', 'Abrir projeto', 'Lista e carrega projetos de placas (L)', 'abrir_proj', 'primary'),
            b('[K]', 'Pasta de saida', 'Abre a pasta do projeto no Explorer (K)', 'abrir_pasta'),
        ]))
        self.sections.append(('VISOES', [
            b('[3]', 'Frente', 'Visao da frente da placa', 'view_frente', 'filter'),
            b('[4]', 'Verso', 'Visao do verso (pads passantes vinculados)', 'view_verso', 'filter'),
            b('[5]', 'Conector', 'Visao de conector / pinagem', 'view_conector', 'filter'),
            b('[6]', 'Foto da visao', 'Escolhe/troca a foto da visao atual', 'view_img', 'action'),
        ]))
        self.sections.append(('COMPONENTES', [
            b('[G]', 'Painel de componentes', 'Lista os componentes e abre o editor (G)', 'comp_painel', 'primary'),
            b('[+]', 'Novo componente', 'Desenhe uma caixa na placa para criar (G)', 'comp_nova', 'success'),
            b('[DS]', 'Buscar datasheet', 'Busca datasheet pela marcacao do componente ou digitando o part number', 'comp_datasheet', 'action'),
            b('[PDF]', 'Pasta de datasheets', 'Abre a pasta de PDFs baixados do projeto', 'datasheets_pasta', 'action'),
            b('[?]', 'Reconhecer tipo', 'Sugere capacitor, resistor, CI, conector, diodo... por nome, marcacao, valor, forma e familias', 'comp_reconhecer', 'success'),
            b('[1]', 'Auto pino 1', 'Detecta o provavel pino 1 pela forma e posicao do pad', 'comp_auto_pino1', 'action'),
            b('[CSV]', 'Exportar pinagem', 'Gera CSV pino -> pad -> familia -> status', 'comp_pinagem', 'action'),
        ]))
        self.sections.append(('MARCACAO', [
            b('[Y]', 'Anotar', 'Cria uma anotacao livre no ponto clicado (Y)', 'modo_anot', 'mode'),
            b('[I]', 'Nomear pino', 'Clique num pad para dar nome/numero ao pino (I)', 'modo_pino', 'mode'),
            b('[U]', 'Marcar GND', 'Clique num pad para marcar/desmarcar GND (U)', 'modo_gnd', 'mode'),
            b('[#]', 'Numerar pinos', 'Numera os pinos do componente selecionado a partir do pino 1', 'pin_numerar', 'action'),
            b('[E]', 'Editar medicao', 'Abre o editor do pad selecionado (E)', 'editar', 'action'),
            b('[+]', 'Proximo pendente', 'Salva e abre o proximo pad sem medir (Ctrl+N)', 'prox_pendente', 'action'),
            b('[+]', 'Mira', 'Liga/desliga a mira de precisao', 'toggle_mira', 'toggle'),
            b('[V]', 'Validar AL', 'Modo validacao Active Learning: aprova/rejeita pseudo-labels', 'modo_al_validar', 'mode'),
            b('[P]', 'Pseudo-Label', 'Gera pseudo-labels automaticos (conf > 0.8)', 'al_pseudo', 'action'),
            b('[T]', 'Treinar LoRA', 'Fine-tuning LoRA do modelo IA com labels atuais', 'al_train', 'action'),
        ]))
        self.sections.append(('DETECCAO', [
            b('[D]', 'Detectar', 'Roda a deteccao automatica (D)', 'detectar', 'success'),
            b('[IA]', 'Detector IA', 'Detecta pads com modelo ONNX treinado (usa GPU/VRAM)', 'modo_detector_ia', 'toggle'),
            b('[ONNX]', 'Escolher modelo', 'Aponta para qualquer arquivo .onnx exportado do YOLO', 'modelo_ia_escolher', 'action'),
            b('[S]', 'Smart/Classico', 'Alterna o detector Smart e o Classico', 'modo_detector', 'toggle'),
            b('[E]', 'Por exemplo', 'Clique num pad bom e detecte os iguais', 'detectar_exemplo'),
            b('[T]', 'Tiles', 'Deteccao por blocos para placas grandes', 'detectar_tiles'),
        ]))
        self.sections.append(('VISAO', [
            b('[T]', 'IDs dos pads', 'Mostra/esconde os IDs dos pads', 'toggle_ids', 'toggle'),
            b('[R]', 'Regua', 'Clique 2 pontos e informe a medida em mm', 'regua'),
            b('[V]', 'Minimapa', 'Mostra/esconde o minimapa', 'toggle_minimap', 'toggle'),
            b('[H]', 'Mascara', 'Mostra a mascara usada na deteccao', 'mascara', 'toggle'),
        ]))
        self.sections.append(('FERRAMENTAS', [
            b('[8]', 'Camera', 'Captura da webcam/microscopio', 'camera'),
            b('[7]', 'Relatorio', 'Gera o relatorio HTML do projeto', 'relatorio'),
            b('[9]', 'Comparar ouro', 'Compara com uma placa de referencia', 'comparar_ouro'),
            b('[!]', 'Anomalias', 'Compara a visao atual com a placa ouro', 'anomalias'),
            b('[K]', 'Comandos', 'Abre a paleta de comandos (Ctrl+K)', 'paleta'),
        ]))
        self.sections.append(('DADOS', [
            b('[S]', 'Salvar', 'Salva CSV, PNG e a sessao', 'salvar', 'success'),
            b('[DS]', 'Exportar dataset', 'Gera dataset YOLO para treino', 'exportar_dataset'),
            b('[AN]', 'Pre-anotar album', 'Pre-anota um album de fotos', 'pre_anotar_album'),
            b('[LK]', 'Vincular visoes', 'Vincula automaticamente os pads passantes', 'vincular_views'),
        ]))
        self.sections.append(('CONFIG', [
            b('[J]', 'GPU', 'Liga/desliga a GPU (VRAM). Ligada por padrao quando existe NVIDIA/AMD/Intel', 'toggle_gpu', 'toggle'),
            b('[A]', 'Auto-passantes', 'Liga/desliga o vinculo automatico entre visoes', 'toggle_auto_vincular', 'toggle'),
            b('[C]', 'Camadas', 'Mostra/esconde as camadas', 'camadas', 'toggle'),
            b('[M]', 'Voltar ao inspetor', 'Fecha este menu e volta ao painel normal', 'sidebar', 'toggle'),
        ]))

        for name, _ in self.sections:
            self.expanded[name] = True

    def layout(self, x: int, y: int, w: int, h: int, font_scale: float):
        """Calcula as posicoes dos botoes, respeitando a rolagem."""
        self.font_scale = font_scale
        self.rect = (x, y, w, h)
        btn_h = 30
        gap = 3
        section_gap = 7
        header_h = 24
        pad_x = 8
        inner_w = max(80, w - 2 * pad_x)
        cy = y + 42 - self.scroll
        self.section_rects = {}
        self.buttons = []
        for section_name, btns in self.sections:
            expanded = self.expanded.get(section_name, True)
            self.section_rects[section_name] = (x + 4, cy, inner_w - 0, header_h)
            cy += header_h
            if expanded:
                for btn in btns:
                    btn.rect = (x + pad_x, cy, inner_w, btn_h)
                    self.buttons.append(btn)
                    cy += btn_h + gap
            cy += section_gap
        self.content_h = max(0, cy - (y + 42 - self.scroll))
        visible_h = max(40, h - 46)
        self.max_scroll = max(0, self.content_h - visible_h)
        scroll_antes = self.scroll
        self.scroll = max(0, min(self.scroll, self.max_scroll))
        if self.scroll != scroll_antes:
            # reposiciona apos o clamp
            cy = y + 42 - self.scroll
            self.section_rects = {}
            self.buttons = []
            for section_name, btns in self.sections:
                expanded = self.expanded.get(section_name, True)
                self.section_rects[section_name] = (x + 4, cy, inner_w, header_h)
                cy += header_h
                if expanded:
                    for btn in btns:
                        btn.rect = (x + pad_x, cy, inner_w, btn_h)
                        self.buttons.append(btn)
                        cy += btn_h + gap
                cy += section_gap

    def _visible(self, y: int, h: int, pad: int = 2) -> bool:
        py = self.rect[1] + 40
        return y + h >= py and y <= self.rect[1] + self.rect[3] - 4

    def draw(self, canvas: np.ndarray, now: float = 0.0):
        x, y, w, h = self.rect
        if w <= 0 or h <= 0:
            return
        self.layout(x, y, w, h, self.font_scale)

        # fundo
        cv2.rectangle(canvas, (x, y), (x + w, y + h), THEME['panel_inspector'], -1, cv2.LINE_AA)
        cv2.line(canvas, (x, y), (x, y + h), THEME['border'], 1)

        # secoes
        for section_name, btns in self.sections:
            hx, hy, hw, hh = self.section_rects.get(section_name, (x + 4, y - 100, w - 8, 24))
            if self._visible(hy, hh, 0):
                draw_rounded_rect(canvas, hx, hy, hw, hh, 6, THEME['field'], -1)
                cv2.line(canvas, (hx+8, hy+hh-1), (hx+hw-8, hy+hh-1), THEME['border'], 1)
                arrow = '-' if self.expanded.get(section_name, True) else '+'
                cv2.putText(canvas, _ascii(f"{arrow} {section_name}"), (hx + 8, hy + 17),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.30, THEME['accent'] if self.expanded.get(section_name, True) else THEME['text_dim'], 1, cv2.LINE_AA)
            if not self.expanded.get(section_name, True):
                continue
            for btn in btns:
                if self._visible(btn.rect[1], btn.rect[3]):
                    btn.draw(canvas, self.font_scale, now=now)

        # FIX v11.4: cabecalho re-desenhado DEPOIS das secoes - com scroll, botoes
        # rolados para tras ficavam desenhados por cima do header (texto sobreposto)
        cv2.rectangle(canvas, (x, y), (x + w, y + 36), THEME['panel_toolbar'], -1, cv2.LINE_AA)
        cv2.putText(canvas, "Menu", (x + 14, y + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, THEME['text_main'], 1, cv2.LINE_AA)
        cv2.putText(canvas, "ANOTADORPAD", (x + w - 120, y + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.27, THEME['text_dim'], 1, cv2.LINE_AA)
        cv2.line(canvas, (x, y + 36), (x + w, y + 36), THEME['border'], 1)

        # barra de rolagem
        if self.max_scroll > 0:
            track_y0 = y + 42
            track_y1 = y + h - 8
            track_h = max(1, track_y1 - track_y0)
            thumb_h = max(28, int(track_h * (track_h / max(track_h, self.content_h))))
            thumb_y = track_y0 + int((track_h - thumb_h) * (self.scroll / self.max_scroll))
            cv2.rectangle(canvas, (x + w - 6, track_y0), (x + w - 3, track_y1), (235, 237, 241), -1)
            cv2.rectangle(canvas, (x + w - 6, thumb_y), (x + w - 3, thumb_y + thumb_h), (185, 192, 202), -1)

        # tooltip do botao em hover (desenhado por ultimo para ficar por cima)
        for btn in self.buttons:
            if btn.show_tooltip and btn.tooltip:
                self._draw_tooltip(canvas, btn)
                break

    def _draw_tooltip(self, canvas: np.ndarray, btn: SidebarButton):
        lines = []
        txt = _ascii(btn.tooltip)
        while len(txt) > 44:
            corte = txt.rfind(' ', 0, 44)
            if corte < 12:
                corte = 44
            lines.append(txt[:corte])
            txt = txt[corte:].lstrip()
        if txt:
            lines.append(txt)
        if not lines:
            return
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.30
        line_h = 15
        pad = 8
        title = _ascii(btn.label)
        box_w = min(300, max(190, max(len(l) for l in lines + [title]) * 7 + 20))
        box_h = 24 + len(lines) * line_h + 2 * pad
        # FIX v11.4: clamp contra as bordas da janela (antes o tooltip sumia
        # inteiro quando a sidebar encostava na direita)
        vh, vw = canvas.shape[:2]
        tx = self.rect[0] - box_w - 8
        ty = max(8, min(btn.rect[1], self.rect[1] + self.rect[3] - box_h - 8))
        if tx < 8:
            tx = self.rect[0] + self.rect[2] + 8
        tx = max(8, min(tx, vw - box_w - 8))
        ty = max(8, min(ty, vh - box_h - 8))
        cv2.rectangle(canvas, (tx+2, ty+3), (tx + box_w+2, ty + box_h+3), THEME['shadow'], -1, cv2.LINE_AA)
        draw_rounded_rect(canvas, tx, ty, box_w, box_h, 8, THEME['card'], -1)
        draw_rounded_rect(canvas, tx, ty, box_w, box_h, 8, (0, 0, 0), 1, THEME['accent'])
        cv2.rectangle(canvas, (tx+1, ty+1), (tx + box_w-1, ty + 23), THEME['field'], -1)
        cv2.putText(canvas, title[:40], (tx + 8, ty + 16), font, 0.32, THEME['accent'], 1, cv2.LINE_AA)
        yy = ty + 22 + 16
        for line in lines[:8]:
            cv2.putText(canvas, line, (tx + 8, yy), font, scale, THEME['text_dim'], 1, cv2.LINE_AA)
            yy += line_h

    def _area_conteudo(self, px: int) -> bool:
        """FIX v11.4: aceita cliques apenas na faixa de conteudo (abaixo do header,
        acima da borda inferior) - antes, a regua do header clicava secoes invisiveis."""
        x, y, w, h = self.rect
        return y + 42 <= px <= y + h - 8

    def handle_click(self, x: int, y: int) -> Optional[str]:
        if x < self.rect[0] or x > self.rect[0] + self.rect[2]:
            return None
        if not self._area_conteudo(y):
            return None
        # cabecalhos primeiro (recolher/expandir)
        for section_name, (hx, hy, hw, hh) in self.section_rects.items():
            if hx <= x <= hx + hw and hy <= y <= hy + hh and self._visible(hy, hh, 0):
                self.expanded[section_name] = not self.expanded.get(section_name, True)
                return None
        for btn in self.buttons:
            # FIX v11.4: botoes rolados para fora NAO recebem clique fantasma
            if self._visible(btn.rect[1], btn.rect[3]) and btn.hit(x, y) and btn.enabled:
                if btn.toggle:
                    btn.active = not btn.active
                return btn.action
        return None

    def handle_motion(self, x: int, y: int, now: float):
        for btn in self.buttons:
            # hover so em botoes realmente visiveis (tooltip de botao invisivel atrapalha)
            if self._visible(btn.rect[1], btn.rect[3]):
                btn.update_hover(x, y, now)
            else:
                btn.hover = False; btn.show_tooltip = False

    def handle_scroll(self, delta: int):
        self.scroll = max(0, min(self.max_scroll, self.scroll - delta * 42))

    def handle_key(self, key: int) -> Optional[str]:
        shortcuts = {
            ord('l'): 'abrir_proj', ord('o'): 'abrir_img',
            ord('d'): 'detectar', ord('s'): 'salvar',
            ord('g'): 'modo_comp', ord('v'): 'toggle_minimap',
            ord('h'): 'mascara', ord('0'): 'fit',
            ord('t'): 'toggle_ids', ord('j'): 'toggle_gpu',
            ord('r'): 'regua', ord(','): 'view_ant',
            ord('.'): 'view_prox',
        }
        return shortcuts.get(key)

    def toggle_section(self, section_name: str):
        self.expanded[section_name] = not self.expanded.get(section_name, True)

    def set_active(self, action: str, active: bool):
        for btn in self.buttons:
            if btn.action == action:
                btn.active = bool(active)


class ContextMenu:
    """Menu contextual (botao direito) para pads/componentes."""
    def __init__(self, font_scale: float = 1.0):
        self.font_scale = font_scale
        self.visible = False
        self.rect = (0, 0, 230, 0)
        self.items: List[Tuple[str, str, str, str]] = []  # (label, icon, action, kind)
        self.hover_idx = -1
        self.bounds = (1366, 768)

    def show(self, x: int, y: int, items: List[Tuple[str, str, str, str]], max_w: int = 230):
        self.items = items
        self.visible = True
        h = len(items) * 30 + 10
        w = max_w
        sw, sh = self.bounds
        if x + w > sw - 6:
            x = sw - w - 6
        # FIX v11.4: clamp correto mesmo com menu mais alto que a janela
        y = max(4, min(y, max(4, sh - h - 42)))
        self.rect = (max(4, x), y, w, h)
        self.hover_idx = -1
        self.visible = True

    def hide(self):
        self.visible = False
        self.hover_idx = -1

    def update_hover(self, x: int, y: int):
        if not self.visible:
            return
        idx = self.index_at(x, y)
        self.hover_idx = idx

    def index_at(self, x: int, y: int) -> int:
        rx, ry, rw, rh = self.rect
        if rx <= x <= rx + rw and ry <= y <= ry + rh:
            idx = (y - ry - 5) // 30
            if 0 <= idx < len(self.items):
                return idx
        return -1

    def draw(self, canvas: np.ndarray):
        if not self.visible:
            return
        x, y, w, h = self.rect
        cv2.rectangle(canvas, (x + 3, y + 4), (x + w + 3, y + h + 4), THEME['shadow'], -1, cv2.LINE_AA)
        draw_rounded_rect(canvas, x, y, w, h, 8, THEME['card'], -1)
        draw_rounded_rect(canvas, x, y, w, h, 8, (0, 0, 0), 1, THEME['border'])
        for i, (label, icon, action, kind) in enumerate(self.items):
            iy = y + 5 + i * 30
            if i == self.hover_idx:
                draw_rounded_rect(canvas, x + 4, iy, w - 8, 27, 5, (250, 242, 236), -1)
            cor = (38, 38, 190) if kind == 'danger' else THEME['text_main']
            if kind == 'success':
                cor = (40, 120, 50)
            txt = _ascii(f"{icon}  {label}")
            cv2.putText(canvas, txt[:38], (x + 12, iy + 19),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.31, cor, 1, cv2.LINE_AA)

    def hit(self, x: int, y: int) -> Optional[str]:
        if not self.visible:
            return None
        idx = self.index_at(x, y)
        if idx >= 0:
            return self.items[idx][2]
        return None


def criar_sidebar_padrao(x: int, y: int, w: int, h: int, font_scale: float) -> Sidebar:
    """Factory para sidebar padrao do AnotadorPad."""
    return Sidebar(x, y, w, h, font_scale)


def criar_menu_contexto_pad(font_scale: float) -> ContextMenu:
    """Menu contextual para pads (botao direito)."""
    menu = ContextMenu(font_scale)
    menu.items = [
        ('Editar medicao', 'E', 'editar', 'default'),
        ('Ciclar status (OK/SUSP/FALHA)', 'S', 'status_ciclo', 'action'),
        ('Conectar a outro pad', 'C', 'conectar', 'default'),
        ('Desconectar', 'X', 'desconectar', 'danger'),
        ('Duplicar pad', 'D', 'duplicar', 'default'),
        ('Isolar familia', 'F', 'isolar', 'action'),
        ('Nomear pino', 'I', 'pino_nomear', 'action'),
        ('Marcar/desmarcar GND', 'G', 'gnd_toggle', 'action'),
        ('Anotar neste pad', 'Y', 'anotar_pad', 'action'),
        ('Numerar pinos do componente', '#', 'comp_numerar', 'success'),
        ('Definir como pino 1', '1', 'comp_pino1', 'action'),
        ('Buscar datasheet', 'DS', 'comp_datasheet', 'action'),
        ('Remover pad', 'DEL', 'remover', 'danger'),
    ]
    return menu


def criar_menu_contexto_componente(font_scale: float) -> ContextMenu:
    """Menu contextual para componentes."""
    menu = ContextMenu(font_scale)
    menu.items = [
        ('Editar componente', 'E', 'comp_editar', 'default'),
        ('Reconhecer tipo', '?', 'comp_reconhecer', 'success'),
        ('Auto pino 1', '1', 'comp_auto_pino1', 'action'),
        ('Girar 90 graus', 'R', 'comp_girar', 'action'),
        ('Numerar pinos', '#', 'comp_numerar', 'success'),
        ('Exportar pinagem CSV', 'CSV', 'comp_pinagem', 'action'),
        ('Baixar datasheet', 'DS', 'comp_datasheet', 'action'),
        ('Definir pino 1', '1', 'comp_pino1', 'action'),
        ('Excluir componente', 'DEL', 'comp_excluir', 'danger'),
    ]
    return menu


def criar_menu_contexto_familia(font_scale: float) -> ContextMenu:
    """Menu contextual para familias (no painel de familias).

    FIX v11.4: 'fam_nova' e 'fam_excluir' tinham acoes sem handler no app
    (clique silencioso); eliminados. O painel de familias ja cria/exclui.
    """
    menu = ContextMenu(font_scale)
    menu.items = [
        ('Renomear', 'E', 'fam_rename', 'default'),
        ('Nova cor', 'C', 'fam_nova_cor', 'action'),
        ('Subir', '^', 'fam_up', 'action'),
        ('Descer', 'v', 'fam_down', 'action'),
    ]
    return menu
