# AnotadorPad v11 - Modular

Projeto dividido para facilitar manutenção e Git.

## Interface v11.7 (barra de ferramentas profissional)
- **Rail vertical de ferramentas** à esquerda (como Photoshop/Affinity): Navegar,
  Medir, Adicionar, Remover, Conectar, Desconectar, Anotar, Pino, GND e Componente,
  com estado ativo, agrupamento e tooltip
- **Barra de opções contextual** no topo: detecção, componentes, pad, visão, filtros
  e placa — cada bloco com legenda
- **Ações globais** na barra superior: Abrir, Projeto, Pasta, Salvar, Desfazer, Refazer, GPU, Menu
- **Dica contextual** na linha das abas explica o modo ativo
- **Área da imagem maior**: ferramentas saíram da barra e foram para o rail
- **Funções importantes visíveis**: Exemplo, Tiles, Vincular, Foto da visão,
  Datasheet, Auto pino 1, Reconhecer, Editar/Duplicar/Isolar, Camadas e Famílias
- **Dicas rápidas**: tooltip em ~0,45 s ao passar o mouse
- **Zoom flutuante** no canto inferior direito (`-  100%  +`; clique no % = fit)
- **Painel direito em cartões** (inspetor, editor de pad, componentes, famílias)
- **Menu lateral** com seções recolhíveis e botões grandes
- Atalhos continuam ativos mesmo sem aparecer no rótulo (mostrados no tooltip)

## Estrutura
```
anotador-modular/
├── main.py                # entry point
├── core/
│   ├── models.py          # Pad, Net, Componente dataclasses
│   ├── detector.py        # detectar_pads_com_mascara_v84
│   ├── geometry.py        # Viewport, zoom, pan
│   └── presets.py         # PRESETS_BANCADA_V84, PALETA_32
├── storage/
│   ├── loader.py          # carregar CSVs + compatibilidade v84..v10.3
│   ├── saver.py           # salvar CSV/PNG
│   └── session.py         # JSON sessão
├── ui/
│   ├── theme.py           # THEME, CORES
│   ├── widgets.py         # ButtonV5, Slider, Dropdowns
│   ├── canvas.py          # render
│   └── interactions.py    # mouse/teclado
└── app/
    └── app.py             # AppV11 (lógica principal)
```

## Rodar
```bash
python main.py imagem.jpg [pasta_projeto]
```

## O que foi corrigido nessa divisão
- Bug crítico de compatibilidade (measurements apagado)
- Zoom desacoplado do render
- right_w de 38% -> 24% (mais área de imagem)
- DEL robusto para Linux/Windows/Qt
- IDs menores, pads não selecionados 50% menor
- Linhas só aparecem na família selecionada

## Abrir outros projetos de placa
- Tecla **L** (ou botão "Abrir Proj") abre a lista de projetos encontrados no diretório atual
- Cada projeto mostra: pads, famílias, componentes e data da última sessão
- Carrega junto a imagem correta (img_path da sessão, `imagens/` próxima ou busca manual)
- Compatível com sessões `sessao_*.json`, `pads_final.csv` + `medicoes_final.csv`
  e projetos antigos com `pads.json` / `pads.csv` / `pads_v2.*`
- O zoom/pan é reajustado ao tamanho da imagem do projeto aberto

## Visões do projeto: FRENTE / VERSO / CONECTOR
- Abas no topo (teclas **3**, **4**, **5**) — cada visão tem **sua própria imagem**
  e suas próprias **anotações** (pads, medições, famílias, componentes)
- **Pré-visualização**: passe o mouse sobre a aba para ver a miniatura da imagem
- **6** ou botão "Foto Visao": define/troca a imagem da visão atual
- Ao trocar de visão a imagem é procurada automaticamente por nome
  (`*verso*`, `*back*`, `*conector*`, `*front*`...) em `imagens/` e na pasta do projeto
- Tudo é salvo no mesmo JSON: `views` + `view_atual` (compatível com sessões antigas,
  que passam a valer como visão FRENTE)

## Visual profissional (v11.1)
- **Pads**: forma real (elipse pelo tamanho do pad), preenchimento translúcido,
  anel de status e ponto central; **LOD** — visão geral mostra pontos discretos
  e os anéis completos aparecem com zoom
