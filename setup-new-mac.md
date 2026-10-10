# 新しい Mac でのセットアップ手順

このリポの `config/` フォルダに設定ファイルの実物(マスター)が入っている。新しい Mac では「必要なツールを入れる → `config/` を所定の場所にコピーする」の 2 段階で環境を再現できる。設定は 2026-09-26 にユーザー名・Homebrew の場所に依存しない形へ修正済みなので、書き換えなしでそのまま使える。

エージェント(Claude / Kiro など)に任せる場合は、このファイルを読ませて「この手順でセットアップして」と頼めばよい。

## 前提となるツール一覧

| ツール | 用途 | 必須度 |
|:--|:--|:--|
| yazi 26.x 以上 | ファイルマネージャー本体 | 必須 |
| glow | md の閲覧・プレビュー | 必須 |
| micro | エディタ(Ctrl+S 保存 / Ctrl+Q 終了) | 必須 |
| Neovim 0.11 以上 + ripgrep | メインのエディタ(LSP・自動整形・Git 表示つき)。ripgrep は文字列検索に使う | 推奨 |
| fzf | Ctrl+R 履歴検索など | 推奨 |
| zsh-autosuggestions | コマンド自動補完 | 推奨 |
| LibreOffice | pptx / xlsx / docx のプレビューと閲覧 | office 機能を使うなら必須 |
| poppler (pdftoppm) | PDF・スライドの画像化 | office 機能を使うなら必須 |
| Node.js + live-server | HTML のライブリロード | HTML 機能を使うなら必須 |
| Google Chrome または Edge | HTML プレビューのレンダリング | HTML 機能を使うなら必須 |

注意: yazi が 25.x 以前だと設定の書式が違い、**設定ファイル全体が無視される**(詳細は [yazi.md](./yazi.md) のトラブルシューティング)。必ず 26.x 以上にすること。

## 手順 1: ツールを入れる

### トラック A: 個人 Mac(Homebrew が使える場合)

```bash
brew install yazi glow micro fzf poppler zsh-autosuggestions node
brew install --cask libreoffice
npm install -g live-server
```

Neovim を使う場合:

```bash
brew install neovim ripgrep
brew install zig   # Zig を書く場合。node は上で入れている
```

Neovim は初回起動時に、Mason が言語サーバーとフォーマッタを自動で入れる。そのために次のものが必要:

| 必要なもの | 使う道具 |
|:--|:--|
| Node.js / npm | pyright、ts_ls、prettier |
| zig | zls と `zig fmt` |
| git、curl、unzip | lazy.nvim の `git clone` と、Mason のダウンロード・展開。curl と unzip は macOS に最初から入っている。git は Xcode Command Line Tools に含まれる |

Python・TypeScript・Zig を書かないなら、その言語の道具は入らなくても Neovim 自体は動く。詳細は [nvim.md](./nvim.md)。

### トラック B: 管理者権限のない Mac(会社支給など、Homebrew が使えない場合)

方針: 管理者権限を使わず、ユーザー領域(`~/.local/bin` と `~/Applications`)だけで完結させる。

```bash
mkdir -p ~/.local/bin ~/Applications
```

1. **バイナリを GitHub Releases からダウンロード**する。それぞれ macOS 用(Apple Silicon なら `aarch64` / `arm64` 表記)の zip / tar.gz を取り、解凍して実行ファイルを `~/.local/bin/` に置く
   - yazi: <https://github.com/sxyazi/yazi/releases>(`yazi` と `ya` の 2 つを置く)
   - glow: <https://github.com/charmbracelet/glow/releases>
   - micro: <https://github.com/zyedidia/micro/releases>
   - fzf: <https://github.com/junegunn/fzf/releases>
2. **隔離属性(quarantine)を外す**。ブラウザでダウンロードしたバイナリは Gatekeeper に「開発元を検証できません」とブロックされるため、「このバイナリを信用する」操作が必要:

   ```bash
   xattr -d com.apple.quarantine ~/.local/bin/yazi ~/.local/bin/ya ~/.local/bin/glow ~/.local/bin/micro ~/.local/bin/fzf
   ```

   コマンドを使いたくない場合は、一度実行してブロックのダイアログを出したあと、システム設定 → プライバシーとセキュリティ → 「このまま開く」でも同じ
