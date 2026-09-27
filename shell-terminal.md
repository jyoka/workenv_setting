# Shell and terminal

Captured on 2026-09-21 from macOS 26.6.2 on Apple Silicon.

## Shell

- Shell: `/bin/zsh`
- Version: zsh 5.9
- Interactive config: `~/.zshrc`
- Login config: `~/.zprofile`

`~/.zprofile` initializes:

- Python 3.10 framework path
- Homebrew through `/opt/homebrew/bin/brew shellenv`
- OrbStack shell integration
- Kiro CLI pre and post startup scripts

`~/.zshrc` initializes:

- Kiro CLI pre and post startup scripts
- Kiro terminal integration when `TERM_PROGRAM=kiro`
- Starship prompt
- Flutter, Turso, Antigravity, LM Studio, and `~/.local/bin` paths

No shell aliases or custom shell functions are currently declared directly in these two files.

## Multiplexers and sessions

### tmux

- Version: `3.7c`
- Config: `~/.config/tmux/tmux.conf`
- Prefix: `Ctrl+a`
- Mouse: enabled
- History limit: 50,000 lines
- Vi copy-mode keys: enabled
- Windows and panes start at index 1
- Windows are automatically renumbered
- True color and focus events are enabled

Keybindings after the prefix:

- `r`: reload config
- `|`: horizontal split in the current path
- `-`: vertical split in the current path
- `c`: new window in the current path
- `h`, `j`, `k`, `l`: navigate panes
- `H`, `J`, `K`, `L`: resize panes by five cells
- `z`: toggle pane zoom
- `A`: create the three-pane `agent | editor | manual` crew layout

The status bar uses a Rose Pine Moon inspired palette and shows the session, windows, date, and time.

### Herdr

Herdr is the higher-level persistent workspace manager. See [herdr.md](./herdr.md).

## コマンド入力支援(2026-09-26 追加)

`~/.zshrc` に以下を追加した。

```zsh
# 履歴からの自動補完(灰色で候補表示、→キーで確定)
source /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh
# fzf 連携: Ctrl+R 履歴あいまい検索 / Ctrl+T ファイル名挿入 / Alt+C フォルダ移動
source <(fzf --zsh)
```

- zsh-autosuggestions(brew, 2026-09-26 導入): コマンドを打ち始めると過去の履歴から続きが灰色で表示される。→キーで確定、無視してそのまま打ち続けてもよい
- fzf シェル連携: `Ctrl+R` でコマンド履歴のあいまい検索(一部だけ打てば候補が絞られる)、`Ctrl+T` でファイルパスを入力中のコマンドに挿入、`Alt+C` でフォルダを選んで移動

## Prompt

- Starship version: `1.26.0`
- Initialized by `eval "$(starship init zsh)"`
- No `~/.config/starship.toml` exists, so Starship currently uses its default configuration.

## Environment variables

The shell defines `SAKANA_API_KEY`. Its value is intentionally not recorded.

Configured path additions:

- `/Library/Frameworks/Python.framework/Versions/3.10/bin`
- `/opt/homebrew/bin` and related Homebrew paths
- `~/dev/flutter/bin`
- `~/.turso`
- `~/.antigravity/antigravity/bin`
- `~/.lmstudio/bin`
- `~/.local/bin`

Never add secret values to this repository.

## Troubleshooting

### Reload zsh settings

```bash
exec zsh
```

### Reload tmux settings

```bash
tmux source-file ~/.config/tmux/tmux.conf
```

Inside tmux, use prefix then `r`.

### Important zsh scripting note

Do not use `path` as a local loop or scalar variable in zsh. It is tied to the `PATH` array and can temporarily make commands unavailable. Use a specific name such as `config_file` instead.
