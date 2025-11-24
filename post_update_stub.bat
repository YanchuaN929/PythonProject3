@echo off
set LOGFILE=%~dp0post_update_log.txt
set NOW=%date% %time%
echo [%NOW%] post_update_stub.bat invoked with args: %* >> "%LOGFILE%"
exit /b 0
