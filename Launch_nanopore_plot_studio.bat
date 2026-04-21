@echo off
setlocal

set "PYTHON_EXE=C:\Users\Odile\AppData\Local\Programs\Python\Python313\python.exe"
set "SCRIPT_PATH=%~dp0nanopore_plot__studio_v11.py"

if not exist "%PYTHON_EXE%" (
    echo Python not found:
    echo %PYTHON_EXE%
    pause
    exit /b 1
)

if not exist "%SCRIPT_PATH%" (
    echo Script not found:
    echo %SCRIPT_PATH%
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%SCRIPT_PATH%"
pause
