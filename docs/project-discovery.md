# Finance Toolkit — Discovery do Projeto

> **Etapa:** 1 — Discovery completo  
> **Data da análise:** 19/11/2026  
> **Versão analisada:** 0.1.0 (`app/__init__.py`)  
> **Escopo:** repositório inteiro (`app/`, `core/`, `modules/`, `tests/`, scripts, spec, README)  
> **Natureza desta entrega:** análise e documentação. Nenhum arquivo de código, configuração, dependência ou interface foi alterado.

---

## 1. Resumo executivo

O **Finance Toolkit** é um aplicativo desktop local, escrito em **Python + Tkinter/ttk**, voltado a profissionais que lidam com grandes volumes de arquivos, planilhas e rotinas financeiras/administrativas. O produto se posiciona como um “hub” de utilitários: uma janela única, catálogo pesquisável, formulários gerados a partir de metadados, pré-visualização antes de alterar arquivos, execução em segundo plano, cancelamento, histórico e exportação de resultados.

Na versão 0.1.0 existem:

- **6 ferramentas operacionais**: organizador de pastas, detector de duplicatas, criador de pastas por empresa, limpador de planilhas, comparador de planilhas e validador de CNPJ.
- **25 utilitários planejados** no catálogo, exibidos como “em breve”.
- **Núcleo compartilhado** independente da interface (`core/`), com contrato de módulo, contexto de execução, histórico SQLite, normalizadores, leitura/exportação de planilhas e operações seguras de arquivos.
- **18 testes automatizados** (`unittest`), todos aprovados na execução desta análise.
- **Build para Windows** via PyInstaller (`finance_toolkit.spec` + `build.bat`).

O projeto é pequeno (≈3.000 linhas de Python em `app/` + `core/` + `modules/`, ≈3.400 contando testes), coeso e com uma separação núcleo/interface acima da média para um MVP. A maturidade, porém, é de **protótipo funcional avançado / MVP inicial**, não de produto pronto para distribuição ampla: faltam versionamento de repositório, integração contínua, migrações de banco, rastreabilidade completa das execuções, tratamento de encerramento durante operações, testes de interface e de plataforma, empacotamento verificado e mecanismos de atualização.

---

## 2. Como o sistema funciona, de ponta a ponta

### 2.1 Inicialização

1. `main.py` importa `app.bootstrap.run` e o executa.
2. `run()`:
   - configura logging rotativo (`core/logging_service.py`);
   - registra o início no log;
   - habilita DPI awareness no Windows (`ctypes.windll.shcore.SetProcessDpiAwareness(1)`);
   - importa `MainWindow` somente depois, para não carregar Tkinter antes da hora;
   - cria `HistoryService(db_path())` (SQLite em `%APPDATA%\FinanceToolkit` ou `~/.finance_toolkit`);
   - cria `Services(history, ConfigService(history))`;
   - monta o registro de módulos (`build_registry()`);
   - instancia `MainWindow(...)` e entra no `mainloop()`.

Evidência: `main.py:1-5`, `app/bootstrap.py:14-31`, `core/paths.py:10-20`, `core/history_service.py:37-43`.

### 2.2 Registro de módulos

- `modules/__init__.py` contém uma **lista explícita** de imports e instâncias (decisão tomada para o PyInstaller detectar os módulos).
- `modules/catalog.py` contém os 25 módulos planejados (`PlannedModule`), com categoria e fase.
- `app/module_registry.py` registra disponíveis e planejados, impede IDs duplicados e fornece categorias/ordem de exibição.
- A interface monta o menu lateral agrupado por categoria, com busca por nome/descrição e indicação “em breve” para planejados.

Evidência: `modules/__init__.py:1-23`, `modules/catalog.py:11-71`, `app/module_registry.py:10-51`, `app/main_window.py:70-90`.

### 2.3 Navegação