- **IDs dos pads**: pílulas escuras com borda na cor da família; aparecem
  automaticamente com zoom 1.2x+ ou na seleção/hover; alterna com **[T]**
- **Componentes**: formas reais desenhadas na placa (círculo, quadrado,
  retângulo H/V, triângulo, losango, hexágono), preenchimento translúcido,
  etiqueta `Símbolo Nome Valor`, linhas até os pinos e alças de seleção;
  preview ao arrastar para criar
- **Famílias**: lista com cor, ID, nome, nº de pads e contadores OK/SUSP/FALHA
  por família; seletor de cor em modal; indicador "1-9 de N"
- **Inspetor**: cartão de título com chip AUTO/MANUAL, status e família em
  badges, e valores alinhados por seção (ligada/desligada)
- **Placa centralizada** na área de desenho (Fit [0] também centraliza)

## Componentes, datasheet e reconhecimento
- **Menu → COMPONENTES** reúne: painel, novo componente, buscar datasheet,
  reconhecer tipo, auto pino 1 e exportar pinagem
- **Painel de componentes [G]**: lista os componentes da placa; clique para editar
- **Novo componente**: desenhe uma caixa em volta do componente na placa
- **Reconhecer tipo**: sugere capacitor, resistor, CI, conector, diodo, cristal,
  transistor ou LED usando nome (`C12`, `R5`, `U3`, `J1`...), marcação impressa
  (`LM358`, `BC547`, `1N4148`...), valor (`100nF`, `10k`, `8MHz`), forma desenhada,
  número de pinos e famílias conectadas
- **Auto pino 1**: escolhe o provável pino 1 pela forma do pad e posição no componente;
  sempre revise e ajuste manualmente se necessário
- **Datasheet [D]**: usa a marcação do componente; se não houver componente
  selecionado, digite o part number (`BC547`, `LM358`, `TDA7388`...)
- Os PDFs baixados vão para `<projeto>/datasheets/`; use **Pasta de datasheets**
  no menu para abrir
- O reconhecimento é **heurístico** (nome/marcação/valor/forma/pinos/famílias),
  não é visão artificial treinada para identificar componentes na foto

## Marcação de pinos, GND e anotações (estilo RastreCurve)
- **Anotar [Y]**: clique na placa para criar uma anotação livre; arraste para mover,
  duplo clique edita o texto e **Del** apaga a anotação selecionada
- **Pino [I]**: clique num pad e digite o nome/número do pino (`1`, `A3`, `VCC`...)
- **GND [U]**: clique num pad para marcar/desmarcar o terra; o pad fica com etiqueta
  verde e símbolo de terra
- **Numerar**: numera os pinos do componente selecionado a partir do **pino 1**
- **Mira**: liga/desliga a mira de precisão no cursor (destacada nos modos de marcação)
- Pinos e GND são **propagados automaticamente** para o pad passante da outra visão
- **Menu**: abre o menu lateral completo (projeto, visões, marcação, detecção,
  visualização, ferramentas, dados e configuração)
- Menu contextual (botão direito): editar, conectar, isolar, nomear pino, marcar GND,
  anotar no pad, definir pino 1, datasheet e remover
- Atalhos: **Y** anotar · **I** pino · **U** GND · **Del** apagar anotação · **Esc** cancela
- Relatório HTML e exportação de pinagem CSV incluem pino, GND e anotações

## Produtividade de bancada (v11.2)
- **Valores com unidades**: duplo clique num slider do editor para digitar
  `10k`, `4.7u`, `100nF`, `3V3`, `1M`, `2m2` — o app converte
- **Próximo sem medir** (`Ctrl+N`): salva a medição atual e abre o próximo pad pendente
- **Progresso**: barra de status com `MED x/y (%)` e falhas; card de progresso no inspetor
- **Camadas** (`Ctrl+L`): pads, IDs, cores de família, componentes, linhas, máscara
- **Paleta de comandos** (`Ctrl+K`): busca e executa qualquer ação
- **Recentes**: projetos usados aparecem com ★ no `[L]`; `python main.py` sem
  argumentos abre o último projeto
- **Recuperação de sessão**: autosave a cada 60 s; ao reabrir após queda, pergunta se recupera
- **Gravação atômica** da sessão (`.tmp` + replace) — evita JSON corrompido
- **Preferências globais** (`~/.pcb_painel.json`): GPU, IDs, camadas, escala, preset, recentes

