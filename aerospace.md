# AeroSpace

## 目的

macOS で Hyprland に近い操作感を得るためのタイル型ウィンドウマネージャー。新しいウィンドウが自動で画面を分け合い、重ならない。キーボードだけでウィンドウとワークスペース(仮想デスクトップ)を移動できる。

主な使い方: Ghostty でエージェントと会話しながら、変更されたファイルを VS Code の別ウィンドウで横に並べてレビューする。

## インストール

```bash
brew install --cask nikitabobko/tap/aerospace
cp config/aerospace/aerospace.toml ~/.aerospace.toml
open -a AeroSpace
```

初回起動時にアクセシビリティ権限を求められる。システム設定 → プライバシーとセキュリティ → アクセシビリティで AeroSpace を許可する。ウィンドウを動かすのに必要な権限のため。

- 記録時のバージョン: 0.21.3-Beta(2026-10-09)
- 設定のマスター: [`config/aerospace/aerospace.toml`](./config/aerospace/aerospace.toml)
- 実際に読まれる場所: `~/.aerospace.toml`
- ログイン時に自動起動する(`start-at-login = true`)
- 設定ファイルを保存すると自動で再読み込みされる(`auto-reload-config = true`)

## ショートカット

ルールは 1 つ。**すべて Ctrl+Option で始まる**。Shift を足すと「移動」になる。prefix キー(先に押す決まったキー)は不要。

| 操作 | キー |
|:--|:--|
| 隣のウィンドウへフォーカス(画面の端では隣のモニターへ移る) | Ctrl+Option+矢印 |
| ウィンドウを隣へ動かす(画面の端では隣のモニターへ運ぶ) | Ctrl+Option+Shift+矢印 |
| ワークスペース 1-5 へ切り替え | Ctrl+Option+1〜5 |
| ウィンドウをワークスペース 1-5 へ送る | Ctrl+Option+Shift+1〜5 |
| 直前のワークスペースへ戻る | Ctrl+Option+Tab |
| 幅を縮める / 広げる | Ctrl+Option+- / = |
| 全画面の切り替え(じっくり読むとき) | Ctrl+Option+F |
| 横並び / 縦並びの切り替え | Ctrl+Option+/ |
| 重ねて表示(アコーディオン) | Ctrl+Option+, |
| このウィンドウだけ浮かせる / 戻す | Ctrl+Option+Space |

### モニターとワークスペースの割り当て

- 外部モニター(macOS の「secondary」): ワークスペース 1〜3
- ノートの画面(macOS の「main」= メニューバーのある画面): ワークスペース 4〜5
- 割り当てを固定しないと、2 枚目のモニター用に AeroSpace が「6」などを勝手に作り、ショートカットで行けなくなる(2026-10-09 に実際に起きた)
- この Mac では外部モニターがノートの画面の**上**にある。外部モニターから Ctrl+Option+↓ でノートの画面へ移る
- ノート単体(外部モニターなし)のときの動きは未確認

### よくある操作

VS Code を Ghostty の横に持ってくる:

1. Ctrl+Option+矢印 で VS Code にフォーカスする(別のモニターにあれば、そちらへ向かう矢印を押す)
2. Ctrl+Option+Shift+矢印 で Ghostty の方向へ運ぶ。モニターの端を越えると隣のモニターへ移る
3. 並び順を変えたいときは、もう一度 Ctrl+Option+Shift+←/→

Option だけ(Ctrl なし)にしなかった理由: macOS では Option+矢印が「単語単位でカーソル移動」に使われており、それを奪わないため。

## エージェントとの連携: ファイルをすぐ開いてレビューする

チャットで「このファイルを開いて」「変更を見せて」と頼むと、エージェントが VS Code で開く。AeroSpace が Ghostty の横に自動で並べる。開くのは頼んだときだけ(編集のたびに自動では開かない)。

エージェントが使うコマンド:

```bash
VSC="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"

# ファイルを開く(:行番号 で該当行へジャンプ。-r で既存の VS Code ウィンドウを再利用)
"$VSC" -r -g path/to/file:42

# コミット前の変更を左右比較で開く(左: 最後のコミット、右: 今のファイル)
git show HEAD:path/to/file > /tmp/file.orig && "$VSC" -r --diff /tmp/file.orig path/to/file
```

この指示(「頼まれたら VS Code で開く」)を書いてある場所:

