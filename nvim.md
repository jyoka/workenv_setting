# Neovim

## 目的

ターミナル内で使うエディタ。マウスをほぼ使わず、キーボードだけでコードを書く・読む。

この設定では、AI エージェントが変えたコードを確かめる用途を重視している。

- Telescope でファイルや文字列をあいまい検索する
- LSP で定義へのジャンプや型の表示をする
- 保存時にコードを自動で整える(format on save)
- gitsigns / diffview / neo-tree で、変更をエディタの中で見る

入力候補は押したときだけ出す。AI のようにコードを自動で書く機能は入れていない。

## 設定のマスター

**編集はこのリポではなく `jyoka/agentic_learning` の `config/nvim/init.lua` で行う。** そちらが正(マスター)で、このリポの [`config/nvim/init.lua`](./config/nvim/init.lua) は新しい Mac に入れるためのコピー。

- 中身はマスターとバイト単位で同じにしておく。このリポ側では編集しない
- マスターを変えたら、このリポのコピーも同期し直す

同期の例(`gh` を使う場合):

```bash
gh api -H "Accept: application/vnd.github.raw" \
  "repos/jyoka/agentic_learning/contents/config/nvim/init.lua?ref=main" > config/nvim/init.lua
```

## インストール

- バージョン: 0.12.4 を記録(2026-09-21 時点。[agent-tools.md](./agent-tools.md))。0.12.6 でも動作を確認済み
- 必要なバージョン: 0.11 以上。設定が `vim.lsp.config` / `vim.lsp.enable` / `vim.lsp.completion` を使うため
- 一緒に入れるもの: ripgrep(`<space>s` の文字列検索が使う)

インストール手順は [setup-new-mac.md](./setup-new-mac.md) を参照。Homebrew を使う場合は `brew install neovim ripgrep`。管理者権限のない Mac では、公式の tar.gz を `~/.local` に展開する。

### Mason が入れる道具に必要なもの

初回起動時に、Mason が言語サーバーとフォーマッタを自動でダウンロードする。そのため次のものが必要になる。

| 必要なもの | 使う道具 |
|:--|:--|
| Node.js / npm | pyright、ts_ls(typescript-language-server)、prettier |
| zig | zls(Zig の言語サーバー)と `zig fmt`。`zig fmt` は zig 本体に入っている |
| git、curl、unzip、tar | lazy.nvim の `git clone` と、Mason のダウンロード・展開 |
| C コンパイラ(`cc`) | Treesitter のパーサーのコンパイル |

- ruff・stylua・lua_ls は GitHub のビルド済みバイナリなので、追加の言語処理系は要らない
- macOS では `/usr/bin/git` が Xcode Command Line Tools の一部なので、git が動けば `cc` も入っている

## 設定ファイル

- 設定ファイル: `~/.config/nvim/init.lua`(1 ファイルだけ)
- プラグイン: `~/.local/share/nvim/lazy/`(lazy.nvim が管理)
- Mason の道具: `~/.local/share/nvim/mason/`
- `lazy-lock.json`(プラグインのバージョン固定ファイル)はこのリポに置いていない

### 入っているプラグイン

| プラグイン | 役割 |
|:--|:--|
| lazy.nvim | プラグイン管理。初回起動時に自分自身を `git clone` する |
| rose-pine(moon) | 色テーマ。WezTerm・tmux と同じ Rose Pine Moon |
| telescope.nvim | ファイル・文字列・バッファのあいまい検索 |
| nvim-treesitter | 構文の色分け |
| mason.nvim + mason-lspconfig + nvim-lspconfig | LSP: pyright、ts_ls、lua_ls、zls |
| mason-tool-installer.nvim | フォーマッタの自動インストール: ruff、prettier、stylua |
| conform.nvim | 保存時の自動整形 |
| gitsigns.nvim | 変更行の印、ハンク単位のステージ |
| diffview.nvim | 変更前と変更後を左右に並べた差分、履歴 |
| neo-tree.nvim | ファイルツリー(ファイルごとの Git の状態つき) |

### 保存時の自動整形

`:w` するたびに、ファイルの種類に合ったフォーマッタが動く。

| 言語 | フォーマッタ |
|:--|:--|
| Python | ruff(import の並び替えも) |
| TypeScript / JavaScript / JSON / Markdown | prettier |
| Lua | stylua(`stylua.toml` がなければ 2 スペース・シングルクォート) |
| Zig | `zig fmt` |

表にない言語は、LSP がつながっていれば LSP で整え、なければ何もしない。

