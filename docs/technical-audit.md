# Finance Toolkit — Auditoria Técnica e Arquitetural

> **Etapa:** 2 e 3 — auditoria técnica, avaliação funcional e de produto  
> **Base:** código-fonte completo, README, scripts, spec, execução real da suíte e sondas isoladas em `/tmp`  
> **Data:** 19/11/2026  
> **Regra:** nenhuma alteração de código, configuração, dependência, banco de dados do usuário ou interface foi realizada.

---

## 1. Método e legenda

A auditoria combinou:

1. leitura integral de `app/`, `core/`, `modules/`, `tests/`, scripts e `README.md`;
2. rastreamento dos fluxos de inicialização, navegação, validação, execução, cancelamento, histórico e exportação;
3. execução da suíte existente, compilação, importação de todos os módulos e smoke tests de UI/execução com dados temporários;
4. sondas isoladas para confirmar suspeitas (tolerância, comparação numérica, injeção em CSV, cabeçalhos duplicados, codificação CSV, banco corrompido, colisão de abas);
5. confronto entre o que o README promete e o que o código faz.

**Status de evidência**

- **Comprovado:** observado no código e/ou reproduzido em execução.
- **Hipótese:** conclusão plausível que depende de ambiente Windows, volume real de dados ou build ainda não executado.

**Gravidade**

- **Crítica:** risco imediato de perda/corrupção silenciosa de dados ou execução de código não intencional.
- **Alta:** erro funcional relevante, risco operacional sério ou bloqueio de evolução.
- **Média:** impacto real, com contorno ou escopo limitado.
- **Baixa:** atrito, manutenção ou melhoria incremental.

**Resumo:** nenhum cenário de perda silenciosa de dados em operação normal foi comprovado. Foram confirmados, porém, **erros financeiros silenciosos**, **risco de execução de fórmulas em exportação CSV**, **interrupção de operações ao fechar o app**, **perda de rastreabilidade por linha** e **falhas de inicialização sem recuperação**. Esses são os focos P0/P1.

---

## 2. Arquitetura

### AUD-01 — Repositório sem controle de versão (Gravidade: Alta; Status: comprovado)

**Evidência:** o diretório não contém `.git`; não há branches, tags, histórico, revisão de mudanças ou possibilidade de reverter uma alteração. Os scripts e o README pressupõem edição direta.

**Impacto:** qualquer regressão ou alteração acidental é irreversível; não há base para revisão, CI, releases reproduzíveis ou trabalho paralelo. Para um produto que manipula arquivos financeiros, isso é um risco de processo desproporcional ao valor do código.

**Recomendação:** adotar Git imediatamente (repositório local é suficiente no início), com `.gitignore` revisado, branches curtas, tags de versão e checklist de release. Não é necessário alterar arquitetura para isso.

**Tarefas:** FT-015, FT-091.

---

### AUD-02 — Ausência de portões de qualidade automatizados (Gravidade: Alta; Status: comprovado)

**Evidência:** não há CI, lint, formatador, verificação de tipos, cobertura, configuração de testes ou `pyproject.toml`. A suíte tem 18 testes e roda apenas por `unittest discover`. O `build.bat` roda testes, mas o desenvolvedor pode ignorar o script. Não há teste em Windows nem no executável.

**Impacto:** regressões entram sem aviso; padrões divergem; o build pode quebrar sem detecção; a confiança para evoluir rápido fica limitada.

**Recomendação:** criar um comando único de verificação (testes + compilação + lint + cobertura mínima), depois CI em Windows e Linux; adicionar testes de regressão para cada correção. Ferramentas e dependências de desenvolvimento devem ser aprovadas antes da instalação.

**Tarefas:** FT-014, FT-047, FT-085, FT-092.

---

### AUD-03 — Inicialização não resiliente a banco corrompido ou pasta indisponível (Gravidade: Alta; Status: comprovado)

**Evidência:** `app/bootstrap.py:23-31` chama `HistoryService(db_path())` sem tratamento. `HistoryService.__init__` executa `executescript(SCHEMA)` e um `UPDATE`; com um arquivo inválido, a sonda reproduziu `sqlite3.DatabaseError: file is not a database`. No executável, `console=False` (`finance_toolkit.spec:34`) significa que o usuário pode ver o app simplesmente não abrir, sem mensagem. `core/paths.py:10-20` também pode falhar ao criar a pasta de dados antes de qualquer diálogo.

**Impacto:** perda de acesso ao produto; difícil suporte; risco de o usuário “consertar” apagando dados manualmente.

**Recomendação:** envolver a inicialização em tratamento de erro com diálogo nativo, log em local alternativo e política de recuperação: detectar banco inválido, renomear para `.corrupt-<timestamp>`, recriar banco vazio e informar o usuário; nunca apagar silenciosamente. Adicionar teste unitário com banco inválido.

**Tarefas:** FT-003, FT-031.

---

### AUD-04 — Encerramento da janela pode interromper operações destrutivas (Gravidade: Alta; Status: comprovado no código)

**Evidência:** `app/pages.py:169` inicia uma thread `daemon`; `app/main_window.py:19-33` não define `WM_DELETE_WINDOW`. Ao fechar a janela, o processo pode terminar enquanto `move_safe`, criação de pastas ou movimentação de duplicatas está em andamento. O histórico só é finalizado em `_finish` (`app/pages.py:217-232`), que não roda nesse cenário. O banco marca `running` como `interrupted` apenas na próxima inicialização (`core/history_service.py:42-43`).

**Impacto:** operação parcialmente aplicada, sem registro final, sem manifesto (no caso de duplicatas) e sem indicação clara ao usuário. Em lote, o efeito é maior.

