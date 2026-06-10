# -*- coding: utf-8 -*-
"""
每 10 分鐘執行一次 scrape_fitbook.main（掃描 + 必要時寫入掃描歷史）。

建議改用 Windows 工作排程器（不需長開終端）：
    powershell -ExecutionPolicy Bypass -File install_windows_task.ps1

取消排程：
    powershell -ExecutionPolicy Bypass -File uninstall_windows_task.ps1

仍可用長駐方式（需視窗常開）：
    python run_hourly.py
"""

import time

import schedule

from scrape_fitbook import main as scrape_main


def job() -> None:
    try:
        scrape_main()
    except Exception as e:
        print(f"[錯誤] {e}")


if __name__ == "__main__":
    schedule.every(10).minutes.do(job)
    if schedule.jobs:
        print("已排程：每 10 分鐘執行一次")
        print(f"下次執行：{schedule.jobs[0].next_run}")
    while True:
        schedule.run_pending()
        time.sleep(30)
