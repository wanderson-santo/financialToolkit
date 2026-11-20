# Finance Toolkit — TODO / Backlog Executável

> **Etapa:** 6 — construção do backlog  
> **Fonte:** `docs/project-discovery.md`, `docs/technical-audit.md`, `docs/improvement-roadmap.md`  
> **Status geral:** planejamento. Nenhuma tarefa foi implementada.  
> **Regra de IDs:** os IDs `FT-xxx` são permanentes. Reordene, divida ou adie tarefas, mas não reutilize nem renumere IDs.

---

## 1. Como usar este backlog

1. Escolha uma tarefa **sem dependências pendentes** e com prioridade mais alta.
2. Leia a tarefa, o achado de auditoria relacionado e os arquivos indicados.
3. Implemente em uma branch curta, com teste de regressão quando aplicável.
4. Execute a suíte + testes novos + verificação de compilação.
5. Atualize o status para `concluída` somente após validação e revisão.
6. Se a tarefa mudar de escopo, crie novas tarefas com IDs novos; não esconda trabalho extra na mesma tarefa.

### Legenda

- **Prioridade:** `P0` bloqueia confiança/segurança; `P1` necessária para a próxima fase; `P2` importante, planejável; `P3` desejável, sem urgência.
- **Complexidade:** `pequena` (≤ 1 dia), `média` (2–4 dias), `grande` (> 4 dias), sempre incluindo testes e documentação.
- **Status:** `pendente`, `em andamento`, `bloqueada`, `concluída`.
- **Aceite:** condição objetiva e verificável.
- **Testes:** o mínimo que deve existir; testes adicionais são bem-vindos.

### Definição de pronto (aplicável a todas as tarefas)

- Código compila/importa.
- Testes existentes e novos passam.
- Comportamento documentado (docstring/README/changelog quando relevante).
- Nenhuma regressão conhecida; nenhum arquivo do usuário alterado em teste.
- Tarefa de operação destrutiva: preview + journal/registro + teste de conflito.

---

## 2. Resumo quantitativo

| Fase | Período de foco | Tarefas | IDs |
|---|---|---:|---|
| Fase 0 | Estabilização | 15 | FT-001–FT-015 |
| Fase 1 | Núcleo confiável | 16 | FT-016–FT-031 |
| Fase 2 | Experiência operacional | 16 | FT-032–FT-047 |
| Fase 3 | Expansão funcional | 26 | FT-048–FT-073 |
| Fase 4 | Automação e integração | 9 | FT-074–FT-082 |
| Fase 5 | Distribuição e maturidade | 13 | FT-083–FT-095 |
| **Total** | | **95** | |

| Prioridade | Quantidade |
|---|---:|
| P0 | 9 |
| P1 | 35 |
| P2 | 41 |
| P3 | 10 |

> A contagem será conferida novamente ao final da implementação; este documento é a fonte de verdade.

### Caminho crítico mínimo

```text
FT-001 → FT-002 → FT-005 → FT-003 → FT-004 → FT-006 → FT-007
   → FT-014 → FT-016 → FT-017 → FT-019 → FT-020 → FT-021 → FT-022
   → FT-024 → FT-032 → FT-033 → FT-038 → FT-074
```

### Primeira tarefa recomendada

**FT-001 — Corrigir a interpretação de tolerância no comparador.** É pequena, isolada, tem impacto financeiro direto, teste objetivo e não depende de nenhuma decisão arquitetural. Em seguida, FT-002, FT-005, FT-003 e FT-004 fecham o bloco de confiança.

---

## 3. Fase 0 — Estabilização

### FT-001 — Corrigir a interpretação de tolerância no comparador

- [x] **FT-001 — Corrigir a interpretação de tolerância no comparador**
  - **Descrição:** definir e implementar uma regra explícita para o campo “Tolerância”, sem aceitar silenciosamente a interpretação errada de `"0.01"` como `1.0`.
  - **Problema/necessidade:** AUD-13; comparação financeira pode declarar igual o que difere em até R$ 1,00.
  - **Arquivos/componentes:** `modules/spreadsheets/comparator.py` (`validate`, `_tolerance`), `core/normalizers.py` (`parse_number`), `tests/test_modules.py`.
  - **Prioridade:** P0 · **Complexidade:** pequena · **Dependências:** —
  - **Critérios de aceite:** `0,01` e `0.01` resultam em `0.01` (ou erro explícito se a regra for “apenas BR”); formatos ambíguos são rejeitados com mensagem; a UI/descrição informa o formato aceito; teste cobre `0`, `0,01`, `0.01`, `1.000`.
  - **Testes necessários:** unidade para `_tolerance` e `same_value`; teste de validação de entrada inválida.
  - **Status:** concluída

### FT-002 — Corrigir comparação de inteiros com separador de milhar brasileiro

- [x] **FT-002 — Corrigir comparação de inteiros com separador de milhar brasileiro**
  - **Descrição:** reconhecer `1.234`, `12.345`, `1.234.567` como inteiros brasileiros no comparador, sem confundir com decimais internacionais.
  - **Problema/necessidade:** AUD-14; `same_value("1.234","1234")` retorna `False`.
  - **Arquivos/componentes:** `modules/spreadsheets/comparator.py` (`_numeric`), `core/normalizers.py`, `tests/test_modules.py`.
  - **Prioridade:** P0 · **Complexidade:** pequena · **Dependências:** —
  - **Critérios de aceite:** casos brasileiros inequívocos são iguais; `1.23` e `1,23` mantêm semântica documentada; valores ambíguos não são convertidos silenciosamente; testes de regressão.
  - **Testes necessários:** `1.234` vs `1234`, `1.234,00` vs `1234`, `1.234.567`, `R$ 1.234`, negativos, decimais.
  - **Status:** concluída

### FT-003 — Recuperar inicialização com banco inválido ou pasta indisponível

- [x] **FT-003 — Recuperar inicialização com banco inválido ou pasta indisponível**
  - **Descrição:** tratar falhas de criação/abertura do SQLite e da pasta de dados com diálogo nativo, preservação do arquivo inválido e recriação segura; nunca encerrar silenciosamente no executável.
  - **Problema/necessidade:** AUD-03; `HistoryService` levanta `DatabaseError` e `console=False` esconde a falha.
  - **Arquivos/componentes:** `app/bootstrap.py`, `core/history_service.py`, `core/paths.py`, `core/logging_service.py`, `tests/test_core.py`.
  - **Prioridade:** P0 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** banco inválido é renomeado para `.corrupt-<timestamp>` (não apagado), um banco novo é criado e o usuário é informado; falha de pasta mostra mensagem clara; log registra o ocorrido; teste com banco inválido.
  - **Testes necessários:** unidade de recuperação com arquivo inválido; teste de caminho não gravável (quando suportado no ambiente).
  - **Status:** concluída

### FT-004 — Encerramento seguro durante execução

- [x] **FT-004 — Encerramento seguro durante execução**
  - **Descrição:** interceptar o fechamento da janela; se houver operação em andamento, confirmar, solicitar cancelamento, aguardar com timeout e registrar o resultado/interrupção antes de sair.
  - **Problema/necessidade:** AUD-04; thread `daemon` pode ser morta no meio de movimentação.
  - **Arquivos/componentes:** `app/main_window.py`, `app/pages.py`, `core/execution_context.py`, `core/history_service.py`.
  - **Prioridade:** P0 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** fechar com operação ativa nunca termina sem confirmação; cancelamento é solicitado; histórico é finalizado como cancelado/interrompido; após timeout, usuário recebe aviso; teste com operação simulada.
  - **Testes necessários:** teste de controlador de fechamento sem UI real; teste de `finish` em cancelamento.
  - **Status:** concluída

### FT-005 — Neutralizar fórmulas em exportações CSV e XLSX

- [x] **FT-005 — Neutralizar fórmulas em exportações CSV e XLSX**
  - **Descrição:** aplicar uma política única de sanitização a todas as saídas tabulares, cobrindo `=`, `+`, `-`, `@`, tab/CR e espaços à esquerda.
  - **Problema/necessidade:** AUD-19; CSV permite injeção de fórmula; XLSX protege apenas `=`.
  - **Arquivos/componentes:** `core/export_service.py`, `app/pages.py` (exportação), `tests/test_core.py` ou novo `tests/test_export.py`.
  - **Prioridade:** P0 · **Complexidade:** pequena · **Dependências:** —
  - **Critérios de aceite:** payloads conhecidos são exportados como texto e não como fórmula em CSV/XLSX; números negativos legítimos continuam números; regra documentada; testes de ambos os formatos.
  - **Testes necessários:** casos `=`, `+`, `-`, `@`, tab, CR, espaços; garantir que valores numéricos não sejam corrompidos.
  - **Status:** concluída

### FT-006 — Deduplicar cabeçalhos de planilha na leitura

- [x] **FT-006 — Deduplicar cabeçalhos de planilha na leitura**
  - **Descrição:** garantir nomes de coluna únicos e determinísticos após `strip`/normalização, preservando a ordem e avisando sobre renomeações.
  - **Problema/necessidade:** AUD-15; `"X"` e `" X "` quebram o limpador e podem perder colunas no comparador.
  - **Arquivos/componentes:** `core/spreadsheet_service.py` (`read_table`), `modules/spreadsheets/cleaner.py`, `modules/spreadsheets/comparator.py`, testes.
  - **Prioridade:** P0 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** cabeçalhos duplicados viram `X`, `X_2`, …; nenhuma coluna é perdida; a renomeação é registrada/logada; limpador e comparador funcionam com o caso; testes.
  - **Testes necessários:** xlsx/csv com `X`/` X `/vazio/duplicado; verificar todas as colunas no resultado.
  - **Status:** concluída

