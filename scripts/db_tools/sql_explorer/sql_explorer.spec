# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None

repo_root = Path.cwd()
db_tools_dir = repo_root / 'scripts' / 'db_tools'
entry_script = db_tools_dir / 'sql_explorer_main.py'

a = Analysis(
    [str(entry_script)],
    pathex=[str(repo_root), str(db_tools_dir)],
    binaries=[],
    datas=[
        (str(repo_root / 'example' / 'template_spec.json'), 'example'),
        (str(repo_root / 'example' / '1818按项目导出IDI手册2026-01-28-15_11_50.xlsx'), 'example'),
        (str(repo_root / 'example' / '内部接口信息单报表181820260128.xlsx'), 'example'),
        (str(repo_root / 'example' / '外部接口ICM报表181820260128.xlsx'), 'example'),
        (str(repo_root / 'example' / '外部接口单报表181820260128.xlsx'), 'example'),
        (str(repo_root / 'example' / '收发文清单1818.xlsx'), 'example'),
        (str(repo_root / 'excel_bin' / '姓名角色表.xlsx'), 'excel_bin'),
        (str(repo_root / 'excel_bin' / '姓名角色表-电力工程研究设计所.xlsx'), 'excel_bin'),
        (
            str(repo_root / 'excel_bin' / '姓名角色表——核工程所通信专业+设备专业.xlsx'),
            'excel_bin',
        ),
    ],
    hiddenimports=[
        'sql_explorer',
        'sql_explorer.cli',
        'sql_explorer.connect',
        'sql_explorer.schema',
        'sql_explorer.sampling',
        'sql_explorer.profiling',
        'sql_explorer.discovery',
        'sql_explorer.roster',
        'sql_explorer.report',
        'sql_explorer.template_spec',
        'sql_explorer.types',
        'pandas',
        'openpyxl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='sql_explorer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='sql_explorer',
)
