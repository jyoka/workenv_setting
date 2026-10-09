# Herdr

## 目的

AI コーディングエージェント向けのターミナルワークスペース管理ツール。永続セッション、ワークスペース、ペイン、エージェント連携、SSH リモート、そしてアップデート時やリモート接続時のライブ引き継ぎ(ハンドオフ)を提供する。

## インストール

- 実行ファイル: `/opt/homebrew/bin/herdr`
- インストール済みバージョン: `0.9.1`
- アップデートチャンネル: `stable`
- プロトコル: `22`
- 取得時点のサーバーの状態: 稼働中、エンドポイント互換あり
- ローカルソケット: `~/.config/herdr/herdr.sock`
- ホームページ: <https://herdr.dev>

## 設定

- 設定ファイル: `~/.config/herdr/config.toml`
- セッションの状態: `~/.config/herdr/session.json`
- プラグインのロックファイル: `~/.config/herdr/.plugins.lock`
- クライアントのログ: `~/.config/herdr/herdr-client.log`
- サーバーのログ: `~/.config/herdr/herdr-server.log`
- 設定ファイルの場所を上書きする変数: `HERDR_CONFIG_PATH`

現在明示している設定:

```toml
onboarding = false

[theme]
name = "nord"
auto_switch = false

[ui]
tab_bar_right = [
  { type = "command", command = "python3 '/Users/<user>/.config/herdr/scripts/herdr_status.py'", interval_seconds = 10, timeout_seconds = 5 },
  { type = "hostname" },
  { type = "datetime", format = "%H:%M" },
]
tab_bar_right_separator = " · "

[ui.sidebar.agents]
row_gap = 0
rows = [
  ["state_icon", "workspace", "tab"],
  ["agent", "$tokens", "state_text"],
]

[ui.sidebar.spaces]
row_gap = 0
rows = [
  ["state_icon", "workspace"],
  ["branch", "git_status"],
  ["$tokens"],
]
```

それ以外の動作はすべて Herdr のデフォルトのまま。

## ステータスダッシュボード

デスクトップのタブバー右側は 10 秒ごとに更新され、次のように表示される:

```text
󰓅 19% |  27% | 󰚩 0 / 󰏤 0 / 󰒠 0 | CX 83%·40% | CC 37%·22% | KR 27/50 · hostname · 00:00
```

- `󰓅`(Nerd Font `nf-md-speedometer`、U+F04C5、メーター): 現在の CPU 使用率(ユーザー + システム)
- ``(Nerd Font `nf-fa-memory`、U+EFC5、メモリの絵): メモリプレッシャーから算出した使用率
- `󰚩`(Nerd Font `nf-md-robot`、U+F06A9、ロボット): 作業中のエージェント数
- `󰏤`(Nerd Font `nf-md-pause`、U+F03E4、一時停止マーク): 止まっている(人間の返答や確認を待っている)エージェント数
- `󰒠`(Nerd Font `nf-md-sigma`、U+F04A0、合計記号): 検出したエージェントの合計数
- `CX 83%·40%`: Codex の利用枠。5 時間枠の使用率、続いて週の枠の使用率(後述)
- `CC 37%·22%`: Claude Code の利用枠。形式は同じ(後述)
- `KR 27/50`: Kiro のクレジット。今の請求期間で使った量と上限(後述)
- `hostname`: Herdr サーバーを動かしているマシン
- 最後の値: サーバーのローカル時刻

ステータススクリプトが制限時間内に終わらなかった場合、このコマンドの欄は `󰓅 ? |  ? | 󰚩 0 / 󰏤 0 / 󰒠 0` と表示され、利用枠の欄を持つツールがインストールされていれば、ツールごとに ` | CX ?` / ` | CC ?` / ` | KR ?` が続く(例: `󰓅 ? |  ? | 󰚩 0 / 󰏤 0 / 󰒠 0 | CX ? | CC ? | KR ?`)。この代替表示はファイルを読むだけで、ツール自体は実行しない。最後に読んだ値が非表示だった欄(`~/.cache/herdr/kiro-usage.json` で Kiro がログアウト中と分かっている場合)は、ここでも表示しない。

### AI の利用枠

