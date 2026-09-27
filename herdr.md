# Herdr

## Purpose

Terminal workspace manager for AI coding agents. It provides persistent sessions, workspaces, panes, agent integrations, SSH remotes, and live handoff during updates or remote attachment.

## Installation

- Binary: `/opt/homebrew/bin/herdr`
- Installed version: `0.9.1`
- Update channel: `stable`
- Protocol: `22`
- Server status at capture time: running and endpoint-compatible
- Local socket: `~/.config/herdr/herdr.sock`
- Home: <https://herdr.dev>

## Configuration

- Config: `~/.config/herdr/config.toml`
- Session state: `~/.config/herdr/session.json`
- Plugin lock: `~/.config/herdr/.plugins.lock`
- Client log: `~/.config/herdr/herdr-client.log`
- Server log: `~/.config/herdr/herdr-server.log`
- Override variable: `HERDR_CONFIG_PATH`

Current explicit config:

```toml
onboarding = false

[theme]
name = "nord"
auto_switch = false

[ui]
tab_bar_right = [
  { type = "command", command = "python3 '/Users/<user>/.config/herdr/scripts/herdr_status.py'", interval_seconds = 10, timeout_seconds = 5 },
  { type = "hostname" },
  { type = "datetime", format = "%H:%M" },
]
tab_bar_right_separator = " · "

[ui.sidebar.agents]
row_gap = 0
rows = [
  ["state_icon", "workspace", "tab"],
  ["agent", "$tokens", "state_text"],
]

[ui.sidebar.spaces]
row_gap = 0
rows = [
  ["state_icon", "workspace"],
  ["branch", "git_status"],
  ["$tokens"],
]
```

All other behavior currently uses Herdr defaults.

## Status dashboard

The right side of the desktop tab bar refreshes every 10 seconds and shows:

```text
󰓅 19% |  27% | 󰚩 0 / 󰏤 0 / 󰒠 0 | CX 83%·40% | CC 37%·22% | KR 27/50 · hostname · 00:00
```

- `󰓅` (Nerd Font `nf-md-speedometer`, U+F04C5, a gauge): current user plus system CPU utilization
- `` (Nerd Font `nf-fa-memory`, U+EFC5, a RAM stick): memory-pressure-based used percentage
- `󰚩` (Nerd Font `nf-md-robot`, U+F06A9, a robot): agents that are working
- `󰏤` (Nerd Font `nf-md-pause`, U+F03E4, a pause sign): agents that are blocked, waiting for a human reply or confirmation
- `󰒠` (Nerd Font `nf-md-sigma`, U+F04A0, a sum sign): total detected agents
- `CX 83%·40%`: Codex usage limits, used percentage of the 5-hour window then the weekly window (see below)
- `CC 37%·22%`: Claude Code usage limits, in the same form (see below)
- `KR 27/50`: Kiro credits, used then limit for this billing cycle (see below)
- `hostname`: machine running the Herdr server
- Final value: local server time

If the status script cannot finish within its budget, the command entry shows `󰓅 ? |  ? | 󰚩 0 / 󰏤 0 / 󰒠 0`, followed by ` | CX ?` / ` | CC ?` / ` | KR ?` for each installed tool that has a usage-limit entry (for example `󰓅 ? |  ? | 󰚩 0 / 󰏤 0 / 󰒠 0 | CX ? | CC ? | KR ?`). The fallback reads only files, never runs the tools: an entry whose last reading was hidden (Kiro logged out, per `~/.cache/herdr/kiro-usage.json`) is left out here too.

### AI usage limits

After the agent counts, the script appends one entry per AI tool installed on this machine, showing how much of each usage limit is used (like CPU and MEM, a bigger number is closer to the limit). A Mac with only Kiro installed shows only `KR`:

