import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "herdr_status.py"
SPEC = importlib.util.spec_from_file_location("herdr_status", SCRIPT_PATH)
assert SPEC and SPEC.loader
STATUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATUS)

STATUSLINE_PATH = Path(__file__).parents[1] / "scripts" / "claude_statusline.py"
STATUSLINE_SPEC = importlib.util.spec_from_file_location("claude_statusline", STATUSLINE_PATH)
assert STATUSLINE_SPEC and STATUSLINE_SPEC.loader
STATUSLINE = importlib.util.module_from_spec(STATUSLINE_SPEC)
STATUSLINE_SPEC.loader.exec_module(STATUSLINE)


def tool_path(root):
    """PATH with the fake tools in root but not the real codex/claude/kiro-cli."""
    return os.pathsep.join([str(root), os.path.dirname(sys.executable), "/usr/bin", "/bin"])


class HerdrStatusTests(unittest.TestCase):
    def test_format_tokens(self):
        self.assertEqual(STATUS.format_tokens(None), "n/a")
        self.assertEqual(STATUS.format_tokens(999), "999 tok")
        self.assertEqual(STATUS.format_tokens(1_500), "1.5K tok")
        self.assertEqual(STATUS.format_tokens(2_500_000), "2.5M tok")

    def test_codex_uses_latest_cumulative_total(self):
        events = [
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {"total_token_usage": {"total_tokens": 100}},
                },
            },
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {"total_token_usage": {"total_tokens": 250}},
                },
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "codex.jsonl"
            source.write_text(
                "".join(json.dumps(event) + "\n" for event in events),
                encoding="utf-8",
            )
            state = {"sessions": {}}
            self.assertEqual(
                STATUS.update_session_usage(source, "codex", state), 250
            )
            self.assertEqual(
                STATUS.update_session_usage(source, "codex", state), 250
            )

    def test_claude_deduplicates_repeated_message_updates(self):
        events = [
            {
                "uuid": "event-1",
                "message": {
                    "id": "message-1",
                    "usage": {
                        "input_tokens": 10,
                        "cache_read_input_tokens": 20,
                        "output_tokens": 5,
                    },
                },
            },
            {
                "uuid": "event-2",
                "message": {
                    "id": "message-1",
                    "usage": {
                        "input_tokens": 10,
                        "cache_read_input_tokens": 20,
                        "output_tokens": 15,
                    },
                },
            },
            {
                "uuid": "event-3",
                "message": {
                    "id": "message-2",
                    "usage": {
                        "input_tokens": 7,
                        "cache_creation_input_tokens": 3,
                        "output_tokens": 2,
                    },
                },
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "claude.jsonl"
            source.write_text(
                "".join(json.dumps(event) + "\n" for event in events),
                encoding="utf-8",
            )
            state = {"sessions": {}}
            self.assertEqual(
                STATUS.update_session_usage(source, "claude", state), 57
            )
            self.assertEqual(
                STATUS.update_session_usage(source, "claude", state), 57
            )

    def test_status_command_stays_within_refresh_budget_with_many_panes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            herdr = root / "herdr"
            herdr.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys, time\n"
                "if sys.argv[1:3] == ['api', 'snapshot']:\n"
                "    print(json.dumps({'result': {'snapshot': {'panes': ["
                "{'pane_id': f'w1:p{i}', 'workspace_id': 'w1', 'agent': 'kiro'} "
                "for i in range(60)]}}}))\n"
                "else:\n"
                "    time.sleep(0.12)\n",
                encoding="utf-8",
            )
            herdr.chmod(0o755)
            for name, output in (
                ("top", "CPU usage: 10% user, 5% sys"),
                ("memory_pressure", "System-wide memory free percentage: 75%"),
                ("codex", ""),
                ("claude", ""),
            ):
                tool = root / name
                tool.write_text(f"#!/bin/sh\necho '{output}'\n", encoding="utf-8")
                tool.chmod(0o755)
            env = dict(os.environ, HERDR_BIN_PATH=str(herdr),
                       HERDR_STATUS_STATE=str(root / "state.json"),
                       HOME=str(root), PATH=tool_path(root))
            started = time.monotonic()
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH)], env=env, capture_output=True,
                text=True, timeout=5.5,
            )
            elapsed = time.monotonic() - started
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertLess(elapsed, 5.1)
            self.assertEqual(
                result.stdout.strip(),
                "\U000f04c5 15% | \uefc5 25% | \U000f06a9 0 / \U000f03e4 0 / \U000f04a0 60 | CX ? | CC ?",
            )

    def test_command_returns_fallback_if_session_read_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "session.jsonl"
            source.write_text('{}\n', encoding="utf-8")
            script = root / "status.py"
            script.write_text(
                SCRIPT_PATH.read_text(encoding="utf-8").replace(
                    "line = handle.readline()", "time.sleep(6)\n            line = handle.readline()"
                ),
                encoding="utf-8",
            )
            herdr = root / "herdr"
            payload = {"result": {"snapshot": {"panes": [{
                "pane_id": "w1:p1", "workspace_id": "w1", "agent": "codex",
                "agent_session": {"kind": "path", "value": str(source)},
            }]}}}
            herdr.write_text(
                "#!/bin/sh\n"
                f"[ \"$1\" = api ] && echo '{json.dumps(payload)}'\n",
                encoding="utf-8",
            )
            herdr.chmod(0o755)
            for name in ("top", "memory_pressure", "codex", "claude", "kiro-cli"):
                tool = root / name
                tool.write_text("#!/bin/sh\necho ready\n", encoding="utf-8")
                tool.chmod(0o755)
            off = root / ".cache" / "herdr" / "kiro-usage.off"  # No Kiro daemon.
            off.parent.mkdir(parents=True)
            off.touch()
            env = dict(os.environ, HERDR_BIN_PATH=str(herdr),
                       HERDR_STATUS_STATE=str(root / "state.json"),
                       HOME=str(root), PATH=tool_path(root))
            fallback = "\U000f04c5 ? | \uefc5 ? | \U000f06a9 0 / \U000f03e4 0 / \U000f04a0 0 | CX ? | CC ?"
            for kiro_cache, expected in ((None, fallback + " | KR ?"),
                                         ({"observed_at": 1, "logged_in": False}, fallback)):
                if kiro_cache:  # Kiro installed but logged out: no KR, as on the normal path.
                    (off.parent / "kiro-usage.json").write_text(
                        json.dumps(kiro_cache), encoding="utf-8")
                started = time.monotonic()
                result = subprocess.run(
                    [sys.executable, str(script)], env=env, capture_output=True,
                    text=True, timeout=5.5,
                )
                elapsed = time.monotonic() - started
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertLess(elapsed, 5.2)
                self.assertEqual(result.stdout.strip(), expected)

    def test_expired_read_resumes_on_next_refresh(self):
        event = {
            "type": "event_msg", "payload": {
                "type": "token_count", "info": {
                    "total_token_usage": {"total_tokens": 25}
                }
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "session.jsonl"
            source.write_text(json.dumps(event) + "\n", encoding="utf-8")
            state = {"sessions": {}}
            self.assertEqual(
                STATUS.update_session_usage(source, "codex", state, time.monotonic() - 1), 0
            )
            self.assertEqual(state["sessions"][str(source)]["offset"], 0)
            self.assertEqual(STATUS.update_session_usage(source, "codex", state), 25)

    def test_repeated_panes_read_one_session_once(self):
        panes = [
            {"pane_id": f"w1:p{i}", "workspace_id": "w1", "agent": "codex",
             "agent_session": {"kind": "path", "value": "/tmp/session.jsonl"}}
            for i in range(2)
        ]
        with patch.object(STATUS, "session_file", return_value=Path("/tmp/session.jsonl")) as lookup, \
             patch.object(STATUS, "update_session_usage", return_value=42) as usage, \
             patch.object(STATUS, "report_token"), \
             patch.object(STATUS, "report_workspace_token"), \
             patch.object(STATUS, "load_state", return_value={"sessions": {}}), \
             patch.object(STATUS, "save_state"):
            STATUS.refresh_session_tokens(panes, time.monotonic() + 10)
        usage.assert_called_once()
        lookup.assert_called_once()

    def test_workspace_deduplicates_id_and_path_for_same_file(self):
        panes = [
            {"pane_id": f"w1:p{i}", "workspace_id": "w1", "agent": "codex",
             "agent_session": {"kind": kind, "value": value}}
            for i, (kind, value) in enumerate((
                ("id", "session-1"), ("path", "/tmp/session.jsonl")
            ))
        ]
        with patch.object(STATUS, "session_file", return_value=Path("/tmp/session.jsonl")), \
             patch.object(STATUS, "update_session_usage", return_value=42), \
             patch.object(STATUS, "report_token"), \
             patch.object(STATUS, "report_workspace_token") as workspace, \
             patch.object(STATUS, "load_state", return_value={"sessions": {}}), \
             patch.object(STATUS, "save_state"):
            STATUS.refresh_session_tokens(panes, time.monotonic() + 10)
        workspace.assert_called_once()
        self.assertEqual(workspace.call_args.args[:2], ("w1", "42 tok"))

    def test_snapshot_keeps_session_panes_when_agent_detection_is_unknown(self):
        payload = {
            "result": {
                "snapshot": {
                    "panes": [
                        {
                            "pane_id": "w1:p1",
                            "workspace_id": "w1",
                            "agent_status": "unknown",
                            "agent_session": {
                                "agent": "codex",
                                "kind": "id",
                                "value": "session-1",
                            },
                        }
                    ]
                }
            }
        }

        panes = STATUS.monitored_panes(payload)

        self.assertEqual(len(panes), 1)
        self.assertEqual(panes[0]["agent"], "codex")


def rate_limit_event(primary, secondary, timestamp="2026-09-26T07:32:47.538Z"):
    return {
        "timestamp": timestamp,
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {"total_token_usage": {"total_tokens": 10}},
            "rate_limits": {"primary": primary, "secondary": secondary},
        },
    }


def window(used, minutes, resets_at):
    return {"used_percent": used, "window_minutes": minutes, "resets_at": resets_at}


class UsageLimitTests(unittest.TestCase):
    NOW = 1_790_400_000.0  # 2026-09-26T05:20:00Z

    def write_rollout(self, home, day, name, events, mtime):
        folder = home / ".codex" / "sessions" / day
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"rollout-{name}.jsonl"
        path.write_text(
            "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
        )
        os.utime(path, (mtime, mtime))
        return path

    def limits(self, home, state=None, now=None, installed=("codex",)):
        state = {"sessions": {}} if state is None else state
        with patch.object(STATUS, "CODEX_SESSIONS", home / ".codex" / "sessions"), \
             patch.object(STATUS, "CLAUDE_LIMITS_PATH", home / "claude-rate-limits.json"), \
             patch.object(STATUS.shutil, "which",
                          side_effect=lambda name: f"/bin/{name}" if name in installed else None):
            return STATUS.usage_limits(state, None, self.NOW if now is None else now)

    def test_codex_windows_come_from_window_minutes(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            # Primary is the weekly window here: slots must not be positional.
            event = rate_limit_event(
                window(40.0, 10080, self.NOW + 86400), window(83.4, 300, self.NOW + 600),
                timestamp="2026-09-26T05:15:00Z",
            )
            self.write_rollout(home, "2026/09/26", "a", [{"type": "other"}, event], self.NOW)
            self.assertEqual(self.limits(home), ["CX 83%·40%"])

    def test_uses_last_token_count_of_newest_rollout(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            future = self.NOW + 3600
            old = rate_limit_event(window(10, 300, future), window(10, 10080, future),
                                   timestamp="2026-09-26T05:10:00Z")
            first = rate_limit_event(window(20, 300, future), window(21, 10080, future),
                                     timestamp="2026-09-26T05:11:00Z")
            last = rate_limit_event(window(30, 300, future), window(31, 10080, future),
                                    timestamp="2026-09-26T05:12:00Z")
            # A long session started on an older day but written most recently.
            self.write_rollout(home, "2026/09/24", "long", [first, last, {"type": "x"}], self.NOW - 60)
            self.write_rollout(home, "2026/09/26", "short", [old], self.NOW - 600)
            # Newest file has no rate limits yet (session just started).
            self.write_rollout(home, "2026/09/26", "new", [{"type": "session_meta"}], self.NOW)
            self.assertEqual(self.limits(home), ["CX 30%·31%"])

    def test_not_installed_shows_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            event = rate_limit_event(window(1, 300, self.NOW + 60), window(2, 10080, self.NOW + 60))
            self.write_rollout(home, "2026/09/26", "a", [event], self.NOW)
            self.assertEqual(self.limits(home, installed=()), [])
            with patch.object(STATUS.shutil, "which", return_value=None):
                self.assertEqual(STATUS.limit_placeholders(), [])
                line = STATUS.status_line(1, 2, 0, 0, 0, STATUS.limit_placeholders())
            self.assertNotIn("CX", line)

    def test_installed_without_value_shows_question_mark(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.limits(Path(directory)), ["CX ?"])

    def test_missing_window_shows_question_mark(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            event = rate_limit_event(window(50, 300, self.NOW + 60), None,
                                     timestamp="2026-09-26T05:19:00Z")
            self.write_rollout(home, "2026/09/26", "a", [event], self.NOW)
            self.assertEqual(self.limits(home), ["CX 50%·?"])

    def test_old_reading_is_marked_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            event = rate_limit_event(window(83, 300, self.NOW + 7200), window(40, 10080, self.NOW + 86400),
                                     timestamp="2026-09-26T04:40:00Z")  # 40 minutes old
            self.write_rollout(home, "2026/09/26", "a", [event], self.NOW - 2400)
            self.assertEqual(self.limits(home), ["CX ~83%·~40%"])

    def test_window_past_reset_counts_as_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            event = rate_limit_event(window(83, 300, self.NOW - 1), window(40, 10080, self.NOW + 86400),
                                     timestamp="2026-09-26T05:19:00Z")
            self.write_rollout(home, "2026/09/26", "a", [event], self.NOW)
            self.assertEqual(self.limits(home), ["CX 0%·40%"])

    def test_cached_reading_is_used_when_logs_disappear(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            event = rate_limit_event(window(83, 300, self.NOW + 7200), window(40, 10080, self.NOW + 86400),
                                     timestamp="2026-09-26T05:19:00Z")
            path = self.write_rollout(home, "2026/09/26", "a", [event], self.NOW)
            state = {"sessions": {}}
            self.assertEqual(self.limits(home, state), ["CX 83%·40%"])
            path.unlink()
            self.assertEqual(self.limits(home, state), ["CX 83%·40%"])
            self.assertEqual(self.limits(home, state, now=self.NOW + 7300), ["CX ~0%·~40%"])

    def test_failing_provider_does_not_break_other_output(self):
        def broken(deadline):
            raise RuntimeError("boom")

        provider = STATUS.LimitProvider("XX", "codex", broken, STATUS.render_percent_windows)
        with patch.object(STATUS, "LIMIT_PROVIDERS", [provider]), \
             patch.object(STATUS.shutil, "which", return_value="/bin/codex"):
            self.assertEqual(STATUS.usage_limits({"sessions": {}}, None, self.NOW), ["XX ?"])

    def test_tail_reader_finds_event_across_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            event = rate_limit_event(window(7, 300, self.NOW + 60), window(8, 10080, self.NOW + 60),
                                     timestamp="2026-09-26T05:19:00Z")
            filler = [{"type": "response_item", "text": "x" * 5000} for _ in range(40)]
            path = self.write_rollout(home, "2026/09/26", "a", [event, *filler], self.NOW)
            with patch.object(STATUS, "TAIL_CHUNK", 4096):
                reading = STATUS.last_codex_limits(path)
            self.assertEqual(reading["windows"]["5h"]["used_percent"], 7)
            self.assertEqual(reading["windows"]["week"]["used_percent"], 8)

    def test_status_command_shows_codex_and_claude_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = time.time()
            stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 60))
            event = rate_limit_event(window(83, 300, now + 3600), window(40, 10080, now + 86400),
                                     timestamp=stamp)
            self.write_rollout(root, time.strftime("%Y/%m/%d"), "a", [event], now)
            for name, output in (
                ("herdr", ""),
                ("top", "CPU usage: 10% user, 5% sys"),
                ("memory_pressure", "System-wide memory free percentage: 75%"),
                ("codex", ""),
                ("claude", ""),
            ):
                tool = root / name
                tool.write_text(f"#!/bin/sh\necho '{output}'\n", encoding="utf-8")
                tool.chmod(0o755)
            env = dict(os.environ, HERDR_BIN_PATH=str(root / "herdr"),
                       HERDR_STATUS_STATE=str(root / "state.json"),
                       HOME=str(root), PATH=tool_path(root))
            env.pop("HERDR_CLAUDE_LIMITS", None)
            statusline = subprocess.run(
                [sys.executable, str(STATUSLINE_PATH)], env=env, capture_output=True, text=True,
                timeout=5, input=json.dumps(claude_input(
                    {"used_percentage": 37.4, "resets_at": int(now) + 3600},
                    {"used_percentage": 22, "resets_at": int(now) + 86400},
                )),
            )
            self.assertEqual(statusline.returncode, 0, statusline.stderr)
            self.assertEqual(statusline.stdout.strip(), "Opus · workenv_setting · 5h 37% · 7d 22%")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH)], env=env, capture_output=True,
                text=True, timeout=5.5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout.strip(),
                "\U000f04c5 15% | \uefc5 25% | \U000f06a9 0 / \U000f03e4 0 / \U000f04a0 0"
                " | CX 83%·40% | CC 37%·22%",
            )