### FT-007 — Tornar a detecção de codificação/separador CSV confiável

- [x] **FT-007 — Tornar a detecção de codificação/separador CSV confiável**
  - **Descrição:** validar a codificação no arquivo inteiro ou em amostras distribuídas e permitir fallback explícito; detectar separador considerando aspas.
  - **Problema/necessidade:** AUD-16; byte não-UTF-8 após 64 KB gera `UnicodeDecodeError` ou mojibake.
  - **Arquivos/componentes:** `core/spreadsheet_service.py` (`_csv_params`, `read_table`), testes com fixtures.
  - **Prioridade:** P0 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** arquivo UTF-8/BOM/cp1252/latin-1 é lido corretamente ou rejeitado com mensagem clara; nenhum `UnicodeDecodeError` cru chega à UI; separador `;`, `,`, tab e `|` testado; codificação detectada é logada.
  - **Testes necessários:** fixtures com acentos, BOM, byte tardio, aspas e separadores; teste de arquivo vazio/só cabeçalho.
  - **Status:** concluída

### FT-008 — Gravar manifesto de duplicatas antes das movimentações

- [x] **FT-008 — Gravar manifesto de duplicatas antes das movimentações**
  - **Descrição:** criar o manifesto (ou journal) antes de mover a primeira cópia e atualizá-lo de forma segura; em falha, manter estado parcial explícito.
  - **Problema/necessidade:** AUD-08; hoje o manifesto é escrito depois, deixando arquivos sem mapa de retorno.
  - **Arquivos/componentes:** `modules/files/duplicate_finder.py`, `core/file_service.py`, testes.
  - **Prioridade:** P0 · **Complexidade:** pequena · **Dependências:** —
  - **Critérios de aceite:** manifesto existe antes do primeiro move; contém grupo, origem e destino; falha de escrita aborta antes de mover; teste de cancelamento/falha.
  - **Testes necessários:** simular falha de manifesto; cancelamento após primeiro move; verificar arquivos e manifesto.
  - **Status:** concluída

### FT-009 — Padronizar status de resultado e cancelamento

- [ ] **FT-009 — Padronizar status de resultado e cancelamento**
  - **Descrição:** usar constantes/helper para todos os status e permitir que `build_result` represente cancelamento/parcial sem mutação de string.
  - **Problema/necessidade:** AUD-33; strings soltas `"cancelled"`.
  - **Arquivos/componentes:** `core/base_module.py`, `modules/files/*.py`, `modules/spreadsheets/*.py`, `modules/finance/*.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** pequena · **Dependências:** —
  - **Critérios de aceite:** nenhum literal de status fora de `core/base_module.py`; resultado inválido é rejeitado/testado; histórico exibe corretamente; testes de cada status.
  - **Testes necessários:** unidade de `build_result`/cancelamento; regressão dos módulos que cancelam.
  - **Status:** pendente

### FT-010 — Evitar colisão de nomes de abas na exportação

- [ ] **FT-010 — Evitar colisão de nomes de abas na exportação**
  - **Descrição:** deduplicar nomes de aba após sanitização/truncamento, garantindo que nenhum DataFrame seja perdido.
  - **Problema/necessidade:** AUD-21; segunda aba longa sobrescreve a primeira.
  - **Arquivos/componentes:** `core/export_service.py`, testes de exportação.
  - **Prioridade:** P1 · **Complexidade:** pequena · **Dependências:** —
  - **Critérios de aceite:** nomes colididos viram `nome`, `nome_2`, …; todas as abas estão presentes; teste com nomes >31 caracteres.
  - **Testes necessários:** colisão exata após truncamento; nome vazio; caracteres inválidos.
  - **Status:** pendente

### FT-011 — Validar metadados de módulo no registro

- [ ] **FT-011 — Validar metadados de módulo no registro**
  - **Descrição:** validar no `build_registry()`/teste que `kind` é permitido, choices existem, sources apontam para parâmetros válidos e IDs/chaves são únicos.
  - **Problema/necessidade:** AUD-12; `ValueError` só aparece ao abrir a página.
  - **Arquivos/componentes:** `app/module_registry.py`, `core/base_module.py`, `tests/test_modules.py`.
  - **Prioridade:** P1 · **Complexidade:** pequena · **Dependências:** —
  - **Critérios de aceite:** registro rejeita módulo inválido com mensagem clara; teste com módulo malformado; módulos atuais passam.
  - **Testes necessários:** fixtures de `kind` inválido, choice vazia, source inexistente, chave duplicada.
  - **Status:** pendente

### FT-012 — Coordenar operações mutáveis simultâneas

- [ ] **FT-012 — Coordenar operações mutáveis simultâneas**
  - **Descrição:** introduzir um coordenador que permita apenas uma operação que altera arquivos por vez (ou fila), com estado global consultável.
  - **Problema/necessidade:** AUD-05; duas páginas podem operar na mesma pasta.
  - **Arquivos/componentes:** novo serviço em `core/` (ex.: `operation_coordinator.py`), `app/services.py`, `app/pages.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** segunda operação mutável é bloqueada/enfileirada com mensagem; preview pode ser permitido conforme política; estado é liberado em sucesso/erro/cancelamento; testes.
  - **Testes necessários:** duas aquisições concorrentes; liberação em exceção; cancelamento.
  - **Status:** pendente

### FT-013 — Correlacionar `run_id` entre log e histórico

- [ ] **FT-013 — Correlacionar `run_id` entre log e histórico**
  - **Descrição:** criar o identificador de execução antes de `history.start()` e reutilizá-lo no `ExecutionContext` e na UI.
  - **Problema/necessidade:** AUD-10; banco e log usam IDs diferentes.
  - **Arquivos/componentes:** `app/pages.py`, `core/execution_context.py`, `core/history_service.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** pequena · **Dependências:** —
  - **Critérios de aceite:** `executions.run_id` é preenchido; linhas de log contêm o mesmo ID; detalhe do histórico exibe o ID; testes.
  - **Testes necessários:** unidade de criação/passagem do ID; teste de registro no banco.
  - **Status:** pendente

### FT-014 — Criar baseline de cobertura e testes de regressão

- [ ] **FT-014 — Criar baseline de cobertura e testes de regressão**
  - **Descrição:** configurar medição de cobertura (ferramenta de desenvolvimento aprovada), registrar baseline e adicionar testes de regressão para os P0 (FT-001–FT-010).
  - **Problema/necessidade:** AUD-28; defeitos confirmados passaram pela suíte.
  - **Arquivos/componentes:** `tests/`, configuração de cobertura, possivelmente `requirements-dev.txt` (somente com autorização).
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** comando único roda testes + cobertura; relatório gerado; todos os P0 têm teste que falha no código antigo e passa no novo; baseline documentado.
  - **Testes necessários:** os próprios testes de regressão; verificar que falham antes da correção.
  - **Status:** pendente

### FT-015 — Adotar controle de versão e higiene de repositório

- [x] **FT-015 — Adotar controle de versão e higiene de repositório**
  - **Descrição:** inicializar Git (ou integrar a repositório existente), revisar `.gitignore`, criar política simples de branches/tags e registrar a versão 0.1.0 como baseline.
  - **Problema/necessidade:** AUD-01; não há histórico nem rollback.
  - **Arquivos/componentes:** raiz do projeto, `.gitignore`, documentação de contribuição/release.
  - **Prioridade:** P0 (processo) · **Complexidade:** pequena · **Dependências:** —
  - **Critérios de aceite:** repositório versionado; `docs/` e código rastreáveis; nenhum artefato de build/venv versionado; tag `v0.1.0`; checklist de commit/release documentado.
  - **Testes necessários:** não se aplica; verificar clone limpo e `git status` limpo.
  - **Status:** concluída

---

## 4. Fase 1 — Núcleo confiável

### FT-016 — Versionar e migrar o esquema SQLite

- [ ] **FT-016 — Versionar e migrar o esquema SQLite**
  - **Descrição:** adicionar `PRAGMA user_version` e migrações incrementais para o banco do histórico.
  - **Problema/necessidade:** AUD-09; evolução do esquema hoje é manual.
  - **Arquivos/componentes:** `core/history_service.py`, novo módulo de migrações, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** banco novo nasce na versão atual; banco antigo migra sem perder dados; migração é idempotente; falha não deixa esquema parcial; teste com banco vazio e “antigo”.
  - **Testes necessários:** migração de cada versão; reexecução; banco corrompido.
  - **Status:** pendente

### FT-017 — Persistir detalhes e artefatos das execuções

- [ ] **FT-017 — Persistir detalhes e artefatos das execuções**
  - **Descrição:** armazenar os detalhes por linha/arquivo de forma consultável, com limite e referência a arquivo externo quando grande.
  - **Problema/necessidade:** AUD-07; fechar o app apaga a evidência operacional.
  - **Arquivos/componentes:** `core/history_service.py`, `app/pages.py`, `core/base_module.py`, migração FT-016, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-016
  - **Critérios de aceite:** execução antiga exibe detalhes; exportação funciona; detalhes grandes não travam a UI; tamanho/retenção definidos; teste de ida e volta.
  - **Testes necessários:** persistência/consulta de 0, poucas e muitas linhas; caracteres especiais; falha de escrita.
  - **Status:** pendente

### FT-018 — Ativar WAL, índices, retenção e backup do banco

- [ ] **FT-018 — Ativar WAL, índices, retenção e backup do banco**
  - **Descrição:** configurar WAL, índices adequados, política de retenção (dias/quantidade) e backup antes de operações sensíveis.
  - **Problema/necessidade:** AUD-09; banco cresce sem limite e concorrência é pior.
  - **Arquivos/componentes:** `core/history_service.py`, `core/paths.py` (`backups_dir`), testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-016
  - **Critérios de aceite:** WAL ativo; consultas filtradas usam índice; retenção remove apenas registros elegíveis; backup restaurável; testes.
  - **Testes necessários:** retenção por data/quantidade; restauração; verificação de integridade.
  - **Status:** pendente

### FT-019 — Journal transacional e undo de operações

- [ ] **FT-019 — Journal transacional e undo de operações**
  - **Descrição:** registrar origem/destino/status antes de cada movimento e oferecer “Desfazer” seguro no histórico para operações reversíveis.
  - **Problema/necessidade:** AUD-08; hoje não há como reverter organizador/duplicatas com garantia.
  - **Arquivos/componentes:** `core/history_service.py`, `core/file_service.py`, `modules/files/folder_organizer.py`, `modules/files/duplicate_finder.py`, `app/pages.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** grande · **Dependências:** FT-017, FT-018
  - **Critérios de aceite:** journal antes do move; undo valida que destino/origem ainda correspondem; nunca sobrescreve; operações não reversíveis são marcadas; falha é reportada sem perda.
  - **Testes necessários:** undo feliz; arquivo alterado; destino ocupado; cancelamento; reinício do app.
  - **Status:** pendente

