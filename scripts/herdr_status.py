#!/usr/bin/env python3
"""Render Herdr system status and publish per-agent session token metadata.

The status line also shows AI usage limits (for example `CX 83%·40%`,
`CC 37%·22%` or `KR 27/50`) for each tool installed on this machine. See
LIMIT_PROVIDERS. Kiro's credits come from a background `--kiro-daemon` process
(see "Kiro credits" below).

The token metric is cumulative processed tokens reported in the native Codex or
Claude session log, including cached input. It is not a billing estimate and it
does not represent remaining context-window capacity.
"""

from __future__ import annotations

import fcntl
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, NamedTuple


USER_HOME = Path.home()
STATE_PATH = Path(
    os.environ.get(
        "HERDR_STATUS_STATE",
        USER_HOME / ".cache" / "herdr" / "status-cache.json",
    )
)
HERDR_BIN = os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr") or "herdr"
METADATA_SOURCE = "user:token-status"
REFRESH_SECONDS = 4.5  # Leave room for Herdr's 5-second command timeout.

# Nerd Font glyphs (present in JetBrainsMono Nerd Font, the Ghostty font).
# Herdr strips ANSI colors from tab bar command output, so the output is plain
# text; the text color comes from the theme token documented in herdr.md.
CPU_ICON = "\U000f04c5"  # nf-md-speedometer (U+F04C5)
MEM_ICON = "\uefc5"  # nf-fa-memory (U+EFC5), a RAM stick
WORKING_ICON = "\U000f06a9"  # nf-md-robot (U+F06A9), agents at work
BLOCKED_ICON = "\U000f03e4"  # nf-md-pause (U+F03E4), agents waiting on a human
TOTAL_ICON = "\U000f04a0"  # nf-md-sigma (U+F04A0), all detected agents

LIMIT_STALE_SECONDS = 30 * 60  # Older readings get a `~` prefix.
CODEX_SESSIONS = USER_HOME / ".codex" / "sessions"
CODEX_WINDOWS = {300: "5h", 10080: "week"}  # window_minutes -> slot
CODEX_DAY_DIRS = 8  # Recent YYYY/MM/DD directories searched for rollouts.
CODEX_CANDIDATES = 5  # Newest rollouts tried before using the cached reading.
CLAUDE_LIMITS_PATH = Path(
    os.environ.get(
        "HERDR_CLAUDE_LIMITS",
        USER_HOME / ".cache" / "herdr" / "claude-rate-limits.json",
    )
)  # Written by scripts/claude_statusline.py (Claude Code statusLine).
KIRO_DIR = USER_HOME / ".cache" / "herdr"
KIRO_USAGE_PATH = KIRO_DIR / "kiro-usage.json"  # Written only by the daemon.
KIRO_PID_PATH = KIRO_DIR / "kiro-usage.pid"  # Locked by the running daemon.
KIRO_OFF_PATH = KIRO_DIR / "kiro-usage.off"  # Present: do not run the daemon.
try:  # Seconds between usage requests; the override is for tests.
    KIRO_INTERVAL = max(0.1, float(os.environ.get("HERDR_KIRO_INTERVAL", 300)))
except ValueError:
    KIRO_INTERVAL = 300.0
KIRO_REQUEST_TIMEOUT = 60.0  # session/new takes about 10 seconds.
TAIL_CHUNK = 64 * 1024
TAIL_LIMIT = 4 * 1024 * 1024


def run_command(args: list[str], timeout: float, deadline: float | None = None) -> str:
    if deadline is not None:
        timeout = min(timeout, deadline - time.monotonic())
        if timeout <= 0:
            return ""
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout


def cpu_percent(deadline: float | None = None) -> int | None:
    output = run_command(
        ["top", "-l", "1", "-n", "0"], timeout=3.0, deadline=deadline
    )
    match = re.search(
        r"CPU usage:\s*([0-9.]+)% user,\s*([0-9.]+)% sys", output
    )
    if not match:
        return None
    return min(100, round(float(match.group(1)) + float(match.group(2))))


def memory_percent(deadline: float | None = None) -> int | None:
    output = run_command(
        ["memory_pressure", "-Q"], timeout=2.0, deadline=deadline
    )
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", output)
    if not match:
        return None
    return max(0, min(100, 100 - int(match.group(1))))


