@echo off
rem Build a single-file JunkChecker.exe with PyInstaller (pip install pyinstaller).
cd /d "%~dp0.."
python -m PyInstaller --noconfirm --onefile --windowed --name JunkChecker ^
  --add-data "junkchecker\default_rules.json;junkchecker" ^
  JunkChecker.pyw
if errorlevel 1 exit /b 1
echo.
echo Built: %cd%\dist\JunkChecker.exe
