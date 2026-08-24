# -*- coding: utf-8 -*-
"""
匯出 FitBook Cookie → config.json，並嘗試更新 GitHub Secret。

用法：
  python export_fitbook_cookie.py
  python export_fitbook_cookie.py --wait 180   （開啟瀏覽器後等待 180 秒，不必按 Enter）

請在跳出的 Edge 視窗登入 FitBook（含 LINE 登入），並能開啟任一場「已預約會員」課程頁後再匯出。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
HOME_URL = "https://www.fit-book.com.tw/urlname459/564"
SAMPLE_COURSE_URL = "https://www.fit-book.com.tw/urlname459/member/course/1668803/564"


def _cookie_header(cookies: list[dict]) -> str:
    relevant = [c for c in cookies if "fit-book" in (c.get("domain") or "")]
    keep = {"XSRF-TOKEN", "laravel_session"}
    pairs = [
        f"{c['name']}={c['value']}"
        for c in relevant
        if c.get("name") in keep
    ]
    return "; ".join(pairs)


def _write_config(header: str) -> None:
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(f"找不到 {CONFIG_PATH}")
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    data["cookie_header"] = header
    CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _set_github_secret(header: str) -> bool:
    for exe in ("gh", "gh.exe"):
        try:
            subprocess.run(
                [exe, "secret", "set", "FITBOOK_COOKIE", "--body", header],
                check=True,
                cwd=str(ROOT),
                capture_output=True,
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    return False


def _verify(header: str) -> tuple[bool, int, bool]:
    from scrape_fitbook import (
        _is_login_wall,
        _make_http_session,
        fetch_member_course_html,
        load_config,
        parse_members_with_avatars_from_html,
    )

    cfg = load_config()
    cfg = dict(cfg)
    cfg["cookie_header"] = header
    s = _make_http_session(cfg)
    page = fetch_member_course_html(cfg, s, 1668803, int(cfg["place_id"]))
    if _is_login_wall(page):
        return False, 0, False
    members = parse_members_with_avatars_from_html(page, None, [])
    return True, len(members), "已預約會員" in page


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wait",
        type=int,
        default=0,
        help="開啟瀏覽器後自動等待秒數（0 表示需按 Enter）",
    )
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("請先執行: pip install playwright")
        print("然後執行: playwright install msedge")
        sys.exit(1)

    print("即將開啟 Edge 視窗…")
    print("1. 若未登入，請用 LINE／帳號登入 FitBook")
    print("2. 建議開啟任一場球敘，確認看得到「已預約會員」名單")
    print(f"3. 完成後 {'等待 ' + str(args.wait) + ' 秒' if args.wait else '回到終端機按 Enter'}")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=120_000)
        try:
            page.goto(SAMPLE_COURSE_URL, wait_until="domcontentloaded", timeout=60_000)
        except Exception:
            pass

        if args.wait > 0:
            for sec in range(args.wait, 0, -10):
                print(f"  剩餘 {sec} 秒…")
                time.sleep(min(10, sec))
        else:
            try:
                input("\n>>> 登入完成後按 Enter 匯出 Cookie… ")
            except EOFError:
                time.sleep(60)

        cookies = context.cookies()
        browser.close()

    header = _cookie_header(cookies)
    if not header or "laravel_session" not in header:
        print("未取得有效 Cookie（需含 XSRF-TOKEN 與 laravel_session）")
        sys.exit(1)

    names = [p.split("=", 1)[0] for p in header.split("; ")]
    print(f"已取得: {', '.join(names)}")

    _write_config(header)
    print(f"已寫入 {CONFIG_PATH}")

    ok, n, html_ok = _verify(header)
    if ok and n > 0:
        print(f"驗證成功：可讀取會員名單（樣本 {n} 人）")
    elif ok and html_ok:
        print("驗證：已登入課程頁（該場可能暫無會員列）")
    else:
        print("警告：Cookie 仍無法讀取課程頁，請重新登入再跑一次本腳本")

    if _set_github_secret(header):
        print("已更新 GitHub Secret: FITBOOK_COOKIE")
    else:
        print(
            "未能自動更新 GitHub Secret（未安裝 gh 或未登入）。\n"
            "請到 GitHub → Settings → Secrets → FITBOOK_COOKIE 手動貼上 config.json 的 cookie_header。"
        )


if __name__ == "__main__":
    main()
