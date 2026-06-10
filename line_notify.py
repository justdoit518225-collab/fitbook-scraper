# -*- coding: utf-8 -*-
"""LINE Messaging API：人員新增／刪除時推送通知。"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests

from telegram_notify import format_diff_message

LINE_PUSH_API = "https://api.line.me/v2/bot/message/push"
MAX_MESSAGE_LEN = 5000


def effective_line_credentials(cfg: dict[str, Any]) -> tuple[str, str]:
    """Channel Access Token 與 User ID：config.json 優先，其次環境變數。"""
    token = (cfg.get("line_channel_access_token") or "").strip()
    user_id = (cfg.get("line_user_id") or "").strip()
    if not token:
        token = (os.environ.get("LINE_CHANNEL_ACCESS_TOKEN") or "").strip()
    if not user_id:
        user_id = (os.environ.get("LINE_USER_ID") or "").strip()
    return token, user_id


def line_notify_enabled(cfg: dict[str, Any]) -> bool:
    token, user_id = effective_line_credentials(cfg)
    return bool(token and user_id)


def send_line_message(token: str, user_id: str, text: str) -> None:
    if not text.strip():
        return
    if len(text) > MAX_MESSAGE_LEN:
        text = text[: MAX_MESSAGE_LEN - 20].rstrip() + "\n…（訊息過長已截斷）"
    r = requests.post(
        LINE_PUSH_API,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "to": user_id,
            "messages": [{"type": "text", "text": text}],
        },
        timeout=30,
    )
    if r.status_code != 200:
        detail = r.text[:500] if r.text else r.status_code
        raise RuntimeError(f"LINE 發送失敗：{detail}")


def maybe_send_line_diff(
    cfg: dict[str, Any],
    diff_df: pd.DataFrame | None,
    *,
    sheet_url: str | None = None,
) -> str | None:
    """有異動且已設定 Token/User ID 時推送；未設定則略過。"""
    if diff_df is None or diff_df.empty:
        return None
    token, user_id = effective_line_credentials(cfg)
    if not token or not user_id:
        return None
    text = format_diff_message(diff_df, sheet_url=sheet_url)
    send_line_message(token, user_id, text)
    return "已發送 LINE 通知"
