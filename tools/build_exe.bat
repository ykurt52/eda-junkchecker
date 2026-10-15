@echo off
rem Build the single-file JunkChecker.exe with PyInstaller (pip install pyinstaller).
rem GitHub Actions runs this for every v* tag and attaches dist\JunkChecker.exe to the release.
cd /d "%~dp0.."
python -m PyInstaller --noconfirm --onefile --windowed --name JunkChecker ^
  --icon "junkchecker\assets\icon.ico" ^
  --add-data "junkchecker\default_rules.json;junkchecker" ^
  --add-data "junkchecker\assets;junkchecker\assets" ^
  --exclude-module PIL --exclude-module numpy ^
  JunkChecker.pyw
if errorlevel 1 exit /b 1
echo.
echo Built: %cd%\dist\JunkChecker.exe
