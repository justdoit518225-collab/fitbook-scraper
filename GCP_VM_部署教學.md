# FitBook 爬蟲 — Google Cloud 小 VM 部署教學

用一台 **GCP 小 VM** 在雲端定時執行 `scrape_fitbook.py`，寫入你的 Google 試算表。  
**人不在家、只有手機** 也能在試算表看到最新資料（電腦不必開著）。

---

## 你需要準備

| 項目 | 說明 |
|------|------|
| Google 帳號 | 可開 GCP 專案、綁定信用卡（新帳號常有免費額度） |
| 本機已有專案 | 資料夾 `爬蟲_APC`（含 `scrape_fitbook.py`） |
| `google_service_account.json` | 服務帳戶金鑰（勿上傳到公開 Git） |
| FitBook **Cookie** | 登入後從瀏覽器複製（會過期，需偶爾更新） |
| 試算表已共用 | 已把試算表「編輯」權限給服務帳戶的 `client_email` |

---

## 第一步：建立 GCP 專案與 VM

1. 開啟 [Google Cloud Console](https://console.cloud.google.com/)
2. 上方選單建立或選擇一個**專案**（例如 `fitbook-scraper`）
3. 左側 **「Compute Engine」→「VM 執行個體」→「建立執行個體」**

建議設定：

| 欄位 | 建議值 |
|------|--------|
| 名稱 | `fitbook-scraper` |
| 區域 | `asia-east1`（台灣）或 `asia-east2`（香港） |
| 機器類型 | `e2-micro`（1 vCPU、1GB RAM，最便宜） |
| 開機磁碟 | Ubuntu 22.04 LTS，**10 GB** 即可 |
| 防火牆 | 勾選「允許 HTTP」**可不必**（爬蟲只需**對外連線**，不需對外開 port） |
| 外部 IP | **建立**（方便 SSH） |

4. 按 **建立**，等 1～2 分鐘 VM 變成綠色「執行中」。

> **費用粗估：** `e2-micro` 在亞洲約每月數美元～十幾美元（依使用與免費額度而異）。不用時可在 Console **停止** VM 省錢，但停止期間**不會**自動爬蟲。

---

## 第二步：在本機安裝 gcloud（只做一次）

1. 下載安裝 [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
2. 開啟 **PowerShell**，執行：

```powershell
gcloud init
gcloud auth login
```

3. 設定預設專案（把 `你的專案ID` 換成 Console 上的專案 ID）：

```powershell
gcloud config set project 你的專案ID
```

---

## 第三步：用 SSH 連到 VM

在 PowerShell（把 `fitbook-scraper` 換成你的 VM 名稱、`asia-east1-a` 換成你的區域）：

```powershell
gcloud compute ssh fitbook-scraper --zone=asia-east1-a
```

第一次會問是否建立 SSH 金鑰，選 **Yes**。  
成功後會進入 Linux 終端，提示符類似 `user@fitbook-scraper:~$`。

---

## 第四步：把專案檔案傳到 VM

**先在本機另開一個 PowerShell 視窗**（不要關 SSH 那個），執行：

```powershell
# 在 VM 上建立目錄
gcloud compute ssh fitbook-scraper --zone=asia-east1-a --command="sudo mkdir -p /opt/fitbook-scraper && sudo chown $env:USERNAME:$env:USERNAME /opt/fitbook-scraper 2>/dev/null || sudo chown $(whoami):$(whoami) /opt/fitbook-scraper"

# 上傳程式（路徑請依你的實際專案目錄調整）
gcloud compute scp --recurse "c:\Users\user\爬蟲_APC\scrape_fitbook.py" "c:\Users\user\爬蟲_APC\google_sheets_export.py" "c:\Users\user\爬蟲_APC\requirements.txt" "c:\Users\user\爬蟲_APC\config.json" "c:\Users\user\爬蟲_APC\google_service_account.json" "c:\Users\user\爬蟲_APC\deploy" fitbook-scraper:/opt/fitbook-scraper/ --zone=asia-east1-a
```

若 `scp` 對中文路徑有問題，可先在本機把專案複製到 `C:\fitbook-scraper` 再上傳：

```powershell
xcopy "c:\Users\user\爬蟲_APC" "C:\fitbook-scraper\" /E /I /Y
gcloud compute scp --recurse C:\fitbook-scraper\* fitbook-scraper:/opt/fitbook-scraper/ --zone=asia-east1-a
```

**不要**把 `last_scan_state.json` 當成必傳（VM 上會自動產生新的比對基準）。

---

## 第五步：在 VM 上執行安裝腳本

回到 **SSH 視窗**，執行：

```bash
cd /opt/fitbook-scraper
sudo bash deploy/gcp/install_on_vm.sh
```

腳本會：

- 安裝 Python 與虛擬環境
- 安裝 `requirements.txt`
- 設定 **每小時第 50 分** 執行一次（與你原本 `run_hourly` 相同）
- 日誌寫入 `/var/log/fitbook-scraper/scrape.log`
- 時區設為 `Asia/Taipei`（若系統支援）

---

## 第六步：設定 Cookie（重要）

Cookie 會過期，建議用環境變數檔（權限 600）：

```bash
sudo nano /opt/fitbook-scraper/.env
```

內容範例（從瀏覽器登入 FitBook 後複製完整 Cookie，或至少 `laravel_session=...`）：

```
FITBOOK_COOKIE=laravel_session=xxxx; 其他=...
```

存檔後：

```bash
sudo chmod 600 /opt/fitbook-scraper/.env
```

若你已在 `config.json` 的 `cookie_header` 填好 Cookie，也可不建 `.env`（但更新 Cookie 時要改檔案並重新上傳或 nano 編輯）。

---

## 第七步：手動試跑一次

```bash
sudo /opt/fitbook-scraper/run_scrape.sh
```

看輸出是否成功。若有錯誤：

```bash
sudo tail -50 /var/log/fitbook-scraper/scrape.log
```

成功後用手機或電腦打開 Google 試算表 **`sessions`** 分頁確認有更新。

---

## 之後怎麼維護（只有手機時）

| 要做的事 | 做法 |
|----------|------|
| 看最新資料 | 直接開 Google 試算表 App |
| Cookie 過期 | 用筆電 SSH 進 VM 改 `.env`；或本機改完再 `scp` 上傳 `config.json` |
| 看有沒有在跑 | SSH 後：`sudo tail -f /var/log/fitbook-scraper/scrape.log` |
| 立刻跑一次 | SSH 後：`sudo /opt/fitbook-scraper/run_scrape.sh` |
| 省錢暫停 | GCP Console 停止 VM（期間不會自動爬） |

### 從手機 SSH（進階）

可安裝 **Termius**、**JuiceSSH**（Android）或 **Termius**（iOS），匯入你用 `gcloud` 產生的 SSH 金鑰，連到 VM 外部 IP。  
或繼續用筆電 `gcloud compute ssh`。

---

## 常見問題

### 1. 試算表沒更新

- 服務帳戶是否為試算表**編輯者**？
- `google_sheet_id` 是否正確？
- Cookie 是否過期？（網頁能登入不代表 API Cookie 還有效）

### 2. `Permission denied` 寫入試算表

確認 JSON 金鑰路徑為 `/opt/fitbook-scraper/google_service_account.json`，且 `config.json` 內檔名一致。

### 3. VM 記憶體不足

`e2-micro` 通常夠用。若 OOM，可改成 `e2-small`。

### 4. 想改執行時間

編輯 `/etc/cron.d/fitbook-scraper` 裡的分鐘數（預設 `50`），或改 `install_on_vm.sh` 後重跑安裝。

### 5. 本機 Windows 排程還要嗎？

VM 在跑之後，可**停用**本機 `FitBook_SCRAPE_SESSIONS` 與桌面 `.bat`，避免重複寫入。若兩邊同時跑，可能重複追加「掃描歷史」。

---

## 安全提醒

- **不要**把 `google_service_account.json`、`config.json`（含 Cookie）放到公開 GitHub。
- VM 上的 `.env` 設 `chmod 600`。
- 不需要對外開放 HTTP port；爬蟲只需**出站**連線。

---

## 快速指令總表

```powershell
# 本機：SSH 進 VM
gcloud compute ssh fitbook-scraper --zone=asia-east1-a

# 本機：上傳更新後的 config
gcloud compute scp "C:\fitbook-scraper\config.json" fitbook-scraper:/opt/fitbook-scraper/ --zone=asia-east1-a
```

```bash
# VM 上：手動執行
sudo /opt/fitbook-scraper/run_scrape.sh

# VM 上：看日誌
sudo tail -f /var/log/fitbook-scraper/scrape.log
```

完成以上步驟後，爬蟲會在雲端每小時自動跑，你用手機看試算表即可。
