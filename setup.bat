@echo off
setlocal

echo Checking for Python...
py -V >nul 2>nul
if errorlevel 1 goto install_python

goto install_requirements

:install_python
echo Python launcher not found.
echo Attempting to install Python via winget...
where winget >nul 2>nul
if errorlevel 1 goto no_winget
winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto install_failed

echo Refreshing environment...
set "PATH=%LocalAppData%\Programs\Python\Launcher;%LocalAppData%\Programs\Python\Python311;%PATH%"
py -V >nul 2>nul
if errorlevel 1 goto install_failed

goto install_requirements

:no_winget
echo winget is not available.
echo Please install Python 3 manually from https://www.python.org/downloads/windows/
exit /b 1

:install_failed
echo Python installation failed. Please install Python 3 manually.
exit /b 1

:install_requirements
echo Installing/updating dependencies...
py -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo Setup complete.
