@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m pip install -r requirements.txt
  if errorlevel 1 goto failed
  goto done
)
where python >nul 2>nul
if %errorlevel%==0 (
  python -m pip install -r requirements.txt
  if errorlevel 1 goto failed
  goto done
)
echo Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/ and enable Add Python to PATH.
goto failed
:done
echo.
echo Setup complete. Double-click Start-LabelOps.bat to run the app.
pause
exit /b 0
:failed
echo.
echo Setup failed. Check the message above, then try again.
pause
exit /b 1
