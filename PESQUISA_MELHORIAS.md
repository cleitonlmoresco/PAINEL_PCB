# Relatório de Pesquisa: Melhorias para AnotadorPad v11.7

## Visão Geral do Estado Atual

**Tamanho do projeto:** ~6.500 linhas Python (app.py ~4.700 linhas + 20 módulos de apoio)
**Arquitetura:** Monolítica OpenCV + numpy, GUI custom via cv2.imshow, serialização JSON/CSV
**ML:** Detecção "Smart" (OpenCV tradicional) + Detector IA ONNX (YOLO via cv2.dnn)
**GPU:** OpenCL/UMat (AMD/Intel) + CUDA opcional (NVIDIA) + OpenCL para DNN
**Serialização:** JSON (sessão multi-view) + CSV (pads/medidas/componentes)
**Testes:** 40 testes pytest (smoke, regressão, units, detector, datasheet, etc.)
**Empacotamento:** PyInstaller one-file (~111MB)

---

## MATRIZ DE MELHORIAS PRIORIZADA

### 🔴 CRÍTICO (Risco de perda de dados / usabilidade bloqueante)

| # | Melhoria | Impacto | Esforço | Descrição |
|---|----------|---------|---------|-----------|
| C1 | **Backup automático antes de sobrescrever sessão/CSV** | Previne perda irrecuperável | Baixo | Antes de `os.replace()` em saver/session, criar `.bak` com timestamp; rotação de 5 backups |
| C2 | **Validação de integridade ao carregar sessão** | Evita sessões corrompidas silenciosas | Baixo | Checksum SHA256 no JSON da sessão; validação de schema (pydantic/jsonschema) |
| C3 | **Undo/Redo transacional (atomic)** | Evita estados inconsistentes | Médio | Snapshot completo (views_store + all state) no undo stack; teste de stress 1000 ops |
| C4 | **Persistência de preferências atômica + schema** | Evita prefs corrompidas | Baixo | jsonschema para prefs; migração automática v1→v2 |

### 🟠 ALTO (Gargalo de produtividade / qualidade)

| # | Melhoria | Impacto | Esforço | Descrição |
|---|----------|---------|---------|-----------|
| A1 | **Pipeline de treino end-to-end (CLI único)** | Reduz fricção IA de horas→minutos | Médio | `py -m anotador train --dataset DIR --epochs N --gpu` → dataset export + treino + export ONNX + cópia models/ |
| A2 | **Active Learning / Human-in-the-loop** | Acelera anotação 5-10x | Alto | Detector propõe pads; usuário valida/rejeita; modelo aprende online (pseudo-label + fine-tune leve) |
| A3 | **Import/Export KiCad/Eagle/Gerber nativo** | Integração fluxo profissional | Médio | Parser Gerber (gerber2png/gerbv) → pads; Export Netlist KiCad (.kicad_pcb) |
| A4 | **Comparação visual lado-a-lado (diff viewer)** | QA de fabricação | Médio | Overlay frente/verso com toggle opacity; heatmap de diff; medição de desalinhamento |
| A5 | **Busca semântica de componentes (OCR + BOM)** | Automatiza BOM | Alto | Tesseract/PaddleOCR em ROI do componente → cross-ref DigiKey/Mouser/LCSC API |
| A6 | **Netlist extraction & DRC básico** | Validação elétrica | Alto | Grafo de conectividade a partir de famílias → DRC (espacamento, largura trilha, anéis) |
| A7 | **Modo "Inspeção Óptica Automatizada" (AOI)** | Caso de uso industrial | Alto | Template matching + registro preciso + relatório PASS/FAIL por pad/componente |
| A8 | **Colaboração multi-usuário (sessão compartilhada)** | Equipes | Alto | WebSocket + CRDT para anotações/pinos; resolução de conflitos last-write-wins |

### 🟡 MÉDIO (Qualidade de vida / robustez)

