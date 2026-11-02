import cv2

PRESETS_BANCADA_V84 = {
    'preset_smd': {"scale": 70, "brilho_min": 140, "brilho_max": 255, "sat_max": 50, "area_min": 6, "area_max": 250, "nms_dist": 14, "label":"SMD DENSO", "desc":"Placa verde moderna, pads 0402/0603. Rejeita vias.", "reject_vias": True},
    'preset_ecu': {"scale": 60, "brilho_min": 150, "brilho_max": 255, "sat_max": 70, "area_min": 12, "area_max": 450, "nms_dist": 16, "label":"ECU VERNIZ", "desc":"ECU com verniz brilhante, pads médios.", "reject_vias": True},
    'preset_fenolite': {"scale": 50, "brilho_min": 100, "brilho_max": 225, "sat_max": 85, "area_min": 25, "area_max": 900, "nms_dist": 20, "label":"FENOLITE ANT.", "desc":"Fenolite marrom antiga, pads grandes.", "reject_vias": False},
    'preset_painel': {"scale": 65, "brilho_min": 130, "brilho_max": 250, "sat_max": 60, "area_min": 20, "area_max": 700, "nms_dist": 18, "label":"PAINEL/CONEC.", "desc":"Painel/conector, trilhas largas.", "reject_vias": True},
    'preset_vias_off': {"scale": 70, "brilho_min": 135, "brilho_max": 255, "sat_max": 55, "area_min": 8, "area_max": 300, "nms_dist": 15, "label":"ANTI-VIA", "desc":"Rejeita furos/vias.", "reject_vias": True},
}

PALETA = [
    ('Azul', (255, 100, 0)), ('Azul-claro', (255, 200, 120)), ('Ciano', (220, 220, 0)),
    ('Turquesa', (200, 200, 60)), ('Roxo', (200, 0, 200)), ('Violeta', (180, 60, 220)),
    ('Magenta', (255, 0, 200)), ('Rosa', (200, 100, 255)), ('Branco', (240, 240, 240)), ('Cinza', (160, 160, 160)),
]

# Paleta Okabe-Ito - alto contraste e segura para daltonismo (CB-safe)
# Usada primeiro para famílias novas; depois completa com a PALETA_32
OKABE_ITO = [
    ('Laranja OK', (0, 159, 230)), ('Azul Céu OK', (233, 180, 86)), ('Verde Água OK', (115, 158, 0)), ('Amarelo OK', (66, 228, 240)),
    ('Azul OK', (178, 114, 0)), ('Vermelhão OK', (0, 94, 213)), ('Roxo OK', (167, 121, 204)), ('Cinza OK', (170, 170, 170)),
]

_CORES_EXTRA = [
    ('Azul Vivo',(255,80,0)),('Azul Claro',(255,180,80)),('Ciano Neon',(220,220,0)),('Turquesa',(200,200,60)),
    ('Verde Lima',(80,220,80)),('Verde Floresta',(40,180,40)),('Amarelo Ouro',(0,215,255)),('Laranja',(0,140,255)),
    ('Roxo Neon',(200,0,200)),('Violeta',(180,60,220)),('Magenta',(255,0,200)),('Rosa Choque',(180,80,255)),
    ('Rosa Claro',(200,120,255)),('Vermelho',(0,0,255)),('Vermelho Claro',(80,80,255)),('Branco',(240,240,240)),
    ('Cinza Claro',(180,180,180)),('Cinza',(140,140,140)),('Coral',(80,80,255)),('Salmon',(100,100,255)),
    ('Dourado',(0,180,255)),('Lime',(100,255,100)),('Menta',(150,255,150)),('Teal',(180,180,0)),
    ('Lavanda',(255,120,180)),('Pêssego',(120,160,255)),('Oliva',(60,120,120)),('Cobre',(50,100,180)),
    ('Prata',(192,192,192)),('Bronze',(60,130,200)),('Indigo',(180,0,100)),('Esmeralda',(80,180,80)),
]
# 40 opções: 8 CB-safe + 32 clássicas
PALETA_32 = OKABE_ITO + _CORES_EXTRA

