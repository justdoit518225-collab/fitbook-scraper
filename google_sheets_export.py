# -*- coding: utf-8 -*-
"""
Google 試算表匯出（服務帳戶）。

設定步驟（摘要）：
1. Google Cloud Console 建立專案 → 啟用「Google Sheets API」。
2. 建立「服務帳戶」→ 建立 JSON 金鑰，下載後放到專案目錄（例如 google_service_account.json）。
3. 新建或開啟一個試算表，網址列 id 為 .../d/<這段>/edit → 填入 config 的 google_sheet_id。
4. 將試算表「共用」給 JSON 內 client_email（編輯者）。

頭像欄（J）使用 =IMAGE("url")；頭像連結欄（L）寫入 URL 並以 API 套用可點擊超連結。
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

import gspread
import pandas as pd
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials

T = TypeVar("T")
_GSPREAD_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

HISTORY_SHEET_NAME = "掃描歷史"
BASELINE_SHEET_NAME = "_scan_baseline"
BASELINE_COLUMNS = [
    "預約頁面",
    "會員暱稱",
    "頭像_url",
    "課程名稱",
    "場館標籤",
    "場次日期",
    "星期",
    "時段",
    "已報名人數",
    "開放名額",
    "剩餘名額",
]
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

# sessions 分頁 L 欄（OUTPUT_COLUMNS 之後）：擷取 J 欄 IMAGE 公式內的圖片 URL
AVATAR_URL_COLUMN = "頭像連結"

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


def _gspread_api_error_code(err: APIError) -> int | None:
    resp = getattr(err, "response", None)
    code = getattr(resp, "status_code", None) if resp is not None else None
    if isinstance(code, int):
        return code
    m = re.search(r"\[(\d{3})\]", str(err))
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def _gspread_call_with_retry(
    fn: Callable[[], T],
    *,
    tries: int = 4,
    pause: float = 2.0,
) -> T:
    """Google Sheets API 偶發 503/429 時短暫重試。"""
    last_err: APIError | None = None
    for attempt in range(tries):
        try:
            return fn()
        except APIError as e:
            last_err = e
            code = _gspread_api_error_code(e)
            if code in _GSPREAD_RETRYABLE_STATUS and attempt < tries - 1:
                time.sleep(pause * (attempt + 1))
                continue
            raise
    if last_err is not None:
        raise last_err
    raise RuntimeError("gspread retry failed")


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
    key = (cfg.get("google_sheet_id") or "").strip()
    return _gspread_call_with_retry(lambda: gc.open_by_key(key))


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


def _avatar_url_plain_cell(url: str | None) -> str:
    """L 欄先寫入純 URL 文字，再由 batchUpdate 套上可點擊超連結。"""
    return ("" if url is None else str(url)).strip()


def parse_avatar_image_url(cell: Any) -> str:
    """從 =IMAGE(\"url\") 或純 URL 字串取出圖片網址。"""
    s = str(cell or "").strip()
    if not s:
        return ""
    m = re.match(r'^=IMAGE\s*\(\s*"((?:[^"]|"")*)"\s*\)', s, re.I)
    if m:
        return m.group(1).replace('""', '"').strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return ""


def baseline_member_avatar_map(
    state: dict[str, dict[str, Any]],
) -> dict[tuple[str, str], str]:
    """基準狀態 → (預約頁面, 會員暱稱) → 頭像 URL（刪除異動還原用）。"""
    out: dict[tuple[str, str], str] = {}
    for url, entry in (state or {}).items():
        if not isinstance(entry, dict):
            continue
        avatars = entry.get("member_avatars") or {}
        if not isinstance(avatars, dict):
            continue
        page = str(url).strip()
        for name, raw in avatars.items():
            u = str(raw or "").strip()
            n = str(name or "").strip()
            if page and n and u:
                out[(page, n)] = u
    return out


def load_sessions_avatar_map(sh: Any) -> dict[tuple[str, str], str]:
    """讀取 sessions 分頁 L 欄（頭像連結）；L 空時改解析 J 欄 =IMAGE()。"""
    try:
        ws = sh.worksheet("sessions")
    except Exception:
        return {}
    rows = ws.get_all_values()
    if len(rows) < 2:
        return {}
    header = [str(h).strip() for h in rows[0]]
    try:
        i_page = header.index("預約頁面")
        i_name = header.index("會員暱稱")
        i_link = header.index(AVATAR_URL_COLUMN)
    except ValueError:
        return {}
    i_image = header.index("頭像") if "頭像" in header else -1
    out: dict[tuple[str, str], str] = {}
    for r in rows[1:]:
        def _cell(i: int) -> str:
            if i < 0 or i >= len(r):
                return ""
            return str(r[i] or "").strip()

        page, name = _cell(i_page), _cell(i_name)
        if not page or not name:
            continue
        url = parse_avatar_image_url(_cell(i_link))
        if not url and i_image >= 0:
            url = parse_avatar_image_url(_cell(i_image))
        if url:
            out[(page, name)] = url
    return out


def enrich_diff_df_avatars(
    diff_df: pd.DataFrame,
    *,
    sessions_map: dict[tuple[str, str], str],
    baseline_avatar_map: dict[tuple[str, str], str] | None = None,
    scrape_map: dict[tuple[str, str], str] | None = None,
) -> pd.DataFrame:
    """以 sessions L 欄 URL 補齊異動列頭像（與試算表顯示一致）。"""
    if diff_df is None or diff_df.empty:
        return diff_df
    out = diff_df.copy()
    if "頭像" not in out.columns:
        out["頭像"] = ""
    baseline_avatar_map = baseline_avatar_map or {}
    scrape_map = scrape_map or {}
    for idx, row in out.iterrows():
        page = str(row.get("預約頁面", "") or "").strip()
        name = str(row.get("會員暱稱", "") or "").strip()
        kind = str(row.get("異動類型", "") or "").strip()
        if not page or not name:
            continue
        key = (page, name)
        url = parse_avatar_image_url(row.get("頭像", ""))
        if kind == "刪除":
            url = (
                url
                or baseline_avatar_map.get(key, "")
                or sessions_map.get(key, "")
                or scrape_map.get(key, "")
            )
        else:
            url = (
                url
                or sessions_map.get(key, "")
                or scrape_map.get(key, "")
                or baseline_avatar_map.get(key, "")
            )
        if url:
            out.at[idx, "頭像"] = url
    return out


def _avatar_column_hyperlink_requests(
    sheet_id: int,
    avatar_urls: list[str | None],
    *,
    col_index: int = 11,
    header_rows: int = 1,
) -> list[dict[str, Any]]:
    """L 欄套用 Sheets API 原生超連結（HYPERLINK 公式在試算表常無法點擊）。"""
    if not avatar_urls:
        return []
    link_blue = {"red": 0.07, "green": 0.45, "blue": 0.82}
    row_data: list[dict[str, Any]] = []
    for raw in avatar_urls:
        u = _avatar_url_plain_cell(raw)
        if u:
            row_data.append(
                {
                    "values": [
                        {
                            "userEnteredValue": {"stringValue": u},
                            "userEnteredFormat": {
                                "textFormat": {
                                    "link": {"uri": u},
                                    "foregroundColor": link_blue,
                                    "underline": True,
                                },
                            },
                        }
                    ]
                }
            )
        else:
            row_data.append(
                {"values": [{"userEnteredValue": {"stringValue": ""}}]}
            )
    return [
        {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": header_rows,
                    "endRowIndex": header_rows + len(avatar_urls),
                    "startColumnIndex": col_index,
                    "endColumnIndex": col_index + 1,
                },
                "rows": row_data,
                "fields": "userEnteredValue,userEnteredFormat.textFormat",
            }
        }
    ]


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
    header = cols + [AVATAR_URL_COLUMN]
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
        u = avatar_urls[i] if i < len(avatar_urls) else None
        line.append(_avatar_url_plain_cell(u))
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
    """像素寬度（約略）。L 欄頭像連結依試算表手動拉寬參考值 1324px。"""
    defaults = [140, 120, 100, 60, 110, 90, 90, 90, 160, 72, 280, 1324]
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


