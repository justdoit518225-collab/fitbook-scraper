@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 重設掃描比對基準：清空掃描歷史，本次結果作為初始版...
python scrape_fitbook.py --reset-baseline
if errorlevel 1 (
    echo.
    echo Failed with exit code %errorlevel%.
    pause
    exit /b %errorlevel%
)
echo.
echo Done.
pause
