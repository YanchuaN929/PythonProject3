@echo off
setlocal ENABLEDELAYEDEXPANSION

cd /d "%~dp0\..\..\.."
echo [INFO] Current dir: %CD%

echo [INFO] Cleaning old build artifacts...
if exist "build\sql_explorer" rmdir /s /q "build\sql_explorer"
if exist "dist\sql_explorer" rmdir /s /q "dist\sql_explorer"
if exist "dist\sql_explorer_onefile.exe" del /q "dist\sql_explorer_onefile.exe"

set BUILD_MODE=onedir

echo [INFO] Trying onefile build first...
python -m PyInstaller --noconfirm --clean --onefile --name sql_explorer_onefile ^
  --paths "scripts\db_tools" ^
  --add-data "example\template_spec.json;example" ^
  --add-data "example\1818按项目导出IDI手册2026-01-28-15_11_50.xlsx;example" ^
  --add-data "example\内部接口信息单报表181820260128.xlsx;example" ^
  --add-data "example\外部接口ICM报表181820260128.xlsx;example" ^
  --add-data "example\外部接口单报表181820260128.xlsx;example" ^
  --add-data "example\收发文清单1818.xlsx;example" ^
  --add-data "excel_bin\姓名角色表.xlsx;excel_bin" ^
  --add-data "excel_bin\姓名角色表-电力工程研究设计所.xlsx;excel_bin" ^
  --add-data "excel_bin\姓名角色表——核工程所通信专业+设备专业.xlsx;excel_bin" ^
  "scripts\db_tools\sql_explorer_main.py"

if errorlevel 1 (
  echo [WARN] Onefile build failed, fallback to onedir spec...
  python -m PyInstaller --noconfirm "scripts\db_tools\sql_explorer\sql_explorer.spec"
  if errorlevel 1 (
    echo [ERROR] PyInstaller build failed in both onefile and onedir mode.
    exit /b 1
  )
) else (
  set BUILD_MODE=onefile
)

if /I "!BUILD_MODE!"=="onefile" (
  if not exist "dist\sql_explorer" mkdir "dist\sql_explorer"
  copy /y "dist\sql_explorer_onefile.exe" "dist\sql_explorer\sql_explorer.exe" >nul
  if errorlevel 1 (
    echo [ERROR] Failed to copy onefile exe to dist\sql_explorer\sql_explorer.exe
    exit /b 1
  )
  if exist "dist\sql_explorer_onefile.exe" del /q "dist\sql_explorer_onefile.exe"
)

echo [INFO] Copying offline docs and example templates...
copy /y "scripts\db_tools\sql_explorer\README_离线运行说明.md" "dist\sql_explorer\" >nul
if not exist "dist\sql_explorer\example" mkdir "dist\sql_explorer\example"
copy /y "example\待处理文件1_模板.xlsx" "dist\sql_explorer\example\" >nul
copy /y "example\待处理文件2_模板.xlsx" "dist\sql_explorer\example\" >nul
copy /y "example\待处理文件3_模板.xlsx" "dist\sql_explorer\example\" >nul
copy /y "example\待处理文件4_模板.xlsx" "dist\sql_explorer\example\" >nul
copy /y "example\待处理文件6_模板.xlsx" "dist\sql_explorer\example\" >nul
copy /y "example\README.md" "dist\sql_explorer\example\" >nul
copy /y "example\template_spec.json" "dist\sql_explorer\example\" >nul

echo [SUCCESS] Build finished: dist\sql_explorer\ (mode=!BUILD_MODE!)
exit /b 0
