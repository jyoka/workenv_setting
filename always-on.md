# 常時稼働マシン(Linux / Omarchy)

Linux 機(Omarchy、Arch 系)を、task-hub のエージェントを無人で動かすホストにするための設定(2026-10-17)。スリープしない・ログインしなくてもユーザーサービスが動く・外から Tailscale 経由で SSH できる・再起動後のディスク(LUKS)のロック解除を SSH でもできる、の 4 つ。

## 目的とよくある使い方

- 停電や更新で再起動しても、スマホ / ノート PC から SSH でディスクのロックを解除すれば、task-hub の watcher(`task-hub-watch.service`)が誰もログインしないまま動き出す
- 画面のロックと消灯(Omarchy のスクリーンセーバー)は今まで通り動く。止めるのはスリープだけ
- Bluetooth キーボード(NuPhy Air75)でのロック解除も今まで通り使える。キーボードと SSH の早い方が解除する

## セットアップ

Linux 機でリポのルートから、ターミナルで実行する(`sudo` がパスワードを聞く):

```bash
scripts/setup_always_on.sh             # 全ステップを順に
scripts/setup_always_on.sh idle linger # 一部だけ
scripts/setup_always_on.sh status      # 何が入っているかの確認だけ(変更しない)
```

何度実行してもよい。ファイルは中身が違うときだけ書き換え、initramfs は入力が前回の作り直しの成功(`/etc/dropbear-initramfs/initramfs-built.stamp`)より新しいときだけ作り直す。作り直しが途中で失敗しても、原因を直して同じコマンドをもう一度実行すれば作り直される。各ステップの中身:

| ステップ | やること | 置くファイル(実物は [`config/linux/always-on/`](./config/linux/always-on/)) |
|:--|:--|:--|
| `idle` | サスペンド・ハイバネートを禁止。logind のアイドル動作・サスペンドキーも無視 | `/etc/systemd/sleep.conf.d/always-on.conf`、`/etc/systemd/logind.conf.d/always-on.conf` |
| `linger` | `loginctl enable-linger $USER`、`task-hub-watch.service` を有効化。gh のトークンがログインなしで読めないと警告する | — |
| `tailscale` | `tailscale` を pacman で入れ、`tailscaled` を有効化、未ログインなら `tailscale up` | — |
| `ssh` | OpenSSH を鍵認証のみにし、ufw で `tailscale0` からの 22 番だけ許可 | `/etc/ssh/sshd_config.d/10-always-on.conf` |
| `initramfs` | initramfs に dropbear(SSH、2222 番)とネットワークを入れ、`encrypt` を `encryptssh` に置き換える | `/etc/initcpio/{install,hooks}/unlock-sshd`、`/etc/mkinitcpio.conf.d/zz_remote_unlock.conf`、`/etc/limine-entry-tool.d/remote-unlock.conf`、`/etc/dropbear-initramfs/` |

### 事前に用意するもの