def load_state() -> dict[str, Any]:
    try:
        value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"sessions": {}}
    if not isinstance(value, dict) or not isinstance(value.get("sessions"), dict):
        return {"sessions": {}}
    return value


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    sessions = state.get("sessions", {})
    if isinstance(sessions, dict) and len(sessions) > 128:
        ordered = sorted(
            sessions.items(),
            key=lambda item: float(item[1].get("updated_at", 0)),
            reverse=True,
        )
        state["sessions"] = dict(ordered[:128])

    fd, temporary_name = tempfile.mkstemp(
        prefix="status-cache.", suffix=".json", dir=STATE_PATH.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, separators=(",", ":"), sort_keys=True)
        os.replace(temporary_name, STATE_PATH)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def session_file(
    agent_kind: str, session: dict[str, Any], deadline: float | None = None
) -> Path | None:
    value = session.get("value")
    kind = session.get("kind")
    if not isinstance(value, str) or not value:
        return None

    if kind == "path":
        candidate = Path(value).expanduser()
        return candidate if candidate.is_file() else None

    if kind != "id" or (deadline is not None and time.monotonic() >= deadline):
        return None

    patterns: list[str]
    if agent_kind == "codex":
        patterns = [f"sessions/**/rollout-*{value}.jsonl"]
        roots = [USER_HOME / ".codex"]
    elif agent_kind == "claude":
        patterns = [f"projects/**/{value}.jsonl"]
        roots = [USER_HOME / ".claude"]
    else:
        return None

    latest: Path | None = None
    latest_mtime = -1.0
    for root in roots:
        for pattern in patterns:
            for item in root.glob(pattern):
                if deadline is not None and time.monotonic() >= deadline:
                    return latest
                try:
                    if item.is_file() and (mtime := item.stat().st_mtime) > latest_mtime:
                        latest, latest_mtime = item, mtime
                except OSError:
                    continue
    return latest


def usage_value(usage: dict[str, Any]) -> int:
    fields = (
        "input_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "output_tokens",
    )
    return sum(int(usage.get(field) or 0) for field in fields)


def update_session_usage(
    file_path: Path, agent_kind: str, state: dict[str, Any],
    deadline: float | None = None,
) -> int | None:
    session_key = str(file_path)
    sessions = state.setdefault("sessions", {})
    record = sessions.get(session_key)
    file_size = file_path.stat().st_size
    if not isinstance(record, dict) or int(record.get("offset", 0)) > file_size:
        record = {"offset": 0, "total": 0, "messages": {}}

    offset = int(record.get("offset", 0))
    total = int(record.get("total", 0))
    messages = record.get("messages", {})
    if not isinstance(messages, dict):
        messages = {}

    with file_path.open("rb") as handle:
        handle.seek(offset)
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                break
            line_start = handle.tell()
            line = handle.readline()
            if not line:
                break
            if not line.endswith(b"\n"):
                handle.seek(line_start)
                break
            offset = handle.tell()
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            if agent_kind == "codex":
                if (
                    event.get("type") == "event_msg"
                    and event.get("payload", {}).get("type") == "token_count"
                ):
                    token_total = (
                        event.get("payload", {})
                        .get("info", {})
                        .get("total_token_usage", {})
                        .get("total_tokens")
                    )
                    if isinstance(token_total, int):
                        total = token_total
            elif agent_kind == "claude":
                message = event.get("message")
                if not isinstance(message, dict) or not isinstance(
                    message.get("usage"), dict
                ):
                    continue
                message_key = message.get("id") or event.get("uuid")
                if not isinstance(message_key, str) or not message_key:
                    message_key = f"offset:{line_start}"
                new_value = usage_value(message["usage"])
                old_value = int(messages.get(message_key, 0))
                messages[message_key] = new_value
                total += new_value - old_value

    record.update(
        {
            "agent": agent_kind,
            "messages": messages if agent_kind == "claude" else {},
            "offset": offset,
            "total": total,
            "updated_at": time.time(),
        }
    )
    sessions[session_key] = record
    return total


def format_tokens(value: int | None) -> str:
    if value is None:
        return "n/a"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B tok"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M tok"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K tok"
    return f"{value} tok"


