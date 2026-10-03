@echo off
setlocal

cd /d "%~dp0"

call .venv\Scripts\activate

echo.
echo ==========================================
echo  Manažer BOZP - Windows build
echo ==========================================
echo.

python generate_version_info.py
python generate_installer_iss.py

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
rmdir /s /q installer 2>nul
del ManazerBOZP.spec 2>nul

pyinstaller --clean --onedir --windowed ^
  --icon core\resources\manager_bozp.ico ^
  --version-file version_info.txt ^
  --name ManazerBOZP ^
  --add-data "moduly;moduly" ^
  --add-data "core;core" ^
  --add-data "ciselniky;ciselniky" ^
  --add-data "zdroje;zdroje" ^
  main.py

if errorlevel 1 (
    echo.
    echo BUILD EXE SELHAL.
    pause
    exit /b 1
)

set "ISCC="
where ISCC.exe >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%I in ('where ISCC.exe') do (
        if not defined ISCC set "ISCC=%%I"
    )
)
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo.
    echo Inno Setup 6 nebyl nalezen. Nainstalujte Inno Setup 6 nebo zpřístupněte ISCC.exe přes PATH.
    pause
    exit /b 1
)

"%ISCC%" installer.iss

if errorlevel 1 (
    echo.
    echo BUILD INSTALATORU SELHAL.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  HOTOVO
echo ==========================================
echo.
echo EXE:
echo dist\ManazerBOZP\ManazerBOZP.exe
echo.
echo INSTALATOR:
echo installer\
for /f "delims=" %%F in ('python -c "from core.version import installer_output_basename; print(installer_output_basename())"') do echo %%F.exe
echo.

pause