@echo off
setlocal EnableDelayedExpansion
title ChangeFormatUSB — Build

echo.
echo  ============================================
echo   ChangeFormatUSB  Build Script
echo  ============================================
echo.

:: ── 1. Dependencias ───────────────────────────────────────────────────────
echo  [1/3]  Instalando dependencias de Python...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Fallo la instalacion de dependencias.
    echo  Asegurate de tener Python 3.8+ y pip correctamente configurados.
    echo.
    pause & exit /b 1
)
echo         OK

:: ── 2. Compilar ejecutable ────────────────────────────────────────────────
echo  [2/3]  Compilando ejecutable con PyInstaller...
pyinstaller changeformatusb.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: PyInstaller fallo. Revisa los mensajes anteriores.
    echo.
    pause & exit /b 1
)
echo         OK  ->  dist\ChangeFormatUSB.exe

:: ── 3. Crear instalador (requiere Inno Setup 6) ───────────────────────────
echo  [3/3]  Creando instalador...

set ISCC=
for %%P in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) do (
    if exist %%P (
        set ISCC=%%P
        goto :found_inno
    )
)

:not_found_inno
echo         AVISO: Inno Setup 6 no encontrado.
echo         Descargalo desde https://jrsoftware.org/isinfo.php
echo         y vuelve a ejecutar este script, o crea el instalador manualmente con:
echo              ISCC.exe installer.iss
goto :done

:found_inno
if not exist "dist\installer" mkdir "dist\installer"
%ISCC% installer.iss
if %errorlevel% neq 0 (
    echo.
    echo  AVISO: El instalador no se pudo crear (ver mensajes anteriores).
    goto :done
)
echo         OK  ->  dist\installer\ChangeFormatUSB-Setup-2.0.exe

:done
echo.
echo  ============================================
echo   Build finalizado
echo  ============================================
echo.
echo   Ejecutable:   dist\ChangeFormatUSB.exe
echo   Instalador:   dist\installer\ChangeFormatUSB-Setup-2.0.exe  (si aplica)
echo.
pause
