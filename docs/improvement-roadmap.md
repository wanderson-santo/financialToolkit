# Finance Toolkit — Roadmap de Melhorias

> **Etapa:** 4 e 5 — proposição de melhorias e planejamento estratégico  
> **Base:** achados de `docs/project-discovery.md` e `docs/technical-audit.md`  
> **Regra:** este documento propõe; não implementa. Nenhuma dependência foi instalada ou atualizada.

---

## 1. Princípios de priorização

1. **Correção antes de expansão.** Um resultado financeiro errado destrói a confiança mais rápido do que uma funcionalidade ausente.
2. **Integridade antes de conveniência.** Nenhuma operação que move arquivos deve ficar sem registro e possibilidade de reversão.
3. **Reuso antes de reescrita.** A arquitetura atual suporta a evolução; não há justificativa para trocar Tkinter, SQLite ou o contrato de módulo nesta fase.
4. **Volume é o caso de uso.** O diferencial do produto é lidar com muitos arquivos/planilhas; lote e automação valem mais que novos utilitários isolados.
5. **Rastreabilidade é funcionalidade.** Histórico não é “extra”: é o que permite conferir, provar e corrigir.
6. **Toda entrega tem teste e critério de aceite.** Correções P0 exigem teste de regressão.
7. **Dependências novas são decisões explícitas.** PDF/OCR/criptografia só entram com avaliação de licença, tamanho e impacto no executável.

### Critérios usados

| Critério | Pergunta |
|---|---|
| Valor | Reduz erro, tempo ou risco real do usuário? |
| Risco | O que acontece se falhar? Há perda de dados? |
| Esforço | Pequeno, médio ou grande, considerando código + testes + documentação? |
| Dependências | Precisa de outra entrega antes? |
| Reversibilidade | É fácil desfazer? |
| Aprendizado | Ajuda a validar uma hipótese de produto? |

---

## 2. Melhorias propostas por categoria

### Categoria 1 — Correções e estabilização

#### IMP-01 — Comparação numérica confiável

- **Descrição:** corrigir a interpretação de tolerância e reconhecer inteiros com separador de milhar brasileiro no comparador.
- **Problema que resolve:** AUD-13 e AUD-14; risco de conciliação declarar igual o que é diferente.
- **Benefício:** confiança no relatório de comparação; menos falso positivo/negativo.
- **Complexidade:** pequena. **Prioridade:** P0.
- **Dependências:** nenhuma.
- **Riscos:** ambiguidade inerente de `1.234`; mitigar com regra explícita e mensagem na UI.
- **Aceite:** `0.01` e `0,01` resultam em `0.01`; `1.234` vs `1234` iguais; casos ambíguos rejeitados ou explicados; testes de regressão.
- **Tarefas:** FT-001, FT-002.

#### IMP-02 — Inicialização e encerramento resilientes

- **Descrição:** recuperar banco inválido/pasta indisponível e impedir fechamento silencioso durante operações.
- **Problema que resolve:** AUD-03 e AUD-04; app pode não abrir ou interromper movimentações.
- **Benefício:** produto previsível; suporte viável; menos estado parcial.
- **Complexidade:** média. **Prioridade:** P0.
- **Dependências:** nenhuma para inicialização; encerramento se beneficia de journal (IMP-12).
- **Riscos:** diálogo de recuperação mal redigido pode assustar; testar cenários e manter backup do banco corrompido.
- **Aceite:** banco inválido não impede a abertura; usuário é informado e o arquivo original é preservado; fechar com operação em curso pede confirmação e registra cancelamento/interrupção.
- **Tarefas:** FT-003, FT-004.

#### IMP-03 — Entrada de planilhas robusta

- **Descrição:** deduplicar cabeçalhos e detectar codificação/separador de CSV com segurança.
- **Problema que resolve:** AUD-15 e AUD-16; falhas e perda silenciosa de colunas.
- **Benefício:** menos “Erro inesperado”; dados lidos corretamente.
- **Complexidade:** média. **Prioridade:** P0.
- **Dependências:** nenhuma.
- **Riscos:** mudança de nomes de colunas pode afetar configurações salvas; versionar/avisar.
- **Aceite:** cabeçalhos repetidos viram nomes únicos e previsíveis; CSV com byte não-UTF-8 após 64 KB é lido ou rejeitado com mensagem clara; testes com fixtures.
- **Tarefas:** FT-006, FT-007.

#### IMP-04 — Exportação segura e íntegra

- **Descrição:** neutralizar fórmulas em CSV/XLSX e impedir colisão de abas.
- **Problema que resolve:** AUD-19 e AUD-21.
- **Benefício:** segurança ao abrir relatórios; nenhuma seção perdida.
- **Complexidade:** pequena. **Prioridade:** P0.
- **Dependências:** nenhuma.
- **Riscos:** sanitização agressiva pode alterar textos legítimos que começam com `-`; documentar e testar.
- **Aceite:** payloads de fórmula não executam; nomes de aba colididos são únicos; testes de exportação.
- **Tarefas:** FT-005, FT-010.

#### IMP-05 — Rastreabilidade básica de execução

- **Descrição:** unificar `run_id` entre log e histórico e eliminar strings soltas de status.
- **Problema que resolve:** AUD-10 e AUD-33.
- **Benefício:** suporte e auditoria correlacionáveis; menos bugs de status.
- **Complexidade:** pequena. **Prioridade:** P1.
- **Dependências:** nenhuma.
- **Riscos:** migração de registros antigos (run_id vazio) precisa ser tolerada.
- **Aceite:** toda execução nova tem o mesmo `run_id` no banco e no log; status de cancelamento usa constante; testes.
- **Tarefas:** FT-009, FT-013.

