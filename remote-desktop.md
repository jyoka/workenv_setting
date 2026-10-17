# iPhone / iPad からのリモートデスクトップ(wayvnc + Tailscale)

Linux 機(Omarchy、Hyprland / Wayland)のデスクトップを、iPhone / iPad から Tailscale 経由で見て操作するための設定(2026-10-17)。Mac 専用の Saffsanity/sill(ScreenCaptureKit で Mac のウィンドウを iPhone に映す)の代わり。[常時稼働マシン](./always-on.md) の Tailscale と ufw の上に乗せる。

## 目的とよくある使い方

- 外出先の iPhone から、herdr で動いている task-hub のエージェントの様子をデスクトップごと見る・操作する
- 画面は物理モニターと同じものが映る(ミラー)。別のデスクトップが増えるわけではない
- ターミナルだけで足りるときは、下の「ターミナルだけ使う」の SSH + herdr の方が軽い

## なぜ wayvnc か

| 候補 | 判断 |
|:--|:--|
| **wayvnc**(採用) | wlroots 系のコンポジター向けの VNC サーバー。Arch の公式リポ(`extra/wayvnc` 0.10.1)にある。Hyprland 0.56.2 のバイナリには、wayvnc が使う画面取り込み(`ext_image_copy_capture_manager_v1`、旧 `zwlr_screencopy_manager_v1`)と入力(`zwlr_virtual_pointer_manager_v1`、`zwp_virtual_keyboard_manager_v1`)のプロトコルが全部入っている(`strings /usr/bin/Hyprland` で確認)。RSA-AES 認証を iOS の Screens 5 が使える(RealVNC Viewer も使えると思われるが未確認) |
| gnome-remote-desktop / KRdp(RDP) | GNOME / KDE 専用で、Hyprland では動かない |
| Sunshine + Moonlight | 動画ストリーミング(H.264 / HEVC)で滑らかだが、ゲーム向けで重い。入力に uinput(root 相当の権限)が要り、AUR になる。デスクトップを見て少し操作する用途には過剰 |
| xdg-desktop-portal 経由の画面共有 | 共有のたびに画面上での許可が要るので、無人では使えない |

## セットアップ