def snapshot_payload(deadline: float | None = None) -> dict[str, Any]:
    output = run_command(
        [HERDR_BIN, "api", "snapshot"], timeout=1.5, deadline=deadline
    )
    if not output:
        return {}
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {}


def monitored_panes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    panes = payload.get("result", {}).get("snapshot", {}).get("panes", [])
    if not isinstance(panes, list):
        return []

    monitored: list[dict[str, Any]] = []
    for original in panes:
        if not isinstance(original, dict):
            continue
        pane = dict(original)
        session = pane.get("agent_session")
        agent_kind = pane.get("agent")
        if not isinstance(agent_kind, str) and isinstance(session, dict):
            session_agent = session.get("agent")
            if isinstance(session_agent, str):
                agent_kind = session_agent
        if not isinstance(agent_kind, str):
            continue
        pane["agent"] = agent_kind
        monitored.append(pane)
    return monitored


def report_token(pane_id: str, token_text: str, deadline: float) -> None:
    run_command(
        [
            HERDR_BIN,
            "pane",
            "report-metadata",
            pane_id,
            "--source",
            METADATA_SOURCE,
            "--token",
            f"tokens={token_text}",
            "--ttl-ms",
            "30000",
        ],
        timeout=1.5,
        deadline=deadline,
    )


def report_workspace_token(workspace_id: str, token_text: str, deadline: float) -> None:
    run_command(
        [
            HERDR_BIN,
            "workspace",
            "report-metadata",
            workspace_id,
            "--source",
            METADATA_SOURCE,
            "--token",
            f"tokens=Σ {token_text}",
            "--ttl-ms",
            "30000",
        ],
        timeout=1.5,
        deadline=deadline,
    )


def refresh_session_tokens(
    panes: list[dict[str, Any]], deadline: float,
    state: dict[str, Any] | None = None,
) -> None:
    if state is None:
        state = load_state()
    resolved: dict[tuple[str, str], int | None] = {}
    references: dict[tuple[str, str, str], Path | None] = {}
    workspace_totals: dict[str, int] = {}
    workspace_sessions: dict[str, set[tuple[str, str]]] = {}
    for pane in panes:
        if time.monotonic() >= deadline:
            break
        pane_id = pane.get("pane_id")
        workspace_id = pane.get("workspace_id")
        agent_kind = pane.get("agent")
        session = pane.get("agent_session")
        if not isinstance(pane_id, str) or not isinstance(agent_kind, str):
            continue
        total: int | None = None
        if isinstance(session, dict):
            reference = (
                agent_kind,
                str(session.get("kind") or ""),
                str(session.get("value") or ""),
            )
            if reference not in references:
                references[reference] = session_file(agent_kind, session, deadline)
            file_path = references[reference]
            if file_path is not None and time.monotonic() < deadline:
                key = (agent_kind, str(file_path))
                if key not in resolved:
                    try:
                        resolved[key] = update_session_usage(
                            file_path, agent_kind, state, deadline
                        )
                    except OSError:
                        resolved[key] = None
                total = resolved[key]
        report_token(pane_id, format_tokens(total), deadline)
        if total is not None and isinstance(workspace_id, str):
            seen = workspace_sessions.setdefault(workspace_id, set())
            if key not in seen:
                seen.add(key)
                workspace_totals[workspace_id] = (
                    workspace_totals.get(workspace_id, 0) + total
                )
    for workspace_id, total in workspace_totals.items():
        report_workspace_token(workspace_id, format_tokens(total), deadline)
    save_state(state)


# --- AI usage limits -------------------------------------------------------
#
# Each provider turns its tool's local data into a reading: a JSON-serializable
# dict with at least "observed_at" (Unix seconds). The last good reading is
# cached in the state file under "limits", so a provider that finds nothing new
# (or fails) still shows its previous value, marked stale once it is old.


class LimitProvider(NamedTuple):
    label: str  # Tab bar prefix, e.g. "CX".
    command: str  # Shown only when this command is on PATH.
    read: Callable[[float | None], dict[str, Any] | None]
    render: Callable[[dict[str, Any], float, bool], str]  # reading, now, stale


def stale_mark(stale: bool) -> str:
    return "~" if stale else ""