---

### Categoria 2 — Refatoração e qualidade interna

#### IMP-06 — Contrato de módulo validado

- **Descrição:** validar `ParamSpec` no registro e tipar o contexto/resultado.
- **Problema que resolve:** AUD-12 e AUD-32; erro de metadado só aparece ao abrir a página.
- **Benefício:** falha cedo, no build/teste, e não no usuário; novos módulos mais seguros.
- **Complexidade:** pequena-média. **Prioridade:** P1.
- **Dependências:** nenhuma.
- **Riscos:** validação excessiva pode bloquear módulos legados; aplicar com mensagens claras.
- **Aceite:** registro rejeita `kind` inválido, choice sem opções, source inexistente e chave duplicada; teste com módulo inválido.
- **Tarefas:** FT-011, FT-029.

#### IMP-07 — Erros acionáveis

- **Descrição:** taxonomia de erros e mapeamento de falhas conhecidas para mensagens de usuário.
- **Problema que resolve:** AUD-12 e AUD-35; hoje erros viram “Erro inesperado: …”.
- **Benefício:** menos suporte, mais autonomia.
- **Complexidade:** média. **Prioridade:** P1.
- **Dependências:** IMP-06 (validação) e IMP-09 (preflight).
- **Riscos:** esconder detalhe técnico demais; manter “copiar detalhes”.
- **Aceite:** aba/coluna ausente, permissão negada, arquivo bloqueado e formato inválido têm mensagem orientativa; log preserva detalhe técnico.
- **Tarefas:** FT-022.

#### IMP-08 — Pipeline plano → execução

- **Descrição:** separar a construção de plano da execução e vincular preview/execute.
- **Problema que resolve:** AUD-06; preview aprovado pode não corresponder ao que executa.
- **Benefício:** segurança operacional e confirmação informada.
- **Complexidade:** média. **Prioridade:** P1.
- **Dependências:** IMP-11/IMP-12 para persistir estado.
- **Riscos:** refatoração transversal nos 6 módulos; fazer incrementalmente.
- **Aceite:** operações mutáveis usam plano com hash/validação; mudança de entrada invalida confirmação; testes por módulo.
- **Tarefas:** FT-020, FT-035.

#### IMP-09 — Validação compartilhada e preflight

- **Descrição:** helpers para validar aba, coluna, arquivo de saída, permissões e limites antes de ler tudo.
- **Problema que resolve:** AUD-12, AUD-17; validação tardia e genérica.
- **Benefício:** feedback rápido; menos leitura desperdiçada.
- **Complexidade:** média. **Prioridade:** P1.
- **Dependências:** IMP-06.
- **Riscos:** duplicar validações já existentes; centralizar sem esconder regra de módulo.
- **Aceite:** coluna/aba/pasta inválidas são detectadas antes da execução com mensagem específica; testes de contrato.
- **Tarefas:** FT-021.

---

### Categoria 3 — Arquitetura e infraestrutura

#### IMP-10 — Banco versionado, íntegro e sustentável

- **Descrição:** migrações incrementais, WAL, índices, retenção, backup e verificação de integridade.
- **Problema que resolve:** AUD-09 e AUD-03.
- **Benefício:** evolução segura do histórico; desempenho e recuperação.
- **Complexidade:** média. **Prioridade:** P1.
- **Dependências:** IMP-11 para desenho das tabelas de detalhes.
- **Riscos:** migração mal testada corrompe dados; sempre copiar antes e testar com banco antigo.
- **Aceite:** `PRAGMA user_version`; migração de banco vazio e antigo; WAL ativo; política de retenção; backup verificável.
- **Tarefas:** FT-016, FT-018, FT-031.

#### IMP-11 — Histórico com detalhes e artefatos

- **Descrição:** persistir detalhes por linha/arquivo e permitir consulta/exportação posterior.
- **Problema que resolve:** AUD-07; hoje só há resumo e log.
- **Benefício:** conferência, suporte, reprocessamento e base para undo/relatórios.
- **Complexidade:** média. **Prioridade:** P1.
- **Dependências:** IMP-10.
- **Riscos:** crescimento do banco; definir limite, compressão e arquivo externo.
- **Aceite:** abrir execução antiga mostra detalhes; exportar detalhes; detalhes grandes não bloqueiam a UI; testes.
- **Tarefas:** FT-017, FT-038.

#### IMP-12 — Journal e undo de operações

- **Descrição:** registrar origem/destino/status antes de cada movimento e oferecer desfazer no histórico.
- **Problema que resolve:** AUD-08; manifesto tardio e ausência de reversão.
- **Benefício:** confiança para operar em lote; recuperação rápida.
- **Complexidade:** grande. **Prioridade:** P1.
- **Dependências:** IMP-11.
- **Riscos:** desfazer precisa validar que o destino ainda é o esperado; não sobrescrever; operações não reversíveis devem ser marcadas.
- **Aceite:** organizador e duplicatas gravam journal antes de mover; undo restaura somente o que ainda corresponde; falha é reportada sem perda.
- **Tarefas:** FT-019, FT-054.

#### IMP-13 — Concorrência e instância única

- **Descrição:** coordenador de operações e lock de instância.
- **Problema que resolve:** AUD-05 e AUD-11.
- **Benefício:** evita duas operações sobre a mesma pasta e status incorretos.
- **Complexidade:** média. **Prioridade:** P1.
- **Dependências:** IMP-02 (encerramento) e IMP-08.
- **Riscos:** bloquear demais irrita; permitir leituras concorrentes e bloquear só escrita.
- **Aceite:** segunda operação mutável é enfileirada/bloqueada com aviso; segunda instância é impedida ou isolada; testes.
- **Tarefas:** FT-012, FT-028, FT-036.

