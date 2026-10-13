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

- テーマ: Omarchy のテーマ(例: `retro-82`)。下の「Omarchy のテーマを使う」を参照
- 左右の余白: `12`
- 上下の余白: `8`
- 余白の均等化: 有効
- 背景の不透明度: `0.95`
- 背景のぼかし半径: `20`
- macOS のタイトルバー形式: tabs
- フォーカスされていない分割ペインの不透明度: `0.85`

#### Omarchy のテーマを使う

Linux 機(Omarchy)の全テーマ(22 個)を、Ghostty のテーマファイルにして [`config/ghostty/themes/`](./config/ghostty/themes/) に置いている。中身は色だけで、フォントや文字サイズは各マシンの設定のまま:

```bash
mkdir -p ~/.config/ghostty/themes
cp config/ghostty/themes/* ~/.config/ghostty/themes/
```

`~/.config/ghostty/config` では、Catppuccin を指定していた `theme = ...` の行を、使いたいテーマ名に置き換える:

```
theme = retro-82
```

- テーマ名はファイル名と同じ: catppuccin, catppuccin-latte, ethereal, everforest, flexoki-light, gruvbox, hackerman, kanagawa, last-horizon, lumon, lupine, matte-black, miasma, nord, osaka-jade, retro-82, ristretto, rose-pine, solitude, tokyo-night, vantablack, white
- `nord` と `rose-pine` は Ghostty の標準テーマと同じ名前だが、`~/.config/ghostty/themes/` に置いた方(Omarchy の色)が優先される
- 1 つのテーマはライトかダークのどちらかだけ。Mac の外観に合わせて切り替えたいときは `theme = light:catppuccin-latte,dark:retro-82` のように書く
- 色見本は Linux 機の `/usr/share/omarchy/themes/<名前>/preview.png`、または `omarchy theme set <名前>` で実際に切り替えて確認する
- herdr はテーマ `terminal` にすると、この Ghostty の色をそのまま使う([herdr.md](./herdr.md))

#### テーマファイルを作り直す

Omarchy の更新でテーマが増えたり変わったりしたら、Linux 機でリポのルートから実行してコミットする:

```bash
scripts/export_omarchy_themes.sh
```

Omarchy 自身のテンプレート処理(`omarchy-theme-set-templates`)を一時的な HOME で動かすので、`omarchy theme set` が作るファイルと同じ色になる。Linux 側は Omarchy が現在のテーマを直接読み込むので、テーマファイルを置く必要はない。

### 入力とカーソル

- カーソルの形: ブロック
- 入力中はマウスカーソルを隠す: 有効
- macOS の Option キーを Alt として扱う: 有効

設定の再読み込みは `Cmd+Shift+,`、または Ghostty の再起動で行う。

## キーバインド

現在の Ghostty 設定では独自のキーバインドを定義していない。`Cmd+Shift+,` で設定を再読み込みできる。

### Linux(Omarchy)

Linux 版 Ghostty は、Mac では Cmd に割り当てているタブ・分割の操作を Alt / Ctrl+Alt に割り当てている。そのままだと herdr のキーが Ghostty に横取りされるので、`~/.config/ghostty/config` で外した(2026-10-13):

```
# Ghostty's Linux defaults grab these for its own tabs/splits; hand them to herdr instead.
keybind = ctrl+alt+arrow_up=unbind
keybind = ctrl+alt+arrow_down=unbind
keybind = ctrl+alt+arrow_left=unbind
keybind = ctrl+alt+arrow_right=unbind
keybind = alt+digit_1=unbind
keybind = alt+1=unbind
# … alt+digit_8 / alt+8 まで同様
keybind = alt+9=unbind
```

| Ghostty の既定キー | 動作 | herdr での用途 |
|:--|:--|:--|
| Alt+1〜8 / Alt+9 | Ghostty のタブ移動 / 最後のタブ | タブ 1〜9 へ移動 |
| Ctrl+Alt+矢印 | Ghostty の分割間を移動 | 隣のペインへ移動 |

- 既定キーの一覧は `ghostty +list-keybinds --default`、外せたかは `ghostty +list-keybinds` で確認する
- 変更後は `ghostty +validate-config` で検証し、Omarchy なら `omarchy restart terminal` で反映する

## トラブルシューティング

### Nerd Font のアイコンが表示されない

`JetBrainsMono Nerd Font` がインストールされていること、フォント名が設定のフォントファミリー名と完全に一致していることを確認する。

### Herdr などの TUI で文字が薄くて読みにくい

現在の設定は `minimum-contrast = 1.3` と `font-thicken = true` を使っている。それでも薄くて読みにくければ、最低コントラストの値を上げる。

## 参考

- <https://ghostty.org/docs>
