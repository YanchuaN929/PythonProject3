@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%"
if exist "%SCRIPT_DIR%..\_internal" set "APP_DIR=%SCRIPT_DIR%.."
if exist "%SCRIPT_DIR%..\..\_internal" set "APP_DIR=%SCRIPT_DIR%..\.."

set "REPORT=%SCRIPT_DIR%win7_probe_report.txt"
if exist "%REPORT%" del /q "%REPORT%" >nul 2>nul

call :log "Win7 runtime probe"
call :log "=================="
call :log "Time: %DATE% %TIME%"
call :log "ScriptDir: %SCRIPT_DIR%"
call :log "AppDir: %APP_DIR%"
call :log ""

call :log "[OS]"
ver >> "%REPORT%"
wmic os get Caption,Version,OSArchitecture,ServicePackMajorVersion /value >> "%REPORT%" 2>&1
call :log ""

call :log "[Architecture]"
call :log "PROCESSOR_ARCHITECTURE=%PROCESSOR_ARCHITECTURE%"
call :log "PROCESSOR_ARCHITEW6432=%PROCESSOR_ARCHITEW6432%"
if /i "%PROCESSOR_ARCHITECTURE%"=="x86" if "%PROCESSOR_ARCHITEW6432%"=="" (
    call :log "RESULT: 32-bit Windows detected. This package is 64-bit and cannot run here."
) else (
    call :log "RESULT: 64-bit Windows detected."
)
call :log ""

call :log "[Hotfixes]"
for %%K in (KB2533623 KB2999226 KB4474419 KB4490628) do (
    wmic qfe get HotFixID 2>nul | findstr /i "%%K" >nul
    if errorlevel 1 (
        call :log "MISSING %%K"
    ) else (
        call :log "OK %%K"
    )
)
call :log ""

call :log "[System runtime files]"
call :check_file "%WINDIR%\System32\ucrtbase.dll"
call :check_file "%WINDIR%\System32\api-ms-win-crt-runtime-l1-1-0.dll"
call :check_file "%WINDIR%\System32\vcruntime140.dll"
call :check_file "%WINDIR%\System32\vcruntime140_1.dll"
call :log ""

call :log "[App local runtime files]"
call :check_file "%APP_DIR%\_internal\ucrtbase.dll"
call :check_file "%APP_DIR%\_internal\python38.dll"
call :check_file "%APP_DIR%\_internal\VCRUNTIME140.dll"
call :check_file "%APP_DIR%\update.exe"
call :check_file "%APP_DIR%\接口筛选.exe"
call :log ""

call :log "[App local ucrtbase compatibility]"
if exist "%APP_DIR%\_internal\ucrtbase.dll" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $f=Get-Item -LiteralPath '%APP_DIR%\_internal\ucrtbase.dll'; 'ucrtbase FileVersion=' + $f.VersionInfo.FileVersion } catch { 'ucrtbase FileVersion=<unknown>' }" >> "%REPORT%" 2>&1
    findstr /m /c:"api-ms-win-core-sysinfo-l1-2-0.dll" "%APP_DIR%\_internal\ucrtbase.dll" >nul 2>nul
    if errorlevel 1 (
        call :log "OK: app-local ucrtbase does not reference api-ms-win-core-sysinfo-l1-2-0.dll."
    ) else (
        call :log "BAD: app-local ucrtbase references api-ms-win-core-sysinfo-l1-2-0.dll. Windows 7 cannot load this runtime."
    )
) else (
    call :log "WARN: app-local ucrtbase.dll not found. Program depends on system UCRT."
)
call :log ""

call :log "[Conclusion]"
call :log "If update.exe reports missing api-ms-win-core-sysinfo-l1-2-0.dll, use the Win7 compatibility package first."
call :log "If runtime files or hotfixes are missing, run install_win7_runtime.cmd as Administrator from the offline toolkit."
call :log "A reboot may be required after installing Microsoft runtime components."

echo.
echo Probe finished. Report:
echo %REPORT%
pause
exit /b 0

:check_file
if exist "%~1" (
    call :log "OK %~1"
) else (
    call :log "MISSING %~1"
)
exit /b 0

:log
echo %~1
echo %~1>> "%REPORT%"
exit /b 0
