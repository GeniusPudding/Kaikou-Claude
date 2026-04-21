"""Idempotently install/uninstall Kaikou-Claude hooks in a Claude Code settings.json.

Usage:
    python patch_settings.py <settings_file> install <platform> <repo_dir>
    python patch_settings.py <settings_file> uninstall

<platform> is either "win" (invoke the PowerShell launchers) or "unix"
(invoke the bash launchers). The command strings are built here so quoting
is consistent and the callers (install.ps1 / install.sh) only need to pass
paths. Existing entries are matched by the MARKERS list below (fixed script
sub-paths, not the repo directory name) so renaming or relocating the repo
does not break idempotency.
"""

import json
import os
import sys

# Our SessionStart/SessionEnd commands always invoke one of these script
# paths. Matching on the fixed sub-path lets us identify our own hook
# entries regardless of where the repo is cloned.
MARKERS = ("scripts/start-voice", "scripts/stop-voice")


def strip_ours(hook_groups):
    """Drop our command entries; remove groups that become empty."""
    if not hook_groups:
        return []
    out = []
    for group in hook_groups:
        kept = [
            h for h in group.get("hooks", [])
            if not any(m in (h.get("command") or "") for m in MARKERS)
        ]
        if kept:
            out.append({**group, "hooks": kept})
    return out


def build_group(command, timeout=10):
    return {"hooks": [{"type": "command", "command": command, "timeout": timeout}]}


def build_commands(platform, repo_dir):
    repo_fwd = repo_dir.replace("\\", "/").rstrip("/")
    if platform == "win":
        start_ps = f'{repo_fwd}/scripts/start-voice.ps1'
        stop_ps = f'{repo_fwd}/scripts/stop-voice.ps1'
        start_cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{start_ps}"'
        stop_cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{stop_ps}"'
    elif platform == "unix":
        start_sh = f'{repo_fwd}/scripts/start-voice.sh'
        stop_sh = f'{repo_fwd}/scripts/stop-voice.sh'
        start_cmd = f'bash "{start_sh}"'
        stop_cmd = f'bash "{stop_sh}"'
    else:
        raise SystemExit(f"unknown platform: {platform} (expected win|unix)")
    return start_cmd, stop_cmd


def main():
    argv = sys.argv[1:]
    if len(argv) < 2:
        print("usage: patch_settings.py <settings_file> <install|uninstall> ...", file=sys.stderr)
        sys.exit(2)

    settings_path, mode = argv[0], argv[1]
    if mode not in ("install", "uninstall"):
        print(f"unknown mode: {mode}", file=sys.stderr)
        sys.exit(2)
    if mode == "install" and len(argv) != 4:
        print("install mode requires: <settings_file> install <platform> <repo_dir>", file=sys.stderr)
        sys.exit(2)

    settings = {}
    if os.path.exists(settings_path):
        with open(settings_path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
            if raw:
                settings = json.loads(raw)

    hooks = settings.setdefault("hooks", {})
    hooks["SessionStart"] = strip_ours(hooks.get("SessionStart"))
    hooks["SessionEnd"] = strip_ours(hooks.get("SessionEnd"))

    if mode == "install":
        platform, repo_dir = argv[2], argv[3]
        start_cmd, stop_cmd = build_commands(platform, repo_dir)
        hooks["SessionStart"].append(build_group(start_cmd))
        hooks["SessionEnd"].append(build_group(stop_cmd))

        # Disable Claude Code's built-in English-only voice to avoid
        # conflicting with Kaikou-Claude's Chinese voice on the same hotkey.
        settings["voiceEnabled"] = False
        if "voice" in settings:
            settings["voice"]["enabled"] = False

    if not hooks["SessionStart"]:
        del hooks["SessionStart"]
    if not hooks["SessionEnd"]:
        del hooks["SessionEnd"]
    if not hooks:
        del settings["hooks"]

    os.makedirs(os.path.dirname(settings_path) or ".", exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"{mode}: {settings_path}")


if __name__ == "__main__":
    main()