### FT-020 — Vincular plano de preview à execução

- [ ] **FT-020 — Vincular plano de preview à execução**
  - **Descrição:** criar um objeto de plano com hash/identificador das entradas e revalidar na execução; invalidar confirmação se o plano mudou.
  - **Problema/necessidade:** AUD-06; preview pode não corresponder ao execute.
  - **Arquivos/componentes:** `core/base_module.py`, módulos mutáveis, `app/pages.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-017, FT-019
  - **Critérios de aceite:** módulos mutáveis expõem plano/hash; mudança de arquivos invalida; UI mostra resumo; execução usa plano validado; testes por módulo.
  - **Testes necessários:** plano inalterado; arquivo adicionado/removido; conteúdo alterado.
  - **Status:** pendente

### FT-021 — Criar validações compartilhadas de aba, coluna e saída

- [ ] **FT-021 — Criar validações compartilhadas de aba, coluna e saída**
  - **Descrição:** helpers em `core/` para verificar existência de aba/coluna, permissão de escrita, formato suportado e limites.
  - **Problema/necessidade:** AUD-12/AUD-17; erros tardios e genéricos.
  - **Arquivos/componentes:** `core/validation_service.py`, `core/spreadsheet_service.py`, módulos, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** módulos usam helpers; mensagens específicas; nenhuma leitura completa antes da validação básica; testes de aba/coluna/pasta inválidas.
  - **Testes necessários:** unidade dos helpers; integração em cada módulo de planilha.
  - **Status:** pendente

### FT-022 — Mapear erros conhecidos para mensagens acionáveis

- [ ] **FT-022 — Mapear erros conhecidos para mensagens acionáveis**
  - **Descrição:** criar taxonomia e tradução de `WorksheetNotFound`, `KeyError`, `PermissionError`, `FileNotFoundError`, `UnicodeDecodeError` etc.
  - **Problema/necessidade:** AUD-12/AUD-35; “Erro inesperado: …” não orienta.
  - **Arquivos/componentes:** `core/exceptions.py`, `core/spreadsheet_service.py`, `app/pages.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-021
  - **Critérios de aceite:** erros conhecidos têm mensagem orientativa; detalhe técnico vai para o log; `ToolkitError` preserva contexto; testes.
  - **Testes necessários:** cada tipo de erro mapeado; garantir que erros desconhecidos continuam logados.
  - **Status:** pendente

### FT-023 — Otimizar exportação de planilhas grandes

- [ ] **FT-023 — Otimizar exportação de planilhas grandes**
  - **Descrição:** remover loops célula a célula desnecessários, aplicar formatos por coluna/intervalo e medir tempo/memória em 10k/100k linhas.
  - **Problema/necessidade:** AUD-20; exportação pode parecer travada em volume.
  - **Arquivos/componentes:** `core/export_service.py`, benchmarks, testes.
  - **Prioridade:** P1 · **Complexidade:** grande · **Dependências:** —
  - **Critérios de aceite:** benchmark antes/depois documentado; ganho mensurável; formatos de data/número preservados; teste de regressão visual/funcional.
  - **Testes necessários:** 10k e 100k linhas; datas/números; abas múltiplas; memória.
  - **Status:** pendente

### FT-024 — Expor descoberta de abas e metadados de planilha

- [ ] **FT-024 — Expor descoberta de abas e metadados de planilha**
  - **Descrição:** usar `list_sheets()` em um serviço/API de introspecção com cache e mensagens de erro adequadas.
  - **Problema/necessidade:** AUD-17; API existe e não é usada.
  - **Arquivos/componentes:** `core/spreadsheet_service.py`, `app/widgets.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-006
  - **Critérios de aceite:** listar abas para xlsx/xls/csv; cache por caminho/mtime; erro claro; teste com arquivo multiaba.
  - **Testes necessários:** xlsx multiaba; csv sem abas; arquivo inválido; cache.
  - **Status:** pendente

### FT-025 — Ampliar configuração: reset, pastas recentes e preferências

- [ ] **FT-025 — Ampliar configuração: reset, pastas recentes e preferências**
  - **Descrição:** expor reset de parâmetros por módulo, pastas recentes e preferências básicas de saída.
  - **Problema/necessidade:** hoje só há “últimos parâmetros”; não há como voltar ao padrão.
  - **Arquivos/componentes:** `core/config_service.py`, `core/history_service.py`, `app/widgets.py`, `app/pages.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** reset restaura defaults; recentes não duplicam; preferências persistem; testes.
  - **Testes necessários:** reset; migração de settings; recentes.
  - **Status:** pendente

### FT-026 — Melhorar logging: acesso, redaction e diagnóstico

- [ ] **FT-026 — Melhorar logging: acesso, redaction e diagnóstico**
  - **Descrição:** criar política de redaction, rotação configurável e funções para abrir/copiar log e gerar pacote básico.
  - **Problema/necessidade:** AUD-31; usuário não encontra o log.
  - **Arquivos/componentes:** `core/logging_service.py`, `core/paths.py`, `app/utils.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** log não contém conteúdo de células; ação abre pasta; pacote inclui versão/SO/log recente; testes de redaction.
  - **Testes necessários:** mensagens com caminhos/nomes; rotação; geração de pacote.
  - **Status:** pendente

### FT-027 — Implementar retenção e controles de privacidade do histórico

- [ ] **FT-027 — Implementar retenção e controles de privacidade do histórico**
  - **Descrição:** permitir limpar histórico por período, exportar dados e definir retenção; documentar o que é gravado.
  - **Problema/necessidade:** AUD-24; dados permanecem indefinidamente e não há descarte.
  - **Arquivos/componentes:** `core/history_service.py`, `app/pages.py`, futura tela de configurações, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-018
  - **Critérios de aceite:** limpeza seletiva/total funciona; exportação inclui metadados; retenção respeitada; confirmação para ações destrutivas; testes.
  - **Testes necessários:** limpeza por data; exportação; retenção; confirmação.
  - **Status:** pendente

### FT-028 — Implementar instância única ou isolamento por instância

- [ ] **FT-028 — Implementar instância única ou isolamento por instância**
  - **Descrição:** mutex/lockfile para impedir duas instâncias ou marcar dono de execuções para não interromper as de outra instância.
  - **Problema/necessidade:** AUD-11; inicialização marca execuções alheias como interrompidas.
  - **Arquivos/componentes:** `app/bootstrap.py`, `core/history_service.py`, `core/paths.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** pequena · **Dependências:** FT-012
  - **Critérios de aceite:** segunda instância é bloqueada com mensagem ou isolada; execuções de outra instância não são marcadas; teste.
  - **Testes necessários:** lock adquirido/liberado; abertura concorrente simulada.
  - **Status:** pendente

### FT-029 — Tipar contrato de módulo e resultado

- [ ] **FT-029 — Tipar contrato de módulo e resultado**
  - **Descrição:** definir Protocol para `ctx`, tipar `details`/status e documentar o contrato; remover ou justificar código morto relacionado.
  - **Problema/necessidade:** AUD-12/AUD-32; facilita novos módulos e evita erros.
  - **Arquivos/componentes:** `core/base_module.py`, `core/execution_context.py`, `modules/`, `app/widgets.py`.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-011
  - **Critérios de aceite:** Protocol usado; type checker configurado (quando aprovado); nenhum `Any` desnecessário; documentação do contrato; testes.
  - **Testes necessários:** contrato dos módulos atuais; importação/checagem estática.
  - **Status:** pendente

### FT-030 — Endurecer nomes/paths de arquivos no Windows

- [ ] **FT-030 — Endurecer nomes/paths de arquivos no Windows**
  - **Descrição:** validar nomes reservados com extensão, comprimento, espaços/pontos e caminhos longos; falhar antes de operar.
  - **Problema/necessidade:** AUD-25; casos reais de razões sociais longas.
  - **Arquivos/componentes:** `core/file_service.py`, módulos de arquivos, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** nomes problemáticos são rejeitados/ajustados com mensagem; nenhuma operação parcial; testes Windows (quando disponível) e unitários.
  - **Testes necessários:** `CON.txt`, nome >255, caminho longo, pontos/espaços finais, unicode.
  - **Status:** pendente

### FT-031 — Verificar integridade e backup do banco na inicialização