| # | Melhoria | Impacto | Esforço | Descrição |
|---|----------|---------|---------|-----------|
| M1 | **Plugin system (Python entry-points)** | Extensibilidade | Médio | `anotador.plugins` entry point; hooks: `on_detect`, `on_save`, `on_export`, `on_measure` |
| M2 | **Configuração YAML/TOML hierárquica** | Gestão de config | Baixo | `config.yaml` com defaults + override por projeto + CLI `--config` |
| M3 | **Logging estruturado (structlog/JSON)** | Debug produção | Baixo | Log nível DEBUG/INFO/WARN/ERROR com contexto; rotação diária; correlação request-id |
| M4 | **Profiling integrado (cProfile + snakeviz)** | Performance | Baixo | `--profile` gera `.prof`; botão "Abrir perfil" no menu |
| M5 | **Testes de propriedade (hypothesis)** | Qualidade | Médio | Property-based tests para geometria, transform, units, detector |
| M6 | **Benchmark contínuo (CI)** | Regressão perf | Baixo | GitHub Action: roda detector em dataset fixo; falha se >5% regressão |
| M7 | **Documentação automática (mkdocstrings)** | Onboarding | Baixo | `mkdocs.yml` + docstrings Google-style → site hospedado |
| M8 | **Internacionalização (i18n)** | Acesso global | Médio | gettext/.po para PT/EN/ES; fallback EN; seletor no menu |

### 🟢 BAIXO (Nice-to-have / experimentais)

| # | Melhoria | Impacto | Esforço | Descrição |
|---|----------|---------|---------|-----------|
| L1 | **WebAssembly build (pyodide)** | Acesso via browser | Alto | Compilar core + UI para WASM; roda offline no navegador |
| L2 | **AR/VR overlay (WebXR/OpenXR)** | Inspeção imersiva | Muito alto | Overlay de pads/pinos no headset; apontar → mede |
| L3 | **Geração de relatório LaTeX/PDF nativo** | Documentação formal | Médio | Jinja2 → .tex → pdfLaTeX; tabelas de medição, schematics |
| L4 | **Simulação SPICE netlist** | Validação circuito | Muito alto | Export netlist → ngspice/pySpice; simulação DC/AC/transient |
| L5 | **Marketplace de modelos IA** | Ecossistema | Alto | Hub de modelos ONNX treinados pela comunidade; rating/download |

---

## ANÁLISE TÉCNICA DETALHADA POR CAMADA

### 1. ARQUITETURA & CÓDIGO BASE (`app/app.py` - 4707 linhas)

**Problemas atuais:**
- **God object:** `AppV101` concentra UI, estado, detecção, serialização, UI, GPU, tudo
- **Estado mutável espalhado:** 150+ atributos de instância; difícil rastrear invariantes
- **UI e lógica acopladas:** `_render` faz lógica + desenho; difícil testar isoladamente
- **Coordinates mágicas:** Hardcoded `x,y,w,h` por todo lado; quebram com DPI/resolução

**Refatoração proposta (fases):**
```
Fase 1 (1-2 semanas): 
  - Extrair StateManager (views_store, pads, nets, components, measurements)
  - Extrair Renderer (draw_pads, draw_ui, draw_canvas)
  - Extrair InputHandler (mouse, keyboard, gestures)
  - Introduzir EventBus pub/sub para desacoplar

Fase 2 (2-3 semanas):
  - Migrar para MVVM: ViewModel expõe propriedades/bindings; View apenas desenha
  - Introduzir Command pattern para undo/redo transacional
  - State persistence via serialização declarativa (attrs/cattrs)

Fase 3 (contínuo):
  - Type hints completos (mypy strict)
  - Property-based tests para geometria/transform
  - Benchmark suite contínua
```

### 2. DETECÇÃO DE PADS

**Atual:** 
- Smart: HSV + morfologia + contornos + heurísticas (ruído, vias, texto)
- Clássico: Threshold fixo + contornos
- IA: YOLO ONNX via cv2.dnn (CPU/GPU)

