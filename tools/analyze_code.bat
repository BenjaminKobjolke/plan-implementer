@echo off
setlocal

uv run ruff check .
if errorlevel 1 exit /b 1

uv run ruff format --check .
if errorlevel 1 exit /b 1

uv run mypy
exit /b %ERRORLEVEL%
