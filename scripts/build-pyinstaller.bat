@echo off
setlocal

cd /d "%~dp0.."

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" -X utf8 scripts\build_pyinstaller.py %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [build] 构建失败，exit code=%EXIT_CODE%
)

endlocal & exit /b %EXIT_CODE%