def render_percent_windows(reading: dict[str, Any], now: float, stale: bool) -> str:
    """Render {"windows": {"5h": {...}, "week": {...}}} as `83%·40%`.

    A window whose resets_at has passed counts as 0% used.
    """
    windows = reading.get("windows")
    if not isinstance(windows, dict):
        windows = {}
    parts = []
    for slot in ("5h", "week"):
        window = windows.get(slot)
        used = window.get("used_percent") if isinstance(window, dict) else None
        if not isinstance(used, (int, float)) or isinstance(used, bool):
            parts.append("?")
            continue
        resets_at = window.get("resets_at")
        if isinstance(resets_at, (int, float)) and resets_at <= now:
            used = 0
        parts.append(f"{stale_mark(stale)}{max(0, min(100, round(used)))}%")
    return "·".join(parts)


def event_time(event: dict[str, Any]) -> float | None:
    value = event.get("timestamp")
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def codex_rate_limits(event: Any, fallback_time: float) -> dict[str, Any] | None:
    if not isinstance(event, dict) or event.get("type") != "event_msg":
        return None
    payload = event.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None
    limits = payload.get("rate_limits")
    if not isinstance(limits, dict):
        return None
    windows: dict[str, Any] = {}
    for key in ("primary", "secondary"):
        window = limits.get(key)
        if not isinstance(window, dict):
            continue
        slot = CODEX_WINDOWS.get(window.get("window_minutes"))
        if slot is not None:
            windows[slot] = {
                "used_percent": window.get("used_percent"),
                "resets_at": window.get("resets_at"),
            }
    if not windows:
        return None
    return {"observed_at": event_time(event) or fallback_time, "windows": windows}


def last_codex_limits(
    file_path: Path, deadline: float | None = None
) -> dict[str, Any] | None:
    """Read a rollout backwards and return its last rate_limits reading."""
    stat = file_path.stat()
    with file_path.open("rb") as handle:
        position = stat.st_size
        carry = b""
        while position > 0 and stat.st_size - position < TAIL_LIMIT:
            if deadline is not None and time.monotonic() >= deadline:
                return None
            size = min(TAIL_CHUNK, position)
            position -= size
            handle.seek(position)
            lines = (handle.read(size) + carry).split(b"\n")
            carry = lines.pop(0) if position > 0 else b""
            for line in reversed(lines):
                if b'"token_count"' not in line:
                    continue
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                reading = codex_rate_limits(event, stat.st_mtime)
                if reading is not None:
                    return reading
    return None


def recent_codex_rollouts(deadline: float | None = None) -> list[Path]:
    """Rollouts from the newest day directories, newest mtime first.

    Rollouts live under the day the session started, so a long session keeps
    writing to an older directory; several recent days are searched.
    """
    day_dirs: list[Path] = []
    try:
        for year in sorted(CODEX_SESSIONS.iterdir(), reverse=True):
            for month in sorted(year.iterdir(), reverse=True) if year.is_dir() else []:
                for day in sorted(month.iterdir(), reverse=True) if month.is_dir() else []:
                    if day.is_dir():
                        day_dirs.append(day)
                    if len(day_dirs) >= CODEX_DAY_DIRS:
                        break
                if len(day_dirs) >= CODEX_DAY_DIRS:
                    break
            if len(day_dirs) >= CODEX_DAY_DIRS:
                break
    except OSError:
        return []

    rollouts: list[tuple[float, Path]] = []
    for day in day_dirs:
        if deadline is not None and time.monotonic() >= deadline:
            break
        for item in day.glob("rollout-*.jsonl"):
            try:
                rollouts.append((item.stat().st_mtime, item))
            except OSError:
                continue
    rollouts.sort(reverse=True)
    return [item for _, item in rollouts]


def read_codex_limits(deadline: float | None = None) -> dict[str, Any] | None:
    # Limits are per account, so the newest rollout with a token_count event
    # is enough, whether or not any Herdr pane is running Codex.
    for file_path in recent_codex_rollouts(deadline)[:CODEX_CANDIDATES]:
        if deadline is not None and time.monotonic() >= deadline:
            break
        try:
            reading = last_codex_limits(file_path, deadline)
        except OSError:
            continue
        if reading is not None:
            return reading
    return None


