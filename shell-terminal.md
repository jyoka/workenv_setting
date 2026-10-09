# シェルとターミナル

2026-09-21 に Apple Silicon の macOS 26.6.2 から取得した。

## シェル

- シェル: `/bin/zsh`
- バージョン: zsh 5.9
- 対話シェル用の設定: `~/.zshrc`
- ログインシェル用の設定: `~/.zprofile`

`~/.zprofile` で初期化しているもの:

- Python 3.10 フレームワークのパス
- `/opt/homebrew/bin/brew shellenv` による Homebrew
- OrbStack のシェル連携
- Kiro CLI の起動前・起動後スクリプト

`~/.zshrc` で初期化しているもの:

- Kiro CLI の起動前・起動後スクリプト
- `TERM_PROGRAM=kiro` のときの Kiro ターミナル連携
- Starship プロンプト
- Flutter・Turso・Antigravity・LM Studio・`~/.local/bin` のパス

現時点では、この 2 つのファイルにシェルのエイリアスや独自のシェル関数は直接定義していない。

## マルチプレクサとセッション

### tmux

- バージョン: `3.7c`
- 設定: `~/.config/tmux/tmux.conf`
- プレフィックス: `Ctrl+a`
- マウス: 有効
- 履歴の上限: 50,000 行
- コピーモードの vi キー: 有効
- ウィンドウとペインの番号は 1 から始まる
- ウィンドウ番号は自動で振り直される
- True Color とフォーカスイベントを有効化

プレフィックスの後のキーバインド:

- `r`: 設定を再読み込み
- `|`: 現在のパスで左右に分割
- `-`: 現在のパスで上下に分割
- `c`: 現在のパスで新しいウィンドウ
- `h`、`j`、`k`、`l`: ペイン間を移動
- `H`、`J`、`K`、`L`: ペインのサイズを 5 セルずつ変更
- `z`: ペインの最大化を切り替え
- `A`: `agent | editor | manual` の 3 ペイン構成(crew レイアウト)を作成

ステータスバーは Rose Pine Moon 風の配色で、セッション・ウィンドウ・日付・時刻を表示する。

### Herdr

Herdr は tmux より上のレベルの永続ワークスペース管理ツール。[herdr.md](./herdr.md) を参照。

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

## プロンプト

- Starship のバージョン: `1.26.0`
- `eval "$(starship init zsh)"` で初期化
- `~/.config/starship.toml` は存在しないので、Starship は現在デフォルト設定で動いている。

## 環境変数

シェルで `SAKANA_API_KEY` を定義している。値は意図的に記録していない。

追加しているパス:

- `/Library/Frameworks/Python.framework/Versions/3.10/bin`
- `/opt/homebrew/bin` と関連する Homebrew のパス
- `~/dev/flutter/bin`
- `~/.turso`
- `~/.antigravity/antigravity/bin`
- `~/.lmstudio/bin`
- `~/.local/bin`

秘密の値は絶対にこのリポジトリに追加しないこと。

## トラブルシューティング

### zsh の設定を再読み込みする

```bash
exec zsh
```

### tmux の設定を再読み込みする

```bash
tmux source-file ~/.config/tmux/tmux.conf
```

tmux の中では、プレフィックスの後に `r` を押す。

### zsh スクリプトを書くときの重要な注意

zsh では `path` をループ変数やスカラー変数として使わないこと。`path` は `PATH` 配列と連動しているため、一時的にコマンドが使えなくなることがある。代わりに `config_file` のような具体的な名前を使う。