**Recomendação:** interceptar o fechamento; se houver execução, pedir confirmação, solicitar cancelamento, aguardar a thread com timeout e registrar resultado como cancelado/interrompido. Para movimentações, gravar journal/manifesto antes de mover. Alternativa: impedir fechamento até concluir/cancelar.

**Tarefas:** FT-004, FT-008, FT-019.

---

### AUD-05 — Falta de coordenação entre operações simultâneas (Gravidade: Média-Alta; Status: comprovado)

**Evidência:** cada `ModulePage` tem seu próprio `_cancel`, `_queue` e thread (`app/pages.py:43-48`). É possível iniciar uma operação, navegar e iniciar outra. Não há lock global, fila de trabalhos ou verificação de sobreposição de pastas/arquivos. `unique_path()` faz verificação seguida de escrita, sem atomicidade (`core/file_service.py:23-33`).

**Impacto:** duas operações podem mover/organizar a mesma pasta, gerar nomes concorrentes ou produzir resultados inconsistentes; o usuário pode não perceber que há trabalho em andamento em outra página.

**Recomendação:** introduzir um coordenador de operações (uma operação mutável por vez, ou fila), indicador global e bloqueio de navegação/ações conflitantes. Leituras/pré-visualizações podem ser permitidas em paralelo se não houver escrita, mas a política precisa ser explícita.

**Tarefas:** FT-012, FT-028, FT-036.

---

### AUD-06 — Preview e execute recalculam o plano, sem vínculo verificável (Gravidade: Média-Alta; Status: comprovado)

**Evidência:** todos os módulos chamam a mesma rotina de análise em `preview()` e `execute()` (por exemplo, `folder_organizer._plan`, `cleaner._run`, `comparator._compare`, `cnpj_validator._analyze`). A interface mostra uma pré-visualização, mas a execução acontece depois e pode encontrar uma pasta/arquivo diferente. A confirmação é genérica (`app/pages.py:146-151`), sem resumo do que será alterado.

**Impacto:** o usuário aprova um cenário e executa outro (arquivos adicionados/removidos, planilha alterada). Em movimentações, isso reduz a eficácia da pré-visualização como mecanismo de segurança.

**Recomendação:** criar um objeto de plano com identificador/ hash das entradas; exibir contagens e amostra na confirmação; revalidar antes de executar e avisar se o plano mudou. Para operações simples, pelo menos confirmar com o resumo da pré-visualização mais recente.

**Tarefas:** FT-020, FT-035.

---

### AUD-07 — Detalhes por linha não são persistidos; histórico não é rastreável (Gravidade: Alta; Status: comprovado)

**Evidência:** `history.finish()` grava status, resumo, contadores, `output_files_json` e eventos (`core/history_service.py:67-78`), mas **não grava `Result.details`**. A tela de histórico mostra parâmetros, log e saída (`app/pages.py:379-409`). Fechado o app, não se sabe quais arquivos foram movidos, quais CNPJs falharam ou quais células mudaram. O README reconhece que o histórico não é trilha inviolável, mas o problema aqui é anterior: não há dados para auditar.

**Impacto:** impossibilidade de conferência posterior, suporte, reprocessamento seletivo ou undo. É uma lacuna central para o propósito “controle e auditoria” do produto.

**Recomendação:** persistir detalhes de forma estruturada e compacta, com limite/tamanho e política de retenção; permitir abrir/exportar detalhes no histórico; ligar cada execução ao `run_id` do log. Para volumes grandes, armazenar arquivo de resultado (Parquet/CSV comprimido) referenciado pela execução, não só JSON no SQLite.

**Tarefas:** FT-016, FT-017, FT-038.

---

### AUD-08 — Sem journal/undo; manifesto de duplicatas é gravado tarde (Gravidade: Alta; Status: comprovado)

**Evidência:** o organizador move arquivos e devolve detalhes, mas não há operação de desfazer. Duplicatas têm manifesto, porém ele é escrito **depois** do loop de movimentação (`modules/files/duplicate_finder.py:134-162`). Uma falha de escrita do manifesto ou encerramento abrupto deixa arquivos na quarentena sem mapa de retorno. O criador de pastas não grava manifesto.

**Impacto:** recuperação manual trabalhosa; risco de perda de referência de onde cada arquivo estava. Para o usuário financeiro, “não excluímos nada” perde valor se não for possível reverter com segurança.

**Recomendação:** journal transacional por operação (origem, destino, timestamp, status), gravado antes de cada movimento e finalizado depois; botão “Desfazer” no histórico para operações reversíveis; manifesto de duplicatas antes das movimentações. Em falha, manter estado “parcial” explícito.

**Tarefas:** FT-008, FT-019, FT-053, FT-054.

---

### AUD-09 — Banco sem migrações, retenção, WAL ou backup (Gravidade: Média; Status: comprovado)

**Evidência:** esquema criado por `CREATE TABLE IF NOT EXISTS` (`core/history_service.py:12-30`), sem `PRAGMA user_version` nem scripts de migração; conexões abrem/fecham por método (`:45-53`), sem WAL; não há rotina de limpeza, índices por `module_id`/`mode`, compactação ou backup. `core/paths.py:33-34` define `backups_dir()` que não é usado.

**Impacto:** evolução do esquema exige intervenção manual; o banco cresce indefinidamente (especialmente com eventos); concorrência de leitura/escrita é pior; recuperação após corrupção não existe. O histórico de anos pode degradar a experiência.

**Recomendação:** versionar o esquema e criar migrações incrementais; ativar WAL e índices; política de retenção configurável por dias/quantidade; backup antes de migrar e opção de restaurar; teste de migração a partir de banco antigo.

**Tarefas:** FT-016, FT-018, FT-027, FT-031, FT-089.

---

### AUD-10 — `run_id` do log não corresponde ao registro do histórico (Gravidade: Média; Status: comprovado)