## キーとショートカット

リーダーキーは `<space>`。以下 `Space` と書く。

### 基本

| キー | 動作 |
|:--|:--|
| `jk`(入力モードで素早く) | `Esc` の代わり |
| `Space w` | 保存 |
| `Esc` | 検索のハイライトを消す |

相対行番号を表示しているので、`5j` や `12k` で狙った行へ飛べる。

### Telescope(検索)

| キー | 動作 |
|:--|:--|
| `Space f` | ファイルを名前で探して開く |
| `Space s` | 全ファイルを文字列で検索(ripgrep) |
| `Space b` | 開いているバッファを切り替え |
| `Space h` | ヘルプを検索 |
| `Space d` | エラー・警告(診断)の一覧 |

### LSP

LSP は Python・TypeScript/JavaScript・Lua・Zig のファイルを開くと自動でつながる。`gd` 以外は Neovim 0.11 以降の標準キー。

| キー | 動作 |
|:--|:--|
| `gd` | 定義へジャンプ(`Ctrl+o` で戻る) |
| `K` | 型・ドキュメントを小窓で表示 |
| `grr` | 使われている場所の一覧 |
| `gri` | 実装へジャンプ |
| `grn` | 名前をまとめて変更 |
| `gra` | 修正の候補(コードアクション) |
| `]d` / `[d` | 次 / 前の診断へ |
| `Ctrl+w d` | カーソル行の診断の全文を表示 |
| `Ctrl+x Ctrl+o`(入力モード) | 入力候補を出す。勝手には出ない |
| `Ctrl+Space`(入力モード) | 入力候補を出す(macOS の設定変更が必要。既知の問題を参照) |

### Git(`Space g` から始まる)

| キー | 動作 | 近い Git コマンド |
|:--|:--|:--|
| `]c` / `[c` | 次 / 前のハンクへ | |
| `Space gp` | ハンクを小窓で見る | `git diff`(その部分) |
| `Space gs` | ハンクをステージ。ビジュアルモードでは選んだ行だけ | `git add -p` |
| `Space gu` | 直前のステージを取り消す | `git restore --staged -p` |
| `Space gr` | ハンクを捨てる(`u` で取り消せる) | `git restore -p` |
| `Space gb` | この行を最後に変えたコミット | `git blame` |
| `Space gd` | 変更を一覧で見る(diffview) | `git status` + `git diff` + `git diff --cached` |
| `Space gh` | このファイルの履歴 | `git log -p -- <file>` |
| `Space gH` | リポジトリ全体の履歴 | `git log -p` |
| `Space gq` | diffview を閉じる | |
| `Space gt` | 変更のあるファイルだけのツリー | `git status` |

ブランチが足した変更だけを見るときは `:DiffviewOpen main...HEAD`。

### ファイルツリー

| キー | 動作 |
|:--|:--|
| `Space e` | ファイルツリーを開く / 閉じる。開いているファイルの位置を表示する |

ツリーの Git の印は `git status --short` と同じ文字(`A` `M` `D` `R` `?` `!` `U`)。`●` はステージ済み、`○` は作業ツリーだけの変更。

### 管理用コマンド

| コマンド | 動作 |
|:--|:--|
| `:Lazy` | プラグインの状態・更新 |
| `:Mason` | 言語サーバー・フォーマッタの状態・再インストール |
| `:checkhealth` | 全体の診断 |
| `:checkhealth vim.lsp` | 開いているファイルに LSP がつながっているか |
| `:checkhealth conform` | フォーマッタが入っているか |

## 他のツールとの連携

### tmux / herdr

- tmux の crew レイアウト(プレフィックス + `A`)は `agent | editor | manual` の 3 ペイン。editor ペインで Neovim を開く([shell-terminal.md](./shell-terminal.md))
- 色は WezTerm・tmux と同じ Rose Pine Moon でそろえている
- tmux はプレフィックスに `Ctrl+a` を使う。tmux の中では `Ctrl+a` が tmux に取られるため、Neovim の「数字を 1 増やす」(`Ctrl+a`)は届かない
- herdr のショートカットは Option キー、AeroSpace は Ctrl+Option([herdr.md](./herdr.md))。この設定は Option(Alt)キーを使わないので、どちらともぶつからない

### エージェントが使う git worktree

エージェントは、タスクごとに git worktree(同じリポの別の作業フォルダ)で作業することが多い。エージェントの変更を確かめるときは、その worktree のフォルダで `nvim` を開く。

