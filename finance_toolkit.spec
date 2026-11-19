# -*- mode: python ; coding: utf-8 -*-
# Uso: pyinstaller --noconfirm --clean finance_toolkit.spec
# Resultado: dist/FinanceToolkit.exe

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],  # se criar resources/ (ícones, temas), use: datas=[('resources', 'resources')]
    # Os módulos são importados de forma explícita em modules/__init__.py,
    # então o PyInstaller os detecta sozinho. Estes dois são carregados pelo pandas.
    hiddenimports=['openpyxl', 'xlrd'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Bibliotecas pesadas que o app não usa (deixam o .exe menor)
    excludes=['matplotlib', 'scipy', 'IPython', 'jupyter', 'pytest', 'numba', 'PIL'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FinanceToolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX costuma gerar falso positivo em antivírus
    runtime_tmpdir=None,
    console=False,           # app de janela, sem terminal preto
    disable_windowed_traceback=False,
    icon=None,               # para ícone: icon='resources/icons/app.ico'
)
