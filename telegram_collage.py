# -*- coding: utf-8 -*-
"""Telegram 人員異動通知：頭像拼圖卡片（方案 A）。"""

from __future__ import annotations

import io
import math
from typing import Any

import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageFont

from telegram_notify import (
    MAX_COLLAGE_SESSIONS,
    _collect_session_groups,
    _format_quota,
    _group_by_course,
    _kind_icon,
    _session_when_text,
    _short_scan_at,
)

CANVAS_W = 600
PAD = 16
AVATAR_SIZE = 48
AVATAR_GAP = 8
MAX_AVATARS_ROW = 6
NAME_MAX_CHARS = 5

COLOR_BG = (248, 249, 251)
COLOR_HEADER = (26, 32, 44)
COLOR_TEXT = (31, 41, 55)
COLOR_MUTED = (107, 114, 128)
COLOR_LINE = (229, 231, 235)
COLOR_GREEN = (34, 197, 94)
COLOR_RED = (239, 68, 68)
COLOR_PLACEHOLDER = (209, 213, 219)


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc"]
        if bold
        else ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc"]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fetch_avatar_bytes(http_session: requests.Session | None, url: str) -> bytes | None:
    if not url:
        return None
    try:
        from scrape_fitbook import _download_avatar_image

        if http_session is not None:
            return _download_avatar_image(http_session, url)
        s = requests.Session()
        return _download_avatar_image(s, url)
    except Exception:
        return None


def _circle_avatar(
    raw: bytes | None,
    name: str,
    *,
    removed: bool = False,
) -> Image.Image:
    size = AVATAR_SIZE
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if raw:
        try:
            src = Image.open(io.BytesIO(raw)).convert("RGBA")
            src = src.resize((size, size), Image.Resampling.LANCZOS)
        except Exception:
            src = None
    else:
        src = None

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)

    if src is not None:
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(src, (0, 0), mask)
        img = out
    else:
        draw.ellipse((0, 0, size - 1, size - 1), fill=COLOR_PLACEHOLDER)
        ch = (name or "?").strip()[:1] or "?"
        font = _load_font(20, bold=True)
        bbox = draw.textbbox((0, 0), ch, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
            ch,
            fill=(75, 85, 99),
            font=font,
        )

    border = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(border).ellipse(
        (0, 0, size - 1, size - 1), outline=(255, 255, 255, 255), width=2
    )
    img = Image.alpha_composite(img.convert("RGBA"), border)

    if removed:
        overlay = Image.new("RGBA", (size, size), (120, 120, 120, 110))
        overlay.putalpha(mask)
        img = Image.alpha_composite(img.convert("RGBA"), overlay)

    return img


def _truncate_name(name: str) -> str:
    name = name.strip()
    if len(name) <= NAME_MAX_CHARS:
        return name
    return name[: NAME_MAX_CHARS - 1] + "…"


def _session_block_height(member_count: int) -> int:
    shown = min(member_count, MAX_AVATARS_ROW)
    overflow = 1 if member_count > MAX_AVATARS_ROW else 0
    slots = shown + overflow
    rows = max(1, math.ceil(slots / MAX_AVATARS_ROW))
    return 30 + rows * (AVATAR_SIZE + 20) + 10


def _estimate_canvas_height(
    course_blocks: list[tuple[str, list[dict[str, Any]]]],
    *,
    hidden_sessions: int,
) -> int:
    y = PAD + 58
    for _title, groups in course_blocks:
        y += 34
        for group in groups:
            rows = group.get("member_rows") or []
            y += _session_block_height(len(rows))
        y += 6
    if hidden_sessions > 0:
        y += 28
    return y + PAD


def _draw_header(
    draw: ImageDraw.ImageDraw,
    *,
    scan_at: str,
    added: int,
    removed: int,
) -> None:
    font_title = _load_font(18, bold=True)
    font_sub = _load_font(13)
    draw.rectangle((0, 0, CANVAS_W, 56), fill=COLOR_HEADER)
    draw.text((PAD, 10), "🏸 FitBook 人員異動", fill=(255, 255, 255), font=font_title)
    sub = f"🕐 {_short_scan_at(scan_at)}   🟢 +{added}   🔴 -{removed}" if scan_at else f"🟢 +{added}   🔴 -{removed}"
    draw.text((PAD, 34), sub, fill=(203, 213, 225), font=font_sub)


