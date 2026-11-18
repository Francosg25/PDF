@echo off
chcp 65001 >nul
title Crear VisorPDF3000 Pro portable
echo ==========================================
echo   CREAR VISORPDF3000 PRO PORTABLE
echo ==========================================
py -3 -m pip install --upgrade pip
if errorlevel 1 goto error
py -3 -m pip install -r requirements.txt
if errorlevel 1 goto error
py -3 -m PyInstaller --noconfirm --clean --windowed --onedir --name VisorPDF3000Pro ^
  --collect-all fitz --collect-all PySide6 visor_pdf_3000_pro.py
if errorlevel 1 goto error
if not exist "dist\VisorPDF3000Pro\Data" mkdir "dist\VisorPDF3000Pro\Data"
echo.
echo LISTO. Tu programa esta en:
echo dist\VisorPDF3000Pro\VisorPDF3000Pro.exe
echo Copia TODA la carpeta VisorPDF3000Pro a una USB si lo deseas.
pause
exit /b 0
:error
echo.
echo Hubo un error. Revisa que Python 3 este instalado y tenga conexion a internet.
pause
exit /b 1
