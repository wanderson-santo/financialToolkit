# Finance Toolkit — Decisões de Arquitetura (ADR)

> **Etapa:** 7 — documentação e organização  
> **Formato:** Architecture Decision Records (ADRs) retrospectivos (decisões já embutidas no código) e prospectivos (decisões propostas).  
> **Status:** `aceita` (vigente), `proposta` (requer aprovação), `substituída` (histórico).  
> **Observação:** não existe configuração de OpenSpec no repositório. Estes ADRs são a fonte de verdade atual; a adoção de OpenSpec é opcional e está registrada em ADR-026.

---

## ADR-001 — Usar Tkinter/ttk para a interface desktop

- **Status:** aceita (existente)
- **Contexto:** aplicativo Windows, local, uma janela, formulários e tabelas; equipe pequena; necessidade de distribuir um executável leve com Python.
- **Decisão:** construir a UI em Tkinter/ttk, com tema `clam` customizado.
- **Justificativa:** vem com Python (sem dependência pesada), é suficiente para formulários/tabelas, facilita o build PyInstaller e mantém o app leve.
- **Consequências:** componentes ricos (tabela virtualizada, diff visual, acessibilidade avançada) exigem mais trabalho; o visual é mais simples que toolkits modernos. **Não trocar agora**: os problemas prioritários são de correção, rastreabilidade e fluxo, não de toolkit. Reavaliar somente após medir limitações reais (ADR-025).
- **Relacionados:** AUD-35, IMP-20.

## ADR-002 — Separar `core/` de `app/`

- **Status:** aceita (existente)
- **Contexto:** necessidade de testar lógica sem abrir janela e permitir troca futura de UI.
- **Decisão:** `core/` não importa `app/`; `modules/` depende de `core/`; `app/` orquestra a interface.
- **Justificativa:** testabilidade, coesão e baixo acoplamento; comprovado pela suíte rodar sem display.
- **Consequências:** algum acoplamento residual da UI a serviços (`list_columns`, `export_rows`); o container `Services` é mínimo. Preservar a regra e, se necessário, evoluir a injeção sem reescrever tudo.
- **Relacionados:** `docs/project-discovery.md` §5.2.

## ADR-003 — Contrato de módulo baseado em `BaseModule` + `ParamSpec` + `Result`

- **Status:** aceita (existente)
- **Contexto:** catálogo grande planejado; custo de criar formulário/execução/histórico por ferramenta.
- **Decisão:** cada ferramenta declara metadados e parâmetros; a UI gera o formulário e o ciclo de execução.
- **Justificativa:** reduz drasticamente o custo de novas ferramentas; mantém consistência de UX e histórico.
- **Consequências:** `kind` string livre e `details` sem esquema permitem erros tardios; `ctx` não é tipado. Evoluir com validação no registro e Protocol (ADR-011/ADR-020), sem quebrar o contrato.
- **Relacionados:** IMP-06, FT-011, FT-029.

## ADR-004 — Registro explícito de módulos (sem descoberta dinâmica)

- **Status:** aceita (existente)
- **Contexto:** PyInstaller não detecta imports dinâmicos; importação por varredura de pastas poderia excluir módulos do executável.
- **Decisão:** lista explícita em `modules/__init__.py`; catálogo planejado separado em `modules/catalog.py`.
- **Justificativa:** build previsível e simples; ordem/controle de disponibilidade.
- **Consequências:** adicionar ferramenta exige dois pontos de edição (módulo + registro); esquecimento gera ferramenta ausente. Validar no registro/teste (FT-011) e documentar o procedimento.
- **Relacionados:** `README.md` “Como adicionar uma ferramenta”.

## ADR-005 — Persistir dados locais em SQLite

- **Status:** aceita (existente)
- **Contexto:** histórico, configurações e favoritos; app local, sem servidor.
- **Decisão:** SQLite em `%APPDATA%\FinanceToolkit`, uma conexão por operação, esquema criado no startup.
- **Justificativa:** zero configuração, transacional, adequado ao volume de metadados.
- **Consequências:** precisa de migrações, WAL, retenção e backup (ADR-014/ADR-015/ADR-016); concorrência entre instâncias deve ser tratada (ADR-018). Não usar ORM neste tamanho.
- **Relacionados:** AUD-09, IMP-10.

## ADR-006 — Local-first e sem telemetria/rede

