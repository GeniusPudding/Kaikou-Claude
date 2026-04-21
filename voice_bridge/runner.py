"""Startup orchestrator: writes PID, loads model, then enters the hotkey loop."""

import os
import sys

from . import audio, config, hotkey


def _write_pid():
    try:
        with open(config.PID_PATH, "w", encoding="ascii") as pf:
            pf.write(str(os.getpid()))
    except Exception:
        pass


def _print_banner():
    print(f"\n=== Claude Code 中文語音中介 === pid={os.getpid()}  platform={sys.platform}")
    print(
        f"載入模型 {config.MODEL_SIZE}({config.DEVICE}, {config.COMPUTE_TYPE})... 首次會下載",
        flush=True,
    )


def _print_hotkey_help():
    print("熱鍵(僅在 Claude Code 焦點時生效,其它時候透明):")
    if config.IS_WIN:
        print(f"  Space(按住 ≥{config.HOLD_THRESHOLD_SEC}s)→ 中文語音,短按則當普通空白")
    elif config.IS_MAC:
        print("  Cmd(按住)→ 中文語音(即時錄音,Cmd+其他鍵自動取消)")
        print("  F9(按住)→ 中文語音(備用)")
        print("  (需授予 Accessibility 權限。)")
    else:
        print("  F9(按住)→ 中文語音")
        print("  (Linux 需 X11 + xdotool。)")
    print("CC 焦點偵測:前景視窗 process tree 內有 claude 相關進程")
    print(f"語音標記後綴:{config.VOICE_MARKER!r}")
    print("Ctrl+C 離開\n", flush=True)


def main() -> int:
    _write_pid()
    _print_banner()
    audio.load_model()
    _print_hotkey_help()
    hotkey.run_loop()
    return 0
