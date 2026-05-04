@echo off
setlocal

set CONFIG=config/accounts.yaml
set HTML=report.html

if not "%~1"=="" set CONFIG=%~1
if not "%~2"=="" set HTML=%~2

py -V >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Run setup.bat first.
  exit /b 1
)

echo Running library tracker...
py -m library_tracker.cli --config "%CONFIG%" --html "%HTML%"
if errorlevel 1 goto :error

if exist "%HTML%" (
  echo Opening HTML report: %HTML%
  start "" "%HTML%"
)

goto :eof

:error
echo Failed.
exit /b 1