- **Status:** aceita (existente)
- **Contexto:** dados financeiros sensíveis; proposta de valor “nada sai do computador”.
- **Decisão:** não enviar dados para serviços externos; logs/histórico locais.
- **Justificativa:** privacidade, confiança e simplicidade; não há dependência de nuvem.
- **Consequências:** suporte e melhoria dependem de diagnóstico local (ADR-022); qualquer futura integração/IA exigirá decisão explícita, consentimento e avaliação de risco. Manter essa decisão como restrição de produto.
- **Relacionados:** IMP-14, IMP-19, FT-088.

## ADR-007 — Operações de arquivo conservadoras

- **Status:** aceita (existente)
- **Contexto:** risco de perda de documentos financeiros.
- **Decisão:** nunca sobrescrever (`unique_path`/`move_safe`), nunca excluir; duplicatas vão para quarentena; pré-visualização antes de mover.
- **Justificativa:** segurança operacional e confiança; reduz dano de erro do usuário.
- **Consequências:** pastas acumulam sufixos `_1`; ainda faltam journal/undo e garantia de manifesto antes do move (ADR-017). Essas lacunas devem ser fechadas sem abandonar a política.
- **Relacionados:** IMP-02, IMP-04, IMP-12, FT-008/FT-019.

## ADR-008 — Execução em thread com fila e cancelamento cooperativo

- **Status:** aceita (existente)
- **Contexto:** operações demoradas não podem congelar a UI; Tkinter não é thread-safe.
- **Decisão:** thread de trabalho + `queue.Queue` + `ExecutionContext.emit` + polling na thread principal; cancelamento por `threading.Event`.
- **Justificativa:** mantém a UI responsiva e isola Tk; padrão simples e testável.
- **Consequências:** cancelamento só ocorre em checkpoints; encerramento e concorrência precisam de coordenação (ADR-018); progresso precisa ser emitido nos loops (FT-037).
- **Relacionados:** AUD-04, AUD-05, AUD-27.

## ADR-009 — Empacotar com PyInstaller em modo onefile, sem console

- **Status:** aceita (existente); sujeita a revisão na Fase 5
- **Contexto:** distribuir um `.exe` para usuários Windows sem Python.
- **Decisão:** `finance_toolkit.spec` gera onefile, `console=False`, sem UPX.
- **Justificativa:** instalação simples e sem janela de terminal; UPX desativado por falso positivo.
- **Consequências:** inicialização mais lenta e extração temporária; falha de startup é silenciosa (AUD-03); não há assinatura/instalador/updater. Reavaliar onefile vs onedir e adicionar smoke test (ADR-024).
- **Relacionados:** AUD-30, IMP-36/IMP-38.

## ADR-010 — Interface e conteúdo em pt-BR; alvo Windows

- **Status:** aceita (existente)
- **Contexto:** usuários brasileiros, rotinas financeiras locais.
- **Decisão:** textos em português, formatação BR, caminhos/atalhos Windows; suporte incidental a outros SOs.
- **Justificativa:** reduz atrito e reflete o domínio (CNPJ, reais, Excel BR).
- **Consequências:** i18n não é prioridade; testes precisam cobrir Windows (FT-095); formatação numérica BR deve ser explícita, não adivinhada (FT-001/002).
- **Relacionados:** IMP-01, IMP-36.

## ADR-011 — Validar o contrato de módulo em tempo de registro

- **Status:** proposta
- **Contexto:** `kind`/choices/sources inválidos só falham ao montar a página; `ctx` e `details` não têm tipo.
- **Decisão:** validar metadados no registro/teste, definir Protocol para `ExecutionContext` e documentar o formato de `details`; introduzir validação sem quebrar módulos existentes.
- **Justificativa:** falha cedo, melhor DX para novas ferramentas, menos erros de UI.
- **Consequências:** exige atualizar testes e possivelmente anotações; não muda a UI. Type checker só entra com dependência aprovada.
- **Relacionados:** FT-011, FT-029, IMP-06.

## ADR-012 — Política única de sanitização de exportação

- **Status:** proposta
- **Contexto:** CSV permite injeção de fórmulas; XLSX protege apenas `=`.
- **Decisão:** toda exportação tabular passa por uma função de proteção que neutraliza `= + - @`, tab/CR e espaços à esquerda, sem corromper números.
- **Justificativa:** segurança e consistência entre formatos.
- **Consequências:** textos legítimos que começam com esses caracteres podem ganhar prefixo; documentar e testar. A regra deve ser central, não copiada por módulo.
- **Relacionados:** FT-005, IMP-04.

