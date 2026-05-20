#!/usr/bin/env python3
"""GitHub Actions：從 Secrets 寫入 config.json 與 google_service_account.json。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _load_service_account_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("\ufeff"):
        raw = raw.lstrip("\ufeff")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        print(
            "GOOGLE_SERVICE_ACCOUNT_JSON 不是合法 JSON。\n"
            "請到 Secret 貼上「整份」google_service_account.json（從 { 到 }），\n"
            "不要加引號包住、不要貼兩次、不要貼網址或 client_email 單獨一行。",
            file=sys.stderr,
        )
        print(f"解析錯誤: {err}", file=sys.stderr)
        raise SystemExit(1) from err


def main() -> None:
    root = Path.cwd()
    sa_raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not sa_raw:
        print("Missing secret: GOOGLE_SERVICE_ACCOUNT_JSON", file=sys.stderr)
        raise SystemExit(1)

    cfg_src = root / "config.github.json"
    if not cfg_src.is_file():
        print(f"Missing {cfg_src}", file=sys.stderr)
        raise SystemExit(1)

    cfg_dst = root / "config.json"
    cfg_dst.write_text(cfg_src.read_text(encoding="utf-8"), encoding="utf-8")

    data = _load_service_account_json(sa_raw)
    sa_path = root / "google_service_account.json"
    sa_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {cfg_dst.name} and {sa_path.name}")


if __name__ == "__main__":
    main()