エージェント数の後ろに、このマシンにインストールされている AI ツールごとに 1 つずつ、利用枠をどれだけ使ったかを表示する(CPU や MEM と同じく、数字が大きいほど上限に近い)。Kiro だけが入っている Mac では `KR` だけが表示される:

- `CX <5h>%·<week>%`: Codex。`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` のうち更新日時が最も新しいファイルを末尾から読み、最後の `token_count` イベント(`payload.rate_limits`)から取得する。`primary` / `secondary` は並び順ではなく `window_minutes`(300 または 10080)で 5 時間枠か週の枠かを判断する。利用枠はアカウント単位なので、Herdr のペインで Codex が動いているかどうかに関係なく、どの rollout でも使える。
- `CC <5h>%·<week>%`: Claude Code。Claude Code のトランスクリプトには利用枠の情報がない。Claude Code が利用枠を渡すのは `statusLine` コマンドの標準入力だけ(`rate_limits.five_hour` / `rate_limits.seven_day`、それぞれ `used_percentage` と `resets_at`)。`scripts/claude_statusline.py` がそのコマンドで、2 つの枠を `~/.cache/herdr/claude-rate-limits.json` に原子的に書き込み、`herdr_status.py` がそのファイルを読む。利用枠は claude.ai の Pro/Max でログインしているときだけ、しかもセッションの最初の API レスポンスの後にしか渡されないため、このファイルは何らかの Claude Code セッションが動いている間しか書かれない。非公式の OAuth 利用量エンドポイントは使わない。
- `KR <used>/<limit>`: Kiro のクレジット。Kiro IDE と同じ表示(`27.31 of 50` を `27/50` と表示)。Kiro にはローカルの利用ログがないため、常駐プロセスが 5 分ごとに `kiro-cli acp` に問い合わせる。[Kiro クレジット取得デーモン](#kiro-クレジット取得デーモン) を参照。値は `data.usageBreakdowns[]` のうち `hasLimit` かつ `limit > 0` の最初の要素で、上限には `bonusCredits` / `addOnCredits` の各要素の `limit` を足す。Kiro 側の数値の更新は数分遅れる。

すべての欄に共通するルール:

- コマンド(`codex`、`claude`、`kiro-cli`)が `PATH` にないツールは何も表示しない(`?` も出さない)。Kiro は `kiro-cli whoami` が未ログインと答えている間も何も表示しない。
- インストール済みだがまだ値がない場合: `CX ?` / `CC ?` / `KR ?`(Claude Code の場合は、後述の `statusLine` が未設定か、Pro/Max のセッションでまだ API レスポンスがない。Kiro の場合は常駐プロセスが起動した直後)。片方の枠だけ値がなければ、その位置に `?` を表示する(例: `CX 50%·?`)。
- 値が 30 分より古い場合(Codex は動いている間だけ、Claude Code はセッションがステータスラインを更新している間だけ利用枠を書く。Kiro の常駐プロセスは動いている間 5 分ごとに書く): 各数字に `~` を付ける(例: `CX ~83%·~40%`、`KR ~27/50`)。
- `resets_at` を過ぎた枠は `0%` と表示する(値が古ければ `~` は付いたまま。他の端末でその後使われているかもしれないため)。Kiro は `billingCycleReset`(その日の 00:00 UTC とみなす)を過ぎると使用量を `0` と表示する。
- 最後に正しく読めた値は `~/.cache/herdr/status-cache.json` の `limits` にキャッシュするので、ログが無い・読めない場合でも前回の値を表示する(古くなれば `~` 付き)。読み取りに失敗した欄は `?` を表示し、CPU・MEM・エージェントの欄は壊さない。

ツールを追加するには、`observed_at`(Unix 秒)を含む JSON 化できる dict を返す読み取り関数を書き、`scripts/herdr_status.py` の `LIMIT_PROVIDERS` に `LimitProvider(label, command, read, render)` を追加する。パーセント表示の枠なら `render_percent_windows` を再利用できる。`"hidden": true` を含む値を返すと、その欄は非表示になる。

### Kiro クレジット取得デーモン

`kiro-cli acp` は、標準入出力上の JSON-RPC(1 行 1 メッセージ。`initialize`、次にセッション、次に `{"command": "usage", "args": {}}` を付けた `_kiro.dev/commands/execute`)で `usage` スラッシュコマンドに応答する。モデルは呼ばずクレジットも消費しないが、ドキュメント化された API ではなく(kiro-cli 2.22.1 で確認)、`session/new` を呼ぶたびに `~/.kiro/sessions/cli/` にファイルが増える。そのため、ステータススクリプト自身は呼び出さない:

- `herdr_status.py --kiro-daemon` がバックグラウンドで、ユーザーごとに 1 つだけ動く。`kiro-cli acp` を 1 つ動かし続け、初回だけセッションを作成し、再起動後も(id を指定した `session/load` で)同じセッションを使い回す。そのため `~/.kiro/sessions/cli/` のセッションは 1 つ(`<id>.json`、`<id>.jsonl`、デーモンが開いている間は `<id>.lock`)だけで、それ以上増えない。5 分ごとにそのセッションに `usage` を送り、`~/.cache/herdr/kiro-usage.json`(`observed_at`、`used`、`limit`、`resets_at`、セッション id、`logged_in`。トークンは含まない)を書き込む。
- 動いている間ずっと `~/.cache/herdr/kiro-usage.pid` をロックしている(動作中は pid が書かれ、終了時に空になる)ので、2 つ目を起動してもすぐに終了する。ステータスの更新のたびにこのロックを確認し、誰も持っていなければデーモンを切り離して起動するため、kill されたりクラッシュしたりしても 10 秒以内に復帰する。ステータススクリプトはキャッシュファイルを読むだけで、Kiro を待つことはない。
- `kiro-cli acp` を起動する前に `kiro-cli whoami` を実行する(終了コードだけを見る)。未ログインなら `logged_in: false` を書き込み、`KR` は表示されなくなり、5 分後に再確認する。`kiro-cli acp` が終了したりリクエストが失敗したりした場合は、5 分後に同じセッションで再試行する。

止めるには(そのままだと次の更新で再起動してしまうので)、停止用ファイルを作ってから kill する:

```bash
touch ~/.cache/herdr/kiro-usage.off
kill "$(cat ~/.cache/herdr/kiro-usage.pid)"
```

デーモンを kill すると、その `kiro-cli acp` も止まる。デーモンが動いていなければ pid ファイルは空なので、`kill` の行はエラーを表示するだけ。`kill` しなくても、デーモンは 5 分以内に自分で終了する。停止用ファイルがある間、`KR` は最後の値を表示し続け、30 分経つと `~` を付ける。再開するには `rm ~/.cache/herdr/kiro-usage.off` を実行すれば、次の更新で起動する。新しい `herdr_status.py` を `~/.config/herdr/scripts/` にコピーした後は、`kill` の行だけを実行すれば、次の更新で新しいコードのデーモンが起動する。`~/.cache/herdr/kiro-usage.json` を削除するとセッション id が失われるため、次の起動時に新しいセッションが 1 つ作られる。

### Claude Code の statusLine(手動設定)

`CC` の欄を出すには、Claude Code のステータスラインとして `claude_statusline.py` を実行させる必要がある。このリポジトリは `~/.claude/settings.json` を書き換えない。マージ後に、スクリプトを Herdr のステータススクリプトと同じ場所へコピーし、`~/.claude/settings.json` に `statusLine` キーを手で追加する(すでに `statusLine` が設定されていると置き換わってしまうので、その出力内容を先にスクリプトへ取り込んでおく):

```bash
cp scripts/claude_statusline.py ~/.config/herdr/scripts/
```

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.config/herdr/scripts/claude_statusline.py"
  }
}
```

これで Claude Code の各セッションの下部、フッターのバッジの上に 1 行が追加される。例:

```text
Opus · workenv_setting · 5h 37% · 7d 22%
```

表示内容は、モデル、現在のディレクトリ名、5 時間枠と 7 日枠の使用率(セッションに利用枠の情報が来るまで枠の部分は出ない)。独自のステータスラインを設定すると、Claude Code は `esc to interrupt` などフッターのキーヒントの大半を表示しなくなる。スクリプトは標準入力以外は何も読まず、書き込むのは `~/.cache/herdr/claude-rate-limits.json`(`observed_at` と `5h` / `week` の枠のみ。トークンやプロンプトは含まない)だけ。`rate_limits` を含まない JSON(API キーでのログイン時や、最初のレスポンスの前)ではファイルを変更しない。Claude Code は `resets_at` を過ぎた枠を送らなくなるが、スクリプトは過去の `resets_at` のままキャッシュの枠を残すので、タブバーにはその枠が `?` ではなく `0%` と表示される。

### タブバーの文字色

Herdr 0.9.1 は `type = "command"` の出力から ANSI エスケープを取り除くので、スクリプトは素のテキストを出力するしかなく、値に色を付けられない。右側の文字色はテーマのトークン `overlay1` で決まる(nord のデフォルトは `#646e82` で、暗い背景では読みにくい)。明るくするには、`~/.config/herdr/config.toml` に次を手で追加して `herdr server reload-config` を実行する:

