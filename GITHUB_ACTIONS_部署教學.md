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

## iPhone 主畫面一鍵「跑爬蟲」（捷徑 App 詳細教學）

GitHub App **無法**把 Run workflow 放在首頁。下面用 iPhone **「捷徑」** 做一顆主畫面按鈕，按下去 = 在 GitHub 上執行一次 **FitBook Scrape**（與 Actions 裡按 Run workflow 相同）。

預計時間：第一次約 **15～20 分鐘**（含申請 Token），之後按一下即可。

---

### 第一部分：申請 GitHub Token（只做一次）

Token 像「遙控器密碼」，讓捷徑有權限幫你觸發 workflow。

1. 用 iPhone **Safari** 開啟（建議登入 GitHub 帳號）：  
   https://github.com/settings/tokens  

2. 點 **Generate new token** → 選 **Generate new token (fine-grained token)**  
   （若只有 Classic 也可，見文末「替代方案」）

3. **Token name** 隨意填，例如：`iPhone-FitBook`

4. **Expiration** 建議選 **90 days** 或 **No expiration**（到期要重做 Token）

5. **Repository access** 選 **Only select repositories** → 勾選 **`fitbook-scraper`**

6. 展開 **Repository permissions**，設定：
   - **Actions** → **Read and write**
   - **Metadata** → **Read**（通常預設就有）

7. 拉到最下面點 **Generate token**

8. 畫面會出現以 `github_pat_` 開頭的一長串 → 點 **複製**  
   - **只會顯示這一次**，請貼到「備忘錄」或「密碼」App 暫存  
   - **不要**傳給任何人、不要貼到群組

---

### 第二部分：建立捷徑（逐步操作）

#### 步驟 1：開新捷徑

1. 打開 iPhone **「捷徑」** App（紫色圖示）
2. 下方點 **「捷徑」** 分頁
3. 右上角 **＋**（建立捷徑）
4. 若出現「建立個人捷徑」等說明，點掉或略過即可

#### 步驟 2～4：兩種作法（新版 iOS 請用「作法 A」）

> **說明：** 舊教學裡的 **「神奇變數」** 在 **iOS 17／18 以後** 常已看不到這四個字。  
> 現在改成：**點欄位 →「選擇變數」**，或點鍵盤上方的 **藍色／灰色小標籤**（寫著「文字」「AuthHeader」等）。  
> 若你找不到，請直接用下面 **作法 A（設定變數）**，最穩。

---

##### 作法 A（推薦）：用「設定變數」— 不依賴神奇變數

**2A-1：Token 文字**

1. **加入動作** → 搜尋 **文字**
2. 內容**一行**貼好（`Bearer ` 後面有空格，再接 token）：

```text
Bearer github_pat_你的完整Token貼在這裡
```

**2A-2：把 Token 存成變數**

1. **加入動作** → 搜尋 **設定變數**（英文 *Set variable*）
2. **變數** 名稱輸入：`AuthHeader`（可自訂，但下面要選同名）
3. **輸入** 欄：點一下 → 在鍵盤上方或彈出清單選 **文字**（上一步的輸出）  
   - 若看到 **選擇變數** → 點進去 → 選 **文字**  
   - 選對後欄位裡會出現類似 `AuthHeader` 或「文字」的**小標籤**，不是空白

**2A-3：JSON 文字**

1. 再加 **文字**，內容：

```json
{"ref":"main"}
```

**2A-4：把 JSON 存成變數**

1. 再加 **設定變數**
2. 變數名稱：`JsonBody`
3. **輸入** 選上一步的 **文字** 輸出（同 2A-2 的選法）

**2A-5：取得 URL 內容**

1. **加入動作** → **取得 URL 內容**
2. **URL** 貼上：

```text
https://api.github.com/repos/justdoit518225-collab/fitbook-scraper/actions/workflows/scrape-fitbook.yml/dispatches
```

3. **顯示更多** → **方法** 選 **POST**
4. **要求內文**：
   - 類型 **JSON**（或「檔案」）
   - 內容欄點一下 → **選擇變數** → 選 **`JsonBody`**（或選「文字」若你沒命名變數、選第二個文字動作）
5. **標頭** 新增 4 筆：

| 標頭名稱 | 標頭值 |
|----------|--------|
| `Accept` | `application/vnd.github+json`（直接打字貼上） |
| `Authorization` | 點欄位 → **選擇變數** → 選 **`AuthHeader`** |
| `Content-Type` | `application/json` |
| `X-GitHub-Api-Version` | `2022-11-28` |

---

##### 作法 B：不建「設定變數」，新版介面直接選上一動作

**B-1～B-2：** 同樣做兩個 **文字** 動作（Token 一行、JSON 一行），**可不做**設定變數。

**B-3：取得 URL 內容**

