# Ghostty

## 目的

メインのターミナル設定。AI エージェントの出力を長時間レビューすること、文字の読みやすさ、Herdr や tmux のペインを使ったワークフローに合わせて調整している。

## インストール

- アプリ: `/Applications/Ghostty.app`
- Homebrew cask: `ghostty 1.3.1`
- チャンネル: stable
- アーキテクチャ: Apple Silicon

## 設定

設定ファイル: `~/.config/ghostty/config`

### 文字

- フォント: `JetBrainsMono Nerd Font`
- フォントサイズ: `14`
- セルの高さ調整: `20%`
- 文字の太らせ(font-thicken): 有効
- 最低コントラスト: `1.3`

### テーマと見た目

- ライトテーマ: `Catppuccin Latte`
- ダークテーマ: `Catppuccin Mocha`
- 左右の余白: `12`
- 上下の余白: `8`
- 余白の均等化: 有効
- 背景の不透明度: `0.95`
- 背景のぼかし半径: `20`
- macOS のタイトルバー形式: tabs
- フォーカスされていない分割ペインの不透明度: `0.85`

### 入力とカーソル

- カーソルの形: ブロック
- 入力中はマウスカーソルを隠す: 有効
- macOS の Option キーを Alt として扱う: 有効

設定の再読み込みは `Cmd+Shift+,`、または Ghostty の再起動で行う。

## キーバインド

現在の Ghostty 設定では独自のキーバインドを定義していない。`Cmd+Shift+,` で設定を再読み込みできる。

## トラブルシューティング

### Nerd Font のアイコンが表示されない

`JetBrainsMono Nerd Font` がインストールされていること、フォント名が設定のフォントファミリー名と完全に一致していることを確認する。

### Herdr などの TUI で文字が薄くて読みにくい

現在の設定は `minimum-contrast = 1.3` と `font-thicken = true` を使っている。それでも薄くて読みにくければ、最低コントラストの値を上げる。

## 参考

- <https://ghostty.org/docs>
