# Ghostty

## Purpose

Primary terminal configuration optimized for long AI-agent reviews, readable text, and Herdr or tmux pane workflows.

## Installation

- Application: `/Applications/Ghostty.app`
- Homebrew cask: `ghostty 1.3.1`
- Channel: stable
- Architecture: Apple Silicon

## Configuration

Config file: `~/.config/ghostty/config`

### Typography

- Font: `JetBrainsMono Nerd Font`
- Font size: `14`
- Cell height adjustment: `20%`
- Font thickening: enabled
- Minimum contrast: `1.3`

### Theme and appearance

- Light theme: `Catppuccin Latte`
- Dark theme: `Catppuccin Mocha`
- Horizontal padding: `12`
- Vertical padding: `8`
- Balanced padding: enabled
- Background opacity: `0.95`
- Background blur radius: `20`
- macOS titlebar style: tabs
- Unfocused split opacity: `0.85`

### Input and cursor

- Cursor style: block
- Hide mouse while typing: enabled
- Treat macOS Option as Alt: enabled

Reload the config with `Cmd+Shift+,` or restart Ghostty.

## Keybindings

No custom keybindings are currently declared in the Ghostty config. `Cmd+Shift+,` reloads the configuration.

## Troubleshooting

### Nerd Font icons are missing

Confirm that `JetBrainsMono Nerd Font` is installed and that the font name matches the configured family exactly.

### Text is too faint in Herdr or another TUI

The current config uses `minimum-contrast = 1.3` and `font-thicken = true`. Increase minimum contrast if faint text remains difficult to read.

## References

- <https://ghostty.org/docs>
