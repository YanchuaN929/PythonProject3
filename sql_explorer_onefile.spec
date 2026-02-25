# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['scripts\\db_tools\\sql_explorer_main.py'],
    pathex=['scripts\\db_tools'],
    binaries=[],
    datas=[('example\\template_spec.json', 'example'), ('excel_bin\\姓名角色表.xlsx', 'excel_bin'), ('excel_bin\\姓名角色表-电力工程研究设计所.xlsx', 'excel_bin'), ('excel_bin\\姓名角色表——核工程所通信专业+设备专业.xlsx', 'excel_bin')],
    hiddenimports=[],
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
    name='sql_explorer_onefile',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
