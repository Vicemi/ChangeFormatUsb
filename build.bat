@echo off
setlocal EnableDelayedExpansion
title ChangeFormatUSB - Build

echo.
echo  ============================================
echo   ChangeFormatUSB  Build Script
echo  ============================================
echo.

:: Detect PyInstaller: prefer venv if it exists
set PYINST=pyinstaller
if exist ".venv\Scripts\pyinstaller.exe" set PYINST=.venv\Scripts\pyinstaller.exe

:: Detect pip: prefer venv if it exists
set PIP=pip
if exist ".venv\Scripts\pip.exe" set PIP=.venv\Scripts\pip.exe

:: ── 1. Dependencies ───────────────────────────────────────────────────────────
echo  [1/3]  Installing dependencies...
%PIP% install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Dependency installation failed.
    echo  Make sure Python 3.8+ and pip are configured.
    echo.
    pause & exit /b 1
)
echo         OK

:: ── 2. Build main application ─────────────────────────────────────────────────
echo  [2/3]  Building main application...
%PYINST% changeformatusb.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: PyInstaller failed. Check the output above.
    echo.
    pause & exit /b 1
)
echo         OK: dist\ChangeFormatUSB.exe

:: ── 3. Build self-contained installer ────────────────────────────────────────
echo  [3/3]  Building installer...

if not exist "dist\ChangeFormatUSB.exe" (
    echo.
    echo  ERROR: dist\ChangeFormatUSB.exe not found.
    echo  The main application must be built before the installer.
    echo.
    pause & exit /b 1
)

%PYINST% setup\installer.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Installer build failed. Check the output above.
    echo.
    pause & exit /b 1
)
echo         OK: dist\ChangeFormatUSB-Setup-2.0.exe

:done
echo.
echo  ============================================
echo   Build complete
echo  ============================================
echo.
echo   Application : dist\ChangeFormatUSB.exe
echo   Installer   : dist\ChangeFormatUSB-Setup-2.0.exe
echo.
pause
