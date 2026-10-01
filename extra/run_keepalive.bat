@echo off
title Anti-suspension de Audifonos
cls
python extra\keepalive_audio.py %* < NUL
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Intentando con 'uv run'...
    uv run python extra\keepalive_audio.py %* < NUL
)