- [ ] **FT-031 — Verificar integridade e backup do banco na inicialização**
  - **Descrição:** executar `PRAGMA integrity_check`/backup antes de migrar e oferecer restauração em caso de falha.
  - **Problema/necessidade:** AUD-09/AUD-03; proteção contra corrupção.
  - **Arquivos/componentes:** `core/history_service.py`, `core/paths.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-018
  - **Critérios de aceite:** backup criado antes de migração; integridade verificada; restauração documentada/testada; teste com banco íntegro/inválido.
  - **Testes necessários:** integrity_check; backup/restore; falha simulada.
  - **Status:** pendente

---

## 5. Fase 2 — Experiência operacional

### FT-032 — Adicionar `ParamSpec` de seleção de aba

- [ ] **FT-032 — Adicionar `ParamSpec` de seleção de aba**
  - **Descrição:** criar `kind="sheet"` com combobox preenchido por `list_sheets`, cascata para colunas e validação.
  - **Problema/necessidade:** AUD-17; hoje a aba é texto livre.
  - **Arquivos/componentes:** `core/base_module.py`, `app/widgets.py`, módulos de planilha, testes.
  - **Prioridade:** P1 · **Complexidade:** grande · **Dependências:** FT-024, FT-021
  - **Critérios de aceite:** abas listadas; troca recarrega colunas; “primeira aba” explícita; erro de leitura visível; todos os módulos usam o novo tipo; testes de UI/headless.
  - **Testes necessários:** arquivo multiaba; troca de aba; aba inválida; CSV; estado salvo.
  - **Status:** pendente

### FT-033 — Melhorar feedback do seletor de colunas

- [ ] **FT-033 — Melhorar feedback do seletor de colunas**
  - **Descrição:** mostrar carregamento/erro ao ler colunas, botão de recarregar e indicação de seleção obsoleta.
  - **Problema/necessidade:** AUD-16/AUD-17; erros silenciosos deixam combos vazios.
  - **Arquivos/componentes:** `app/widgets.py`, `core/spreadsheet_service.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-024
  - **Critérios de aceite:** erro de leitura aparece sem bloquear; recarregar funciona; seleção preservada quando possível; testes.
  - **Testes necessários:** arquivo inválido; troca de arquivo; coluna removida; recarregar.
  - **Status:** pendente

### FT-034 — Validação inline e preflight no formulário

- [ ] **FT-034 — Validação inline e preflight no formulário**
  - **Descrição:** exibir erros próximos aos campos e rodar validações compartilhadas antes de iniciar a thread.
  - **Problema/necessidade:** AUD-35; hoje erros aparecem em diálogo após clicar.
  - **Arquivos/componentes:** `app/widgets.py`, `app/pages.py`, `core/validation_service.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-021, FT-022
  - **Critérios de aceite:** campos obrigatórios/inválidos sinalizados; foco no primeiro erro; execução bloqueada; testes de UI.
  - **Testes necessários:** obrigatório vazio; arquivo/pasta inexistente; coluna inválida; aviso não bloqueante.
  - **Status:** pendente

### FT-035 — Confirmação com resumo do plano

- [ ] **FT-035 — Confirmação com resumo do plano**
  - **Descrição:** substituir o diálogo genérico por um resumo com contagens e amostra do que será feito; alertar se o plano mudou.
  - **Problema/necessidade:** AUD-06; usuário confirma sem saber o impacto.
  - **Arquivos/componentes:** `app/pages.py`, módulos mutáveis, FT-020, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-020
  - **Critérios de aceite:** resumo por operação (ex.: N arquivos, M pastas); opção cancelar; plano alterado invalida; testes.
  - **Testes necessários:** resumo de organizer/duplicatas/empresas; plano alterado; cancelar.
  - **Status:** pendente

### FT-036 — Indicador global de operação e proteção de navegação

- [ ] **FT-036 — Indicador global de operação e proteção de navegação**
  - **Descrição:** mostrar na janela principal que há operação em andamento e impedir/avisar ao iniciar outra operação conflitante.
  - **Problema/necessidade:** AUD-05; operação pode ficar “escondida” em outra página.
  - **Arquivos/componentes:** `app/main_window.py`, `app/pages.py`, coordenador FT-012, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-012, FT-004
  - **Critérios de aceite:** banner/status global; segunda operação bloqueada com explicação; navegação não perde o estado; testes.
  - **Testes necessários:** iniciar/trocar página; concluir/cancelar; tentar segunda operação.
  - **Status:** pendente

### FT-037 — Progresso por fase e cancelamento em pontos seguros

- [ ] **FT-037 — Progresso por fase e cancelamento em pontos seguros**
  - **Descrição:** emitir progresso durante leitura/limpeza, usar modo indeterminado quando não houver total e adicionar `check_cancel` em loops longos.
  - **Problema/necessidade:** AUD-27; barra parada e cancelamento tardio.
  - **Arquivos/componentes:** `core/execution_context.py`, `app/pages.py`, `modules/spreadsheets/cleaner.py`, `modules/files/duplicate_finder.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** fases visíveis; leitura mostra “processando”; limpeza cancela em checkpoint; UI não congela; testes de cancelamento.
  - **Testes necessários:** cancelamento no meio; progresso total/indeterminado; conclusão.
  - **Status:** pendente

### FT-038 — Histórico com filtros, busca, exportação e reexecução

- [ ] **FT-038 — Histórico com filtros, busca, exportação e reexecução**
  - **Descrição:** ampliar o histórico com filtros por módulo/modo/status/período, busca, exportação e reexecução com revalidação.
  - **Problema/necessidade:** AUD-07/AUD-32; histórico hoje é uma lista fixa de 300 registros.
  - **Arquivos/componentes:** `core/history_service.py`, `app/pages.py`, `tests/test_core.py`, testes de UI.
  - **Prioridade:** P1 · **Complexidade:** grande · **Dependências:** FT-017, FT-027
  - **Critérios de aceite:** filtros combinam; exportação CSV; detalhes abrem; reexecutar pede confirmação e revalida caminhos; testes.
  - **Testes necessários:** consultas com filtros; exportação; reexecução com caminho ausente; paginação/limite.
  - **Status:** pendente

### FT-039 — Ações para abrir logs, dados e saídas

- [ ] **FT-039 — Ações para abrir logs, dados e saídas**
  - **Descrição:** adicionar botões “Abrir logs”, “Abrir pasta de dados” e “Abrir saída” em pontos claros da UI.
  - **Problema/necessidade:** AUD-31; usuário não encontra o log citado no erro.
  - **Arquivos/componentes:** `app/main_window.py`, `app/pages.py`, `app/utils.py`, `core/paths.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** pequena · **Dependências:** FT-026
  - **Critérios de aceite:** cada ação abre o local correto; erro orienta o próximo passo; teste de resolução de caminho.
  - **Testes necessários:** caminho existente/inexistente; pasta vs arquivo.
  - **Status:** pendente

### FT-040 — Criar tela de configurações

- [ ] **FT-040 — Criar tela de configurações**
  - **Descrição:** centralizar preferências: retenção, pasta de saída padrão, tema (se houver), reset, localização de dados e logs.
  - **Problema/necessidade:** não há settings; opções ficam espalhadas ou inexistentes.
  - **Arquivos/componentes:** nova página em `app/`, `core/config_service.py`, `app/main_window.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-025, FT-027
  - **Critérios de aceite:** preferências persistem; reset seguro; validação de pasta; testes.
  - **Testes necessários:** salvar/carregar; reset; valor inválido.
  - **Status:** pendente

### FT-041 — Refinar dashboard inicial

- [ ] **FT-041 — Refinar dashboard inicial**
  - **Descrição:** incluir canceladas, estados vazios, atalhos para favoritos/recentes e indicador de última atualização.
  - **Problema/necessidade:** KPIs não cobrem canceladas e a Home não orienta o primeiro uso.
  - **Arquivos/componentes:** `app/pages.py` (`HomePage`), `core/history_service.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** pequena · **Dependências:** FT-038
  - **Critérios de aceite:** números consistentes; estados vazios claros; navegação funciona; testes de estatística.
  - **Testes necessários:** stats com sucesso/alerta/falha/cancelado; zero execuções.
  - **Status:** pendente

### FT-042 — Melhorar tabela de resultados em volume

- [ ] **FT-042 — Melhorar tabela de resultados em volume**
  - **Descrição:** ordenação, filtro, cópia de células/linhas, redimensionamento e paginação/“carregar mais” além de 1.000 linhas.
  - **Problema/necessidade:** AUD-35; conferência manual difícil.
  - **Arquivos/componentes:** `app/widgets.py` (`ResultTable`), `app/pages.py`, testes de UI.
  - **Prioridade:** P2 · **Complexidade:** grande · **Dependências:** —
  - **Critérios de aceite:** ordenar/filtrar/copiar; limite explícito; navegação por teclado; desempenho aceitável; testes.
  - **Testes necessários:** 0/poucas/muitas linhas; colunas variáveis; filtro/ordenação.
  - **Status:** pendente

### FT-043 — Atalhos de teclado e acessibilidade básica

- [ ] **FT-043 — Atalhos de teclado e acessibilidade básica**
  - **Descrição:** adicionar atalhos (buscar, executar, cancelar, exportar, ajuda), foco visível, rótulos e revisão de contraste.
  - **Problema/necessidade:** AUD-35; uso repetitivo e acessibilidade.
  - **Arquivos/componentes:** `app/main_window.py`, `app/pages.py`, `app/theme.py`, testes manuais.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** atalhos documentados; não conflitam com campos de texto; foco navegável; contraste mínimo; checklist manual.
  - **Testes necessários:** teste manual em Windows; smoke de UI.
  - **Status:** pendente

### FT-044 — Ajuda contextual por ferramenta

- [ ] **FT-044 — Ajuda contextual por ferramenta**
  - **Descrição:** adicionar painel/aba “Ajuda” com finalidade, pré-requisitos, exemplos e limitações de cada módulo.
  - **Problema/necessidade:** AUD-35; descrição curta não cobre configuração.
  - **Arquivos/componentes:** `app/pages.py`, metadados de módulo/arquivo de ajuda, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-039
  - **Critérios de aceite:** todos os módulos têm ajuda; exemplos não prometem o que não existe; navegação simples; teste de conteúdo.
  - **Testes necessários:** verificar presença para todos os módulos; links/caminhos.
  - **Status:** pendente

### FT-045 — Melhorar diálogos de erro

- [ ] **FT-045 — Melhorar diálogos de erro**
  - **Descrição:** separar mensagem amigável de detalhe técnico expansível, com “copiar detalhes” e orientação.
  - **Problema/necessidade:** AUD-35; mensagem atual é técnica e sem ação.
  - **Arquivos/componentes:** `app/main_window.py`, `app/pages.py`, `core/exceptions.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** pequena · **Dependências:** FT-022
  - **Critérios de aceite:** diálogo com resumo + detalhe copiável; log referenciado; teste de formatação.
  - **Testes necessários:** erro conhecido/desconhecido; cópia.
  - **Status:** pendente