## Recursos avançados (v11.2)
- **Régua / escala** (`R`): clique 2 pontos e informe a medida real em mm; passa a mostrar
  tamanho dos pads em mm e distâncias
- **Relatório HTML** (`7`): resumo por visão, famílias, componentes e medições
  (imprima para PDF pelo navegador)
- **Câmera** (`8`): captura um frame direto para a visão atual (USB/microscópio)
- **Comparar com placa ouro** (`9`): compara a visão atual com a referência e salva em `anomalias/`
- **Transferir anotações**: alinha por homografia (ORB+RANSAC) e move pads/componentes
  para uma foto nova da mesma face
- **Importar centroides** (CSV/KiCad): cria pads a partir de `Ref, Mid X, Mid Y, Side`
- **Detecção por tiles**: ideal para placas grandes; botão `Tiles` na aba CALIBRAR
- **Componentes**: arraste para mover, alças de canto para redimensionar, `GIRAR`,
  `PINAGEM CSV` (conector: pino → pad → família → status)
- **Testes automatizados**: `pytest tests` (46 testes) + lint objetivo no CI
- **Executável**: `build_exe.ps1` gera `dist\AnotadorPad.exe` com PyInstaller
  (não depende mais de arquivos fora do repositório)
  - O EXE não embute o stack de treino (`torch`/`ultralytics`) para ficar leve:
    pseudo-labels e detecção ONNX funcionam; o fine-tuning LoRA roda no Python

## Correções da auditoria v11.4
Auditoria profunda do projeto (estado/visões, armazenamento, interface, detectores)
corrigiu os seguintes bugs:

- **Del não apaga mais por engano**: setas/Home/F1-F12 (byte baixo 0 no Windows)
  e `Shift+S` não removem mais o pad/anotação selecionados
- **Undo agora desfaz a propagação** de pino/GND para as outras visões
  (o snapshot inclui o `views_store`)
- **Sessão corrompida é preservada**: vira `<arquivo>.corrompida_bak` e o app
  **não sobrescreve** o projeto ao fechar
- **Sessões antigas (sem views)**: anotações e `next_*` são carregados do
  top-level (antes eram perdidos ao salvar de novo)
- **`next_id`/`next_net_id`/`next_comp_id`/`next_anot_id`**: nunca ficam `None`
  (crash ao criar família/componente/anotação em sessões v8x) e `next_id` nunca
  é rebaixado (ids reutilizados não herdam medições órfãs)
- **Troca de visão** cancela inline input e confirmação de reset (não vazam
  para a visão errada)
- **Pan com botão esquerdo** não fica mais "preso" ao soltar; clique direito
  cancela arrastes pendentes
- **Clique que fecha menu contextual** não vaza mais para o canvas (não cria
  anotação/GND/drag sem querer)
- **Sidebar**: header não recebe mais clique fantasma de seções roladas;
  tooltip não some fora da janela; botoes fora da área visível são ignorados
- **CSV**: leitura com BOM (`utf-8-sig`), linhas curtas não descartam medições,
  CSV antigo sem coluna `manual` não marca tudo como manual, `pino/gnd/link`
  preservados em **todas** as rotas de carga, escrita atômica (`.tmp`+replace),
  componentes mantêm `cor/datasheet/marcacao/pino1/sugestao` no round-trip
- **Remover pad** limpa medição órfã e referências em componentes (`pads`, `pino1`)
- **Pino 1 sem pad selecionado** usa o pad mais próximo do clique (não mais um
  pad velho de seleção anterior)
- **Valor inválido no editor** (`edit_num_`) mostra aviso em vez de sumir em silêncio
- **Units**: notação resistiva `4R7`/`0R1` e `2.4g` (GHz) agora são interpretados
- **Homografia**: saneamento de cantos/determinante rejeita alinhamentos
  degradados (padrões repetitivos) que gravariam links errados
- **Detectores**: resize não gera dimensão 0 em imagens minúsculas; Viewport com
  imagem 0x0 não divide por zero; dedup do detector IA por IoU (pads cortados nas
  costuras dos tiles); ROI verde só é confiado se ≥3% da imagem
- **Widgets**: removidas definições duplicadas (a antiga `draw_rounded_rect`
  quadrada sombreava a correta); seta do preset de detecção corrigida; rótulos
  longos truncados; menus com clamp correto em janelas pequenas
