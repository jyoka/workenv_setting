# LOOP: Herdr status monitor

## 目的(1文)

HerdrのタブバーにMacのCPU・メモリ・エージェント状態と、入っているAIツールの利用枠(Codexは`CX 5時間枠%·週の枠%`、Claude Codeは`CC 5時間枠%·週の枠%`、Kiroは`KR 使ったクレジット/上限`)を表示し、各Agent行に現在のネイティブセッションの累積処理トークン数、各Space行にworkspace内のunique session合計を表示する。

## トリガーとcadence

- 起動方式: Herdr `ui.tab_bar_right` のcommand entry
- 頻度: Herdrクライアント表示中に10秒ごと
- 実行環境: ローカルMac上のHerdr server

## 停止条件(検証可能な形式で)

- 1回の実行が5秒以内に終了する(内部処理は4.5秒の共通期限内、4.75秒を超える場合はworkerを停止して `󰓅 ? |  ? | 󰚩 0 / 󰏤 0 / 󰒠 0` を返す。利用枠の対象ツールが入っていれば後ろに ` | CX ?`、` | CC ?`、` | KR ?` を付ける。ただし最後に読んだ値が非表示(Kiroが未ログイン)のものは付けない。この判定はファイルを読むだけで、コマンドは実行しない)
- 標準出力の最終行が `󰓅 ... |  ... | 󰚩 ... / 󰏤 ... / 󰒠 ...[ | CX ...][ | CC ...][ | KR ...]` の形式になる(利用枠は `LIMIT_PROVIDERS` の順に ` | ` 区切りで続く。CPUは Nerd Font `nf-md-speedometer` U+F04C5、MEMは `nf-fa-memory` U+EFC5、作業中のエージェント数は `nf-md-robot` U+F06A9、待ち(Blocked)の数は `nf-md-pause` U+F03E4、合計は `nf-md-sigma` U+F04A0 のアイコンで表す。Herdr 0.9.1 はANSIの色を消すので、色のエスケープは出さない)
- Agent sessionが取得できる場合、対象paneに`tokens` metadataを報告する
- `codex`がPATHにあるとき`CX <5h>%·<週>%`を出す。5時間と週は`window_minutes`(300/10080)で判断する。`codex`が無いときは`CX`を出さない
- `claude`がPATHにあるとき`CC <5h>%·<週>%`を出す。値はClaude Codeの`statusLine`(`scripts/claude_statusline.py`)が`~/.cache/herdr/claude-rate-limits.json`に原子的に書いたものを読む。`rate_limits`が無いJSONではファイルを変えない。`claude`が無いときは`CC`を出さない
- `kiro-cli`がPATHにあるとき`KR <使った>/<上限>`(例 `KR 27/50`、小数は四捨五入)を出す。値は常駐の`herdr_status.py --kiro-daemon`が`~/.cache/herdr/kiro-usage.json`に原子的に書いたものを読む。`kiro-cli`が無いとき、または`kiro-cli whoami`が失敗する(未ログイン)ときは`KR`を出さない
- Kiroの常駐プロセス: `~/.cache/herdr/kiro-usage.pid`のロックで1本だけ。ロックが空いていればstatus commandが切り離して起動する(待たない)。`kiro-cli acp`を1本動かし続け、セッションは最初の1回だけ`session/new`し、以後は`session/load`で同じセッションを使う。5分ごとに`usage`を送る。`~/.cache/herdr/kiro-usage.off`があれば起動せず、動いていれば終わる
- 利用枠の値がないときは`?`、30分より古いときは数字に`~`、`resets_at`(Kiroは`billingCycleReset`の日の00:00 UTC)を過ぎた枠は`0%`(Kiroは使った数を`0`)
- Agent processが`unknown`または停止中でも、paneにnative session参照があれば集計対象にする
- HerdrがAgentを検出できない場合はAgent行自体が生成されないため、Space行のworkspace合計を必須fallback表示とする
- Kiro CLIのnested PTYがHerdr内でagent processを隠さないよう、`HERDR_ENV`内ではKiro shell initをskipする
- workspaceには同じsessionを重複加算せず、unique session合計を報告する
- Agent sessionが取得できない場合、他の表示を壊さず`tokens=n/a`を報告する
- 判定者: Python unit tests、`herdr config check`、実行時間と実画面の人間確認
- 最大試行回数: 1回の起動につき1回。失敗時は次の10秒周期まで再試行しない

