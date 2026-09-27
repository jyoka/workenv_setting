# workenv_setting

Terminal tools, agent workflows, and local development settings captured from this Mac on 2026-09-21. (旧リポ名: workagent_setting。2026-09-26 に改名)

## 別の Mac に環境を再現する

**[新しい Mac でのセットアップ手順](./setup-new-mac.md)** を参照。設定ファイルの実物(マスター)は [`config/`](./config/) に入っている。Homebrew が使えない、管理者権限のない Mac(会社支給など)向けの手順も含む。

## Contents

- [Yazi](./yazi.md)
- [Herdr](./herdr.md)
- [Glow](./glow.md)
- [Ghostty](./ghostty.md)
- [WezTerm](./wezterm.md)
- [Shell and terminal](./shell-terminal.md)
- [Agent tools](./agent-tools.md)
- [Troubleshooting](./troubleshooting.md)

## Documentation convention

For each tool, record:

1. Purpose and common use cases
2. Installation method and version
3. Configuration file locations
4. Important commands and shortcuts
5. Integrations with other tools
6. Known issues and fixes
7. Links to official documentation

Do not store API keys, access tokens, passwords, or other secrets in this directory.

## Environment snapshot

- macOS 26.6.2, build 25G83
- Apple Silicon (`arm64`)
- Login shell: zsh 5.9
- Primary recorded terminal: Ghostty 1.3.1
- Alternative terminal: WezTerm 20240203-110809-5046fc22
- Multiplexer: tmux 3.7c

## How the stack fits together

| Layer | Tool | What it does |
|:--|:--|:--|
| Terminal window | Ghostty or WezTerm | Draws the terminal window, text, colors, tabs, and terminal-level panes |
| Shell | zsh | Reads and runs the commands you type |
| Prompt | Starship | Builds the information shown before each command, such as the current folder, Git state, runtime, and previous command status |
| Multiplexer | tmux | Keeps shell sessions alive and organizes terminal windows and panes |
| Agent workspace | Herdr | Manages persistent workspaces, agents, panes, remotes, and handoffs at a higher level than tmux |
| Markdown viewer | Glow | Renders and browses Markdown in the terminal |
| Coding agents | Codex, Claude Code, Kiro | Inspect and change projects using terminal workflows |
| Editor | Neovim | Edits text and code inside the terminal |

### Starship in this setup

Starship is only the prompt renderer. It does not replace zsh, Ghostty, tmux, or Herdr. The following line in `~/.zshrc` asks zsh to generate its prompt with Starship:

```zsh
eval "$(starship init zsh)"
```

Starship 1.26.0 is installed. No `~/.config/starship.toml` exists, so it currently uses the default appearance and modules. Removing the initialization line would return zsh to a basic prompt without uninstalling or changing the other terminal tools.

Official documentation: <https://starship.rs/>