### FT-046 — Melhorar busca e navegação do catálogo

- [ ] **FT-046 — Melhorar busca e navegação do catálogo**
  - **Descrição:** busca por tags/keywords, estado “nenhum resultado”, breadcrumb/voltar e preservação de posição.
  - **Problema/necessidade:** busca limitada a nome/descrição.
  - **Arquivos/componentes:** `app/main_window.py`, `app/module_registry.py`, metadados de módulo, testes.
  - **Prioridade:** P3 · **Complexidade:** pequena · **Dependências:** FT-041
  - **Critérios de aceite:** encontrar ferramenta por termo útil; estado vazio; navegação previsível; testes.
  - **Testes necessários:** busca com/sem acento; tags; sem resultado.
  - **Status:** pendente

### FT-047 — Criar testes smoke de UI headless

- [ ] **FT-047 — Criar testes smoke de UI headless**
  - **Descrição:** testar abertura da janela, navegação, montagem de formulário, execução de preview e exportação com Tk em ambiente controlado.
  - **Problema/necessidade:** AUD-28; nenhum teste de UI.
  - **Arquivos/componentes:** `tests/`, executor de UI (Windows CI ou Xvfb), helpers.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-014
  - **Critérios de aceite:** smoke roda em CI; falha se janela não abrir ou preview não concluir; tempo controlado; sem dependência de dados do usuário.
  - **Testes necessários:** MainWindow; ModulePage; Home; History.
  - **Status:** pendente

---

## 6. Fase 3 — Expansão funcional

### FT-048 — Suportar múltiplas abas no limpador

- [ ] **FT-048 — Suportar múltiplas abas no limpador**
  - **Descrição:** permitir escolher uma ou várias abas e definir o comportamento de saída (uma aba por vez ou consolidado), documentando o que é preservado.
  - **Problema/necessidade:** AUD-31; hoje lê/grava apenas uma aba e perde o restante.
  - **Arquivos/componentes:** `modules/spreadsheets/cleaner.py`, `core/spreadsheet_service.py`, `core/export_service.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** grande · **Dependências:** FT-032, FT-023
  - **Critérios de aceite:** seleção de abas; saída previsível; limitações (fórmulas/estilos) documentadas; testes com multiaba.
  - **Testes necessários:** uma/múltiplas abas; aba vazia; nomes longos; original intacto.
  - **Status:** pendente

### FT-049 — Preview antes/depois por célula no limpador

- [ ] **FT-049 — Preview antes/depois por célula no limpador**
  - **Descrição:** mostrar amostra de transformações (valor original → novo) além das estatísticas agregadas.
  - **Problema/necessidade:** conferência da limpeza é difícil.
  - **Arquivos/componentes:** `modules/spreadsheets/cleaner.py`, `app/widgets.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** amostra por operação/coluna; limite de linhas; exportação inclui detalhes; testes.
  - **Testes necessários:** CNPJ/data/valor/texto; células vazias; limite.
  - **Status:** pendente

### FT-050 — Política de chaves duplicadas e normalização no comparador

- [ ] **FT-050 — Política de chaves duplicadas e normalização no comparador**
  - **Descrição:** permitir abortar, usar primeira, agregar ou comparar ocorrências; normalizar chaves (CNPJ, caixa, acentos) de forma explícita.
  - **Problema/necessidade:** AUD-18; duplicidade hoje é aviso silencioso.
  - **Arquivos/componentes:** `modules/spreadsheets/comparator.py`, `core/validation_service.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-021
  - **Critérios de aceite:** padrão seguro (abortar) documentado; opções testadas; resumo destaca decisão; testes.
  - **Testes necessários:** chaves duplicadas em A/B; agregação; normalização.
  - **Status:** pendente

### FT-051 — Comparador com abas independentes e relatório de diferenças

- [ ] **FT-051 — Comparador com abas independentes e relatório de diferenças**
  - **Descrição:** permitir escolher aba de A e de B e exportar somente diferenças.
  - **Problema/necessidade:** comparador sempre lê a primeira aba.
  - **Arquivos/componentes:** `modules/spreadsheets/comparator.py`, `app/widgets.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-032, FT-050
  - **Critérios de aceite:** abas independentes; relatório só com diferenças; resumo consistente; testes.
  - **Testes necessários:** abas diferentes; aba ausente; diferenças vazias.
  - **Status:** pendente

### FT-052 — Melhorar relatório do validador de CNPJ

- [ ] **FT-052 — Melhorar relatório do validador de CNPJ**
  - **Descrição:** separar inválidos/vazios/duplicados, detectar coluna e aba, permitir exportar só exceções.
  - **Problema/necessidade:** contadores misturados e erro genérico.
  - **Arquivos/componentes:** `modules/finance/cnpj_validator.py`, `core/validation_service.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-021
  - **Critérios de aceite:** contagens separadas; coluna/aba validadas; relatório de exceções; testes.
  - **Testes necessários:** válidos, inválidos, vazios, duplicados, alfanumérico.
  - **Status:** pendente

### FT-053 — Pastas por empresa com CNPJ, manifesto e preview de conflitos

- [ ] **FT-053 — Pastas por empresa com CNPJ, manifesto e preview de conflitos**
  - **Descrição:** opção de nome por CNPJ/nome curto, manifesto do que foi criado e preview de colisões.
  - **Problema/necessidade:** falta rastreabilidade e critério de nome.
  - **Arquivos/componentes:** `modules/files/company_folders.py`, `core/file_service.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-019
  - **Critérios de aceite:** opções de nome; manifesto; conflito mostrado; nada sobrescrito; testes.
  - **Testes necessários:** CNPJ, nome curto, repetidos, pasta existente.
  - **Status:** pendente

### FT-054 — Presets, recursão e undo no organizador

- [ ] **FT-054 — Presets, recursão e undo no organizador**
  - **Descrição:** salvar regras, opção de varrer subpastas com cuidado e desfazer movimentações.
  - **Problema/necessidade:** regras digitadas toda vez; sem recursão/undo.
  - **Arquivos/componentes:** `modules/files/folder_organizer.py`, `core/config_service.py`, journal FT-019, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-019
  - **Critérios de aceite:** preset salvo/carregado; recursão explícita e segura; undo pelo histórico; testes.
  - **Testes necessários:** preset; recursão; undo; colisão.
  - **Status:** pendente

### FT-055 — Acelerar detecção de duplicatas

- [ ] **FT-055 — Acelerar detecção de duplicatas**
  - **Descrição:** cache de hash (tamanho+mtime), hash parcial e processamento limitado em paralelo; progresso na enumeração.
  - **Problema/necessidade:** AUD-26; hash sequencial em pastas grandes.
  - **Arquivos/componentes:** `modules/files/duplicate_finder.py`, `core/file_service.py`, testes/benchmarks.
  - **Prioridade:** P2 · **Complexidade:** grande · **Dependências:** —
  - **Critérios de aceite:** benchmark com ganho; cache invalidado corretamente; resultado idêntico ao atual; testes.
  - **Testes necessários:** cache hit/miss; arquivo alterado; colisões; benchmark.
  - **Status:** pendente

### FT-056 — Proteger quarentena fora da pasta analisada

- [ ] **FT-056 — Proteger quarentena fora da pasta analisada**
  - **Descrição:** validar caminho, avisar/confirmar quando estiver fora da árvore e impedir quarentena igual à raiz.
  - **Problema/necessidade:** AUD-23; movimentação inesperada.
  - **Arquivos/componentes:** `modules/files/duplicate_finder.py`, `core/file_service.py` (`is_inside`), testes.
  - **Prioridade:** P2 · **Complexidade:** pequena · **Dependências:** —
  - **Critérios de aceite:** caminho externo exige confirmação; raiz bloqueada; teste de path relativo/absoluto.
  - **Testes necessários:** dentro/fora; `..`; absoluto; raiz.
  - **Status:** pendente

### FT-057 — Criar motor de renomeação em lote

