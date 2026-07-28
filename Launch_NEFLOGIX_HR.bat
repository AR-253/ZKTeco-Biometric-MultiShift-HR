@echo off
title NEFLOGIX HR Management System - Production Server
color 0A
cls
echo ====================================================================
echo               NEFLOGIX SMART BIOMETRIC ^& MULTI-SHIFT HR
echo ====================================================================
echo.
echo  [+] Local Database: MS SQL Server (.\SQLEXPRESS -> HR_Management)
echo  [+] ZKTeco Hardware: 192.168.18.25:4370 (MB360 Live Feed)
echo  [+] Local Network Access: http://192.168.18.139:5000
echo.
echo  Starting Server... (Do NOT close this window)
echo ====================================================================
echo.

cd /d "%~dp0"
python server.py

pause
