# エージェントツール

## ツール一覧

| ツール | バージョン | 実行ファイル |
|:--|:--|:--|
| Codex CLI | `0.144.6` | `/opt/homebrew/bin/codex` |
| Claude Code | `2.1.278` | `~/.local/bin/claude` |
| Kiro CLI | `1.1.14` | `/usr/local/bin/kiro` |
| Herdr | `0.9.1` | `/opt/homebrew/bin/herdr` |
| Neovim | `0.12.4` | `/opt/homebrew/bin/nvim` |

2026-09-21 の棚卸し時点では、Gemini CLI は `PATH` 上に見つからなかった。

## 共通の指示ファイル

Kiro は `~/.zprofile` と `~/.zshrc` の両方に起動前・起動後のブロックを追加する。Kiro のターミナル専用の zsh 連携は、`TERM_PROGRAM` が `kiro` のときだけ読み込まれる。

プロジェクト固有の `AGENTS.md`・`CLAUDE.md`・スキル・フックは、適用範囲や権限がそれぞれ違うため、リポジトリごとに記録する。これらのファイルに認証情報やマシン固有の秘密の値をコピーしないこと。

## ワークフロー

現在のターミナル構成は次の組み合わせを前提にしている:

1. ターミナルエミュレータとして Ghostty または WezTerm
2. AI エージェントの永続ワークスペースとして Herdr
3. ペインとウィンドウのレイアウトを明示的に組むための tmux
4. 対話シェルとして zsh + Starship
5. コーディングエージェントとして Codex・Claude Code・Kiro のいずれか
6. Markdown の閲覧に Glow
7. ターミナルエディタとして Neovim

タスク単位のエージェント作業(Claude Code・Codex・Pi・Kiro をローカルで動かすタスクボード。タスクごとに herdr のワークスペースを 1 つ使う)は別リポジトリにある: `~/AIprogramming PJ/task-hub`(`task` CLI、`/task` スキル)、https://github.com/jyoka/task-hub 。詳しくはその README を参照。

## 権限と安全

- API キーやトークンは環境変数か、承認済みのシークレットストアに置く。
- 記録するのは変数名だけにし、値は絶対に書かない。
- ログにはプロジェクトのパスやコマンド引数が含まれることがあるので、コピーする前に中身を確認する。
- プロジェクト固有の権限設定は、そのプロジェクトのエージェント向け指示ファイルに置く。

## トラブルシューティング

### インストール済みのバージョンを確認する

```bash
codex --version
claude --version
kiro --version
herdr --version
nvim --version
```

### エージェントのコマンドが見つからない

`exec zsh` で新しい zsh セッションを開始し、`PATH` に Homebrew と `~/.local/bin` が含まれていることを確認する。