**Limitações conhecidas:**
- Smart: Sensível a iluminação; falsos positivos em serigrafia; vias confundidas
- IA: Modelo baseline fraco (12 épocas); confiança max ~0.07; NMS básico
- Sem ensemble; sem tiling inteligente; sem augmentação no treino

**Roteiro detecção v2.0:**
```
Q1: Ensemble Smart + IA (weighted NMS)
    - Smart como prior; IA refina; consenso por IoU > 0.5
    - Tiling adaptativo: tiles menores em áreas densas, maiores em áreas vazias
    
Q2: Active Learning Loop
    - Usuário valida/rejeita → adiciona ao dataset → fine-tune LoRA (5-10 min GPU)
    - Query strategy: uncertainty sampling (confiança ~0.5) + diversity
    
Q3: Detecção multi-classe
    - Classes: pad, via, fiducial, fiducial_local, mounting_hole, test_point
    - Treino multi-task: detecção + classificação + regressão de ângulo
    
Q4: Foundation Model Adapter
    - SAM (Segment Anything) como backbone; prompt = ponto/caixa do usuário
    - Few-shot: 10-20 anotações → adaptação LoRA
```

### 3. GPU / COMPUTE

**Atual:** 
- OpenCL/UMat para Smart (filtros, morfologia)
- CUDA/OpenCL para DNN (YOLO ONNX)
- Benchmark único na inicialização

**Gaps críticos:**
- **Sem memória unificada:** Copia CPU↔GPU a cada frame; `UMat.get()` bloqueia
- **Sem pipeline assíncrono:** Detecção trava UI; sem double-buffer
- **Sem memory pool:** Alocações frequentes fragmentam VRAM
- **Sem fallback gracioso:** Driver crash = app crash (sem watchdog)

**Arquitetura GPU v2.0:**
```python
class ComputeManager:
    def __init__(self):
        self.device = self._select_best_device()  # CUDA > OpenCL(AMD/Intel) > CPU
        self.stream = cv2.cuda_Stream() if cuda else None
        self.mem_pool = VRAMPool(self.device, max_mb=1024)
        self.async_queue = AsyncQueue(max_workers=2)
    
    def process_async(self, frame, pipeline):
        future = self.async_queue.submit(pipeline, frame)
        return future  # callback quando pronto
    
    def pipeline_smart(self, frame):
        # Tudo em UMat/GpuMat; zero copy CPU
        return self.mem_pool.get_output()
```

### 4. SERIALIZAÇÃO & PERSISTÊNCIA

**Atual:** JSON (sessão) + CSV (pads/medidas/componentes) + PNG (overlay)

**Problemas:**
- JSON monolítico (sessão inteira); não streamável
- CSV sem schema; parsing frágil (BOM, linhas curtas, tipos)
- Sem compressão; sessão de 5000 pads = 10-50MB JSON
- Sem versionamento semântico de schema

**Formato v2.0 (MessagePack + Schema):**
```yaml
# anotador_v2.msgpack (binário, ~60% menor)
version: 2
schema_hash: sha256
metadata:
  created: "2026-11-02T10:00:00Z"
  version: "11.7"
  project_hash: "sha256(project_path)"
views:
  frente:
    pads: [[id, x, y, w, h, area, manual, pino, gnd, link, forma, score], ...]
    measurements: {pid: {status, ligada: {V,Hz,forma,obs}, desligada: {R,cont,C,Vf,obs}}}
    nets: [{id, nome, cor, pads[], uid}, ...]
    components: [{id, nome, tipo, forma, bbox, pads[], valores...}, ...]
    annotations: [{id, x, y, text, cor}, ...]
    next_ids: {pad, net, comp, annot}
    transform: {H_matrix, score, mirror}
    image_ref: {path, hash, mtime}
```

### 5. INTERFACE & UX

