# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['base.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # 核心模块 (core/)
        ('core/main.py', 'core'),
        ('core/main2.py', 'core'),
        ('core/Monitor.py', 'core'),
        ('core/__init__.py', 'core'),
        # UI模块 (ui/)
        ('ui/window.py', 'ui'),
        ('ui/input_handler.py', 'ui'),
        ('ui/ignore_overdue_dialog.py', 'ui'),
        ('ui/help_viewer.py', 'ui'),
        ('ui/ui_copy.py', 'ui'),
        ('ui/__init__.py', 'ui'),
        # 服务模块 (services/)
        ('services/file_manager.py', 'services'),
        ('services/distribution.py', 'services'),
        ('services/db_status.py', 'services'),
        ('services/__init__.py', 'services'),
        # 工具模块 (utils/)
        ('utils/date_utils.py', 'utils'),
        ('utils/adjust.py', 'utils'),
        ('utils/__init__.py', 'utils'),
        # 配置文件
        ('config.json', '.'),
        ('version.json', '.'),
        # 文档文件
        ('document/4_使用说明.md', 'document'),
        # 资源文件
        ('ico_bin/tubiao.ico', 'ico_bin'),
        ('excel_bin/姓名角色表.xlsx', 'excel_bin'),
    ],
    hiddenimports=[
        # 核心模块 (core/)
        'core',
        'core.main',
        'core.main2',
        'core.Monitor',
        # UI模块 (ui/)
        'ui',
        'ui.window',
        'ui.input_handler',
        'ui.ignore_overdue_dialog',
        'ui.help_viewer',
        'ui.ui_copy',
        # 服务模块 (services/)
        'services',
        'services.file_manager',
        'services.distribution',
        'services.db_status',
        # 工具模块 (utils/)
        'utils',
        'utils.date_utils',
        'utils.adjust',
        # write_tasks 模块（写入任务面板/回文提交等）
        'write_tasks',
        'write_tasks.manager',
        'write_tasks.executors',
        'write_tasks.cache',
        'write_tasks.models',
        'write_tasks.pending_cache',
        'write_tasks.shared_log',
        'write_tasks.task_panel',
        # 第三方库
        'pandas',
        'openpyxl',
        'xlrd', 
        'numpy',
        'pystray',
        'PIL',
        'PIL.Image',
        # tkinter相关
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
        # 标准库
        'winreg',
        'threading',
        'json',
        'datetime',
        'pathlib',
        'subprocess',
        'copy',
        'warnings',
        're',
        'hashlib',
        'pickle',
        'shutil',
        'sys',
        'os',
        'typing',
        'traceback',
        'tempfile',
        'argparse',
        'time',
        'sqlite3',
        # registry模块
        'registry',
        'registry.hooks',
        'registry.config',
        'registry.db',
        'registry.service',
        'registry.util',
        'registry.models',
        'registry.history_ui',
        'registry.migrate',
        'registry.local_cache',
        'registry.write_queue',
        # update模块
        'update',
        'update.manager',
        'update.versioning',
        'update.updater_cli',
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

update_analysis = Analysis(
    ['update/updater_cli.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
update_pyz = PYZ(update_analysis.pure, update_analysis.zipped_data, cipher=block_cipher)

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

update_exe = EXE(
    update_pyz,
    update_analysis.scripts,
    [],
    exclude_binaries=True,
    name='update',
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
    update_exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='接口筛选'
)