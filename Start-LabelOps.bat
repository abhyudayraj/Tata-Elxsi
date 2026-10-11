@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py"
  set "PYARGS=-3"
  goto check_python
)
where python >nul 2>nul
if %errorlevel%==0 (
  set "PY=python"
  set "PYARGS="
  goto check_python
)
echo Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/ and enable Add Python to PATH.
goto failed

:check_python
%PY% %PYARGS% --version
if errorlevel 1 goto failed
%PY% %PYARGS% -c "import PIL,cv2,requests" >nul 2>nul
if errorlevel 1 goto install_deps
goto launch_server

:install_deps
echo Installing the required packages, including OpenCV. This may take a few minutes...
%PY% %PYARGS% -m pip install -r requirements.txt
if errorlevel 1 goto failed

:launch_server
echo Starting the LabelOps server window...
start "LabelOps server" cmd /k "%PY% %PYARGS% -u server.py"
echo Waiting for the local API to become ready...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ready=$false; for($i=0;$i -lt 30;$i++){try{$r=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 1; if($r.ok){$ready=$true;break}}catch{}; Start-Sleep -Milliseconds 500}; if($ready){Start-Process 'http://127.0.0.1:8765'; exit 0}else{Write-Host 'LabelOps did not respond. Check the LabelOps server window for its startup error.' -ForegroundColor Red; exit 1}"
if errorlevel 1 goto failed
echo LabelOps is running. Keep the LabelOps server window open.
goto done

:failed
echo.
echo Startup did not complete. Read the error above and check that Python 3.10+ is installed.
pause
exit /b 1

:done
exit /b 0
