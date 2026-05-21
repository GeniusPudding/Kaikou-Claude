[English](README.md) · [繁體中文](README.zh-TW.md)

# Kaikou-Claude（開口即克）

本地離線中文語音輸入給各種 AI 程式助手。按住熱鍵講話、放開自動轉錄貼上送出。

支援 **Claude Code**（終端機、VS Code、SSH）、**Claude Desktop**、**Gemini Code Assist**、**Aider**、**Codex**，以及任何在終端機跑的 AI agent。

底層使用 [faster-whisper](https://github.com/SYSTRAN/faster-whisper)。不需 API key,資料不離開你的電腦。

## 平台支援

| 平台 | 熱鍵 | 備註 |
|------|------|------|
| Windows | **空白鍵（按住 ≥ 250ms）** | 短按 = 一般空白,長按 = 語音 |
| macOS | **Cmd（按住）** | 即時錄音。Cmd+其他鍵 = 一般快捷鍵（自動取消語音）。需「輔助使用」權限 |
| Linux | F9（按住） | 僅限 X11。建議安裝 `xdotool` |

> **SSH / 遠端使用：** 安裝在你**鍵盤所在的那台機器**（本地 Mac 或 Windows）。daemon 在本地攔截鍵盤並貼上 — 對任何連到遠端主機的終端機透明運作。

## 安裝

```bash
git clone https://github.com/GeniusPudding/Kaikou-Claude.git
cd Kaikou-Claude

# Windows
.\install.ps1

# macOS / Linux
./install.sh
```

安裝腳本會：

1. 建 `.venv` 並安裝 Python 依賴。
2. 寫一份預設 `.env`（若不存在）。
3. 把 `SessionStart` / `SessionEnd` hook 註冊到 `~/.claude/settings.json`。
4. 在你的 shell 設定（`~/.bashrc` / `~/.zshrc` / PowerShell `$PROFILE`）加 **preexec hook**,讓你打 Gemini、Aider、ssh 等其他 AI agent 時 daemon 也會自動啟動。
5. 預先下載 Whisper 模型（CPU `small` ~500 MB / CUDA `large-v3-turbo` ~1.6 GB）。

冪等 — 隨時重跑都安全。

## 重新安裝 / 升級

```bash
git pull
.\install.ps1        # Windows
./install.sh         # macOS / Linux
```

## 解除安裝

```bash
.\uninstall.ps1      # Windows
./uninstall.sh       # macOS / Linux
```

從 `~/.claude/settings.json` 移除 hook、從 shell 設定移除 preexec 區塊、強制停 daemon。repo 檔案保留。

## 使用

安裝完照常使用 AI 工具,daemon 自動就位。按住熱鍵講話：

| 平台 | 行為 |
|------|------|
| Windows | 按住空白鍵 ≥ 250ms → 講話 → 放開。短按仍是一般空白 |
| macOS | 按住 Cmd → 講話 → 放開。Cmd+其他鍵（例 Cmd+C）自動取消 |
| Linux | 按住 F9 → 講話 → 放開 |

## 運作原理

```
                 ┌──────────────────────────────────────────────┐
   三層啟動機制  │ Layer 1: Claude SessionStart hook            │
   覆蓋任何      │   → 開 `claude` 時觸發                       │
   AI agent      ├──────────────────────────────────────────────┤
   在任何        │ Layer 2: Shell preexec hook                  │
   終端機:       │   → 打 `claude / gemini / aider / codex /    │
                 │     ssh` + Enter 時觸發                      │
                 │     (zsh preexec、bash DEBUG trap、          │
                 │      PowerShell PSReadLine)                  │
                 ├──────────────────────────────────────────────┤
                 │ Layer 3: start-voice 自我修復                │
                 │   → venv 不存在就自動重建                    │
                 └──────────────────────────────────────────────┘
                                       ↓
              ┌──────────────────────────────────────────────┐
              │ Daemon 載入完成（Whisper 模型在記憶體裡）    │
              │   → Win32 LL hook（Windows）                 │
              │   → pynput listener（macOS / Linux）         │
              └──────────────────────────────────────────────┘
                                       ↓
              ┌──────────────────────────────────────────────┐
              │ 你按住熱鍵                                   │
              │   → 焦點檢查：前景是 AI agent 嗎？           │
              │       Win32 GetForegroundWindow + tree (Win) │
              │       NSWorkspace + Quartz title (mac)       │
              │       xdotool + tree (Linux)                 │
              │   → 是 → 開始錄音 (sounddevice)              │
              └──────────────────────────────────────────────┘
                                       ↓
              ┌──────────────────────────────────────────────┐
              │ 你放開                                       │
              │   → faster-whisper 在本地轉錄                │
              │   → 剪貼簿 ← 文字 + <voice> 標記             │
              │   → Ctrl+V（macOS Cmd+V）貼到焦點視窗        │
              │   → Enter（若 VOICE_AUTO_SUBMIT=1）          │
              └──────────────────────────────────────────────┘
                                       ↓
              ┌──────────────────────────────────────────────┐
              │ 所有 AI session 都關了                       │
              │   → SessionEnd hook 檢查存活的 process       │
              │   → 都沒了才停 daemon                        │
              │     (含 SSH session,保守策略)                │
              └──────────────────────────────────────────────┘
```

全程本地運行 — 不需網路、不需 API key、資料不離開你的電腦。

## 設定

寫在 repo 根目錄的 `.env`。

| 變數 | 預設 | 說明 |
|------|------|------|
| `VOICE_LANGUAGE` | `zh` | Whisper 語言提示 |
| `VOICE_AUTO_SUBMIT` | `1` | `0` 只貼上不送出。可用於檢查或混搭打字 |
| `VOICE_HOLD_THRESHOLD_SEC` | `0.25` | Windows 空白鍵長短按切點（macOS 不使用） |
| `VOICE_MARKER` | ` <voice>` | 語音標記後綴,空字串停用 |
| `WHISPER_MODEL_SIZE` | auto | CUDA → `large-v3-turbo`,CPU → `small` |
| `WHISPER_DEVICE` | auto | `cuda` 或 `cpu` |
| `WHISPER_COMPUTE_TYPE` | auto | CUDA → `float16`,CPU → `int8` |
| `VOICE_IDLE_UNLOAD_SEC` | `300` | 僅 CUDA:閒置這麼多秒後把權重從 VRAM 換到 CPU RAM,讓 GPU 還給訓練等其他工作。下次轉錄會多 ~1-2 秒換回。設 `0` 則永久常駐 GPU |

## 語音標記

每筆轉錄送出時是 `<文字> <voice>`。在 Claude Code 中,`CLAUDE.md` 指示 Claude 容忍語音標記：同音字、漏標點、聲調錯都自動腦補。其他工具會收到原始文字加標記,無害;不想要就 `VOICE_MARKER=` 設空。

## 日誌

| 平台 | Log | PID |
|------|-----|-----|
| Windows | `%TEMP%\claude-voice.log` | `%TEMP%\claude-voice.pid` |
| macOS | `$TMPDIR/claude-voice.log` | `$TMPDIR/claude-voice.pid` |
| Linux | `/tmp/claude-voice.log` | `/tmp/claude-voice.pid` |

## 手動 daemon 控制

Daemon 通常自動啟動。debug 用的手動指令：

```bash
# 啟動（冪等）
.\scripts\start-voice.ps1     # Windows
bash scripts/start-voice.sh   # macOS / Linux

# 強制停止
.\scripts\stop-voice.ps1 -Force
bash scripts/stop-voice.sh --force
```

## VS Code 注意事項

語音在 VS Code 整合終端可以使用,兩點注意：

1. **內建語音衝突** — Claude Code extension 有自己的英文語音用同一個熱鍵。安裝腳本會自動關閉（`voiceEnabled: false`）以避免亂碼。

2. **貼上目標** — VS Code 有多個 panel,Ctrl+V 送到「游標所在的 panel」。**講話前先點一下 terminal panel** 確保游標在那。

## 常見問題

- **Daemon 沒在跑。** 看 `claude-voice.log`。Daemon 靠 `SessionStart` hook（Claude）或 preexec hook（其他 agent / SSH）自動啟動。如果掛掉了,用 `start-voice.{ps1,sh}` 手動重啟。持續失敗 → 重跑 install 修復 venv。
- **熱鍵沒反應。** 確認 AI agent process 存在（`tasklist` / `ps -ef | grep claude`）。看 log 按住熱鍵後有沒有 `● 錄音中...`。
- **macOS：Cmd 沒反應。** 去「系統設定 → 隱私權與安全性 → 輔助使用」把你的終端機加進去。
- **轉錄為空。** 講久一點（≥ 0.5 秒）,VAD 會過濾太短的音訊。
- **Windows：空白鍵卡住。** 強制重啟 daemon。

> **多 tab 終端機**（Windows Terminal、VS Code、Terminal.app、iTerm2）共用一個 process。偵測作用於整個 app — 只要其中一個 tab 有 Claude,同視窗的所有 tab 都能觸發語音。實務上可接受。