```toml
[theme.custom]
overlay1 = "#d8dee9"  # nord4 (Snow Storm)
```

`overlay1` はグローバルなトークンなので、ステータス欄だけでなく、新規タブの `+` ボタンなど、このトークンを使う Herdr の控えめな UI の色もすべて変わる。`ui.tab_bar_right` には欄ごとのスタイル指定がない(herdrdev/herdr#4304 は not planned としてクローズされた)。

Herdr が動作中のエージェントを検出すると、展開した Agent 行にエージェントの種類、ネイティブセッションの累積トークン数、状態(semantic state)が表示される。Herdr 0.9.1 は現在このマシンで動いている Codex と Claude のペインを `unknown` と分類するため、それらの Agent 行は作られない。そこで、各 Space 行には、そのワークスペースのペインにつながっている Codex と Claude のセッション(重複なし)の合計も表示している。このワークスペース合計は、エージェントのプロセスが止まっていたり一時的に検出されなかったりしても表示され続ける。

トークン数は、ネイティブセッションのログに記録された処理済みトークンの累計(キャッシュされた入力を含む)を意味する。料金の見積もりではなく、コンテキストウィンドウの残り容量を示すものでもない。セッションが無い、または未対応の場合は `n/a` と表示する。

### 2026-09-22 の表示修正

最初の実装は `herdr agent list` だけを読んでいた。この API は、ペインが有効なネイティブセッション参照を持っていても、エージェントのプロセスが止まっているか `unknown` に分類されているペインを返さない。現在のモニターは `herdr api snapshot` からセッションを持つすべてのペインを読み、トークン数をペインに報告し、その合計をワークスペースに報告する。

Agent パネルが空だったのは別の原因による。Kiro CLI のシェル初期化が `kiro-cli-term` を起動し、Codex と Claude を入れ子の疑似端末(PTY)の中に入れていたため、Herdr にはエージェントのプロセスではなく外側のラッパーが見えていた。現在は `HERDR_ENV` が設定されているときだけ、`~/.zshrc` と `~/.zprofile` の Kiro の起動前・起動後ブロックをスキップする。新しい Herdr ペインでは本物のフォアグラウンドのエージェントプロセスが見え、Herdr の外のターミナルでは Kiro 連携がそのまま使える。すでにラップされているペインは作り直す必要がある。

修正後に確認した実際の値:

- `ai-CA_RA-A2A-PoC`: `Σ 25.6M tok`
- Claude のペイン `w1:p4`: `11.8M tok`
- Codex のペイン `w1:p6`: `13.8M tok`
- 2 つ目の作業用ワークスペース: `Σ 11.3M tok`

実装:

- スクリプト(実行される本体): `~/.config/herdr/scripts/herdr_status.py`(2026-09-26 にグローバル位置へ移動。このリポジトリの外にあるので、リポジトリを移動・削除してもステータス表示は壊れない)
- スクリプト(ソース管理用マスター): `workenv_setting/scripts/herdr_status.py`。修正したら `cp scripts/herdr_status.py ~/.config/herdr/scripts/` で反映する
- ループの仕様: `workenv_setting/loops/herdr-status-monitor.md`
- キャッシュ: `~/.cache/herdr/status-cache.json`
- Kiro のクレジット: `herdr_status.py --kiro-daemon`(ステータススクリプトが起動する)が `~/.cache/herdr/kiro-usage.json` に書き込む。pid とロックは `~/.cache/herdr/kiro-usage.pid`
- Claude Code の利用枠: `~/.config/herdr/scripts/claude_statusline.py`(マスター: `workenv_setting/scripts/claude_statusline.py`)が `~/.cache/herdr/claude-rate-limits.json` に書き込む
- 更新: Herdr のコマンド型ステータス欄で 10 秒ごと
- 外部 API や LLM の利用: LLM は呼ばない。Kiro のデーモンが 5 分ごとに `kiro-cli acp` 経由で Kiro のサービスにクレジットの使用量を問い合わせる
- 設定のバックアップ: `~/.config/herdr/config.toml.backup-20260922-status`

ダッシュボードを無効にするには、バックアップを戻して再読み込みする:

```bash
cp ~/.config/herdr/config.toml.backup-20260922-status ~/.config/herdr/config.toml
herdr server reload-config
```

## コマンドと使い方

```bash
herdr                         # 永続セッションを起動、またはアタッチ
herdr --session NAME          # 名前付きセッションを使う(なければ作成)
herdr session attach NAME     # 名前付きセッションにアタッチ
herdr status server           # サーバーの状態を確認
herdr status client           # クライアントの状態を確認
herdr server reload-config    # config.toml の変更を反映
herdr server stop             # ローカルサーバーを停止
herdr update --handoff        # ライブ引き継ぎ付きでアップデート
herdr completion zsh          # zsh の補完スクリプトを生成
```

リモートとマシン関連のコマンド:

```bash
herdr --remote HOST
herdr --machine LABEL COMMAND
herdr machine --help
```

## キーバインド

ルールは 1 つ。**Option = herdr(ターミナルの中)、Ctrl+Option = AeroSpace(ウィンドウ同士)**。prefix(Ctrl+B を押してから文字)を使わずに、1 回の操作で動く。prefix の既定キーもそのまま使える。

`~/.config/herdr/config.toml` の末尾に `[keys]` を追加した(2026-10-09、変更前のバックアップは `config.toml.backup-20261009-keys`):

```toml
[keys]
switch_tab = "alt+1..9"
new_tab = "alt+n"
new_workspace = "alt+shift+n"
previous_workspace = "alt+["
next_workspace = "alt+]"
workspace_picker = "alt+w"
focus_pane_left = "alt+shift+left"
focus_pane_down = "alt+shift+down"
focus_pane_up = "alt+shift+up"
focus_pane_right = "alt+shift+right"
split_vertical = "alt+v"
split_horizontal = "alt+minus"
zoom = "alt+z"
close_pane = "alt+x"
```

| 操作 | キー |
|:--|:--|
| タブ 1〜9 へ移動 / 新しいタブ | Option+1〜9 / Option+N |
| 新しいワークスペース | Option+Shift+N |
| 前 / 次のワークスペース | Option+[ / Option+] |
| ワークスペースを一覧から選ぶ | Option+W |
| 隣のペインへ移動 | Option+Shift+矢印 |
| 左右に分割 / 上下に分割 | Option+V / Option+- |
| ペインを最大化(もう一度で戻る) | Option+Z |
| ペインを閉じる | Option+X |

- Option が herdr に届くのは、Ghostty の設定 `macos-option-as-alt = true` のおかげ([ghostty.md](./ghostty.md))
- Option+矢印と Option+B / F / D は使っていない。シェルが「単語単位でカーソル移動・削除」に使うため
- 変更後は `herdr config check` で検証し、`herdr server reload-config` で反映する
- カスタムキーを全部消して既定に戻すには `herdr config reset-keys`(config.toml は自動でバックアップされる)

## トラブルシューティング

### 設定の変更が反映されない

動いているサーバーに再読み込みさせる:

```bash
herdr server reload-config
```

### ログを確認する

```bash
tail -f ~/.config/herdr/herdr-server.log
tail -f ~/.config/herdr/herdr-client.log
```

ログ全体をこのリポジトリにコピーする場合は、事前にプロジェクトのパスや機密情報が含まれていないか確認すること。

## 参考

- <https://herdr.dev>
- 初めて使うエージェント向けガイド: <https://herdr.dev/agent-guide.md>
- デバッグ用リファレンス: <https://herdr.dev/llms.txt>