## 権限境界

### 無人で実行可

- `top`、`memory_pressure`、Herdr CLIからの読み取り
- CodexとClaudeの現在のsession JSONLからusageフィールドだけを読み取る
- 最新のCodex rollout JSONLの末尾から`token_count`の`rate_limits`だけを読み取る
- `~/.cache/herdr/claude-rate-limits.json`(Claude Codeの`statusLine`が書く利用枠のキャッシュ)を読み取る
- Kiroの常駐プロセスを起動する。常駐プロセスは`kiro-cli whoami`(終了コードのみ)と`kiro-cli acp`を実行し、`usage`コマンドだけを送る(モデルは呼ばず、クレジットを使わない)。セッションは1つだけ作り、使い回す
- `~/.cache/herdr/kiro-usage.json`と`~/.cache/herdr/kiro-usage.pid`の原子的な更新
- `herdr pane report-metadata`による表示専用metadata更新
- `~/.cache/herdr/status-cache.json`の原子的な更新

### 人間ゲート必須

- `~/.config/herdr/config.toml`への初回設定追加
- `~/.claude/settings.json`への`statusLine`の追加(`herdr.md`の手順で人が行う)
- 他のagent種類への対応追加
- token定義や表示頻度の変更

### 禁止

- agent sessionファイルの変更
- agentへのprompt送信やキー入力
- 外部API呼び出し(例外: Kiroの常駐プロセスが`kiro-cli acp`の`usage`コマンド経由で5分ごとにクレジットの使用量を問い合わせることだけ)
- `kiro-cli acp`へのprompt送信、2つ目以降のKiroセッションの作成
- token値から料金を推定して確定値として表示すること
- API key、prompt本文、agent出力の保存

## 検証カスケード

1. 決定的: `python3 -m unittest discover -s tests -p 'test_*.py'`、`python3 scripts/herdr_status.py`
2. ルール: 標準出力は1行、cache以外への書き込みなし、session JSONLはread-only
3. LLM verifier: 使用しない

## 状態

- stateファイル: `~/.cache/herdr/status-cache.json`
- 書き込み内容: session path、読み取りoffset、message ID別usage合計、最終更新時刻、`limits`(ツール別の最後の利用枠の値と観測時刻)
- Kiroのstateファイル: `~/.cache/herdr/kiro-usage.json`(常駐プロセスだけが書く。`observed_at`、`used`、`limit`、`resets_at`、`logged_in`、使い回すセッションのID)、`~/.cache/herdr/kiro-usage.pid`(常駐プロセスのpidとロック)。`kiro-usage.json`を消すとセッションIDを失い、次の起動で新しいセッションが1つできる
- Compaction: audit logではないため、scriptが最大128 sessionに決定的に制限する。手動削除しても次回再構築される

## コスト見積もり

- 1実行あたり概算トークン: 0
- 月間概算: 0 LLM tokens、外部API料金0円
- 空振り時: system metricsの取得と`herdr api snapshot`のみ
- ローカル負荷: 10秒ごとに短時間の`top`、`memory_pressure`、Herdr CLI実行。Kiroが入っていれば常駐の`kiro-cli acp`1本と、5分ごとの`usage`問い合わせ

## エスカレーション

- 通知先: なし。workerがタイムアウトしたら不明値を表示し、次回周期で再試行
- エスカレーション条件: 連続して表示されない、5秒timeout、agent log schema変更、`kiro-cli acp`の`usage`の形の変更(非公式。kiro-cli 2.22.1で確認)、`~/.kiro/sessions/cli/`のセッションが増える

## レビュー計画(人間の帯域)

- 成果物のレビュー所要時間見込み: 初回2分、その後は不具合時のみ
- レビュー担当と確認タイミング: ユーザーがHerdr再読み込み後に表示と値を確認
