# LINE 萬能助理 Bot

用 FastAPI + Claude API 打造的 LINE Official Account 互動機器人。
預設行為：任何文字訊息都會丟給 Claude 產生智能回覆，並保留每個使用者的對話記憶（記憶體版，重啟會清空）。

## 專案結構

```
line-bot/
├── app/
│   ├── main.py              # FastAPI 入口，webhook 路由與簽章驗證
│   ├── config.py             # 環境變數設定
│   ├── line_client.py        # LINE Messaging API 封裝（reply / push）
│   ├── claude_client.py      # Claude API 封裝
│   ├── storage/               # 對話歷史儲存（自動選擇記憶體版或 Google Drive 版）
│   │   ├── __init__.py         # 依環境變數決定用哪個實作
│   │   ├── memory_store.py     # 記憶體版
│   │   └── drive_store.py      # Google Drive 版
│   └── handlers.py           # 指令路由 + 訊息處理邏輯（要加新功能改這裡）
├── requirements.txt
├── .env.example
├── Procfile                  # 給 Render/Railway 用的啟動指令
└── README.md
```

## 一、申請 LINE Official Account 與 Messaging API

1. 到 [LINE Developers Console](https://developers.line.biz/console/) 登入（用你的 LINE 帳號）
2. 建立一個 Provider（如果還沒有）
3. 在該 Provider 底下建立一個 **Messaging API** channel
4. 進入該 channel 的設定頁：
   - **Basic settings** 頁籤 → 複製 `Channel secret`
   - **Messaging API** 頁籤 → 往下拉，`Issue` 一組 `Channel access token (long-lived)` 並複製
   - 同一頁把 **Webhook** 打開（Use webhook → Enabled）
   - 建議把「Auto-reply messages」「Greeting messages」關掉，避免跟你的 bot 邏輯衝突

## 二、取得 Anthropic API Key

到 [console.anthropic.com](https://console.anthropic.com/) 建立 API Key。

## 三、本機設定

```bash
cd line-bot
python -m venv venv
source venv/bin/activate  # Windows 用 venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# 編輯 .env，填入剛才取得的三組金鑰
```

本機啟動：

```bash
export $(cat .env | xargs)   # 或用 python-dotenv 載入，看你習慣
uvicorn app.main:app --reload --port 8000
```

## 四、本機測試（用 ngrok 讓 LINE 連得到你的電腦）

LINE 的 webhook 網址必須是公開的 HTTPS，本機開發可以用 ngrok 打洞：

```bash
ngrok http 8000
```

會得到一個網址，例如 `https://xxxx.ngrok-free.app`，
把 `https://xxxx.ngrok-free.app/webhook` 填進 LINE Developers Console
的 **Messaging API → Webhook URL**，按 **Verify** 應該會顯示成功。

用手機掃 LINE Developers Console 上的 QR Code 加該官方帳號好友，
傳訊息測試看看有沒有收到 Claude 的回覆。

## 五、正式部署（三選一，都有免費額度可先試）

### 選項 A：Render
1. 把這個資料夾 push 到 GitHub repo
2. Render.com → New → Web Service → 連接該 repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Environment 頁籤填入三組環境變數
6. 部署完成後會拿到一個 `https://xxx.onrender.com` 網址，
   把 `/webhook` 接到 LINE Console 的 Webhook URL

### 選項 B：Railway
流程類似 Render，`railway.app` 新建專案、連 GitHub repo，
在 Variables 頁籤填環境變數即可，會自動偵測 Procfile。

### 選項 C：Google Cloud Run（你已經在用 GCP 生態系的話比較順手）
```bash
gcloud run deploy line-bot \
  --source . \
  --set-env-vars LINE_CHANNEL_ACCESS_TOKEN=xxx,LINE_CHANNEL_SECRET=xxx,ANTHROPIC_API_KEY=xxx \
  --allow-unauthenticated
```

部署完成後一樣把回傳的網址 + `/webhook` 填回 LINE Console。

## 六、把對話記錄存進 Google Drive（選用，但建議正式使用時開啟）

**重要觀念**：你在跟 Claude 聊天時授權的 Google Drive，只在「你本人跟 AI 對話」時有效，
是你的個人帳號登入。但 LINE bot 是一支**無人值守、跑在伺服器上**的程式，
沒辦法跳出瀏覽器讓你登入——所以它要存取 Drive，得用 **Service Account**（服務帳號），
這是 Google 提供給「程式對程式」使用的機器帳號，跟你平常登入 Drive 是兩回事。

設定步驟：

1. 到 [Google Cloud Console](https://console.cloud.google.com/) 建立（或選擇既有）專案
2. **API 和服務 → 程式庫**，搜尋並啟用 **Google Drive API**
3. **API 和服務 → 憑證 → 建立憑證 → 服務帳號**，填名稱後建立
4. 建好後點進該服務帳號 → **金鑰** 頁籤 → **新增金鑰 → JSON**，會下載一個 JSON 檔案，
   *這份檔案本身就是密碼，不要 commit 進 GitHub*
5. 打開下載的 JSON，複製其中 `client_email` 欄位的值（長得像
   `xxx@xxx.iam.gserviceaccount.com`）
6. 到你的 Google Drive，建立一個資料夾（例如「LINE Bot 對話記錄」），
   右鍵 **共用**，把上一步的 `client_email` 加進去，權限設 **編輯者**
   （這一步很關鍵：沒分享的話服務帳號完全看不到你的資料夾）
7. 從該資料夾的網址複製 folder ID：
   `https://drive.google.com/drive/folders/【這一段】`
8. 把整份下載的 JSON 內容填進環境變數 `GOOGLE_SERVICE_ACCOUNT_JSON`，
   folder ID 填進 `GOOGLE_DRIVE_FOLDER_ID`（部署平台的環境變數欄位通常支援多行貼上）

設定完成後不用改任何程式碼，`app/storage/__init__.py` 會自動偵測並切換到 Drive 版儲存。
每個 LINE 使用者的對話記錄會存成資料夾裡的 `conv_<userId>.json`。

**這個做法的取捨**：
- 優點：重啟服務、換部署平台都不會遺失對話記錄，你也可以直接在 Drive 裡打開檔案看內容
- 缺點：每則訊息會多一次 Drive API 的網路往返（讀取快取後才需要），
  比純記憶體版稍慢；且 Drive API 有每使用者/每 100 秒的配額限制，
  高流量情境不適合，正式高用量建議換成 Redis 或資料庫

## 七、如何擴充功能

這個架構刻意留了擴充點，之後想加功能改這兩個地方就好：

1. **新增指令**：在 `app/handlers.py` 的 `handle_text_message` 裡加 `if text == "/xxx":` 判斷，
   例如接你的 TWSE 股價腳本、查詢資料庫、串接行事曆等。
2. **新增事件類型**：在 `app/main.py` 的 `dispatch_event` 裡，
   `event_type` 除了 `message`、`follow`、`postback`，
   LINE 還有 `unfollow`（被封鎖）、`join`（被拉進群組）等，可依需要處理。
3. **主動推播/排程通知**：`line_client.push_text(user_id, text)` 可以搭配
   cron job 或排程服務（例如每天早上推播天氣/股價摘要），
   但要注意免費方案每月 push 訊息數有配額限制。

## 八、已知限制，正式上線前建議處理

- **未設定 Google Drive 時是記憶體版**：服務重啟、或部署平台自動 restart / 多副本，記錄會消失或不同步。
  設定第六節的 Google Drive 儲存可以解決這個問題；高流量情境則建議改用 Redis 或資料庫。
- **免費方案的 sleep 問題**：Render/Railway 免費方案閒置一段時間會休眠，
  第一則訊息可能會因為喚醒延遲導致 LINE 端逾時（reply token 過期）。
  正式使用建議升級付費方案或用 Cloud Run（按request計費、冷啟動較快）。
- **沒有速率限制與濫用防護**：目前任何加好友的人都能無限次呼叫 Claude API，
  正式上線前建議加上每人每日訊息數上限，避免 API 費用失控。
