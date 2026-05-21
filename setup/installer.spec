# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the ChangeFormatUSB self-contained installer.

Build order:
  1. Build main app  -> dist/ChangeFormatUSB.exe
  2. Build installer -> dist/ChangeFormatUSB-Setup-2.0.exe   (this spec)

The installer embeds dist/ChangeFormatUSB.exe as a payload resource.
"""

import os

# Resolve from repo root (one level above setup/)
ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), ".."))

block_cipher = None

a = Analysis(
    [os.path.join(ROOT, "setup", "installer.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # ── payload: the main application ──────────────────────────────────
        (os.path.join(ROOT, "dist", "ChangeFormatUSB.exe"), "dist"),

        # ── SVG icons (same set used by the installer UI) ──────────────────
        (os.path.join(ROOT, "resources", "icons", "*.svg"), "resources/icons"),

        # ── window icon ────────────────────────────────────────────────────
        (os.path.join(ROOT, "resources", "icon.ico"), "resources"),
    ],
    hiddenimports=[
        "win32com",
        "win32com.client",
        "win32timezone",
        "pywintypes",
        "pythoncom",
        "PyQt5.QtSvg",
        "PyQt5.QtXml",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
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
    name="ChangeFormatUSB-Setup-2.0",
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
    icon=os.path.join(ROOT, "resources", "icon.ico"),
    onefile=True,
)