- `CX <5h>%·<week>%`: Codex. Read from the last `token_count` event (`payload.rate_limits`) in the newest `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` by modification time, reading the file backwards. `primary`/`secondary` are assigned to the 5-hour or weekly slot by `window_minutes` (300 or 10080), not by position. The limits are per account, so any rollout works, whether or not a Herdr pane runs Codex.
- `CC <5h>%·<week>%`: Claude Code. Its transcripts have no usage limits; Claude Code passes them only to the `statusLine` command on stdin (`rate_limits.five_hour` / `rate_limits.seven_day`, each `used_percentage` and `resets_at`). `scripts/claude_statusline.py` is that command: it writes the two windows atomically to `~/.cache/herdr/claude-rate-limits.json`, and `herdr_status.py` reads that file. The limits appear only when logged in with claude.ai Pro/Max, and only after a session's first API response, so the file is written only while some Claude Code session is active. The unofficial OAuth usage endpoint is not used.
- `KR <used>/<limit>`: Kiro credits, like the Kiro IDE shows them (`27.31 of 50` is shown as `27/50`). Kiro has no local usage log, so a background daemon asks `kiro-cli acp` for them every 5 minutes; see [Kiro credits daemon](#kiro-credits-daemon). The value is the first `data.usageBreakdowns[]` entry with `hasLimit` and `limit > 0`, with the `limit` of each `bonusCredits` / `addOnCredits` entry added to the limit. Kiro itself updates the numbers a few minutes late.

Rules shared by every entry:

- A tool whose command (`codex`, `claude`, `kiro-cli`) is not on `PATH` shows nothing, not even `?`. Kiro also shows nothing while `kiro-cli whoami` says it is not logged in.
- Installed but no value yet: `CX ?` / `CC ?` / `KR ?` (for Claude Code: the `statusLine` below is not set up, or no Pro/Max session has had an API response yet; for Kiro: the daemon has just started). A single missing window shows `?` in its place, for example `CX 50%·?`.
- The reading is older than 30 minutes (Codex writes limits only while it runs, Claude Code only while a session updates its status line, the Kiro daemon every 5 minutes while it runs): each number gets `~`, for example `CX ~83%·~40%` or `KR ~27/50`.
- A window whose `resets_at` has passed shows `0%` (still with `~` when the reading is old, since other devices may have used it since). For Kiro, the used credits show `0` once `billingCycleReset` (taken as 00:00 UTC of that day) has passed.
- The last good reading is cached in `~/.cache/herdr/status-cache.json` under `limits`, so a missing or unreadable log still shows the previous value (marked `~` once old). A failing reader shows `?` and never breaks the CPU, MEM, or agent entries.

To add a tool, write a reader returning a JSON-serializable dict with `observed_at` (Unix seconds) and add a `LimitProvider(label, command, read, render)` to `LIMIT_PROVIDERS` in `scripts/herdr_status.py`; percentage windows can reuse `render_percent_windows`. A reading with `"hidden": true` hides the entry.

### Kiro credits daemon

`kiro-cli acp` answers the `usage` slash command over stdin/stdout JSON-RPC (one message per line: `initialize`, then a session, then `_kiro.dev/commands/execute` with `{"command": "usage", "args": {}}`). It calls no model and uses no credits, but it is not a documented API (checked with kiro-cli 2.22.1), and every `session/new` adds files under `~/.kiro/sessions/cli/`. So the status script does not call it itself:

- `herdr_status.py --kiro-daemon` runs in the background, one per user. It keeps one `kiro-cli acp` running, creates one session the first time, and reuses it (`session/load` by id) after any restart, so `~/.kiro/sessions/cli/` gets one session (`<id>.json`, `<id>.jsonl`, and `<id>.lock` while the daemon has it open) and never more. Every 5 minutes it sends `usage` to that session and writes `~/.cache/herdr/kiro-usage.json` (`observed_at`, `used`, `limit`, `resets_at`, the session id, and `logged_in`; no tokens).
- It holds a lock on `~/.cache/herdr/kiro-usage.pid` (which contains its pid while it runs and is emptied when it exits) for as long as it runs, so a second copy exits at once. Each status refresh checks that lock and starts the daemon, detached, if nobody holds it, so a killed or crashed daemon comes back within 10 seconds. The status script only reads the cache file and never waits for Kiro.
- Before starting `kiro-cli acp`, it runs `kiro-cli whoami` (exit code only). When not logged in, it writes `logged_in: false`, `KR` disappears, and it checks again after 5 minutes. If `kiro-cli acp` exits or a request fails, it retries after 5 minutes with the same session.

To stop it (it would otherwise come back on the next refresh), create the off file, then kill it:

```bash
touch ~/.cache/herdr/kiro-usage.off
kill "$(cat ~/.cache/herdr/kiro-usage.pid)"
```

Killing the daemon also stops its `kiro-cli acp`. If no daemon is running, the pid file is empty and the `kill` line only prints an error. Without the `kill`, the daemon exits by itself within 5 minutes. While the off file exists, `KR` keeps the last value and marks it `~` after 30 minutes. To start it again, `rm ~/.cache/herdr/kiro-usage.off`; the next refresh starts it. After copying a new `herdr_status.py` to `~/.config/herdr/scripts/`, run only the `kill` line so the next refresh starts the daemon with the new code. Deleting `~/.cache/herdr/kiro-usage.json` loses the session id, so the next start creates one new session.

### Claude Code statusLine (manual setup)

The `CC` entry needs Claude Code to run `claude_statusline.py` as its status line. This repository does not edit `~/.claude/settings.json`; after merging, copy the script next to the Herdr status script and add the `statusLine` key to `~/.claude/settings.json` by hand (a `statusLine` that is already set would be replaced, so merge its output into the script first):

```bash
cp scripts/claude_statusline.py ~/.config/herdr/scripts/
```

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.config/herdr/scripts/claude_statusline.py"
  }
}
```

This adds one line at the bottom of every Claude Code session, above the footer badges, for example:

```text
Opus · workenv_setting · 5h 37% · 7d 22%
```

It shows the model, the current directory name, and the used percentage of the 5-hour and 7-day windows (the window parts are left out until the session has limits). With a custom status line, Claude Code also stops showing most footer key hints such as `esc to interrupt`. The script reads nothing but stdin and writes only `~/.cache/herdr/claude-rate-limits.json` (`observed_at` plus `5h` / `week` windows, no tokens or prompts). JSON without `rate_limits` (API-key login, before the first response) leaves the file untouched. Claude Code drops a window once its `resets_at` passes; the script then keeps the cached window with its past `resets_at`, so the tab bar shows `0%` for it instead of `?`.

### Tab bar text color

Herdr 0.9.1 strips ANSI escapes from `type = "command"` output, so the script prints plain text and cannot color the values. The right-side text color comes from the theme token `overlay1` (nord default `#646e82`, which is hard to read on the dark background). To make it brighter, add this to `~/.config/herdr/config.toml` by hand and run `herdr server reload-config`:

