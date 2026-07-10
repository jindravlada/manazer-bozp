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
  --icon manager_bozp.ico ^
  --version-file version_info.txt ^
  --name ManazerBOZP ^
  main.py

if errorlevel 1 (
    echo.
    echo BUILD EXE SELHAL.
    pause
    exit /b 1
)

"C:\Users\Test\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss

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