# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        # Translations
        ('resources/translations/*.json', 'resources/translations'),
        # Icons (original .ico and PNGs)
        ('resources/*.ico',               'resources'),
        ('resources/*.png',               'resources'),
        # SVG icon set
        ('resources/icons/*.svg',         'resources/icons'),
        # Source modules (needed when frozen)
        ('core/*.py',                     'core'),
        ('ui/*.py',                       'ui'),
        ('utils/*.py',                    'utils'),
    ],
    hiddenimports=[
        'win32timezone',
        'win32com',
        'win32com.client',
        'pkg_resources.py2_warn',
        'psutil._psutil_windows',
        'pywintypes',
        'pythoncom',
        'win32api',
        'win32file',
        'win32con',
        'wmi',
        'ctypes',
        'ctypes.wintypes',
        'PyQt5.QtSvg',
        'PyQt5.QtXml',
    ] + collect_submodules('PyQt5'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    version_file=None,
    onefile=True,
)
