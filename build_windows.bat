@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo.
    echo Virtualni prostredi .venv zatim neni. Vytvarim ho Pythonem 3.14.
    call :create_venv
    if errorlevel 1 (
        echo.
        echo Instalator nebyl vytvoren.
        pause
        exit /b 1
    )
)

echo.
echo ==========================================
echo  Manažer BOZP - Windows build
echo ==========================================
echo.
echo Instaluji zavislosti do .venv
"%VENV_PY%" -m pip install --disable-pip-version-check -r requirements.txt -r requirements-build.txt
if errorlevel 1 (
    echo.
    echo Instalace zavislosti selhala. Instalator nebyl vytvoren.
    pause
    exit /b 1
)

"%VENV_PY%" -c "import PySide6, PyInstaller"
if errorlevel 1 (
    echo.
    echo Ve virtualnim prostredi chybi PySide6 nebo PyInstaller. Instalator nebyl vytvoren.
    pause
    exit /b 1
)

"%VENV_PY%" generate_version_info.py
if errorlevel 1 (
    echo.
    echo Generovani verze selhalo. Instalator nebyl vytvoren.
    pause
    exit /b 1
)
"%VENV_PY%" generate_installer_iss.py
if errorlevel 1 (
    echo.
    echo Generovani instalatoru selhalo. Instalator nebyl vytvoren.
    pause
    exit /b 1
)

if exist build rmdir /s /q build
mkdir build
"%VENV_PY%" -m core.packaging.windows_qt_bundle --argfile build\qt-binaries.args
if errorlevel 1 (
    echo.
    echo CHYBI KNIHOVNY QT PRO CISTY WINDOWS. Instalator nebyl vytvoren.
    pause
    exit /b 1
)

rmdir /s /q dist 2>nul
rmdir /s /q installer 2>nul
del ManazerBOZP.spec 2>nul

"%VENV_PY%" -m PyInstaller --clean --onedir --windowed ^
  --icon core\resources\manager_bozp.ico ^
  --version-file version_info.txt ^
  --name ManazerBOZP ^
  --runtime-hook packaging\pyi_rth_windows_qt_dlls.py ^
  --add-data "moduly;moduly" ^
  --add-data "core;core" ^
  --add-data "ciselniky;ciselniky" ^
  --add-data "zdroje;zdroje" @build\qt-binaries.args ^
  main.py

if errorlevel 1 (
    echo.
    echo BUILD EXE SELHAL. Instalator nebyl vytvoren.
    pause
    exit /b 1
)

"%VENV_PY%" -m core.packaging.windows_qt_bundle --check dist\ManazerBOZP
if errorlevel 1 (
    echo.
    echo BALICEK NEOBSAHUJE KNIHOVNY QT. Instalator nebyl vytvoren.
    if exist installer rmdir /s /q installer
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
    echo Instalator nebyl vytvoren.
    pause
    exit /b 1
)

"%ISCC%" installer.iss

if errorlevel 1 (
    echo.
    echo BUILD INSTALATORU SELHAL.
    if exist installer rmdir /s /q installer
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
for /f "delims=" %%F in ('"%VENV_PY%" -c "from core.version import installer_output_basename; print(installer_output_basename())"') do echo %%F.exe
echo.

pause
exit /b 0

:create_venv
set "BASE_KIND="
where py >nul 2>&1
if not errorlevel 1 (
    py -3.14 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 14) and sys.maxsize > 2 ** 32 else 1)" >nul 2>&1
    if not errorlevel 1 set "BASE_KIND=py314"
)
if not defined BASE_KIND (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 14) and sys.maxsize > 2 ** 32 else 1)" >nul 2>&1
        if not errorlevel 1 set "BASE_KIND=python"
    )
)
if not defined BASE_KIND (
    echo.
    echo Nenalezen 64bitovy Python 3.14.
    echo Nainstalujte ho. Py launcher nechte zapnuty, nebo pridejte python.exe do PATH.
    exit /b 1
)
if exist "%~dp0.venv" rmdir /s /q "%~dp0.venv"
if "%BASE_KIND%"=="py314" (
    py -3.14 -m venv "%~dp0.venv"
) else (
    python -m venv "%~dp0.venv"
)
if errorlevel 1 (
    echo.
    echo Virtualni prostredi .venv se nepodarilo vytvorit.
    exit /b 1
)
if not exist "%VENV_PY%" (
    echo.
    echo Virtualni prostredi .venv neobsahuje python.exe.
    exit /b 1
)
exit /b 0