前提: [`scripts/setup_always_on.sh tailscale`](./always-on.md#セットアップ) が済んでいて(`tailscale ip -4` が `100.x.y.z` を返す)、ufw が有効。

Linux 機でリポのルートから、Hyprland にログインした状態のターミナルで実行する(`sudo` がパスワードを聞く):

```bash
scripts/setup_remote_desktop.sh           # wayvnc を入れて設定し、起動する
scripts/setup_remote_desktop.sh status    # 何が入っているかの確認だけ(変更しない)
scripts/setup_remote_desktop.sh password  # iPhone に入れるユーザー名とパスワードを表示
```

何度実行してもよい。鍵とパスワードは最初の 1 回だけ作り、以後は残す。設定ファイルとユニットは中身が違うときだけ書き換え、そのときだけ wayvnc を再起動する。やること:

| やること | 置くファイル |
|:--|:--|
| `wayvnc` を pacman で入れる | — |
| RSA-AES 用の RSA 鍵、VeNCrypt(TLS)用の自己署名証明書を作る(mode 600) | `~/.config/wayvnc/rsa_key.pem`、`tls_key.pem`、`tls_cert.pem` |
| ランダムなパスワードを作り、Tailscale の IP だけで待ち受ける設定を書く(mode 600) | `~/.config/wayvnc/config` |
| Hyprland のセッションと一緒に起動する systemd ユーザーユニットを入れて有効化 | `~/.config/systemd/user/wayvnc.service`(実物は [`config/linux/remote-desktop/`](./config/linux/remote-desktop/)) |
| ufw で `tailscale0` からの 5900 番だけ許可 | — |
| 待ち受けが Tailscale の IP だけか `ss -ltn` で確かめ、違えばエラーで止まる | — |

ポートを変えるときは `VNC_PORT=5901 scripts/setup_remote_desktop.sh`(`undo` にも同じものを付ける)。

## 設定の詳細

### Tailscale の IP だけで待ち受ける

`~/.config/wayvnc/config` の `address=` に、セットアップ時の `tailscale ip -4` を書く。`0.0.0.0` にはしない。さらに ufw で `tailscale0` から来た 5900 番だけを許可する。Linux は、自分の IP 宛てのパケットならどの NIC で受けても受け取る(weak host model)ので、LAN の機器が `100.x.y.z` 宛てのパケットをこのマシンに直接送ると届いてしまう。ufw の既定の拒否がそれを落とす。

Tailscale の IP はマシンごとに固定で、普段は変わらない。マシンを tailnet から消して入れ直したなどで変わったら、スクリプトをもう一度実行する(`address=` を書き換えて再起動する)。

確認:

```bash
ss -ltnp 'sport = :5900'   # 100.x.y.z:5900 の 1 行だけ。0.0.0.0:5900 や *:5900 があってはいけない
sudo ufw status | grep 5900  # 5900/tcp on tailscale0 ALLOW IN だけ
```

### 認証

`enable_auth=true`、`relax_encryption=false`(認証後も暗号化を必須にする)。クライアントが次のどちらかを選ぶ:

- **RSA-AES**(`rsa_private_key_file`): ユーザー名とパスワードで認証し、通信は AES で暗号化。サーバーの鍵は初回接続時に覚える方式(TOFU、SSH と同じ)。Screens 5 はこちらを使う。RealVNC Viewer もこちらと思われるが未確認(下の「動作確認」で確かめる)
- **VeNCrypt / TLS**(`private_key_file`、`certificate_file`): 自己署名証明書の TLS の中でユーザー名とパスワードを送る

暗号化のない認証(DES の VNC パスワード、Apple の Diffie-Hellman)は有効にしていない(`allow_broken_crypto`、`relax_encryption` を付けない)。macOS の画面共有は DES しか話さないので、つながらなくてよい。Tailscale(WireGuard)ですでに暗号化されているが、VNC 自体にも暗号化をかけて二重にしている。

ユーザー名は `$USER`、パスワードは `openssl rand` で作った 32 文字。どちらも `~/.config/wayvnc/config`(mode 600、ディレクトリは 700)にだけあり、リポには入らない。iPhone 側のアプリにも保存させる。パスワードを変えるときは、`config` の `password=` 行を消してスクリプトをもう一度実行する(新しいパスワードを作る)。

### セッションと一緒に起動する

Hyprland の `autostart.lua`(`exec-once` 相当)ではなく、systemd のユーザーユニットにした。Omarchy は Hyprland を uwsm で起動していて、ログインすると `graphical-session.target` が上がり、`WAYLAND_DISPLAY` がユーザーの systemd に渡される。ユニットは `WantedBy=graphical-session.target`、`PartOf=graphical-session.target` なので、Hyprland と一緒に起動・終了する。`systemctl --user status wayvnc` / `journalctl --user -u wayvnc` で様子が見え、落ちても 10 秒ごとに起動し直す(起動直後で `tailscale0` にまだ IP がないときも、付くまで待つ)。Omarchy が管理する Hyprland の設定ファイルには触らない。

linger(常時稼働マシンの設定)でユーザーの systemd はログインなしでも動くが、`graphical-session.target` はログインしないと上がらないので、wayvnc はログインするまで動かない(下の「制限」)。

ポインターは `--render-cursor` で画面に描き込む(付けないと iPhone にカーソルが出ない)。

## iPhone / iPad の設定

### おすすめのクライアント

| アプリ | 料金 | 認証 | メモ |
|:--|:--|:--|:--|
| **Screens 5**(Edovia) | サブスクリプション(試用あり) | RSA-AES | App Store の説明に「WayVNC の RSA-AES 認証に対応」とある。Tailscale との連携、トラックパッド風の操作、iPad のマウス・キーボードに対応 |
| **RealVNC Viewer** | 無料 | RSA-AES(と思われる) | Raspberry Pi OS(Bookworm 以降は wayvnc)への接続で広く使われている。アカウントなしで、アドレス直打ちで使える |
| Jump Desktop | 買い切り | VeNCrypt / TLS(と思われる) | VNC の TLS に対応とあるが、wayvnc との組み合わせは未確認 |

どれも未検証(下の「動作確認」で確かめる)。Screens 5 か RealVNC Viewer から試す。

### つなぎ方

1. iPhone に **Tailscale** アプリを入れ、Linux 機と同じ tailnet にログインして VPN をオンにする
2. Linux 機で `scripts/setup_remote_desktop.sh password` を実行し、ユーザー名とパスワードを控える(`status` の `tailscale ip` がアドレス)
3. VNC アプリで新しい接続を作る
   - アドレス: `100.x.y.z`(Tailscale の IP)、または MagicDNS の名前(`omarchy` など、`uname -n` の名前)。ポート `5900`
   - 認証: ユーザー名とパスワード(Screens では「ユーザー名とパスワード」、RealVNC Viewer では接続時に聞かれる)
4. 初回はサーバーの鍵(RSA-AES)または証明書(TLS)を信頼するか聞かれる。「信頼する」で覚えさせる。**以後、鍵が変わったという警告が出たら接続しない**(鍵は `~/.config/wayvnc/` を消さない限り変わらない)
5. 画質や操作が重いときは、アプリ側で画質(色数)を下げる。wayvnc 側の上限は 30 fps(`-f` で変更可)

## 制限

- **Hyprland にログインしている必要がある**: wayvnc はログイン中の Hyprland の画面を映すので、SDDM のログイン画面や LUKS のパスフレーズ入力は映らない。再起動後は、まず LUKS を解除する(キーボード、または [SSH でのロック解除](./always-on.md#ssh-でのロック解除initramfs)、LAN の中からだけ)
  - 今の SDDM は **自動ログイン** になっている(`/etc/sddm.conf.d/autologin.conf` の `[Autologin] User=joka`、`Session=omarchy.desktop`)。LUKS を解除すればそのまま Hyprland が起動し、wayvnc も起動する。つまり SSH でディスクを解除したあと、iPhone からデスクトップに入れる
  - トレードオフ: 自動ログインでは、LUKS のパスフレーズがログインパスワードの代わりになる。解除後のマシンの前にいる人は、ロックされるまでデスクトップを使える。自動ログインを切る(`autologin.conf` を消す)と、再起動のたびにマシンの前でのログインが要り、リモートからは wayvnc が使えなくなる(SSH は使える)
- **ロック中はロック画面が映る**: Omarchy の画面ロックは hyprlock ではなく Omarchy シェル(Quickshell、`omarchy-shell lock`)で、放置 300 秒(`~/.config/omarchy/shell.json` の `idle.lock`)でロックされる。VNC にはロック画面が映り、パスワード(PAM、ログインのパスワード)を入れて解除する。VNC の仮想キーボードでロック画面に入力できるか、画面が消灯(DPMS オフ)しているときに VNC から復帰できるかは未確認(下の「動作確認」)。駄目なときは SSH から `hyprctl dispatch dpms on` で画面をつける
- **iPhone に映る画面は物理モニターにも映る**: マシンの前にいる人には、iPhone での操作が全部見える
- **複数モニター**: wayvnc は 1 つのモニター(既定は最初のもの)だけを映す。今は `HDMI-A-1` だけ。モニターを増やしたら:
  - その場で切り替え: `wayvncctl output-list`、`wayvncctl output-cycle`、`wayvncctl output-set HDMI-A-2`(SSH から)
  - 決めておく: `systemctl --user edit wayvnc` で次を書き、`systemctl --user restart wayvnc`

    ```ini
    [Service]
    Environment="WAYVNC_EXTRA_ARGS=--output=HDMI-A-2"
    ```

- **キーボード配列**: 記号がずれるときは、`~/.config/wayvnc/config` の末尾に `xkb_layout=us`(または `jp`)を足して `systemctl --user restart wayvnc`。スクリプトをもう一度実行しても `xkb_` の行は残る
- **音は出ない**: VNC は画面と入力だけ

## ターミナルだけ使う(SSH + herdr)

エージェントの様子を見る・指示するだけなら、VNC より SSH の方が軽く、通信が細くても使える。[常時稼働マシンの `ssh` ステップ](./always-on.md#リモートアクセスtailscale--openssh) で、OpenSSH が `tailscale0` だけで鍵認証で待ち受けている。ログインしていなくても(LUKS を解除しただけで)使える。

1. iPhone に **Blink Shell** か **Termius** を入れ、アプリで鍵を作る。公開鍵を Linux 機の `~/.ssh/authorized_keys` に足す
2. Tailscale アプリをオンにして、`ssh joka@<マシン名>`(MagicDNS)か `ssh joka@100.x.y.z` でつなぐ
3. herdr のセッションにアタッチする:

   ```bash
   herdr                       # 永続セッションにアタッチ(なければ作る)
   herdr session attach NAME   # 名前付きセッションに
   ```

   Blink は Mosh にも対応していて、電波が切れても接続が戻る(Linux 機に `mosh` を入れ、ufw で `tailscale0` の UDP 60000-61000 を開ける必要がある。今回はやっていない)。herdr 自体の詳しい操作は [Herdr](./herdr.md#コマンドと使い方) を参照。

## 動作確認

| 確認すること | 方法 |
|:--|:--|
| Tailscale の IP だけで待ち受けている | `ss -ltnp 'sport = :5900'` が `100.x.y.z:5900` の 1 行だけで、`users:(("wayvnc",...))` が出ること。`scripts/setup_remote_desktop.sh status` の `listening on` も同じ |
| LAN からは届かない | 同じ LAN の別の端末(Tailscale オフ)から `nc -vz <LAN の IP> 5900` が失敗すること |
| 認証が要る | VNC アプリでパスワードを間違えると拒否されること。認証なし(None)では接続できないこと |
| **iPhone から Tailscale 経由でつながる(手作業)** | iPhone の Wi-Fi を切ってモバイル回線にし、Tailscale をオン、上の「つなぎ方」で接続。デスクトップが映り、タップ・ドラッグ・文字入力が効くこと |
| ロック画面の解除 | `omarchy system lock` でロックし、iPhone からパスワードを入れて解除できること。消灯後に VNC から触って画面が戻ること |
| 再起動後に自動で起動する | 再起動して LUKS を解除し(自動ログイン)、何も操作せずに iPhone から接続できること。`systemctl --user is-active wayvnc` が `active` |

## 元に戻す

```bash
scripts/setup_remote_desktop.sh undo   # wayvnc を止め、ユニットと ufw のルールを消す(鍵とパスワードは残す)
rm -r ~/.config/wayvnc                  # 鍵とパスワードも消す(iPhone 側の接続設定も消す)
sudo pacman -Rns wayvnc                 # パッケージも消す
rm -r ~/.config/systemd/user/wayvnc.service.d  # systemctl --user edit で作った上書きがあれば
```

`undo` のあとは 5900 番で何も待ち受けていないこと(`ss -ltn 'sport = :5900'` が空)を確かめる。Tailscale と SSH は [常時稼働マシン](./always-on.md#元に戻す復旧) の設定なので、ここでは触らない。

## 既知の問題と対処法

- **接続できない**: `systemctl --user status wayvnc` と `journalctl --user -u wayvnc -n 50` を見る。bind に失敗したログが続くなら `tailscale ip -4` と `config` の `address=` が一致しているか確認し、違えばスクリプトをもう一度実行する。iPhone の Tailscale がオンかも確認する
- **`... was skipped because of an unmet condition check (ConditionPathExists=...)`**: `~/.config/wayvnc/config` がない。スクリプトを実行する
- **ログインしたのに起動しない**: `systemctl --user is-active graphical-session.target` が `active` か確認(uwsm を使わずに Hyprland を起動すると上がらない)
- **「セキュリティの種類が対応していない」と言われる**: そのアプリが RSA-AES も VeNCrypt も話せない。暗号化のない方式は有効にしないので、Screens 5 か RealVNC Viewer を使う
- **カーソルが二重に見える**: アプリ側の「ローカルカーソルを表示」を切る

## 公式ドキュメント

- wayvnc: <https://github.com/any1/wayvnc>(`man wayvnc`、`man wayvncctl`)
- uwsm と `graphical-session.target`: <https://github.com/Vladimir-csp/uwsm>
- Tailscale on Arch: <https://wiki.archlinux.org/title/Tailscale>
- Screens 5: <https://apps.apple.com/app/id1663047912>
- Blink Shell: <https://blink.sh/>
