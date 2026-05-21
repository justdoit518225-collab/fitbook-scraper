# -*- coding: utf-8 -*-
"""
Google 試算表匯出（服務帳戶）。

設定步驟（摘要）：
1. Google Cloud Console 建立專案 → 啟用「Google Sheets API」。
2. 建立「服務帳戶」→ 建立 JSON 金鑰，下載後放到專案目錄（例如 google_service_account.json）。
3. 新建或開啟一個試算表，網址列 id 為 .../d/<這段>/edit → 填入 config 的 google_sheet_id。
4. 將試算表「共用」給 JSON 內 client_email（編輯者）。

頭像欄使用 =IMAGE("url")，由試算表載入圖片（不需本機嵌入）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

HISTORY_SHEET_NAME = "掃描歷史"
OUTPUT_COLUMNS = [
    "掃描時間",
    "場館標籤",
    "場次日期",
    "星期",
    "時段",
    "已報名人數",
    "開放名額",
    "剩餘名額",
    "會員暱稱",
    "頭像",
    "預約頁面",
]

SESSION_MERGE_COLUMNS = [
    "掃描時間",
    "場館標籤",
    "場次日期",
    "星期",
    "時段",
    "已報名人數",
    "開放名額",
    "剩餘名額",
    "預約頁面",
]


def _emptyish_for_merge(x: Any) -> bool:
    if x is None or (isinstance(x, (float,)) and pd.isna(x)):
        return True
    if x == "" or (isinstance(x, str) and not str(x).strip()):
        return True
    s = str(x).strip()
    if s in ("", "None", "nan", "NaT"):
        return True
    return False


def _cell_equal_for_merge(a: Any, b: Any) -> bool:
    if _emptyish_for_merge(a) and _emptyish_for_merge(b):
        return True
    if _emptyish_for_merge(a) and not _emptyish_for_merge(b):
        try:
            if float(b) == 0.0:
                return True
        except (TypeError, ValueError, OverflowError):
            pass
        return False
    if _emptyish_for_merge(b) and not _emptyish_for_merge(a):
        try:
            if float(a) == 0.0:
                return True
        except (TypeError, ValueError, OverflowError):
            pass
        return False
    if a == b:
        return True
    try:
        if float(a) == float(b):
            return True
    except (TypeError, ValueError, OverflowError):
        pass
    return str(a).strip() == str(b).strip()


def _merge_text_norm(x: Any) -> str:
    s = ("" if _emptyish_for_merge(x) else str(x)).replace("～", "~").replace("–", "-")
    s = re.sub(r"\s+", " ", s.strip())
    return s


def _merge_booking_key(x: Any) -> str:
    s = ("" if _emptyish_for_merge(x) else str(x)).strip()
    s = s.split("#", 1)[0].split("?", 1)[0]
    m = re.search(r"/course/(\d+)/(\d+)", s)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return s


def _merge_date_equal(a: Any, b: Any) -> bool:
    if _emptyish_for_merge(a) and _emptyish_for_merge(b):
        return True
    d1 = pd.to_datetime(a, errors="coerce")
    d2 = pd.to_datetime(b, errors="coerce")
    if not pd.isna(d1) and not pd.isna(d2) and d1.normalize() == d2.normalize():
        return True
    return _merge_text_norm(a) == _merge_text_norm(b)


def _merge_field_equal(col: str, a: Any, b: Any) -> bool:
    if col == "預約頁面":
        ka, kb = _merge_booking_key(a), _merge_booking_key(b)
        if ka and kb and ka == kb:
            return True
        return _emptyish_for_merge(a) and _emptyish_for_merge(b)
    if col == "場次日期":
        return _merge_date_equal(a, b)
    if col in ("掃描時間", "場館標籤", "星期", "時段"):
        if _cell_equal_for_merge(a, b):
            return True
        return _merge_text_norm(a) == _merge_text_norm(b)
    return _cell_equal_for_merge(a, b)


def _rows_same_session_block(df: pd.DataFrame, i: int, j: int) -> bool:
    for c in SESSION_MERGE_COLUMNS:
        if c not in df.columns:
            return False
        if not _merge_field_equal(c, df.iloc[i][c], df.iloc[j][c]):
            return False
    return True

SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)


def google_sheets_enabled(cfg: dict[str, Any]) -> bool:
    sid = (cfg.get("google_sheet_id") or "").strip()
    sa = (cfg.get("google_service_account_json") or "").strip()
    if not sid or not sa:
        return False
    p = Path(sa)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent / p
    return p.is_file()


def _service_account_path(cfg: dict[str, Any]) -> Path:
    sa = (cfg.get("google_service_account_json") or "").strip()
    p = Path(sa)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent / p
    return p


def _gspread_client(cfg: dict[str, Any]) -> gspread.Client:
    creds = Credentials.from_service_account_file(
        str(_service_account_path(cfg)),
        scopes=list(SCOPES),
    )
    return gspread.authorize(creds)


def _open_spreadsheet(cfg: dict[str, Any]) -> gspread.Spreadsheet:
    gc = _gspread_client(cfg)
    return gc.open_by_key((cfg.get("google_sheet_id") or "").strip())


def _ensure_worksheet(sh: gspread.Spreadsheet, title: str, rows: int = 2000, cols: int = 20) -> gspread.Worksheet:
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)


def _col_a1(n: int) -> str:
    """1-based 欄序轉 A1 欄名。"""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _sanitize_cell_for_api(val: Any) -> Any:
    """gspread 送 JSON 時不可含 nan/inf；空值改為空字串。"""
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(val, float):
        if val != val or val in (float("inf"), float("-inf")):
            return ""
    if hasattr(val, "item"):
        try:
            return _sanitize_cell_for_api(val.item())
        except (ValueError, AttributeError):
            pass
    return val


def _df_to_plain_values(df: pd.DataFrame) -> list[list[Any]]:
    """掃描歷史等純文字表：欄位標題 + 列資料，無 NaN。"""
    cols = list(df.columns)
    rows: list[list[Any]] = [cols]
    if df.empty:
        return rows
    av_idx = cols.index("頭像") if "頭像" in cols else -1
    for tup in df.itertuples(index=False, name=None):
        line: list[Any] = []
        for j, v in enumerate(tup):
            if j == av_idx:
                line.append(_avatar_cell_value(v))
            else:
                line.append(_sanitize_cell_for_api(v))
        rows.append(line)
    return rows


def _image_formula(url: str) -> str:
    if pd.isna(url):
        return ""
    u = str(url or "").strip().replace('"', '""')
    if not u:
        return ""
    return f'=IMAGE("{u}")'


def _avatar_cell_value(val: Any) -> Any:
    """掃描歷史頭像欄：URL 轉 =IMAGE()，其餘照舊。"""
    s = str(val or "").strip()
    if not s:
        return ""
    if s.startswith("=IMAGE"):
        return s
    if s.startswith("http://") or s.startswith("https://"):
        return _image_formula(s)
    return _sanitize_cell_for_api(val)


def _df_to_values_with_images(
    df: pd.DataFrame, avatar_urls: list[str | None]
) -> list[list[Any]]:
    cols = [c for c in OUTPUT_COLUMNS if c in df.columns]
    header = cols
    rows: list[list[Any]] = [header]
    if df.empty:
        return rows
    av_col = cols.index("頭像") if "頭像" in cols else -1
    for i, (_, rec) in enumerate(df.iterrows()):
        line: list[Any] = []
        for c in cols:
            if c == "頭像" and av_col >= 0 and i < len(avatar_urls):
                u = avatar_urls[i]
                line.append(_image_formula(u) if u else "")
            else:
                v = rec.get(c, "")
                if pd.isna(v):
                    line.append("")
                else:
                    line.append(v)
        rows.append(line)
    return rows


def _unmerge_sheet_grid(
    sheet_id: int, end_row: int = 10000, end_col: int = 30
) -> dict[str, Any]:
    """解除工作表上一大片區域的合併（clear() 不會移除合併狀態，易與新 merge 衝突）。"""
    return {
        "unmergeCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "endRowIndex": end_row,
                "startColumnIndex": 0,
                "endColumnIndex": end_col,
            }
        }
    }


def _clear_basic_filter(sheet_id: int) -> dict[str, Any]:
    """清除工作表篩選，避免 mergeCells 遇到 filtered row 失敗。"""
    return {"clearBasicFilter": {"sheetId": sheet_id}}


def _merge_requests_for_sessions(
    df: pd.DataFrame, sheet_id: int
) -> list[dict[str, Any]]:
    if df.empty or len(df) < 2:
        return []
    if not all(c in df.columns for c in SESSION_MERGE_COLUMNS):
        return []
    col_idx = {c: list(df.columns).index(c) for c in SESSION_MERGE_COLUMNS}
    reqs: list[dict[str, Any]] = []
    n = len(df)
    i = 0
    while i < n:
        j = i + 1
        while j < n and _rows_same_session_block(df, i, j):
            j += 1
        if j > i + 1:
            # 列 0 為標題；資料列 i 對應試算表列索引 1+i。endRowIndex 為「不包含」。
            start_row = 1 + i
            end_row = j + 1
            for c in SESSION_MERGE_COLUMNS:
                ci = col_idx[c]
                reqs.append(
                    {
                        "mergeCells": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": start_row,
                                "endRowIndex": end_row,
                                "startColumnIndex": ci,
                                "endColumnIndex": ci + 1,
                            },
                            "mergeType": "MERGE_ALL",
                        }
                    }
                )
        i = j
    return reqs


def _format_requests(
    sheet_id: int,
    num_rows: int,
    num_cols: int,
    *,
    header_row_index: int = 0,
) -> list[dict[str, Any]]:
    """全表微軟正黑體；標題列淺藍底，其餘列白底（避免未指定底色時與標題同色）。"""
    if num_rows < 1 or num_cols < 1:
        return []
    body_font = {
        "textFormat": {
            "fontFamily": "Microsoft JhengHei",
            "fontSize": 11,
        },
        "verticalAlignment": "MIDDLE",
        "wrapStrategy": "WRAP",
        "backgroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
    }
    header_font = {
        "textFormat": {
            "fontFamily": "Microsoft JhengHei",
            "fontSize": 11,
            "bold": True,
        },
        "backgroundColor": {"red": 0.85, "green": 0.9, "blue": 0.95},
        "verticalAlignment": "MIDDLE",
        "wrapStrategy": "WRAP",
    }
    out: list[dict[str, Any]] = []
    # 資料列：白底＋內文（不含標題列）
    if header_row_index + 1 < num_rows:
        out.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": header_row_index + 1,
                        "endRowIndex": num_rows,
                        "startColumnIndex": 0,
                        "endColumnIndex": num_cols,
                    },
                    "cell": {"userEnteredFormat": body_font},
                    "fields": "userEnteredFormat(textFormat,backgroundColor,verticalAlignment,wrapStrategy)",
                }
            }
        )
    if 0 <= header_row_index < num_rows:
        out.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": header_row_index,
                        "endRowIndex": header_row_index + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": num_cols,
                    },
                    "cell": {"userEnteredFormat": header_font},
                    "fields": "userEnteredFormat(textFormat,backgroundColor,verticalAlignment,wrapStrategy)",
                }
            }
        )
    return out


def _column_width_requests(sheet_id: int, num_cols: int) -> list[dict[str, Any]]:
    """像素寬度（約略）。"""
    defaults = [140, 120, 100, 60, 110, 90, 90, 90, 160, 72, 280]
    widths = (defaults + [120] * num_cols)[:num_cols]
    return [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": i,
                    "endIndex": i + 1,
                },
                "properties": {"pixelSize": w},
                "fields": "pixelSize",
            }
        }
        for i, w in enumerate(widths)
    ]


def load_history_from_gsheet(cfg: dict[str, Any], columns: list[str]) -> pd.DataFrame:
    sh = _open_spreadsheet(cfg)
    try:
        ws = sh.worksheet(HISTORY_SHEET_NAME)
    except gspread.WorksheetNotFound:
        return pd.DataFrame(columns=columns)
    rows = ws.get_all_values()
    if not rows:
        return pd.DataFrame(columns=columns)
    header, data = rows[0], rows[1:]
    df = pd.DataFrame(data, columns=header[: len(header)])
    if "異動類型" not in df.columns:
        return pd.DataFrame(columns=columns)
    df = df.reindex(columns=columns)
    if "掃描時間" in df.columns:
        df["掃描時間"] = df["掃描時間"].astype(str).str.strip()
    return df


def _history_header_columns() -> list[str]:
    return ["掃描時間", "異動類型"] + [
        c for c in OUTPUT_COLUMNS if c != "掃描時間"
    ]


def _write_history_sheet(
    sh: Any,
    hw: Any,
    *,
    history_append_df: pd.DataFrame | None,
    history_reset: bool,
) -> None:
    """掃描歷史：僅在重設或本次有異動時寫入；插入新列、不改既有列與欄寬。"""
    header = _history_header_columns()
    hid = hw.id

    if history_reset:
        hw.clear()
        hw.update("A1", [header], value_input_option="USER_ENTERED")
        return

    if history_append_df is None or history_append_df.empty:
        return

    plain = _df_to_plain_values(history_append_df)
    data_rows = plain[1:] if len(plain) > 1 else []
    if not data_rows:
        return

    existing = hw.get_all_values()
    if not existing:
        hw.update("A1", [header], value_input_option="USER_ENTERED")

    n = len(data_rows)
    ncol = len(data_rows[0])
    sh.batch_update(
        {
            "requests": [
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": hid,
                            "dimension": "ROWS",
                            "startIndex": 1,
                            "endIndex": 1 + n,
                        },
                        "inheritFromBefore": False,
                    }
                }
            ]
        }
    )
    hw.update(
        f"A2:{_col_a1(ncol)}{1 + n}",
        data_rows,
        value_input_option="USER_ENTERED",
    )


def write_google_sheets(
    df: pd.DataFrame,
    avatar_urls: list[str | None],
    cfg: dict[str, Any],
    *,
    history_append_df: pd.DataFrame | None = None,
    history_reset: bool = False,
) -> str:
    sh = _open_spreadsheet(cfg)

    # --- sessions ---
    ws = _ensure_worksheet(sh, "sessions")
    ws.clear()
    values = _df_to_values_with_images(df, avatar_urls)
    if values:
        end_r = len(values)
        end_c = len(values[0])
        rng = f"A1:{_col_a1(end_c)}{end_r}"
        ws.update(rng, values, value_input_option="USER_ENTERED")

    sheet_id = ws.id
    num_rows = len(values)
    num_cols = len(values[0]) if values else len(OUTPUT_COLUMNS)

    reqs: list[dict[str, Any]] = [
        _clear_basic_filter(sheet_id),
        _unmerge_sheet_grid(sheet_id, end_row=max(num_rows + 500, 2000), end_col=max(num_cols + 5, 20))
    ]
    if cfg.get("merge_session_cells", True):
        reqs.extend(_merge_requests_for_sessions(df, sheet_id))
    reqs.extend(_format_requests(sheet_id, max(num_rows, 1), num_cols))
    reqs.extend(_column_width_requests(sheet_id, num_cols))

    if reqs:
        sh.batch_update({"requests": reqs})

    # --- 掃描歷史：僅插入新列，不 clear、不調欄寬 ---
    if history_reset or (
        history_append_df is not None and not history_append_df.empty
    ):
        hw = _ensure_worksheet(sh, HISTORY_SHEET_NAME)
        _write_history_sheet(
            sh,
            hw,
            history_append_df=history_append_df,
            history_reset=history_reset,
        )

    sid = (cfg.get("google_sheet_id") or "").strip()
    return f"https://docs.google.com/spreadsheets/d/{sid}/edit"
