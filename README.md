# Finance Toolkit

Hub desktop (Windows) com utilitários para automatizar rotinas do setor financeiro.
Tudo roda **localmente**: nenhum dado sai do computador.

Esta é a **v0.1.0**: núcleo da plataforma + 6 ferramentas. O restante do catálogo
(25 utilitários) aparece no menu como “em breve”, já com a fase prevista.

## Ferramentas disponíveis

| Categoria | Ferramenta | O que faz |
|---|---|---|
| Arquivos e documentos | Organizador automático de pastas | Move arquivos para subpastas por palavra no nome (prioridade) e por extensão. |
| Arquivos e documentos | Detector de arquivos duplicados | Tamanho + SHA-256; só relata ou move as cópias para uma quarentena (com manifesto CSV). Nunca exclui. |
| Arquivos e documentos | Criador de pastas por empresa | Uma pasta por empresa **ATIVA**, com o nome curto (“BB EMPREENDIMENTOS E PARTICIPACOES SA” → “BB”). |
| Excel e dados | Limpador e padronizador de planilhas | Remove vazios, limpa espaços/invisíveis, formata CNPJ, converte datas e valores. Gera `_limpo.xlsx`. |
| Excel e dados | Comparador de planilhas | Incluídos, removidos e alterados por chave, com tolerância numérica. Gera relatório em Excel. |
| Operações financeiras | Validador de CNPJ | Dígitos verificadores (numérico e alfanumérico), formatação e duplicidades. |

Todas têm **Pré-visualizar** (não altera nada), **Executar**, **Cancelar** (seguro),
**Exportar resultado** (XLSX/CSV), histórico e favoritos.

## Como rodar

Requisitos: Windows, Python 3.10–3.12 com Tcl/Tk (vem marcado no instalador) e o launcher `py`.

- `run_dev.bat` — cria o ambiente, instala as dependências e abre o app.
- `run_tests.bat` — roda os testes automatizados (para cobertura, use `python scripts/run_tests.py`).
- `build.bat` — roda os testes e gera `dist\FinanceToolkit.exe` com PyInstaller.

Manualmente:

```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements-build.txt
python main.py                                   # abrir o app
python -m unittest discover -s tests -t .        # somente testes
python scripts/run_tests.py                      # testes + cobertura
pyinstaller --noconfirm --clean finance_toolkit.spec
```

Para testes com cobertura, instale também `requirements-dev.txt`. A baseline e o
mapeamento dos testes de regressão estão em [`docs/testing.md`](docs/testing.md).

Dados do app (histórico, configurações, logs): `%APPDATA%\FinanceToolkit`.

## Arquitetura

```
finance_toolkit/
├── main.py                   ponto de entrada
├── finance_toolkit.spec      configuração do PyInstaller
├── app/                      interface (Tkinter)
│   ├── bootstrap.py          inicialização
│   ├── main_window.py        menu lateral, busca, navegação, erros globais
│   ├── pages.py              Início, Módulo (genérica), Histórico, “em breve”
│   ├── widgets.py            formulário gerado por ParamSpec, tabela, rolagem
│   ├── module_registry.py    registro de módulos disponíveis e planejados
│   └── theme.py              tema escuro
├── core/                     serviços compartilhados (sem dependência de interface)
│   ├── base_module.py        contrato: BaseModule, ParamSpec, Result
│   ├── execution_context.py  log, progresso e cancelamento seguro
│   ├── history_service.py    SQLite: execuções, eventos, configurações, favoritos
│   ├── config_service.py, logging_service.py, paths.py, exceptions.py
│   ├── normalizers.py        texto, CNPJ, números e datas
│   ├── validation_service.py, file_service.py
│   ├── spreadsheet_service.py  leitura XLSX/XLS/CSV (codificação e separador automáticos)
│   └── export_service.py     XLSX/CSV
├── modules/                  um arquivo por ferramenta
│   ├── files/ spreadsheets/ finance/
│   ├── catalog.py            utilitários planejados (roadmap)
│   └── __init__.py           lista explícita de módulos (o PyInstaller precisa dela)
└── tests/                    testes automatizados (unittest)
```

A pasta `core/` não importa nada de `app/`: toda a lógica pode ser testada sem janela
e a interface pode ser trocada (por exemplo, por PySide6) sem reescrever os módulos.

### Como adicionar uma ferramenta

1. Crie `modules/<grupo>/minha_ferramenta.py` com uma classe `BaseModule`:

```python
from core.base_module import BaseModule, ParamSpec, build_result
from core.categories import CATEGORY_SHEETS

class MinhaFerramenta(BaseModule):
    module_id = "minha_ferramenta"
    name = "Minha ferramenta"
    category = CATEGORY_SHEETS
    description = "O que ela faz."
    params = [
        ParamSpec("spreadsheet", "Planilha", "file"),
        ParamSpec("column", "Coluna", "column", source="spreadsheet"),
    ]

    def preview(self, inputs, ctx):   # não altera nada
        ctx.log("Analisando...")
        return build_result("Resumo", processed=0, details=[{"Coluna": "valor"}])

    def execute(self, inputs, ctx):
        ctx.check_cancel()            # permite cancelar
        ctx.progress(1, 1, "Processando")
        return build_result("Concluído", processed=1)
```

2. Registre em `modules/__init__.py` (função `available_modules`).
3. Se ela estava em `modules/catalog.py`, remova de lá.

O formulário, a pré-visualização, a execução em segundo plano, o cancelamento, o
histórico e a exportação já funcionam sem mexer na interface.

## Segurança operacional

- Arquivos originais nunca são sobrescritos; saídas ganham `_1`, `_2`… se o nome já existe.
- Apenas uma execução que altera arquivos roda por vez; pré-visualizações (somente leitura) podem rodar em paralelo.
- Operações que movem arquivos pedem confirmação e podem ser pré-visualizadas antes.
- Duplicatas vão para quarentena com manifesto CSV, nunca são excluídas.
- Cada execução recebe um ID curto, registrado no histórico e nas linhas de log (permite correlacionar suporte e auditoria).
- Os logs registram caminhos e contagens, não o conteúdo das células.
- O histórico local **não** é uma trilha de auditoria inviolável (qualquer pessoa com acesso à
  pasta de dados pode editá-lo).

## Limitações conhecidas desta versão

- Ler `.xls` (formato antigo) exige a biblioteca `xlrd` (já em `requirements.txt`).
- O CNPJ alfanumérico segue a regra de dígito verificador (módulo 11, letras = código ASCII − 48).
- Tabelas na tela mostram até 1.000 linhas; o export traz tudo.
- Alguns antivírus marcam executáveis do PyInstaller como suspeitos (falso positivo).

## Versionamento e release

O projeto usa Git com `main` estável, commits por tarefa e tags SemVer. O
checklist de commit/release está em [`docs/versioning.md`](docs/versioning.md).
A baseline atual é a tag `v0.1.0`.

## Roadmap (do documento de arquitetura)

- **Fase 1** — Histórico ampliado (filtros, exportação), serviços restantes.
- **Fase 2** — Renomeador de arquivos, conversor de arquivos.
- **Fase 3** — PDF, validador de planilhas, verificador e buscador de documentos.
- **Fase 4** — Conferidor de pagamentos e saldos, rateio, calculadoras, comparador de períodos.
- **Fase 5** — Monitor de pastas, agendador, OCR, detector de anomalias, fluxos encadeados.
- **Fase 6** — Instalador, atualizações, testes em máquinas sem Python.
