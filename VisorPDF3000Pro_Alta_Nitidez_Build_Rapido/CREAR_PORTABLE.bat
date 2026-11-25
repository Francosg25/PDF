@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
title VisorPDF3000Pro - Build rapido
py -3.13 -c "import PySide6, fitz, pytesseract, PIL, PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias faltantes...
    py -3.13 -m pip install -r requirements.txt
    if errorlevel 1 goto error
)
echo Generando portable...
py -3.13 -m PyInstaller --noconfirm --onedir --windowed --name VisorPDF3000Pro ^
  --exclude-module torch --exclude-module tensorflow --exclude-module pandas ^
  --exclude-module scipy --exclude-module matplotlib --exclude-module pytest ^
  --exclude-module pyarrow --exclude-module openpyxl visor_pdf_3000_pro.py
if errorlevel 1 goto error
if not exist "dist\VisorPDF3000Pro\Data" mkdir "dist\VisorPDF3000Pro\Data"
echo.
echo LISTO: dist\VisorPDF3000Pro\VisorPDF3000Pro.exe
echo Comparte toda la carpeta VisorPDF3000Pro, no solo el EXE.
pause
exit /b 0
:error
echo Error. Verifica Python 3.13 y los mensajes anteriores.
pause
exit /b 1