#### IMP-14 — Configuração, logging e privacidade

- **Descrição:** preferências centrais, reset, pastas recentes, log acessível, redaction e retenção.
- **Problema que resolve:** AUD-24, AUD-31 e ausência de settings.
- **Benefício:** operação previsível, suporte e governança de dados.
- **Complexidade:** média. **Prioridade:** P2.
- **Dependências:** IMP-10.
- **Riscos:** não logar demais nem de menos; documentar o que é gravado.
- **Aceite:** usuário vê/limpa dados, define retenção, abre logs e reseta preferências; logs não contêm conteúdo de células.
- **Tarefas:** FT-025, FT-026, FT-027.

---

### Categoria 4 — Interface e experiência do usuário

#### IMP-15 — Seleção de abas e colunas de verdade

- **Descrição:** `ParamSpec` de aba, preenchimento em cascata, validação e feedback.
- **Problema que resolve:** AUD-17 e atrito de configuração.
- **Benefício:** reduz a maior fonte de erro; viabiliza arquivos multiaba.
- **Complexidade:** grande. **Prioridade:** P1.
- **Dependências:** IMP-03/IMP-09.
- **Riscos:** desempenho ao ler cabeçalhos em arquivos grandes/rede; cache e carregamento assíncrono se necessário.
- **Aceite:** abas listadas; colunas atualizam ao trocar aba; seleção inválida é sinalizada; comparador aceita abas independentes.
- **Tarefas:** FT-024, FT-032, FT-033.

#### IMP-16 — Preflight, confirmação e prevenção de erro

- **Descrição:** validação inline, resumo do que será feito e confirmação informada.
- **Problema que resolve:** AUD-06 e AUD-35.
- **Benefício:** menos execuções erradas; mais confiança.
- **Complexidade:** média. **Prioridade:** P1.
- **Dependências:** IMP-08/IMP-09.
- **Riscos:** excesso de diálogos; usar resumo somente para operações mutáveis.
- **Aceite:** erros aparecem junto ao campo; confirmação mostra contagem/amostra e alerta se o plano mudou.
- **Tarefas:** FT-034, FT-035.

#### IMP-17 — Progresso, cancelamento e estado global

- **Descrição:** progresso por fase, indeterminado em leitura, ETA, checkpoints e indicador global.
- **Problema que resolve:** AUD-27 e AUD-05.
- **Benefício:** reduz sensação de travamento e fechamento acidental.
- **Complexidade:** média. **Prioridade:** P1.
- **Dependências:** IMP-13.
- **Riscos:** falso ETA; preferir “processando X de Y” quando não houver estimativa confiável.
- **Aceite:** leitura longa mostra estado; limpeza cancela em checkpoint; só uma operação mutável; testes de cancelamento.
- **Tarefas:** FT-036, FT-037.

#### IMP-18 — Histórico utilizável

- **Descrição:** filtros, busca, exportação, reexecução, detalhes e abertura de saída.
- **Problema que resolve:** AUD-07/AUD-32.
- **Benefício:** conferência e repetição de tarefas; base de auditoria.
- **Complexidade:** grande. **Prioridade:** P1.
- **Dependências:** IMP-11.
- **Riscos:** privacidade; reexecução deve revalidar caminhos e nunca repetir às cegas.
- **Aceite:** filtrar por módulo/modo/status/período; exportar CSV; abrir detalhes; reexecutar com confirmação.
- **Tarefas:** FT-038.

#### IMP-19 — Diagnóstico, configurações e ajuda

- **Descrição:** abrir logs/dados, settings, sobre, ajuda contextual e pacote de suporte.
- **Problema que resolve:** AUD-31 e AUD-35.
- **Benefício:** autonomia do usuário e suporte eficiente.
- **Complexidade:** média. **Prioridade:** P2.
- **Dependências:** IMP-14.
- **Riscos:** expor caminhos sensíveis; pacote deve excluir conteúdo de células.
- **Aceite:** ações abrem a pasta correta; “Sobre” mostra versão/SO/dados; ajuda por ferramenta; pacote de diagnóstico gerado.
- **Tarefas:** FT-039, FT-040, FT-044, FT-088.

#### IMP-20 — Produtividade visual e acessibilidade

- **Descrição:** tabela com filtro/ordenação/cópia, atalhos, estados vazios, contraste/escala.
- **Problema que resolve:** AUD-35 e limitação de 1.000 linhas sem navegação.
- **Benefício:** uso diário mais rápido; inclusão.
- **Complexidade:** grande. **Prioridade:** P2.
- **Dependências:** IMP-18.
- **Riscos:** complexidade de tabela em Tkinter; começar por filtro/ordenação/cópia e paginação.
- **Aceite:** filtrar/ordenar/copiar; navegação por teclado; textos legíveis; testes de UI.
- **Tarefas:** FT-041, FT-042, FT-043, FT-045, FT-046, FT-047.

---

### Categoria 5 — Melhorias nas ferramentas existentes

#### IMP-21 — Limpador mais seguro e transparente

- **Descrição:** suporte a múltiplas abas, preview antes/depois e limites explícitos.
- **Problema que resolve:** AUD-31 (fidelidade) e conferência difícil.
- **Benefício:** menos retrabalho; confiança no que mudou.
- **Complexidade:** grande. **Prioridade:** P2.
- **Dependências:** IMP-15 e IMP-23 (exportação).
- **Riscos:** preservar fórmulas/estilos é complexo; declarar claramente o que é preservado.
- **Aceite:** escolher abas; amostra de células antes/depois; documentação de limitações; testes.
- **Tarefas:** FT-048, FT-049.

#### IMP-22 — Comparador mais confiável