- A janela principal tem menu lateral fixo, busca, árvore de módulos e botões “Início”/“Histórico”.
- As páginas são criadas sob demanda e **cacheadas** em `MainWindow._pages`; ao trocar de página, a anterior é ocultada com `pack_forget()`.
- `show_module()` resolve o módulo real ou o planejado e cria a página correspondente.
- A seleção da árvore dispara `show_module()`; ao clicar em “Início”/“Histórico”, a seleção é limpa.

Evidência: `app/main_window.py:28-33`, `app/main_window.py:94-132`.

### 2.4 Formulário e parâmetros

Cada módulo declara uma lista de `ParamSpec`. A interface gera o formulário automaticamente para os tipos:

| `kind` | Controle gerado |
|---|---|
| `file` | campo + botão “Procurar…” |
| `folder` | campo + seletor de pasta |
| `text` | entrada de uma linha |
| `multiline` | `tk.Text` |
| `choice` | `Combobox` somente leitura |
| `bool` | `Checkbutton` |
| `column` | `Combobox` preenchido com colunas da planilha de origem |
| `columns` | `Listbox` de seleção múltipla |

Colunas são carregadas ao escolher/tirar o foco do arquivo ou ao apertar Enter. O campo de aba é identificado **pelo nome fixo `"sheet"`** e também dispara recarga. Erros de leitura silenciosos são engolidos quando a recarga é automática; só aparecem em recarga explícita.

Evidência: `core/base_module.py:29-57`, `app/widgets.py:107-304`.

### 2.5 Validação e confirmação

Antes de executar/pré-visualizar:

1. `ParamForm.get_values()` coleta os valores.
2. `module.validate(values)` devolve `Issue` de erro/aviso.
3. Erros bloqueiam; avisos pedem confirmação.
4. Em modo `execute`, se `module.requires_confirmation(values)` for verdadeiro, pede confirmação genérica (“vai alterar arquivos”).
5. Os valores são salvos em `module_settings` (SQLite) **antes** da execução.

Evidência: `app/pages.py:133-153`, `core/base_module.py:120-139`.

### 2.6 Execução em segundo plano

1. `ModulePage._start()` limpa estado, cria uma linha em `executions` com status `running`, limpa tabela/log e desabilita botões.
2. Cria uma thread `daemon` executando `_work(mode, values)`.
3. Na thread, cria-se `ExecutionContext` com:
   - `emit` que apenas enfileira tuplas (`log`, `progress`, `done`) em `queue.Queue`;
   - `cancel_event` compartilhado.
4. O módulo executa `preview()` ou `execute()`, chamando `ctx.log()`, `ctx.progress()` e `ctx.check_cancel()`.
5. A interface consulta a fila a cada ~80 ms (`_poll`), atualiza log, barra e status.
6. Ao receber `done`, `_finish()` registra o resultado no histórico (`history.finish`) e habilita exportação/abertura de saída.

Evidência: `app/pages.py:155-232`, `core/execution_context.py:15-45`.

### 2.7 Cancelamento

- O botão “Cancelar” define o `threading.Event` e desabilita a si mesmo.
- Módulos só são interrompidos nos pontos em que chamam `ctx.check_cancel()`, que lança `CancelledError`.
- `_work` captura `CancelledError` e devolve `Result(status="cancelled")`.
- Alguns módulos capturam o cancelamento internamente (organizador, duplicatas, pastas por empresa) para registrar o que já foi feito e marcar o resultado como cancelado.
- **Não há cancelamento durante leituras longas de planilha** nem durante a maior parte da limpeza de dados; nesses trechos a interface fica aguardando.

Evidência: `core/execution_context.py:39-45`, `app/pages.py:172-185`, `modules/files/folder_organizer.py:136-165`.

### 2.8 Resultado, histórico e exportação

- O módulo devolve `Result` com status, resumo, contadores, arquivos gerados e `details` (linhas de tabela).
- A interface exibe até 1.000 linhas (`ResultTable.MAX_ROWS`) e exporta **todas** as linhas de `details` para XLSX ou CSV escolhido pelo usuário.
- O histórico grava: módulo, versão, modo, início/fim, status, resumo, contadores, parâmetros (JSON), arquivos de saída (JSON) e eventos de log.
- **Os `details` não são persistidos no histórico.** Depois de fechar o app, não é possível auditar quais arquivos foram movidos, quais células mudaram ou quais CNPJs falharam; resta apenas o resumo e o log.
- A tela de detalhe do histórico mostra parâmetros, contadores, saída e log, mas não as linhas de resultado.

