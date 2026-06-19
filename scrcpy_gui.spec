# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec fayli — scrcpy_gui.py ni bitta .exe ga aylantiradi.

a = Analysis(
    ['scrcpy_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('app_icon.ico', '.')],
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
    icon='app_icon.ico',
)
