@echo off
setlocal enabledelayedexpansion

set PROJECT_DIR=%~dp0
set PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe

:: Cargar variables desde .env (ignorar comentarios y lineas vacias)
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /v "^#" "%PROJECT_DIR%.env"`) do (
    if not "%%A"=="" set "%%A=%%B"
)

:: Log con fecha YYYYMMDD
set LOG_DIR=%PROJECT_DIR%logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set LOG_FILE=%LOG_DIR%\snapshot_%date:~-4,4%%date:~-7,2%%date:~-10,2%.log

:: Ejecucion
cd /d "%PROJECT_DIR%"
echo [%date% %time%] Iniciando snapshot >> "%LOG_FILE%"

"%PYTHON%" redshift_to_s3_snapshot.py >> "%LOG_FILE%" 2>&1

if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] ERROR: el snapshot termino con errores. Ver log. >> "%LOG_FILE%"
    exit /b 1
)

echo [%date% %time%] Snapshot completado OK >> "%LOG_FILE%"
exit /b 0
