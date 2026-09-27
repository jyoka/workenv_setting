# Yazi

## 目的

ターミナル用ファイルマネージャー。ディレクトリ移動・プレビュー・ファイル操作をキーボードだけで行う。

## インストール

- バイナリ: `/opt/homebrew/bin/yazi`
- Homebrew パッケージ: `yazi 26.9.1`

## 設定

設定ファイル: `~/.config/yazi/yazi.toml`(2026-09-26 作成)

設定のマスター: [`config/yazi/yazi.toml`](./config/yazi/yazi.toml)。別の Mac へコピーする手順は [setup-new-mac.md](./setup-new-mac.md) を参照。

これにより `.md` / `.markdown` ファイルを Enter で開くと glow のページャー(スクロール閲覧画面)で表示され、`q` キーだけで yazi に戻れる。vim のように `:q!` を打つ必要はない。

- opener = 「このコマンドでファイルを開く」という定義。ここでは markdown 用に glow と vim の 2 つを登録している
- `%s` = 選択中のファイルパスに置き換わる記号。古い解説記事にある `"$@"` は yazi 26.x では動かない(引数が渡らない)
- ルールのキーは `url`。古い書き方の `name` は yazi 26.x ではパースエラーになり、設定全体が無視される
- `glow -p` = ページャーモード。glow 本体の設定(`pager: false`)より優先される
- `block = true` = 表示している間 yazi を待たせる設定。閲覧を終えると yazi に戻る

## トラブルシューティング

### 設定を書いたのに Enter の動作が変わらない

yazi は設定ファイルにひとつでもパースエラーがあると、起動時に「Press any key to continue with preset settings...」と一瞬表示して設定全体を無視し、デフォルト動作で起動する。エラー内容は起動直後の画面に出るが見逃しやすい。yazi 26.9.1 で `name =` キーを使って発生したのを確認済み(正しくは `url =`)。

## プレビュープラグイン(glow-md)

`~/.config/yazi/plugins/glow-md.yazi/main.lua`(2026-09-26 作成)

カーソルを合わせただけで、右側のプレビュー欄に md を glow で整形表示するプラグイン。[Reledia/glow.yazi](https://github.com/Reledia/glow.yazi) を元に、yazi 26.x で変わった Lua API(`args` → `arg`、`ya.mgr_emit` → `ya.emit`、`ya.preview_widgets` → `ya.preview_widget`)に合わせて修正した自作版。元のプラグインは 26.x では「Lua error during peek」になるため使えない。

## office プレビュープラグイン(office)

`~/.config/yazi/plugins/office.yazi/main.lua`(2026-09-26 作成)

pptx / docx / xlsx などにカーソルを合わせると、プレビュー欄に中身を表示する自作プラグイン。Quick Look(`qlmanage`)は xlsx が真っ白になったり pptx のレイアウトが崩れるため、LibreOffice(`soffice`、インストール済み)で変換する方式にした。

- スライド・文書(pptx, ppt, odp, docx, doc, odt): PDF に変換し、実際のスライド / ページの見た目そのままの画像を表示。`J` / `K` でページ送り
- 表計算(xlsx, xls, ods): 先頭シートを列を揃えたテキスト表で表示(先頭 500 行まで。色やグラフは出ない)
- 初回のみ変換に 2〜5 秒かかる。結果は `/tmp/yazi-office-cache/` にキャッシュされる。プレビュー時に元ファイルの内容を照合するため、同じ秒に複数回保存しても再変換される
- 全シート・グラフまで見たいときは Enter で LibreOffice が開く(2026-09-26 に macOS の関連付けを `duti` で Microsoft Office → LibreOffice に変更。Office ライセンス未所持のため。対象: pptx / ppt / xlsx / xls / docx / doc)

## HTML プレビュープラグイン(html-view)

`~/.config/yazi/plugins/html-view.yazi/main.lua`(2026-09-26 作成)

`.html` / `.htm` にカーソルを合わせると、ヘッドレス Chrome(画面なしで裏で動く Chrome)でレンダリングした見た目がプレビュー欄に出る。CSS・日本語フォント込みで実際の表示と同じ。ファイルの内容を変更すると自動で再レンダリングされる(内容でキャッシュ判定)。キャッシュは `/tmp/yazi-html-cache/`。

静止画なのでアニメーションや hover 効果は見えない。改修しながら動きも見たいときは live-server を使う。

### live-server(HTML は Enter で起動)

yazi で HTML ファイルを選んで **Enter** を押すと live-server が起動し、ブラウザが開く(起動スクリプト: `~/.config/yazi/open-live-server.sh`)。以降、その HTML を保存するたびブラウザが自動リロードされる。**終了は Ctrl+C**(yazi に戻る)。

- live-server 起動中は yazi が待ち状態になるので、編集は別ペイン・別ウィンドウで行う
- HTML を micro で編集したいときは **Shift+Enter** → 「$EDITOR」を選ぶ
- yazi を使わず手動で起動する場合: `cd 対象フォルダ && live-server`
- live-server 1.2.2 は npm でグローバルインストール済み(2026-09-26)

## エディタ(micro)

- `brew install micro`(2.0.15、2026-09-26 導入)
- micro は「Ctrl+S で保存、Ctrl+Q で終了」の一般的な操作感のエディタ。vim のモード切替は不要
- `~/.zshrc` に `export EDITOR=micro` / `export VISUAL=micro` を設定済み。yazi のデフォルト opener は `${EDITOR:-vi}` を使うため、md 以外のテキストファイルも Enter で micro が開く

## キーマップ

`~/.config/yazi/keymap.toml`(2026-09-26 作成)

```toml
[mgr]
prepend_keymap = [
	{ on = "<C-p>", run = "shell --orphan -- qlmanage -p %s", desc = "Quick Look でプレビュー" },
]
```

`Ctrl+P` で macOS の Quick Look(Finder のスペースキー相当)が開く。pptx / xlsx / docx / PDF / 画像 / 動画など、mac が表示できるものは何でも見られる。閉じるのは Esc。`qlmanage -p` は macOS 標準の Quick Look をコマンドラインから呼ぶツール。

## 使い方

- `Enter`: 選択中の md ファイルを glow で閲覧(`q` で戻る)
- `Shift+Enter`: 開き方を選ぶメニューを表示。「micro で編集」を選ぶと編集できる
- md 以外のテキストファイルは Enter で micro が開く(EDITOR 設定による)
- pptx / docx / xlsx: カーソルを合わせるだけでプレビュー欄に中身が出る(office プラグイン)
- html: カーソルでレンダリング画像をプレビュー、Enter で live-server 起動(Ctrl+C で終了)
- `Ctrl+P`: Quick Look でプレビュー(画像や PDF 向け。office ファイルは表示品質が低いためプレビュー欄推奨)
- `~`: yazi の全キー操作一覧を表示(そのまま検索も可能)

## 参考

- <https://github.com/sxyazi/yazi>
- opener の公式ドキュメント: <https://yazi-rs.github.io/docs/configuration/yazi#opener>
