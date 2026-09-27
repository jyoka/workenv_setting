# WezTerm

## Purpose

Alternative cross-platform terminal emulator with a Lua configuration and automatic config reload. The configuration deliberately keeps terminal keybindings minimal because tmux is the primary multiplexer.

## Installation

- Binary: `/opt/homebrew/bin/wezterm`
- Version: `20240203-110809-5046fc22`

## Configuration

Config file: `~/.config/wezterm/wezterm.lua`

### Appearance

- Color scheme: `Rose Pine Moon`
- Font fallback: `JetBrains Mono`, then `Menlo`
- Font size: `14.0`
- Line height: `1.05`
- Background opacity: `0.97`
- macOS background blur: `20`
- Window decorations: resize border only
- Padding: left 8, right 8, top 8, bottom 4
- Hide the tab bar when only one tab exists
- Simple tab bar at the bottom
- Do not resize the window when font size changes

### Behavior

- Scrollback: 10,000 lines
- Audible bell: disabled
- Automatic config reload: enabled
- Cursor: blinking bar

## Keybindings

Leader: `Cmd+a`, with a one-second timeout.

After the leader:

- `Shift+|`: horizontal split
- `-`: vertical split
- `h`, `j`, `k`, `l`: navigate panes
- `z`: toggle pane zoom
- `c`: create a tab

## Relationship with tmux

tmux is the primary multiplexer. WezTerm's leader and pane bindings are retained for sessions that run without tmux. Keep future WezTerm bindings minimal to avoid conflicts with the tmux `Ctrl+a` prefix.

## iPad usage

WezTerm does not provide a native iPadOS application. Its officially supported desktop platforms are macOS, Linux, Windows, FreeBSD, and NetBSD.

Use an iPad SSH client such as Blink Shell or Termius to connect to the Mac, then attach to the persistent environment there:

```bash
ssh USER@MAC_HOST
herdr
# or
tmux attach
```

The WezTerm Lua configuration applies only when running WezTerm on a supported desktop system. It does not transfer to the iPad SSH application.

## References

- <https://wezfurlong.org/wezterm/>
- <https://wezterm.org/features.html>