def _draw_session_block(
    canvas: Image.Image,
    y: int,
    group: dict[str, Any],
    *,
    http_session: requests.Session | None,
) -> int:
    draw = ImageDraw.Draw(canvas)
    row: pd.Series = group["meta"]
    kind = str(group.get("kind", "") or "")
    removed = kind == "刪除"
    accent = COLOR_RED if removed else COLOR_GREEN

    when = _session_when_text(row)
    quota = _format_quota(row)
    head = f"{_kind_icon(kind)} {when}"
    if quota:
        head += f"  {quota}"

    font_head = _load_font(13, bold=True)
    draw.text((PAD, y), head, fill=COLOR_TEXT, font=font_head)
    y += 28

    members: list[dict[str, str]] = list(group.get("member_rows") or [])
    if not members:
        names = group.get("members") or []
        members = [{"name": str(n), "avatar": ""} for n in names if str(n).strip()]

    display = members[:MAX_AVATARS_ROW]
    overflow = len(members) - len(display)

    col_w = AVATAR_SIZE + AVATAR_GAP
    x = PAD
    row_y = y
    for i, item in enumerate(display):
        if i > 0 and i % MAX_AVATARS_ROW == 0:
            row_y += AVATAR_SIZE + 20
            x = PAD
        raw = _fetch_avatar_bytes(http_session, item.get("avatar", ""))
        avatar = _circle_avatar(raw, item.get("name", ""), removed=removed)
        canvas.paste(avatar, (x, row_y), avatar)

        name_font = _load_font(11)
        label = _truncate_name(item.get("name", ""))
        bbox = draw.textbbox((0, 0), label, font=name_font)
        tw = bbox[2] - bbox[0]
        draw.text(
            (x + (AVATAR_SIZE - tw) / 2, row_y + AVATAR_SIZE + 2),
            label,
            fill=COLOR_MUTED if removed else COLOR_TEXT,
            font=name_font,
        )
        x += col_w

    if overflow > 0:
        idx = len(display)
        if idx > 0 and idx % MAX_AVATARS_ROW == 0:
            row_y += AVATAR_SIZE + 20
            x = PAD
        plus_font = _load_font(14, bold=True)
        draw.ellipse(
            (x, row_y, x + AVATAR_SIZE - 1, row_y + AVATAR_SIZE - 1),
            fill=(243, 244, 246),
            outline=COLOR_LINE,
        )
        label = f"+{overflow}"
        bbox = draw.textbbox((0, 0), label, font=plus_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            (x + (AVATAR_SIZE - tw) / 2 - bbox[0], row_y + (AVATAR_SIZE - th) / 2 - bbox[1]),
            label,
            fill=COLOR_MUTED,
            font=plus_font,
        )

    rows_used = max(
        1,
        math.ceil((len(display) + (1 if overflow else 0)) / MAX_AVATARS_ROW),
    )
    return y + rows_used * (AVATAR_SIZE + 20) + 10


def build_diff_collage_png(
    diff_df: pd.DataFrame,
    *,
    http_session: requests.Session | None = None,
) -> bytes | None:
    """依異動資料產生 PNG 拼圖；無異動或無法繪製時回傳 None。"""
    if diff_df is None or diff_df.empty:
        return None

    added = removed = 0
    if "異動類型" in diff_df.columns:
        added = int((diff_df["異動類型"] == "新增").sum())
        removed = int((diff_df["異動類型"] == "刪除").sum())
    if added + removed == 0:
        return None

    scan_at = ""
    if "掃描時間" in diff_df.columns and not diff_df["掃描時間"].empty:
        scan_at = str(diff_df["掃描時間"].iloc[0] or "").strip()

    session_groups = _collect_session_groups(diff_df)
    if not session_groups:
        return None

    course_blocks: list[tuple[str, list[dict[str, Any]]]] = []
    shown = 0
    hidden = 0
    for title, groups in _group_by_course(session_groups):
        block: list[dict[str, Any]] = []
        for group in groups:
            if shown >= MAX_COLLAGE_SESSIONS:
                hidden += 1
                continue
            block.append(group)
            shown += 1
        if block:
            course_blocks.append((title, block))

    if not course_blocks:
        return None

    height = _estimate_canvas_height(course_blocks, hidden_sessions=hidden)
    canvas = Image.new("RGB", (CANVAS_W, height), COLOR_BG)
    draw = ImageDraw.Draw(canvas)
    _draw_header(draw, scan_at=scan_at, added=added, removed=removed)

    y = 56 + PAD
    font_course = _load_font(14, bold=True)
    for title, groups in course_blocks:
        draw.line((PAD, y, CANVAS_W - PAD, y), fill=COLOR_LINE, width=1)
        y += 8
        draw.text((PAD, y), f"📘 {title}", fill=COLOR_TEXT, font=font_course)
        y += 26
        for group in groups:
            y = _draw_session_block(canvas, y, group, http_session=http_session)

    if hidden > 0:
        font_note = _load_font(12)
        draw.text(
            (PAD, height - PAD - 18),
            f"⚠️ 另有 {hidden} 場次未顯示於圖中",
            fill=COLOR_MUTED,
            font=font_note,
        )

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
