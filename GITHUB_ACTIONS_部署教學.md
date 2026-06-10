# FitBook 爬蟲 — GitHub Actions 部署教學

用 **GitHub Actions** 在雲端定時執行 `scrape_fitbook.py`，寫入 Google 試算表。  
**不用開電腦、不用 VPS**，有手機看試算表即可；需要「立刻跑一次」可在 GitHub App 手動觸發。

---

## 原理

| 項目 | 說明 |
|------|------|
| 排程 | 每 **10 分鐘（台北時間）** 自動跑（:00、:10、:20…） |
| 每週重設 | 每週一 **08:00（台北）** workflow **FitBook Weekly Reset**（`--reset-baseline`） |
| 手動 | GitHub 網頁 / App → Actions → **Run workflow** |
| 機密 | Cookie、服務帳戶 JSON 放在 **Secrets**，不進 Git |
| 比對基準 | 存在試算表隱藏分頁 **`_scan_baseline`**（本機與雲端共用同一份；不再使用 Actions Cache） |
| 掃描歷史 | 僅記 **新增／刪除**；解析失敗或異常時自動略過，不寫入也不更新基準 |
| 每週一 08:00 | GitHub Actions **FitBook Weekly Reset** 自動清空歷史並重設基準 |

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
- **Value：** 須同時含 **`XSRF-TOKEN`** 與 **`laravel_session`**

**建議：** 本機雙擊 **`export_fitbook_cookie.bat`** → 在跳出 Edge 登入 FitBook → 等待 120 秒 → 自動寫入 `config.json`。

手動（Edge / Chrome）若找不到 Cookies：

1. 登入 https://www.fit-book.com.tw/urlname459/564  
2. F12 → **Network** → 重新整理 → 點任一 `fit-book.com.tw` 請求  
3. **Headers** → **Request Headers** → 複製 **`cookie:`** 整段（要有 `XSRF-TOKEN` 與 `laravel_session`）  
4. 貼到 GitHub Secret，以及 `config.json` 的 `cookie_header`

程式會讀環境變數 `FITBOOK_COOKIE`（`config.github.json` 已設 `cookie_env`）。

**重要：** 必須**一整行**、不要貼 `Cookie:` 字樣、不要換行。

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

之後會 **每 10 分鐘（台北）** 自動跑。

---

## 只有手機時怎麼用

| 需求 | 做法 |
|------|------|
| 看資料 | Google 試算表 App |
| 立刻更新一次 | 主畫面 **FitBook 更新** 捷徑（見下方教學），或 **GitHub App** → Actions → **Run workflow** |
| Cookie 過期 | 用電腦瀏覽器更新 Secret `FITBOOK_COOKIE`（Settings → Secrets） |
| 看有沒有跑 | GitHub App / 網頁 → Actions 看最近紀錄 |

---

## iPhone 主畫面一鍵「跑爬蟲」（新版 iOS 捷徑完整教學）

> **適用：** iOS 17／18 及更新版本（含 iOS 26）。  
> **說明：** 新版「捷徑」**沒有「神奇變數」** 字樣；改用手動 **「設定變數」** + **「選擇變數」**／鍵盤上方 **小標籤**。  
> 本教學**只走一條路**，照順序做即可。

**你會得到什麼：** 主畫面多一顆 **FitBook 更新** 按鈕 → 按一下 = GitHub 執行一次 **FitBook Scrape**（等同網頁 Actions 的 Run workflow）。

**預計時間：** 第一次約 20 分鐘；之後每次約 5 秒。

---

### 零、新版介面名詞對照（先看這段）

| 你可能看到的 | 意思 |
|--------------|------|
| **加入動作** | 在捷徑裡新增一步 |
| **文字** | 放一段固定文字（Token、JSON） |
| **設定變數** | 把上一步結果「取名」存起來（英文 *Set variable*） |
| **選擇變數** | 點輸入欄後，從清單選先前步驟的輸出 |
| 鍵盤上方的 **小標籤** | 寫著「文字」「AuthHeader」等，點一下插入 |
| **取得 URL 內容** | 發送網路請求（英文 *Get Contents of URL*） |
| **標頭** | HTTP Headers |
| **要求內文** | POST 要送出的內容（Request Body） |

**選變數的三種方式（任一出現就用）：**

1. 點空白欄位 → 點 **選擇變數** → 點 `AuthHeader` 或 **文字**  
2. 點空白欄位 → 鍵盤**上方**出現小標籤 → 點 **AuthHeader** 或 **文字**  
3. 點欄位左側的 **×** 或 **變數圖示** → 從清單選  

選對後，欄位裡會出現**一行膠囊**（不是空白、也不是要你手打整串 token）。

---

### 一、申請 GitHub Token（只做一次）

Token = 讓捷徑有權限代你「按」Run workflow。

1. iPhone 用 **Safari** 開（請先登入 GitHub）：  
   https://github.com/settings/tokens  

2. 點綠色 **Generate new token**  