```toml
[theme.custom]
overlay1 = "#d8dee9"  # nord4 (Snow Storm)
```

`overlay1` is a global token: it also recolors the `+` new-tab button and other muted Herdr UI that uses it, not only the status entries. There is no per-entry style for `ui.tab_bar_right` (herdrdev/herdr#4304 was closed as not planned).

When Herdr detects an active agent, its expanded Agent row displays the current agent kind, cumulative native-session token count, and semantic state. Herdr 0.9.1 currently classifies the live Codex and Claude panes on this machine as `unknown`, so those Agent rows are not created. Each Space row therefore also displays the sum of the unique Codex and Claude sessions attached to panes in that workspace. These workspace totals remain visible when an agent process is stopped or temporarily undetected.

Token counts mean cumulative processed tokens reported in the native session log, including cached input. They are not billing estimates and do not show remaining context-window capacity. A missing or unsupported session displays `n/a`.

### 2026-09-22 visibility fix

The first implementation read only `herdr agent list`. That API omits panes whose agent process is stopped or currently classified as `unknown`, even when the pane retains a valid native session reference. The monitor now reads every session-bearing pane from `herdr api snapshot`, publishes tokens to the pane, and publishes an aggregate to its workspace.

The empty Agent panel had a separate cause: Kiro CLI shell initialization launched `kiro-cli-term`, putting Codex and Claude inside a nested pseudo-terminal. Herdr saw the outer wrapper instead of the agent process. The Kiro pre/post initialization blocks in `~/.zshrc` and `~/.zprofile` are now skipped only when `HERDR_ENV` is set. New Herdr panes expose the real foreground agent process; terminals outside Herdr retain Kiro integration. Existing wrapped panes must be recreated.

Verified live values after the fix:

- `ai-CA_RA-A2A-PoC`: `Σ 25.6M tok`
- Claude pane `w1:p4`: `11.8M tok`
- Codex pane `w1:p6`: `13.8M tok`
- a second work workspace: `Σ 11.3M tok`

Implementation:

- Script (実行される本体): `~/.config/herdr/scripts/herdr_status.py`(2026-09-26 にグローバル位置へ移動。このリポジトリの外にあるので、リポジトリを移動・削除してもステータス表示は壊れない)
- Script (ソース管理用マスター): `workenv_setting/scripts/herdr_status.py`。修正したら `cp scripts/herdr_status.py ~/.config/herdr/scripts/` で反映する
- Loop specification: `workenv_setting/loops/herdr-status-monitor.md`
- Cache: `~/.cache/herdr/status-cache.json`
- Kiro credits: `herdr_status.py --kiro-daemon` (started by the status script) writes `~/.cache/herdr/kiro-usage.json`; pid and lock in `~/.cache/herdr/kiro-usage.pid`
- Claude Code limits: `~/.config/herdr/scripts/claude_statusline.py` (master: `workenv_setting/scripts/claude_statusline.py`) writes `~/.cache/herdr/claude-rate-limits.json`
- Refresh: Herdr command status entry, every 10 seconds
- External API or LLM usage: no LLM calls; the Kiro daemon asks Kiro's service for the credit usage through `kiro-cli acp` every 5 minutes
- Config backup: `~/.config/herdr/config.toml.backup-20260922-status`

To disable the dashboard, restore the backup and reload:

```bash
cp ~/.config/herdr/config.toml.backup-20260922-status ~/.config/herdr/config.toml
herdr server reload-config
```

## Commands and workflows

```bash
herdr                         # launch or attach to the persistent session
herdr --session NAME          # use or create a named session
herdr session attach NAME     # attach to a named session
herdr status server           # inspect server status
herdr status client           # inspect client status
herdr server reload-config    # apply config.toml changes
herdr server stop             # stop the local server
herdr update --handoff        # update with live handoff
herdr completion zsh          # generate zsh completions
```

Remote and machine commands:

```bash
herdr --remote HOST
herdr --machine LABEL COMMAND
herdr machine --help
```

## Troubleshooting

### Configuration changes are not applied

Reload the running server:

```bash
herdr server reload-config
```

### Inspect logs

```bash
tail -f ~/.config/herdr/herdr-server.log
tail -f ~/.config/herdr/herdr-client.log
```

Do not copy full logs into this repository without checking them for project paths or sensitive content.

## References

- <https://herdr.dev>
- First-time agent guide: <https://herdr.dev/agent-guide.md>
- Debugging reference: <https://herdr.dev/llms.txt>