- **Relatório HTML**: imagem com caminho seguro (`pathname2url`); medições
  ordenadas por pino natural (`pino10` depois de `pino2`)
- **Datasheet**: nome de arquivo sempre sanitizado (evita `OSError` silencioso
  e path traversal); download atômico com `.part`; PDF aceito com offset de bytes
- **Modelo de pad**: células vazias em CSV não derrubam a linha

## Detecção inteligente (smart)- **Smart [D]** (padrão): limiar de metal adaptativo (Otsu), remoção de texto/trilhas
  finas por espessura, rejeição de vias/furos por contorno interno e classificação
  de forma (círculo/retângulo/oval/polígono) com ângulo e score por pad
- **Exemplo**: clique num pad de referência na placa e use *Exemplo* — o app procura
  pads iguais por template matching multi-escala
- Ajuste de sensibilidade na paleta (`Ctrl+K`): "Sensibilidade smart +/-"
- Alternância Smart/Clássico também pela paleta (`modo_detector`)
- Comparativo na placa de teste: smart ~379 pads **sem os falsos de serigrafia** × clássico 566
  (o clássico inclui letras/texto); no verso de outra placa, smart 245 × 908 antes do filtro de texto

## Pasta de projetos (workspace)
- O app detecta automaticamente `PROJETOS` (ou `Projects`) ao lado do anotador e
  passa a abrir/explorar essa pasta no `[L]`
- Pastas com apenas fotos aparecem como **[NOVO]** — abrir cria o projeto ali
  mesmo (`sessao_v87.json` na pasta), sem precisar navegar
- Botão **"Pasta de projetos..."** no diálogo define/lembra outra pasta
- `python main.py IAW 9GV` também procura dentro da pasta de projetos

## Integração CAD: KiCad / Eagle / Gerber (v11.8)
- **Exportar KiCad** (grupo `PCB` na barra): gera `.kicad_pcb` com um *footprint*
  por componente, pads com forma/tamanho reais e as famílias como **nets**
  (`(net N "GND")`). O contorno da placa sai em `Edge.Cuts`.
- **Exportar Gerber**: gera RS-274X com os pads como flashes `D03`
  (aperturas C/R/O) em `<projeto>/gerber/`.
- **Importar**: aceita `.kicad_pcb`, `.brd` (Eagle) e `.gbr` (Gerber) —
  cria pads, componentes e famílias na visão atual (desfaz com `[Z]`).
- A escala vem da **Régua [R]** (`mm/px`). Sem calibração, exporta com 0.1 mm/px
  e importa encaixando o desenho na imagem (o aviso aparece na barra).
- CLI:
  - `anotador export-kicad <projeto> -o placa.kicad_pcb --escala 0.05`
  - `anotador export-gerber <projeto> -o cobre.gbr --escala 0.05`
  - `anotador import-pcb placa.kicad_pcb -o pcb_importado --escala 0.05`

## Pads passantes (frente ↔ verso)
- Ao trocar de visão, o app **alinha as fotos** (ORB + espelho) e vincula
  automaticamente os pads do **mesmo furo/pad** dos dois lados
- Pads vinculados mostram um losango branco e "Passante: VERSO #x" no inspetor
- **Famílias se propagam**: conectar/renomear/cor numa visão atualiza a outra
- **Medição se propaga**: medir num lado copia status/valores para o pad equivalente
- Manual: selecione um pad → `Ctrl+K` → "Vincular pad manual"; troque de visão,
  selecione o equivalente e repita
- `Ctrl+K` → "Auto-vincular pads passantes (on/off)" desliga/liga
- Navegação: **◀ ▶** ao lado das visões ou teclas **`,`** e **`.`**

## Diff viewer: frente ↔ verso com heatmap (v11.8)
- Botão **Diff frente x verso** (grupo `DIFF` na barra de opções): compara duas
  visões da mesma placa alinhando-as por ORB+RANSAC e gerando um mapa de
  diferença + heatmap (COLORMAP_JET).
- **Lado a lado**: mostra frente | verso com pads em verde (ref) e azul (alvo).
- **Sobreposto**: sobrepõe o heatmap de diferença na imagem da referência.
- Opções: `Recalcular` (executa o alinhamento/cálculo novamente) e ajuste de
  limiar de diferença. Requer imagem cadastrada em pelo menos 2 visões
  (use [6] Foto da Visão).