## ADR-013 — Codificação e separador explícitos, com detecção conservadora

- **Status:** proposta
- **Contexto:** heurística atual valida só 64 KB e pode falhar/mojibake.
- **Decisão:** detectar com validação mais ampla, registrar a decisão e permitir override explícito na UI; nunca aceitar `UnicodeDecodeError` cru.
- **Justificativa:** dados BR frequentemente vêm em cp1252/latin-1; erro silencioso é pior que erro claro.
- **Consequências:** UI ganha campo avançado; arquivos ambíguos podem exigir escolha do usuário. Não adicionar dependência de detecção sem avaliação.
- **Relacionados:** FT-007, FT-033, IMP-03.

## ADR-014 — Versionar o esquema SQLite com migrações incrementais

- **Status:** proposta
- **Contexto:** `CREATE TABLE IF NOT EXISTS` não evolui esquema; futuro exige mudanças.
- **Decisão:** `PRAGMA user_version`, migrações numeradas, backup antes de migrar e teste de upgrade.
- **Justificativa:** evolução segura e recuperável.
- **Consequências:** complexidade adicional no startup; migrações devem ser pequenas e idempotentes. Nunca apagar dados sem confirmação.
- **Relacionados:** FT-016, FT-031, IMP-10.

## ADR-015 — Persistir detalhes de execução com retenção

- **Status:** aceita (implementada na FT-017; retenção configurável fica para a FT-018)
- **Contexto:** detalhes por linha não são gravados; histórico perde valor de auditoria.
- **Decisão:** armazenar detalhes em tabela/arquivo referenciado, com limite e retenção configurável; exportação e consulta pela UI.
- **Justificativa:** rastreabilidade, suporte, undo e relatórios.
- **Consequências:** crescimento de dados; exigir política de retenção (ADR-021) e compressão/arquivo externo para volumes grandes.
- **Relacionados:** FT-017, FT-038, IMP-11.

## ADR-016 — Journal transacional e undo para operações reversíveis

- **Status:** proposta
- **Contexto:** movimentações não têm registro prévio nem reversão; manifesto de duplicatas é tardio.
- **Decisão:** journal antes de cada movimento; undo valida origem/destino/hash; operações não reversíveis marcadas explicitamente.
- **Justificativa:** confiança para volume e recuperação de erro.
- **Consequências:** cada módulo mutável precisa cooperar; undo não pode sobrescrever nem “adivinhar”. Testes adversariais obrigatórios.
- **Relacionados:** FT-008, FT-019, FT-054, IMP-12.

## ADR-017 — Plano de execução vinculado ao preview

- **Status:** proposta
- **Contexto:** preview e execute recalculam; usuário pode aprovar um cenário e executar outro.
- **Decisão:** representar o plano, calcular hash/assinatura das entradas e revalidar antes de executar; confirmação mostra resumo.
- **Justificativa:** a pré-visualização é o principal mecanismo de segurança; precisa ser confiável.
- **Consequências:** refatoração incremental dos módulos mutáveis; leitura duplicada deve ser equilibrada com desempenho. Plano pode ser persistido no journal.
- **Relacionados:** FT-020, FT-035, IMP-08.

## ADR-018 — Coordenador de operações e instância única

- **Status:** proposta
- **Contexto:** múltiplas páginas/instâncias podem operar simultaneamente e marcar execuções alheias como interrompidas.
- **Decisão:** uma operação mutável por instância (ou fila), indicador global e lock de instância; leituras podem ser concorrentes se seguro.
- **Justificativa:** integridade de arquivos e histórico.
- **Consequências:** UX precisa explicar bloqueios; timeout/recuperação de lock; testes de concorrência.
- **Relacionados:** FT-012, FT-028, FT-036, IMP-13.

## ADR-019 — Taxonomia de erros e mensagens acionáveis

- **Status:** proposta
- **Contexto:** erros conhecidos chegam como “Erro inesperado”, sem orientação.
- **Decisão:** mapear exceções de domínio/biblioteca para `ToolkitError` com mensagem de usuário, mantendo detalhe técnico no log e opção de copiar.
- **Justificativa:** reduz suporte e melhora autonomia.
- **Consequências:** exige disciplina ao adicionar novos erros; não esconder informação em falhas desconhecidas.
- **Relacionados:** FT-022, FT-045, IMP-07.

## ADR-020 — Contrato de resultado explícito e testável

