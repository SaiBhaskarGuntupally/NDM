# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['ndm_oncall']
hiddenimports += collect_submodules('ndm_oncall')


a = Analysis(
    ['C:\\Users\\vidhy\\OneDrive\\Desktop\\Exp_2\\ndm_oncall\\ndm_backend.py'],
    pathex=['C:\\Users\\vidhy\\OneDrive\\Desktop\\Exp_2'],
    binaries=[],
    datas=[('C:\\Users\\vidhy\\OneDrive\\Desktop\\Exp_2\\ndm_oncall\\templates', 'templates'), ('C:\\Users\\vidhy\\OneDrive\\Desktop\\Exp_2\\ndm_oncall\\static', 'static')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ndm_backend',
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
)