| エージェント | 指示ファイル |
|:--|:--|
| Claude Code | `~/.claude/CLAUDE.md` |
| Codex | `~/.codex/AGENTS.md` |
| Pi | `~/.pi/agent/AGENTS.md` |
| Kiro CLI | `~/.kiro/agents/coder.json` の `prompt`(既定エージェントが `coder` のため) |

### @ だけで開く

入力欄で `@` を打ってファイルを選び、**他に何も書かずに** Enter を押すと、VS Code で開く。プロンプトはモデルに送られないので、待ち時間もトークン消費もない。

| 入力 | 動き |
|:--|:--|
| `@README.md` だけ | ファイルを VS Code で開く |
| `@README.md#L10` だけ | 10 行目へジャンプして開く |
| `@config/` だけ(フォルダ) | フォルダを VS Code の新しいウィンドウで開く。左のファイル一覧と「ソース管理」で変更をまとめて見られる |
| `@a.md @b.md` だけ | 両方開く |
| `@README.md これを説明して` | 普通のプロンプトとして送る(開かない) |

判定のロジックは 1 本のスクリプトにまとめ、各エージェントから呼ぶ。直すときはこのスクリプトだけ直せばよい。

- スクリプトのマスター: [`scripts/open_mention.py`](./scripts/open_mention.py)
- 実際に動く場所: `~/.config/agent-hooks/open_mention.py`
- 存在しないパスが混じっていたら、何もせず普通のプロンプトとして送る

| エージェント | 仕組み | 登録先 | 状態 |
|:--|:--|:--|:--|
| Claude Code | `UserPromptSubmit` フック | `~/.claude/settings.json` | 動作確認済み |
| Codex | `UserPromptSubmit` フック(`--bare-paths` 付き) | `~/.codex/hooks.json` | 初回に `/hooks` で承認が必要。実機の Enter は未確認 |
| Pi | 拡張の `input` イベント | `~/.pi/agent/extensions/open-mention.ts`(マスター: [`config/pi/extensions/open-mention.ts`](./config/pi/extensions/open-mention.ts)) | 実機の Enter は未確認 |
| Kiro CLI | なし | - | 2.x のフックはプロンプトを止められない(モデルに送られてしまう)ため入れていない。3.0 では止められるとドキュメントにある |

登録の中身(既存の `hooks` があれば、その中に足す):

```json
// ~/.claude/settings.json の "hooks" の中
"UserPromptSubmit": [
  { "hooks": [{ "type": "command", "command": "python3 ~/.config/agent-hooks/open_mention.py", "timeout": 10 }] }
]

// ~/.codex/hooks.json の "hooks" の中
"UserPromptSubmit": [
  { "hooks": [{ "type": "command", "command": "python3 ~/.config/agent-hooks/open_mention.py --bare-paths", "timeout": 10 }] }
]
```

Codex だけ `--bare-paths` を付ける理由: Codex の `@` ピッカーはファイルを選ぶと `@` を消してパスだけを入れる。そのため「存在するパスだけのプロンプト」も開く対象にしている。副作用として、存在するファイル名 1 語だけを送ると、質問ではなく「開く」になる。

## 既知の注意点

- `code` コマンドは Cursor と VS Code の両方が作る。この Mac では Cursor が `/usr/local/bin/code`、Homebrew 版 VS Code が `/opt/homebrew/bin/code` を作っており、PATH の順で VS Code が勝つ。どちらが勝っても動くように、フックと指示では VS Code をフルパスで呼ぶ。
- VS Code は Homebrew で入れる(`brew install --cask visual-studio-code`、2026-10-09 時点 1.141.0)。ブラウザでダウンロードしたものを `mv` で Applications に移すと、macOS が毎回一時コピー(AppTranslocation)から起動し、隔離フラグも `xattr -d` で消せなかった。Finder で移し直しても直らなかった。Homebrew で入れ直したら解消した。
- VS Code のウィンドウが別のワークスペースにあると、開いたときにそちらへ切り替わる。Ghostty と同じワークスペースに置いておけば横に並ぶ(Ctrl+Option+Shift+数字で送る)。
- 設定やダイアログの小窓が勝手にタイルされて邪魔なときは、Ctrl+Option+Space で浮かせる。

## リンク

- 公式: <https://github.com/nikitabobko/AeroSpace>
- ガイド: <https://nikitabobko.github.io/AeroSpace/guide>
- コマンド一覧: <https://nikitabobko.github.io/AeroSpace/commands>