- Útil para encontrar pads ausentes, desalinhados ou oxidadas entre as faces
  da placa.

## Componente: marcação, pino 1 e datasheet (v11.2)
- No editor do componente, preencha a **Marcação** (código impresso, ex: `BC547`)
- **PINO 1**: clique no pad correspondente na placa e depois em `Pino 1` — o app
  marca **1** no pad na placa e passa a numerar a pinagem a partir dele
- **DATASHEET**: busca na internet (Bing) e mostra os resultados; escolha
  **Abrir** ou **Baixar PDF** (salva em `<projeto>/datasheets/`)
- Fallback automático de download (alguns sites como Mouser bloqueiam)
- A lista de componentes mostra `DS` quando há datasheet vinculado
- CLI: `py -3.11 tools/buscar_datasheet.py --termo BC547 --baixar C:\PCB_Painel\datasheets`

## IA treinável (suas 500 fotos → modelo)
Fluxo completo de *active learning*:
1. **Pré-anotar o álbum** (gera dataset YOLO com o detector smart):
   ```bash
   py -3.11 tools/exportar_dataset.py album --fotos "C:\caminho\do\album" --saida "C:\PCB_Painel\dataset_placas" --escala 0.7
   ```
   Também disponível no app: `Ctrl+K` → "Pre-anotar album de fotos (YOLO)".
2. **Exportar os projetos já corrigidos** (ground truth real):
   ```bash
   py -3.11 tools/exportar_dataset.py projetos --pastas C:\PCB_Painel --saida C:\PCB_Painel\dataset_projetos
   ```
   No app: `Ctrl+K` → "Exportar dataset YOLO".
3. **Treinar** (YOLO11 nano; CPU funciona, GPU/Colab acelera muito):
   ```bash
   py -3.11 -m pip install -r requirements_treino.txt
   py -3.11 tools/treinar_pads.py --dataset C:\PCB_Painel\dataset_placas --epochs 100 --imgsz 1024
   ```
   O best.pt é exportado para `models/pads.onnx`.
