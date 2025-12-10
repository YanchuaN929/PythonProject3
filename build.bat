@echo off
chcp 65001 >nul
echo ============================================
echo   接口筛选程序 - 自动打包脚本
echo   使用虚拟环境: .venv (Python 3.8.5)
echo ============================================
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 检查虚拟环境是否存在
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在: .venv\Scripts\python.exe
    echo 请先创建虚拟环境或检查路径
    pause
    exit /b 1
)

:: 显示 Python 版本
echo [信息] 检查 Python 版本...
.venv\Scripts\python.exe --version
echo.

:: 步骤1：清理旧的构建文件
echo [步骤1] 清理旧的构建文件...
if exist "build" (
    echo   删除 build 目录...
    rmdir /s /q "build" 2>nul
)
if exist "dist" (
    echo   删除 dist 目录...
    rmdir /s /q "dist" 2>nul
)
if exist "__pycache__" (
    echo   删除 __pycache__ 目录...
    rmdir /s /q "__pycache__" 2>nul
)
:: 清理 registry 模块的缓存
if exist "registry\__pycache__" (
    echo   删除 registry\__pycache__ 目录...
    rmdir /s /q "registry\__pycache__" 2>nul
)
:: 清理 update 模块的缓存
if exist "update\__pycache__" (
    echo   删除 update\__pycache__ 目录...
    rmdir /s /q "update\__pycache__" 2>nul
)
:: 清理 .spec 生成的临时文件
if exist "*.spec.bak" (
    del /q "*.spec.bak" 2>nul
)
echo   清理完成!
echo.

:: 步骤2：检查 PyInstaller 是否安装
echo [步骤2] 检查 PyInstaller...
.venv\Scripts\python.exe -c "import PyInstaller; print(f'  PyInstaller 版本: {PyInstaller.__version__}')" 2>nul
if errorlevel 1 (
    echo   [警告] PyInstaller 未安装，正在安装...
    .venv\Scripts\pip.exe install pyinstaller
    if errorlevel 1 (
        echo   [错误] PyInstaller 安装失败
        pause
        exit /b 1
    )
)
echo.

:: 步骤3：执行打包
echo [步骤3] 开始打包...
echo   使用配置文件: excel_processor.spec
echo.
.venv\Scripts\pyinstaller.exe excel_processor.spec --noconfirm

:: 检查打包结果
if errorlevel 1 (
    echo.
    echo ============================================
    echo   [错误] 打包失败!
    echo ============================================
    pause
    exit /b 1
)

echo.
echo ============================================
echo   [成功] 打包完成!
echo   输出目录: dist\接口筛选\
echo ============================================
echo.

:: 显示输出文件
echo [信息] 输出文件列表:
dir /b "dist\接口筛选\*.exe" 2>nul
echo.

:: 询问是否打开输出目录
set /p open_dir="是否打开输出目录? (Y/N): "
if /i "%open_dir%"=="Y" (
    explorer "dist\接口筛选"
)

pause