- **Status:** proposta
- **Contexto:** status como strings soltas; `details` sem esquema; cancelamento por mutação.
- **Decisão:** constantes/helper central, validação de status e documentação do formato de `details`; manter compatibilidade com módulos atuais.
- **Justificativa:** consistência de histórico/relatórios e menos bugs.
- **Consequências:** pequena refatoração nos módulos; testes de contrato. Não introduzir hierarquia de classes desnecessária.
- **Relacionados:** FT-009, FT-029, IMP-05.

## ADR-021 — Retenção e privacidade de dados locais

- **Status:** proposta
- **Contexto:** histórico/logs guardam caminhos e parâmetros indefinidamente, sem controles.
- **Decisão:** política de retenção configurável, limpeza/exportação, localização visível dos dados e documentação do que é gravado; sem telemetria.
- **Justificativa:** governança/LGPD e sustentabilidade do banco.
- **Consequências:** usuário pode apagar evidências; oferecer exportação antes de limpar. Não criptografar nesta fase (sem segredos), mas registrar a decisão para o futuro.
- **Relacionados:** FT-018, FT-027, FT-089, IMP-14.

## ADR-022 — Diagnóstico local em vez de telemetria

- **Status:** proposta
- **Contexto:** suporte precisa de evidências, mas o produto promete não enviar dados.
- **Decisão:** pacote de diagnóstico gerado localmente (versão, SO, log, estado do banco, sem conteúdo de células) e ações para abrir logs/pasta de dados.
- **Justificativa:** concilia suporte e privacidade.
- **Consequências:** usuário precisa anexar manualmente; documentar o conteúdo e permitir revisão antes de enviar.
- **Relacionados:** FT-026, FT-039, FT-088, IMP-19.

## ADR-023 — Processamento em lote antes de fluxos e agendamento

- **Status:** proposta
- **Contexto:** usuários repetem a mesma configuração para muitos arquivos; automação completa sem base é arriscada.
- **Decisão:** implementar lote com journal/relatório; somente depois fluxos encadeados, monitor, agendador e CLI.
- **Justificativa:** maior valor com menor risco; valida idempotência e recuperação antes de operar sem supervisão.
- **Consequências:** a arquitetura de lote deve ser reutilizada por fluxos/CLI; evitar duplicar runner. Limites e dry-run obrigatórios.
- **Relacionados:** FT-074–FT-082, IMP-30/31/32.

## ADR-024 — Distribuição verificada e atualizável

- **Status:** proposta
- **Contexto:** build nunca validado; sem instalador/assinatura/updater; `console=False` esconde falhas.
- **Decisão:** build reproduzível em Windows, smoke test do executável, metadados/ícone, instalador, backup antes de atualizar e assinatura quando viável.
- **Justificativa:** confiança e suporte em campo.
- **Consequências:** custo de certificado e pipeline; fases anteriores não devem ser bloqueadas por isso. Validar onefile vs onedir com dados reais.
- **Relacionados:** FT-083–FT-087, FT-095, IMP-36/38.

## ADR-025 — Não trocar Tkinter nesta fase

- **Status:** proposta (decisão de não fazer)
- **Contexto:** limitações de tabela/acessibilidade geram desejo de migrar para Qt/Web.
- **Decisão:** manter Tkinter durante as fases 0–3; reavaliar apenas se métricas mostrarem que a UI impede entregas de alto valor.
- **Justificativa:** reescrever a UI não corrige comparação, histórico, journal, abas ou lote; consumiria o orçamento sem entregar valor imediato.
- **Consequências:** algumas melhorias serão mais trabalhosas; priorizar componentes simples (filtro/ordenação/paginação) e medir.
- **Relacionados:** ADR-001, IMP-20.

## ADR-026 — Documentação versionada e OpenSpec opcional

- **Status:** proposta
- **Contexto:** não havia `docs/` nem OpenSpec; README e catálogo divergem.
- **Decisão:** manter `docs/` como fonte de verdade (discovery, auditoria, roadmap, TODO, ADRs); se o time adotar OpenSpec, usá-lo para mudanças futuras, sem duplicar os documentos atuais.
- **Justificativa:** rastreabilidade de decisões e onboarding; baixo custo.
- **Consequências:** documentos precisam ser atualizados a cada fase/release; IDs de tarefas e ADRs são estáveis. Não substituir documentos existentes sem avaliar conteúdo.
- **Relacionados:** FT-090, FT-091, IMP-39/40.

## ADR-027 — Estratégia de testes em camadas