Evidência: `core/base_module.py:73-108`, `app/pages.py:217-232`, `core/history_service.py:12-30`, `core/history_service.py:57-78`, `app/pages.py:379-409`.

---

## 3. Estrutura de diretórios

```text
FinanceToolkit/
├── main.py                     # entrada: chama app.bootstrap.run()
├── finance_toolkit.spec        # PyInstaller (onefile, console=False)
├── requirements.txt            # pandas, openpyxl, xlrd (sem versões fixas)
├── requirements-build.txt      # requirements + pyinstaller
├── build.bat                   # venv, deps, testes, PyInstaller
├── run_dev.bat                 # venv, deps, python main.py
├── run_tests.bat               # venv, deps, unittest discover
├── README.md                   # visão, arquitetura, uso, segurança, roadmap
├── app/                        # interface Tkinter
│   ├── bootstrap.py            # inicialização
│   ├── main_window.py          # shell, menu, busca, navegação, erro global
│   ├── pages.py                # Home, Module, History, Planned
│   ├── widgets.py              # ParamForm, ResultTable, ScrollFrame
│   ├── module_registry.py      # registro de módulos/planejados
│   ├── services.py             # container de serviços (history, config)
│   ├── theme.py                # tema escuro
│   ├── utils.py                # abrir arquivo/pasta no SO
│   └── __init__.py             # __version__ = "0.1.0"
├── core/                       # serviços sem dependência de UI
│   ├── base_module.py          # BaseModule, ParamSpec, Issue, Result, build_result
│   ├── execution_context.py    # log/progresso/cancelamento
│   ├── history_service.py      # SQLite: execuções, eventos, settings, favoritos
│   ├── config_service.py       # wrapper de preferências
│   ├── logging_service.py      # log rotativo
│   ├── paths.py                # %APPDATA%/FinanceToolkit ou ~/.finance_toolkit
│   ├── exceptions.py           # ToolkitError, ValidationError, CancelledError
│   ├── normalizers.py          # texto, CNPJ, números, datas
│   ├── validation_service.py    # validação CNPJ e duplicidades
│   ├── file_service.py         # nomes seguros, move sem sobrescrita, hash, varredura
│   ├── spreadsheet_service.py  # leitura XLSX/XLSM/XLS/CSV/TSV/TXT
│   ├── export_service.py       # XLSX/CSV
│   └── categories.py           # categorias e ordem
├── modules/
│   ├── __init__.py             # lista explícita de módulos disponíveis
│   ├── catalog.py              # 25 utilitários planejados
│   ├── files/
│   │   ├── folder_organizer.py
│   │   ├── duplicate_finder.py
│   │   └── company_folders.py
│   ├── spreadsheets/
│   │   ├── cleaner.py
│   │   └── comparator.py
│   └── finance/
│       └── cnpj_validator.py
└── tests/
    ├── helpers.py              # TempDirCase: diretório temporário + FINANCE_TOOLKIT_HOME
    ├── test_core.py            # normalizadores e histórico
    └── test_modules.py         # 6 módulos + registro
```

Observações:

- Não existe diretório `docs/` prévio; estes documentos são a primeira documentação estruturada.
- Não existe configuração de **OpenSpec** no repositório. Nada foi inicializado ou substituído.
- O diretório **não é um repositório Git** (`git status` não se aplica; não há `.git`), o que é um risco relevante de processo.
- Não há `pyproject.toml`, `setup.cfg`, configuração de lint/format/type check, cobertura, CI ou changelog.

---

## 4. Tecnologias e dependências