**Evidência:** `history.start(self.module, mode, values)` é chamado sem `run_id` (`app/pages.py:157`); o `ExecutionContext` cria seu próprio UUID em `core/execution_context.py:21-23`. A coluna `run_id` fica vazia, enquanto as linhas de log usam outro identificador.

**Impacto:** não é possível correlacionar uma linha do log com uma execução do banco; suporte e auditoria ficam mais lentos.

**Recomendação:** criar um `RunContext`/`run_id` antes de iniciar o histórico e passar o mesmo valor para `history.start` e `ExecutionContext`; exibir o ID na tela e no detalhe do histórico.

**Tarefas:** FT-013.

---

### AUD-11 — Múltiplas instâncias do app podem se atropelar (Gravidade: Média; Status: comprovado no código)

**Evidência:** não há lockfile/mutex; cada instância abre o mesmo SQLite e pode operar nas mesmas pastas. Na inicialização, `HistoryService` marca **todas** as execuções `running` como `interrupted` (`core/history_service.py:42-43`), inclusive as de outra instância ainda ativa.

**Impacto:** status incorretos e concorrência de arquivos entre janelas.

**Recomendação:** instância única (mutex/lockfile) ou, se multi-instância for desejada, identificar dono por instância e não marcar execuções de terceiros como interrompidas; coordenar operações por pasta.

**Tarefas:** FT-028.

---

### AUD-12 — Contrato de módulo sem validação estrutural e erros genéricos (Gravidade: Média; Status: comprovado)

**Evidência:** `ParamSpec.kind` é string livre (`core/base_module.py:47-56`); `app/widgets.py:199` levanta `ValueError` para tipo desconhecido somente ao montar a página. `BaseModule.validate()` não verifica existência de coluna/aba nem permissão de escrita; `cnpj_validator` faz `df[column]` (`modules/finance/cnpj_validator.py:33-35`) e, se a coluna não existir, o erro chega como `KeyError` e vira “Erro inesperado” (`app/pages.py:181-183`). O teste de registro valida IDs, chaves e fontes, mas não os `kind` permitidos (`tests/test_modules.py:208-220`).

**Impacto:** ferramenta pode nem abrir por erro de metadado; usuário recebe mensagem técnica; validação falha tarde, depois de ler arquivos grandes.

**Recomendação:** validar módulos no registro (kinds permitidos, choices, sources, unicidade), tipar `ctx` com um Protocol e criar validações compartilhadas de aba/coluna/arquivo de saída, com mensagens acionáveis. Mapear erros conhecidos (`WorksheetNotFound`, `KeyError`, `PermissionError`) para `ToolkitError`.

**Tarefas:** FT-011, FT-021, FT-022, FT-029.

---

## 3. Correção funcional e integridade

### AUD-13 — Tolerância `"0.01"` é interpretada como `1.0` no comparador (Gravidade: Alta; Status: comprovado)

**Evidência:** `SheetComparator._tolerance` (`modules/spreadsheets/comparator.py:71-75`) tenta primeiro `parse_number(text, "br")`. Em `core/normalizers.py:124`, o formato `br` remove todos os pontos, então `"0.01"` vira `"001"` → `1.0`. Sonda: `_tolerance("0.01") == 1.0`; `_tolerance("0,01") == 0.01`.

**Impacto:** diferenças de até R$ 1,00 passam como iguais quando o usuário digita o separador decimal em formato internacional/inglês (muito comum em teclados e exports). O comparador pode declarar planilhas conciliadas quando há divergência. É um erro financeiro silencioso.

**Recomendação:** definir uma regra explícita de parsing (campo dedicado com validação, ou tentar BR e internacional com desambiguação), rejeitar formatos ambíguos e testar `0.01`, `0,01`, `1.000`, `1,000.00`. Nunca aceitar silenciosamente uma interpretação 100× maior.

**Tarefas:** FT-001.

---

### AUD-14 — Inteiros com separador de milhar brasileiro geram falsos diffs (Gravidade: Média-Alta; Status: comprovado)

**Evidência:** `_numeric` em `modules/spreadsheets/comparator.py:18-30` só aplica `parse_number` BR quando o texto casa com `-?\d{1,3}(\.\d{3})*,\d+|-?\d+,\d+` — ou seja, exige parte decimal com vírgula. `"1.234"` tenta `float("1.234")` e vira `1.234`; `"1234"` vira `1234`. Sonda: `same_value("1.234", "1234") == False`.

**Impacto:** valores inteiros exportados em formato brasileiro aparecem como alterados; relatórios de conciliação ficam poluídos e perdem credibilidade.

**Recomendação:** reconhecer milhar BR sem decimais quando o padrão for inequívoco, ou exigir normalização prévia das colunas comparadas; adicionar testes com `1.234`, `12.345`, `1.234.567`, `R$ 1.234` e valores ambíguos. Documentar a regra na UI.

**Tarefas:** FT-002.

---

### AUD-15 — Cabeçalhos duplicados após `strip` quebram o limpador e perdem colunas (Gravidade: Média; Status: comprovado)

**Evidência:** `read_table` faz `df.columns = [str(c).strip() for c in df.columns]` (`core/spreadsheet_service.py:53`). Cabeçalhos `"X"` e `" X "` passam a ser ambos `"X"`. `clean_table` monta `data = {str(c): df[c].tolist() for c in df.columns}` (`modules/spreadsheets/cleaner.py:36`); com rótulo duplicado, `df[c]` devolve `DataFrame`, que não tem `.tolist()`, gerando `AttributeError`. Sonda reproduzida. No comparador, `to_dict("records")` mantém só uma das colunas e emite warning do pandas.

**Impacto:** ferramenta falha com “Erro inesperado” ou, pior, análise silenciosamente incompleta.

**Recomendação:** deduplicar nomes de colunas de forma determinística na leitura (ex.: `X`, `X_2`, preservando a ordem) e registrar aviso; usar estruturas posicionais quando necessário; testar planilhas com cabeçalhos repetidos e vazios.

