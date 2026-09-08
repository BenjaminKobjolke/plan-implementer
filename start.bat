@echo off
setlocal

where uv >nul 2>nul
if errorlevel 1 (
    echo ERROR: uv is not installed or not in PATH
    exit /b 2
)

uv run plan-implementer %*
exit /b %ERRORLEVEL%
