# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec fayli — scrcpy_gui.py ni bitta .exe ga aylantiradi.

import os
# Ikon fayli mavjud bo'lsa ishlatamiz, bo'lmasa build baribir davom etadi.
_icon = 'app_icon.ico' if os.path.isfile('app_icon.ico') else None

a = Analysis(
    ['scrcpy_gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter', 'socket', 'json'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ScrcpyConnect',
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
    icon=_icon,
)