**Tarefas:** FT-006.

---

### AUD-16 — Detecção de codificação CSV falha tardiamente e pode gerar mojibake (Gravidade: Média; Status: comprovado)

**Evidência:** `_csv_params` lê apenas 64 KB e valida com decoder incremental (`core/spreadsheet_service.py:15-30`). Um arquivo válido nos primeiros 64 KB e com byte `0xE3` depois foi classificado como UTF-8 e falhou no `read_csv` com `UnicodeDecodeError` (sonda). Se o byte for válido em cp1252, o arquivo pode ser lido com caracteres errados sem erro.

**Impacto:** falha genérica em arquivos reais grandes ou dados corrompidos; conversão silenciosa de acentos, afetando CNPJ/razão social e relatórios.

**Recomendação:** validar a codificação no arquivo inteiro ou em amostras distribuídas; oferecer seleção explícita de codificação/separador na UI para arquivos problemáticos; registrar a codificação detectada; testar UTF-8, UTF-8 BOM, cp1252, latin-1 e arquivos mistos.

**Tarefas:** FT-007, FT-033.

---

### AUD-17 — Seleção de abas não existe na UI, apesar de API pronta (Gravidade: Média; Status: comprovado)

**Evidência:** `list_sheets()` existe em `core/spreadsheet_service.py:61-66` e **não é chamado em nenhum lugar** (grep). Os módulos expõem “Aba (vazio = primeira)” como `text`; o comparador não expõe nem isso e sempre lê a primeira aba (`modules/spreadsheets/comparator.py:79`). Digitar uma aba inexistente gera erro tardio.

**Impacto:** usuários com planilhas multiaba não conseguem escolher a aba correta em várias ferramentas; erros de digitação são comuns; o comparador é inutilizável para arquivos cuja aba relevante não é a primeira.

**Recomendação:** criar um `ParamSpec` do tipo `sheet`, populado por `list_sheets(path)`, com atualização em cascata para colunas; validar a aba antes de executar; adicionar suporte no comparador (duas abas independentes).

**Tarefas:** FT-024, FT-032, FT-051.

---

### AUD-18 — Chaves duplicadas no comparador são resolvidas silenciosamente pela primeira (Gravidade: Média; Status: comprovado)

**Evidência:** `_compare` indexa por chave e, ao encontrar duplicata, incrementa `dup` e ignora a linha seguinte (`modules/spreadsheets/comparator.py:100-119`). O fato vira um “aviso” no relatório, mas a comparação prossegue e o resumo pode parecer conclusivo. Não há opção de abortar, agregar ou comparar todas as ocorrências.

**Impacto:** em bases financeiras, uma chave repetida (mesmo CNPJ/documento em linhas diferentes) pode esconder divergências; o usuário pode confiar em um resultado incompleto.

**Recomendação:** política explícita: abortar por padrão em chaves duplicadas, com opção “usar primeira”, “agregar” ou “comparar por ocorrência”; destacar no topo do relatório e no resumo.

**Tarefas:** FT-050.

---

### AUD-19 — Exportação CSV permite injeção de fórmulas (Gravidade: Alta; Status: comprovado)

**Evidência:** `export_sheets` neutraliza apenas strings que começam com `"="` (`core/export_service.py:14-27`). `export_rows` grava CSV diretamente com `to_csv`, sem `_guard` (`:65-72`). Sonda: um valor `=HYPERLINK("http://evil","click")` saiu intacto no CSV. Também não há tratamento para `+`, `-`, `@`, tab, CR e variações com espaços à esquerda.

**Impacto:** se o CSV for aberto no Excel/LibreOffice, fórmulas podem executar comandos, exfiltrar dados ou alterar o arquivo. O conteúdo pode vir de planilhas de terceiros (comparador exporta “Valor anterior/novo”), o que torna o vetor realista.

**Recomendação:** sanitizar toda exportação tabular (CSV e XLSX) com regra única: prefixar apóstrofo ou tabulação em valores que comecem com `= + - @` após espaços, e neutralizar CR/LF em contextos apropriados; testar com payloads conhecidos e documentar a política.

**Tarefas:** FT-005.

---

### AUD-20 — Exportação XLSX é O(linhas × colunas) em Python e pode travar em planilhas grandes (Gravidade: Média; Status: comprovado no código; impacto depende do volume)

**Evidência:** `export_sheets` percorre todas as células para aplicar formato de data (`core/export_service.py:52-56`) e todas as linhas de cada coluna numérica (`:57-61`), depois de `df.to_excel`. Também calcula largura com `head(200)`, mas o loop de datas não é limitado. Cada acesso `ws.cell()` é custoso. A leitura e a transformação mantêm o DataFrame inteiro em memória; o limpador cria listas por coluna (`modules/spreadsheets/cleaner.py:36`).

**Impacto:** planilhas de dezenas/centenas de milhares de linhas podem levar minutos, consumir memória excessiva e parecer travadas (a barra não reflete a escrita). O app é voltado a “grandes volumes”, então isso é um risco de produto.

**Recomendação:** medir com benchmarks; usar `write_only`/streaming ou aplicar formatos por coluna via `openpyxl` de forma vetorizada; limitar loops; processar em chunks; exibir progresso real na escrita; definir limite de tamanho com mensagem clara.

**Tarefas:** FT-023, FT-037, FT-092.

---

### AUD-21 — Colisão de nomes de abas na exportação sobrescreve dados silenciosamente (Gravidade: Média; Status: comprovado)

**Evidência:** `export_sheets` sanitiza e trunca nomes em 31 caracteres (`core/export_service.py:43`), mas não deduplica. Sonda com duas chaves longas terminando em caracteres diferentes produziu **uma única aba**, contendo apenas o segundo DataFrame. Os módulos atuais usam nomes fixos curtos, então o defeito é latente; qualquer módulo futuro com nomes dinâmicos pode perdê-lo.