- **Descrição:** política de chaves duplicadas, normalização de chaves, abas e relatório de diferenças.
- **Problema que resolve:** AUD-17/AUD-18 e comparação em multiaba.
- **Benefício:** conciliação confiável e utilizável em bases reais.
- **Complexidade:** média. **Prioridade:** P1.
- **Dependências:** IMP-01/IMP-15.
- **Riscos:** mudar semântica padrão pode surpreender; documentar e permitir escolha.
- **Aceite:** duplicidade aborta por padrão (ou opção explícita); abas selecionáveis; exportar somente diferenças; testes.
- **Tarefas:** FT-050, FT-051.

#### IMP-23 — CNPJ e pastas por empresa

- **Descrição:** melhorar validação, relatório de exceções, nomes por CNPJ, manifesto e preview de conflitos.
- **Problema que resolve:** lacunas de conferência e rastreabilidade.
- **Benefício:** uso em cadastros reais; recuperação.
- **Complexidade:** média. **Prioridade:** P2.
- **Dependências:** IMP-12 (undo/manifesto) e IMP-09.
- **Riscos:** regra de nome curto é subjetiva; manter configurável.
- **Aceite:** relatório de inválidos/duplicados separado; opção de CNPJ no nome; manifesto; testes.
- **Tarefas:** FT-052, FT-053.

#### IMP-24 — Organizador e duplicatas mais seguros e rápidos

- **Descrição:** presets, recursão opcional, undo, cache/paralelismo de hash, guarda de quarentena.
- **Problema que resolve:** AUD-23/AUD-26/AUD-08.
- **Benefício:** volume com segurança; menos tempo de espera.
- **Complexidade:** grande. **Prioridade:** P2.
- **Dependências:** IMP-12.
- **Riscos:** recursão e cache podem mover/hashar mais do que o esperado; preview obrigatório.
- **Aceite:** preset salvo/reutilizado; recursão explícita; quarentena fora da árvore confirmada; hash com cache; testes.
- **Tarefas:** FT-054, FT-055, FT-056.

---

### Categoria 6 — Novas ferramentas financeiras

> Priorizadas por reuso do núcleo, valor para o usuário e risco de domínio. Nenhuma deve ser implementada antes das correções P0/P1.

#### IMP-25 — Renomeador e conversor de arquivos

- **Descrição:** renomeação em lote por empresa/CNPJ/competência/tipo e conversão XLSX/XLS/CSV.
- **Problema que resolve:** trabalho manual massivo e formatos inconsistentes.
- **Benefício:** organização padronizada; interoperabilidade.
- **Complexidade:** grande (dois módulos). **Prioridade:** P1.
- **Dependências:** IMP-15, IMP-12 (para renomeação segura).
- **Riscos:** renomear é destrutivo; exigir preview, conflito explícito e journal.
- **Aceite:** regras previsíveis, preview com conflitos, nada sobrescrito, journal; conversão com opções de codificação/separador e validação.
- **Tarefas:** FT-057, FT-058, FT-059.

#### IMP-26 — Validador de planilhas

- **Descrição:** regras de campos obrigatórios, datas, valores, duplicidades e consistência, com relatório de pendências.
- **Problema que resolve:** conferência manual e erros que só aparecem depois.
- **Benefício:** qualidade de dados antes de conciliar/importar.
- **Complexidade:** grande. **Prioridade:** P1.
- **Dependências:** IMP-15/IMP-09.
- **Riscos:** regras rígidas demais; começar por um conjunto pequeno e configurável.
- **Aceite:** regras salvas, execução por lote, relatório de violações com linha/coluna; testes.
- **Tarefas:** FT-060, FT-061.

#### IMP-27 — Conferência financeira

- **Descrição:** boleto, pagamentos duplicados, conciliação de pagamentos, comparação de períodos e saldos.
- **Problema que resolve:** rotinas financeiras de alto valor e alto risco.
- **Benefício:** detecção de divergências e evidências.
- **Complexidade:** grande. **Prioridade:** P2.
- **Dependências:** IMP-22 (comparador), IMP-11 (histórico).
- **Riscos:** regras de negócio variam por empresa; validar com usuários e manter parâmetros explícitos.
- **Aceite:** cada ferramenta com casos de teste reais anonimizados, relatório de conciliados/pendentes e trilha.
- **Tarefas:** FT-062, FT-063, FT-064, FT-065, FT-066.

#### IMP-28 — Cálculos e rateio

- **Descrição:** juros, atualização monetária, rateio e memória de cálculo.
- **Problema que resolve:** cálculos repetitivos em planilhas manuais.
- **Benefício:** padronização e conferência.
- **Complexidade:** média. **Prioridade:** P2.
- **Dependências:** IMP-09 e política de arredondamento documentada.
- **Riscos:** erro de fórmula/índice; exigir memória de cálculo e testes com valores conhecidos.
- **Aceite:** parâmetros, memória passo a passo, exportação e casos de teste validados.
- **Tarefas:** FT-067, FT-068.

#### IMP-29 — Documentos, busca, PDF e clipboard

- **Descrição:** verificador de documentos, busca, manipulação de PDF e histórico de clipboard.
- **Problema que resolve:** conferência documental e produtividade.
- **Benefício:** reduz saltos entre ferramentas.
- **Complexidade:** grande. **Prioridade:** P3.
- **Dependências:** IMP-25/IMP-30; PDF exige dependência nova aprovada.
- **Riscos:** OCR/PDF têm licenças e tamanho; busca em conteúdo é custosa.
- **Aceite:** cada ferramenta com escopo mínimo, dependência avaliada e testes.
- **Tarefas:** FT-069, FT-070, FT-071, FT-072, FT-073.

