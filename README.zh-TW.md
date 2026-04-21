[English](README.md) · [繁體中文](README.zh-TW.md)

# Kaikou-Claude（開口即克）

本地離線中文語音輸入,支援各種 AI 程式助手。按住熱鍵講話、放開自動轉錄貼上送出。適用 Claude Code、Claude Desktop、Gemini Code Assist、SSH 遠端 agent 等任何在終端機中執行的 AI 工具。

底層使用 [faster-whisper](https://github.com/SYSTRAN/faster-whisper)。不需 API key,資料不離開你的電腦。

## 支援目標

語音在前景視窗是已知終端機（iTerm、Terminal.app、Warp、Windows Terminal）或 process tree / 視窗 title 含 `claude` 時觸發,涵蓋：

- **Claude Code** — 終端機、VS Code 整合終端、SSH
- **Claude Desktop** — Electron app
- **Gemini Code Assist / 其他 AI agent** — 任何跑在終端機視窗裡的工具
- **SSH 遠端 agent** — daemon 裝在本地,貼上動作送進 SSH session

## 平台支援

| 平台 | 狀態 | 熱鍵 | 備註 |
|------|------|------|------|
| Windows | **穩定** | **空白鍵(按住)** | 短按 = 一般空白,長按 ≥ 250ms = 語音 |
| macOS | **穩定** | **Cmd(按住)** | 即時錄音,Cmd+其他鍵自動取消。F9 備用。需「輔助使用」權限 |

> **SSH / 遠端使用：** 安裝在你**鍵盤所在的那台機器**（本地 Mac 或 Windows），不是遠端 server。daemon 在本地攔截鍵盤並貼上——對任何 SSH 終端機透明運作。
>
> **Linux 桌面（少見）：** 裝在本地,熱鍵是 F9。需 X11 + `xdotool`。

## 運作原理

```
┌──────────────────────────────────────────────────────────┐
│  你打開 Claude Code session（或任何支援的工具）             │
│    → SessionStart hook 在背景啟動 daemon                  │
│    → 載入 Whisper 模型（自動偵測 CUDA）                    │
│    → 安裝鍵盤 hook                                       │
└──────────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────────┐
│  你按住熱鍵                                              │
│    → 焦點檢查:前景是支援的目標嗎？                         │
│      • Windows: Win32 GetForegroundWindow + process tree  │
│      • macOS: NSWorkspace + Quartz 視窗 title + tree      │
│      • Linux: xdotool + process tree                      │
│    → 是 → 透過 sounddevice 開始錄音                       │
└──────────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────────┐
│  你放開按鍵                                              │
│    → faster-whisper 在本地轉錄                            │
│    → 文字複製到剪貼簿                                     │
│    → Ctrl+V (macOS Cmd+V) 貼到焦點視窗                    │
│    → Enter 送出（若 VOICE_AUTO_SUBMIT=1）                 │
└──────────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────────┐
│  你關閉所有 Claude session                                │
│    → SessionEnd hook 檢查有無殘存 claude process           │
│    → 都沒了才殺 daemon                                    │
└──────────────────────────────────────────────────────────┘
```

全程本地運行 — 不需網路、不需 API key、資料不離開你的電腦。

## 特色

- **情境感知。** 熱鍵只在支援的 AI 工具有焦點時生效,其他地方透明。
- **自動貼上送出。** 轉錄經剪貼簿貼入,按 Enter 送出。
- **語音標記。** 轉錄加上 `<voice>` 後綴,Claude Code 會自動容錯 ASR 瑕疵（見[語音標記](#語音標記)）。
- **自動選 CUDA。** 偵測不到 GPU 時回退 CPU `int8`。
- **Daemon 生命週期。** 只要有 `claude` process 存在就不死;全部關了才自動停。

## 安裝

### Windows

```powershell
git clone https://github.com/GeniusPudding/Kaikou-Claude.git
cd Kaikou-Claude
.\install.ps1
```

### macOS / Linux

```bash
git clone https://github.com/GeniusPudding/Kaikou-Claude.git
cd Kaikou-Claude
./install.sh
```

安裝腳本會建 `.venv`、安裝依賴、寫 `.env`(若不存在)、把 hook 合併到 `~/.claude/settings.json`。冪等 — 隨時重跑都安全。

首次 session 後會下載 Whisper 模型（`small` 約 500 MB,`medium` 約 1.5 GB）。

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

從 `~/.claude/settings.json` 移除 hook 並停 daemon。其他 hook 保留。repo 檔案留著,要徹底清除自己刪目錄。

## 使用

安裝完照常使用 AI 工具即可,daemon 自動伴隨 session 啟動。按住熱鍵講話：

| 平台 | 按鍵 | 行為 |
|------|------|------|
| Windows | 空白鍵(短按) | 一般空白(正常打字) |
| Windows | 空白鍵(按住 ≥ 250ms) | 錄音 → 轉錄 → 貼上 → 送出 |
| macOS | Cmd(按住) | 即時錄音 → 放開 → 送出 |
| macOS | Cmd+其他鍵 | 正常快捷鍵(自動取消語音) |

## 設定

寫在 `.env`（repo 根目錄）。

| 變數 | 預設 | 說明 |
|------|------|------|
| `VOICE_LANGUAGE` | `zh` | Whisper 語言提示 |
| `VOICE_AUTO_SUBMIT` | `1` | `0` 只貼上不送出 — 可先檢查或混搭打字。設 `1` 時 ASR 瑕疵由 `<voice>` 標記讓 Claude 自動容錯。 |
| `VOICE_HOLD_THRESHOLD_SEC` | `0.25` | Windows 空白鍵長短按切點(macOS 不使用) |
| `VOICE_MARKER` | ` <voice>` | 語音標記後綴,空字串停用 |
| `WHISPER_MODEL_SIZE` | auto | CUDA → `medium`,CPU → `small` |
| `WHISPER_DEVICE` | auto | `cuda` 或 `cpu` |
| `WHISPER_COMPUTE_TYPE` | auto | CUDA → `float16`,CPU → `int8` |

## 語音標記

轉錄送出時長這樣：

```
今天天氣如何 <voice>
```

在 Claude Code 中,`CLAUDE.md` 指示 Claude 容忍語音標記：同音字、漏標點、聲調錯都自動腦補。其他工具(Gemini、Claude Desktop)收到原始文字加標記,無害;不想要就 `VOICE_MARKER=` 設空。

## Daemon 生命週期

Daemon 只要系統上還有 `claude` process 就不會死。最後一個關了且 `SessionEnd` 觸發時才停。不用 counter 檔,不怕漂移 — 直接看活著的 process。

## 日誌

| 平台 | Log | PID |
|------|-----|-----|
| Windows | `%TEMP%\claude-voice.log` | `%TEMP%\claude-voice.pid` |
| macOS | `$TMPDIR/claude-voice.log` | `$TMPDIR/claude-voice.pid` |
| Linux | `/tmp/claude-voice.log` | `/tmp/claude-voice.pid` |

## 手動啟動 / 重啟 daemon

如果 daemon 沒在跑（如 uninstall 後重裝、或意外崩潰），手動啟動：

```bash
# Windows
powershell -ExecutionPolicy Bypass -File scripts\start-voice.ps1

# macOS / Linux
bash scripts/start-voice.sh
```

強制重啟：

```bash
# Windows
powershell -ExecutionPolicy Bypass -File scripts\stop-voice.ps1 -Force
powershell -ExecutionPolicy Bypass -File scripts\start-voice.ps1

# macOS / Linux
bash scripts/stop-voice.sh --force
bash scripts/start-voice.sh
```

## VS Code 注意事項

語音在 VS Code 整合終端可以使用,兩點注意：

1. **內建語音衝突。** Claude Code extension 有自己的英文語音用同一個熱鍵。`install.ps1` / `install.sh` 安裝時會自動關閉（`voiceEnabled: false`）以避免亂碼。

2. **貼上目標。** VS Code 有多個 panel,Ctrl+V 送到「游標所在的 panel」。如果游標在程式碼編輯區,轉錄會貼到原始碼裡。**講話前先點一下 terminal panel** 確保游標在那。

## 常見問題

- **熱鍵沒反應。** 看 `claude-voice.log` 有沒有 `● 錄音中...`。沒有 = 焦點偵測沒命中或 daemon 沒在跑。確認 `claude` process 存在,若 daemon 不在就手動啟動（見上方）。
- **macOS：Cmd 沒反應。** 去「系統設定 → 隱私權與安全性 → 輔助使用」把你的終端機加進去。
- **轉錄為空。** 講久一點(≥ 0.5 秒),VAD 會過濾太短的音訊。
- **Windows：空白鍵卡住。** 強制重啟 daemon（見上方）。

> **附註：** 多 tab 終端機（Windows Terminal、VS Code、Terminal.app、iTerm2）共用同一個 process,語音偵測作用於整個終端 app 而非個別 tab。只要其中一個 tab 有跑 AI agent,同視窗的所有 tab 都能觸發語音。實際使用上幾乎不受影響。
