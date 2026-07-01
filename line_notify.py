# -*- coding: utf-8 -*-
"""LINE Messaging API：人員新增／刪除時推送通知。"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests

from telegram_notify import format_diff_message

LINE_PUSH_API = "https://api.line.me/v2/bot/message/push"
LINE_BROADCAST_API = "https://api.line.me/v2/bot/message/broadcast"
MAX_MESSAGE_LEN = 5000


def line_use_broadcast(cfg: dict[str, Any]) -> bool:
    """廣播給所有好友，不需 line_user_id（適合僅自己一人加好友）。"""
    if cfg.get("line_use_broadcast") is True:
        return True
    env = (os.environ.get("LINE_USE_BROADCAST") or "").strip().lower()
    return env in ("1", "true", "yes")


def effective_line_credentials(cfg: dict[str, Any]) -> tuple[str, str]:
    """Channel Access Token 與 User ID：config.json 優先，其次環境變數。"""
    token = (cfg.get("line_channel_access_token") or "").strip()
    user_id = (cfg.get("line_user_id") or "").strip()
    if not token:
        token = (os.environ.get("LINE_CHANNEL_ACCESS_TOKEN") or "").strip()
    if not user_id:
        user_id = (os.environ.get("LINE_USER_ID") or "").strip()
    return token, user_id


def _line_notify_config_enabled(cfg: dict[str, Any]) -> bool:
    """是否啟用 LINE 通知（預設關閉，需明確設 line_notify_enabled: true）。"""
    if cfg.get("line_notify_enabled") is True:
        return True
    if cfg.get("line_notify_enabled") is False:
        return False
    env = (os.environ.get("LINE_NOTIFY_ENABLED") or "").strip().lower()
    return env in ("1", "true", "yes")


def line_notify_enabled(cfg: dict[str, Any]) -> bool:
    if not _line_notify_config_enabled(cfg):
        return False
    token, user_id = effective_line_credentials(cfg)
    if not token:
        return False
    if line_use_broadcast(cfg):
        return True
    return bool(user_id)


def _trim_line_text(text: str) -> str:
    if len(text) > MAX_MESSAGE_LEN:
        return text[: MAX_MESSAGE_LEN - 20].rstrip() + "\n…（訊息過長已截斷）"
    return text


def _line_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def send_line_message(token: str, user_id: str, text: str) -> None:
    if not text.strip():
        return
    text = _trim_line_text(text)
    r = requests.post(
        LINE_PUSH_API,
        headers=_line_headers(token),
        json={
            "to": user_id,
            "messages": [{"type": "text", "text": text}],
        },
        timeout=30,
    )
    if r.status_code != 200:
        detail = r.text[:500] if r.text else r.status_code
        raise RuntimeError(f"LINE 發送失敗：{detail}")


def send_line_broadcast(token: str, text: str) -> None:
    if not text.strip():
        return
    text = _trim_line_text(text)
    r = requests.post(
        LINE_BROADCAST_API,
        headers=_line_headers(token),
        json={"messages": [{"type": "text", "text": text}]},
        timeout=30,
    )
    if r.status_code != 200:
        detail = r.text[:500] if r.text else r.status_code
        raise RuntimeError(f"LINE 廣播失敗：{detail}")


def maybe_send_line_diff(
    cfg: dict[str, Any],
    diff_df: pd.DataFrame | None,
    *,
    sheet_url: str | None = None,
) -> str | None:
    """有異動且已設定 Token（廣播或 User ID 推播）時發送；未設定則略過。"""
    if not line_notify_enabled(cfg):
        return None
    if diff_df is None or diff_df.empty:
        return None
    token, user_id = effective_line_credentials(cfg)
    use_broadcast = line_use_broadcast(cfg)
    if not token or (not use_broadcast and not user_id):
        return None
    text = format_diff_message(diff_df, sheet_url=sheet_url)
    if use_broadcast:
        send_line_broadcast(token, text)
    else:
        send_line_message(token, user_id, text)
    return "已發送 LINE 通知"