---

### Categoria 7 — Automação de processos

#### IMP-30 — Processamento em lote

- **Descrição:** executar um módulo sobre vários arquivos/abas com relatório consolidado e continuidade em falhas.
- **Problema que resolve:** repetição manual; maior ganho de produtividade.
- **Benefício:** processar 100 arquivos em uma operação; menos erro.
- **Complexidade:** grande. **Prioridade:** P1.
- **Dependências:** IMP-08/IMP-11/IMP-12.
- **Riscos:** falha parcial; exigir journal, resumo por item e opção de parar/continuar.
- **Aceite:** seleção múltipla, preview consolidado, execução com journal, relatório e retomada; testes.
- **Tarefas:** FT-074, FT-075.

#### IMP-31 — Fluxos encadeados e presets

- **Descrição:** salvar configurações e encadear módulos (saída de um vira entrada de outro).
- **Problema que resolve:** rotinas mensais compostas.
- **Benefício:** automação reutilizável; menos configuração.
- **Complexidade:** grande. **Prioridade:** P2.
- **Dependências:** IMP-30.
- **Riscos:** acoplamento e depuração; começar por 2–3 etapas e logs claros.
- **Aceite:** fluxo salvo, validação de entradas/saídas, execução com journal e falha controlada; testes.
- **Tarefas:** FT-076, FT-077, FT-078.

#### IMP-32 — Monitor, agendador, notificações e CLI

- **Descrição:** observar pastas, executar em horários, notificar e rodar sem interface.
- **Problema que resolve:** rotinas que precisam rodar sozinhas.
- **Benefício:** automação real; integração com Windows.
- **Complexidade:** grande. **Prioridade:** P3.
- **Dependências:** IMP-30/IMP-31 e assinatura/segurança.
- **Riscos:** execuções não supervisionadas; exigir idempotência, logs, limite e “dry-run”.
- **Aceite:** agendamento testado, notificação, CLI documentada e desabilitada por padrão.
- **Tarefas:** FT-079, FT-080, FT-081, FT-082.

---

### Categoria 8 — Segurança e integridade dos dados

#### IMP-33 — Quarentena e operações destrutivas revisadas

- **Descrição:** validar quarentena, confirmar saída da árvore, revisar todas as operações que movem/criam e documentar reversibilidade.
- **Problema que resolve:** AUD-23 e risco de comportamento inesperado.
- **Benefício:** operações previsíveis e recuperáveis.
- **Complexidade:** média. **Prioridade:** P1.
- **Dependências:** IMP-12.
- **Riscos:** excesso de confirmações; aplicar só quando houver movimento fora do escopo.
- **Aceite:** quarentena fora da pasta exige confirmação; nenhuma operação sobrescreve; checklist de revisão assinado.
- **Tarefas:** FT-056, FT-093.

#### IMP-34 — Confiança na distribuição

- **Descrição:** assinatura de código e verificação de integridade do executável/atualizações.
- **Problema que resolve:** SmartScreen/antivírus e atualização segura.
- **Benefício:** instalação sem atrito; confiança.
- **Complexidade:** grande (custo/processo). **Prioridade:** P2.
- **Dependências:** IMP-38.
- **Riscos:** certificado tem custo e processo; validar antes de prometer.
- **Aceite:** executável assinado e verificado; atualização com hash/assinatura.
- **Tarefas:** FT-087.

---

### Categoria 9 — Testes e confiabilidade

#### IMP-35 — Regressão, cobertura e testes de UI

- **Descrição:** testes para cada P0, testes de contrato, UI headless, fixtures de arquivos problemáticos e benchmarks.
- **Problema que resolve:** AUD-28.
- **Benefício:** evolução segura; bugs conhecidos não voltam.
- **Complexidade:** média. **Prioridade:** P1.
- **Dependências:** nenhuma; começar junto dos P0.
- **Riscos:** testes frágeis de UI; usar poucos smoke tests e muito teste de serviço.
- **Aceite:** suíte cobre os fluxos críticos e falhas conhecidas; cobertura medida; benchmarks registram tempo/memória.
- **Tarefas:** FT-014, FT-047, FT-092.

#### IMP-36 — Compatibilidade Windows e build

- **Descrição:** matriz Windows 10/11, Python suportado, build e smoke test do executável.
- **Problema que resolve:** AUD-29/AUD-30.
- **Benefício:** release previsível.
- **Complexidade:** grande. **Prioridade:** P1.
- **Dependências:** IMP-35.
- **Riscos:** ambiente de CI Windows e tempo de build; começar por um job manual reproduzível.
- **Aceite:** build reproduzível, testes e exe abrindo em máquina limpa; relatório de versões.
- **Tarefas:** FT-085, FT-095.

---

### Categoria 10 — Distribuição, instalação e atualização

#### IMP-37 — Dependências reproduzíveis

- **Descrição:** pins/lock, requirements de dev, política de atualização e matriz de Python.
- **Problema que resolve:** AUD-29.
- **Benefício:** builds iguais; bugs reproduzíveis.
- **Complexidade:** média. **Prioridade:** P1.
- **Dependências:** nenhuma.
- **Riscos:** pins atrasam correções de segurança; revisar periodicamente.
- **Aceite:** ambiente recriado do zero gera as mesmas versões; documentação e teste.
- **Tarefas:** FT-083.

#### IMP-38 — Metadados, instalador e atualização

- **Descrição:** ícone, versão, instalador, desinstalador e atualização.
- **Problema que resolve:** AUD-30.
- **Benefício:** distribuição profissional; menor suporte.
- **Complexidade:** grande. **Prioridade:** P2.
- **Dependências:** IMP-36.
- **Riscos:** atualização pode quebrar dados; exigir backup e migração.
- **Aceite:** instalador em máquina limpa, versão visível, atualização com rollback e dados preservados.
- **Tarefas:** FT-084, FT-086.

