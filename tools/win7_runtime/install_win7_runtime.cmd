@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "LOG=%SCRIPT_DIR%win7_runtime_install.log"
set "REDIST_DIR=%SCRIPT_DIR%redist"
if exist "%LOG%" del /q "%LOG%" >nul 2>nul

call :log "Win7 offline runtime installer"
call :log "=============================="
call :log "Time: %DATE% %TIME%"
call :log "ScriptDir: %SCRIPT_DIR%"
call :log ""

net session >nul 2>nul
if errorlevel 1 (
    call :log "ERROR: Administrator privileges are required."
    call :log "Right-click install_win7_runtime.cmd and choose Run as administrator."
    echo.
    pause
    exit /b 1
)

if /i "%PROCESSOR_ARCHITECTURE%"=="x86" if "%PROCESSOR_ARCHITEW6432%"=="" (
    call :log "ERROR: 32-bit Windows detected. The application package is 64-bit."
    pause
    exit /b 1
)

if not exist "%REDIST_DIR%" (
    call :log "ERROR: redist directory not found: %REDIST_DIR%"
    pause
    exit /b 1
)

call :log "[Before install probe]"
if exist "%SCRIPT_DIR%win7_probe.cmd" call "%SCRIPT_DIR%win7_probe.cmd"

set "NEED_VC=0"
if not exist "%WINDIR%\System32\ucrtbase.dll" set "NEED_VC=1"
if not exist "%WINDIR%\System32\api-ms-win-crt-runtime-l1-1-0.dll" set "NEED_VC=1"
if not exist "%WINDIR%\System32\vcruntime140.dll" set "NEED_VC=1"

if "%NEED_VC%"=="1" (
    call :install_vc_redist
) else (
    call :log "VC/UCRT files already exist in System32; VC redist install skipped."
)

call :install_msu_files

call :log ""
call :log "[After install probe]"
if exist "%SCRIPT_DIR%win7_probe.cmd" call "%SCRIPT_DIR%win7_probe.cmd"

call :log ""
call :log "Install flow finished. Reboot Windows if any package was installed."
echo.
echo Finished. Log:
echo %LOG%
pause
exit /b 0

:install_vc_redist
set "VC_EXE="
if exist "%REDIST_DIR%\vc_redist.x64.exe" set "VC_EXE=%REDIST_DIR%\vc_redist.x64.exe"
if not defined VC_EXE if exist "%REDIST_DIR%\vcredist_x64.exe" set "VC_EXE=%REDIST_DIR%\vcredist_x64.exe"
if not defined VC_EXE (
    call :log "WARN: VC redist installer not found in redist directory."
    call :log "Expected: vc_redist.x64.exe or vcredist_x64.exe"
    exit /b 0
)
call :log "Installing VC redist: %VC_EXE%"
"%VC_EXE%" /install /quiet /norestart >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
call :log "VC redist exit code: %RC%"
exit /b 0

:install_msu_files
for %%F in ("%REDIST_DIR%\*.msu") do (
    if exist "%%~fF" (
        call :log "Installing MSU: %%~nxF"
        wusa.exe "%%~fF" /quiet /norestart >> "%LOG%" 2>&1
        call :log "MSU exit code: !ERRORLEVEL!"
    )
)
exit /b 0

:log
echo %~1
echo %~1>> "%LOG%"
exit /b 0