4. **Usar no app**: `Ctrl+K` → "Detector IA (modelo ONNX)" (ou `modo_detector_ia`).
   Para o EXE, copie `pads.onnx` + `pads.json` também para `anotador-modular\dist\models\`.
5. **Melhorar**: use a IA para pré-anotar novas fotos, corrija no app e re-exporte.

O dataset é gerado em **tiles de 1024** (preserva o tamanho real dos pads), com split
treino/validação por foto (sem vazamento), `data.yaml` e labels YOLO (classe `pad`).
HEIC é suportado (pillow-heif). Fotos com acento no caminho também.

## Detector IA (ONNX)

O detector IA usa um modelo YOLO exportado para ONNX. Ele **não vem treinado** para
a sua placa: é preciso treinar com fotos anotadas.

### Usar na interface
1. Aba **CALIBRAR** → grupo **DETECÇÃO** → botão **IA ONNX**
2. Se houver modelo, ele roda na hora e usa GPU/VRAM quando disponível
3. Se não houver, abra **Menu → DETECÇÃO → Escolher modelo** e aponte o `.onnx`
4. Também disponível na paleta **Ctrl+K** → "Detector IA (modelo ONNX)"

O app procura automaticamente por `models/pads.onnx` (recomendado) e
`models/pads_baseline.onnx` (modelo de teste fraco que acompanha o projeto,
treinado por apenas 12 épocas — serve só para validar o fluxo).

### Treinar um modelo útil
1. Anote os pads em várias fotos (use o detector Smart + revisão manual)
2. Exporte o dataset: **Menu → DADOS → Exportar dataset** (ou
   `py -3.11 tools/exportar_dataset.py projetos --pastas ... --saida ...`)
3. Treine:
   - **Colab (GPU grátis)**: abra `tools/Colab_Treinar_Pads.ipynb`
   - **Local**: `py -3.11 tools/treinar_pads.py --dataset C:\PCB_Painel\dataset_placas --epochs 100 --imgsz 1024`
4. Copie o `best.onnx` para `models/pads.onnx` e o `pads.json` (com `imgsz`) ao lado
   — ou use **Escolher modelo** no app
5. Clique **IA ONNX** e ajuste a confiança com a sensibilidade do Smart (paleta Ctrl+K)

### Backend GPU
- NVIDIA: CUDA se o OpenCV tiver suporte; senão OpenCL
- AMD/Intel: OpenCL (DNN_TARGET_OPENCL)
- Se o driver falhar na compilação dos kernels, o app repete a inferência na CPU
- O chip no rodapé mostra o backend ativo (`GPU AMD`, `GPU Intel`, `GPU NVIDIA`)

## GPU / VRAM
- **VRAM ligada por padrão** sempre que existir GPU (NVIDIA, AMD, Intel, Apple, Qualcomm)
- **NVIDIA**: usa CUDA quando o build do OpenCV tem suporte; senão OpenCL
- **AMD / Intel / outras**: OpenCL (T-API/UMat) nos wheels padrão do OpenCV
- **Inferência ONNX** também usa a GPU: `DNN_TARGET_CUDA` (NVIDIA) ou
  `DNN_TARGET_OPENCL` (AMD/Intel), com fallback automático para CPU se o driver falhar
- Renderizadores OpenCL de software (llvmpipe/SwiftShader) são detectados e não
  contam como GPU
- Botão **GPU [J]** liga/desliga manualmente; a escolha é salva na sessão
- O chip no canto inferior direito mostra o vendor (ex.: `GPU AMD`, `GPU Intel`,
  `GPU NVIDIA`, `GPU CUDA`)

## Cores das famílias
- Paleta com **40 cores** (as 8 Okabe-Ito, seguras para daltonismo, vêm primeiro)
- Família nova recebe automaticamente a primeira cor ainda não usada
- Cor **semântica** ao renomear: GND/DGND/AGND = cinza, VCC/VDD = vermelho,
  5V, 3V3, 12V, VBAT, VIN, SDA, SCL, MOSI, MISO, SCK, TX, RX
- No painel FAMÍLIAS: clique na família e escolha a cor no seletor (40 cores), "Nova cor" ou "Renomear"

## Abrir projeto direto pelo terminal
```bash
# projeto (detecta a imagem sozinho)
python main.py --projeto saida_pads_placa_teste_293a4f

# forma curta: primeiro argumento é uma pasta
python main.py saida_pads_v2

# imagem específica, se necessário
python main.py --projeto <pasta> --imagem imagens/placa_teste.jpg
```

## Sistema de Plugins (M1)
O AnotadorPad suporta plugins externos via **entry-points** (`anotadorpad.plugins`) e via pasta local `plugins/`.

### Como criar um plugin
Crie um arquivo `plugins/seu_plugin.py` com uma classe herdeira de `core.plugin_system.PluginBase`:

```python
from core.plugin_system import PluginBase

class SeuPlugin(PluginBase):
    name = "seu_plugin"
    version = "1.0.0"
    description = "Faz algo útil na placa"

    def get_cli_commands(self):
        return [("meu-comando", self.cli_meu_comando, "Ajuda")]

    def cli_meu_comando(self, app=None, **kwargs):
        print("Rodando plugin!")

    def get_toolbar_buttons(self):
        return [{"label": "Meu Botão", "key": "meu_botao", "kind": "action"}]

    def btn_meu_botao(self, app):
        app._flash("Plugin executado!", cor=(0,220,120), dur=3.0)

plugin = SeuPlugin()
```

O plugin é carregado automaticamente na inicialização e:
  * Seus comandos CLI ficam disponíveis em `anotador <comando>`
  * Seus botões aparecem na barra de opções (grupo `PLUGINS`)
  * Pode responder a hooks: `on_app_start`, `on_view_change`, `on_pad_detectado`, `on_salvar_sessao`, `on_exportar_pcb`

### Gerenciar plugins pelo CLI
```bash
# Lista plugins carregados
anotador plugin-list

# Detalhes de um plugin
anotador plugin-info resumo_placa

