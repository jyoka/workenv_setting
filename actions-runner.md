# GitHub Actions のセルフホストランナー(Linux / Omarchy)

Linux 機(Omarchy、Arch 系。i7-8700 12 スレッド、メモリ 15 GB)を GitHub Actions のセルフホストランナーにする設定(2026-10-17)。CI を M1 Pro の Mac や GitHub のランナーではなくこのマシンで動かし、Mac の負荷を減らすのが目的。スリープしない・ログインなしで動く・Tailscale などの常時稼働の設定は [常時稼働マシン](./always-on.md) で行う。

## 目的とよくある使い方

- 自分のプライベートリポの CI(テスト・lint・ビルド)をこのマシンで動かす
- ランナーは専用ユーザー `github-runner` の systemd サービスとして起動時に動き出す。ジョブは `/home/joka`(SSH 鍵、gh・Claude の認証情報、task-hub の状態)を読めない
- CPU・メモリに上限があるので、CI が走っていても task-hub のエージェント(`task-hub-watch.service`)とデスクトップが詰まらない

## セキュリティ(必読)

セルフホストランナーは **PR のコードをこのマシンでそのまま実行する**。

- **プライベートリポ、または PR を出せるのが自分だけのリポにだけ付ける**。フォークからの PR を受け付ける公開リポには絶対に付けない(誰でもこのマシンでコードを実行できてしまう)
- 公開リポに付けざるを得ないときは、リポの Settings → Actions → General → **「Fork pull request workflows from outside collaborators」を「Require approval for all outside collaborators」** にする(既定の「first-time contributors」だけでは足りない)。それでも承認前にコードを読むこと
- 専用ユーザーとサンドボックス(下の「仕組み」)は事故を小さくするためのもので、悪意のあるコードを安全に動かせる保証ではない。ジョブはネットワーク(LAN・tailnet)に出られる
- `github-runner` を `docker` グループや `wheel` に入れない。`docker` グループは root と同じ権限なので、`/home/joka` も読めてしまう(`status` が警告を出す)

## インストール方法とバージョン