- `Space f` / `Space s` は Neovim を開いたフォルダの中を探す。worktree のフォルダで開けば、その worktree だけが対象になる
- gitsigns・diffview・neo-tree は、開いたファイルが属する worktree の Git の状態を表示する
- `Space gd` で未コミットの変更、`:DiffviewOpen main...HEAD` でブランチ全体の変更を見られる
- プラグインと Mason の道具は `~/.local/share/nvim/` に 1 組だけ入る。worktree ごとに入れ直す必要はない

### VS Code

ファイルや差分を大きな画面で見たいときは VS Code を横に開く。Neovim と役割を分けている([aerospace.md](./aerospace.md))。

## 既知の問題と対処法

### 初回起動で「Press ENTER」が何度も出て、インストールが止まる

初回起動では、Treesitter がパーサーを入れる途中経過を表示するたびに、画面下に `Press ENTER or type command to continue` が出る。この表示が出ている間は、Mason のインストールも止まる。放置すると、10 分たっても言語サーバーが 1 つも入らなかった。

対処は、表示が出なくなるまで Enter を押し続けること。この Mac では約 80 秒で全部入った。終わったら `:qa` で閉じて開き直す。2 回目からはこの表示は出ない。

途中で `tar: tree-sitter-python.tar.gz ... No such file or directory` というエラーが 1 回出ることがある。それでも最終的には python のパーサーも入り、動作に問題はなかった。`.py` を開いたまま初回起動すると、同じパーサーを 2 か所から同時に入れようとして衝突するためと思われる(推測)。気になるときは `:TSInstall python` で入れ直す。

### 初回起動で、プラグインや言語サーバーが入らない

初回起動時に、lazy.nvim が `git clone` でプラグインを取得し、Mason が言語サーバーとフォーマッタをダウンロードする。通信を検査するセキュリティソフトがある環境では、SSL エラーでこれが失敗する。

対処は [setup-new-mac.md の SSL エラー対策](./setup-new-mac.md#通信を検査するセキュリティソフトがある環境での-ssl-エラー対策) を参照。証明書を設定したら、Neovim を開き直して `:Lazy sync` と `:Mason` で入り直す。

### `Ctrl+Space` で入力候補が出ない

macOS では `Ctrl+Space` が入力ソースの切り替えに使われていて、Neovim に届かない。使いたいときは、システム設定 > キーボード > キーボードショートカット > 入力ソース で、このショートカットをオフにする。`Ctrl+x Ctrl+o` ならそのままで動く。

### Zig のファイルを開くと警告が出る

zig 本体と Mason の zls のバージョンがずれると、警告が出ることがある。zig 本体と zls のバージョンをそろえる。zls は `:MasonInstall zls@<バージョン>` で版を指定して入れられる。

### アイコンが豆腐(□)や変な文字になる

ファイルツリーと diffview のアイコンは Nerd Font の文字を使う。ターミナルのフォントを Nerd Font にすると直る。アイコンが出なくても他の機能は動く。

### `:checkhealth` の lazy に luarocks の ERROR が出る

`{.../lazy-rocks/hererocks/bin/luarocks} not installed` という ERROR が出る。この設定には luarocks を使うプラグインがないので、無視してよい。同じ欄に「no plugins require `luarocks`, so you can ignore any warnings below」と出ている。

### Markdown を開くとエラーが出る(Neovim 0.12)

nvim-treesitter の master ブランチは Neovim 0.12 より古く、そのままだと Markdown のコードブロックや LSP の小窓でエラーになる。設定の `init` に回避策を入れてあるので、通常は起きない。設定を書き換えるときは、この回避策を消さないこと。

## 公式ドキュメント

- Neovim: <https://neovim.io/doc/>
- Neovim のインストール: <https://github.com/neovim/neovim/blob/master/INSTALL.md>
- Neovim のリリース: <https://github.com/neovim/neovim/releases>
- lazy.nvim: <https://lazy.folke.io/>
- mason.nvim: <https://github.com/mason-org/mason.nvim>
- mason-lspconfig.nvim: <https://github.com/mason-org/mason-lspconfig.nvim>
- conform.nvim: <https://github.com/stevearc/conform.nvim>
- telescope.nvim: <https://github.com/nvim-telescope/telescope.nvim>
- gitsigns.nvim: <https://github.com/lewis6991/gitsigns.nvim>
- diffview.nvim: <https://github.com/sindrets/diffview.nvim>
- neo-tree.nvim: <https://github.com/nvim-neo-tree/neo-tree.nvim>
- ripgrep: <https://github.com/BurntSushi/ripgrep>
