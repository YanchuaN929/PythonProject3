@echo off
setlocal EnableExtensions
chcp 65001 >nul

echo ============================================
echo   SQL Explorer Onefile 重新打包脚本
echo ============================================
echo.

cd /d "%~dp0"

set "PY_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

echo [信息] 使用 Python:
echo   %PY_CMD%
%PY_CMD% --version
if errorlevel 1 (
    echo [错误] Python 不可用，请检查 Python 或 .venv 环境
    pause
    exit /b 1
)
echo.

echo [步骤1] 清理旧产物...
if exist "dist\sql_explorer_onefile.exe" (
    echo   删除 dist\sql_explorer_onefile.exe
    del /f /q "dist\sql_explorer_onefile.exe"
    if exist "dist\sql_explorer_onefile.exe" (
        echo [错误] 无法删除旧 exe（可能正在运行中）
        pause
        exit /b 1
    )
)
if exist "build\sql_explorer_onefile" (
    echo   删除 build\sql_explorer_onefile
    rmdir /s /q "build\sql_explorer_onefile"
)
echo   清理完成
echo.

echo [步骤2] 检查 PyInstaller...
%PY_CMD% -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo [错误] PyInstaller 未安装，请先执行:
    echo   %PY_CMD% -m pip install pyinstaller
    pause
    exit /b 1
)
echo   PyInstaller 可用
echo.

echo [步骤3] 执行打包...
%PY_CMD% -m PyInstaller --noconfirm "sql_explorer_onefile.spec"
if errorlevel 1 (
    echo.
    echo ============================================
    echo   [错误] 打包失败
    echo ============================================
    pause
    exit /b 1
)
echo.

if not exist "dist\sql_explorer_onefile.exe" (
    echo [错误] 打包完成但未找到 dist\sql_explorer_onefile.exe
    pause
    exit /b 1
)

for %%I in ("dist\sql_explorer_onefile.exe") do (
    echo ============================================
    echo   [成功] 打包完成
    echo   文件: %%~fI
    echo   大小: %%~zI bytes
    echo ============================================
)
echo.

set /p OPEN_DIR=是否打开 dist 目录? (Y/N): 
if /i "%OPEN_DIR%"=="Y" (
    start "" "dist"
)

pause
exit /b 0