- [ ] **FT-057 — Criar motor de renomeação em lote**
  - **Descrição:** modelo de padrão (empresa/CNPJ/competência/tipo), sanitização, resolução de conflitos e plano de renomeação.
  - **Problema/necessidade:** organização manual de documentos.
  - **Arquivos/componentes:** novo `modules/files/file_renamer.py` (ou serviço), `core/normalizers.py`, `core/file_service.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** grande · **Dependências:** FT-021
  - **Critérios de aceite:** padrões previsíveis; preview com conflitos; nada sobrescrito; journal; testes.
  - **Testes necessários:** padrões, acentos, CNPJ, conflitos, extensões.
  - **Status:** pendente

### FT-058 — Expor renomeador na UI com preview e confirmação

- [ ] **FT-058 — Expor renomeador na UI com preview e confirmação**
  - **Descrição:** formulário do renomeador, amostra, conflitos e execução com journal.
  - **Problema/necessidade:** completar a ferramenta de renomeação.
  - **Arquivos/componentes:** `modules/files/file_renamer.py`, `modules/__init__.py`, UI genérica, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-057, FT-032
  - **Critérios de aceite:** módulo registrado; preview/execute; conflitos; undo; testes.
  - **Testes necessários:** integração do módulo; UI smoke; cancelamento.
  - **Status:** pendente

### FT-059 — Implementar conversor de arquivos financeiros

- [ ] **FT-059 — Implementar conversor de arquivos financeiros**
  - **Descrição:** converter XLSX/XLS/CSV com escolha de separador, codificação, decimais e datas.
  - **Problema/necessidade:** formatos recebidos de terceiros.
  - **Arquivos/componentes:** novo `modules/spreadsheets/file_converter.py`, `core/spreadsheet_service.py`, `core/export_service.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-024
  - **Critérios de aceite:** conversões preservam dados esperados; opções explícitas; original intacto; testes.
  - **Testes necessários:** CSV↔XLSX, codificações, separadores, datas/decimais.
  - **Status:** pendente

### FT-060 — Criar motor de regras do validador de planilhas

- [ ] **FT-060 — Criar motor de regras do validador de planilhas**
  - **Descrição:** regras declarativas de obrigatoriedade, tipo, faixa, data, duplicidade e consistência, com relatório.
  - **Problema/necessidade:** conferência manual de qualidade de dados.
  - **Arquivos/componentes:** novo módulo/serviço, `core/validation_service.py`, testes.
  - **Prioridade:** P1 · **Complexidade:** grande · **Dependências:** FT-021
  - **Critérios de aceite:** regras combináveis; relatório por linha/coluna; performance aceitável; testes.
  - **Testes necessários:** cada tipo de regra; combinações; dados válidos/inválidos.
  - **Status:** pendente

### FT-061 — Expor validador de planilhas com presets

- [ ] **FT-061 — Expor validador de planilhas com presets**
  - **Descrição:** UI do validador, presets de regras e exportação de pendências.
  - **Problema/necessidade:** completar a ferramenta.
  - **Arquivos/componentes:** novo módulo, `modules/__init__.py`, UI, testes.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** FT-060, FT-034
  - **Critérios de aceite:** preset salvo; relatório exportável; preview; testes.
  - **Testes necessários:** integração; preset; exportação; UI smoke.
  - **Status:** pendente

### FT-062 — Implementar validador de boleto

- [ ] **FT-062 — Implementar validador de boleto**
  - **Descrição:** validar linha digitável/código de barras, DVs, formato e dados extraíveis.
  - **Problema/necessidade:** conferência de boletos manuais.
  - **Arquivos/componentes:** novo módulo, `core/normalizers.py`, testes com casos conhecidos.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-021
  - **Critérios de aceite:** linhas válidas/inválidas classificadas; mensagens; testes com boletos de referência.
  - **Testes necessários:** bancos/formatos, DVs, entradas malformadas.
  - **Status:** pendente

### FT-063 — Implementar detector de pagamentos duplicados

- [ ] **FT-063 — Implementar detector de pagamentos duplicados**
  - **Descrição:** comparar pagamentos por valor, data, beneficiário e documento, com janela de tolerância.
  - **Problema/necessidade:** risco de pagamento em duplicidade.
  - **Arquivos/componentes:** novo módulo, comparador, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-050
  - **Critérios de aceite:** grupos de suspeitos com evidências; falsos positivos controláveis; exportação; testes.
  - **Testes necessários:** duplicata exata; mesma data/valor; diferenças de nome; janela.
  - **Status:** pendente

### FT-064 — Implementar conferidor de pagamentos

- [ ] **FT-064 — Implementar conferidor de pagamentos**
  - **Descrição:** cruzar pagamentos com remessas/títulos por data, valor, favorecido e CNPJ; separar conciliados/pendentes.
  - **Problema/necessidade:** conciliação manual e propensa a erro.
  - **Arquivos/componentes:** novo módulo, comparador, normalizadores, testes.
  - **Prioridade:** P2 · **Complexidade:** grande · **Dependências:** FT-050
  - **Critérios de aceite:** relatório conciliado/pendente; regras explícitas; tolerâncias; testes com casos reais anonimizados.
  - **Testes necessários:** match exato/aproximado; múltiplos; sem match; duplicidade.
  - **Status:** pendente

### FT-065 — Implementar comparador de períodos

- [ ] **FT-065 — Implementar comparador de períodos**
  - **Descrição:** comparar movimentações/indicadores entre meses/trimestres, com variações absolutas/percentuais.
  - **Problema/necessidade:** análise gerencial manual.
  - **Arquivos/componentes:** novo módulo, comparador, exportação, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-050
  - **Critérios de aceite:** séries alinhadas; variações; relatório; testes.
  - **Testes necessários:** períodos completos/incompletos; divisão por zero; valores nulos.
  - **Status:** pendente

### FT-066 — Implementar conferidor de saldos

- [ ] **FT-066 — Implementar conferidor de saldos**
  - **Descrição:** comparar saldos entre razão/balancete/extrato e destacar diferenças.
  - **Problema/necessidade:** conferência contábil manual.
  - **Arquivos/componentes:** novo módulo, comparador, normalizadores, testes.
  - **Prioridade:** P2 · **Complexidade:** grande · **Dependências:** FT-050
  - **Critérios de aceite:** mapa de contas; diferenças; tolerância; relatório; testes.
  - **Testes necessários:** saldos iguais/diferentes; contas faltantes; múltiplas fontes.
  - **Status:** pendente

### FT-067 — Implementar gerador de rateio

- [ ] **FT-067 — Implementar gerador de rateio**
  - **Descrição:** distribuir despesas por empresa/unidade/centro de custo, conferindo o total.
  - **Problema/necessidade:** rateios manuais.
  - **Arquivos/componentes:** novo módulo, normalizadores, exportação, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-021
  - **Critérios de aceite:** critérios de rateio; arredondamento; total confere; relatório; testes.
  - **Testes necessários:** percentual, peso, partes iguais; arredondamento; total zero.
  - **Status:** pendente

### FT-068 — Implementar calculadoras de juros e atualização monetária

- [ ] **FT-068 — Implementar calculadoras de juros e atualização monetária**
  - **Descrição:** juros simples/compostos, multa/mora e atualização por índice, com memória de cálculo.
  - **Problema/necessidade:** cálculos repetitivos em planilhas.
  - **Arquivos/componentes:** novos módulos, normalizadores, exportação, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-021
  - **Critérios de aceite:** memória passo a passo; parâmetros claros; arredondamento; testes com valores conhecidos.
  - **Testes necessários:** casos simples/compostos; datas; índices; arredondamento.
  - **Status:** pendente

### FT-069 — Implementar verificador de documentos

- [ ] **FT-069 — Implementar verificador de documentos**
  - **Descrição:** conferir documentos esperados por empresa/período/processo, com checklist e relatório de faltantes.
  - **Problema/necessidade:** controle documental manual.
  - **Arquivos/componentes:** novo módulo, `core/file_service.py`, batch, testes.
  - **Prioridade:** P2 · **Complexidade:** grande · **Dependências:** FT-024
  - **Critérios de aceite:** regras de expectativa; relatório; nomes/pastas; testes.
  - **Testes necessários:** completo/faltante; duplicado; subpastas; padrões.
  - **Status:** pendente

### FT-070 — Implementar busca de arquivos por metadados

- [ ] **FT-070 — Implementar busca de arquivos por metadados**
  - **Descrição:** buscar por nome/extensão/pasta/tamanho/data, com filtros e exportação; conteúdo textual em fase posterior.
  - **Problema/necessidade:** localizar documentos rapidamente.
  - **Arquivos/componentes:** novo módulo, `core/file_service.py`, testes.
  - **Prioridade:** P3 · **Complexidade:** grande · **Dependências:** FT-030
  - **Critérios de aceite:** filtros combinam; performance aceitável; exportação; testes.
  - **Testes necessários:** filtros; acentos; subpastas; arquivos inacessíveis.
  - **Status:** pendente

### FT-071 — Implementar ferramentas de PDF

- [ ] **FT-071 — Implementar ferramentas de PDF**
  - **Descrição:** unir, dividir, reordenar/extrair páginas e converter imagens, com dependência aprovada.
  - **Problema/necessidade:** organização de comprovantes/documentos.
  - **Arquivos/componentes:** novo módulo, dependência (ex.: `pypdf`, a aprovar), testes.
  - **Prioridade:** P3 · **Complexidade:** grande · **Dependências:** —
  - **Critérios de aceite:** operações básicas; preservação de páginas; erros claros; licença/tamanho avaliados; testes.
  - **Testes necessários:** PDFs de amostra; senha/corrompido; páginas.
  - **Status:** pendente

### FT-072 — Implementar gerenciador de área de transferência

