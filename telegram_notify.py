# -*- coding: utf-8 -*-
"""Telegram Bot：人員新增／刪除時推送通知。"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LEN = 4000


def effective_telegram_credentials(cfg: dict[str, Any]) -> tuple[str, str]:
    """Bot Token 與 Chat ID：config.json 優先，其次環境變數。"""
    token = (cfg.get("telegram_bot_token") or "").strip()
    chat_id = (cfg.get("telegram_chat_id") or "").strip()
    if not token:
        token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not chat_id:
        chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    return token, chat_id


def telegram_enabled(cfg: dict[str, Any]) -> bool:
    token, chat_id = effective_telegram_credentials(cfg)
    return bool(token and chat_id)


def _row_line(row: pd.Series) -> str:
    kind = str(row.get("異動類型", "") or "").strip()
    venue = str(row.get("場館標籤", "") or "").strip()
    date = str(row.get("場次日期", "") or "").strip()
    dow = str(row.get("星期", "") or "").strip()
    slot = str(row.get("時段", "") or "").strip()
    member = str(row.get("會員暱稱", "") or "").strip()
    prefix = "＋" if kind == "新增" else "－" if kind == "刪除" else "·"
    session = "｜".join(x for x in (venue, date, dow, slot) if x)
    if session and member:
        return f"{prefix}{kind} {session}\n  {member}"
    if member:
        return f"{prefix}{kind} {member}"
    return f"{prefix}{kind} {session}".strip()


def format_diff_message(
    diff_df: pd.DataFrame,
    *,
    sheet_url: str | None = None,
) -> str:
    if diff_df.empty:
        return ""
    added = removed = 0
    if "異動類型" in diff_df.columns:
        added = int((diff_df["異動類型"] == "新增").sum())
        removed = int((diff_df["異動類型"] == "刪除").sum())
    scan_at = ""
    if "掃描時間" in diff_df.columns and not diff_df["掃描時間"].empty:
        scan_at = str(diff_df["掃描時間"].iloc[0] or "").strip()

    lines = ["FitBook 人員異動"]
    if scan_at:
        lines.append(f"掃描：{scan_at}")
    lines.append(f"新增 {added}｜刪除 {removed}")
    lines.append("")

    for _, row in diff_df.iterrows():
        lines.append(_row_line(row))

    if sheet_url:
        lines.extend(["", f"試算表：{sheet_url.strip()}"])

    text = "\n".join(lines).strip()
    if len(text) > MAX_MESSAGE_LEN:
        text = text[: MAX_MESSAGE_LEN - 20].rstrip() + "\n…（訊息過長已截斷）"
    return text


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    if not text.strip():
        return
    url = TELEGRAM_API.format(token=token)
    r = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    if r.status_code != 200:
        detail = r.text[:500] if r.text else r.status_code
        raise RuntimeError(f"Telegram 發送失敗：{detail}")


def maybe_send_telegram_diff(
    cfg: dict[str, Any],
    diff_df: pd.DataFrame | None,
    *,
    sheet_url: str | None = None,
) -> str | None:
    """有異動且已設定 Token/Chat ID 時推送；未設定則略過。回傳結果說明或 None。"""
    if diff_df is None or diff_df.empty:
        return None
    token, chat_id = effective_telegram_credentials(cfg)
    if not token or not chat_id:
        return None
    text = format_diff_message(diff_df, sheet_url=sheet_url)
    send_telegram_message(token, chat_id, text)
    return "已發送 Telegram 通知"
