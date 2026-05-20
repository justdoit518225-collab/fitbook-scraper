# FitBook 爬蟲 — GitHub Actions 部署教學

用 **GitHub Actions** 在雲端定時執行 `scrape_fitbook.py`，寫入 Google 試算表。  
**不用開電腦、不用 VPS**，有手機看試算表即可；需要「立刻跑一次」可在 GitHub App 手動觸發。

---

## 原理

| 項目 | 說明 |
|------|------|
| 排程 | 每小時 **第 50 分（台北時間）** 自動跑 |
| 手動 | GitHub 網頁 / App → Actions → **Run workflow** |
| 機密 | Cookie、服務帳戶 JSON 放在 **Secrets**，不進 Git |
| 比對檔 | `last_scan_state.json` 用 Actions **Cache** 保留，供「掃描歷史」比對 |

---

## 第一步：建立 GitHub 倉庫（建議私人）

1. 登入 [GitHub](https://github.com/)
2. **New repository** → 名稱例如 `fitbook-scraper`
3. 選 **Private（私人）**（避免 workflow 被外人複製濫用）
4. 不要勾選「Add README」也可（我們會從本機推送）

---

## 第二步：本機把專案推上 GitHub

在本機 **PowerShell**（專案目錄）：

```powershell
cd "c:\Users\user\爬蟲_APC"

git init
git add scrape_fitbook.py google_sheets_export.py requirements.txt config.github.json .github/workflows/scrape-fitbook.yml GITHUB_ACTIONS_部署教學.md config.json.example .gitignore deploy/
git commit -m "Add FitBook scraper and GitHub Actions workflow"

git branch -M main
git remote add origin https://github.com/你的帳號/fitbook-scraper.git
git push -u origin main
```

**不要** `git add` 這些檔案：

- `config.json`（可能有 Cookie）
- `google_service_account.json`
- `last_scan_state.json`
- `.env`

（已在 `.gitignore` 排除。）

---

## 第三步：設定 GitHub Secrets

倉庫頁面 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

### 1. `FITBOOK_COOKIE`

- **Name：** `FITBOOK_COOKIE`
- **Value：** 瀏覽器登入 FitBook 後的 Cookie（至少含 `laravel_session=...`；建議整段 Cookie 貼上）

取得方式（Chrome）：

1. 登入 https://www.fit-book.com.tw  
2. F12 → **Application** → **Cookies** → 選網域  
3. 或 **Network** 任選請求 → **Request Headers** → 複製 `Cookie:` 整行（不要 `Cookie:` 前綴也可，程式會用環境變數整段當 header 值時需在 config 用 cookie_env）

程式會讀環境變數 `FITBOOK_COOKIE`（`config.github.json` 已設 `cookie_env`）。

**重要：** Secret 必須是**一整行**（不可換行）。若出現 `InvalidHeader`，請 Update Secret：刪掉所有換行，不要貼 `Cookie:` 字樣。

### 2. `GOOGLE_SERVICE_ACCOUNT_JSON`

- **Name：** `GOOGLE_SERVICE_ACCOUNT_JSON`
- **Value：** 打開本機 `google_service_account.json`，**整份 JSON 全文複製貼上**（從 `{` 到 `}`）

**常見錯誤（會出現 `JSONDecodeError: Extra data`）：**

- 只貼了 `client_email` 一行，不是整份 JSON  
- 在 Secret 外層又包了一層 `"` 引號  
- 貼了兩份 JSON 接在一起  
- 結尾多了說明文字  

正確做法：用記事本打開 `google_service_account.json` → 全選 → 複製 → 貼到 Secret 的 Value（可多行，沒關係）

---

## 第四步：確認試算表設定

編輯倉庫裡的 **`config.github.json`**（推送前或 GitHub 網頁編輯）：

- `google_sheet_id`：你的試算表 ID（網址 `.../d/這段/edit`）
- 場館、`match_all_templates` 等與本機一致即可

試算表須已 **共用** 給服務帳戶 JSON 內的 `client_email`（**編輯者**）。

---

## 第五步：第一次執行

1. 倉庫 → **Actions**
2. 左側選 **FitBook Scrape**
3. 右側 **Run workflow** → **Run workflow**

約 1～3 分鐘後：

- 綠勾 = 成功 → 手機打開 Google 試算表 `sessions` 分頁
- 紅叉 = 失敗 → 點進該次 run 看 **Run scraper** 步驟的 log（不會顯示 Secret 內容）

之後會 **每小時 :50（台北）** 自動跑。

---

## 只有手機時怎麼用

| 需求 | 做法 |
|------|------|
| 看資料 | Google 試算表 App |
| 立刻更新一次 | 安裝 **GitHub App** → 你的倉庫 → **Actions** → **FitBook Scrape** → **Run workflow** |
| Cookie 過期 | 用電腦瀏覽器更新 Secret `FITBOOK_COOKIE`（Settings → Secrets） |
| 看有沒有跑 | GitHub App / 網頁 → Actions 看最近紀錄 |

---

## iPhone 主畫面一鍵「跑爬蟲」（捷徑 App）

GitHub App **無法**把 Run workflow 放在首頁；可用 iPhone 內建 **「捷徑」** 呼叫 GitHub API，效果等同按 Run workflow。

### A. 先建立 GitHub Token（只做一次）

1. 用 Safari 開：https://github.com/settings/tokens  
2. **Generate new token** → 建議選 **Fine-grained token**  
3. 設定：
   - Repository access：**Only select** → 選 `fitbook-scraper`
   - Permissions → **Actions**：Read and write  
   - **Metadata**：Read（通常會自動勾）
4. 產生後**複製 token**（只顯示一次，請存到密碼管理器）

（也可用 Classic token，勾選 `repo` 權限。）

### B. 建立捷徑

1. 打開 iPhone **「捷徑」** App → 右下角 **＋**  
2. 新增動作 **「文字」**，內容貼上（把 `你的TOKEN` 換成剛才的 token）：

```text
你的TOKEN
```

3. 再新增 **「取得 URL 內容」**，設定：

| 項目 | 值 |
|------|-----|
| URL | `https://api.github.com/repos/justdoit518225-collab/fitbook-scraper/actions/workflows/scrape-fitbook.yml/dispatches` |
| 方法 | **POST** |
| 標頭 | 見下方 |
| 要求內文 | **JSON**，內容 `{"ref":"main"}` |

**標頭（在「取得 URL 內容」裡新增標頭）：**

| 鍵 | 值 |
|----|-----|
| Accept | `application/vnd.github+json` |
| Authorization | `Bearer` + 空格 + 上一步「文字」的變數（點選「神奇變數」選該文字） |
| Content-Type | `application/json` |
| X-GitHub-Api-Version | `2022-11-28` |

4. 建議再加 **「顯示通知」**：標題「FitBook」，內文「已送出爬蟲，約 1～3 分鐘後看試算表」  
5. 捷徑命名例如：**FitBook 更新**  
6. 點捷徑名稱旁 **ⓘ** → **加入主畫面**（可自訂圖示）

### C. 使用方式

- 主畫面點 **FitBook 更新** → 等通知  
- 打開 **GitHub App** → 倉庫 **Actions** 可看到新的 run 在跑  
- 完成後刷新 Google 試算表 `sessions`

### 注意

- Token 外洩等於別人能代你跑 workflow，勿分享、勿截圖  
- 此捷徑只負責「觸發」；Cookie 過期仍要到 GitHub **Secrets** 更新  
- 與每小時自動排程可並存，勿在短時間內狂按多次

---

## 更新 Cookie（常見維護）

1. 本機瀏覽器重新登入 FitBook，複製新 Cookie  
2. GitHub 倉庫 → **Settings** → **Secrets** → `FITBOOK_COOKIE` → **Update**  
3. Actions → **Run workflow** 測試一次  

不必重推程式碼。

---

## 免費額度（約略）

| 倉庫類型 | Actions 免費分鐘 |
|----------|------------------|
| 私人 repo | 每月約 2000 分鐘 |
| 公開 repo | 較寬鬆 |

每次爬蟲約 1～3 分鐘，每小時 1 次 → 每月約 1500 分鐘內，**私人 repo 通常夠用**。

---

## 與本機排程並存？

**不要** 同時開：

- Windows 工作排程 / `run_hourly.py` / 桌面 `.bat`  
- **以及** GitHub Actions  

會重複寫入、重複追加「掃描歷史」。選一種即可。

---

## 常見錯誤

| 現象 | 處理 |
|------|------|
| Missing secret | 檢查兩個 Secret 名稱是否完全一致（大小寫） |
| 試算表沒變 | Cookie 過期；或服務帳戶沒有試算表編輯權 |
| JSON 錯誤 | `GOOGLE_SERVICE_ACCOUNT_JSON` 要完整 JSON，不要有多餘引號或換行錯誤 |
| 0 筆資料 | 檢查 `config.github.json` 的場館設定；Cookie 是否有效 |

---

## 檔案說明

| 檔案 | 用途 |
|------|------|
| `.github/workflows/scrape-fitbook.yml` | Actions 工作流程 |
| `config.github.json` | 非機密設定（可進 Git） |
| `config.json` | 本機用，勿推送 |
| `google_service_account.json` | 僅放 Secret，勿推送 |

---

## 快速檢查清單

- [ ] 私人倉庫已建立並 push 程式  
- [ ] Secrets：`FITBOOK_COOKIE`、`GOOGLE_SERVICE_ACCOUNT_JSON`  
- [ ] `config.github.json` 的 `google_sheet_id` 正確  
- [ ] 試算表已共用給服務帳戶 email  
- [ ] Actions 手動 Run 成功  
- [ ] 本機 Windows 排程已停用（避免重複）  

完成後即可只靠 GitHub + 手機試算表使用。