3. **zsh-autosuggestions** はバイナリではなく zsh スクリプトなので git clone だけでよい:

   ```bash
   git clone https://github.com/zsh-users/zsh-autosuggestions ~/.zsh/zsh-autosuggestions
   ```

4. **Node.js + live-server**(HTML 機能を使う場合)。公式サイトの「Standalone Binary (tar.gz)」を使えば管理者権限不要:

   ```bash
   # https://nodejs.org/en/download から macOS arm64 の tar.gz を取得して展開し、
   # 例として ~/.local/node に置いた場合:
   export PATH="$HOME/.local/node/bin:$PATH"   # ~/.zshrc にも追記する
   npm install -g live-server
   ```

5. **LibreOffice**(office 機能を使う場合)。<https://www.libreoffice.org/download/> から dmg を取得し、**`~/Applications` にドラッグ**する(/Applications と違い管理者権限不要)。初回起動時に Gatekeeper の確認が出たら許可する。yazi のプラグインは `~/Applications/LibreOffice.app` を自動で見つける
6. **pdftoppm**(PDF・スライドのプレビュー用)。poppler は Homebrew なしでの入手が難しいため、代わりに Xpdf command line tools(<https://www.xpdfreader.com/download.html>)の `pdftoppm` を `~/.local/bin/` に置き、隔離属性を外す。入手できなければ、スライドプレビューだけ諦めれば他の機能はすべて動く
7. **Neovim + ripgrep**(Neovim を使う場合)。公式の GitHub Releases の tar.gz を `~/.local` に展開し、`~/.local/bin` からリンクを張る。Neovim は `bin/` と `share/` がそろって動くので、フォルダごと置く:

   ```bash
   cd "$(mktemp -d)"
   # Neovim: https://github.com/neovim/neovim/releases (Intel Mac は nvim-macos-x86_64)
   curl -fLO https://github.com/neovim/neovim/releases/latest/download/nvim-macos-arm64.tar.gz
   tar xzf nvim-macos-arm64.tar.gz
   rm -rf ~/.local/nvim-macos-arm64
   mv nvim-macos-arm64 ~/.local/
   ln -sf ~/.local/nvim-macos-arm64/bin/nvim ~/.local/bin/nvim

   # ripgrep: 最新のバージョンは https://github.com/BurntSushi/ripgrep/releases で確認する
   RG=15.2.0
   curl -fLO https://github.com/BurntSushi/ripgrep/releases/download/$RG/ripgrep-$RG-aarch64-apple-darwin.tar.gz
   tar xzf ripgrep-$RG-aarch64-apple-darwin.tar.gz
   cp ripgrep-$RG-aarch64-apple-darwin/rg ~/.local/bin/
   ```

   ブラウザでダウンロードした場合は、2. と同じく隔離属性を外す。Neovim はフォルダごと外す:

   ```bash
   xattr -dr com.apple.quarantine ~/.local/nvim-macos-arm64
   xattr -d com.apple.quarantine ~/.local/bin/rg
   ```

   Mason が入れる道具には Node.js / npm(4. の手順)と zig も要る。zig は <https://ziglang.org/download/> の macOS 用 tar.xz を `~/.local` に展開し、`zig` を PATH に通す。Zig を書かないなら不要。詳細は [nvim.md](./nvim.md)

トラック B の注意: 端末管理(MDM)の設定によっては、隔離解除やダウンロードしたバイナリの実行自体をポリシーでブロックしている場合がある。その場合は端末の管理者に「開発ツールとして許可してほしい」と相談するしかない。また、会社支給の Microsoft Office ライセンスがあるなら、デフォルトアプリの変更(後述)は不要。

### 通信を検査するセキュリティソフトがある環境での SSL エラー対策

通信の中身を検査するセキュリティソフト(VPN と組み合わせて使われることが多い)は、HTTPS をいったん復号して独自の証明書に差し替える。CLI ツールはその証明書を知らないため、`git clone` / `npm install` / `curl` などが次のようなエラーで失敗することがある:

- `self-signed certificate in certificate chain`
- `unable to get local issuer certificate`
- `SSL certificate problem`

#### 正攻法(推奨): セキュリティソフトの証明書をツールに教える

SSL 検証を切るのではなく、「セキュリティソフトの証明書も信用してよい」と各ツールに教えるのが安全な解決策。この種のソフトは証明書バンドル(`.pem` ファイル)を端末内に置いていることが多いので、それを指すだけでよい:

```bash
# セキュリティソフトが配る証明書バンドルのパス(置き場所は製品ごとに違う。製品のドキュメントか管理者に確認)
NSCERT="/path/to/ca-bundle.pem"

# ~/.zshrc に追記しておくと全ツール共通で効く
export SSL_CERT_FILE="$NSCERT"          # curl など
export NODE_EXTRA_CA_CERTS="$NSCERT"    # Node.js / npm / live-server
export REQUESTS_CA_BUNDLE="$NSCERT"     # Python 系

# git だけは個別設定
git config --global http.sslCAInfo "$NSCERT"
```

注意: VPN を切って社外ネットワークから使うときはセキュリティソフトの検査を経由しないため、この設定が逆に邪魔になるケースがある。その場合は該当行をコメントアウトして新しいターミナルを開く。

#### 最後の手段: SSL 検証を一時的にオフ

証明書ファイルが見つからない・急いでいる場合の一時しのぎ。**通信相手が本物か確認しない状態になるので、社内ネットワークにいる間だけ・必要なコマンドだけに限定し、終わったら必ず戻すこと。**

```bash
# git: そのコマンド 1 回だけ検証オフ(グローバル設定を汚さないのでこちらを推奨)
git -c http.sslVerify=false clone https://github.com/jyoka/workenv_setting.git

# npm: オフにしたら作業後に必ず戻す
npm config set strict-ssl false
# ...(インストール作業)...
npm config set strict-ssl true

# curl: -k を付けたコマンドだけ検証オフ
curl -k -LO <URL>
```

`git config --global http.sslVerify false` のような**恒久的なオフ設定は残さない**こと。戻し忘れの確認は `git config --global --get http.sslVerify` と `npm config get strict-ssl`。

#### Neovim の初回起動も通信する

Neovim は初回起動時に、lazy.nvim がプラグインを `git clone` し、Mason が言語サーバーとフォーマッタを(curl と npm で)ダウンロードする。このためセキュリティソフトがある環境では、上と同じ SSL エラーで失敗する。先に上の「正攻法」の設定をしてから Neovim を起動する。失敗した後に設定した場合は、Neovim を開き直して `:Lazy sync` と `:Mason` で入り直す。

## 手順 2: 設定ファイルをコピーする

このリポを取得して、`config/` の中身を所定の場所へコピーする:

```bash
git clone https://github.com/jyoka/workenv_setting.git
cd workenv_setting

# yazi 設定一式(設定 + プラグイン + 起動スクリプト)
mkdir -p ~/.config/yazi
cp -R config/yazi/ ~/.config/yazi/
chmod +x ~/.config/yazi/open-live-server.sh

# zsh 設定(中身を確認してから追記)
cat config/zsh/zshrc-additions.zsh >> ~/.zshrc

# herdr ステータススクリプト(herdr を使う場合)
mkdir -p ~/.config/herdr/scripts
cp scripts/herdr_status.py ~/.config/herdr/scripts/
```

herdr の `config.toml`(タブバー・サイドバー設定)は [herdr.md](./herdr.md) を参照して反映する。

Neovim を使う場合:

**既存の `~/.config/nvim` がある場合は、先にバックアップする。** `cp` で `init.lua` が上書きされ、元の設定が消えるため:

```bash
[ -e ~/.config/nvim ] && mv ~/.config/nvim ~/.config/nvim.bak
```

```bash
mkdir -p ~/.config/nvim && cp config/nvim/init.lua ~/.config/nvim/
```

この `init.lua` はコピー。編集するときは `jyoka/agentic_learning` の `config/nvim/init.lua`(マスター)を変える([nvim.md](./nvim.md))。

初回の `nvim` 起動時に、lazy.nvim がプラグインを `git clone` し、Mason が言語サーバーとフォーマッタをダウンロードする。数分かかることがあり、進み具合は `:Lazy` と `:Mason` で見られる。通信を検査するセキュリティソフトがある環境では失敗するので、先に [SSL エラー対策](#通信を検査するセキュリティソフトがある環境での-ssl-エラー対策) をしておく。途中で `Press ENTER` が何度も出たら、Enter を押し続ける(押さないとインストールが止まる。[nvim.md](./nvim.md#初回起動でpress-enterが何度も出てインストールが止まる) 参照)。

AeroSpace(タイル型ウィンドウマネージャー)と、`@` だけで VS Code を開く Claude Code フックを使う場合(Homebrew がある場合):

```bash
brew install --cask nikitabobko/tap/aerospace visual-studio-code
cp config/aerospace/aerospace.toml ~/.aerospace.toml
mkdir -p ~/.config/agent-hooks ~/.pi/agent/extensions
cp scripts/open_mention.py ~/.config/agent-hooks/
cp config/pi/extensions/open-mention.ts ~/.pi/agent/extensions/   # Pi を使う場合
```

フックの登録(Claude Code / Codex)、各エージェントへの指示、アクセシビリティ権限は [aerospace.md](./aerospace.md) を参照する。VS Code はブラウザからではなく Homebrew で入れる(理由は同じく aerospace.md の「既知の注意点」)。

管理者権限のない Mac(トラック B)では、Homebrew の代わりに `curl` で落として `~/Applications` に置く。

```bash
cd "$(mktemp -d)"
curl -fsSL -o a.zip https://github.com/nikitabobko/AeroSpace/releases/download/v0.21.3-Beta/AeroSpace-v0.21.3-Beta.zip
shasum -a 256 a.zip   # bdbd3fedb3a41bdd3987d241dd5cc1d8b74a56fdbc0d76a98e6925c5cfef4ce4 と一致すること
ditto -x -k a.zip .
mkdir -p ~/Applications ~/.local/bin
ditto AeroSpace-*/AeroSpace.app ~/Applications/AeroSpace.app
cp AeroSpace-*/bin/aerospace ~/.local/bin/
cp ~/path/to/workenv_setting/config/aerospace/aerospace.toml ~/.aerospace.toml   # このリポの場所に合わせる
open ~/Applications/AeroSpace.app
```

- 会社支給の Mac では、入れる前に情シスに確認する。判断材料は [aerospace.md](./aerospace.md) の「安全性」にまとめてある
- 何に管理者権限が要るか、SSL エラーやブロックが出たときの対処も aerospace.md の「管理者権限のない Mac」を参照する

## 手順 3: デフォルトアプリの変更(任意)

Office ライセンスがない Mac では、pptx / xlsx / docx をダブルクリックしたとき LibreOffice が開くようにする。

- コマンドでやる場合(duti が必要。Homebrew: `brew install duti`): [yazi.md](./yazi.md) 参照
- **ツールなしでやる場合(管理者権限のない Mac 向け)**: Finder で対象ファイルを右クリック → 「情報を見る」 → 「このアプリケーションで開く」で LibreOffice を選び、**「すべてを変更…」** を押す。pptx / xlsx / docx それぞれ 1 ファイルずつやれば全ファイルに適用される

## 手順 4: 動作確認チェックリスト

新しいターミナルを開いてから:

- [ ] コマンドを打ち始めると灰色の補完候補が出る(zsh-autosuggestions)
- [ ] `Ctrl+R` で履歴のあいまい検索が開く(fzf)
- [ ] `yazi` を起動してエラー画面(Press any key to continue...)が**出ない**
- [ ] md ファイル: カーソルで整形プレビュー、Enter で glow 閲覧(q で戻る)
- [ ] xlsx: カーソルで表プレビュー(初回は 2〜5 秒待つ)
- [ ] pptx: カーソルでスライド画像プレビュー
- [ ] html: カーソルでレンダリング画像、Enter で live-server 起動(Ctrl+C で終了)
- [ ] `Ctrl+P` で Quick Look が開く
- [ ] `nvim` がエラーなしで起動し、`:checkhealth` に ERROR がない(lazy の luarocks の ERROR は無視してよい。[nvim.md](./nvim.md) の既知の問題)。`:Mason` で pyright・ts_ls(typescript-language-server)・lua_ls(lua-language-server)・zls が入っている

うまくいかないときは [yazi.md](./yazi.md)、[nvim.md](./nvim.md)、[troubleshooting.md](./troubleshooting.md) を参照。