THEME = {'bg':(243,244,246), 'panel_tab':(250,250,251), 'panel_toolbar':(255,255,255),
         'panel_inspector':(250,250,251), 'panel_status':(255,255,255),
         'text_main':(40,44,52), 'text_dim':(118,124,134),
         'accent':(235,99,37), 'accent_hover':(250,150,90), 'success':(74,163,22), 'danger':(38,38,220),
         'border':(223,226,231), 'card':(255,255,255), 'card_alt':(246,247,249), 'field':(243,244,246),
         'shadow':(226,228,233), 'accent_soft':(252,238,229)}

COMPONENTES_TIPOS = {
    "capacitor": {"nome":"Capacitor","simbolo":"C","cor":(80,140,255)},
    "resistor": {"nome":"Resistor","simbolo":"R","cor":(255,120,80)},
    "ci": {"nome":"CI","simbolo":"U","cor":(80,255,120)},
    "conector": {"nome":"Conector","simbolo":"J","cor":(255,200,80)},
    "diodo": {"nome":"Diodo","simbolo":"D","cor":(255,80,120)},
    "cristal": {"nome":"Cristal","simbolo":"Y","cor":(120,80,255)},
    "transistor": {"nome":"Transistor","simbolo":"Q","cor":(80,255,255)},
    "led": {"nome":"LED","simbolo":"L","cor":(0,255,255)},
}

# Cores semânticas por nome de net (comparação normalizada: sem espaço/hífen/_)
CORES_SEMANTICAS = {
    'GND': (100,100,100), 'VCC': (0,0,255), '5V': (0,140,255), '3V3': (0,215,255), '12V': (0,60,255),
    'VBAT': (0,90,200), 'VIN': (0,120,255), 'SDA': (255,100,0), 'SCL': (255,200,120),
    'MOSI': (255,0,200), 'MISO': (200,100,255), 'SCK': (220,220,0), 'TX': (80,220,80), 'RX': (180,80,255),
}

_MAPA_SEMANTICO = {
    'GND':'GND','DGND':'GND','AGND':'GND','GNDA':'GND',
    'VCC':'VCC','VDD':'VCC','3V3':'3V3','3.3V':'3V3','33V':'3V3','5V':'5V','5VOLT':'5V','12V':'12V',
    'VBAT':'VBAT','VIN':'VIN','SDA':'SDA','SCL':'SCL','MOSI':'MOSI','MISO':'MISO',
    'SCK':'SCK','SCLK':'SCK','TX':'TX','TXD':'TX','RX':'RX','RXD':'RX',
}


def cor_semantica(nome):
    """Cor sugerida pelo nome da família (GND, VCC, 3V3, SDA...) ou None."""
    if not nome:
        return None
    chave = str(nome).strip().upper().replace(' ', '').replace('-', '').replace('_', '')
    canonica = _MAPA_SEMANTICO.get(chave)
    if not canonica:
        return None
    cor = CORES_SEMANTICAS.get(canonica)
    return tuple(cor) if cor else None


FORMAS_COMPONENTE = [
    ("circulo","Capacitor"),
    ("quadrado","Resistor"),
    ("retangulo_h","CI Horizontal"),
    ("retangulo_v","Conector Vertical"),
    ("triangulo","Diodo"),
    ("losango","Cristal"),
    ("hexagono","Transistor"),
]

# Cores status
CORES_STATUS={"OK":(0,200,0),"SUSP":(0,200,255),"FALHA":(0,0,220),None:(160,160,160)}