- [ ] **FT-072 — Implementar gerenciador de área de transferência**
  - **Descrição:** histórico local de textos copiados, favoritos e busca.
  - **Problema/necessidade:** reutilizar CNPJs/códigos.
  - **Arquivos/componentes:** novo módulo/serviço, persistência, testes.
  - **Prioridade:** P3 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** local-only; limite/retenção; busca; testes.
  - **Testes necessários:** captura simulada; favoritos; retenção.
  - **Status:** pendente

### FT-073 — Implementar fluxo de caixa e layouts de cobrança

- [ ] **FT-073 — Implementar fluxo de caixa e layouts de cobrança**
  - **Descrição:** simular entradas/saídas/saldo e exportar dados em layouts configuráveis.
  - **Problema/necessidade:** planejamento e integração com cobrança.
  - **Arquivos/componentes:** novos módulos, exportação, testes.
  - **Prioridade:** P3 · **Complexidade:** grande · **Dependências:** FT-067, FT-068
  - **Critérios de aceite:** cenários; saldo; layout validado; testes.
  - **Testes necessários:** cenários; datas; totais; layout.
  - **Status:** pendente

---

## 7. Fase 4 — Automação e integração

### FT-074 — Criar motor de processamento em lote

- [ ] **FT-074 — Criar motor de processamento em lote**
  - **Descrição:** executar um módulo sobre múltiplos arquivos/abas, com plano consolidado, journal, continuidade/parada e resumo.
  - **Problema/necessidade:** repetição manual é o maior custo operacional.
  - **Arquivos/componentes:** novo serviço `core/batch_service.py`, contrato de módulo, UI, testes.
  - **Prioridade:** P1 · **Complexidade:** grande · **Dependências:** FT-020, FT-019
  - **Critérios de aceite:** seleção múltipla; progresso por item; falha não interrompe tudo por padrão (configurável); journal; resumo; testes.
  - **Testes necessários:** lote feliz; item com erro; cancelamento; retomada; 100 itens.
  - **Status:** pendente

### FT-075 — Expor lote na UI com relatório consolidado

- [ ] **FT-075 — Expor lote na UI com relatório consolidado**
  - **Descrição:** seleção de arquivos/abas, preview consolidado, execução e relatório por item.
  - **Problema/necessidade:** completar a capacidade de lote.
  - **Arquivos/componentes:** `app/pages.py`, `app/widgets.py`, batch service, testes.
  - **Prioridade:** P2 · **Complexidade:** grande · **Dependências:** FT-074
  - **Critérios de aceite:** UI clara; status por item; exportação; testes/UI smoke.
  - **Testes necessários:** integração; falhas; cancelamento; exportação.
  - **Status:** pendente

### FT-076 — Criar modelo e motor de fluxos encadeados

- [ ] **FT-076 — Criar modelo e motor de fluxos encadeados**
  - **Descrição:** definir etapas, entradas/saídas, validação e execução sequencial com falha controlada.
  - **Problema/necessidade:** rotinas mensais compostas.
  - **Arquivos/componentes:** novo serviço, batch, journal, testes.
  - **Prioridade:** P2 · **Complexidade:** grande · **Dependências:** FT-020, FT-074
  - **Critérios de aceite:** fluxo salvo; validação de compatibilidade; execução com log; falha não corrompe; testes.
  - **Testes necessários:** 2–3 etapas; saída→entrada; falha no meio; reexecução.
  - **Status:** pendente

### FT-077 — Expor fluxos na UI

- [ ] **FT-077 — Expor fluxos na UI**
  - **Descrição:** editor/lista de fluxos, execução, histórico de execução e diagnóstico por etapa.
  - **Problema/necessidade:** tornar automação acessível.
  - **Arquivos/componentes:** `app/pages.py`, novo editor, testes.
  - **Prioridade:** P2 · **Complexidade:** grande · **Dependências:** FT-076
  - **Critérios de aceite:** criar/salvar/executar; status por etapa; testes/UI smoke.
  - **Testes necessários:** fluxo completo; etapa inválida; cancelamento.
  - **Status:** pendente

### FT-078 — Criar presets reutilizáveis de módulos

- [ ] **FT-078 — Criar presets reutilizáveis de módulos**
  - **Descrição:** salvar/carregar múltiplos conjuntos de parâmetros por módulo.
  - **Problema/necessidade:** repetir configuração toda vez.
  - **Arquivos/componentes:** `core/config_service.py`, `app/widgets.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-054
  - **Critérios de aceite:** criar/renomear/excluir preset; validação; testes.
  - **Testes necessários:** salvar/carregar; preset inválido; colisão de nome.
  - **Status:** pendente

### FT-079 — Implementar monitor de pastas

- [ ] **FT-079 — Implementar monitor de pastas**
  - **Descrição:** detectar arquivos novos/alterados e disparar rotinas configuradas, com dry-run e limites.
  - **Problema/necessidade:** automação de entrada de documentos.
  - **Arquivos/componentes:** novo serviço, batch/fluxos, testes.
  - **Prioridade:** P3 · **Complexidade:** grande · **Dependências:** FT-074
  - **Critérios de aceite:** evento dispara ação; debounce; log; desligado por padrão; testes.
  - **Testes necessários:** criação/alteração/remoção; debounce; falha.
  - **Status:** pendente

### FT-080 — Implementar agendador de tarefas

- [ ] **FT-080 — Implementar agendador de tarefas**
  - **Descrição:** executar fluxos em horários definidos, com histórico e opção de usar o Agendador do Windows.
  - **Problema/necessidade:** rotinas fora do horário de trabalho.
  - **Arquivos/componentes:** novo serviço, fluxos, documentação, testes.
  - **Prioridade:** P3 · **Complexidade:** grande · **Dependências:** FT-076
  - **Critérios de aceite:** agendamento confiável; log; falha visível; testes com relógio simulado.
  - **Testes necessários:** execução agendada; sobreposição; falha; reinício.
  - **Status:** pendente

### FT-081 — Notificações de conclusão

- [ ] **FT-081 — Notificações de conclusão**
  - **Descrição:** notificar sucesso/falha de operações longas/lote, respeitando configuração.
  - **Problema/necessidade:** usuário não precisa vigiar a tela.
  - **Arquivos/componentes:** `app/pages.py`, `core/config_service.py`, testes.
  - **Prioridade:** P3 · **Complexidade:** pequena · **Dependências:** FT-036
  - **Critérios de aceite:** notificação configurável; sem spam; testes.
  - **Testes necessários:** sucesso/falha; desabilitado; múltiplas operações.
  - **Status:** pendente

### FT-082 — Criar modo CLI headless

- [ ] **FT-082 — Criar modo CLI headless**
  - **Descrição:** executar módulos/fluxos por linha de comando com parâmetros, saída e código de retorno.
  - **Problema/necessidade:** integração com scripts/agendador.
  - **Arquivos/componentes:** novo entrypoint/CLI, serviços core, documentação, testes.
  - **Prioridade:** P3 · **Complexidade:** grande · **Dependências:** FT-074
  - **Critérios de aceite:** comandos documentados; códigos de retorno; log; sem Tk; testes.
  - **Testes necessários:** execução de cada tipo; erro; parâmetros inválidos.
  - **Status:** pendente

---

## 8. Fase 5 — Distribuição e maturidade

### FT-083 — Fixar dependências e matriz de Python

- [ ] **FT-083 — Fixar dependências e matriz de Python**
  - **Descrição:** criar constraints/lock, separar runtime/dev e documentar versões suportadas.
  - **Problema/necessidade:** AUD-29; builds não reproduzíveis.
  - **Arquivos/componentes:** `requirements*.txt`, lock, README, build.
  - **Prioridade:** P1 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** ambiente recriado do zero usa as mesmas versões; Python suportado testado; política de atualização documentada.
  - **Testes necessários:** instalação limpa; suíte; build.
  - **Status:** pendente

### FT-084 — Adicionar metadados, versão e ícone ao executável

- [ ] **FT-084 — Adicionar metadados, versão e ícone ao executável**
  - **Descrição:** configurar versão de arquivo, nome, ícone e informações do produto no spec/PyInstaller.
  - **Problema/necessidade:** AUD-30; executável sem identidade profissional.
  - **Arquivos/componentes:** `finance_toolkit.spec`, recursos, `app/__init__.py`, build.
  - **Prioridade:** P1 · **Complexidade:** pequena · **Dependências:** —
  - **Critérios de aceite:** propriedades do `.exe` corretas; ícone aparece; versão única/fonte de verdade.
  - **Testes necessários:** inspeção das propriedades; build.
  - **Status:** pendente

### FT-085 — Criar build reproduzível com smoke test do executável

- [ ] **FT-085 — Criar build reproduzível com smoke test do executável**
  - **Descrição:** pipeline/script que instala, testa, gera o exe e o abre em ambiente controlado executando uma operação mínima.
  - **Problema/necessidade:** AUD-30; build nunca foi validado nesta análise.
  - **Arquivos/componentes:** `build.bat`/novo script, CI Windows, testes de fumaça.
  - **Prioridade:** P1 · **Complexidade:** grande · **Dependências:** FT-014, FT-084
  - **Critérios de aceite:** build em máquina limpa; exe inicia e executa preview/exporta; falha retorna código; artefato versionado.
  - **Testes necessários:** build completo; smoke; instalação sem Python.
  - **Status:** pendente

### FT-086 — Criar instalador e desinstalador

- [ ] **FT-086 — Criar instalador e desinstalador**
  - **Descrição:** empacotar o app com instalador Windows, atalhos e preservação de dados na desinstalação.
  - **Problema/necessidade:** AUD-30; distribuição manual do exe.
  - **Arquivos/componentes:** script de instalador (ex.: Inno Setup), docs, build.
  - **Prioridade:** P2 · **Complexidade:** grande · **Dependências:** FT-085
  - **Critérios de aceite:** instala/desinstala em máquina limpa; dados preservados/opção de remover; testes.
  - **Testes necessários:** instalação limpa; upgrade; desinstalação.
  - **Status:** pendente

### FT-087 — Implementar atualização e assinatura de código

- [ ] **FT-087 — Implementar atualização e assinatura de código**
  - **Descrição:** estratégia de atualização com verificação de assinatura/hash e rollback.
  - **Problema/necessidade:** AUD-30/AUD-34; versões antigas e SmartScreen.
  - **Arquivos/componentes:** pipeline de release, updater, docs.
  - **Prioridade:** P2 · **Complexidade:** grande · **Dependências:** FT-086
  - **Critérios de aceite:** atualização segura; falha reverte; executável assinado; testes/documentação.
  - **Testes necessários:** update feliz; hash inválido; rollback.
  - **Status:** pendente

### FT-088 — Gerar pacote de diagnóstico

- [ ] **FT-088 — Gerar pacote de diagnóstico**
  - **Descrição:** coletar versão, SO, configuração (sem conteúdo), log recente e estado do banco em um arquivo para suporte.
  - **Problema/necessidade:** AUD-31; suporte depende de idas e vindas.
  - **Arquivos/componentes:** `app/main_window.py`, `core/logging_service.py`, `core/paths.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-026, FT-039
  - **Critérios de aceite:** pacote gerado; nenhum conteúdo de célula; caminho exibido; testes.
  - **Testes necessários:** conteúdo do pacote; redaction; falha de escrita.
  - **Status:** pendente