#### IMP-39 — Documentação, suporte, backup e release

- **Descrição:** manual, changelog, pacote de diagnóstico, backup/restauração e checklist de release.
- **Problema que resolve:** AUD-31/AUD-34.
- **Benefício:** onboarding e suporte; releases disciplinadas.
- **Complexidade:** média. **Prioridade:** P2.
- **Dependências:** IMP-14/IMP-38.
- **Riscos:** documentação desatualizada; gerar changelog do próprio repositório e revisar no release.
- **Aceite:** manual e changelog publicados; backup/restore testado; checklist aplicado a uma release.
- **Tarefas:** FT-088, FT-089, FT-090, FT-094.

#### IMP-40 — Higiene de repositório e release

- **Descrição:** Git, branches, tags, changelog e política de versão.
- **Problema que resolve:** AUD-01.
- **Benefício:** histórico, revisão, rollback e releases rastreáveis.
- **Complexidade:** pequena. **Prioridade:** P0 (processo).
- **Dependências:** nenhuma.
- **Riscos:** processo burocrático demais para um desenvolvedor; manter simples (branch curta + tag).
- **Aceite:** repositório versionado, `.gitignore` revisado, tag `v0.1.0` e checklist de release.
- **Tarefas:** FT-015, FT-091.

---

## 3. Fases de evolução

> As fases são intencionais: cada uma entrega uma capacidade verificável. A numeração dos IDs é preservada; tarefas podem ser antecipadas, mas não renumeradas.

### Fase 0 — Estabilização e confiança

**Objetivo:** eliminar erros conhecidos, impedir perda de integridade e criar base de verificação.

**Entregas esperadas**

- Correções de comparação numérica, inicialização, encerramento, exportação, cabeçalhos e CSV.
- Manifesto antes de movimentações.
- `run_id` correlacionado e status padronizados.
- Registro validado, lock de operação e baseline de cobertura.
- Repositório versionado.

**Tarefas:** FT-001 a FT-015.

**Dependências:** nenhuma externa; FT-004/FT-012 se beneficiam de decisões de journal (Fase 1), mas podem começar com bloqueio simples.

**Critérios de conclusão**

- Todos os P0 com teste de regressão.
- Suíte existente + novos testes aprovados em Linux e Windows.
- Nenhuma fórmula executável em CSV/XLSX; nenhuma colisão de aba.
- Fechar o app durante operação não deixa estado sem registro.
- Banco inválido não impede abertura.
- Build local reproduzível (mesmo que o instalador venha depois).

**Riscos:** mudanças transversais em módulos; priorizar testes e fazer uma correção por vez. Não iniciar novas ferramentas antes de fechar os P0.

---

### Fase 1 — Núcleo confiável

**Objetivo:** transformar histórico, validação e operações de arquivo em serviços maduros.

**Entregas esperadas**

- Migrações, WAL, índices, retenção e backup.
- Detalhes persistidos e consultáveis.
- Journal/undo de movimentações.
- Plano de execução vinculado ao preview.
- Validação/preflight compartilhados e erros acionáveis.
- Exportação com desempenho adequado.
- Configuração, logging e privacidade.

**Tarefas:** FT-016 a FT-031.

**Dependências:** Fase 0 (especialmente FT-003, FT-004, FT-012, FT-014).

**Critérios de conclusão**

- Banco migra de versão antiga sem perda; retenção funciona.
- Detalhes de uma execução antiga abrem/exportam.
- Organizador e duplicatas podem ser desfeitos com segurança.
- Preview aprovado é revalidado antes de executar.
- Erros conhecidos têm mensagem orientativa.
- Benchmarks de exportação registrados.

**Riscos:** migração e undo são as áreas mais sensíveis; implementar com backup, testes e feature flag interna. Não otimizar prematuramente o banco sem medir.

---

### Fase 2 — Experiência operacional

**Objetivo:** reduzir atrito e dar visibilidade ao usuário.

**Entregas esperadas**

- Seleção de abas/colunas com cascata e feedback.
- Validação inline e confirmação com resumo.
- Indicador global, progresso e cancelamento melhores.
- Histórico filtrável/exportável/reexecutável.
- Diagnóstico, configurações, ajuda e acessibilidade básica.
- Tabela de resultados utilizável em volume.

**Tarefas:** FT-032 a FT-047.

**Dependências:** Fase 1 (histórico, validação, plano).

**Critérios de conclusão**

- Nenhum campo de aba é texto livre nos módulos.
- Erros comuns aparecem antes da execução.
- Usuário encontra logs/dados sem suporte.
- Histórico responde às perguntas “o que rodou?”, “o que mudou?”, “posso repetir?”.
- Testes de UI headless no CI Windows.

**Riscos:** Tkinter limita componentes ricos; priorizar tabela/filtros e atalhos, não reescrever a UI. Evitar excesso de diálogos.

---

### Fase 3 — Expansão funcional

**Objetivo:** aprofundar ferramentas existentes e adicionar as de maior valor/reuso.

**Entregas esperadas**

- Limpador/comparador/CNPJ/empresas/organizador/duplicatas evoluídos.
- Renomeador, conversor e validador de planilhas.
- Conferência financeira (boletos, pagamentos, períodos, saldos).
- Cálculos/rateio.
- Ferramentas documentais em fase posterior.

**Tarefas:** FT-048 a FT-073.

**Dependências:** Fases 1 e 2; renomeação depende de journal; conferência depende de comparador.

**Critérios de conclusão**

