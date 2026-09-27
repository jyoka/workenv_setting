#!/usr/bin/env python3
"""Claude Code statusLine command that also records usage limits for Herdr.

Claude Code pipes session JSON to this script on stdin. When the JSON has
`rate_limits` (claude.ai Pro/Max, after the session's first API response), the
5-hour and weekly windows are written atomically to CACHE_PATH, where
`herdr_status.py` reads them for its `CC` entry. The script prints one short
line for the Claude Code status bar: `<model> · <directory>[ · 5h 37% · 7d 22%]`.

It never fails loudly: bad or partial input still prints what it can.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


CACHE_PATH = Path(
    os.environ.get(
        "HERDR_CLAUDE_LIMITS",
        Path.home() / ".cache" / "herdr" / "claude-rate-limits.json",
    )
)
WINDOWS = {"five_hour": "5h", "seven_day": "week"}  # rate_limits key -> slot


def number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def extract_windows(data: Any) -> dict[str, Any]:
    """Return {"5h": {...}, "week": {...}} for the windows present in `data`."""
    limits = data.get("rate_limits") if isinstance(data, dict) else None
    if not isinstance(limits, dict):
        return {}
    windows: dict[str, Any] = {}
    for key, slot in WINDOWS.items():
        window = limits.get(key)
        if isinstance(window, dict) and number(window.get("used_percentage")):
            windows[slot] = {
                "used_percent": window["used_percentage"],
                "resets_at": window.get("resets_at") if number(window.get("resets_at")) else None,
            }
    return windows


def load_cache() -> dict[str, Any]:
    try:
        value = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def save_limits(windows: dict[str, Any], now: float) -> None:
    """Write the reading; keep cached windows Claude Code dropped after reset.

    Claude Code drops a window once its resets_at passes, so a previously seen
    window with a past resets_at is kept (Herdr shows it as 0%). A window that
    is missing for any other reason is left out and shows `?`.
    """
    if not windows:
        return
    previous = load_cache().get("windows")
    if isinstance(previous, dict):
        for slot, window in previous.items():
            if (
                slot not in windows
                and isinstance(window, dict)
                and number(window.get("resets_at"))
                and window["resets_at"] <= now
            ):
                windows[slot] = window
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix="claude-rate-limits.", suffix=".json", dir=CACHE_PATH.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"observed_at": now, "windows": windows}, handle,
                      separators=(",", ":"), sort_keys=True)
        os.replace(temporary_name, CACHE_PATH)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def status_text(data: Any, windows: dict[str, Any]) -> str:
    parts = []
    if isinstance(data, dict):
        model = data.get("model")
        name = model.get("display_name") if isinstance(model, dict) else None
        if isinstance(name, str) and name:
            parts.append(name)
        workspace = data.get("workspace")
        directory = workspace.get("current_dir") if isinstance(workspace, dict) else None
        if not isinstance(directory, str) or not directory:
            directory = data.get("cwd")
        if isinstance(directory, str) and directory:
            parts.append(os.path.basename(directory.rstrip("/")) or directory)
    for slot, label in (("5h", "5h"), ("week", "7d")):
        if slot in windows:
            parts.append(f"{label} {round(windows[slot]['used_percent'])}%")
    return " · ".join(parts)


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "null")
    except (OSError, ValueError):
        data = None
    windows = extract_windows(data)
    try:
        save_limits(dict(windows), time.time())
    except OSError:
        pass
    print(status_text(data, windows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
