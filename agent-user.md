# task-hub エージェント専用ユーザー(Linux / Omarchy)

task-hub のコーディングエージェント(Claude Code など)を、自分(`joka`)ではなく **専用の権限のないユーザー `task-agent`** で動かすための設定(2026-10-17)。エージェントが `joka` の全権限(SSH 鍵、gh・Claude の認証情報、他のリポ)で動かないようにするのが目的。

task-hub のサンドボックスのタスク(「Self-hosted dev assistant (3/6): sandbox runs」、[jyoka/task-hub#80](https://github.com/jyoka/task-hub/pull/80))は bwrap をやめて、エージェントを別の Linux ユーザーで動かす方式にした(bwrap は、サンドボックスの外で動く task-hub 自身の git の処理から抜けられてしまったため)。ユーザーを作るには root が要り、無人のエージェントにはできないので、このスクリプトを自分で `sudo` で実行する。

## 目的とよくある使い方

- task-hub は `sudo -n -u task-agent -H -D <worktree> -- <エージェントのコマンド>` でエージェントを起動する(パスワードなし)
- エージェントが読み書きできるのは task-hub の worktree(`~/.local/share/task-hub/worktrees/`)と、その元のリポ(`~/.local/share/task-hub/repos/`)だけ
- **エージェントが自分で commit・push する。** git は `task-agent` の名前と、`task-agent` 専用の fine-grained GitHub トークン(task のリポだけ、Contents と Pull requests)で動く。task-hub(`joka`)は worktree でも repos でも git を動かさず、結果は GitHub の API で読むだけ(2026-10-17 に決めた「案 A」)
- `/home/joka` の中身は一覧できず、読めない(`~/.ssh`、`~/.config/gh`、`~/.claude`、`~/.claude.json` など)。エージェントは自分の HOME(`/var/lib/task-agent`)に自分の認証情報を持つ
- `joka` が `sudo` で `task-agent` になれるだけで、`task-agent` からは root にも `joka` にもなれない

GitHub Actions のランナー用の `github-runner`([GitHub Actions のセルフホストランナー](./actions-runner.md))とは別のユーザー。同じやり方(システムユーザー、追加グループなし、sudo なし)で作るが、使い回さない。

## セキュリティ(必読)

- **これは事故を小さくするためのもので、悪意のあるコードを安全に動かす保証ではない。** エージェントはネットワーク(LAN・tailnet)に出られ、`/tmp` や誰でも読めるシステムのファイルは見える
- **`task-agent` を `wheel`・`docker` グループに入れない**(root になれてしまう。スクリプトは警告を出す)
- **worktree のコードを `joka` で実行しない。** エージェントは worktree のファイルを自由に書き換えられるので、task-hub が `joka` のまま worktree のテスト・`Makefile`・`npm` スクリプトなどを動かすと、それがエージェントの抜け道になる。worktree のコードは `task-agent` で動かす
- **`joka` は worktree(`worktrees/`)と元のリポ(`repos/`)で git を動かさない。** どちらもエージェントが書ける。`.git/config`(`core.fsmonitor`、`core.hooksPath`、`core.sshCommand`、フィルターなど)や hooks を書き換えられると、`joka` が動かした `git status`・`add`・`commit`・`fetch`・`worktree add` の中でエージェントのコードが `joka` として動く。bwrap が破られたのと同じ道。task-hub がこれらの場所でやる git(clone・fetch・`worktree add`・commit・push)は全部 `sudo -n -u task-agent -H git ...` で動かし、結果(push されたブランチ、PR)は `joka` の gh で GitHub の API から読む
- **git の所有者チェック(`safe.directory`、「dubious ownership」)はこの守りにならない。** git が見るのは worktree・`.git` ファイル・gitdir の持ち主だけで、スクリプトの ACL ではエージェントが `joka` 持ちのファイルやディレクトリも書き換えられる。たとえば `joka` 持ちの `.git` ファイルの中身を書き換えて `joka` 持ちの別のディレクトリ(中身はエージェントが作った `HEAD`・`objects/`・`config`)を指させたり、`joka` 持ちのディレクトリの名前を `.git` に変えたりできる。どれも持ち主は `joka` のままなので、`joka` の git はそのまま受け入れ、そこの `config` の `core.fsmonitor` を実行する。`-c core.fsmonitor=false -c core.hooksPath=/dev/null` を付けても、`config` で効く設定はほかにもある(`core.sshCommand`、`diff.external`、filter など)ので完全には防げない。だから「`joka` は git を動かさない」を守る
- エージェントの GitHub トークンはエージェント自身が読める(`/var/lib/task-agent/.config/gh/hosts.yml`)。漏れても困らないよう、task のリポだけ・Contents と Pull requests だけ・期限付きにする(下の「GitHub のトークン」)
- **スクリプトは、エージェントが書ける共有ディレクトリ(`worktrees/`・`repos/`)の中で、エージェントが動ける間は root でパスをたどるコマンドを動かさない。** `chgrp`・`chmod`・`setfacl` はシンボリックリンクをたどるので、`find` がパスを集めてからコマンドが動くまでの間にエージェントがディレクトリを `/etc` へのシンボリックリンクに差し替えると、root が `/etc/shadow` などに `task-agent` の rw を付けてしまう(root になれる)。そこで `install`・`uninstall` は、まず `~/.local/share/task-hub` に `task-agent` の `---` の ACL を付けて共有ディレクトリへの入口を閉じ(エージェントは `~/.local/share/task-hub` を書けないので、そこは差し替えられない)、`task-agent` のプロセスが残っていないことを確かめてから中をたどり、最後に入口を `--x` に戻す。`install` は `task-agent` のプロセスが動いていると共有ディレクトリの ACL を変える前に止まり、`uninstall` は止める。途中で失敗したときは入口が閉じたままになる(安全側。もう一度実行すれば戻る)。`chgrp` には `-h`、`uninstall` の `chown -R -h` はシンボリックリンクをたどらない
- `/home/joka` の中は、スクリプトを実行した時点にあったものに「`task-agent` は読めない」ACL を付けている。あとから `~` に増えたディレクトリ・ファイルは、名前を知っていれば読める可能性がある。`status` が警告を出すので、そのときは `install` をもう一度実行する(下の「仕組み」)

## インストール方法とバージョン

足すパッケージは `github-cli`(`/usr/bin/gh`。`task-agent` の push と PR 用)だけ。`acl`・`sudo`・`shadow` は Omarchy に最初から入っている(`setfacl` がないときだけ `acl` を pacman で入れる)。どちらも `pacman -S --needed` なので、入っていれば何もしない。

### セットアップ

Linux 機でリポのルートから、**自分(`joka`)のアカウントで `sudo` を付けて** 実行する(`joka` が task-hub のユーザーになる。`SUDO_USER` から決まる):

```bash
sudo scripts/setup_agent_user.sh            # ユーザー・グループ・sudoers・ACL を作る(直す)
sudo scripts/setup_agent_user.sh status     # 何が入っているか(変更しない)
sudo scripts/setup_agent_user.sh check      # 受け入れチェック(下の「確認」)
```

何度実行してもよい。ユーザー・グループはないときだけ作り、sudoers は中身が違うときだけ書き換える。ACL は毎回付け直すので、ずれた権限の修復にもなる。ただし `task-agent` のプロセス(実行中のタスク)があると `install` は止まるので、タスクが動いていないときに実行する(下の「セキュリティ」)。最後に task-hub に設定する値を表示する:

```text
task-hub settings:
  agent user   task-agent
  agent group  task-agents
  agent home   /var/lib/task-agent
  shared dirs  /home/joka/.local/share/task-hub/worktrees /home/joka/.local/share/task-hub/repos (read/write)
  git identity jyoka <56349011+jyoka@users.noreply.github.com>
  run a command as the agent:  sudo -n -u task-agent -H -D <worktree> -- <command>
```

**実行したあと、一度ログアウトしてログインし直す(または再起動する)。** `joka` を `task-agents` グループに足したのが、今のセッションと `task-hub-watch.service` などのユーザーサービスに反映されるのはその後になる(ACL には `joka` の名前も入れてあるので、ログインし直す前でも読み書きはできる)。

名前・場所は環境変数で変えられる:

```bash
sudo AGENT_USER=task-agent AGENT_GROUP=task-agents AGENT_HOME=/var/lib/task-agent \
  TASKHUB_USER=joka TASKHUB_DATA=/home/joka/.local/share/task-hub scripts/setup_agent_user.sh
```

### やること

| やること | 中身 |
|:--|:--|
| ユーザー | システムユーザー `task-agent`(ホーム `/var/lib/task-agent`、モード 700、シェル `/bin/bash`、パスワードはロック、追加グループなし) |
| グループ | `task-agents`(システムグループ)。`joka` と `task-agent` の 2 人が入る |
| sudoers | `/etc/sudoers.d/task-agent`(モード 440)。`visudo -cf` で確かめてから置き、置いたあと `visudo -c` で全体を確かめる |
| worktree | `~/.local/share/task-hub/worktrees` 以下を全部グループ `task-agents` にし、ディレクトリに setgid、`joka`・`task-agent`・`task-agents` に rw のアクセス ACL とデフォルト ACL(`setfacl`) |
| 元のリポ | `~/.local/share/task-hub/repos` 以下も worktree と同じ(エージェントが commit で `objects/`・`refs/`・worktree の gitdir に書くため) |
| `/home/joka` | `~`・`~/.local`・`~/.local/share`・`~/.local/share/task-hub` に `task-agent` の通過だけ(`--x`)の ACL。その途中の他のもの全部(`~/.claude`、`~/.config`、`~/.zshrc`、`~/.local/share/mise`、`~/.local/lib`(task-hub の実行用クローン)、`task-hub/prompts`・`task-hub/run` など)に `task-agent` の「アクセスなし」(`---`)の ACL |
| git | `task-agent` の `~/.gitconfig` に `safe.directory` として `worktrees/*` と `repos/*` を足す(`joka` 持ちのリポを `task-agent` の git が拒否しないように)。`user.name`・`user.email` を入れる(既定は `joka` の git の値) |
| gh | `/usr/bin/gh` がなければ `github-cli` を pacman で入れる(`joka` の gh は mise の中にあり、`task-agent` からは読めない) |

シェルを `nologin` にしないのは、`sudo` が `SHELL` を相手のユーザーのシェルにし、Claude Code の Bash ツールがそのシェルでコマンドを動かすため。パスワードがロックされていて、`authorized_keys` もないので、ログインはできない。

### sudoers の選び方

```sudoers
joka ALL=(task-agent) CWD=* NOPASSWD: ALL
```

- 実行できる相手は `task-agent` だけ(`root` も他のユーザーも、`-g` でのグループ指定もない)。`sudo -u root` はこの行からは許されない
- コマンドは `ALL` にした。エージェントの起動コマンド(`claude` の場所、引数、`env`、`git`)は task-hub の作りしだいで変わり、`task-agent` で何を動かしても `task-agent` の権限しかないので、コマンドを絞っても守れるものが増えない。task-hub の起動方法が決まったら、`/var/lib/task-agent/.local/bin/claude` などに絞ってもよい(そのときはこのスクリプトのテンプレートを直す)
- `CWD=*` は `sudo -D <worktree>`(作業ディレクトリの指定)を許すため。どのディレクトリでも、入れるかどうかは `task-agent` の権限で決まる
- `NOPASSWD` なので、無人の task-hub から `sudo -n` で使える

`joka` は `wheel` に入っているので、パスワードを入れれば今まで通り root になれる。それはこのファイルとは関係ない(`check` はパスワードなしで root になれないことを確かめる)。

## 認証情報(エージェント用ユーザーに持たせるもの)

エージェントは `joka` の認証情報を使えないので、要るものは `task-agent` 自身に持たせる。どれも `/var/lib/task-agent`(モード 700)に入り、`joka` は `sudo -u task-agent` で見られるが、他のユーザーからは見えない。**このリポにはコミットしない。**

`task-agent` のシェルに入るには:

```bash
sudo -u task-agent -H -i          # cd /var/lib/task-agent してから bash -l
```

### Claude Code(必要)

`joka` の Claude Code(`~/.local/share/mise/installs/claude/...`)は `task-agent` からは使えない(`~/.local/share/mise` を読めない)。`task-agent` 用に別に入れてログインする:

```bash
sudo -u task-agent -H -i
curl -fsSL https://claude.ai/install.sh | bash   # ~/.local/bin/claude に入る(自動更新される)
~/.local/bin/claude                             # 起動して /login(表示される URL をブラウザで開いてコードを貼る)
exit
```

- ログイン情報は `/var/lib/task-agent/.claude/.credentials.json` に入る
- `sudo` は `PATH` を決まった値に戻すので、task-hub からはフルパス(`/var/lib/task-agent/.local/bin/claude`)で呼ぶ
- ブラウザでのログインができないときは、`claude setup-token` で長期のトークンを作り、task-hub から環境変数 `CLAUDE_CODE_OAUTH_TOKEN` で渡す方法もある(`sudo` は環境変数を消すので `sudo -u task-agent -H env CLAUDE_CODE_OAUTH_TOKEN=... claude ...` の形になる。トークンが `ps` に見えるので、使うなら task-hub 側で標準入力から渡す工夫がいる)

### git の名前とメール(必要、スクリプトが入れる)

commit はエージェントが `task-agent` で行うので、`task-agent` の git に名前とメールが要る。`install` が `task-agent` の `~/.gitconfig` に入れる。既定は `joka` の git の `user.name`・`user.email`(今までと同じ作者で commit される)。別の名前にしたいときは指定して `install` をもう一度実行する:

```bash
sudo AGENT_GIT_NAME='task-agent (jyoka)' AGENT_GIT_EMAIL='56349011+jyoka@users.noreply.github.com' \
  scripts/setup_agent_user.sh
```

`safe.directory` もスクリプトが入れる(`task-agent` の git だけに効く。`joka` の git には入れない)。

### GitHub のトークン(必要)

push と PR はエージェントが `task-agent` の gh で行う。`joka` の gh のトークンも SSH 鍵も渡さず、`task-agent` 専用の **fine-grained personal access token** を作る:

1. <https://github.com/settings/personal-access-tokens/new> を開く(`jyoka` でログインした自分のブラウザで)
2. Token name: `task-agent`、Expiration: 90 日など期限を付ける
3. Repository access: **Only select repositories** で task-hub が扱うリポだけ(今は `jyoka/workenv_setting`・`jyoka/task-hub`・`jyoka/task-sandbox` など、`~/.local/share/task-hub/repos/` にあるもの)
4. Repository permissions: **Contents: Read and write**、**Pull requests: Read and write**(Metadata: Read-only は自動で付く)。ほかは付けない(Workflows・Administration・Secrets は付けない)
5. 作ったトークンをファイルに保存し、スクリプトに標準入力で渡す。終わったらファイルを消す:

```bash
sudo scripts/setup_agent_user.sh token < token.txt && rm token.txt
# または、何もリダイレクトせずに実行すると入力を求められる(画面には出ない)
sudo scripts/setup_agent_user.sh token
```

`token` は `task-agent` で `gh auth login --with-token`(トークンは `/var/lib/task-agent/.config/gh/hosts.yml`、HOME はモード 700)と `gh auth setup-git`(`task-agent` の git が https の push で gh のトークンを使う)を実行し、`gh auth status` を表示する。トークンはコマンドの引数にしないので `ps` やシェルの履歴に出ない。**トークンはこのリポにもどこにもコミットしない。** リポを足したとき・期限が切れたときは GitHub でトークンを直す(作り直したら `token` をもう一度実行する)。

task-hub のリポの remote は https(`https://github.com/jyoka/...`)にする。SSH の remote だと `task-agent` には鍵がないので push できない。

### ツールチェーン

`joka` の mise(`~/.local/share/mise`)も読めない。エージェントが言語のランタイムを使うなら、`task-agent` に mise を入れて(`/usr/bin/mise` があればそれを使い)、`task-agent` の HOME にインストールする。

## 仕組み・設定ファイルの場所

| 場所 | 中身 |
|:--|:--|
| [`scripts/setup_agent_user.sh`](./scripts/setup_agent_user.sh) | セットアップ・状態表示・チェック・アンインストール |
| `/etc/sudoers.d/task-agent` | `joka` → `task-agent` の sudo のルール |
| `/var/lib/task-agent/` | `task-agent` の HOME(Claude Code のログイン、`.gitconfig`、gh のトークン `.config/gh/hosts.yml`) |
| `~/.local/share/task-hub/worktrees/` | 共有(グループ `task-agents`、setgid、ACL) |
| `~/.local/share/task-hub/repos/` | 共有(同上) |

### worktree の共有

- ディレクトリの setgid で、どちらが作ったファイルもグループ `task-agents` になる
- デフォルト ACL で、新しいファイル・ディレクトリにも `joka`・`task-agent`・`task-agents` の rw が付く(デフォルト ACL があると umask は効かない)
- `joka` の名前も ACL に入れてあるのは、ログインし直すまで `joka` のプロセスが `task-agents` グループを持っていないため

### `/home/joka` を読ませない仕組み

worktree が `/home/joka`(モード 700)の中にあるので、`task-agent` には途中のディレクトリを通る権限(`x` だけ)を付けている。`x` だけなので `ls /home/joka` はできないが、名前が分かっているものには届いてしまう。`~/.config`・`~/.claude`(会話の記録)などは誰でも読めるモード(755・644)のものが多いので、途中のものには全部 `task-agent` 用の `---` の ACL を付けて閉じている(名前付きユーザーの ACL は「その他」より優先される)。

あとから増えたものは閉じていないので、ときどき `status` を見て、`WARNING: task-agent can read ...` が出たら `sudo scripts/setup_agent_user.sh` をもう一度実行する。根本的には、task-hub のデータ(worktree と repos)を HOME の外(`/srv/task-hub` など)に置けば、HOME を通らせなくて済む(task-hub 側の変更が要る)。

## 確認

```bash
sudo scripts/setup_agent_user.sh check
```

`check` が確かめること(1 つでも失敗すると終了コード 1):

1. `joka` で `sudo -u task-agent -n true` がパスワードなしで通る
2. `joka` で `sudo -u root -n true` が通らない(キャッシュされたパスワードは使わない)。`/etc/sudoers.d/task-agent` に `task-agent` 以外が書かれていない
3. worktree の中で、`joka` が作ったファイルを `task-agent` が読み書きでき、`task-agent` が作ったファイル・ディレクトリを `joka` が読み書き・削除できる
4. 既存の worktree で `task-agent` が `git status` できる。`repos/` の `.git` の `objects/`・`refs/heads/` に `task-agent` が書ける(commit できる)
5. `task-agent` に git の名前とメールがあり、gh に自分のトークンでログインしている
6. `task-agent` が `/home/joka` を一覧できず、`~` の中の共有していないものを何も読めない

手で確かめるとき:

```bash
sudo -k; sudo -n -u task-agent true && echo ok          # パスワードなしで通る
sudo -k; sudo -n -u root true || echo refused           # 「a password is required」で断られる
sudo -u task-agent ls /home/joka                        # → Permission denied なら OK
sudo -u task-agent cat /home/joka/.claude.json          # → Permission denied なら OK
sudo -u task-agent ls /home/joka/.local/share/task-hub/worktrees   # 見える
sudo -u task-agent -H gh auth status                    # task-agent のトークンでログインしている
sudo -u task-agent -H gh repo view jyoka/workenv_setting --json name   # 対象のリポは見える
```

## 重要なコマンド

```bash
sudo scripts/setup_agent_user.sh status                 # 全体の状態、読めてしまうものの警告
sudo -u task-agent -H -i                                # task-agent のシェル(ログイン・設定用)
sudo -n -u task-agent -H -D <worktree> -- <command>     # task-hub が使う形
sudo -u task-agent -H rm -rf <worktree>/<dir>           # joka が消せないファイルの掃除(下の「既知の問題」)
getfacl ~/.local/share/task-hub/worktrees               # ACL の中身
sudo -l -U joka                                         # joka に許されている sudo のルール
```

## アンインストール・ロールバック

```bash
sudo scripts/setup_agent_user.sh uninstall
```

やること(この順):

1. `/etc/sudoers.d/task-agent` を消す
2. `~/.local/share/task-hub` に `task-agent` の `---` の ACL を付けて入口を閉じ、`task-agent` のプロセスを止め、worktree と repos の中の `task-agent` 持ちのファイルを `joka` に戻す(ユーザーを消すと持ち主が数字だけになるため)
3. worktree と repos の ACL を全部外し(`setfacl -b`)、setgid を外し、グループ `task-agents` を `joka` に戻す
4. `~/.local/share/task-hub` と `/home/joka` の途中のものから `task-agent` の ACL を外す
5. ユーザー `task-agent` と `/var/lib/task-agent`(Claude Code のログイン情報・gh のトークンごと)、グループ `task-agents` を消す

そのあとログアウトしてログインし直すと、`joka` のセッションからも `task-agents` グループが消える。task-hub の設定でエージェントのユーザーを指定していたら、それも外す(外さないと `sudo -n -u task-agent` が失敗してタスクが動かない)。Claude の Web の設定(<https://claude.ai/settings>)で `task-agent` のログインのセッションを取り消し、GitHub の <https://github.com/settings/personal-access-tokens> で `task-agent` のトークンを消す(ファイルを消すだけではトークンは生きている)。

**ロールバックしても、worktree と repos はエージェントが書けた場所のまま。** `joka` で git を動かす前に、中の `.git/config`・`.git/hooks`・worktree の `.git` ファイルに覚えのないものがないか確かめるか、`repos/` を消して clone し直す。

手で戻すときの中身:

```bash
sudo rm /etc/sudoers.d/task-agent
sudo setfacl -m u:task-agent:--- ~/.local/share/task-hub && sudo pkill -KILL -u task-agent   # 先に入口を閉じてエージェントを止める
sudo chown -R -h --from=task-agent joka ~/.local/share/task-hub/worktrees
sudo chown -R -h --from=task-agent joka ~/.local/share/task-hub/repos
sudo setfacl -R -P -b ~/.local/share/task-hub/worktrees ~/.local/share/task-hub/repos
sudo setfacl -x u:task-agent ~ ~/.local ~/.local/share ~/.local/share/task-hub   # 途中のものの --- の ACL も同様に
sudo userdel task-agent && sudo rm -rf /var/lib/task-agent && sudo groupdel task-agents
```

## 既知の問題と対処法

- **`joka` が worktree のファイルを消せない・書けない**: ツールがモードを明示して作ったファイル・ディレクトリ(`mkdir -m 700`、`chmod 600` など)は ACL のマスクが狭まり、もう一方のユーザーが触れなくなる。root なしで直すには、**ファイルの持ち主が** `chmod -R g+rwX <path>` を実行する(ACL のあるファイルでは group のビットがマスクになるので、これでマスクが戻る)。`joka` の作ったものは `chmod -R g+rwX <path>`、`task-agent` の作ったものは `sudo -u task-agent -H chmod -R g+rwX <path>`(sudoers で許されている)。消すだけなら `sudo -u task-agent -H rm -rf <path>`。`sudo scripts/setup_agent_user.sh` をもう一度実行しても直る。task-hub は無人で root を使えないので、**エージェントの実行が終わったあと(worktree を消す前など)に `sudo -u task-agent -H chmod -R g+rwX <worktree>` を実行する**ようにする(`joka` 持ちのファイルには `Operation not permitted` が出るが、それは `joka` 側で `chmod -R g+rwX` すればよい。chmod は git ではないので `joka` で動かしてよい。task-hub 側の対応。まだ入っていない既知のすき間)
- **`install` が `processes run as task-agent` で止まる**: タスクの実行中。タスクが終わるのを待つか、`sudo pkill -u task-agent` で止めてからもう一度実行する(エージェントが動いている間は、root で共有ディレクトリをたどれないため。上の「セキュリティ」)
- **`sudo: a password is required`(`task-agent` への sudo で)**: `/etc/sudoers.d/task-agent` がない、または `/etc/sudoers` が `/etc/sudoers.d` を読んでいない(スクリプトは `@includedir /etc/sudoers.d` がないと止まる)。`status` で確認
- **エージェントの git が「dubious ownership」**: `task-agent` の `safe.directory` がない、または `TASKHUB_DATA` を変えた。`install` をもう一度実行する
- **エージェントの `git add`・`git commit` が `Permission denied`**: `repos/` の中のファイルのマスクが狭まった(上と同じ)か、`install` のあとに task-hub が `joka` で新しいリポを clone した(ACL が付いていない)。`install` をもう一度実行する
- **エージェントの `git push` が認証で失敗する**: `sudo -u task-agent -H gh auth status` でトークンを確かめる。期限切れ・対象のリポが入っていない・Contents の書き込みがない、のどれか。GitHub でトークンを直して `token` をもう一度実行する。remote が SSH なら https にする
- **task-hub 側でまだやること(既知のすき間)**: task-hub が今 `joka` で動かしている git(clone・fetch・`git worktree add`・commit・push)を、全部 `sudo -n -u task-agent -H git ...` にし、PR の確認を `joka` の gh の API(`gh pr view` など、リポのファイルを読まないもの)に変える。それまでは、エージェントを `task-agent` で動かしても上の「セキュリティ」の抜け道が残る
- **新しく作ったファイルが `task-agents` グループにならない**: setgid が外れた(`chmod` でモードを丸ごと指定した、など)。`install` をもう一度実行する
- **グループが効かない**: `id joka` に `task-agents` があっても、ログインし直すまで今のプロセスには反映されない

## 公式ドキュメント

- sudoers(`Runas_Spec`、`CWD`、`NOPASSWD`): <https://www.sudo.ws/docs/man/sudoers.man/>
- ACL(`setfacl`): <https://man.archlinux.org/man/setfacl.1>、<https://wiki.archlinux.org/title/Access_Control_Lists>
- ユーザーとグループ(Arch Wiki): <https://wiki.archlinux.org/title/Users_and_groups>
- git の `safe.directory`: <https://git-scm.com/docs/git-config#Documentation/git-config.txt-safedirectory>
- fine-grained personal access token: <https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens>
- `gh auth login`・`gh auth setup-git`: <https://cli.github.com/manual/gh_auth_login>、<https://cli.github.com/manual/gh_auth_setup-git>
- Claude Code のインストールと認証: <https://docs.anthropic.com/en/docs/claude-code/setup>