**Forças atuais:**
- Rail vertical (Photoshop-style) ✓
- Barra contextual agrupada ✓
- Dica contextual dinâmica ✓
- Tooltip 0.45s ✓
- Zoom flutuante ✓

**Gaps UX críticos:**
- **Sem atalhos visuais:** Teclas não mostram no rail (ex: `Y` ao lado de Anotar)
- **Sem busca global unificada:** `Ctrl+K` só para comandos; não busca pads/componentes/nets
- **Sem workspace personalizável:** Rail/panels fixos; não salva layout por usuário
- **Sem modo "apresentação":** Oculta UI, só canvas + zoom/pan
- **Sem acessibilidade:** Sem screen reader; cores não testadas para daltonismo
- **Sem undo visual:** Não mostra preview do que será desfeito

### 6. TESTES & QUALIDADE

**Atual:** 46 testes pytest (smoke, units, detector, regressão, active learning)

**Cobertura gaps:**
```
Cobertura atual estimada: ~35% (branches)
Faltando:
- Property-based: geometry, transform, units, detector NMS
- Mutation testing: mutmut (detecta testes fracos)
- Contract tests: schema validation (JSON/CSV/ONNX)
- Visual regression: screenshot diff (pytest-visual)
- Load test: 5000 pads + 100 componentes + 50 anotações
- Fuzzing: atheris para parsers CSV/JSON/ONNX
```

---

## PLANO DE EXECUÇÃO SUGERIDO (12 MESES)

### Sprint 1-2 (Semanas 1-4): Fundação & Estabilidade
- [x] C1, C2, C3, C4 (backups, validação, undo atômico, prefs schema)
- [x] M2, M3 (config YAML + logging estruturado)
- [x] Refatorar `AppV101` → `StateManager` (Renderer/InputHandler pendentes)
- [x] CI: pytest + coverage + ruff (gate objetivo); mypy informativo; mutmut pendente

### Sprint 3-4 (Semanas 5-8): Detecção v2.0
- [ ] Ensemble Smart+IA (weighted NMS)
- [ ] Tiling adaptativo (densidade baseada)
- [x] Active Learning: validação → pseudo-label → fine-tune LoRA
- [ ] Métricas: PR curve, AP@0.5, inference time

### Sprint 5-6 (Semanas 9-12): GPU & Performance
- [ ] ComputeManager com VRAM pool + async queue
- [ ] Double-buffer detecção (UI nunca trava)
- [ ] Memory pool VRAM (evita fragmentação)
- [ ] Benchmark CI (regressão >5% falha)

### Sprint 7-8 (Semanas 13-16): Serialização v2 + Import/Export
- [ ] Formato MessagePack v2 com schema
- [ ] Import KiCad/Eagle/Gerber
- [ ] Export Netlist KiCad + BOM CSV
- [x] Diff viewer frente/verso + heatmap

### Sprint 9-10 (Semanas 17-20): IA Avançada
- [x] Active Learning loop (validação → fine-tune LoRA 5 min)
- [ ] Ensemble Smart+IA (weighted NMS)
- [ ] SAM adapter (few-shot 10-20 shots)
- [ ] Multi-class: pad/via/fiducial/mounting/test_point

### Sprint 11-12 (Semanas 21-24): Ecossistema & Entrega
- [x] Plugin system (entry-points)
- [x] CLI unificado (`anotador train|detect|export|convert`)
- [ ] WebAssembly demo (pyodide)
- [ ] Documentação mkdocs + i18n PT/EN
- [ ] Release v12.0

---

## RISCOS & MITIGAÇÕES

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Refatoração quebra funcionalidade existente | Alta | Crítico | Testes de contrato (JSON/CSV/ONNX) + visual regression antes de cada merge |
| GPU drivers instáveis (AMD/OpenCL) | Média | Alto | Fallback CPU automático + watchdog + logs detalhados |
| Modelo IA não generaliza | Média | Alto | Active Learning + ensemble + monitoramento drift |
| Escopo creep (feature creep) | Alta | Médio | Roadmap fixo por sprint; "no new features" nas últimas 2 semanas |
| Dependência OpenCV (breaking changes) | Baixa | Crítico | Pin `opencv-python==4.10.*`; testes de compat em CI |