- **要求內文**：點內容欄 → 看鍵盤**上方**是否出現 **「文字」** 小標籤 → 點它（要選**第二個**文字，內容是 `{"ref":"main"}` 那個）  
  - 或點欄位 → **選擇變數** / **Select Variable** → 點列表裡對應的 **文字**
- **Authorization 標頭值**：點值欄 → 選**第一個** **文字**（Bearer 開頭那個）  
  - 選對時會變成**一行小膠囊**卡在欄位裡，不要整段 token 用手打

**如何分辨選對哪個「文字」：**  
在變數列表或預覽裡，一個開頭是 `Bearer`，另一個是 `{`；選錯會 401。

---

##### 作法 C（最簡）：JSON 不用變數，手動貼

若 **要求內文** 一直選不到變數：

1. **要求內文** 類型選 JSON
2. 內容欄**直接手打**（不要選變數）：

```json
{"ref":"main"}
```

3. **Authorization** 仍要用變數或「設定變數」的 `AuthHeader`（token 太長不建議手打）

**作法 A 完成後的動作順序：**

```text
文字（Bearer + Token）
設定變數 → AuthHeader
文字（{"ref":"main"}）
設定變數 → JsonBody
取得 URL 內容（POST + 4 標頭）
顯示通知
```

#### 步驟 5：成功提示（建議）

1. **加入動作** → 搜尋 **顯示通知**
2. 標題：`FitBook`
3. 內文：`已送出爬蟲，約 1～3 分鐘後請刷新試算表`

（也可加 **「震動」** 動作，按完會震一下。）

#### 步驟 6：命名並試跑

1. 點左上角 **完成** 或 **✓**
2. 點上方名稱（預設「新捷徑」）→ 改名為 **`FitBook 更新`**
3. 點名稱下方的 **▶ 播放** 試跑一次

**如何確認成功：**

1. 若出現通知「已送出爬蟲…」且**沒有紅色錯誤** → 多半成功  
2. 打開 **GitHub App** → 進入 **justdoit518225-collab/fitbook-scraper** → **Actions**  
3. 應看到新的 **FitBook Scrape** 在跑或剛跑完（黃點/綠勾）  
4. 約 1～3 分鐘後開 **Google 試算表** 看 `sessions` 是否更新  

---

### 第三部分：加到主畫面（像 App 圖示）

1. 在「捷徑」裡打開 **FitBook 更新** 這條捷徑
2. 點右上角 **ⓘ**（資料圖示）或 **⋯** → **詳細資料**
3. 選 **加入主畫面**
4. 可改圖示名稱、選顏色 → 點右上角 **加入**
5. 回到主畫面，會多一顆 **FitBook 更新** 圖示

之後：**點主畫面圖示** → 等通知 → 去試算表刷新。

---

### 第四部分：捷徑動作順序檢查（請對照）

**作法 A（推薦）** 從上到下應為：

```text
1. 文字          → Bearer github_pat_...（一行）
2. 設定變數      → AuthHeader = 上一步文字
3. 文字          → {"ref":"main"}
4. 設定變數      → JsonBody = 上一步文字
5. 取得 URL 內容 → POST + 4 標頭 + JsonBody
6. 顯示通知
```

順序不要顛倒；**Authorization** 一定要選到 `AuthHeader`（或第一個文字），不是 JsonBody。

---

### 常見錯誤排除

| 現象 | 可能原因 | 處理 |
|------|----------|------|
| 捷徑跑完但 Actions 沒新紀錄 | Token 權限不足或 URL 打錯 | 確認 Actions 為 Read and write；URL 完整貼上 |
| 出現 401 / Bad credentials | Token 錯或 Authorization 沒加 Bearer | 確認 `Bearer `+token 在同一行 |
| 出現 404 | 倉庫名或 workflow 檔名錯 | 確認網址含 `justdoit518225-collab/fitbook-scraper` 與 `scrape-fitbook.yml` |
| 出現 422 | JSON 錯 | 內文必須是 `{"ref":"main"}`，分支名為 `main` |
| 「取得 URL 內容」失敗 | 沒網路 | 改用 Wi‑Fi 或關 VPN 再試 |

---

### 替代方案：Classic Token（若找不到 fine-grained）

1. https://github.com/settings/tokens → **Generate new token (classic)**
2. 勾選 **`repo`**
3. 產生後同樣做成 `Bearer ghp_xxxx...` 放進步驟 2 的文字

---

### 注意事項

- Token 外洩 = 別人可代你跑 workflow，**勿截圖分享捷徑內容**
- 此捷徑只「觸發」GitHub Actions；**Cookie 過期**仍要到網頁 **Secrets** 更新 `FITBOOK_COOKIE`
- 已有每小時 :50 自動跑，手動捷徑可當「我想馬上看最新資料」時使用
- 不要連續狂按多次（會排很多個 workflow）

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
