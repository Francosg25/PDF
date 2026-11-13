@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
    py -3 visor_pdf_3000_pro.py
) else (
    python visor_pdf_3000_pro.py
)
if errorlevel 1 (
    echo.
    echo El programa no pudo abrirse. Asegura instalar requirements.txt.
    pause
)
