@echo off
setlocal
cd /d "%~dp0"
python register.py --config config.json
pause
