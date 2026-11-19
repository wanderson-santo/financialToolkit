"""Utilitários ainda não implementados (roadmap do catálogo)."""
from __future__ import annotations

from dataclasses import dataclass

from core.categories import (
    CATEGORY_AUDIT, CATEGORY_FILES, CATEGORY_FINANCE, CATEGORY_PRODUCTIVITY, CATEGORY_SHEETS,
)


@dataclass(frozen=True)
class PlannedModule:
    module_id: str
    name: str
    category: str
    description: str
    phase: int


PLANNED = [
    PlannedModule("file_renamer", "Renomeador inteligente de arquivos", CATEGORY_FILES,
                  "Renomeia em lote por empresa, CNPJ, competência e tipo documental; trata conflitos e duplicidades.", 2),
    PlannedModule("pdf_tools", "Manipulador de PDF", CATEGORY_FILES,
                  "Une, divide, reordena e extrai páginas; compacta; converte imagens em PDF; separa comprovantes.", 3),
    PlannedModule("file_converter", "Conversor de arquivos financeiros", CATEGORY_SHEETS,
                  "Converte XLSX, XLS e CSV com delimitador, codificação, decimais e datas configuráveis.", 2),
    PlannedModule("sheet_validator", "Validador de planilhas", CATEGORY_SHEETS,
                  "Verifica campos obrigatórios, datas, valores suspeitos e inconsistências; gera lista de pendências.", 3),
    PlannedModule("formula_auditor", "Auditor de fórmulas Excel", CATEGORY_SHEETS,
                  "Localiza fórmulas com erro, referências externas e valores fixos em áreas calculadas.", 5),
    PlannedModule("payment_checker", "Conferidor de pagamentos", CATEGORY_FINANCE,
                  "Cruza pagamentos com remessas e títulos por data, valor, favorecido e CNPJ; separa conciliados e pendentes.", 4),
    PlannedModule("interest_calculator", "Calculadora de juros", CATEGORY_FINANCE,
                  "Juros simples e compostos, multa, mora e encargos conforme os parâmetros informados.", 4),
    PlannedModule("monetary_update", "Calculadora de atualização monetária", CATEGORY_FINANCE,
                  "Atualiza valores por índice e período, com memória de cálculo e data-base registradas.", 4),
    PlannedModule("allocation", "Gerador de rateio", CATEGORY_FINANCE,
                  "Distribui despesas por empresa, unidade ou centro de custo e confere o total distribuído.", 4),
    PlannedModule("boleto_validator", "Conferidor de boletos", CATEGORY_FINANCE,
                  "Valida linha digitável e código de barras, incluindo dígitos verificadores.", 4),
    PlannedModule("duplicate_payments", "Identificador de pagamentos duplicados", CATEGORY_FINANCE,
                  "Procura pagamentos repetidos por valor, data, beneficiário e documento.", 4),
    PlannedModule("collection_files", "Gerador de arquivos de cobrança", CATEGORY_FINANCE,
                  "Organiza dados e exporta em layouts de cobrança configuráveis.", 4),
    PlannedModule("cash_flow", "Calculadora de fluxo de caixa", CATEGORY_FINANCE,
                  "Simula entradas, saídas, saldo projetado e cenários por período.", 4),
    PlannedModule("balance_checker", "Conferidor de saldos", CATEGORY_FINANCE,
                  "Compara saldos entre razão, balancete e extrato e destaca as diferenças.", 4),
    PlannedModule("clipboard", "Gerenciador de área de transferência", CATEGORY_PRODUCTIVITY,
                  "Histórico local de textos copiados, favoritos (CNPJs, códigos) e busca.", 5),
    PlannedModule("file_search", "Buscador inteligente de documentos", CATEGORY_PRODUCTIVITY,
                  "Pesquisa por nome, extensão, pasta e conteúdo; filtros por empresa e competência.", 3),
    PlannedModule("ocr_extractor", "Extrator de informações com OCR", CATEGORY_PRODUCTIVITY,
                  "Lê comprovantes e PDFs digitalizados e extrai CNPJ, valor, data e favorecido, com revisão humana.", 5),
    PlannedModule("task_scheduler", "Agendador de tarefas financeiras", CATEGORY_PRODUCTIVITY,
                  "Executa rotinas em horários definidos e processa arquivos automaticamente.", 5),
    PlannedModule("activity_log", "Log de atividades", CATEGORY_AUDIT,
                  "Registro completo de operações. Hoje já existe o Histórico básico; esta versão amplia filtros e exportação.", 1),
    PlannedModule("folder_monitor", "Monitor de pastas", CATEGORY_AUDIT,
                  "Identifica arquivos novos, alterados ou removidos e dispara rotinas configuradas.", 5),
    PlannedModule("document_checker", "Verificador de documentos", CATEGORY_AUDIT,
                  "Confere se os documentos esperados foram recebidos por empresa, período ou processo.", 3),
    PlannedModule("monthly_close", "Controle de fechamento mensal", CATEGORY_AUDIT,
                  "Checklist de atividades, responsáveis, status, prazos e pendências do fechamento.", 6),
    PlannedModule("evidence_generator", "Gerador de evidências", CATEGORY_AUDIT,
                  "Organiza comprovantes, relatórios e registros associados a uma execução ou processo.", 6),
    PlannedModule("period_comparator", "Comparador de períodos", CATEGORY_AUDIT,
                  "Compara movimentações e indicadores entre meses, trimestres ou outros intervalos.", 4),
    PlannedModule("anomaly_detector", "Detector de anomalias", CATEGORY_AUDIT,
                  "Sinaliza valores atípicos, duplicidades e comportamentos incomuns para análise.", 5),
]
