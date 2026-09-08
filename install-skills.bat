@echo off
echo ========================================
echo  Claude Code slash commands - Install
echo ========================================
echo.

:: Check if uv is installed
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: uv is not installed or not in PATH
    echo Please install uv first: https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)

uv run python -m plan_implementer.skill_installer
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Failed to install the slash commands
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Slash commands installed!
echo ========================================
echo.
pause