**Impacto:** perda silenciosa de seções do relatório.

**Recomendação:** deduplicar nomes de aba de forma determinística (`nome`, `nome_2`, …), testar colisões e validar o conjunto antes de escrever.

**Tarefas:** FT-010.

---

### AUD-22 — Resultados e detalhes crescem em memória sem limite (Gravidade: Média; Status: comprovado)

**Evidência:** o validador de CNPJ cria um dicionário por linha (`modules/finance/cnpj_validator.py:47-65`); o comparador mantém dois DataFrames, dois índices de registros e todas as alterações (`modules/spreadsheets/comparator.py:141-146`); o limpador materializa listas por coluna. A UI guarda `_last_result` e a tabela mostra no máximo 1.000 linhas, mas o restante permanece em memória para exportação.

**Impacto:** consumo alto em arquivos grandes; risco de `MemoryError` sem mensagem amigável; tempo de resposta.

**Recomendação:** medir; limitar detalhes em preview; para execução, gravar detalhes em arquivo incremental e manter amostra na memória; definir limites explícitos e mensagem. Considerar processamento por chunks.

**Tarefas:** FT-017, FT-023, FT-037, FT-092.

---

## 4. Segurança e integridade operacional

### AUD-23 — Quarentena pode apontar para fora da pasta analisada sem aviso (Gravidade: Média-Baixa; Status: comprovado)

**Evidência:** `_quarantine_dir` aceita caminho relativo com `..` ou absoluto (`modules/files/duplicate_finder.py:59-61`). Não há confirmação específica nem aviso de que arquivos sairão da árvore analisada. `is_inside()` existe em `core/file_service.py:53-58`, mas não é usado.

**Impacto:** movimentação inesperada para outra unidade/pasta; dificulta conferência e aumenta risco de “perder” arquivos.

**Recomendação:** avisar e confirmar quando a quarentena estiver fora da pasta analisada; validar caminho; usar `is_inside()` para decisões explícitas; impedir quarentena igual à raiz.

**Tarefas:** FT-056.

---

### AUD-24 — Dados sensíveis e histórico sem controles de privacidade/retenção (Gravidade: Média; Status: comprovado)

**Evidência:** `executions.params_json` guarda caminhos completos de arquivos, nomes de colunas e configurações; `execution_events` guarda mensagens com nomes de arquivos; tudo em SQLite sem criptografia. Não há tela para limpar histórico, definir retenção ou exportar/eliminar dados. Logs ficam em texto claro. O README alerta que o histórico não é inviolável, mas não oferece controles.

**Impacto:** em contextos com LGPD/auditoria, dados de clientes podem permanecer indefinidamente; suporte e descarte ficam manuais. O risco é de governança, não de exploit remoto.

**Recomendação:** definir política de retenção e oferecer “limpar histórico”, “exportar dados”, “apagar por período” e localização visível da pasta de dados; avaliar criptografia/OS keychain se segredos forem adicionados no futuro; documentar claramente o modelo de ameaça local.

**Tarefas:** FT-027, FT-040, FT-089.

---

### AUD-25 — Proteção de nomes/paths do Windows é parcial (Gravidade: Baixa-Média; Status: comprovado no código; hipótese para casos de borda)

**Evidência:** `sanitize_folder_name` remove caracteres proibidos e trata nomes reservados exatos (`core/file_service.py:14-20`), mas não cobre `CON.txt`, nomes com mais de 255 caracteres, caminhos > 260 caracteres (`MAX_PATH`) ou espaços/pontos internos. `unique_path` não é atômico. Erros de `mkdir`/`move` são capturados por arquivo em alguns módulos, mas não em todos.

**Impacto:** falhas em nomes vindos de razões sociais longas ou planilhas reais; erros por arquivo em vez de bloqueio prévio.

