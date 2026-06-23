# -*- coding: utf-8 -*-
"""
快掃排程：依 config 間隔執行 scrape_fitbook.main（先快掃，有異動才深度掃描）。

建議改用 Windows 工作排程器（不需長開終端）：
    powershell -ExecutionPolicy Bypass -File install_windows_task.ps1

仍可用長駐方式（需視窗常開）：
    python run_hourly.py
"""

import time

import schedule

from scrape_fitbook import load_config, main as scrape_main, quick_scan_interval_minutes


def job() -> None:
    try:
        scrape_main()
    except Exception as e:
        print(f"[錯誤] {e}")


if __name__ == "__main__":
    cfg = load_config()
    minutes = quick_scan_interval_minutes(cfg)
    schedule.every(minutes).minutes.do(job)
    if schedule.jobs:
        print(f"已排程：每 {minutes} 分鐘執行一次（快掃 + 必要時深度掃描）")
        print(f"下次執行：{schedule.jobs[0].next_run}")
    while True:
        schedule.run_pending()
        time.sleep(30)