def _repair_history_sheet_layout(hw: Any) -> None:
    """修正曾寫入「課程名稱」導致 C 欄後全欄錯位（D 欄起與標題不符）的舊資料。"""
    expected = _history_header_columns()
    ncol = len(expected)
    existing = hw.get_all_values()
    if not existing:
        return
    header = existing[0]
    misaligned = header != expected or any(len(r) > ncol for r in existing[1:])
    if not misaligned:
        return
    fixed: list[list[Any]] = []
    for i, raw in enumerate(existing):
        row = list(raw)
        if i > 0 and len(row) > ncol:
            # 多出的第 3 欄（原 D 欄視覺錯位）為「課程名稱」，刪除後 E→D 左移對齊標題
            if len(row) >= 3:
                row = row[:2] + row[3:]
        fixed.append((row + [""] * ncol)[:ncol])
    fixed[0] = expected
    hw.clear()
    if fixed:
        hw.update(
            f"A1:{_col_a1(ncol)}{len(fixed)}",
            fixed,
            value_input_option="USER_ENTERED",
        )


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

    _repair_history_sheet_layout(hw)

    sheet_cols = _history_header_columns()
    df_write = history_append_df.reindex(columns=sheet_cols)
    plain = _df_to_plain_values(df_write)
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


def open_spreadsheet(cfg: dict[str, Any]) -> Any:
    """供主程式取得 spreadsheet 物件（共用同一連線執行基準讀寫）。"""
    return _open_spreadsheet(cfg)


def _hide_worksheet(sh: Any, ws: Any) -> None:
    try:
        sh.batch_update(
            {
                "requests": [
                    {
                        "updateSheetProperties": {
                            "properties": {"sheetId": ws.id, "hidden": True},
                            "fields": "hidden",
                        }
                    }
                ]
            }
        )
    except Exception:
        pass