公式の [`actions/runner`](https://github.com/actions/runner) のリリース(`actions-runner-linux-x64-<版>.tar.gz`)を使う。AUR の `github-actions-runner` は使わない:

- ランナーは自分自身を新しい版に自動更新する。AUR パッケージだとパッケージのファイルをランナーが書き換え、pacman の管理と食い違う
- 個人アカウントではリポごとにランナーを 1 つずつ登録するので、リポごとのコピーがいる。パッケージの 1 か所のインストールでは足りない
- AUR ヘルパー(yay など)なしで動く。ダウンロードはリリースノートの SHA-256 で検証する

2026-10-17 時点の最新は v2.338.0。スクリプトはいつも最新のリリースを取る。

### セットアップ

Linux 機でリポのルートから、**自分のユーザーで** ターミナルで実行する(`sudo` がパスワードを聞く。`gh` はリポの管理者権限でログインしている必要がある):

```bash
scripts/setup_actions_runner.sh install                 # ユーザー・パッケージ・systemd ユニット・ランナー本体
scripts/setup_actions_runner.sh add jyoka/workenv_setting jyoka/task-hub   # リポを足す(登録して起動)
scripts/setup_actions_runner.sh status                  # 何が入っているか(変更しない)
```

何度実行してもよい。ユーザー・パッケージ・ユニットはないときだけ作り、ファイルは中身が違うときだけ書き換え、登録済みのリポ(`.runner` がある)は登録し直さない。設定を変えたときだけランナーを再起動する。`add` は `install` を含む。

`install` がやること:

| やること | 中身 |
|:--|:--|
| パッケージ | `git jq curl tar unzip zip icu krb5 base-devel` を pacman で(`icu`・`krb5` はランナー本体が使う)。`/usr/bin/mise` がなければ `mise` も |
| ユーザー | システムユーザー `github-runner`(ホーム `/var/lib/github-runner`、シェル `nologin`、追加グループなし、sudo なし) |
| systemd | [`config/linux/actions-runner/systemd/`](./config/linux/actions-runner/systemd/) の `ci.slice` と `actions-runner@.service` を `/etc/systemd/system/` に置く |
| ランナー本体 | 最新リリースを `/var/lib/github-runner/cache/` にダウンロードして SHA-256 を確認 |

`add owner/repo` がやること: `/var/lib/github-runner/runners/<owner>__<repo>/` に展開 → `gh api` で登録トークンを取って `config.sh --unattended` で登録 → `actions-runner@<owner>__<repo>.service` を有効化・起動 → GitHub 上の状態を表示。

ラベルは `self-hosted, Linux, X64`(ランナーが自動で付ける)と `omarchy`。ランナー名はホスト名。変えるときは `RUNNER_LABELS=omarchy,gpu RUNNER_NAME=box scripts/setup_actions_runner.sh add ...`(登録済みのリポは一度 `remove` してから)。

### トークンについて

登録・削除のトークンは実行のたびに `gh api -X POST repos/<owner>/<repo>/actions/runners/{registration,remove}-token` で取る(1 時間で失効)。トークンは標準入力と環境変数 `ACTIONS_RUNNER_INPUT_TOKEN` で `config.sh` に渡すので、コマンドライン(`ps`)にもファイルにも残らない。**トークンをこのリポにコミットしないこと。** 登録後の認証情報(`.credentials`、`.credentials_rsaparams`)は各ランナーのディレクトリにあり、`github-runner` しか読めない。

## リポを足す・外す

個人アカウント(jyoka)には **ユーザー単位のランナーがない**(GitHub が用意しているのはリポ・Organization・Enterprise 単位だけ)。なので 1 リポにつき 1 ランナー(ディレクトリと systemd インスタンス)を作る。全部同じユーザー・同じ `ci.slice` で動くので、上限は全ランナーの合計にかかる。

```bash
scripts/setup_actions_runner.sh add jyoka/new-repo        # 足す
scripts/setup_actions_runner.sh remove jyoka/old-repo     # 外す(GitHub から登録解除して、ディレクトリも消す)
```

リポを Organization に移せば Organization 単位のランナー 1 つで全リポをまかなえるが、今はしていない。

`remove` でトークンが取れない(リポを消した、権限がない)ときは、ローカルだけ消して警告を出す。GitHub 側に残ったオフラインのランナーは、リポの Settings → Actions → Runners から消す。

## ワークフローからの使い方

```yaml
jobs:
  test:
    runs-on: [self-hosted, linux]
    steps:
      - uses: actions/checkout@v5
      - run: make test
```

### ubuntu-latest へのフォールバック

`runs-on` は「セルフホストが落ちていたら GitHub のランナー」という自動切り替えができない(ジョブはランナーが戻るまで待ち続ける)。リポ変数で切り替えられるようにしておく:

```yaml
jobs:
  test:
    # Repository variable CI_RUNNER = ["self-hosted","linux"] → this machine; unset → ubuntu-latest
    runs-on: ${{ vars.CI_RUNNER && fromJSON(vars.CI_RUNNER) || 'ubuntu-latest' }}
```

- このマシンを使う: `gh variable set CI_RUNNER --body '["self-hosted","linux"]' -R jyoka/<repo>`
- GitHub のランナーに戻す(マシンを止めるとき、公開リポにするとき): `gh variable delete CI_RUNNER -R jyoka/<repo>`

### 動作確認用のワークフロー

`.github/workflows/runner-check.yml` として置き、Actions タブから手動で実行する(`gh workflow run runner-check.yml`)。成功すれば、ランナーが動いていて、ジョブから `/home/joka` が見えないことが確認できる:

```yaml
name: runner-check
on: workflow_dispatch
jobs:
  check:
    runs-on: [self-hosted, linux]
    steps:
      - uses: actions/checkout@v5
      - run: id && uname -a && nproc && mise --version
      - name: Jobs cannot read /home/joka
        run: |
          if ls -A /home/joka 2>/dev/null | grep -q .; then
            echo "::error::/home/joka is readable from CI jobs"; exit 1
          fi
          echo "ok: /home/joka is not readable"
```

### ツールチェーン(mise)

ランナーのユーザーには最小限だけ入れている: git・jq・curl・unzip・zip・`base-devel`(gcc・make)・mise。言語のランタイムはジョブの中で入れる:

- リポに `mise.toml` があれば、ステップで `mise install` してから `mise exec -- <コマンド>`(または `jdx/mise-action`)。入れたものは `/var/lib/github-runner/.local/share/mise` に残るので 2 回目から速い。`MISE_TRUSTED_CONFIG_PATHS` をランナーの `.env` に入れてあるので、チェックアウトした `mise.toml` は確認なしで信頼される
- `actions/setup-node` などの `setup-*` も使える(`/var/lib/github-runner/runners/<repo>/_work/_tool` にキャッシュされる)
- ランナーの PATH は各ランナーの `.path`(mise の shims が先頭)。`add` が書く

**Docker / Podman は入れていない。** `docker` グループは root 相当で、上のサンドボックスと `/home/joka` の保護が意味をなくすうえ、コンテナは `ci.slice` の外(`docker.service`)で動くのでリソースの上限も効かない。`container:` や `services:` を使うジョブ、Docker を使うアクションは GitHub のランナー(`ubuntu-latest`)で動かす。必要になったら、`github-runner` 用のルートレス Podman を別途検討する。

### macOS のジョブ

このマシンは Linux x64 だけ。macOS が要るジョブ(Xcode、`swift test` on macOS、macOS 専用のツール)は今まで通り `runs-on: macos-latest`(GitHub の macOS ランナー)か Mac で動かす。

## 仕組み・設定ファイルの場所

| 場所 | 中身 |
|:--|:--|
| [`scripts/setup_actions_runner.sh`](./scripts/setup_actions_runner.sh) | セットアップ・追加・削除・状態表示・アンインストール |
| `/etc/systemd/system/ci.slice` | 全ランナー共通のリソース上限(実物は `config/linux/actions-runner/systemd/ci.slice`) |
| `/etc/systemd/system/actions-runner@.service` | ランナー 1 つ分のサービス(テンプレート)。インスタンス名は `<owner>__<repo>` |
| `/var/lib/github-runner/runners/<owner>__<repo>/` | ランナー本体・登録情報(`.runner`、`.credentials`)・作業ディレクトリ `_work`・ログ `_diag` |
| `/var/lib/github-runner/cache/` | ダウンロードしたリリースの tar.gz(最新だけ残す) |

### リソースの上限

`ci.slice` は `user.slice`(デスクトップと `task-hub-watch`)・`system.slice` と並ぶトップレベルの slice。

| 設定 | 値 | 意味 |
|:--|:--|:--|
| `CPUWeight` | 20 | CPU が混んでいるときの取り分。`user.slice` の 100 に対して 1/5 なので、エージェントとデスクトップが優先される |
| `CPUQuota` | 600% | 空いていても 6 スレッド分まで(12 スレッド中) |
| `MemoryHigh` / `MemoryMax` | 6G / 8G | 6 GiB を超えると CI のメモリから回収、8 GiB で CI のジョブだけ OOM で止まる |
| `MemorySwapMax` | 2G | スワップの上限 |
| `IOWeight` | 20 | ディスク I/O の取り分 |
| `TasksMax` | 4096 | プロセス数の上限(fork 爆弾よけ) |
| `Nice` / `IOSchedulingPriority` / `OOMScoreAdjust` | 10 / 7 / 500 | サービス側。優先度を下げ、メモリ不足時は CI から先に止める |

変えるときは repo の `ci.slice` を直して `install` を再実行する(マシンだけで試すなら `sudo systemctl edit ci.slice`)。

### サンドボックス

`actions-runner@.service` の設定:

- `ProtectHome=yes`: `/home`・`/root`・`/run/user` に入れない(`Permission denied`)。`/home/joka` のパーミッション(700)とあわせて二重に守る
- `ProtectSystem=strict` + `ReadWritePaths=/var/lib/github-runner`: 書けるのはランナーのホームと自分専用の `/tmp` だけ
- `PrivateTmp=yes`、`NoNewPrivileges=yes`、`RestrictSUIDSGID=yes`: `sudo` や setuid で権限を上げられない
- `ProtectKernel*`・`ProtectControlGroups`・`ProtectClock`: カーネル設定・cgroup・時計を変えられない

このため、ジョブの中で `sudo`・`pacman`・`apt` は使えない。システムにパッケージが要るときは、`install` の `need_pkgs` に足して再実行する。

## 重要なコマンド

```bash
scripts/setup_actions_runner.sh status                       # 全体の状態と GitHub 上の Online/Offline
systemctl status 'actions-runner@*'                          # サービスの状態
journalctl -u actions-runner@jyoka__workenv_setting -f       # ランナーのログ
systemd-cgtop ci.slice                                       # CI が今使っている CPU・メモリ
sudo systemctl stop 'actions-runner@*'                       # 一時的に止める(ジョブは待ち状態になる)
gh api repos/jyoka/<repo>/actions/runners --jq '.runners[] | {name,status,busy}'
```

`/home/joka` が読めないことをマシンで確かめる(ジョブと同じサンドボックスで `ls` する):

```bash
sudo systemd-run --pipe --wait -p User=github-runner -p ProtectHome=yes ls -la /home/joka
# → ls: cannot access '/home/joka': Permission denied  なら OK
```

## アンインストール・登録解除

```bash
scripts/setup_actions_runner.sh remove jyoka/<repo>   # 1 リポだけ外す
scripts/setup_actions_runner.sh uninstall             # 全部
```

`uninstall` は全ランナーを GitHub から登録解除し、サービス・`ci.slice`・`actions-runner@.service`・ユーザー `github-runner`・`/var/lib/github-runner` を消す。pacman で入れたパッケージは残す。最後に各リポの Settings → Actions → Runners に残りがないか確認し、`CI_RUNNER` 変数を使っていたら消す(`gh variable delete CI_RUNNER -R jyoka/<repo>`)。

## 既知の問題と対処法

- **ランナーが Offline**: `journalctl -u actions-runner@<owner>__<repo>` を見る。ネットワーク待ちなら自動で再接続する。登録が消えている(GitHub 側で削除した)ときは `remove` → `add`
- **ジョブが「Waiting for a runner」のまま**: `runs-on` のラベルがランナーのラベルと合っていない、またはランナーが止まっている。`status` で確認
- **ジョブが `sudo` や `apt-get` で失敗**: サンドボックスで使えない(上の「サンドボックス」)。`ubuntu-latest` 前提のワークフローはそのままでは動かないことがある
- **ジョブが OOM で落ちる**: `ci.slice` の `MemoryMax`(8G)に当たった。`journalctl -k | grep -i oom` で確認
- **ランナーの自動更新**: ランナーは新しい版が出ると自分で更新して再起動する(`runsvc.sh` が面倒を見る)。キャッシュの tar.gz は次の `add` / `install` で最新になる

## 公式ドキュメント

- セルフホストランナー: <https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners>
- セキュリティ(公開リポで使わない理由): <https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions#hardening-for-self-hosted-runners>
- フォークの PR の承認: <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#controlling-changes-from-forks-to-workflows-in-public-repositories>
- 登録トークンの API: <https://docs.github.com/en/rest/actions/self-hosted-runners>
- ランナーのリリース: <https://github.com/actions/runner/releases>