| Item | Situação observada |
|---|---|
| Linguagem | Python; código usa `from __future__ import annotations`, `dataclasses`, tipagem parcial |
| Interface | Tkinter/ttk, tema `clam`, tema escuro customizado |
| Dados | pandas 2.3.3 (ambiente local), openpyxl 3.1.5 |
| Excel legado | `xlrd>=2.0.1` declarado, **ausente no ambiente local** |
| Persistência | SQLite via `sqlite3` (stdlib), sem ORM |
| Hash | `hashlib` SHA-256 |
| Empacotamento | PyInstaller (`>=6.0`), onefile, `console=False` |
| Testes | `unittest` (stdlib) |
| Alvo declarado | Windows, Python 3.10–3.12 (README) |
| Ambiente desta análise | Linux, Python 3.13.13, pandas 2.3.3, openpyxl 3.1.5, **sem xlrd**, **sem PyInstaller** |

Riscos de dependência:

- `requirements.txt` usa apenas mínimos (`pandas>=2.0`), sem limite superior, lockfile ou constraints. Uma futura versão do pandas pode quebrar comportamento.
- O README declara Python 3.10–3.12, mas a análise rodou em 3.13; não há matriz testada.
- `xlrd` é opcional na prática (só `.xls`), mas está na instalação obrigatória.
- O build não foi reproduzido nesta máquina (PyInstaller ausente); conclusões sobre o `.exe` são hipóteses a validar no Windows.

---

## 5. Arquitetura atual

### 5.1 Visão em camadas

