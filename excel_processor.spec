# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['base.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('main.py', '.'),
        ('main2.py', '.'),
        ('Monitor.py', '.'),
        ('config.json', '.'),
        ('ico_bin/tubiao.ico', 'ico_bin'),
        ('excel_bin/姓名角色表.xlsx', 'excel_bin'),
    ],
    hiddenimports=[
        'main',
        'main2',
        'Monitor',
        'pandas',
        'openpyxl',
        'xlrd', 
        'numpy',
        'pystray',
        'PIL',
        'PIL.Image',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
        'winreg',
        'threading',
        'json',
        'datetime',
        'pathlib',
        'subprocess',
        'copy',
        'warnings',
        're'
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
    name='接口筛选',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ico_bin/tubiao.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='接口筛选'
)