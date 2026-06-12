# -*- coding: utf-8 -*-
"""Telegram Bot：人員新增／刪除時推送通知。"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Any

import pandas as pd
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LEN = 4000
MAX_DETAIL_SESSIONS = 12
_LINE_SEP = "────────────────"


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


def _short_scan_at(scan_at: str) -> str:
    scan_at = str(scan_at or "").strip()
    m = re.match(
        r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2})",
        scan_at,
    )
    if m:
        return f"{int(m.group(2)):02d}/{int(m.group(3)):02d} {m.group(4)}:{m.group(5)}"
    return scan_at


def _short_date(date_str: Any) -> str:
    date_str = str(date_str or "").strip()
    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", date_str)
    if m:
        return f"{int(m.group(2)):02d}/{int(m.group(3)):02d}"
    return date_str


def _short_slot(slot: Any) -> str:
    return str(slot or "").replace("～", "–").replace("~", "–").strip()


def _int_cell(row: pd.Series, key: str) -> int | None:
    val = row.get(key)
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if str(val).strip() == "":
            return None
        return int(val)
    except (TypeError, ValueError):
        return None


def _format_quota(row: pd.Series) -> str:
    signed = _int_cell(row, "已報名人數")
    total = _int_cell(row, "開放名額")
    remain = _int_cell(row, "剩餘名額")
    if signed is not None and total is not None and remain is not None:
        return f"（{signed}/{total}，剩 {remain}）"
    return ""


def _norm_paren(s: str) -> str:
    return s.replace("（", "(").replace("）", ")")


def _course_title(row: pd.Series) -> str:
    course = str(row.get("課程名稱", "") or "").strip()
    venue = str(row.get("場館標籤", "") or "").strip()
    if not course and not venue:
        return "未分類"
    if not course:
        return venue
    if not venue or course == venue:
        return course
    cn, vn = _norm_paren(course), _norm_paren(venue)
    if vn in cn or cn.endswith(f"({vn})"):
        return course
    return f"{course}（{venue}）"


def _course_group_key(row: pd.Series) -> str:
    course = str(row.get("課程名稱", "") or "").strip()
    venue = str(row.get("場館標籤", "") or "").strip()
    return f"{course}\0{venue}"


def _session_sort_key(row: pd.Series) -> tuple[Any, ...]:
    from scrape_fitbook import _slot_start_minutes

    return (
        str(row.get("場次日期", "") or ""),
        _slot_start_minutes(row.get("時段")),
        str(row.get("星期", "") or ""),
        str(row.get("預約頁面", "") or ""),
    )


def _format_members(names: list[str]) -> str:
    clean = [n.strip() for n in names if str(n or "").strip()]
    if not clean:
        return "（無姓名）"
    return "、".join(clean)


def _kind_icon(kind: str) -> str:
    if kind == "新增":
        return "🟢"
    if kind == "刪除":
        return "🔴"
    return "·"


def _collect_session_groups(diff_df: pd.DataFrame) -> list[dict[str, Any]]:
    buckets: dict[tuple[Any, ...], dict[str, Any]] = {}
    order: list[tuple[Any, ...]] = []
    for _, row in diff_df.iterrows():
        kind = str(row.get("異動類型", "") or "").strip()
        if kind not in ("新增", "刪除"):
            continue
        page = str(row.get("預約頁面", "") or "").strip()
        if page:
            key: tuple[Any, ...] = (page, kind)
        else:
            key = (
                str(row.get("場館標籤", "") or ""),
                str(row.get("場次日期", "") or ""),
                str(row.get("星期", "") or ""),
                str(row.get("時段", "") or ""),
                kind,
            )
        if key not in buckets:
            buckets[key] = {"meta": row, "members": [], "kind": kind}
            order.append(key)
        member = str(row.get("會員暱稱", "") or "").strip()
        if member:
            buckets[key]["members"].append(member)
    return [buckets[k] for k in order]


def _format_session_line(group: dict[str, Any]) -> str:
    row: pd.Series = group["meta"]
    kind = str(group.get("kind", "") or "")
    date = _short_date(row.get("場次日期"))
    dow = str(row.get("星期", "") or "").strip()
    slot = _short_slot(row.get("時段"))
    if date and dow and slot:
        when = f"{date}（{dow}）{slot}"
    elif date and slot:
        when = f"{date} {slot}"
    else:
        when = " ".join(x for x in (date, dow, slot) if x).strip() or "（場次未知）"
    members = _format_members(group.get("members") or [])
    quota = _format_quota(row)
    return f"{_kind_icon(kind)} {when}　{members}{quota}"


def _group_by_course(groups: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    course_order: list[str] = []
    course_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        key = _course_group_key(group["meta"])
        if key not in course_map:
            course_order.append(key)
        course_map[key].append(group)
    out: list[tuple[str, list[dict[str, Any]]]] = []
    for key in course_order:
        items = sorted(course_map[key], key=lambda g: _session_sort_key(g["meta"]))
        out.append((_course_title(items[0]["meta"]), items))
    return out


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

    lines = ["🏸 FitBook 人員異動"]
    if scan_at:
        lines.append(f"🕐 {_short_scan_at(scan_at)}　新增 {added}｜刪除 {removed}")
    else:
        lines.append(f"新增 {added}｜刪除 {removed}")
    lines.append(_LINE_SEP)

    session_groups = _collect_session_groups(diff_df)
    shown = 0
    hidden = 0
    for title, groups in _group_by_course(session_groups):
        block: list[str] = []
        for group in groups:
            if shown >= MAX_DETAIL_SESSIONS:
                hidden += 1
                continue
            block.append(f"　{_format_session_line(group)}")
            shown += 1
        if block:
            lines.append(f"📘 {title}")
            lines.extend(block)

    if hidden > 0:
        lines.extend(
            [
                _LINE_SEP,
                f"⚠️ 另有 {hidden} 場次未顯示，請開試算表「掃描歷史」",
            ]
        )

    if sheet_url:
        lines.extend([_LINE_SEP, "📎 試算表", sheet_url.strip()])

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
