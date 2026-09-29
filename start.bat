@echo off
title My Agent Restart
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
