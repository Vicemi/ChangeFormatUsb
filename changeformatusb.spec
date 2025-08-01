# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Configuración de análisis principal
a = Analysis(
    ['main.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        ('resources/translations/*.json', 'resources/translations'),
        
        # Incluir otros recursos
        ('resources/*.ico', 'resources'),
        ('resources/*.png', 'resources'),
        
        # Incluir módulos
        ('core/*.py', 'core'),
        ('utils/*.py', 'utils'),
    ],
    hiddenimports=[
        'win32timezone',
        'win32com',
        'pkg_resources.py2_warn',
        'psutil._psutil_windows',
        'pywintypes',
        'pythoncom',
        'win32api',
        'win32file',
        'win32con',
        'ctypes',
        'ctypes.wintypes',
    ] + collect_submodules('PyQt5'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Configuración del PYZ
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Configuración del ejecutable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='ChangeFormatUSB',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon=os.path.join('resources', 'icon.ico'),
    onefile=True
)