def load_baseline_from_sheet(sh: Any) -> dict[str, dict[str, Any]]:
    """從 _scan_baseline 分頁讀取基準。分頁不存在回傳空字典；API 錯誤則拋出。"""
    try:
        ws = sh.worksheet(BASELINE_SHEET_NAME)
    except gspread.WorksheetNotFound:
        return {}
    rows = _gspread_call_with_retry(lambda: ws.get_all_values())
    if len(rows) < 2:
        return {}
    header = rows[0]
    state: dict[str, dict[str, Any]] = {}
    for r in rows[1:]:
        rec = dict(zip(header, r))
        url = (rec.get("預約頁面") or "").strip()
        name = (rec.get("會員暱稱") or "").strip()
        if not url or not name:
            continue
        entry = state.setdefault(
            url,
            {"members": [], "meta": {}, "member_avatars": {}},
        )
        entry["members"].append(name)
        avatar = (rec.get("頭像_url") or "").strip()
        if avatar:
            entry["member_avatars"][name] = avatar
        if not entry["meta"]:
            for c in BASELINE_COLUMNS:
                if c in ("預約頁面", "會員暱稱", "頭像_url"):
                    continue
                v = rec.get(c, "")
                if v != "":
                    entry["meta"][c] = v
            entry["meta"]["預約頁面"] = url
    return state


def save_baseline_to_sheet(sh: Any, state: dict[str, dict[str, Any]]) -> None:
    """完整覆寫 _scan_baseline 分頁（每位會員一列）。"""
    ws = _ensure_worksheet(sh, BASELINE_SHEET_NAME, rows=4000, cols=len(BASELINE_COLUMNS))
    ws.clear()
    rows: list[list[Any]] = [list(BASELINE_COLUMNS)]
    for url, entry in state.items():
        if not isinstance(entry, dict):
            continue
        meta = entry.get("meta") or {}
        avatars = entry.get("member_avatars") or {}
        members = entry.get("members") or []
        for name in members:
            row = [url, str(name), str(avatars.get(name, "") or "")]
            for c in BASELINE_COLUMNS:
                if c in ("預約頁面", "會員暱稱", "頭像_url"):
                    continue
                row.append(_sanitize_cell_for_api(meta.get(c, "")))
            rows.append(row)
    end_c = len(BASELINE_COLUMNS)
    end_r = len(rows)
    ws.update(
        f"A1:{_col_a1(end_c)}{end_r}",
        rows,
        value_input_option="USER_ENTERED",
    )
    _hide_worksheet(sh, ws)


def clear_history_sheet(sh: Any) -> None:
    """清空 掃描歷史 分頁，僅留標題列。"""
    hw = _ensure_worksheet(sh, HISTORY_SHEET_NAME)
    hw.clear()
    header = _history_header_columns()
    hw.update("A1", [header], value_input_option="USER_ENTERED")


def write_google_sheets(
    df: pd.DataFrame,
    avatar_urls: list[str | None],
    cfg: dict[str, Any],
    *,
    history_append_df: pd.DataFrame | None = None,
    history_reset: bool = False,
    spreadsheet: Any | None = None,
) -> str:
    sh = spreadsheet if spreadsheet is not None else _open_spreadsheet(cfg)

    # --- sessions ---
    ws = _ensure_worksheet(sh, "sessions")
    sheet_id = ws.id
    values = _df_to_values_with_images(df, avatar_urls)
    num_rows = len(values)
    num_cols = len(values[0]) if values else len(OUTPUT_COLUMNS)

    # clear() 不會移除合併格；若先 update 再 unmerge，非左上角列的 A～H 會寫不進去而變空白。
    pre_reqs: list[dict[str, Any]] = [
        _clear_basic_filter(sheet_id),
        _unmerge_sheet_grid(
            sheet_id,
            end_row=max(num_rows + 500, 2000),
            end_col=max(num_cols + 5, 20),
        ),
    ]
    sh.batch_update({"requests": pre_reqs})

    ws.clear()
    if values:
        end_r = len(values)
        end_c = len(values[0])
        rng = f"A1:{_col_a1(end_c)}{end_r}"
        ws.update(rng, values, value_input_option="USER_ENTERED")

    post_reqs: list[dict[str, Any]] = []
    if cfg.get("merge_session_cells", True):
        post_reqs.extend(_merge_requests_for_sessions(df, sheet_id))
    post_reqs.extend(_format_requests(sheet_id, max(num_rows, 1), num_cols))
    post_reqs.extend(_column_width_requests(sheet_id, num_cols))
    # 須在 format 之後，否則 repeatCell 會蓋掉 textFormat.link
    post_reqs.extend(
        _avatar_column_hyperlink_requests(sheet_id, avatar_urls, col_index=num_cols - 1)
    )

    if post_reqs:
        sh.batch_update({"requests": post_reqs})

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