3. 選 **Generate new token (fine-grained token)**  
   - 若畫面只有 Classic，見本文最後 **附錄：Classic Token**

4. 填寫：
   - **Token name：** `iPhone-FitBook`（隨意）
   - **Expiration：** 建議 **90 days**（到期要重做）
   - **Repository access：** 選 **Only select repositories** → 只勾 **`fitbook-scraper`**
   - **Repository permissions** 往下找：
     - **Actions** → 改成 **Read and write**
     - **Metadata** → **Read**（通常已有）

5. 最下面 **Generate token**

6. 出現 `github_pat_` 開頭的一長串 → 點 **複製**  
   - 貼到 **備忘錄** 暫存（只顯示這一次）  
   - **勿**傳給他人、勿貼群組

---

### 二、建立捷徑（共 8 個動作，請依序）

#### 動作 1：開新捷徑

1. 打開 **捷徑** App（紫色圖示）  
2. 底部分頁選 **捷徑**  
3. 右上角 **＋**  
4. 出現空白編輯畫面即可（可關閉「新手上路」提示）

---

#### 動作 2：文字 — 登入用 Token（一行）

1. 點 **加入動作**（或底部搜尋）  
2. 搜尋 **文字** → 點 **文字**  
3. 在輸入框內**一次貼完整行**（範例格式）：

```text
Bearer github_pat_xxxxxxxxxxxxxxxx
```

**注意：**

- `Bearer` 後面**一定要有一個空格**  
- `github_pat_` 換成你備忘錄裡複製的整串  
- **整段在同一行**，不要斷成兩行  

4. （可選）長按動作標題 **文字** → 重新命名為 `Token文字`

---

#### 動作 3：設定變數 — 取名 AuthHeader

1. **加入動作** → 搜尋 **設定變數**（或 **Set variable**）  
2. **變數**（名稱）欄輸入：`AuthHeader`（大小寫建議照抄）  
3. **輸入** 欄（要接上一步的 Token）：
   - **點一下「輸入」欄**（游標閃爍）  
   - 看鍵盤**上方**有沒有 **文字** 或 **Token文字** 小標籤 → **點它**  
   - 若沒有標籤：點 **選擇變數** → 在清單點 **文字**（通常是上一個動作）  
   - 成功時「輸入」欄會出現 **AuthHeader** 或 **文字** 的**膠囊**，不是空白  

4. 確認：展開動作 2 的「文字」仍顯示 `Bearer github_pat_...`

---

#### 動作 4：文字 — 觸發分支 JSON

1. **加入動作** → **文字**  
2. 內容**照抄**（含大括號、雙引號）：

```json
{"ref":"main"}
```

3. （可選）重新命名為 `JSON文字`

---

#### 動作 5：設定變數 — 取名 JsonBody

1. **加入動作** → **設定變數**  
2. **變數** 名稱：`JsonBody`  
3. **輸入** 欄：同動作 3 的方式，選**上一個「文字」**（內容是 `{"ref":"main"}` 那個）  
   - 清單裡若有兩個「文字」，看預覽：一個是 `Bearer` 開頭、一個是 `{` 開頭 → 選 `{` 那個  
4. 成功時「輸入」欄有 **JsonBody** 膠囊  

> **若 JSON 變數怎麼都選不上：** 可跳過動作 4、5，在動作 6 的「要求內文」**直接手打** `{"ref":"main"}`（見動作 6 備註）。

---

#### 動作 6：取得 URL 內容 — 送出到 GitHub（核心）

1. **加入動作** → 搜尋 **URL** → 選 **取得 URL 內容**  

2. **URL** 欄貼上（長按貼上，避免少字）：

```text
https://api.github.com/repos/justdoit518225-collab/fitbook-scraper/actions/workflows/scrape-fitbook.yml/dispatches
```

3. 點 **顯示更多**（或 **▼**）展開  

4. **方法** → 改成 **POST**（預設常是 GET，必須改）  

5. **要求內文**（或 Request Body）：
   - 若有 **類型**：選 **JSON** 或 **檔案**  
   - **內容** 欄：
     - **方式甲：** 點欄位 → **選擇變數** → 選 **JsonBody**  
     - **方式乙：** 直接手打 `{"ref":"main"}`（沒做動作 4、5 時用這個）  

6. **標頭**（Headers）— 點 **新增標頭** / **+** 共 **4 筆**：

| # | 標頭名稱（鍵） | 標頭值（值）怎麼填 |
|---|----------------|-------------------|
| 1 | `Accept` | 直接貼：`application/vnd.github+json` |
| 2 | `Authorization` | 點「值」欄 → **選擇變數** → 選 **AuthHeader**（勿選 JsonBody） |
| 3 | `Content-Type` | 直接貼：`application/json` |
| 4 | `X-GitHub-Api-Version` | 直接貼：`2022-11-28` |

**Authorization 檢查（最常錯）：**

- 「值」欄應是 **AuthHeader** 膠囊，不是手打 token  
- 不要選成 JsonBody，否則 GitHub 回 401  

7. 其餘開關保持預設（不用填帳號／密碼）