def read_claude_limits(deadline: float | None = None) -> dict[str, Any] | None:
    # Claude Code has no usage limits in its transcripts; they only reach the
    # statusLine command, which caches them (see scripts/claude_statusline.py).
    try:
        reading = json.loads(CLAUDE_LIMITS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        not isinstance(reading, dict)
        or not isinstance(reading.get("observed_at"), (int, float))
        or not isinstance(reading.get("windows"), dict)
    ):
        return None
    return reading


# --- Kiro credits ----------------------------------------------------------
#
# Kiro has no local usage log. `kiro-cli acp` answers the `usage` slash command
# over stdio JSON-RPC (undocumented, checked with kiro-cli 2.22.1) without
# calling a model, but it needs a session, and every session/new adds files
# under ~/.kiro/sessions/cli/. So one long-running daemon
# (`herdr_status.py --kiro-daemon`) keeps a single `kiro-cli acp`, creates one
# session once (reloaded by id after a restart), asks for usage every
# KIRO_INTERVAL seconds, and writes KIRO_USAGE_PATH. The status command only
# starts the daemon when it is not running and reads that file.


class KiroError(Exception):
    pass


class KiroAcp:
    """A `kiro-cli acp` child speaking JSON-RPC, one message per line."""

    def __init__(self, command: str) -> None:
        KIRO_DIR.mkdir(parents=True, exist_ok=True)
        self.process = subprocess.Popen(
            [command, "acp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=KIRO_DIR,
        )
        self.messages: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self.next_id = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            try:
                message = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(message, dict):
                self.messages.put(message)
        self.messages.put(None)

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.next_id += 1
        request_id = self.next_id
        line = json.dumps(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )
        try:
            assert self.process.stdin is not None
            self.process.stdin.write(line.encode("utf-8") + b"\n")
            self.process.stdin.flush()
        except (OSError, ValueError) as error:
            raise KiroError(f"{method}: {error}") from error
        deadline = time.monotonic() + KIRO_REQUEST_TIMEOUT
        while True:
            try:
                message = self.messages.get(
                    timeout=max(0.0, deadline - time.monotonic())
                )
            except queue.Empty:
                raise KiroError(f"{method}: timed out") from None
            if message is None:
                self.messages.put(None)  # Keep reporting EOF.
                raise KiroError(f"{method}: kiro-cli acp exited")
            if message.get("id") != request_id or "method" in message:
                continue  # Notifications and requests from the agent.
            if not isinstance(message.get("result"), dict):
                raise KiroError(f"{method}: {message.get('error')}")
            return message["result"]

    def close(self) -> None:
        try:
            if self.process.stdin is not None:
                self.process.stdin.close()
        except OSError:
            pass
        self.process.terminate()
        try:
            self.process.wait(5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()


def number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def kiro_reading(result: dict[str, Any], now: float) -> dict[str, Any] | None:
    """Turn a `usage` command result into {"used", "limit", "resets_at"}."""
    data = result.get("data")
    if not isinstance(data, dict):
        return None
    breakdowns = data.get("usageBreakdowns")
    for breakdown in breakdowns if isinstance(breakdowns, list) else []:
        if not isinstance(breakdown, dict) or breakdown.get("hasLimit") is not True:
            continue
        used, limit = number(breakdown.get("used")), number(breakdown.get("limit"))
        if used is None or limit is None or limit <= 0:
            continue
        for key in ("bonusCredits", "addOnCredits"):
            extras = data.get(key)
            for extra in extras if isinstance(extras, list) else []:
                if isinstance(extra, dict) and (value := number(extra.get("limit"))):
                    limit += value
        resets_at = None
        reset_day = data.get("billingCycleReset")
        if isinstance(reset_day, str):
            try:
                resets_at = datetime.strptime(reset_day, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                ).timestamp()
            except ValueError:
                pass
        return {"observed_at": now, "used": used, "limit": limit, "resets_at": resets_at}
    return None


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f"{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, separators=(",", ":"), sort_keys=True)
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def load_kiro_cache() -> dict[str, Any]:
    try:
        value = json.loads(KIRO_USAGE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def kiro_open_session(acp: KiroAcp, cache: dict[str, Any]) -> str:
    """Reuse the session this daemon created before; create one only once."""
    acp.request(
        "initialize",
        {
            "protocolVersion": 1,
            "clientCapabilities": {},
            "clientInfo": {"name": "herdr-status", "version": "1"},
        },
    )
    session_id = cache.get("session_id")
    if isinstance(session_id, str) and session_id:
        try:
            acp.request(
                "session/load",
                {"sessionId": session_id, "cwd": str(KIRO_DIR), "mcpServers": []},
            )
            return session_id
        except KiroError:
            if acp.process.poll() is not None:
                raise  # The process died; retry the same session later.
    result = acp.request("session/new", {"cwd": str(KIRO_DIR), "mcpServers": []})
    session_id = result.get("sessionId")
    if not isinstance(session_id, str) or not session_id:
        raise KiroError("session/new: no sessionId")
    cache["session_id"] = session_id
    write_json(KIRO_USAGE_PATH, cache)
    return session_id


def kiro_logged_in(command: str) -> bool:
    try:
        return subprocess.run(
            [command, "whoami"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=KIRO_REQUEST_TIMEOUT,
            check=False,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return True  # Unknown: let acp decide.


def kiro_poll(command: str) -> None:
    """One `kiro-cli acp` lifetime: usage every KIRO_INTERVAL until it fails."""
    cache = load_kiro_cache()
    if not kiro_logged_in(command):
        # Keep the session id so logging back in reuses it.
        cache.update({"observed_at": time.time(), "logged_in": False})
        for key in ("used", "limit", "resets_at"):
            cache.pop(key, None)
        write_json(KIRO_USAGE_PATH, cache)
        return
    acp = KiroAcp(command)
    try:
        session_id = kiro_open_session(acp, cache)
        while not KIRO_OFF_PATH.exists():
            result = acp.request(
                "_kiro.dev/commands/execute",
                {"sessionId": session_id, "command": {"command": "usage", "args": {}}},
            )
            reading = kiro_reading(result, time.time())
            if reading is None:
                raise KiroError("usage: no credit limit in result")
            cache.update(reading, logged_in=True)
            write_json(KIRO_USAGE_PATH, cache)
            time.sleep(KIRO_INTERVAL)
    finally:
        acp.close()


def kiro_daemon() -> int:
    KIRO_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(KIRO_PID_PATH, "a+", encoding="utf-8")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0  # Another daemon is running.
    lock.truncate(0)
    lock.write(f"{os.getpid()}\n")
    lock.flush()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    command = shutil.which("kiro-cli") or "kiro-cli"
    try:
        while not KIRO_OFF_PATH.exists():
            try:
                kiro_poll(command)
            except (KiroError, OSError):
                pass
            if not KIRO_OFF_PATH.exists():
                time.sleep(KIRO_INTERVAL)
    finally:
        # Still holding the lock: a later `kill "$(cat ...pid)"` finds no pid.
        lock.truncate(0)
        lock.flush()
    return 0


def kiro_daemon_running() -> bool:
    try:
        KIRO_DIR.mkdir(parents=True, exist_ok=True)
        with open(KIRO_PID_PATH, "a", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return True
            fcntl.flock(lock, fcntl.LOCK_UN)
    except OSError:
        return True  # Cannot tell; do not start another one.
    return False


def start_kiro_daemon() -> None:
    # Detached, with no pipes: the Herdr worker must not wait for it.
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--kiro-daemon"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=KIRO_DIR,
        start_new_session=True,
    )


def read_kiro_limits(deadline: float | None = None) -> dict[str, Any] | None:
    if not KIRO_OFF_PATH.exists() and not kiro_daemon_running():
        start_kiro_daemon()  # Fast: the daemon writes the cache later.
    cache = load_kiro_cache()
    observed_at = number(cache.get("observed_at"))
    if observed_at is None:
        return None
    if cache.get("logged_in") is False:
        return {"observed_at": observed_at, "hidden": True}
    used, limit = number(cache.get("used")), number(cache.get("limit"))
    if used is None or limit is None:
        return None
    return {"observed_at": observed_at, "used": used, "limit": limit,
            "resets_at": number(cache.get("resets_at"))}


def render_credits(reading: dict[str, Any], now: float, stale: bool) -> str:
    """Render {"used": 27.3, "limit": 50} as `27/50`; 0 used after resets_at."""
    used, limit = number(reading.get("used")), number(reading.get("limit"))
    if used is None or limit is None:
        return "?"
    resets_at = number(reading.get("resets_at"))
    if resets_at is not None and resets_at <= now:
        used = 0
    return f"{stale_mark(stale)}{round(used)}/{round(limit)}"


# Order here is the order on the tab bar. To add a tool, write a read function
# returning {"observed_at": ..., ...} and pick or write a render function.
LIMIT_PROVIDERS: list[LimitProvider] = [
    LimitProvider("CX", "codex", read_codex_limits, render_percent_windows),
    LimitProvider("CC", "claude", read_claude_limits, render_percent_windows),
    LimitProvider("KR", "kiro-cli", read_kiro_limits, render_credits),
]


def installed_limit_providers() -> list[LimitProvider]:
    return [p for p in LIMIT_PROVIDERS if shutil.which(p.command)]


def usage_limits(
    state: dict[str, Any], deadline: float | None = None, now: float | None = None
) -> list[str]:
    now = time.time() if now is None else now
    cache = state.get("limits")
    if not isinstance(cache, dict):
        cache = state["limits"] = {}
    segments = []
    for provider in installed_limit_providers():
        try:
            reading = provider.read(deadline)
        except Exception:
            reading = None
        if reading is not None:
            cache[provider.label] = reading
        else:
            reading = cache.get(provider.label)
        if isinstance(reading, dict) and reading.get("hidden") is True:
            continue  # Installed but not logged in: show nothing.
        text = "?"
        if isinstance(reading, dict):
            observed_at = reading.get("observed_at")
            stale = (
                not isinstance(observed_at, (int, float))
                or now - observed_at > LIMIT_STALE_SECONDS
            )
            try:
                text = provider.render(reading, now, stale)
            except Exception:
                text = "?"
        segments.append(f"{provider.label} {text}")
    return segments


def limit_hidden(provider: LimitProvider, state: dict[str, Any] | None) -> bool:
    """Whether the last known reading hides this entry; reads files only."""
    if provider.label == "KR":
        cache = load_kiro_cache()
        if "logged_in" in cache or number(cache.get("observed_at")) is not None:
            return cache.get("logged_in") is False
    limits = state.get("limits") if isinstance(state, dict) else None
    reading = limits.get(provider.label) if isinstance(limits, dict) else None
    return isinstance(reading, dict) and reading.get("hidden") is True


def limit_placeholders(state: dict[str, Any] | None = None) -> list[str]:
    state = load_state() if state is None else state
    return [f"{provider.label} ?" for provider in installed_limit_providers()
            if not limit_hidden(provider, state)]


def metric(value: int | None) -> str:
    return "?" if value is None else f"{value}%"


def agents(working: int, blocked: int, total: int) -> str:
    return f"{WORKING_ICON} {working} / {BLOCKED_ICON} {blocked} / {TOTAL_ICON} {total}"


def status_line(
    cpu: int | None, memory: int | None, working: int, blocked: int, total: int,
    limits: list[str],
) -> str:
    return " | ".join(
        [f"{CPU_ICON} {metric(cpu)}", f"{MEM_ICON} {metric(memory)}",
         agents(working, blocked, total), *limits]
    )


def main() -> int:
    deadline = time.monotonic() + REFRESH_SECONDS
    panes = monitored_panes(snapshot_payload(deadline))
    working = sum(pane.get("agent_status") == "working" for pane in panes)
    blocked = sum(pane.get("agent_status") == "blocked" for pane in panes)
    cpu = cpu_percent(deadline)
    memory = memory_percent(deadline)
    state = load_state()
    try:
        limits = usage_limits(state, deadline)
    except Exception:
        limits = limit_placeholders(state)
    refresh_session_tokens(panes, deadline, state)
    print(status_line(cpu, memory, working, blocked, len(panes), limits))
    return 0


def run_bounded() -> int:
    try:
        result = subprocess.run(
            [sys.executable, __file__, "--worker"],
            capture_output=True,
            text=True,
            timeout=4.75,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        print(result.stdout.strip())
    else:
        print(status_line(None, None, 0, 0, 0, limit_placeholders()))
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--kiro-daemon"]:
        sys.exit(kiro_daemon())
    sys.exit(main() if sys.argv[1:] == ["--worker"] else run_bounded())
