# Agent tools

## Tools

| Tool | Version | Binary |
|:--|:--|:--|
| Codex CLI | `0.144.6` | `/opt/homebrew/bin/codex` |
| Claude Code | `2.1.278` | `~/.local/bin/claude` |
| Kiro CLI | `1.1.14` | `/usr/local/bin/kiro` |
| Herdr | `0.9.1` | `/opt/homebrew/bin/herdr` |
| Neovim | `0.12.4` | `/opt/homebrew/bin/nvim` |

Gemini CLI was not found on `PATH` during the 2026-09-21 inventory.

## Shared instructions

Kiro installs pre and post startup blocks in both `~/.zprofile` and `~/.zshrc`. Its terminal-specific zsh integration is loaded only when `TERM_PROGRAM` is `kiro`.

Project-specific `AGENTS.md`, `CLAUDE.md`, skills, and hooks should be documented per repository because their scope and permissions differ. Do not copy credentials or machine-specific secret values into those files.

## Workflows

The current terminal stack is designed around:

1. Ghostty or WezTerm as the terminal emulator
2. Herdr for persistent AI-agent workspaces
3. tmux for explicit pane and window layouts
4. zsh with Starship for the interactive shell
5. Codex, Claude Code, or Kiro as the coding agent
6. Glow for Markdown browsing
7. Neovim as the terminal editor

Task-oriented agent work (task board that runs Claude Code, Codex, Pi, or Kiro locally, one herdr workspace per task) lives in its own repo: `~/AIprogramming PJ/task-hub` (`task` CLI, `/task` skill), https://github.com/jyoka/task-hub. See its README.

## Permissions and safety

- Keep API keys and tokens in environment variables or approved secret stores.
- Document variable names only, never values.
- Review logs before copying them because they may contain project paths or command arguments.
- Keep project-specific permissions in that project's agent instruction files.

## Troubleshooting

### Confirm installed versions

```bash
codex --version
claude --version
kiro --version
herdr --version
nvim --version
```

### Agent command is not found

Start a new zsh session with `exec zsh`, then confirm that Homebrew and `~/.local/bin` are present in `PATH`.