- Cada ferramenta nova tem preview, journal quando aplicável, testes e documentação.
- Pelo menos um caso real anonimizado validado por ferramenta financeira.
- Nenhuma ferramenta nova duplica lógica existente sem reuso.

**Riscos:** domínio financeiro e variação entre empresas; validar com usuários antes de generalizar. Não implementar 25 ferramentas em paralelo.

---

### Fase 4 — Automação e integração

**Objetivo:** permitir processar volume e encadear rotinas.

**Entregas esperadas**

- Lote de arquivos/abas com relatório consolidado.
- Presets e fluxos encadeados.
- Monitor de pastas, agendador, notificações e CLI.

**Tarefas:** FT-074 a FT-082.

**Dependências:** Fase 3 e journal/plano maduros.

**Critérios de conclusão**

- Um lote de 100 itens é executado com resumo e journal.
- Fluxo de 2–3 etapas é salvo, reexecutado e falha de forma controlada.
- Nenhuma automação roda sem log, limite e opção de dry-run.

**Riscos:** automação não supervisionada multiplica erros; exigir idempotência, confirmação na primeira execução e limites. Agendador/monitor só depois de maturidade operacional.

---

### Fase 5 — Distribuição e maturidade

**Objetivo:** entregar, atualizar e suportar o produto com previsibilidade.

**Entregas esperadas**

- Dependências reproduzíveis e matriz de compatibilidade.
- Metadados, build verificado, instalador e atualização.
- Assinatura, pacote de diagnóstico, backup/restore.
- Manual, changelog, checklist e piloto.

**Tarefas:** FT-083 a FT-095.

**Dependências:** todas as anteriores, especialmente Fase 2 (diagnóstico) e Fase 1 (migrações).

**Critérios de conclusão**

- Instalação em máquina Windows limpa sem Python.
- Executável abre, executa uma ferramenta e exporta.
- Atualização preserva dados; rollback existe.
- Suporte consegue pedir um pacote de diagnóstico.
- Release taggeada e documentada.

**Riscos:** assinatura/instalador têm custo e processo; não bloquear valor das fases anteriores por isso. Validar antivírus/SmartScreen cedo.

---

## 4. Reorganização do roadmap existente

O catálogo atual tem 25 itens em fases 1–6. A proposta abaixo preserva a intenção, mas muda a ordem por **risco, reuso e valor**. “Fase” aqui se refere a este roadmap, não ao campo `phase` do catálogo.

| Item planejado | Decisão | Justificativa | Dependências principais |
|---|---|---|---|
| `activity_log` | **Redefinir** | Não criar módulo separado: ampliar o histórico existente (filtros, exportação, detalhes, reexecução). Evita duplicação de conceito. | FT-017, FT-038 |
| `file_renamer` | **Antecipar** | Alto valor, reuso de normalizadores/sanitização; exige journal por ser destrutivo. | FT-019, FT-057/058 |
| `file_converter` | **Antecipar** | Baixo risco, reusa leitura/exportação; resolve formatos incomuns. | FT-024, FT-059 |
| `sheet_validator` | **Antecipar** | Complementa limpador/comparador; alto valor de conferência. | FT-021, FT-060/061 |
| `boleto_validator` | **Manter/antecipar moderadamente** | Algoritmo bem definido, valor alto, escopo controlado. | FT-062 |
| `duplicate_payments` | **Manter** | Reusa comparação; depende de política de chaves. | FT-050, FT-063 |
| `payment_checker` | **Manter** | Alto valor, domínio complexo; validar regras com usuários. | FT-050, FT-064 |
| `balance_checker` | **Manter** | Alto valor; precisa de layouts e tolerâncias. | FT-050, FT-066 |
| `period_comparator` | **Manter** | Reusa comparador e histórico. | FT-050, FT-065 |
| `interest_calculator`, `monetary_update` | **Manter** | Cálculo exige memória e testes; não é urgente antes do núcleo. | FT-068 |
| `allocation` | **Manter** | Médio valor; a conferência do total distribuído é essencial. | FT-067 |
| `cash_flow` | **Adiar** | Depende de modelo de dados e premissas; maior escopo. | Fase 4/5 |
| `collection_files` | **Adiar** | Layouts de cobrança variam muito; requer descoberta com usuários. | Fase 5 |
| `document_checker` | **Manter depois do lote** | Ganha valor com processamento em lote e busca. | FT-030, FT-069 |
| `file_search` | **Adiar moderadamente** | Indexação e conteúdo são custosos; começar por nome/metadados. | FT-070 |
| `pdf_tools` | **Adiar** | Dependência nova (`pypdf` etc.), licença e tamanho; alto valor, mas não bloqueia o núcleo. | FT-071 |
| `clipboard` | **Adiar** | Fora do núcleo financeiro; baixo risco, baixa prioridade. | FT-072 |
| `formula_auditor` | **Adiar** | Exige parsing de fórmulas/estilos; escopo técnico maior. | Fase 5 |
| `ocr_extractor` | **Adiar** | Dependência pesada, precisão incerta, privacidade; só com casos reais. | Fase 5+ |
| `anomaly_detector` | **Adiar** | Precisa de dados rotulados e definição de “anomalia”; risco de falso positivo. | Fase 5+ |
| `folder_monitor` | **Adiar para automação** | Só faz sentido com lote/journal/idempotência. | FT-079 |
| `task_scheduler` | **Adiar para automação** | Idem; preferir Agendador do Windows no início. | FT-080 |
| `monthly_close` | **Redefinir como produto de processo** | Não é um utilitário isolado; requer modelo de checklist, responsáveis e prazos. | Fase 5+ |
| `evidence_generator` | **Adiar** | Depende de histórico/artefatos confiáveis. | FT-011/FT-039 |
| `duplicate_payments` (já citado) | — | — | — |
| `file_renamer` (já citado) | — | — | — |

