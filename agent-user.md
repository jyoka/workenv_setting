# task-hub エージェント専用ユーザー(Linux / Omarchy)

task-hub のコーディングエージェント(Claude Code など)を、自分(`joka`)ではなく **専用の権限のないユーザー `task-agent`** で動かすための設定(2026-10-17)。エージェントが `joka` の全権限(SSH 鍵、gh・Claude の認証情報、他のリポ)で動かないようにするのが目的。

task-hub のサンドボックスのタスク(「Self-hosted dev assistant (3/6): sandbox runs」、[jyoka/task-hub#80](https://github.com/jyoka/task-hub/pull/80))は bwrap をやめて、エージェントを別の Linux ユーザーで動かす方式にした(bwrap は、サンドボックスの外で動く task-hub 自身の git の処理から抜けられてしまったため)。ユーザーを作るには root が要り、無人のエージェントにはできないので、このスクリプトを自分で `sudo` で実行する。

## 目的とよくある使い方

- task-hub は `sudo -n -u task-agent -H -D <worktree> -- <エージェントのコマンド>` でエージェントを起動する(パスワードなし)
- エージェントが読み書きできるのは task-hub の worktree(`~/.local/share/task-hub/worktrees/`)だけ。worktree の元のリポ(`~/.local/share/task-hub/repos/`)は読むだけ
- `/home/joka` の中身は一覧できず、読めない(`~/.ssh`、`~/.config/gh`、`~/.claude`、`~/.claude.json` など)。エージェントは自分の HOME(`/var/lib/task-agent`)に自分の認証情報を持つ
- `joka` が `sudo` で `task-agent` になれるだけで、`task-agent` からは root にも `joka` にもなれない

GitHub Actions のランナー用の `github-runner`([GitHub Actions のセルフホストランナー](./actions-runner.md))とは別のユーザー。同じやり方(システムユーザー、追加グループなし、sudo なし)で作るが、使い回さない。

## セキュリティ(必読)

- **これは事故を小さくするためのもので、悪意のあるコードを安全に動かす保証ではない。** エージェントはネットワーク(LAN・tailnet)に出られ、`/tmp` や誰でも読めるシステムのファイルは見える
- **`task-agent` を `wheel`・`docker` グループに入れない**(root になれてしまう。スクリプトは警告を出す)
- **worktree のコードを `joka` で実行しない。** エージェントは worktree のファイルを自由に書き換えられるので、task-hub が `joka` のまま worktree のテスト・`Makefile`・`npm` スクリプトなどを動かすと、それがエージェントの抜け道になる。worktree のコードは `task-agent` で動かす
- **元のリポ(`repos/`)はエージェントに書かせない。** `.git/hooks` や `.git/config`(`core.hooksPath`、`core.fsmonitor`)を書き換えられると、task-hub が `joka` で動かす git(commit・push)の中でそれが実行される。bwrap が破られたのと同じ道なので、スクリプトは `repos/` を読み取り専用にしている
- **`joka` の git に `safe.directory = *` を設定しない。** worktree の `.git` ファイル(gitdir へのポインタ)はエージェントが書き換えられる場所にある。エージェントが自分の持ち物の gitdir に向け直しても、`joka` の git は所有者が違うので拒否する(「dubious ownership」)。`safe.directory = *` はこの保護を外してしまう
- `/home/joka` の中は、スクリプトを実行した時点にあったものに「`task-agent` は読めない」ACL を付けている。あとから `~` に増えたディレクトリ・ファイルは、名前を知っていれば読める可能性がある。`status` が警告を出すので、そのときは `install` をもう一度実行する(下の「仕組み」)

## インストール方法とバージョン

パッケージは足さない(`acl`・`sudo`・`shadow` は Omarchy に最初から入っている。`setfacl` がないときだけ `acl` を pacman で入れる)。

### セットアップ

Linux 機でリポのルートから、**自分(`joka`)のアカウントで `sudo` を付けて** 実行する(`joka` が task-hub のユーザーになる。`SUDO_USER` から決まる):

```bash
sudo scripts/setup_agent_user.sh            # ユーザー・グループ・sudoers・ACL を作る(直す)
sudo scripts/setup_agent_user.sh status     # 何が入っているか(変更しない)
sudo scripts/setup_agent_user.sh check      # 受け入れチェック(下の「確認」)
```

何度実行してもよい。ユーザー・グループはないときだけ作り、sudoers は中身が違うときだけ書き換える。ACL は毎回付け直すので、ずれた権限の修復にもなる。最後に task-hub に設定する値を表示する:

```text
task-hub settings:
  agent user   task-agent
  agent group  task-agents
  agent home   /var/lib/task-agent
  shared dirs  /home/joka/.local/share/task-hub/worktrees (read/write)
  read-only    /home/joka/.local/share/task-hub/repos
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
| 元のリポ | `~/.local/share/task-hub/repos` 以下に `task-agent` の読み取りだけの ACL(アクセスとデフォルト) |
| `/home/joka` | `~`・`~/.local`・`~/.local/share`・`~/.local/share/task-hub` に `task-agent` の通過だけ(`--x`)の ACL。その途中の他のもの全部(`~/.claude`、`~/.config`、`~/.zshrc`、`~/.local/share/mise`、`~/.local/lib`(task-hub の実行用クローン)、`task-hub/prompts`・`task-hub/run` など)に `task-agent` の「アクセスなし」(`---`)の ACL |
| git | `task-agent` の `~/.gitconfig` に `safe.directory` として `worktrees/*` と `repos/*` を足す(`joka` 持ちのリポを git が拒否しないように) |

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

### git の名前とメール(必要)

task-hub の commit・push は `joka` で行うが、エージェントが worktree で git を使うと名前がないと怒られることがある。自分の名前と GitHub の noreply アドレスなど、使いたい値を入れる:

```bash
sudo -u task-agent -H git config --global user.name  '<名前>'
sudo -u task-agent -H git config --global user.email '<メール>'
```

`safe.directory` はスクリプトが入れる。`task-agent` は `repos/` に書けないので、`git status`・`git diff`・`git log` は使えるが、`git add`・`git commit`・`git stash`・`git checkout -- <file>` などインデックスを書き換えるものは失敗する。task-hub の作り(エージェントは commit しない、commit は task-hub が行う)に合わせた制限。

### gh のトークン(今は要らない)

push と PR は task-hub が `joka` の `gh` で行うので、`task-agent` には gh のトークンも SSH 鍵も渡さない。task-hub の作りが変わってエージェントが GitHub の API を使う必要が出たら、対象のリポだけに絞った fine-grained token を作って `task-agent` でログインする(`joka` のトークンは渡さない):

```bash
sudo -u task-agent -H -i
gh auth login --with-token < token.txt && rm token.txt   # ~/.config/gh/hosts.yml に入る
```

### ツールチェーン

`joka` の mise(`~/.local/share/mise`)も読めない。エージェントが言語のランタイムを使うなら、`task-agent` に mise を入れて(`/usr/bin/mise` があればそれを使い)、`task-agent` の HOME にインストールする。

## 仕組み・設定ファイルの場所

| 場所 | 中身 |
|:--|:--|
| [`scripts/setup_agent_user.sh`](./scripts/setup_agent_user.sh) | セットアップ・状態表示・チェック・アンインストール |
| `/etc/sudoers.d/task-agent` | `joka` → `task-agent` の sudo のルール |
| `/var/lib/task-agent/` | `task-agent` の HOME(Claude Code のログイン、`.gitconfig`) |
| `~/.local/share/task-hub/worktrees/` | 共有(グループ `task-agents`、setgid、ACL) |
| `~/.local/share/task-hub/repos/` | `task-agent` は読むだけ |

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
4. 既存の worktree で `task-agent` が `git status` できる。`repos/` の `.git`(本体・`config`・`hooks`)に `task-agent` が書けない
5. `task-agent` が `/home/joka` を一覧できず、`~` の中の共有していないものを何も読めない

手で確かめるとき:

```bash
sudo -k; sudo -n -u task-agent true && echo ok          # パスワードなしで通る
sudo -k; sudo -n -u root true || echo refused           # 「a password is required」で断られる
sudo -u task-agent ls /home/joka                        # → Permission denied なら OK
sudo -u task-agent cat /home/joka/.claude.json          # → Permission denied なら OK
sudo -u task-agent ls /home/joka/.local/share/task-hub/worktrees   # 見える
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
2. `task-agent` のプロセスを止め、worktree の中の `task-agent` 持ちのファイルを `joka` に戻す(ユーザーを消すと持ち主が数字だけになるため)
3. `/home/joka` の途中のもの・`repos/` から `task-agent` の ACL を外す
4. worktree の ACL を全部外し(`setfacl -b`)、setgid を外し、グループ `task-agents` を `joka` に戻す
5. ユーザー `task-agent` と `/var/lib/task-agent`(Claude Code のログイン情報ごと)、グループ `task-agents` を消す

そのあとログアウトしてログインし直すと、`joka` のセッションからも `task-agents` グループが消える。task-hub の設定でエージェントのユーザーを指定していたら、それも外す(外さないと `sudo -n -u task-agent` が失敗してタスクが動かない)。Claude の Web の設定(<https://claude.ai/settings>)で `task-agent` のログインのセッションを取り消しておくとよい。

手で戻すときの中身:

```bash
sudo rm /etc/sudoers.d/task-agent
sudo chown -R -h --from=task-agent joka ~/.local/share/task-hub/worktrees
sudo setfacl -R -b ~/.local/share/task-hub/worktrees
sudo setfacl -R -x u:task-agent ~/.local/share/task-hub/repos
sudo setfacl -x u:task-agent ~ ~/.local ~/.local/share ~/.local/share/task-hub   # 途中のものの --- の ACL も同様に
sudo userdel task-agent && sudo rm -rf /var/lib/task-agent && sudo groupdel task-agents
```

## 既知の問題と対処法

- **`joka` が worktree のファイルを消せない・書けない**: ツールがモードを明示して作ったファイル・ディレクトリ(`mkdir -m 700`、`chmod 600` など)は ACL のマスクが狭まり、もう一方のユーザーが触れなくなる。root なしで直すには、**ファイルの持ち主が** `chmod -R g+rwX <path>` を実行する(ACL のあるファイルでは group のビットがマスクになるので、これでマスクが戻る)。`joka` の作ったものは `chmod -R g+rwX <path>`、`task-agent` の作ったものは `sudo -u task-agent -H chmod -R g+rwX <path>`(sudoers で許されている)。消すだけなら `sudo -u task-agent -H rm -rf <path>`。`sudo scripts/setup_agent_user.sh` をもう一度実行しても直る。task-hub は無人で root を使えないので、**エージェントの実行が終わったあと、commit の前に `sudo -u task-agent -H chmod -R g+rwX <worktree>` を実行する**ようにする(`joka` 持ちのファイルには `Operation not permitted` が出るが、それは `joka` 側で `chmod -R g+rwX` すればよい。task-hub 側の対応。まだ入っていない既知のすき間)
- **`sudo: a password is required`(`task-agent` への sudo で)**: `/etc/sudoers.d/task-agent` がない、または `/etc/sudoers` が `/etc/sudoers.d` を読んでいない(スクリプトは `@includedir /etc/sudoers.d` がないと止まる)。`status` で確認
- **エージェントの git が「dubious ownership」**: `task-agent` の `safe.directory` がない、または `TASKHUB_DATA` を変えた。`install` をもう一度実行する
- **エージェントの `git add`・`git commit` が `Permission denied`**: 仕様(上の「git の名前とメール」)。commit は task-hub が `joka` で行う
- **新しく作ったファイルが `task-agents` グループにならない**: setgid が外れた(`chmod` でモードを丸ごと指定した、など)。`install` をもう一度実行する
- **グループが効かない**: `id joka` に `task-agents` があっても、ログインし直すまで今のプロセスには反映されない

## 公式ドキュメント

- sudoers(`Runas_Spec`、`CWD`、`NOPASSWD`): <https://www.sudo.ws/docs/man/sudoers.man/>
- ACL(`setfacl`): <https://man.archlinux.org/man/setfacl.1>、<https://wiki.archlinux.org/title/Access_Control_Lists>
- ユーザーとグループ(Arch Wiki): <https://wiki.archlinux.org/title/Users_and_groups>
- git の `safe.directory`: <https://git-scm.com/docs/git-config#Documentation/git-config.txt-safedirectory>
- Claude Code のインストールと認証: <https://docs.anthropic.com/en/docs/claude-code/setup>
