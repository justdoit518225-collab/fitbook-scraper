@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ========================================
echo  FitBook Cookie 匯出（請在跳出視窗登入）
echo ========================================
echo.
python export_fitbook_cookie.py --wait 120
echo.
pause