**Resumo da reorganização**

- **Antecipados:** renomeador, conversor, validador de planilhas.
- **Redefinidos:** `activity_log` (histórico) e `monthly_close` (processo, não utilitário).
- **Mantidos:** conferência financeira, cálculos, rateio, boletos, períodos.
- **Adiados:** PDF, busca de conteúdo, OCR, anomalias, monitor, agendador, clipboard, fechamento/evidências.

Justificativa técnica: os antecipados reutilizam serviços existentes e atacam dores imediatas; os adiados introduzem dependências, domínio ou operação não supervisionada que exigem a base das fases anteriores.

---

## 5. Ordem recomendada de execução

### Caminho crítico (mínimo viável)

```text
FT-001/002 (comparação)
   → FT-005/010 (exportação)
   → FT-003/004 (início/fim)
   → FT-006/007 (planilhas)
   → FT-014 (regressão)
   → FT-016/017 (migração + detalhes)
   → FT-019 (journal/undo)
   → FT-020/021/022 (plano + validação + erros)
   → FT-024/032/033 (abas/colunas)
   → FT-038 (histórico)
   → FT-074 (lote)
```

### Lotes de trabalho sugeridos

| Lote | Foco | Tarefas | Resultado |
|---|---|---|---|
| L0 | Correções que impedem confiança | FT-001–008, FT-015 | base estável |
| L1 | Verificação e contrato | FT-009–014 | regressão, lock, registro |
| L2 | Núcleo de dados | FT-016–023 | migração, detalhes, journal, exportação |
| L3 | Entrada e feedback | FT-024, FT-032–037 | abas, validação, progresso |
| L4 | Histórico e diagnóstico | FT-025–031, FT-038–040 | operação e suporte |
| L5 | Ferramentas de maior valor | FT-048–061 | limpeza, comparação, renomeação, conversão, validação |
| L6 | Conferência financeira | FT-062–068 | boletos, pagamentos, períodos, saldos, cálculos |
| L7 | Lote e automação | FT-074–082 | produtividade em volume |
| L8 | Distribuição | FT-083–095 | release sustentável |

### O que não fazer agora

- Trocar Tkinter, SQLite ou o contrato `BaseModule`.
- Implementar OCR, anomalias, monitor/agendador ou fluxos antes de journal/lote.
- Criar um segundo sistema de histórico paralelo (`activity_log`).
- Refatorar todos os módulos para “clean architecture” sem ganho concreto.
- Atualizar dependências sem autorização e sem testes.
- Prometer preservação de fórmulas/estilos em planilhas antes de validar a abordagem.

---

## 6. Métricas de acompanhamento

| Dimensão | Métrica | Meta inicial |
|---|---|---|
| Correção | Bugs P0 abertos | 0 antes da Fase 1 |
| Testes | Fluxos críticos com teste de regressão | 100% |
| Cobertura | Linhas em `core/` e `modules/` | ≥ 80% (medida, não dogma) |
| Integridade | Operações mutáveis com journal | 100% |
| Rastreabilidade | Execuções com detalhes consultáveis | 100% |
| Performance | 100k linhas: leitura + limpeza + exportação | baseline definido e monitorado |
| Produtividade | Tempo para processar lote de 100 arquivos | reduzir vs execução manual |
| Suporte | Execuções com pacote de diagnóstico | 100% dos erros reportados |
| Distribuição | Instalação limpa + smoke test | 1 por release |
| Confiabilidade | Execuções interrompidas sem registro | 0 |

---

## 7. Riscos do roadmap e mitigações

| Risco | Mitigação |
|---|---|
| Escopo grande demais | Entregas pequenas por fase; não iniciar Fase 3 antes de fechar P0/P1 |
| Refatoração transversal quebrar módulos | Testes de contrato e regressão antes de mover código |
| Migração de banco perder dados | Backup automático + migração testada + versão de esquema |
| Undo restaurar arquivo errado | Journal com hash/origem/destino e validação antes de desfazer |
| UI Tkinter limitar evolução | Priorizar componentes simples; reavaliar toolkit somente após medir |
| Dependência nova inflar o executável | Avaliar licença/tamanho; empacotar opcionalmente |
| Automação não supervisionada causar dano | Dry-run, limites, logs, idempotência, confirmação inicial |
| Instalador/assinatura atrasar valor | Fases 0–4 não dependem de assinatura; distribuir beta sem ela, com aviso |
| Falta de tempo para testes | Testes fazem parte da definição de pronto de cada tarefa |

---

## 8. Recomendação final de sequência

1. **Fechar a Fase 0 inteira.** É curta, reduz risco e cria confiança.
2. **Fazer Fase 1 em duas ondas:** (a) migrações + detalhes + journal; (b) validação + erros + exportação + configuração.
3. **Fase 2 junto com o início da Fase 1**, pois abas/validação/feedback dependem de serviços, mas podem ser prototipadas cedo.
4. **Só então expandir ferramentas.** Renomeador/conversor/validador de planilhas primeiro; conferência financeira depois de comparador confiável.
5. **Lote antes de fluxos/agendador.** Sem journal e lote, automação é risco.
6. **Distribuição contínua, não no fim absoluto:** metadados e smoke test do `.exe` podem começar na Fase 1; instalador/assinatura ficam para a Fase 5.

A justificativa é simples: o produto já tem valor funcional; o que impede escalar é a confiança nos resultados e a capacidade de operar em volume. Corrigir, registrar e automatizar nessa ordem multiplica o valor de cada ferramenta existente antes de adicionar novas.