```text
┌─────────────────────────────────────────────────────────────┐
│ main.py                                                     │
│   └── app/bootstrap.py                                      │
│         ├── logging / paths / HistoryService / ConfigService│
│         ├── ModuleRegistry (modules/__init__ + catalog)     │
│         └── MainWindow (Tkinter)                            │
├─────────────────────────────────────────────────────────────┤
│ app/  — interface e orquestração de tela                    │
│   main_window / pages / widgets / theme / utils             │
│   (formulário genérico, thread, fila, polling, histórico)   │
├─────────────────────────────────────────────────────────────┤
│ modules/ — uma classe BaseModule por ferramenta             │
│   files/ / spreadsheets/ / finance/                         │
│   (validação específica, preview, execute, detalhes)        │
├─────────────────────────────────────────────────────────────┤
│ core/ — serviços compartilhados, sem importar app/          │
│   base_module / execution_context / history / config /      │
│   normalizers / validation / file / spreadsheet / export /  │
│   logging / paths / exceptions / categories                 │
├─────────────────────────────────────────────────────────────┤
│ Sistema operacional: arquivos/pastas + SQLite + log         │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Regra de dependência

- `core/` **não importa** `app/` — confirmado por inspeção. Isso permite testar lógica sem janela.
- `modules/` importa `core/`, mas não importa `app/` (exceto testes de registro).
- `app/` importa `core/` e `modules/` indiretamente via registro.
- Existem acoplamentos residuais da UI a serviços: `app/widgets.py` chama `core.spreadsheet_service.list_columns` diretamente; `app/pages.py` chama `core.export_service.export_rows`. Não quebram a regra principal, mas pulam o container `Services`.
- `app/services.py` só carrega `history` e `config`; não injeta `file`, `export`, `spreadsheet`, `validation`. Os módulos importam serviços diretamente. Para o tamanho atual é simples e testável; para crescer, vale um container mais explícito.

### 5.3 Contrato de módulo

`core/base_module.py` define:

- `ParamSpec`: metadados do formulário;
- `Issue`: erro/aviso de validação;
- `Result`: status, resumo, contadores, arquivos e detalhes;
- `build_result()`: deriva status a partir dos contadores;
- `BaseModule`: `module_id`, `name`, `category`, `description`, `version`, `params`, `modifies_files`, `validate`, `requires_confirmation`, `preview`, `execute`.

O contrato é simples e produtivo: uma ferramenta nova ganha formulário, execução em thread, cancelamento, histórico e exportação sem tocar na UI. Em contrapartida:

- `ctx` não é tipado;
- `details` é `list[dict]` sem esquema;
- `kind` é string livre, validada apenas quando a página é montada (um erro de digitação pode derrubar a abertura da ferramenta);
- não existe um objeto explícito de “plano de execução” reutilizado entre preview e execute.

### 5.4 Serviços compartilhados

| Serviço | Responsabilidade | Observações |
|---|---|---|
| `HistoryService` | execuções, eventos, settings, favoritos | SQLite, uma conexão por operação, sem migrações/retenção |
| `ConfigService` | preferências e últimos parâmetros | fino, em cima de `module_settings` |
| `ExecutionContext` | log, progresso, cancelamento | `emit` para fila; run_id local |
| `logging_service` | log rotativo | 1 MB × 5, sem UI de acesso |
| `paths` | locais de dados | `backups_dir()` existe e não é usado |
| `normalizers` | texto, CNPJ, números, datas | funções puras, boa base de testes |
| `validation_service` | CNPJ e duplicidades | reutilizável |
| `file_service` | nomes seguros, move sem sobrescrever, hash, varredura | `is_inside()` existe e não é usado |
| `spreadsheet_service` | leitura de planilhas | detecta CSV por amostra de 64 KB; sem seleção de abas na UI |
| `export_service` | escrita XLSX/CSV | proteção parcial contra fórmulas; loops célula a célula |

### 5.5 Persistência

Banco: `%APPDATA%\FinanceToolkit\finance_toolkit.db` (Windows) ou `~/.finance_toolkit/finance_toolkit.db` (outros), sobrescrevível por `FINANCE_TOOLKIT_HOME`.

Tabelas:

- `executions`: id, run_id, módulo, versão, modo, início/fim, status, resumo, contadores, `params_json`, `output_files_json`;
- `execution_events`: id, execution_id, timestamp, nível, mensagem;
- `module_settings`: module_id → JSON;
- `favorites`: module_id.

Características:

- `HistoryService.__init__` cria o esquema e marca qualquer execução `running` como `interrupted` — inclusive de outra instância aberta.
- Não há `PRAGMA user_version`, migrações, `WAL`, índices por módulo/modo, limite de crescimento, compactação ou backup automático.
- Os detalhes por linha não são gravados.
- O README reconhece que o histórico não é trilha de auditoria inviolável.

### 5.6 Arquivos e segurança operacional

- Saídas de planilhas usam `unique_path()` (`_1`, `_2`…), preservando o original.
- Movimentações usam `move_safe()` (nunca sobrescreve).
- Duplicatas são movidas para quarentena com manifesto CSV; nada é excluído.
- Regras de nome de pasta são sanitizadas para o Windows.
- Fórmulas em exportação XLSX são neutralizadas apenas quando o texto começa com `"="`; o caminho CSV **não** aplica essa proteção.
- Não há journal/undo geral para movimentações do organizador.
- O manifesto de duplicatas é gravado **depois** das movimentações; um encerramento forçado no meio deixa arquivos movidos sem manifesto.

### 5.7 Threads, fila e ciclo de vida

- Cada `ModulePage` tem sua própria thread, fila, evento de cancelamento e polling.
- Não existe coordenador global: é possível iniciar uma operação em um módulo, navegar para outro e iniciar outra operação simultânea.
- Fechar a janela não pede confirmação nem aguarda threads `daemon`; o processo pode terminar no meio de uma movimentação.
- A interface só é tocada pela thread principal; a thread de trabalho enfileira mensagens. Essa parte está correta.

### 5.8 Testes e build

- 18 testes `unittest`, cobrindo normalizadores, histórico, os 6 módulos e o registro.
- Não há testes de UI, de cancelamento, de encerramento, de erros de leitura, de CSV com codificação problemática, de exportação maliciosa, de desempenho, de `.xls`, de Windows ou do executável.
- `build.bat` cria `.venv`, instala dependências, roda testes e chama PyInstaller. Não há smoke test do `.exe`, metadados de versão, ícone, assinatura ou instalador.

---

## 6. Funcionalidades implementadas

### 6.1 Organizador automático de pastas (`folder_organizer`)

- **Entrada:** pasta, regras `Pasta=termo1, termo2` por nome, regras por extensão, pasta para não classificados.
- **Funcionamento:** lista apenas arquivos da raiz; regras de nome têm prioridade; depois extensão; depois “Outros”. Ignora `desktop.ini`, `thumbs.db` e `~$*`.
- **Saída:** arquivos movidos para subpastas, com detalhes por arquivo (destino, motivo, resultado).
- **Segurança:** `move_safe` nunca sobrescreve; pré-visualização não altera nada; confirmação antes de executar.
- **Limitações:** não é recursivo; não há undo; preview e execute recalculam o plano; nomes são comparados sem remover acentos; pastas não são movidas.

### 6.2 Detector de arquivos duplicados (`duplicate_finder`)

- **Entrada:** pasta, recursivo, ação (relatar/mover), critério de cópia mantida, quarentena.
- **Funcionamento:** agrupa por tamanho, calcula SHA-256 apenas dos candidatos, escolhe o arquivo mantido e relaciona as cópias.
- **Saída:** tabela de grupos, manifesto CSV na quarentena.
- **Segurança:** nunca exclui; quarentena é excluída da varredura; confirmação apenas ao mover.
- **Limitações:** hash sequencial sem cache; manifesto após as movimentações; caminho de quarentena pode sair da pasta analisada sem aviso; arquivos vazios são ignorados; não há undo automatizado.

### 6.3 Criador de pastas por empresa (`company_folders`)

- **Entrada:** planilha, aba (texto), coluna de nome, coluna de situação, valores ativos, pasta destino, palavras de corte.
- **Funcionamento:** considera apenas linhas ativas; gera nome curto até a primeira palavra de corte; agrupa nomes repetidos; cria as pastas que não existem.
- **Saída:** pastas e relatório por empresa.
- **Segurança:** não altera pastas existentes; confirmação antes de executar.
- **Limitações:** não usa CNPJ; não grava manifesto; a pasta destino precisa existir; não há preview de conflito de nomes (apenas “já existe”); depende de a planilha ter as colunas exatas.

### 6.4 Limpador e padronizador de planilhas (`sheet_cleaner`)

- **Entrada:** planilha, aba (texto), opções de remoção de vazios, limpeza de texto, padronização de cabeçalhos, colunas de CNPJ/data/valor, formato numérico, pasta de saída.
- **Funcionamento:** converte células, remove linhas/colunas vazias, normaliza cabeçalhos, formata CNPJ, datas e números.
- **Saída:** `<nome>_limpo.xlsx`, com contadores e estatísticas por operação.
- **Segurança:** original nunca é alterado; saída única.
- **Limitações:** lê apenas uma aba e grava apenas os dados limpos dessa aba (perde outras abas, fórmulas, estilos, larguras etc.); cabeçalhos duplicados após `strip` podem quebrar a limpeza; não há cancelamento durante a limpeza; `preview` faz o trabalho completo.

### 6.5 Comparador de planilhas (`sheet_comparator`)

- **Entrada:** arquivo A, arquivo B, colunas-chave, colunas a comparar, ignorar caixa, tolerância numérica, pasta do relatório.
- **Funcionamento:** indexa por chave, aponta incluídos, removidos e alterados célula a célula; compara texto normalizado e números com tolerância.
- **Saída:** relatório XLSX com Resumo, Incluídos, Removidos, Alterados e Avisos.
- **Segurança:** apenas lê os originais e grava um novo relatório.
- **Limitações:** sempre lê a primeira aba dos dois arquivos; chaves duplicadas usam a primeira e apenas avisam; “1.234” (inteiro com milhar brasileiro) pode ser tratado como 1,234; a tolerância `"0.01"` é interpretada como `1.0` (bug confirmado); não há visualização de diff lado a lado.

### 6.6 Validador de CNPJ (`cnpj_validator`)

- **Entrada:** planilha, aba, coluna de CNPJ, pasta de saída.
- **Funcionamento:** normaliza CNPJ numérico/alfanumérico, valida dois dígitos verificadores, formata, encontra duplicidades entre válidos e gera uma cópia da planilha com três colunas novas.
- **Saída:** `<nome>_cnpj_validado.xlsx` e detalhes por linha.
- **Segurança:** original preservado.
- **Limitações:** coluna inexistente gera erro genérico; não valida a aba antes; “inválida/vazia” são contadas juntas; duplicidades de CNPJs inválidos não são sinalizadas; apenas a primeira aba é processada.

### 6.7 Funcionalidades transversais

- Busca no catálogo (nome/descrição, sem acento/caixa).
- Favoritos por módulo.
- “Usados recentemente” e “Últimas execuções” na Home.
- KPIs de execuções (total, concluídas, com alertas, com falhas); canceladas entram no total, mas não têm cartão.
- Pré-visualização, execução, cancelamento cooperativo.
- Exportação de `details` para XLSX/CSV.
- Histórico com detalhes de parâmetros, log e arquivos de saída.
- Persistência automática dos últimos parâmetros por módulo.
- Tratamento global de exceções de callbacks da UI com log.

---

## 7. Catálogo planejado (25 itens)

Distribuição por categoria e fase declarada em `modules/catalog.py`:

| Categoria | Itens | Fases |
|---|---:|---|
| Arquivos e documentos | 2 | 2, 3 |
| Excel e dados | 3 | 2, 3, 5 |
| Operações financeiras | 9 | 4 |
| Produtividade no Windows | 4 | 3, 5 |
| Controle e auditoria | 7 | 1, 3, 4, 5, 6 |

Observações:

- O README apresenta um roadmap em 6 fases com agrupamento diferente do campo `phase` do catálogo (por exemplo, “fechamento mensal” aparece como fase 6 no catálogo, enquanto a fase 6 do README é instalação/atualização). Há inconsistência de narrativa, não de código.
- `activity_log` (“Log de atividades”, fase 1) se sobrepõe ao Histórico já existente; a decisão de produto precisa ser “ampliar o histórico” versus “criar outro módulo”.
- Os 25 itens variam de pequenos utilitários (conversor, validador de boleto) a iniciativas grandes (OCR, agendador, monitor de pastas, fechamento mensal). Tratá-los como uma lista única de “fases” esconde dependências e riscos.

---

## 8. O que está documentado versus o que está implementado

| Alegação do README | Situação verificada |
|---|---|
| “Todas têm Pré-visualizar, Executar, Cancelar, Exportar, histórico e favoritos” | Verdadeiro para os 6 módulos disponíveis, via contrato genérico. |
| “Arquivos originais nunca são sobrescritos” | Verdadeiro para saídas de módulos (`unique_path`); exportação manual pode sobrescrever por escolha do usuário no diálogo. |
| “Duplicatas vão para quarentena com manifesto CSV, nunca são excluídas” | Verdadeiro, mas o manifesto é gravado após as movimentações. |
| “Os logs registram caminhos e contagens, não o conteúdo das células” | Verdadeiro nos logs observados; exceções inesperadas podem registrar stack traces com caminhos. |
| “Histórico local não é trilha de auditoria inviolável” | Verdadeiro; além disso, não persiste os detalhes por linha, o que limita a rastreabilidade mesmo sem adulteração. |
| “Ler `.xls` exige xlrd (já em requirements)” | Declarado, mas `xlrd` não estava instalado no ambiente analisado. |
| “Tabelas mostram até 1.000 linhas; export traz tudo” | Verdadeiro. |
| “Nenhum dado sai do computador” | Verdadeiro; não há chamadas de rede no código. |
| “core/ não importa app/” | Verdadeiro. |
| “Adicionar ferramenta = criar classe + registrar” | Verdadeiro; a UI é genérica. |
| “25 utilitários no menu como em breve” | Verdadeiro (25 em `PLANNED`). |

---

## 9. Validação executada nesta análise

Comandos e resultados reais (ambiente Linux, sem alterar dados do usuário; `FINANCE_TOOLKIT_HOME` apontando para `/tmp` nos testes de UI):

```text
python3 --version
Python 3.13.13

