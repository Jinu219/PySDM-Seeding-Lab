@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy_server.ps1" %*
exit /b %ERRORLEVEL%
