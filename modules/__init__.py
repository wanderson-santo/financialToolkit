"""Registro explícito dos módulos disponíveis.

A lista é explícita (e não por varredura de pastas) para que o PyInstaller
detecte todos os módulos ao gerar o .exe.
"""


def available_modules():
    from modules.files.company_folders import CompanyFolders
    from modules.files.duplicate_finder import DuplicateFinder
    from modules.files.folder_organizer import FolderOrganizer
    from modules.finance.cnpj_validator import CnpjValidator
    from modules.spreadsheets.cleaner import SheetCleaner
    from modules.spreadsheets.comparator import SheetComparator

    return [
        FolderOrganizer(),
        DuplicateFinder(),
        CompanyFolders(),
        SheetCleaner(),
        SheetComparator(),
        CnpjValidator(),
    ]