**Recomendação:** validar/limitar nomes antes de executar, reportar pré-condições, testar no Windows e considerar prefixo `\\?\` apenas se necessário; documentar limites.

**Tarefas:** FT-030.

---

## 5. Desempenho e escalabilidade

### AUD-26 — Detecção de duplicatas é sequencial e sem cache (Gravidade: Média; Status: comprovado)

**Evidência:** `_scan` percorre todos os arquivos, agrupa por tamanho e calcula SHA-256 sequencialmente (`modules/files/duplicate_finder.py:63-95`). Não há cache por caminho/tamanho/mtime, hash parcial ou paralelismo. O progresso só aparece na fase de hash.

**Impacto:** pastas grandes/rede ficam lentas; reexecuções recalculam tudo.

**Recomendação:** cache de hash (tamanho + mtime), pré-filtro por hash parcial, pool de threads/processos limitado, progresso na enumeração e opção de excluir padrões.

**Tarefas:** FT-055.

### AUD-27 — Cancelamento e progresso são grossos (Gravidade: Média; Status: comprovado)

**Evidência:** `clean_table` só verifica cancelamento antes/depois (`modules/spreadsheets/cleaner.py:169-186`); a leitura de planilhas não é cancelável; o progresso é emitido em poucos passos (`0/3`, `1/3`). `ExecutionContext.progress` limita a 50 ms (`core/execution_context.py:33-37`), mas os módulos não chamam em loops de limpeza/leitura. A barra fica em 0 durante operações longas.

**Impacto:** sensação de travamento; usuário fecha o app (ver AUD-04) ou repete a operação.

**Recomendação:** checkpoints em loops longos, progresso indeterminado explícito por fase, ETA e mensagem; cancelamento seguro em pontos definidos; testes de cancelamento.

**Tarefas:** FT-037.

---

## 6. Testabilidade e confiabilidade

### AUD-28 — Cobertura limitada e concentrada em caminhos felizes (Gravidade: Alta; Status: comprovado)

**Evidência:** 18 testes, todos aprovados. Não há testes para:
- interface (`MainWindow`, `ParamForm`, `ResultTable`, páginas);
- cancelamento e encerramento;
- falhas de leitura (arquivo bloqueado, aba inexistente, coluna ausente, permissão);
- CSV com codificação problemática, separadores e BOM;
- injeção de fórmulas;
- cabeçalhos duplicados;
- banco corrompido, migração, retenção, multi-instância;
- `.xls`, Windows, paths longos;
- desempenho e limites;
- build/executável.

`TempDirCase` define `FINANCE_TOOLKIT_HOME` e não restaura o valor anterior (`tests/helpers.py:9-17`), o que pode contaminar testes seguintes no mesmo processo.

**Impacto:** os defeitos confirmados nesta auditoria passaram pela suíte; a confiança para refatorar é baixa.

**Recomendação:** criar testes de regressão para cada correção; adicionar testes de UI headless (com Tk em CI Windows), testes de contrato dos módulos, fixtures de arquivos corrompidos e testes de integração de histórico; medir cobertura, sem transformar a métrica em meta cega.

**Tarefas:** FT-014, FT-047, FT-085, FT-092.

---

## 7. Dependências, build e distribuição

### AUD-29 — Dependências não reproduzíveis e alvo de Python inconsistente (Gravidade: Média; Status: comprovado)

**Evidência:** `requirements.txt` tem apenas mínimos; não há lock/constraints; o README declara 3.10–3.12; a análise rodou em 3.13; `xlrd` não estava instalado; PyInstaller não estava instalado. `build.bat` faz `pip install --upgrade pip` e instala sem pins, dependendo de rede.

**Impacto:** builds diferentes, falhas futuras por atualização de pandas, dificuldade de reproduzir bug do usuário.

**Recomendação:** fixar versões (ou lock), matriz de Python suportada, requirements de desenvolvimento separados, build reproduzível e documentação de ambiente. Atualizações somente com autorização e testes.

**Tarefas:** FT-083, FT-095.

---

### AUD-30 — Build e distribuição não verificados de ponta a ponta (Gravidade: Alta para lançamento; Status: comprovado + hipótese)

**Evidência:** há spec e script, mas não foi possível executar PyInstaller nesta máquina. Não há ícone, versão de arquivo, assinatura, instalador, atualização, teste de inicialização do `.exe` ou smoke test em Windows limpo. `console=False` + exceção de inicialização = falha silenciosa (ver AUD-03). O spec exclui `PIL`; a leitura de imagens em xlsx é descartada graciosamente pelo openpyxl, então isso não é um defeito por si, mas precisa ser validado.

**Impacto:** o artefato pode falhar em campo sem diagnóstico; SmartScreen/antivírus podem bloquear; usuários não têm caminho de atualização.

**Recomendação:** pipeline de build em Windows, smoke test automatizado do executável, metadados/ícone, instalador, assinatura e estratégia de atualização; testar em máquina sem Python.

**Tarefas:** FT-084, FT-085, FT-086, FT-087, FT-095.

---

### AUD-31 — Logs existem, mas não há diagnóstico acessível ao usuário (Gravidade: Média; Status: comprovado)

**Evidência:** o diálogo global diz “O detalhe foi gravado no arquivo de log” (`app/main_window.py:37-39`), mas não há botão para abrir a pasta de logs, copiar o erro ou gerar um pacote de suporte. O caminho não aparece na UI. `app/utils.open_path` existe, mas não é usado para logs.

**Impacto:** suporte de primeira linha ineficiente; usuário não encontra evidência; aumento de idas e vindas.

**Recomendação:** ação “Abrir logs”, “Copiar detalhes”, “Gerar pacote de diagnóstico” (versão, SO, log recente, schema do banco, sem conteúdo de planilhas), além de localização dos dados em “Sobre”.

**Tarefas:** FT-026, FT-039, FT-088.

---

## 8. Outros achados e dívidas menores

### AUD-32 — Código morto e funcionalidades “quase prontas” (Gravidade: Baixa; Status: comprovado)

- `core/file_service.is_inside()` — definido, sem uso.
- `core/paths.backups_dir()` — definido, sem uso.
- `core/spreadsheet_service.list_sheets()` — definido, sem uso (indicador da lacuna de seleção de abas).
- `HistoryService.recent(mode=...)` — suporta filtro, mas a UI não oferece.
- `ConfigService.app_setting()` — sem uso atual.
- `app/widgets.ScrollFrame` registra `bind_all("<MouseWheel>")` a cada instância, sem desregistrar (`app/widgets.py:47`); no Linux/X11 o evento esperado é `Button-4/5`, então a roda pode não funcionar no ambiente de desenvolvimento (o alvo é Windows).
- `sanitize_folder_name("..")` devolve `""`; os fluxos tratam, mas a validação é indireta.

**Impacto:** sinaliza intenções não concluídas e aumenta custo cognitivo; baixo risco imediato.

**Recomendação:** usar ou remover (com decisão registrada); completar a seleção de abas; expor filtros já suportados; revisar bindings de scroll.

**Tarefas:** FT-024, FT-029, FT-038, FT-046.

### AUD-33 — Semântica de status/cancelamento espalhada (Gravidade: Baixa; Status: comprovado)

**Evidência:** módulos atribuem `result.status = "cancelled"` como string literal (`modules/files/folder_organizer.py:163-164`, `modules/files/duplicate_finder.py:168-169`, `modules/files/company_folders.py:159-160`), enquanto `CANCELLED` existe em `core/base_module.py:17`. `PARTIAL`/`SUCCESS` também são strings. `build_result` não modela cancelamento.

**Impacto:** risco de divergência futura; status inválido não é detectado; relatórios podem tratar cancelamento como sucesso/falha.

**Recomendação:** constantes e helper de resultado (ou enum), validação no `Result`/histórico, testes de cada status.

**Tarefas:** FT-009.

### AUD-34 — Documentação e roadmap divergem da implementação (Gravidade: Baixa; Status: comprovado)

- README não lista `app/utils.py` nem `docs/` (que não existia).
- Fases do README e `PlannedModule.phase` não coincidem; “fechamento mensal” aparece como fase 6, enquanto a fase 6 do README é distribuição.
- `activity_log` duplica o conceito de histórico já existente.
- O README diz “Tudo roda localmente”, o que é verdade, mas não detalha que a saída de planilhas lê só uma aba e perde fórmulas/estilos.
- Não há changelog, licença, manual do usuário ou política de suporte.

**Impacto:** expectativas erradas, dificuldade de onboarding, decisões de roadmap inconsistentes.

**Recomendação:** uma fonte de verdade para roadmap e catálogo; documentar limitações de fidelidade de planilhas; changelog e manual; decidir o papel de `activity_log`.

**Tarefas:** FT-090, FT-091.

### AUD-35 — UI: erros técnicos, sem ajuda contextual e com acessibilidade limitada (Gravidade: Média; Status: comprovado)

**Evidência:** erros inesperados mostram `str(exc)` e “veja o log”; não há detalhe expansível/copiar. O formulário não valida campo a campo; o usuário descobre problemas ao executar. A tabela limita a 1.000 linhas sem paginação/filtro. Não há atalhos de teclado, tema claro, escala de fonte ou suporte a leitor de tela. Emojis são usados como ícones. A busca não mostra “nenhum resultado”. Não há onboarding/ajuda por ferramenta.

**Impacto:** curva de aprendizado, suporte e acessibilidade; usuários de alto volume perdem tempo conferindo tabelas truncadas.

**Recomendação:** mensagens acionáveis com “copiar detalhes”, ajuda contextual, atalhos, tabela com filtro/ordenação/cópia, estados vazios e revisão de contraste/escala. Não é necessário trocar Tkinter para obter ganhos relevantes.

**Tarefas:** FT-034, FT-039, FT-042, FT-043, FT-044, FT-045.

---

## 9. Avaliação funcional e de produto

### 9.1 Proposta de valor e personas

**Proposta:** reduzir trabalho manual repetitivo com arquivos e planilhas, sem enviar dados para a nuvem, com pré-visualização e sem exclusões.

**Personas prováveis:**

1. **Analista financeiro/contábil:** concilia planilhas, confere pagamentos, valida CNPJs, organiza comprovantes.
2. **Assistente administrativo/financeiro:** organiza pastas, renomeia documentos, cria estruturas por empresa, limpa bases recebidas.
3. **Coordenador/gestor:** precisa de conferência, evidências, relatórios e rastreabilidade, sem operar cada arquivo manualmente.

**Jobs to be done:** “recebo uma base bagunçada e preciso devolvê-la confiável”, “preciso provar o que mudou entre versões”, “preciso organizar milhares de documentos por empresa/competência”, “preciso conferir se pagamentos batem”, “preciso repetir isso todo mês”.

### 9.2 Jornada atual e atritos

```text
Abrir app → buscar ferramenta → escolher arquivo/pasta → preencher parâmetros
   → (colunas carregam) → Pré-visualizar → conferir tabela/log → Executar
   → confirmar → aguardar → exportar → consultar histórico
