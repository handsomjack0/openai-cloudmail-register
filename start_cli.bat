@echo off
setlocal
cd /d "%~dp0"
echo.
echo OpenAI CloudMail Register Runner
echo.
echo 1. Doctor
echo 2. Run smoke preset
echo 3. Run stable preset
echo 4. Resume
echo 5. Retry failed
echo 6. Status
echo 7. Export txt
echo.
set /p choice=Choose an action:
if "%choice%"=="1" python register.py doctor --config config.json
if "%choice%"=="2" python register.py run --config config.json --preset smoke
if "%choice%"=="3" python register.py run --config config.json --preset stable
if "%choice%"=="4" python register.py resume --config config.json
if "%choice%"=="5" python register.py retry-failed --config config.json
if "%choice%"=="6" python register.py status --config config.json
if "%choice%"=="7" python register.py export --config config.json --format txt
pause