### FT-089 — Backup, restauração e migração dos dados do app

- [ ] **FT-089 — Backup, restauração e migração dos dados do app**
  - **Descrição:** exportar/importar banco/configurações e restaurar após migração/atualização.
  - **Problema/necessidade:** AUD-09/AUD-24; dados locais sem recuperação.
  - **Arquivos/componentes:** `core/history_service.py`, `core/paths.py`, `app/pages.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-016, FT-031
  - **Critérios de aceite:** backup/restore completos; validação de versão; teste com banco antigo.
  - **Testes necessários:** backup/restauração; versão incompatível; corrupção.
  - **Status:** pendente

### FT-090 — Produzir manual, changelog e documentação de suporte

- [ ] **FT-090 — Produzir manual, changelog e documentação de suporte**
  - **Descrição:** manual do usuário por ferramenta, limitações, changelog e guia de suporte.
  - **Problema/necessidade:** AUD-34; README é a única fonte e está incompleto.
  - **Arquivos/componentes:** `docs/`, `README.md`, ajuda in-app.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** —
  - **Critérios de aceite:** manual cobre os módulos; limitações explícitas; changelog versionado; revisão.
  - **Testes necessários:** revisão de conteúdo; links; consistência com a UI.
  - **Status:** pendente

### FT-091 — Formalizar checklist e política de release

- [ ] **FT-091 — Formalizar checklist e política de release**
  - **Descrição:** checklist (testes, build, smoke, docs, migração, tag) e política de versionamento semântico.
  - **Problema/necessidade:** AUD-01/AUD-34; releases ad hoc.
  - **Arquivos/componentes:** documentação, Git, build.
  - **Prioridade:** P1 · **Complexidade:** pequena · **Dependências:** FT-015
  - **Critérios de aceite:** checklist aplicado a uma release; versão/tag consistentes; artefatos anexados.
  - **Testes necessários:** simulação de release; verificação de artefatos.
  - **Status:** pendente

### FT-092 — Criar benchmarks de desempenho

- [ ] **FT-092 — Criar benchmarks de desempenho**
  - **Descrição:** medir leitura, limpeza, comparação, hash e exportação em 10k/100k linhas e pastas grandes; registrar baseline.
  - **Problema/necessidade:** AUD-20/AUD-22/AUD-26; sem evidência de escala.
  - **Arquivos/componentes:** `benchmarks/`, fixtures geradas, documentação.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-023
  - **Critérios de aceite:** comandos reproduzíveis; tempo/memória registrados; comparação antes/depois; sem dados reais.
  - **Testes necessários:** geração de fixtures; execução; limites.
  - **Status:** pendente

### FT-093 — Revisão de segurança das operações destrutivas

- [ ] **FT-093 — Revisão de segurança das operações destrutivas**
  - **Descrição:** checklist e testes para mover/criar/renomear: confirmação, journal, conflito, path traversal, permissões, cancelamento e recuperação.
  - **Problema/necessidade:** AUD-08/AUD-23; alto impacto.
  - **Arquivos/componentes:** módulos de arquivos, `core/file_service.py`, testes.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-019
  - **Critérios de aceite:** checklist assinado; testes adversariais; nenhum caminho sobrescreve; falhas seguras.
  - **Testes necessários:** path traversal; colisão; permissão; cancelamento; journal incompleto.
  - **Status:** pendente

### FT-094 — Planejar piloto e feedback de usuários

- [ ] **FT-094 — Planejar piloto e feedback de usuários**
  - **Descrição:** definir grupo piloto, roteiro de teste, coleta de feedback e critérios de saída.
  - **Problema/necessidade:** reduzir risco de produto sem telemetria.
  - **Arquivos/componentes:** documentação, checklist, formulário.
  - **Prioridade:** P3 · **Complexidade:** média · **Dependências:** FT-085
  - **Critérios de aceite:** piloto executado; feedback categorizado; decisões registradas.
  - **Testes necessários:** não se aplica; roteiro validado.
  - **Status:** pendente

### FT-095 — Validar matriz de compatibilidade Windows

- [ ] **FT-095 — Validar matriz de compatibilidade Windows**
  - **Descrição:** testar Windows 10/11, versões de Python suportadas, DPI, caminhos longos, Excel/CSV e antivírus.
  - **Problema/necessidade:** AUD-29/AUD-30; desenvolvimento em Linux não cobre o alvo.
  - **Arquivos/componentes:** CI/máquinas de teste, docs, build.
  - **Prioridade:** P2 · **Complexidade:** média · **Dependências:** FT-085
  - **Critérios de aceite:** matriz registrada; falhas conhecidas documentadas; smoke em cada combinação suportada.
  - **Testes necessários:** instalação; abertura; operações; exportação; Tk/DPI.
  - **Status:** pendente

---

## 9. Dependências críticas entre tarefas

```text
Confiança imediata
  FT-001/002/005/003/004/006/007/008/010
        │
        ├─→ FT-014 (regressão/cobertura)
        │
Núcleo
  FT-016 (migrações) ─→ FT-017 (detalhes) ─→ FT-019 (journal/undo)
        │                     │                    │
        └─→ FT-018 ───────────┘                    ├─→ FT-053/054
                                                   └─→ FT-020 (plano)
  FT-021 (validação) ─→ FT-022 (erros) ─→ FT-034/035
        │
        └─→ FT-011/029 (contrato)
  FT-024 (abas) ─→ FT-032 (sheet spec) ─→ FT-033/048/051/059

Experiência
  FT-012 (lock) ─→ FT-036 (indicador) ─→ FT-081 (notificações)
  FT-017/027 ─→ FT-038 (histórico)
  FT-026/039 ─→ FT-088 (diagnóstico)

Automação
  FT-019/020 ─→ FT-074 (lote) ─→ FT-075 ─→ FT-076/079/082
  FT-076 ─→ FT-080 (agendador)

Distribuição
  FT-014/084 ─→ FT-085 (build/smoke) ─→ FT-086 ─→ FT-087
  FT-085 ─→ FT-094/095
```

### Bloqueios de decisão (não de código)

| Decisão necessária | Impacto | Tarefas afetadas |
|---|---|---|
| Autorizar Git e fluxo de branches | Sem rollback/revisão | FT-015, FT-091 |
| Autorizar dependências de desenvolvimento (cobertura/lint) | Sem portão de qualidade | FT-014 |
| Definir política de retenção de histórico | Privacidade/crescimento | FT-018, FT-027 |
| Aprovar dependência de PDF (se Fase 3 avançar) | Licença/tamanho do exe | FT-071 |
| Definir se haverá assinatura de código | Custo/processo de distribuição | FT-087 |
| Validar regras financeiras com usuários | Risco de domínio | FT-062–FT-068 |

---

## 10. Checklist de execução por tarefa

Antes de marcar uma tarefa como concluída:

- [ ] Li o achado de auditoria e os arquivos indicados.
- [ ] Verifiquei dependências e nenhuma está pendente/bloqueada.
- [ ] Implementei o menor escopo que satisfaz o aceite.
- [ ] Adicionei/atualizei testes (incluindo regressão, quando P0/P1).
- [ ] Rodei a suíte completa e a compilação.
- [ ] Testei o caminho de erro/cancelamento, quando aplicável.
- [ ] Não alterei arquivos do usuário durante testes.
- [ ] Atualizei documentação/changelog quando o comportamento mudou.
- [ ] Registrei o status e a evidência (comando/teste) na tarefa ou no PR.
- [ ] Não introduzi dependência nova sem autorização.

---

## 11. Observações finais

- Este backlog é **propositalmente maior que uma release**. As fases 0–2 são a prioridade; as fases 3–5 devem ser refinadas com feedback real.
- Tarefas grandes (FT-019, FT-023, FT-032, FT-038, FT-074, FT-076, FT-085) devem ser divididas em subtarefas no momento da execução, mantendo o ID principal e criando IDs `FT-xxx-a`, `FT-xxx-b` se necessário.
- Nenhuma tarefa deste documento foi executada. O próximo passo é a aprovação do planejamento e a escolha da primeira tarefa (recomendação: **FT-001**).
