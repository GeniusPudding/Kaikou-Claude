[English](README.md) · [繁體中文](README.zh-TW.md)

# Kaikou-Claude(開口即克)

[Claude Code](https://docs.anthropic.com/claude/docs/claude-code) 與 [Claude Desktop](https://claude.ai/download) 的離線中文語音輸入,跨平台可用。按住熱鍵講話,放開自動轉錄、貼上、送出。底層使用 [faster-whisper](https://github.com/SYSTRAN/faster-whisper),不需任何 API key。

> **備註:** 焦點偵測會匹配所有 process tree 中含有 `claude.exe` 或 `node … claude` 的視窗,因此 Claude Code（終端機、VS Code 擴充套件）和 Claude Desktop 都能使用。`<voice>` 語音標記和 ASR 容錯（透過 `CLAUDE.md`）僅在 Claude Code 中生效；Claude Desktop 收到的是原始轉錄文字。

## 平台支援

| 平台 | 狀態 | 熱鍵 | 備註 |
|------|------|------|------|
| Windows | **穩定** | **空白鍵(按住)** | 短按 = 一般空白,長按 ≥ 250ms = 語音 |
| macOS | 🚧 尚未驗證 | F9(按住) | 需授權「輔助使用」權限 |
| Linux | 🚧 尚未驗證 | F9(按住) | 僅限 X11,需安裝 `xdotool` |

Windows 用低階鍵盤 hook 能選擇性攔截空白鍵而不影響打字和 IME。macOS / Linux 無法做到,改用 F9。

## 運作原理

```
┌──────────────────────────────────────────────────────┐
│  你打開 `claude`                                      │
│    → SessionStart hook 執行 scripts/start-voice.{ps1,sh}│
│    → daemon 在背景啟動                                 │
│    → 載入 Whisper 模型（自動偵測 CUDA）                 │
│    → 安裝鍵盤 hook                                    │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│  你按住熱鍵(Win 空白鍵 / Mac·Linux F9)                  │
│    → 焦點檢查：前景視窗 process tree 含 claude？        │
│      • Windows: Win32 GetForegroundWindow + psutil    │
│      • macOS:   NSWorkspace + psutil                  │
│      • Linux:   xdotool + psutil                      │
│    → 有 → 透過 sounddevice 開始錄音                    │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│  你放開按鍵                                           │
│    → faster-whisper 在本地轉錄音檔                     │
│    → 文字 + <voice> 標記複製到剪貼簿                    │
│    → Ctrl+V (macOS 用 Cmd+V) 貼到焦點視窗              │
│    → Enter 送出（若 VOICE_AUTO_SUBMIT=1）              │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│  你關閉 `claude`                                      │
│    → SessionEnd hook 遞減 session 計數器               │
│    → 歸零才真的殺 daemon（多開安全）                    │
└──────────────────────────────────────────────────────┘
```

全程本地運行 — 不需網路、不需 API key、資料不離開你的電腦。Whisper 模型從 Hugging Face 下載一次後快取在本地磁碟。

## 特色

- **自動偵測焦點。** 熱鍵只在 Claude Code 是前景視窗時生效,其他地方完全透明。
- **自動貼上並送出。** 轉錄完經剪貼簿貼入,按 Enter 送出。
- **語音標記。** 每筆轉錄自動加上 `<voice>` 後綴,讓 Claude 知道這是語音輸入並容忍 ASR 錯字(詳見 [語音標記](#語音標記))。
- **自動選 CUDA。** 偵測不到 GPU 或載入失敗時回退 CPU `int8`。
- **多開安全。** Session 計數器確保多開時不會誤殺 daemon。

## 安裝

### Windows

```powershell
git clone <repo-url> kaikou-claude
cd kaikou-claude
.\install.ps1
```

### macOS / Linux

```bash
git clone <repo-url> kaikou-claude
cd kaikou-claude
./install.sh
```

安裝腳本會建 `.venv`、安裝依賴、若 `.env` 不存在就寫一份預設,並把 `SessionStart` / `SessionEnd` hook 合併到 `~/.claude/settings.json`。冪等 — 隨時重跑都安全,不會重複、不會蓋到其他 hook。

安裝完後第一次開 `claude` 會下載 Whisper 權重(`small` 約 500 MB,`medium` 約 1.5 GB)。

## 重新安裝 / 升級

```powershell
git pull
.\install.ps1        # Windows
./install.sh         # macOS / Linux
```

指令跟第一次安裝一樣。已存在的 `.venv`、`.env`、hook 會自動偵測並就地更新;舊的 `kaikou-claude` hook 會先被剝除再加回新的,不會重複。

## 解除安裝

```powershell
.\uninstall.ps1      # Windows
./uninstall.sh       # macOS / Linux
```

從 `~/.claude/settings.json` 移除本專案的 `SessionStart` / `SessionEnd` entry,並強制停掉 daemon。你原本的其他 hook 保留不動。檔案(`.venv`、`.env`、原始碼)留在磁碟上 — 要徹底清除請自己刪目錄。想再裝回來就再跑一次安裝腳本。

## 使用

安裝完之後,照常用 Claude Code 即可 — daemon 會在每個 session 啟動時自動跑起來,最後一個 session 結束時自動關閉(詳見[多開共用](#多開共用))。`scripts/` 底下的啟動/停止腳本是給 hook 用的,除非要 debug 否則不用手動執行。

| 按鍵 | 行為 |
|------|------|
| 空白鍵(短按) | 一般空白字元(正常打字) |
| 空白鍵(按住 ≥ 250ms) | 錄音 → 轉錄 → 貼上 → 送出 |

macOS / Linux 改用 F9(按住)。

## 設定

寫在 `.env` 或環境變數。

| 變數 | 預設 | 說明 |
|------|------|------|
| `VOICE_LANGUAGE` | `zh` | Whisper 語言提示 |
| `VOICE_AUTO_SUBMIT` | `1` | `0` 只貼上不送出 — 可以先檢查辨識結果或混搭打字再手動 Enter。設 `1`（預設）時辨識瑕疵由 `<voice>` 標記讓 Claude 自動容錯,日常使用建議保持自動送出。 |
| `VOICE_HOLD_THRESHOLD_SEC` | `0.25` | 空白鍵長短按切點 |
| `VOICE_MARKER` | ` <voice>` | 語音標記後綴,空字串停用 |
| `WHISPER_MODEL_SIZE` | `medium`(cuda)/ `small`(cpu) | |
| `WHISPER_DEVICE` | auto | `cuda` 或 `cpu` |
| `WHISPER_COMPUTE_TYPE` | auto | `float16` / `int8` |

## 語音標記

每筆轉錄送給 Claude 時會長這樣:

```
今天天氣如何 <voice>
```

`CLAUDE.md` 告訴 Claude:看到這個標記代表是語音輸入,應該容忍同音字、錯誤聲調、缺少標點等 ASR 瑕疵,直接理解原意,也不要把標記回傳出來。不想要就把 `VOICE_MARKER=` 設空。

## 多開共用

Session 計數器位在 `%TEMP%\claude-voice.sessions`(Unix 是 `$TMPDIR/claude-voice.sessions`)— 每次 `SessionStart` +1、`SessionEnd` -1,**歸零**才真的殺 daemon。同時開好幾個 Claude Code 視窗時,關其中一個不會把其他視窗的語音搞壞。`uninstall.{ps1,sh}` 與 `stop-voice.{ps1,sh} --force` 會跳過計數器直接殺。

## 日誌

| 平台 | Log | PID |
|------|-----|-----|
| Windows | `%TEMP%\claude-voice.log` | `%TEMP%\claude-voice.pid` |
| macOS | `$TMPDIR/claude-voice.log` | `$TMPDIR/claude-voice.pid` |
| Linux | `/tmp/claude-voice.log`(或 `$TMPDIR`) | `/tmp/claude-voice.pid` |

## 常見問題

- **按住空白沒反應。** 焦點偵測沒命中。看 `claude-voice.log` 有沒有 `● 錄音中...`;沒有就代表前景 process tree 裡沒有 claude。用 `tasklist`(Windows)或 `ps -ef | grep claude`(Unix)確認。
- **macOS / Linux：F9 沒反應。** macOS 要在「系統設定 → 輔助使用」授權;Linux 要裝 `xdotool`(Wayland 需 XWayland)。
- **轉錄結果為空。** VAD 把短音訊濾掉了,講久一點(≥ 500ms)。
- **Windows：一般空白也打不出來。** `scripts\stop-voice.ps1 -Force` 再 `scripts\start-voice.ps1` 重啟。
