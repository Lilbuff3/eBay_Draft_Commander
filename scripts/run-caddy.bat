@echo off
cd /d "%~dp0.."
if not exist "data" mkdir "data"
if "%~1" == "" (
    caddy run --config Caddyfile >> data\caddy_service.log 2>&1
) else (
    "%~1" run --config Caddyfile >> data\caddy_service.log 2>&1
)
