@echo off
setlocal

cd /d "%~dp0.."

pyinstaller --clean --noconfirm main.spec

endlocal