```

Atritos observados:

| Etapa | Atrito | Consequência |
|---|---|---|
| Buscar | Busca só por nome/descrição, sem tags; sem “nenhum resultado” | ferramenta difícil de achar |
| Configurar | Aba é texto livre; erros de coluna/aba só no fim | tentativa e erro |
| Pré-visualizar | Tabela limitada a 1.000 linhas; sem filtro; detalhes densos | conferência difícil em volume |
| Confirmar | Diálogo genérico, sem resumo do plano | decisão pouco informada |
| Executar | Progresso grosseiro; sem ETA; cancelamento limitado | sensação de travamento |
| Erro | Mensagem técnica; log inacessível | suporte difícil |
| Exportar | CSV sem proteção; sem opções de codificação/separador | risco e retrabalho |
| Histórico | Sem filtros/exportação/reexecução; sem detalhes | pouca rastreabilidade |
| Repetir | Sem presets, lote ou agendamento | trabalho manual recorrente |

### 9.3 Avaliação por ferramenta

| Ferramenta | Valor entregue | Usabilidade | Segurança | Principal lacuna de produto |
|---|---|---|---|---|
| Organizador de pastas | Alto para volume | Média (regras em texto) | Boa (preview, sem sobrescrever) | Sem undo, sem recursão, sem presets |
| Duplicatas | Alto (economia de espaço) | Média | Boa (quarentena) | Hash lento; manifesto tardio; sem agendamento |
| Pastas por empresa | Alto e específico | Média | Boa (não altera existentes) | Sem CNPJ, manifesto ou undo |
| Limpador | Muito alto | Média | Boa (original intacto) | Só uma aba; perde fórmulas/estilos; sem preview por célula |
| Comparador | Muito alto para conferência | Média | Boa (só lê) | Tolerância bug; chaves duplicadas; sem diff visual |
| Validador CNPJ | Alto e rápido | Média | Boa | Sem seleção de aba; erros genéricos; sem relatório de exceções |

### 9.4 Oportunidades de evolução (avaliação, não implementação)

**Alto valor e viabilidade agora**

1. **Seleção de abas e colunas com validação em tempo real** — reaproveita `list_sheets`; reduz a maior fonte de erro operacional.
2. **Histórico com detalhes, filtros, exportação e reexecução** — transforma registro em ferramenta de conferência.
3. **Confirmação com resumo do plano + journal/undo** — aumenta confiança nas operações que movem arquivos.
4. **Correções de comparação/exportação** — eliminam resultados errados e risco de fórmula.
5. **Lote de arquivos/abas** — o usuário de alto volume hoje repete a mesma operação N vezes; é a alavanca de produtividade mais direta.
6. **Renomeador e conversor** — alto valor, baixo custo arquitetural, reutilizam normalizadores e serviços.
7. **Validador de planilhas** — complementa limpador/comparador e endereça conferência recorrente.
8. **Diagnóstico e configurações** — logs acessíveis, pasta de dados, retenção, presets.

**Valor alto, porém com mais domínio/risco**

9. **Conferência de pagamentos, duplicidade de pagamentos, boletos e saldos** — exigem regras de negócio, layouts e validação com usuários; alto valor financeiro.
10. **Relatórios gerenciais e comparador de períodos** — dependem de histórico confiável e definições de indicadores.
11. **Fluxos encadeados e agendamento** — multiplicam valor, mas exigem plano/journal, idempotência, logs e tratamento de falhas.
12. **Monitor de pastas e OCR** — alto custo, dependências externas, privacidade e falso positivo; deixar para depois de a base estar estável.

**Baixo valor imediato / alto custo**

13. Trocar Tkinter por outro toolkit agora: não resolve os problemas principais e consome meses.
14. OCR/anomalias com IA sem dados rotulados: risco de expectativa e precisão.
15. Clipboard manager: útil, mas fora do núcleo financeiro; pode esperar.
16. Fechamento mensal/evidências: alto valor, mas é um produto de processo, não um utilitário isolado; requer modelo de dados e colaboração.

### 9.5 Priorização de produto (valor × esforço)

```text
Alto valor / baixo esforço      → correções P0, abas, histórico filtrável, confirmação/undo, lote simples
Alto valor / médio esforço      → renomeador, conversor, validador de planilhas, journal, presets
Alto valor / alto esforço       → conferência de pagamentos, fluxos, agendador, relatórios
Médio valor / baixo esforço     → clipboard, notificações, atalhos, temas
Baixo valor agora / alto esforço→ OCR, anomalias, troca de UI, app colaborativo
```

### 9.6 Critérios de sucesso sugeridos

- **Correção:** zero divergências financeiras conhecidas causadas por parsing; 100% dos bugs P0 com teste de regressão.
- **Confiabilidade:** nenhuma operação destrutiva sem journal; nenhum fechamento abrupto sem registro; taxa de falhas de execução monitorada localmente.
- **Produtividade:** tempo para processar 100 arquivos/abas reduzido de “N execuções manuais” para “1 lote”; presets reutilizáveis.
- **Rastreabilidade:** toda execução com detalhes consultáveis, `run_id` correlacionado e exportação.
- **Qualidade:** cobertura dos fluxos críticos e testes em Windows/executável antes de release.
- **Suporte:** pacote de diagnóstico em um clique; tempo de primeira resposta reduzido.

---

## 10. Matriz resumida de riscos

| ID | Risco | Gravidade | Probabilidade | Prioridade de tratamento |
|---|---|---|---|---|
| AUD-13 | Tolerância financeira incorreta | Alta | Alta (digitação comum) | P0 |
| AUD-19 | Injeção de fórmula em CSV | Alta | Média | P0 |
| AUD-04 | Encerramento no meio de movimentação | Alta | Média | P0 |
| AUD-03 | App não abre com banco inválido | Alta | Baixa-Média | P0 |
| AUD-07 | Perda de rastreabilidade por linha | Alta | Certa ao fechar | P1 |
| AUD-15 | Cabeçalho duplicado quebra/perde dados | Média | Média | P0 |
| AUD-16 | Codificação CSV falha/mojibake | Média | Média | P0 |
| AUD-01/02 | Sem Git/CI, regressões | Alta (processo) | Alta | P0/P1 |
| AUD-08 | Sem undo/manifesto tardio | Alta | Média | P1 |
| AUD-05 | Operações concorrentes | Média-Alta | Baixa-Média | P1 |
| AUD-30 | Build/distribuição não verificados | Alta (lançamento) | Alta | P1/P2 |
| AUD-20/22 | Desempenho/memória em volume | Média | Média-Alta | P1/P2 |
| AUD-17/18 | Abas/chaves duplicadas | Média | Alta | P1 |
| AUD-09/24 | Banco sem migração/retenção | Média | Certa no tempo | P1/P2 |
| AUD-35 | UX/erros/acessibilidade | Média | Alta | P2 |

---

## 11. Conclusão da auditoria

**Pontos fortes a preservar**

- Separação `core/` ↔ `app/` e contrato `BaseModule` simples.
- UI genérica dirigida por `ParamSpec`, que reduz muito o custo de novas ferramentas.
- Operações de arquivo conservadoras (sem sobrescrever, quarentena, pré-visualização).
- Execução em thread com fila, sem tocar em Tk fora da thread principal.
- Local-first, sem rede; bom para privacidade.
- Normalizadores e serviços com funções puras e testes.

**Dívidas que bloqueiam a próxima fase**

1. Correção financeira e segurança de exportação.
2. Rastreabilidade e recuperação (detalhes, `run_id`, journal/undo, encerramento).
3. Entrada de planilhas confiável (abas, colunas, codificação, cabeçalhos).
4. Portões de qualidade (Git, testes de regressão, CI, Windows, build).
5. Experiência para volume (lote, presets, histórico filtrável, progresso).

**Recomendação geral:** não reescrever a arquitetura nem trocar Tkinter. Estabilizar o núcleo, transformar o histórico em registro operacional, corrigir a entrada/saída de dados e só então expandir o catálogo. A ordem detalhada está em `docs/improvement-roadmap.md`; o backlog executável, em `docs/TODO.md`.