---

## MÉTRICAS DE SUCESSO (KPIs)

| Métrica | Baseline (v11.7) | Target v12.0 | Target v13.0 |
|---------|------------------|--------------|--------------|
| Tempo detecção 5000 pads (GPU) | ~2.5s | <1.5s | <0.8s |
| Falsos positivos Smart | ~15% | <5% | <2% |
| Recall IA (baseline→treinado) | ~10% | >85% | >95% |
| Tempo anotação 100 pads | 45 min | 15 min | 5 min |
| Taxa de crash/sessão | ~2% | <0.1% | 0% |
| Cobertura testes (branches) | 35% | 70% | 90% |
| Tempo build EXE | 8 min | 5 min | 3 min |
| Tamanho EXE | 111 MB | 90 MB | 70 MB |
| Tempo onboarding (novo usuário) | 30 min | 10 min | 5 min |

---

## RECURSOS NECESSÁRIOS

| Recurso | Q1 | Q2 | Q3 | Q4 |
|---------|----|----|----|----|
| Dev Senior (Python/OpenCV/ML) | 1.0 | 1.0 | 1.0 | 1.0 |
| Dev Mid (Python/UI/Tests) | 0.5 | 1.0 | 1.0 | 0.5 |
| ML Engineer (treino/LoRA) | 0.0 | 0.5 | 1.0 | 1.0 |
| QA/Automação (CI/Tests) | 0.5 | 0.5 | 0.5 | 0.5 |
| GPU Cloud (Colab Pro/AWS) | $50/mês | $200/mês | $500/mês | $500/mês |
| CI/CD (GitHub Actions) | Free | Free | Free | $50/mês |

---

## PRÓXIMOS PASSOS IMEDIATOS (ESTA SEMANA)

1. **Aprovar/ajustar roadmap** com stakeholders
2. **Criar issues GitHub** para C1-C4, A1, M2, M3 (templates prontos)
3. **Configurar CI baseline:** pytest + coverage + mypy + ruff + mutmut baseline
2. **Criar branch `refactor/state-manager`** e iniciar extração `StateManager`
3. **Documentar API interna** (docstrings Google-style) para `StateManager`, `Renderer`, `InputHandler`
4. **Adicionar `pyproject.toml`** com `build-system`, `tool.ruff`, `tool.mypy`, `tool.pytest.ini_options`

---

## ANEXO: COMPARATIVO COMPETITIVO

| Feature | AnotadorPad | KiCad | Altium | Eagle | Gerbv | AOI Commercial |
|---------|-------------|-------|--------|-------|-------|----------------|
| Detecção pads automática | ✓ Smart+IA | ✗ | ✓ | ✓ | ✗ | ✓ |
| Anotação manual | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Marcação pino/GND | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ |
| Vinculação frente/verso | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| Treino IA customizado | ✓ (YOLO) | ✗ | ✗ | ✗ | ✗ | ✓ (proprietary) |
| Active Learning | Planeado | ✗ | ✗ | ✗ | ✗ | ✓ |
| Export KiCad/Gerber | Planeado | Nativo | Nativo | Nativo | Nativo | ✗ |
| AOI/Diff visual | Parcial | ✗ | ✓ | ✗ | ✗ | ✓ |
| Preço | **Gratuito/Open** | Gratuito | $5000+/ano | $1000+/ano | Gratuito | $50k+/ano |
| Licença | MIT | GPL | Proprietária | Proprietária | GPL | Proprietária |

**Posicionamento único:** Único **gratuito/open-source** com **detecção IA treinável pelo usuário** + **active learning** + **fluxo bancada completo** (foto → anotação → IA → relatório).

---

*Documento gerado em 2026-11-02 | Baseado em AnotadorPad v11.7 | Para discussão e priorização*