# Executa um comando de plugin
anotador plugin-exec resumo
```

### Plugin de exemplo incluído
O repositório vem com `plugins/resumo_placa.py` que exibe um resumo rápido de pads/famílias/componentes tanto via CLI (`anotador resumo`) quanto via botão na toolbar.

---

# Tutorial e Dicas

## Primeiros passos (5 min)

1. **Abra uma imagem de placa:**
   ```bash
   python main.py imagens/placa_teste.jpg
   ```
   Ou abra um projeto existente:
   ```bash
   python main.py --projeto saida_pads_placa_teste_293a4f
   ```

2. **Detecte os pads automaticamente:**
   Pressione **`D`** (Detectar) ou clique em **Detectar** na barra. Os pads aparecem como contornos verdes.

3. **Calibre a escala (opcional, mas recomendado):**
   Pressione **`R`**, clique em dois pontos de referência na placa e informe a medida real em mm. A partir daí, todos os pads mostram tamanho real e o export KiCad/Gerber fica correto.

4. **Salve o projeto:**
   Pressione **`S`** (Salvar). A sessão fica em `sessao_v87.json` dentro da pasta do projeto.

---

## Detecção de pads

| Método | Tecla | Quando usar |
|--------|-------|-------------|
| **Smart** (padrão) | `D` | Placas comuns, bom equilíbrio precisão/velocidade |
| **Por exemplo** | Selecione um pad bom → `Exemplo` | Placas com pads de tamanho/padrão muito específico |
| **Tiles** | `Tiles` | Placas grandes (detecta por blocos) |
| **IA ONNX** | `IA ONNX` | Após treinar um modelo com `anotador train` |

**Dicas:**
- Ajuste sensibilidade com `Sens +` / `Sens -` se faltarem pads ou houver muitos falsos positivos.
- Use `Tiles` se a placa ocupar quase toda a imagem.
- Pads detectados automaticamente ficam com `manual=False`; você pode marcá-los como manual depois.

---

## Marcação de pinos, GND e anotações

1. **Nomear pino:** Clique num pad → `I` → digite (ex: `A3`, `VCC`, `GND`).
2. **Marcar GND:** Clique num pad → `U` (alterna GND). A marcação propaga para o pad passante do outro lado se houver vinculação.
3. **Anotação livre:** `Y` → clique na placa → digite o texto. Útil para "verificar solda", "componente aquecido", etc.
4. **Numerar pinos de componente:** Selecione o componente → `Numerar pinos`. O app numera a partir do pino 1 definido.

---

## Componentes e datasheet

1. **Criar componente:** Modo `Componente` → arraste na placa ao redor dos pads do componente.
2. **Definir pino 1:** Clique no pad do pino 1 → `Pino 1`. A pinagem é numerada a partir dele.
3. **Reconhecer tipo:** Selecione o componente → `Reconhecer` (usa marcação/valor/forma).
4. **Buscar datasheet:** Selecione o componente → `Datasheet`. Busca na internet e oferece para baixar o PDF (salvo em `<projeto>/datasheets/`).

---

## Visões múltiplas (frente ↔ verso) e pads passantes

O app suporta até 3 visões por projeto: **Frente**, **Verso** e **Conector**.

1. **Adicionar imagem de outra visão:** `[6] Foto da Visão` → escolha Frente/Verso/Conector.
2. **Vincular pads passantes:** `Vincular visões` (auto) ou 2 cliques (manual). Pads do mesmo furo ficam vinculados.
3. **Propagação:** Quando você marca GND ou nomeia um pino em um lado, propaga automaticamente para o pad vinculado do outro lado.
4. **Alternar visões:** Teclas `3`, `4`, `5` ou `,` `.`

---

## Diff viewer: frente vs verso (QA de fabricação)

Útil para encontrar pads ausentes, desalinhados ou oxidados entre as faces.

1. Cadastre imagem em **Frente** e **Verso** (tecla `6`).
2. Clique em **Diff frente x verso** (grupo `DIFF` na barra).
3. Escolha **Lado a lado** ou **Sobreposto**.
4. Clique em **Recalcular** para executar o alinhamento (ORB+RANSAC) e gerar o heatmap.
5. Ajuste o **limiar de diferença** se necessário.

O resultado mostra qual percentual da placa difere entre as faces e destaca os pads diferentes.

---

## Exportação para KiCad / Gerber

1. Calibre a escala com a Régua `[R]` (sem escala, usa 0,1 mm/px com aviso).
2. **KiCad:** `Exportar KiCad` → gera `.kicad_pcb` com footprints e nets (famílias).
3. **Gerber:** `Exportar Gerber` → gera RS-274X com flashes C/R/O, salvo em `<projeto>/gerber/`.
4. Pelo CLI:
   ```bash
   anotador export-kicad <projeto> -o placa.kicad_pcb --escala 0.05
   anotador export-gerber <projeto> -o cobre.gbr --escala 0.05
   ```

---

## Active Learning (IA) — loop completo

Se você tem muitas placas para anotar:

1. **Pré-anotar álbum:** `Pré-anotar álbum` gera um dataset YOLO com o detector smart.
2. **Treinar modelo:** `anotador train <dataset> --epochs 100` → gera `models/pads.onnx`.
3. **Usar IA:** `IA ONNX` na barra detecta com o modelo treinado.
4. **Validar AL:** `Validar AL` → clique em pseudo-labels para aprovar ou rejeitar.
5. **Pseudo-label:** `Pseudo-Label` → gera anotações automáticas de alta confiança.
6. **Treinar LoRA:** `Treinar LoRA` → fine-tune rápido do modelo com dados validados.

---

## Sistema de Plugins (M1)

Crie plugins em `plugins/seu_plugin.py` (herdando `core.plugin_system.PluginBase`). Eles são carregados automaticamente e podem:
- Adicionar comandos CLI (`anotador plugin-list`, `plugin-info`, `plugin-exec`)
- Adicionar botões na toolbar (grupo `PLUGINS`)
- Responder a hooks: `on_app_start`, `on_view_change`, `on_pad_detectado`, `on_salvar_sessao`, `on_exportar_pcb`

Exemplo pronto: `plugins/resumo_placa.py`.

---

## Atalhos de teclado (resumo)

| Tecla | Ação |
|-------|------|
| `L` | Lista de projetos |
| `O` | Abrir imagem |
| `S` | Salvar sessão |
| `D` | Detectar pads |
| `R` | Régua / calibrar escala mm-por-px |
| `3` `4` `5` | Trocar visão Frente / Verso / Conector |
| `6` | Foto da visão |
| `J` | Ligar/desligar GPU |
| `T` | Mostrar/ocultar IDs dos pads |
| `I` | Nomear pino |
| `U` | Marcar/desmarcar GND |
| `Y` | Anotar |
| `Z` | Desfazer |
| `Ctrl+Z` / `Ctrl+Y` | Desfazer / Refazer |
| `Ctrl+K` | Paleta de comandos (busca qualquer ação) |
| `7` | Relatório HTML |
| `8` | Câmera |
| `9` | Comparar com placa ouro |
| `Esc` | Voltar ao modo navegar |
| `X` da janela | Fechar o aplicativo |

---

## Dicas de produtividade

- **Use `Ctrl+K`** para buscar qualquer ação rapidamente sem navegar por menus.
- **Calibre sempre a escala** antes de exportar KiCad/Gerber; sem ela, as medidas ficam em 0,1 mm/px.
- **Use desfazer (`Z`) liberalmente**: a propagação de GND/pino entre visões também é desfeita.
- **Pads vinculados** (passantes) mostram um losango branco; aproveite para não anotar duas vezes o mesmo furo.
- **Relatório HTML (`7`)**: imprima para PDF pelo navegador e leve para a bancada de produção.
- **Não feche o EXE pelo Gerenciador de Tarefas**: use o botão `X` da janela para garantir que a sessão seja salva corretamente.
- **Sessões são salvas automaticamente** a cada 60 s (autosave) e de forma atômica (não corrompem se houver queda de energia).

---

## Solução de problemas

| Problema | Solução |
|----------|---------|
| O EXE não abre ou some silenciosamente | O console fica aberto 10 s se houver erro. Rode pelo terminal para ver a mensagem. |
| Nenhum pad detectado | Aumente a sensibilidade (`Sens +`) ou tente `Tiles`. Verifique brilho/contraste da foto. |
| Pads do verso não aparecem alinhados | Use `Vincular visões` ou ajuste a imagem com `Foto da Visão`. |
| Export KiCad sem pads | Verifique se há pads detectados na visão atual e se a escala está calibrada. |
| Tkinter indisponível | O app cai para entrada por console (digite o caminho quando solicitado). |
| Sessão corrompida | Ela é renomeada para `.corrompida_bak` e o projeto original é preservado. |
| GPU não detectada | O app usa OpenCL (AMD/Intel) ou fallback CPU. O botão `GPU [J]` mostra o status. |


