@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
if not exist output mkdir output

set "LIMIT_ARG="
if defined RICS_TEST_LIMIT set "LIMIT_ARG=--limit %RICS_TEST_LIMIT%"

:menu
cls
echo ===============================
echo          MENU RICS
echo ===============================
echo 1 - Pesquisar Rics
echo 2 - Baixar Rics
echo 3 - Sair
echo.
set /p opcao=Escolha uma opcao: 

if "%opcao%"=="1" (
    echo.
    python rics_scraper.py search %LIMIT_ARG%
    echo.
    pause
    goto menu
)

if "%opcao%"=="2" (
    echo.
    python rics_scraper.py download %LIMIT_ARG%
    echo.
    pause
    goto menu
)

if "%opcao%"=="3" (
    exit /b 0
)

echo Opcao invalida.
timeout /t 2 >nul
goto menu