- **SSH の公開鍵**: スマホ / ノート PC の公開鍵を `~/.ssh/authorized_keys` に入れておく。`ssh` ステップはパスワードログインを止めるので、空だと SSH で入れなくなる(マシンの前ではログインできる)。`initramfs` ステップは同じファイルをロック解除用の鍵として使う(別の鍵にしたいときは `UNLOCK_KEYS=<ファイル>` を付けて実行)
- **ufw が有効**: Omarchy は既定で有効。無効だと sshd が LAN 全体に開くので、`ssh` ステップは止まる
- **有線 LAN**: 下の「SSH でのロック解除」を参照
- **Tailscale のログイン**: `tailscale up` が出す URL を別の端末で開く。管理画面(<https://login.tailscale.com/admin/machines>)でこのマシンの **Key expiry を無効** にしておく(期限切れで勝手に tailnet から外れないように)

### BIOS(手作業)

停電後に自動で電源が入るよう、BIOS / UEFI の **「Restore on AC Power Loss」(AC Back、After Power Loss などとも)を「Power On」** にする。メーカーで名前が違う。これがないと、停電のたびに誰かが電源ボタンを押す必要がある。

## 設定の詳細

### スリープしない(画面のロックは残す)

Omarchy のアイドル処理は hypridle ではなく Omarchy シェル(`~/.config/omarchy/shell.json` の `idle.screensaver` / `idle.lock`)で、スクリーンセーバー → ロックまでしかしない。サスペンドするのは手動(メニュー、`systemctl suspend`)か logind だけなので、`sleep.conf.d` で `AllowSuspend=no` などを指定してどこから頼まれても眠らないようにした。`shell.json` は触っていないので、画面のロックと消灯はそのまま。

- メニューの「Suspend」を押しても失敗するだけ。メニューから消したいときは `omarchy toggle suspend`
- ハイバネート(`omarchy hibernation setup` で設定済み)も禁止される
- Omarchy の「Stay Awake」(`omarchy toggle idle`)をオンにすると画面もロックされなくなる。`status` で確認できる
- `logind.conf.d` は次の起動から効く(`sleep.conf.d` は即時)

### ログインなしでユーザーサービスを動かす(linger)

linger を有効にすると、起動時にユーザーの systemd(`systemctl --user`)が立ち上がり、`WantedBy=default.target` のユニットが動く。`task-hub-watch.service`(`~/.config/systemd/user/`)はこれで、グラフィカルログインなしで起動する。Wi-Fi(NetworkManager の接続「jyoka」)はシステム側に保存されたパスワードで自動接続するので、ログイン前からネットにつながる。

**GitHub のトークン(要対応)**: 今の `gh` はトークンを gnome-keyring に保存している(`gh auth status` に `(keyring)` と出て、`~/.config/gh/hosts.yml` に `oauth_token` がない)。gnome-keyring は SDDM でログインしたとき(`pam_gnome_keyring`)にしか開かないので、**誰もログインしていないと watcher の `gh` が毎回認証エラーになる**。ユニット自体は `active (running)` のままなので、`systemctl status` では気づけない。どちらかでログインなしでも読める場所にトークンを置く:

- **(おすすめ)ユニットに `GH_TOKEN` を渡す**: トークンはこのユニットだけが読む。`gh auth token` は keyring が開いている(ログインしている)ときに実行する

  ```bash
  install -Dm600 /dev/null ~/.config/task-hub/gh-token.env
  printf 'GH_TOKEN=%s\n' "$(gh auth token)" > ~/.config/task-hub/gh-token.env
  mkdir -p ~/.config/systemd/user/task-hub-watch.service.d
  printf '[Service]\nEnvironmentFile=%%h/.config/task-hub/gh-token.env\n' \
    > ~/.config/systemd/user/task-hub-watch.service.d/gh-token.conf
  systemctl --user daemon-reload && systemctl --user restart task-hub-watch
  ```

- **`gh auth login --insecure-storage`**: トークンを `~/.config/gh/hosts.yml` に平文で書く。ターミナルの `gh` も含め全部がそれを使う

どちらも、トークンがディスク上に平文で置かれる(LUKS で暗号化されたディスクの中、自分だけが読めるファイル)。keyring に比べ、ログイン中に同じユーザーで動くものなら何でも読める点が弱くなる。トークンを作り直したら(`gh auth refresh` など)、1 つ目の方法なら `gh-token.env` も書き直す。`scripts/setup_always_on.sh linger` は、どちらもされていないと警告する。

### リモートアクセス(Tailscale + OpenSSH)

Tailscale を選んだ理由: ポート開放やダイナミック DNS が要らず、スマホ・ノート PC から同じ名前(MagicDNS)で届く。WireGuard で端末同士が認証し合うので、SSH を LAN やインターネットに出さずに済む。

SSH は Tailscale SSH(`tailscale up --ssh`)ではなく、普通の OpenSSH にした。どの SSH クライアント(スマホの Termius など)でも同じ鍵で入れ、initramfs のロック解除と鍵を共有できるため。外への露出は ufw で絞る:

```bash
sudo ufw status | grep 22       # 22/tcp on tailscale0 ALLOW IN だけがあること
ssh <user>@<マシン名>            # 別の端末から、tailnet 経由で
```

iPhone / iPad からデスクトップごと見て操作したいときは、この Tailscale の上に wayvnc を乗せる: [リモートデスクトップ](./remote-desktop.md)。

### SSH でのロック解除(initramfs)

Arch の公式リポにある部品を組み合わせた:

| 部品 | パッケージ | 役割 |
|:--|:--|:--|
| `netconf` フック | `mkinitcpio-netconf` | カーネル引数 `ip=:::::eth0:dhcp` で initramfs の中で有線 NIC を上げる |
| `unlock-sshd` フック | このリポ(`config/linux/always-on/initcpio/`) | dropbear を 2222 番で起動する(鍵認証のみ、ポート転送なし) |
| `encryptssh` フック | `mkinitcpio-utils` | `encrypt` の代わり。キーボード(plymouth の入力欄)と SSH のどちらでも解除でき、片方が成功するともう片方の入力待ちを終わらせる |

フックの並びは `... block bluetooth netconf unlock-sshd encryptssh filesystems ...` になる。`zz_remote_unlock.conf` は `zz_bluetooth.conf` より後に読まれ、`encrypt` を置き換えるだけなので、Bluetooth キーボードのフックはプロンプトの直前に残る。

解除のしかた(再起動後、画面にパスワード入力が出ている状態で):

```bash
ssh -p 2222 root@<LAN の IP>     # 例: 192.168.0.x。ルーターで eno1 の MAC に IP を固定しておくと楽
# "Enter passphrase for ..." が出るので LUKS のパスフレーズを入力 → 接続が切れて起動が続く
```

initramfs の SSH ユーザーは `root` 固定で、ログインシェルは `cryptsetup_shell`(パスフレーズを聞くだけ)。シェルは取れない。

**届く範囲の制限**:

- initramfs には Tailscale がないので、**解除は LAN の中からだけ**。外から解除したいときは、LAN にいる常時稼働の別の機器(ルーター、Apple TV など)を Tailscale の [サブネットルーター](https://tailscale.com/kb/1019/subnets) にして `192.168.0.0/24` を流すと、tailnet 経由で `192.168.0.x:2222` に届く
- **有線 LAN(eno1)が必要**。今の接続は USB の Wi-Fi(`wlp0s20f0u6`)で、initramfs の中では Wi-Fi に接続できない(パスワードと wpa_supplicant を initramfs に入れる必要があり、やっていない)。initramfs では udev の名前付けがないので、有線 NIC は `eno1` ではなく `eth0` になる。既定の `ip=:::::eth0:dhcp` は `eth0` だけで DHCP を試し、10 秒(`netconf_timeout=10`)で諦める。ケーブルが刺さっていないと起動が最大 10 秒遅れるだけで、キーボードでの解除はできる
- **`ip=dhcp` は使わない**。netconf は本体に切り替わる前に、`ip=` の 6 番目の欄に書かれたデバイスだけを落とす(`ip addr flush`、`ip link set down`)。`ip=dhcp` にはデバイス名がないので何も落とされず、Wi-Fi を含む NIC が initramfs の DHCP のアドレスのまま残る(更新されないリースが残り、`eth0` → `eno1` の名前変更も邪魔されうる)
- NIC が複数あって `eth0` が有線でないときは、`UNLOCK_IP=:::::eth1:dhcp scripts/setup_always_on.sh initramfs` のように名前を変える(マシンの前で `quiet splash` を外して起動すると、`IP-Config:` の行に使ったデバイスが出る)

**セキュリティ上のトレードオフ**:

- initramfs は暗号化されていない ESP(`/boot`)に置かれる。中の **dropbear のホスト鍵は誰でも読める** 前提で考える。そのため、本体の sshd のホスト鍵は使い回さず、initramfs 専用の ed25519 鍵(`/etc/dropbear-initramfs/dropbear_ed25519_host_key`)を作っている(`mkinitcpio-dropbear` を使わなかったのは、本体の鍵をコピーしてしまうため)。ポートも 2222 に分けたので、`known_hosts` で本体と別の鍵として記録される
- ホスト鍵が盗まれると、LAN 内の攻撃者が initramfs のふりをしてパスフレーズを盗める。初回接続時に `setup_always_on.sh initramfs` が表示したフィンガープリントと照合し、**以後ホスト鍵の警告が出たらパスフレーズを入れない**
- 物理的に触れる人は initramfs 自体を書き換えられる(evil maid)。これは SSH 解除を入れる前からある LUKS + 暗号化されていない `/boot` の限界で、今回の変更で新しく生まれたものではない
- 認証は **鍵のみ**(dropbear `-s`)。パスワードログインはできない。`authorized_keys` は initramfs にコピーされるので、鍵を変えたら `setup_always_on.sh initramfs` をもう一度実行する(変更があれば作り直す)
- 2222 番は LAN に開く(initramfs には ufw がない)。シェルは取れず、ポート転送も無効(`-j -k`)

## 動作確認

| 確認すること | 方法 |
|:--|:--|
| アイドルでスリープしない / 画面はロックされる | 放置して `idle.lock`(既定 300 秒)後にロック画面になり、その後も SSH が通ること。`systemctl suspend` が失敗すること |
| ログインなしで `task-hub-watch` が動き、GitHub に届く | 再起動して SSH でディスクを解除し、ログイン画面のまま別の端末から `ssh <マシン名>` して、`systemctl --user status task-hub-watch` が `active`、`systemctl --user show task-hub-watch -p Environment -p EnvironmentFiles` に `GH_TOKEN` かそのファイルが出る(または `gh auth status` が `hosts.yml` を使っている)こと、さらに 2 分ほど待って `tail ~/.local/state/task-hub/watch.err.log` に新しい認証エラー(`gh auth login`、`HTTP 401` など)が出ていないこと。`systemctl status` だけでは足りない(SSH ログインでも keyring は開かないので、SSH 上の `gh auth status` は `GH_TOKEN` を渡さないと失敗する。それで正常) |
| tailnet 経由の SSH | スマホ / ノート PC から `ssh <user>@<マシン名>`。LAN の IP(`192.168.0.99:22`)には届かないこと |
| SSH でのロック解除 | 有線をつないで再起動し、`ssh -p 2222 root@<LAN の IP>` でパスフレーズを入力 |
| キーボードでのロック解除 | 再起動し、Air75 でパスフレーズを入力 |

`scripts/setup_always_on.sh status` で、入っている設定を一覧できる。

## 元に戻す・復旧

### 1 ステップずつ戻す

```bash
scripts/setup_always_on.sh undo initramfs  # encrypt に戻し、initramfs を作り直す(/etc/dropbear-initramfs の鍵は残す)。失敗したら原因を直してもう一度
scripts/setup_always_on.sh undo ssh        # ufw のルールと sshd の設定を消し、sshd を止める
scripts/setup_always_on.sh undo idle       # サスペンドを再び許可
sudo loginctl disable-linger "$USER"       # linger を止める
rm -f ~/.config/systemd/user/task-hub-watch.service.d/gh-token.conf ~/.config/task-hub/gh-token.env  # GH_TOKEN の方法を使った場合
sudo systemctl disable --now tailscaled && sudo pacman -Rns tailscale
```

### initramfs が壊れて起動しないとき

1. **Limine のメニューで古いスナップショットを選ぶ**: Omarchy は Limine にスナップショットの起動項目を並べる。変更前の項目から起動し、上の `undo initramfs` を実行する
2. **それでも駄目なら Arch / Omarchy のインストール USB から起動して chroot する**:

   ```bash
   cryptsetup open /dev/disk/by-partuuid/73140e67-a629-4ce5-90fb-6c50d97ae437 root  # パーティションは lsblk で確認
   mount -o subvol=@ /dev/mapper/root /mnt
   arch-chroot /mnt
   mount -a                                      # /boot(ESP)を含めて fstab の通りにマウント
   rm /etc/mkinitcpio.conf.d/zz_remote_unlock.conf /etc/limine-entry-tool.d/remote-unlock.conf
   limine-mkinitcpio                             # 元の encrypt フックで initramfs と Limine の項目を作り直す
   exit; reboot
   ```

3. Bluetooth キーボードが効かないときは、USB の有線キーボードでも同じ入力欄に打てる(`keyboard` フックは残っている)

## 既知の問題と対処法

- **SSH 解除で接続できない**: 有線がつながっているか、ルーターの DHCP で IP が変わっていないかを確認。マシンの前で起動メッセージ(`quiet splash` を外すと見える)に `IP-Config:` の行が出ているかを見る
- **"REMOTE HOST IDENTIFICATION HAS CHANGED"**: 2222 番では initramfs 専用鍵、22 番では本体の鍵が出る。同じポートで警告が出たら、上のトレードオフの通りパスフレーズを入れずに原因を調べる
- **`unlock-sshd: ... is missing` で initramfs の作成が失敗する**: `/etc/dropbear-initramfs/` の鍵が消えている。`scripts/setup_always_on.sh initramfs` で作り直す

## 公式ドキュメント

- dm-crypt のリモート解除: <https://wiki.archlinux.org/title/Dm-crypt/Specialties#Remote_unlocking_of_root_(or_other)_partition>
- mkinitcpio-utils(encryptssh): <https://github.com/grazzolini/mkinitcpio-utils>
- mkinitcpio-netconf: <https://github.com/grazzolini/mkinitcpio-netconf>
- systemd-sleep.conf: <https://man.archlinux.org/man/systemd-sleep.conf.5>
- Tailscale on Arch: <https://wiki.archlinux.org/title/Tailscale>
- Limine の起動項目(limine-entry-tool): `/usr/share/doc/limine-entry-tool/README.md`
