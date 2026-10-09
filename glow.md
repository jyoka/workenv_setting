# Glow

## 目的

ターミナルで Markdown ファイルを整形表示・閲覧する。TUI はこの設定ディレクトリの中を見て回るのに便利。

## インストール

- 実行ファイル: `/opt/homebrew/bin/glow`
- Homebrew パッケージ: `glow 3.0.0`

## 設定

設定ファイル: `~/Library/Preferences/glow/glow.yml`

```yaml
style: "auto"
mouse: false
pager: false
width: 80
all: false
```

この設定では、Glow はターミナルのテーマに合わせて表示し、マウス入力と自動ページャーを無効にし、80 桁で折り返し、隠しファイルや無視対象のファイルを表示しない。

## コマンドと使い方

現在のディレクトリを対話型のファイルブラウザで開く:

```bash
glow --tui .
```

特定の Markdown ファイルを開く:

```bash
glow README.md
```

TUI で便利なキー:

- `r`: ディレクトリ一覧を再読み込み
- `/`: 検索
- `Enter`: 選択中のドキュメントを開く
- `e`: 選択中のドキュメントを編集
- `q`: 終了、または前の画面に戻る

## トラブルシューティング

### 新しく作った Markdown ファイルが表示されない

Glow の TUI が以前のディレクトリ一覧を表示したままになっていることがある。`r` を押して再読み込みする。Glow 3.0.0 で確認済み。

## 参考

- <https://github.com/charmbracelet/glow>
