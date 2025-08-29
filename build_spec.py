#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyInstaller配置文件生成器
用于创建更详细的打包配置
"""

spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['base.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('main.py', '.'),
        ('requirements.txt', '.'),
        ('使用说明.md', '.'),
    ],
    hiddenimports=[
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
        'subprocess'
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Excel数据处理程序',
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
    icon='icon.ico'
)
'''

# 写入spec文件
with open('excel_processor.spec', 'w', encoding='utf-8') as f:
    f.write(spec_content)

print("已生成 excel_processor.spec 文件")
print("使用方法:")
print("1. 运行: pyinstaller excel_processor.spec")
print("2. 或者直接运行: build_exe.bat")