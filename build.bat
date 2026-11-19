@echo off
cd /d "%~dp0"

if not exist .venv (
    echo Criando ambiente virtual...
    py -m venv .venv
    if errorlevel 1 goto erro
)

call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-build.txt
if errorlevel 1 goto erro

echo.
echo Rodando os testes...
python -m unittest discover -s tests -t .
if errorlevel 1 goto erro

pyinstaller --noconfirm --clean finance_toolkit.spec
if errorlevel 1 goto erro

echo.
echo Pronto: dist\FinanceToolkit.exe
pause
exit /b 0

:erro
echo.
echo Ocorreu um erro. Veja as mensagens acima.
pause
exit /b 1