pandas 2.3.3
openpyxl 3.1.5
xlrd: ModuleNotFoundError
pyinstaller: não instalado
.v venv: não existe

python3 -m unittest discover -s tests -t . -v
Ran 18 tests in 0.229s
OK

python3 -m compileall -q app core modules tests
COMPILE_OK

import de todos os módulos de app/core
IMPORTS_OK

smoke test de UI (MainWindow, banco em /tmp)
UI_OK Finance Toolkit 1220 780

smoke test de fluxo real (SheetCleaner.preview via ModulePage)
Pré-visualização concluída; histórico gravou modo=preview, status=success, processed=1
```

Sondas adicionais (somente leitura, arquivos em `/tmp`):

- `_tolerance("0.01")` → `1.0` (deveria ser `0.01`).
- `same_value("1.234", "1234")` → `False` (esperado `True` para inteiro com milhar brasileiro).
- Exportação CSV de `=HYPERLINK(...)` manteve a fórmula (injeção).
- Cabeçalhos `"X"` e `" X "` viram `"X"`/`"X"` e quebram o limpador (`AttributeError`).
- CSV com byte não-UTF-8 após 64 KB falha com `UnicodeDecodeError`.
- Banco SQLite corrompido levanta `sqlite3.DatabaseError` na inicialização.
- Duas abas com nomes longos iguais após truncamento fazem a segunda sobrescrever a primeira silenciosamente.

O build PyInstaller **não foi executado** (ferramenta ausente e alvo Windows). Portanto, não se declara o executável como validado.

---

## 10. Limitações e lacunas identificadas

1. **Rastreabilidade incompleta:** detalhes por linha não são salvos; `run_id` do log não é o mesmo do registro no banco; não há undo/journal.
2. **Operações concorrentes e encerramento:** sem coordenação global; fechar a janela pode interromper movimentações sem registro final.
3. **Entrada de planilhas:** sem seletor de abas na UI (apesar de `list_sheets()` existir e não ser usado); sem validação prévia de coluna/aba; heurística de CSV frágil; cabeçalhos duplicados.
4. **Comparação financeira:** bug de tolerância; inteiros com separador de milhar; política de chaves duplicadas conservadora e silenciosa.
5. **Exportação:** injeção de fórmulas em CSV; proteção XLSX parcial; colisão de nomes de abas; loops célula a célula caros; tudo em memória.
6. **Produto:** processa um arquivo/aba por vez; não há lote, fluxos, agendamento, presets, undo, relatórios gerenciais ou configurações centrais.
7. **Histórico:** sem filtros, busca, exportação, reexecução, retenção ou controles de privacidade; cresce sem limite.
8. **UX:** erros técnicos, sem acesso ao log pela interface, progresso grosseiro, cancelamento limitado, tabela truncada em 1.000 linhas, sem ajuda contextual/onboarding, acessibilidade limitada.
9. **Engenharia:** sem Git/CI/lint/type/cobertura; dependências sem lock; sem testes de UI/Windows/executável; sem migrações de banco.
10. **Distribuição:** sem instalador, assinatura, metadados de versão, atualização automática ou diagnóstico de suporte.

---

## 11. Conclusão do discovery

O Finance Toolkit já tem uma **base conceitual e técnica sólida** para evoluir: contrato de módulo claro, UI dirigida por metadados, núcleo testável, operações de arquivo conservadoras e foco local-first. O que falta não é reescrever a arquitetura, e sim:

1. fechar lacunas de **correção e integridade** (comparação, exportação, entradas, encerramento);
2. transformar o histórico em **registro operacional confiável** (detalhes, journal, undo);
3. evoluir a **experiência operacional** (abas, validação, progresso, histórico filtrável, diagnóstico);
4. criar **capacidade de lote e automação**, que é onde o valor para o usuário de alto volume realmente aparece;
5. profissionalizar **testes, build e distribuição**.

A auditoria detalhada, com evidências, impactos e recomendações, está em [`docs/technical-audit.md`](technical-audit.md). O plano de evolução e o backlog executável estão em [`docs/improvement-roadmap.md`](improvement-roadmap.md) e [`docs/TODO.md`](TODO.md).