DESCRICOES_BOTOES = {
    'abrir_img': ("ABRIR IMAGEM [O]", ["Cria um projeto novo a partir de uma foto", "JPG, PNG, BMP, TIFF", "Cria pasta saida_pads_*"]),
    'abrir_proj': ("ABRIR PROJETO [L]", ["Lista os projetos de placas encontrados", "Carrega pads, medições, famílias e imagem", "Duplo clique para abrir", "Ou escolha qualquer pasta"]),
    'abrir_pasta': ("PASTA SAÍDA [K]", ["Abre pasta no Explorer", "CSV + PNG numerado"]),
    'toggle_minimap': ("MINIMAPA [V]", ["Mostra/esconde preview", "Topo-direito da placa", "Clique para navegar"]),
    'toggle_gpu': ("GPU / VRAM [J]", ["Liga/desliga a aceleracao por GPU", "NVIDIA: CUDA ou OpenCL", "AMD/Intel/outras: OpenCL", "Ligada por padrao quando existe GPU"]),
    'tab_calibrar': ("ABA CALIBRAR [1]", ["Detecção automática", "Ajuste filtros", "Presets"]),
    'tab_anotar': ("ABA ANOTAR [2]", ["Medição e anotação", "Conectar famílias"]),
    'modo_nav': ("NAVEGAR [N]", ["Navegação padrão", "Clique seleciona pad", "Meio arrasta = pan"]),
    'modo_add': ("ADICIONAR [A]", ["Adiciona pad manual", "Não apagado por Detectar"]),
    'modo_move': ("MOVER [M]", ["Move pad arrastando", "Só aba CALIBRAR"]),
    'modo_del': ("REMOVER [Del]", ["Remove pad", "Remove de famílias", "Undo [Z]"]),
    'detectar': ("DETECTAR [D]", ["Detecta no modo atual", "Smart (auto) ou Clássico", "Preserva manuais", "Usa GPU se ativa"]),
    'detectar_smart': ("SMART", ["Detector inteligente", "Limiar adaptativo (Otsu)", "Rejeita vias/furos e texto fino", "Forma/ângulo/score por pad"]),
    'modo_detector_ia': ("DETECTOR IA (ONNX)", ["Detecta pads com modelo YOLO em ONNX", "Usa GPU/VRAM (CUDA ou OpenCL)", "Sem modelo: Menu > DETECCAO > Escolher modelo", "Atalho na paleta Ctrl+K"]),
    'modelo_ia_escolher': ("ESCOLHER MODELO IA", ["Aponta para qualquer arquivo .onnx", "Ex.: best.onnx exportado do treino YOLO", "O caminho fica salvo nas preferencias", "Depois clique em IA ONNX"]),
    'detectar_exemplo': ("EXEMPLO", ["Clique num pad bom na placa", "Depois clique em Exemplo", "Procura pads iguais (multi-escala)"]),
    'modo_detector': ("MODO DETECTOR", ["Alterna Smart / Clássico", "Também na paleta Ctrl+K"]),
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
    'modo_comp': ("COMPONENTE [G]", ["Desenha componentes na placa", "Arraste para criar", "Clique no componente para mover", "Alças de canto redimensionam"]),
    'anomalias': ("ANOMALIAS", ["Compara com placa de referência", "Detector de anomalias visual", "Resultados em anomalias/"]),
    'toggle_gpu': ("GPU / VRAM [J]", ["Liga/desliga a aceleracao por GPU", "NVIDIA: CUDA ou OpenCL", "AMD/Intel/outras: OpenCL", "Ligada por padrao quando existe GPU"]),
    'toggle_ids': ("IDs DOS PADS [T]", ["Liga/desliga numeração dos pads", "Com zoom 1.2x+ aparecem todos", "Seleção/hover sempre mostram o ID"]),
    'detectar_smart': ("SMART", ["Detector inteligente (padrão)", "Limiar de metal adaptativo (Otsu)", "Rejeita texto de serigrafia e vias", "Forma, ângulo e score por pad"]),
    'detectar_exemplo': ("EXEMPLO", ["Clique num pad bom na placa", "Depois clique em Exemplo", "Procura pads iguais (multi-escala)"]),
    'detectar_tiles': ("TILES", ["Detecção por blocos (placas grandes)", "Roda o detector em tiles de 1800px", "Funde resultados com NMS"]),
    'prox_pendente': ("PROX [CTRL+N]", ["Salva a medição atual", "Abre o próximo pad sem medir", "Fluxo contínuo de bancada"]),
    'camadas': ("CAMADAS [CTRL+L]", ["Liga/desliga camadas", "Pads, IDs, famílias, componentes,", "linhas e máscara"]),
    'view_img': ("FOTO DA VISÃO [6]", ["Define/troca a foto da visão atual", "Verso, frente ou conector", "Mantém as outras visões"]),
    'relatorio': ("RELATÓRIO [7]", ["Gera relatório HTML do projeto", "Famílias, medições e componentes", "Imprima em PDF pelo navegador"]),
    'camera': ("CÂMERA [8]", ["Captura da webcam/microscópio", "SPACE captura, ESC cancela", "Vira imagem da visão atual"]),
    'comparar_ouro': ("COMPARAR OURO [9]", ["Compara com placa de referência", "Usa detector de anomalias", "Salva resultado em anomalias/"]),
    'transferir': ("TRANSFERIR ANOTAÇÕES", ["Alinha uma foto nova da mesma face", "Move pads/componentes por homografia", "Bom para refazer fotos"]),
    'importar_centroides': ("IMPORTAR CENTROIDES", ["Lê CSV/KiCad (Ref, X, Y, Side)", "Cria pads nas posições", "Usa escala mm/px se calibrada"]),
    'export_kicad': ("EXPORTAR KICAD", ["Gera .kicad_pcb do projeto", "Pads viram footprints com nets", "Use a Régua [R] p/ escala real"]),
    'export_gerber': ("EXPORTAR GERBER", ["Gera Gerber RS-274X do cobre", "Pads como flashes C/R/O", "Salva em <projeto>/gerber/"]),
    'import_pcb': ("IMPORTAR PCB", ["Lê KiCad, Eagle (.brd) e Gerber", "Cria pads, componentes e famílias", "Adiciona à visão atual (undo [Z])"]),
    'modo_al_validar': ("VALIDAR AL [V]", ["Modo validação Active Learning", "Clique em pseudo-label para aprovar", "Clique em vazio para criar novo", "Clique com botão direito para rejeitar"]),
    'al_pseudo': ("PSEUDO-LABEL [P]", ["Gera pseudo-labels automáticos", "Usa detecções com confiança > 0.8", "Converte para anotações amarelas"]),
    'al_train': ("TREINAR LoRA [T]", ["Fine-tuning LoRA do modelo IA", "Usa labels humanos + pseudo-labels", "Salva modelo atualizado em models/"]),
    'regua': ("RÉGUA [R]", ["Clique 2 pontos e informe mm", "Calibra escala mm/por-px", "Mostra tamanho real dos pads"]),
    'paleta': ("COMANDOS [CTRL+K]", ["Busca qualquer ação", "Digite para filtrar", "Enter executa"]),
    'exportar_dataset': ("EXPORTAR DATASET", ["Gera dataset YOLO dos projetos", "Tiles 1024 + labels", "Use para treinar a IA"]),
    'pre_anotar_album': ("PRÉ-ANOTAR ÁLBUM", ["Pré-anota fotos com o smart", "Gera dataset YOLO", "Para 500+ fotos use o CLI"]),
    'modo_detector_ia': ("DETECTOR IA", ["Usa modelo ONNX treinado", "models/pads.onnx", "Requer dataset + treino"]),
    'smart_sens_mais': ("SENS +", ["Aumenta sensibilidade do smart", "Mais pads (mais falsos)"]),
    'smart_sens_menos': ("SENS -", ["Diminui sensibilidade do smart", "Menos pads (mais precisão)"]),
    'recuperar_ultimo': ("ÚLTIMO PROJETO", ["Reabre o último projeto usado", "Também abre sem argumentos"]),
    'edit_salvar': ("SALVAR", ["Salva a medição do pad", "Atalho: Enter"]),
    'edit_cancelar': ("CANCELAR", ["Sai do editor sem salvar", "Atalho: Esc"]),
    'edit_limpar': ("LIMPAR", ["Zera sliders e campos", "Não salva até SALVAR"]),
    'st_0': ("STATUS VAZIO", ["Pad sem medição"]),
    'st_1': ("STATUS OK", ["Componente/medição aprovada"]),
    'st_2': ("STATUS SUSP", ["Suspeita - verificar"]),
    'st_3': ("STATUS FALHA", ["Componente/medição com falha"]),
    'edit_field_forma': ("FORMA DE ONDA", ["Ex: DC, senoidal, quadrada", "Clique para digitar"]),
    'edit_field_cont': ("CONTINUIDADE", ["Ex: OK, ABERTO, CURTO", "Clique para digitar"]),
    'edit_field_obs_lig': ("OBS LIGADA", ["Anotação com placa energizada"]),
    'edit_field_obs_des': ("OBS DESLIGADA", ["Anotação com placa desenergizada"]),
    'comp_salvar': ("SALVAR COMPONENTE", ["Confirma nome/valor/tipo", "Atualiza na placa"]),
    'comp_cancelar': ("CANCELAR", ["Sai da edição do componente"]),
    'comp_excluir': ("EXCLUIR", ["Remove o componente", "Undo [Z] desfaz"]),
    'comp_girar': ("GIRAR 90°", ["Rotaciona a caixa do componente", "Alterna retângulo H/V"]),
    'comp_pinagem': ("PINAGEM CSV", ["Exporta pino → pad → família → status", "Útil para conectores"]),
    'comp_field_nome': ("NOME", ["Nome do componente (C1, R5...)"]),
    'comp_field_valor': ("VALOR", ["Ex: 10k, 100nF, BC547"]),
    'comp_field_tensao': ("TENSÃO", ["Ex: 16V, 25V"]),
    'comp_field_pinos': ("PINOS", ["IDs dos pads vinculados", "Ex: 1,2,3"]),
    'comp_field_obs': ("OBSERVAÇÃO", ["Notas do componente"]),
    'comp_field_marcacao': ("MARCAÇÃO", ["Código impresso no componente", "Ex: BC547, TLE4275, LM358", "Usado para buscar o datasheet"]),
    'comp_pino1': ("PINO 1", ["Clique no pad que é o pino 1", "Depois clique neste botão", "Marca 1 na placa e ordena pinagem"]),
    'comp_datasheet': ("DATASHEET", ["Busca o datasheet na internet", "Usa a marcação do componente", "Abrir no navegador ou baixar PDF"]),
    'vincular_views': ("VINCULAR VISÕES", ["Alinha frente/verso/conector", "Vincula pads do mesmo furo", "Famílias passam a se propagar", "Também na paleta Ctrl+K"]),
    'vincular_manual': ("VÍNCULO MANUAL", ["Selecione um pad e clique aqui", "Troque de visão, selecione o outro", "Clique aqui de novo para vincular"]),
    'view_ant': ("VISÃO ANTERIOR", ["Troca para a visão anterior", "Atalho: tecla ,"]),
    'view_prox': ("PRÓXIMA VISÃO", ["Troca para a próxima visão", "Atalho: tecla ."]),
    'toggle_auto_vincular': ("AUTO-PASSANTES", ["Liga/desliga vínculo automático", "Ao trocar frente/verso, liga os", "pads do mesmo furo automaticamente"]),
    'fam_up': ("SUBIR", ["Rola a lista para cima"]),
    'fam_down': ("DESCER", ["Rola a lista para baixo"]),
    'fam_nova_cor': ("NOVA COR", ["Próxima cor da paleta"]),
    'fam_rename': ("RENOMEAR", ["Digite o nome da família", "GND/VCC/3V3 aplicam cor semântica"]),
    'fam_voltar': ("VOLTAR", ["Fecha o painel atual"]),
    'comp_up': ("SUBIR", ["Rola a lista de componentes"]),
    'comp_down': ("DESCER", ["Rola a lista de componentes"]),
    'comp_nova': ("NOVA", ["Entra no modo de desenhar componente"]),
    'redo': ("REDO [CTRL+Y]", ["Refaz a última ação desfeita", "Também tecla ]"]),
    'modo_anot': ("ANOTAR [Y]", ["Cria anotações livres na placa", "Clique para criar, arraste para mover", "Duplo clique edita o texto", "Del apaga a anotação selecionada"]),
    'modo_pino': ("NOMEAR PINO [I]", ["Clique num pad para dar nome/número", "Ex: 1, A3, VCC, SDA", "Propaga para o pad passante da outra visão"]),
    'modo_gnd': ("MARCAR GND [U]", ["Clique num pad para marcar/desmarcar GND", "O terra fica verde na placa", "Propaga para o pad passante da outra visão"]),
    'pin_numerar': ("NUMERAR PINOS", ["Numera os pinos do componente", "Começa pelo pino 1 definido", "Segue a ordem da pinagem", "Propaga para as outras visões"]),
    'toggle_mira': ("MIRA DE PRECISÃO", ["Liga/desliga a mira no cursor", "Ajuda a acertar pads pequenos", "Fica destacada nos modos de marcação"]),
    'anot_limpar': ("LIMPAR ANOTAÇÕES", ["Remove todas as anotações da visão", "Undo [Z] restaura"]),
    'sidebar': ("MENU", ["Abre/fecha o menu lateral completo", "Projeto, visões, marcação, detecção,", "ferramentas, dados e configuração"]),
    'comp_numerar': ("NUMERAR PINOS", ["Numera os pinos do componente", "Usa o pino 1 como referência", "Atualiza a pinagem do conector"]),
    'pino_nomear': ("NOMEAR PINO", ["Digite o nome/número do pino", "Ex: 1, A3, VCC", "Propaga entre frente/verso"]),
    'gnd_toggle': ("GND", ["Marca/desmarca este pad como terra", "Atalho do menu: G", "Propaga entre frente/verso"]),
    'anotar_pad': ("ANOTAR NO PAD", ["Cria uma anotação ao lado deste pad", "Digite o texto e Enter"]),
    'status_ciclo': ("STATUS", ["Cicla o status do pad", "VAZIO -> OK -> SUSP -> FALHA"]),
    'comp_painel': ("PAINEL DE COMPONENTES [G]", ["Lista os componentes da placa", "Clique num componente para editar", "Novo: desenhe uma caixa na placa"]),
    'comp_reconhecer': ("RECONHECER TIPO", ["Sugere o tipo do componente", "Usa nome (C12, R5, U3...), marcacao, valor,", "forma, numero de pinos e familias conectadas"]),
    'comp_auto_pino1': ("AUTO PINO 1", ["Detecta o provavel pino 1", "Considera pad retangular e posicao", "Sempre revise; pode ajustar manualmente"]),
    'datasheet_livre': ("DATASHEET LIVRE", ["Busca datasheet por part number", "Ex: BC547, LM358, TDA7388", "Nao precisa ter componente cadastrado"]),
    'datasheets_pasta': ("PASTA DE DATASHEETS", ["Abre a pasta <projeto>/datasheets", "PDFs baixados ficam salvos ali"]),
    'comp_datasheet': ("DATASHEET [D]", ["Busca datasheet na internet", "Usa a marcacao do componente", "Sem componente: digite o part number", "Abrir no navegador ou baixar PDF"]),
}

# FIX v11.4: removida a classe DropdownPaleta morta deste modulo (setas nao-ASCII
# que o cv2 nao desenha e duplicata de ui/widgets.DropdownPaleta, a usada pelo app)

