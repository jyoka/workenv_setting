# WezTerm

## 目的

Lua で設定でき、設定を自動で再読み込みする、クロスプラットフォームの代替ターミナルエミュレータ。メインのマルチプレクサは tmux なので、ターミナル側のキーバインドはあえて最小限にしている。

## インストール

- 実行ファイル: `/opt/homebrew/bin/wezterm`
- バージョン: `20240203-110809-5046fc22`

## 設定

設定ファイル: `~/.config/wezterm/wezterm.lua`

### 見た目

- カラースキーム: `Rose Pine Moon`
- フォント: `JetBrains Mono`、なければ `Menlo`
- フォントサイズ: `14.0`
- 行の高さ: `1.05`
- 背景の不透明度: `0.97`
- macOS の背景ぼかし: `20`
- ウィンドウ装飾: リサイズ用の枠のみ
- 余白: 左 8、右 8、上 8、下 4
- タブが 1 つだけのときはタブバーを隠す
- シンプルなタブバーを下部に表示
- フォントサイズを変えてもウィンドウサイズは変えない

### 動作

- スクロールバック: 10,000 行
- ベル音: 無効
- 設定の自動再読み込み: 有効
- カーソル: 点滅する縦棒

## キーバインド

リーダーキー: `Cmd+a`(タイムアウト 1 秒)。

リーダーキーの後に:

- `Shift+|`: 左右に分割
- `-`: 上下に分割
- `h`、`j`、`k`、`l`: ペイン間を移動
- `z`: ペインの最大化を切り替え
- `c`: タブを作成

## tmux との関係

メインのマルチプレクサは tmux。WezTerm のリーダーキーとペイン操作のキーバインドは、tmux を使わないセッション用に残している。tmux のプレフィックス `Ctrl+a` とぶつからないよう、今後も WezTerm のキーバインドは最小限にとどめる。

## iPad での利用

WezTerm にはネイティブの iPadOS アプリがない。公式にサポートされているデスクトップ環境は macOS・Linux・Windows・FreeBSD・NetBSD。

iPad からは Blink Shell や Termius などの SSH クライアントで Mac に接続し、Mac 側の永続環境にアタッチする:

```bash
ssh USER@MAC_HOST
herdr
# または
tmux attach
```

WezTerm の Lua 設定は、サポート対象のデスクトップ環境で WezTerm を動かしたときにだけ適用される。iPad の SSH アプリには引き継がれない。

## 参考

- <https://wezfurlong.org/wezterm/>
- <https://wezterm.org/features.html>
