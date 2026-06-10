@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo FitBook 排程：每 10 分鐘掃描一次
echo 請保持此視窗開啟，關閉即停止排程
echo ========================================
echo.

python run_hourly.py
if errorlevel 1 (
    echo.
    echo 執行結束或發生錯誤，按任意鍵關閉...
    pause >nul
)
