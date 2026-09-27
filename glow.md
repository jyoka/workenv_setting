# Glow

## Purpose

Render and browse Markdown files in the terminal. The TUI is useful for navigating this settings directory.

## Installation

- Binary: `/opt/homebrew/bin/glow`
- Homebrew package: `glow 3.0.0`

## Configuration

Config file: `~/Library/Preferences/glow/glow.yml`

```yaml
style: "auto"
mouse: false
pager: false
width: 80
all: false
```

This means Glow follows the terminal theme, disables mouse input and automatic paging, wraps at 80 columns, and hides hidden or ignored files.

## Commands and workflows

Open the current directory in the interactive file browser:

```bash
glow --tui .
```

Open a specific Markdown file:

```bash
glow README.md
```

Useful TUI keys:

- `r`: refresh the directory listing
- `/`: find
- `Enter`: open the selected document
- `e`: edit the selected document
- `q`: quit or return to the previous view

## Troubleshooting

### A newly created Markdown file does not appear

The Glow TUI may still be showing its previous directory listing. Press `r` to refresh. This was verified with Glow 3.0.0.

## References

- <https://github.com/charmbracelet/glow>
