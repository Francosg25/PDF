@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Crear VisorPDF3000 Pro ligero

echo ==============================================
echo   CREAR VISORPDF3000 PRO - VERSION LIGERA
echo ==============================================
echo.

REM Compatible con Python instalado por IT: NO crea entorno virtual.
REM El directorio de trabajo se coloca fuera de OneDrive para acelerar.
where py >nul 2>&1
if %errorlevel%==0 (
    set "PY_CMD=py -3"
) else (
    where python >nul 2>&1
    if errorlevel 1 goto python_error
    set "PY_CMD=python"
)

%PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto error

set "WORKDIR=%TEMP%\VisorPDF3000Pro_compilacion"
if not exist "%WORKDIR%" mkdir "%WORKDIR%"

REM Respalda SIEMPRE Data antes de regenerar dist. Evita perder favoritos,
REM catalogo SQLite y ruta de Tesseract entre compilaciones.
set "DATA_BACKUP=%CD%\Data_Respaldo_Compilacion"
if exist "dist\VisorPDF3000Pro\Data" (
    echo Guardando catalogo anterior antes de reemplazar el ejecutable...
    robocopy "dist\VisorPDF3000Pro\Data" "%DATA_BACKUP%" /E /R:1 /W:1 >nul
    if errorlevel 8 goto backup_error
)

REM La carpeta dist anterior puede incluir PyTorch (cientos de MB).
REM Eliminarla es seguro: es salida GENERADA, NO el codigo fuente.
if exist "dist\VisorPDF3000Pro" (
    echo Eliminando version compilada anterior...
    rmdir /s /q "dist\VisorPDF3000Pro"
    if exist "dist\VisorPDF3000Pro" goto locked
)

echo.
echo Compilando solo QtCore, QtGui, QtWidgets y PyMuPDF...
%PY_CMD% -m PyInstaller ^
    --noconfirm --windowed --onedir ^
    --name VisorPDF3000Pro ^
    --workpath "%WORKDIR%\build" ^
    --specpath "%WORKDIR%" ^
    --distpath "%CD%\dist" ^
    --exclude-module pandas ^
    --exclude-module numpy ^
    --exclude-module scipy ^
    --exclude-module torch ^
    --exclude-module tensorflow ^
    --exclude-module matplotlib ^
    --exclude-module pyarrow ^
    --exclude-module sklearn ^
    --exclude-module sympy ^
    --exclude-module PIL ^
    --exclude-module pytesseract ^
    --exclude-module PySide6.QtQml ^
    --exclude-module PySide6.QtQuick ^
    --exclude-module PySide6.QtQuickWidgets ^
    --exclude-module PySide6.QtWebEngineCore ^
    --exclude-module PySide6.QtWebEngineWidgets ^
    --exclude-module PySide6.QtWebEngineQuick ^
    --exclude-module PySide6.Qt3DCore ^
    --exclude-module PySide6.Qt3DRender ^
    visor_pdf_3000_pro.py
if errorlevel 1 goto error

if not exist "dist\VisorPDF3000Pro\VisorPDF3000Pro.exe" goto error
if not exist "dist\VisorPDF3000Pro\Data" mkdir "dist\VisorPDF3000Pro\Data"
REM Copia datos locales y luego restaura el ultimo catalogo del EXE anterior.
if exist "Data" (
    robocopy "Data" "dist\VisorPDF3000Pro\Data" /E /R:1 /W:1 >nul
    if errorlevel 8 goto backup_error
)
if exist "%DATA_BACKUP%" (
    robocopy "%DATA_BACKUP%" "dist\VisorPDF3000Pro\Data" /E /R:1 /W:1 >nul
    if errorlevel 8 goto backup_error
)
if exist "dist\VisorPDF3000Pro\_internal\torch\lib\torch_cpu.dll" goto too_heavy

echo.
echo ==============================================
echo   COMPILACION COMPLETADA
echo ==============================================
echo Inicia: dist\VisorPDF3000Pro\VisorPDF3000Pro.exe
echo Copia TODA esa carpeta para usarla en otra PC.
echo Nota: Tesseract OCR se instala por separado.
pause
exit /b 0

:backup_error
echo.
echo ERROR: No se pudieron copiar los datos del catalogo.
echo Cierra el visor, confirma permisos y vuelve a intentar.
echo El respaldo anterior permanece en Data_Respaldo_Compilacion.
pause
exit /b 1

:too_heavy
echo.
echo ERROR: Se empaqueto torch_cpu.dll, algo que no deberia suceder.
echo Comparte el registro antes de distribuir esta version.
pause
exit /b 1

:locked
echo.
echo ERROR: No se pudo borrar dist\VisorPDF3000Pro.
echo Cierra el visor y pausa la sincronizacion de OneDrive, luego reintenta.
pause
exit /b 1

:python_error
echo.
echo ERROR: No se encontro Python ni el lanzador py.
pause
exit /b 1

:error
echo.
echo ERROR DE COMPILACION. Comparte las ultimas lineas de la consola.
pause
exit /b 1
