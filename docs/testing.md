# Testes e cobertura

## Comando único

```bash
python -m pip install -r requirements-dev.txt
python scripts/run_tests.py
```

O script roda toda a suíte `unittest`, grava `.coverage` e imprime o relatório de
linhas com os trechos descobertos. Sai com código diferente de zero se algum teste
falhar ou se o `coverage` não estiver instalado.

Para rodar apenas os testes, sem cobertura:

```bash
python -m unittest discover -s tests -t .
```

No Windows, `run_tests.bat` roda apenas a suíte. Para cobertura, instale
`requirements-dev.txt` e execute `python scripts\run_tests.py` no ambiente ativado.

## Baseline

- Data da medição: 19/11/2026
- Python: 3.13.13
- `coverage`: 7.17.3
- Testes: **113 aprovados**
- Cobertura de linhas: **61,6%** (2.915 instruções, 1.118 sem cobertura)
- Configuração: `.coveragerc` (`source = app, core, modules`, sem os testes)

A interface Tkinter (`app/pages.py`, `app/widgets.py`, `app/main_window.py`) ainda
não tem testes automatizados; por isso aparece com 0% e puxa o total para baixo.
O núcleo e os módulos ficam acima de 77% na maioria dos arquivos.

Artefatos `.coverage` e `htmlcov/` não são versionados.

## Regressões dos P0

Cada defeito corrigido no bloco P0 tem teste automatizado que protege o
comportamento novo:

| Tarefa | Defeito protegido | Testes principais |
|---|---|---|
| FT-001 | Tolerância `0.01` interpretada como `1.0` | `ComparatorTests.test_tolerancia_formatos_inequivocos`, `test_tolerancia_ambigua_ou_invalida`, `test_tolerancia_0_01_nao_ignora_50_centavos` |
| FT-002 | `1.234` lido como `1,234` | `NormalizerTests.test_numeros`, `ComparatorTests.test_numeros_brasileiros`, `test_comparacao_inteiros_br` |
| FT-003 | Inicialização quebrada por banco corrompido | `HistoryTests.test_recupera_banco_corrompido`, `test_erro_de_pasta_nao_e_tratado_como_corrupcao` |
| FT-004 | Fechamento durante operação sem registro | `ShutdownTests.test_cancelamento_conclui_antes_do_timeout`, `test_timeout_interrompe_e_avisa`, `test_multiplas_operacoes_so_interrompe_pendentes` |
| FT-005 | Injeção de fórmulas em CSV/XLSX | `ExportSecurityTests.test_csv_neutraliza_formulas`, `test_xlsx_neutraliza_formulas`, `test_cabecalhos_tambem_sao_protegidos` |
| FT-006 | Cabeçalhos duplicados perdendo colunas | `HeaderDedupTests.*`, `CleanerTests.test_limpeza_com_cabecalhos_repetidos`, `ComparatorTests.test_comparacao_com_cabecalhos_repetidos` |
| FT-007 | Codificação/separador detectados em amostra parcial | `CsvDetectionTests.*` (UTF-8/BOM, cp1252, latin-1, separadores, aspas) |
| FT-008 | Duplicatas movidas sem manifesto | `DuplicateTests.test_manifesto_existe_antes_do_primeiro_move`, `test_falha_ao_gravar_manifesto_aborta_antes_de_mover`, `test_cancelamento_apos_primeiro_move_preserva_manifesto` |

Tarefas P1 já concluídas também têm cobertura de regressão:

| Tarefa | Testes principais |
|---|---|
| FT-009 | `StatusTests.*`, `HistoryTests.test_finish_registra_cancelamento_e_interrupcao`, `test_stats_reconhece_todos_os_status` |
| FT-010 | `ExportSecurityTests.test_abas_truncadas_nao_se_sobrescrevem`, `test_abas_com_mesmo_nome_ignorando_maiusculas`, `test_nome_vazio_e_caracteres_invalidos` |
| FT-011 | `RegistryTests.*` |
| FT-012 | `CoordinatorTests.*` |
| FT-013 | `ExecutionContextTests.*`, `HistoryTests.test_start_grava_run_id` |
| FT-016 | `MigrationTests.*` |
| FT-017 | `HistoryDetailsTests.*` (zero/poucos/muitos detalhes, arquivo externo, falha de escrita, ida e volta e exportação) |
| FT-018 | `MaintenanceTests.*` (WAL, uso de índices, retenção por data/quantidade, backup e restauração) |

## Atualizando a baseline

1. Rode `python scripts/run_tests.py`.
2. Atualize a data, a contagem de testes e o percentual neste documento quando a
   mudança for intencional.
3. Cobertura não deve cair sem justificativa; novos módulos e correções devem
   trazer testes junto.
4. Antes de um release, valide em um clone limpo (ver `docs/versioning.md`).