def claude_input(five_hour=None, seven_day=None, rate_limits=True):
    data = {
        "model": {"id": "claude-opus", "display_name": "Opus"},
        "workspace": {"current_dir": "/Users/me/src/workenv_setting"},
    }
    if rate_limits:
        data["rate_limits"] = {}
        if five_hour is not None:
            data["rate_limits"]["five_hour"] = five_hour
        if seven_day is not None:
            data["rate_limits"]["seven_day"] = seven_day
    return data


class ClaudeLimitTests(unittest.TestCase):
    NOW = UsageLimitTests.NOW

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.cache = Path(self.directory.name) / "herdr" / "claude-rate-limits.json"
        self.patches = [
            patch.object(STATUSLINE, "CACHE_PATH", self.cache),
            patch.object(STATUS, "CLAUDE_LIMITS_PATH", self.cache),
            patch.object(STATUS, "CODEX_SESSIONS", Path(self.directory.name) / "sessions"),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.directory.cleanup()

    def record(self, data, now=None):
        """Run the statusline logic as Claude Code would; return its line."""
        windows = STATUSLINE.extract_windows(data)
        STATUSLINE.save_limits(dict(windows), self.NOW if now is None else now)
        return STATUSLINE.status_text(data, windows)

    def limits(self, state=None, now=None, installed=("claude",)):
        state = {"sessions": {}} if state is None else state
        with patch.object(STATUS.shutil, "which",
                          side_effect=lambda name: f"/bin/{name}" if name in installed else None):
            return STATUS.usage_limits(state, None, self.NOW if now is None else now)

    def test_statusline_caches_both_windows(self):
        line = self.record(claude_input(
            {"used_percentage": 37, "resets_at": self.NOW + 3600},
            {"used_percentage": 22.4, "resets_at": self.NOW + 86400},
        ))
        self.assertEqual(line, "Opus · workenv_setting · 5h 37% · 7d 22%")
        cached = json.loads(self.cache.read_text(encoding="utf-8"))
        self.assertEqual(cached["observed_at"], self.NOW)
        self.assertEqual(cached["windows"]["5h"], {"used_percent": 37, "resets_at": self.NOW + 3600})
        self.assertEqual(self.limits(), ["CC 37%·22%"])
        self.assertEqual(list(self.cache.parent.iterdir()), [self.cache])  # no temp files left

    def test_statusline_without_rate_limits_keeps_cache(self):
        self.record(claude_input({"used_percentage": 10, "resets_at": self.NOW + 3600},
                                 {"used_percentage": 20, "resets_at": self.NOW + 86400}))
        # API-key login, or before the session's first API response.
        line = self.record(claude_input(rate_limits=False), now=self.NOW + 60)
        self.assertEqual(line, "Opus · workenv_setting")
        self.assertEqual(json.loads(self.cache.read_text(encoding="utf-8"))["observed_at"], self.NOW)
        self.assertEqual(self.limits(), ["CC 10%·20%"])

    def test_statusline_survives_bad_input(self):
        for data in (None, [], "text", {"rate_limits": None}, {"rate_limits": {"five_hour": "x"}},
                     {"rate_limits": {"five_hour": {"used_percentage": True}}}):
            self.assertEqual(self.record(data), "")
        self.assertFalse(self.cache.exists())
        result = subprocess.run([sys.executable, str(STATUSLINE_PATH)], input="not json",
                                capture_output=True, text=True, timeout=5,
                                env=dict(os.environ, HERDR_CLAUDE_LIMITS=str(self.cache)))
        self.assertEqual((result.returncode, result.stdout), (0, "\n"))

    def test_missing_window_shows_question_mark(self):
        self.record(claude_input(None, {"used_percentage": 22, "resets_at": self.NOW + 86400}))
        self.assertEqual(self.limits(), ["CC ?·22%"])

    def test_window_dropped_after_reset_counts_as_zero(self):
        self.record(claude_input({"used_percentage": 90, "resets_at": self.NOW - 60},
                                 {"used_percentage": 22, "resets_at": self.NOW + 86400}),
                    now=self.NOW - 120)
        # Claude Code drops five_hour once its resets_at passes.
        self.record(claude_input(None, {"used_percentage": 23, "resets_at": self.NOW + 86400}))
        self.assertEqual(self.limits(), ["CC 0%·23%"])

    def test_old_cache_is_marked_stale(self):
        self.record(claude_input({"used_percentage": 37, "resets_at": self.NOW + 7200},
                                 {"used_percentage": 22, "resets_at": self.NOW + 86400}),
                    now=self.NOW - 2400)
        self.assertEqual(self.limits(), ["CC ~37%·~22%"])

    def test_no_cache_shows_question_mark(self):
        self.assertEqual(self.limits(), ["CC ?"])
        self.cache.parent.mkdir(parents=True)
        self.cache.write_text("{broken", encoding="utf-8")
        self.assertEqual(self.limits(), ["CC ?"])

    def test_not_installed_shows_nothing(self):
        self.record(claude_input({"used_percentage": 1, "resets_at": self.NOW + 60},
                                 {"used_percentage": 2, "resets_at": self.NOW + 60}))
        self.assertEqual(self.limits(installed=()), [])
        self.assertEqual(self.limits(installed=("codex", "claude")), ["CX ?", "CC 1%·2%"])
        with patch.object(STATUS.shutil, "which", return_value=None):
            line = STATUS.status_line(1, 2, 0, 0, 0, STATUS.limit_placeholders())
        self.assertNotIn("CC", line)


def kiro_usage_result(used=27.31, limit=45.0, reset="2026-10-01", bonus=5.0):
    return {"success": True, "message": "Estimated Usage", "data": {
        "planName": "KIRO FREE", "billingCycleReset": reset,
        "usageBreakdowns": [
            {"resourceType": "OTHER", "used": 1, "limit": 0.0, "hasLimit": True},
            {"resourceType": "CREDIT", "used": used, "limit": limit, "hasLimit": True},
        ],
        "bonusCredits": [{"used": 1.0, "limit": bonus}] if bonus else [],
        "addOnCredits": [],
    }}


# A stand-in for `kiro-cli`: `whoami` fails while root/logged_out exists, and
# `acp` answers initialize, session/new, session/load and the usage command.
# Every call is logged to root/kiro.log.
FAKE_KIRO = """#!{python}
import json, os, sys
root = os.path.dirname(os.path.abspath(__file__))
def note(text):
    with open(os.path.join(root, "kiro.log"), "a") as log:
        log.write(text + "\\n")
if sys.argv[1:] == ["whoami"]:
    sys.exit(1 if os.path.exists(os.path.join(root, "logged_out")) else 0)
note("acp %d" % os.getpid())
for line in sys.stdin:
    message = json.loads(line)
    method = message["method"]
    note(method)
    reply = {{"jsonrpc": "2.0", "id": message["id"]}}
    if method == "initialize":
        reply["result"] = {{"protocolVersion": 1}}
    elif method == "session/new":
        reply["result"] = {{"sessionId": "session-1"}}
    elif method == "session/load" and message["params"]["sessionId"] == "session-1":
        reply["result"] = {{}}
    elif method == "_kiro.dev/commands/execute":
        print(json.dumps({{"jsonrpc": "2.0", "method": "_kiro.dev/metadata", "params": {{}}}}))
        reply["result"] = {usage}
    else:
        reply["error"] = {{"code": -32603, "message": "no"}}
    print(json.dumps(reply), flush=True)
"""


class KiroLimitTests(unittest.TestCase):
    NOW = UsageLimitTests.NOW

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.cache = self.root / ".cache" / "herdr"
        self.cache.mkdir(parents=True)
        self.started = []
        self.patches = [
            patch.object(STATUS, "KIRO_DIR", self.cache),
            patch.object(STATUS, "KIRO_USAGE_PATH", self.cache / "kiro-usage.json"),
            patch.object(STATUS, "KIRO_PID_PATH", self.cache / "kiro-usage.pid"),
            patch.object(STATUS, "KIRO_OFF_PATH", self.cache / "kiro-usage.off"),
            patch.object(STATUS, "start_kiro_daemon", lambda: self.started.append(1)),
            patch.object(STATUS, "CODEX_SESSIONS", self.root / "sessions"),
            patch.object(STATUS, "CLAUDE_LIMITS_PATH", self.root / "claude-rate-limits.json"),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.directory.cleanup()

    def write_cache(self, **values):
        (self.cache / "kiro-usage.json").write_text(json.dumps(values), encoding="utf-8")

    def limits(self, state=None, now=None, installed=("kiro-cli",)):
        state = {"sessions": {}} if state is None else state
        with patch.object(STATUS.shutil, "which",
                          side_effect=lambda name: f"/bin/{name}" if name in installed else None):
            return STATUS.usage_limits(state, None, self.NOW if now is None else now)

    def test_reading_uses_first_credit_limit_plus_bonus(self):
        reading = STATUS.kiro_reading(kiro_usage_result(), self.NOW)
        self.assertEqual(reading, {"observed_at": self.NOW, "used": 27.31, "limit": 50.0,
                                   "resets_at": 1_790_812_800.0})  # 2026-10-01T00:00Z
        self.assertIsNone(STATUS.kiro_reading({"success": False}, self.NOW))
        self.assertIsNone(STATUS.kiro_reading({"data": {"usageBreakdowns": [
            {"used": 1, "limit": 10, "hasLimit": False}]}}, self.NOW))

    def test_shows_used_and_limit(self):
        self.write_cache(observed_at=self.NOW - 60, used=27.31, limit=50.0,
                         resets_at=self.NOW + 86400, session_id="s")
        state = {"sessions": {}}
        self.assertEqual(self.limits(state), ["KR 27/50"])
        self.assertNotIn("session_id", state["limits"]["KR"])

    def test_no_value_yet_shows_question_mark_and_starts_daemon(self):
        self.assertEqual(self.limits(), ["KR ?"])
        self.assertEqual(self.started, [1])
        self.write_cache(session_id="s")  # Session created, no usage yet.
        self.assertEqual(self.limits(), ["KR ?"])

    def test_old_value_is_marked_stale(self):
        self.write_cache(observed_at=self.NOW - 2400, used=27.31, limit=50.0, resets_at=None)
        self.assertEqual(self.limits(), ["KR ~27/50"])

    def test_past_reset_counts_as_zero(self):
        self.write_cache(observed_at=self.NOW - 60, used=27.31, limit=50.0, resets_at=self.NOW - 1)
        self.assertEqual(self.limits(), ["KR 0/50"])

    def test_not_installed_shows_nothing_and_starts_nothing(self):
        self.write_cache(observed_at=self.NOW, used=1, limit=50)
        self.assertEqual(self.limits(installed=()), [])
        self.assertEqual(self.started, [])
        self.assertEqual(self.limits(installed=("codex", "claude", "kiro-cli")),
                         ["CX ?", "CC ?", "KR 1/50"])

    def test_logged_out_shows_nothing_even_with_old_value(self):
        state = {"sessions": {}}
        self.write_cache(observed_at=self.NOW - 60, used=27.31, limit=50.0)
        self.assertEqual(self.limits(state), ["KR 27/50"])
        self.write_cache(observed_at=self.NOW, logged_in=False, session_id="s")
        self.assertEqual(self.limits(state), [])
        (self.cache / "kiro-usage.json").unlink()  # Cached "hidden" still applies.
        self.assertEqual(self.limits(state), [])

    def test_fallback_hides_logged_out_kiro(self):
        with patch.object(STATUS.shutil, "which", return_value="/bin/kiro-cli"), \
                patch.object(STATUS, "STATE_PATH", self.root / "state.json"):
            self.assertEqual(STATUS.limit_placeholders(), ["CX ?", "CC ?", "KR ?"])
            self.write_cache(observed_at=self.NOW, logged_in=False)
            self.assertEqual(STATUS.limit_placeholders(), ["CX ?", "CC ?"])
            self.write_cache(observed_at=self.NOW, logged_in=True, used=1, limit=50)
            hidden = {"sessions": {}, "limits": {"CX": {"hidden": True}}}
            self.assertEqual(STATUS.limit_placeholders(hidden), ["CC ?", "KR ?"])
            self.assertEqual(self.started, [])  # The fallback never starts the daemon.

    def test_running_daemon_is_not_started_again(self):
        import fcntl
        with open(self.cache / "kiro-usage.pid", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertTrue(STATUS.kiro_daemon_running())
            self.limits()
            self.assertEqual(self.started, [])
        self.assertFalse(STATUS.kiro_daemon_running())

    def test_off_switch_starts_nothing(self):
        (self.cache / "kiro-usage.off").touch()
        self.assertEqual(self.limits(), ["KR ?"])
        self.assertEqual(self.started, [])


class KiroDaemonTests(unittest.TestCase):
    """End to end: the status command, the real daemon, a fake `kiro-cli acp`."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.cache = self.root / ".cache" / "herdr"
        kiro = self.root / "kiro-cli"
        kiro.write_text(FAKE_KIRO.format(python=sys.executable,
                                         usage=repr(kiro_usage_result(reset="2999-01-01"))),
                        encoding="utf-8")
        kiro.chmod(0o755)
        for name, output in (("herdr", ""), ("top", "CPU usage: 10% user, 5% sys"),
                             ("memory_pressure", "System-wide memory free percentage: 75%")):
            tool = self.root / name
            tool.write_text(f"#!/bin/sh\necho '{output}'\n", encoding="utf-8")
            tool.chmod(0o755)
        self.env = dict(os.environ, HERDR_BIN_PATH=str(self.root / "herdr"),
                        HERDR_STATUS_STATE=str(self.root / "state.json"),
                        HERDR_KIRO_INTERVAL="0.2", HOME=str(self.root),
                        PATH=tool_path(self.root))

    def tearDown(self):
        self.cache.mkdir(parents=True, exist_ok=True)
        (self.cache / "kiro-usage.off").touch()
        pid = self.daemon_pid()
        if pid and self.alive(pid):
            os.kill(pid, signal.SIGTERM)
            self.wait_for(lambda: not self.alive(pid))
        self.directory.cleanup()

    def status(self):
        result = subprocess.run([sys.executable, str(SCRIPT_PATH)], env=self.env,
                                capture_output=True, text=True, timeout=5.5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def log(self):
        try:
            return (self.root / "kiro.log").read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []

    def daemon_pid(self):
        try:
            return int((self.cache / "kiro-usage.pid").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    @staticmethod
    def alive(pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def wait_for(self, condition, timeout=10.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if condition():
                return
            time.sleep(0.05)
        self.fail(f"timed out; kiro.log: {self.log()}")

    def usage_count(self):
        return self.log().count("_kiro.dev/commands/execute")

    def test_one_daemon_one_session_and_restart(self):
        prefix = "\U000f04c5 15% |  25% | \U000f06a9 0 / \U000f03e4 0 / \U000f04a0 0 | "
        self.assertIn(self.status(), (prefix + "KR ?", prefix + "KR 27/50"))
        self.wait_for(lambda: self.usage_count() >= 3)
        first = self.daemon_pid()
        for _ in range(3):
            self.assertEqual(self.status(), prefix + "KR 27/50")
        self.assertEqual(self.daemon_pid(), first)
        log = self.log()
        self.assertEqual(sum(line.startswith("acp ") for line in log), 1)
        self.assertEqual(log.count("session/new"), 1)
        self.assertEqual(log.count("session/load"), 0)

        # A killed daemon comes back on the next refresh, with the same session.
        os.kill(first, signal.SIGTERM)
        self.wait_for(lambda: not self.alive(first))
        self.assertIsNone(self.daemon_pid())  # Cleared on exit: a stale kill hits nothing.
        before = self.usage_count()
        self.status()
        self.wait_for(lambda: self.usage_count() > before)
        self.assertNotEqual(self.daemon_pid(), first)
        log = self.log()
        self.assertEqual(sum(line.startswith("acp ") for line in log), 2)
        self.assertEqual(log.count("session/new"), 1)
        self.assertEqual(log.count("session/load"), 1)
        acp_pids = [int(line.split()[1]) for line in log if line.startswith("acp ")]
        self.assertFalse(self.alive(acp_pids[0]))  # The old acp was stopped.

        # The off file stops the daemon and its acp without a kill.
        second = self.daemon_pid()
        (self.cache / "kiro-usage.off").touch()
        self.wait_for(lambda: not self.alive(second) and not self.alive(acp_pids[1]))
        self.assertIsNone(self.daemon_pid())
        self.status()
        time.sleep(0.5)
        self.assertEqual(sum(line.startswith("acp ") for line in self.log()), 2)

    def test_logged_out_shows_no_kiro_entry(self):
        (self.root / "logged_out").touch()
        self.status()
        self.wait_for(lambda: '"logged_in":false' in
                      (self.cache / "kiro-usage.json").read_text(encoding="utf-8")
                      if (self.cache / "kiro-usage.json").exists() else False)
        self.assertEqual(
            self.status(), "\U000f04c5 15% |  25% | \U000f06a9 0 / \U000f03e4 0 / \U000f04a0 0")
        self.assertEqual(self.log(), [])  # acp never started.


if __name__ == "__main__":
    unittest.main()