- **Status:** proposta
- **Contexto:** 18 testes cobrem caminhos felizes; sem UI/Windows/build.
- **Decisão:** (1) unidade para `core/` e funções puras; (2) integração para serviços/módulos com arquivos temporários; (3) contrato para todos os módulos; (4) smoke de UI headless; (5) smoke do executável em Windows; (6) benchmarks separados.
- **Justificativa:** maximiza confiança por custo; evita pirâmide invertida de testes de UI.
- **Consequências:** exige fixtures e ambiente Windows; testes de UI devem ser poucos e estáveis. Cobertura é indicador, não meta isolada.
- **Relacionados:** FT-014, FT-047, FT-085, FT-092, IMP-35/36.

## ADR-028 — Fidelidade de planilhas: declarar o que é preservado

- **Status:** proposta
- **Contexto:** limpador lê uma aba e grava dados sem fórmulas/estilos; usuário pode esperar cópia fiel.
- **Decisão:** documentar e exibir que a saída é uma nova base de dados (não uma cópia fiel); suportar múltiplas abas apenas quando o comportamento for explícito; não prometer preservação de fórmulas/estilos sem implementação dedicada.
- **Justificativa:** evita expectativa errada e perda percebida de informação.
- **Consequências:** pode reduzir adoção em casos que exigem formatação; oferecer “exportar apenas dados” como escolha clara. Avaliar `openpyxl` com preservação em tarefa futura.
- **Relacionados:** FT-048, IMP-21.

## ADR-029 — Evolução do catálogo por valor e reuso, não por fases rígidas

- **Status:** proposta
- **Contexto:** catálogo de 25 itens em fases 1–6; fases do README e do catálogo divergem.
- **Decisão:** priorizar renomeador/conversor/validador; redefinir `activity_log` como histórico; adiar OCR/anomalias/monitor/fluxos; usar dependências e valor como critério.
- **Justificativa:** foco em dores reais e reuso; evita 25 frentes simultâneas.
- **Consequências:** itens “planejados” podem mudar de fase ou ser desmembrados; comunicar no catálogo/README. Preservar IDs/descrições para não confundir usuários.
- **Relacionados:** `docs/improvement-roadmap.md` §4, IMP-29.

## ADR-030 — Decisões registradas antes de implementações grandes

- **Status:** proposta
- **Contexto:** mudanças transversais (journal, plano, migrações, lote) afetam vários módulos.
- **Decisão:** toda tarefa “grande” começa com uma nota de decisão curta neste arquivo (contexto, opções, escolha, consequências) e termina com atualização de docs/testes.
- **Justificativa:** evita decisões implícitas e retrabalho; melhora continuidade entre sessões.
- **Consequências:** pequeno overhead; obrigatório para FT-019, FT-023, FT-032, FT-038, FT-074, FT-076, FT-085.
- **Relacionados:** todas as tarefas grandes.

---

## 4. Mapa de decisões existentes → riscos → tarefas

| Decisão existente | Risco decorrente | ADR/ação |
|---|---|---|
| Tkinter | UI limitada para volume | ADR-001/025; FT-042/043 |
| Contrato ParamSpec | Erro só na UI | ADR-003/011; FT-011/029 |
| Registro explícito | Módulo esquecido | ADR-004; FT-011 |
| SQLite sem migração | Evolução/manutenção | ADR-005/014; FT-016 |
| Local-first | Suporte sem telemetria | ADR-006/022; FT-088 |
| Nunca sobrescrever | Sem undo/journal | ADR-007/016; FT-019 |
| Thread+fila | Fechamento/concorrência | ADR-008/018; FT-004/012 |
| Onefile console=False | Falha silenciosa | ADR-009/024; FT-003/085 |
| Histórico resumido | Sem auditoria | ADR-015; FT-017 |
| Roadmap em fases | Divergência/foco | ADR-029; IMP-29 |

---

## 5. Processo de atualização

1. Antes de uma tarefa **grande**, adicionar/atualizar um ADR com status `proposta`.
2. Após implementação e validação, mudar para `aceita` e registrar consequências reais.
3. Decisões revertidas ficam como `substituída`, com link para a nova.
4. Não reescrever o passado: ADRs são históricos; correções vão em novo ADR.
5. Revisar este arquivo no início de cada fase e no release.

**Próxima decisão pendente de aprovação:** FT-001 (correção de tolerância) não exige ADR; FT-016/FT-019/FT-020 exigem ADR antes da implementação.