---

#### 動作 7：顯示通知 — 按完有提示

1. **加入動作** → **顯示通知**  
2. **標題：** `FitBook`  
3. **內文：** `已送出爬蟲，約 1～3 分鐘後請刷新試算表`  
4. （可選）再加 **震動**

---

#### 動作 8：命名並試跑

1. 點左上角 **完成**（或 **✓**）  
2. 點頂部名稱 **新捷徑** → 改名 **`FitBook 更新`**  
3. 點 **▶**（播放）試跑  

**成功怎麼看：**

1. 出現通知、捷徑**沒有紅字錯誤**  
2. 打開 **GitHub App** → 倉庫 **fitbook-scraper** → **Actions** → 看到新的 **FitBook Scrape**（黃色進行中或綠色完成）  
3. 1～3 分鐘後開 **Google 試算表** → **sessions** 分頁刷新  

---

### 三、加到 iPhone 主畫面

1. 在「捷徑」列表點開 **FitBook 更新**  
2. 點右上角 **ⓘ**（圓圈 i）或 **⋯** → **詳細資料**  
3. 點 **加入主畫面**  
4. 可改顯示名稱、選圖示顏色 → 右上角 **加入**  
5. 回主畫面，會多一顆 App 圖示  

以後：**點圖示** → 等通知 → 刷新試算表。

---

### 四、完成後請對照（動作順序）

從**上到下**必須是這 7～8 段（JSON 若手打可少 2 段）：

```text
① 文字           Bearer github_pat_...（一行）
② 設定變數         變數名 AuthHeader ← 輸入選 ①
③ 文字           {"ref":"main"}
④ 設定變數         變數名 JsonBody   ← 輸入選 ③
⑤ 取得 URL 內容    POST + URL + 4 標頭 + JsonBody（或手打 JSON）
⑥ 顯示通知
```

**簡化版（JSON 手打時）：**

```text
① 文字 → Bearer token
② 設定變數 → AuthHeader
③ 取得 URL 內容 → POST，內文手打 {"ref":"main"}，Authorization 選 AuthHeader
④ 顯示通知
```

---

### 五、常見問題

| 狀況 | 原因 | 處理 |
|------|------|------|
| 找不到「選擇變數」 | 要先點**輸入欄**才會出現 | 點欄位 → 看鍵盤上方小標籤 |
| 輸入欄一直是空白 | 沒選到上一動作 | 重做動作 3，選「文字」膠囊 |
| 401 / Bad credentials | Authorization 錯 | 確認 Bearer+空格+token；標頭值選 AuthHeader |
| 404 | URL 錯 | 完整貼上教學裡的網址 |
| 422 | 分支名錯 | 內文必須 `{"ref":"main"}` |
| Actions 沒新紀錄 | Token 權限不足 | Actions 改 Read and write |
| 試算表沒更新 | Cookie 過期 | 更新 GitHub Secret `FITBOOK_COOKIE`（見下方章節） |
| 捷徑成功但資料舊 | 爬蟲還在跑 | 等 1～3 分鐘再刷新 |

---

### 附錄：Classic Token（沒有 fine-grained 時）

1. https://github.com/settings/tokens  
2. **Generate new token (classic)**  
3. 勾選 **`repo`** → Generate  
4. 複製 `ghp_` 開頭的 token  
5. 在動作 2 貼成：`Bearer ghp_你的token`（同樣 Bearer 後有空格）

---

### 注意

- **勿**把含 Token 的捷徑截圖給別人  
- 捷徑只**觸發** GitHub Actions；**Cookie** 仍要在 GitHub **Secrets** 維護  
- 已有每 **10 分鐘** 自動跑；手動按鈕給「想立刻更新」時用  
- 勿連續狂按（會排很多個 workflow）

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

每次爬蟲約 1～3 分鐘，每 10 分鐘 1 次 → 每月約 **4000～8000 分鐘**，**私人 repo 免費額度（約 2000 分/月）可能不夠**；可改 public repo、付費方案，或改回較低頻率。

---

## 每週一 08:00 自動重設（可選）

雲端已內建 workflow **FitBook Weekly Reset**（`reset-scan-baseline.yml`）：

- **時間：** 每週一 **08:00 台北時間**（workflow 以 `cron: 0 0 * * 1` UTC 對應，並設 `TZ=Asia/Taipei`；若曾變成下午才跑，多半是未套用台灣時區）
- **動作：** 等同 `python scrape_fitbook.py --reset-baseline`（清空掃描歷史、重建比對基準）
- **手動：** Actions → **FitBook Weekly Reset** → Run workflow

本機若要同時間重設（需電腦開機）：

```powershell
powershell -ExecutionPolicy Bypass -File .\install_windows_reset_task.ps1
```

取消：`uninstall_windows_reset_task.ps1`

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
| `.github/workflows/scrape-fitbook.yml` | 每 10 分鐘爬蟲 |
| `.github/workflows/reset-scan-baseline.yml` | 每週一 08:00 重設比對基準 |
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
