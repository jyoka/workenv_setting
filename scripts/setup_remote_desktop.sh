#!/bin/bash
# See and control the Hyprland desktop from an iPhone / iPad over Tailscale (see remote-desktop.md).
# Run on the Omarchy machine from the repo root, in a terminal (sudo asks for the password),
# after `scripts/setup_always_on.sh tailscale`:
#
#   scripts/setup_remote_desktop.sh           # install and configure wayvnc
#   scripts/setup_remote_desktop.sh status    # show what is in place, change nothing
#   scripts/setup_remote_desktop.sh password  # print the VNC user name and password
#   scripts/setup_remote_desktop.sh undo      # stop wayvnc, remove the unit and the ufw rule
#
# Safe to run again: keys and the password are generated once and kept; the config and the unit
# are only rewritten when they differ, and wayvnc is only restarted when one of them changed.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO/config/linux/remote-desktop"
CONF_DIR="$HOME/.config/wayvnc"
CONF="$CONF_DIR/config"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT=wayvnc.service
VNC_PORT="${VNC_PORT:-5900}"

changed=0

say() { printf '==> %s\n' "$*"; }
warn() { printf '==> WARNING: %s\n' "$*" >&2; }
die() {
  printf '==> ERROR: %s\n' "$*" >&2
  exit 1
}

need_pkgs() {
  local missing=()
  for p in "$@"; do
    pacman -Q "$p" &>/dev/null || missing+=("$p")
  done
  if ((${#missing[@]})); then
    sudo pacman -S --needed --noconfirm "${missing[@]}"
  fi
}

# write_if_changed <tmp> <dest>: move tmp over dest (mode 600) only when the content differs.
write_if_changed() {
  local tmp="$1" dest="$2"
  if [[ -f $dest ]] && cmp -s "$tmp" "$dest"; then
    rm -f "$tmp"
    return 0
  fi
  install -Dm600 "$tmp" "$dest"
  rm -f "$tmp"
  say "wrote $dest"
  changed=1
}

# conf_value <key>: the value of key= in the current config, or nothing.
conf_value() {
  [[ -f $CONF ]] || return 0
  sed -n "s/^$1=//p" "$CONF" | tail -n1
}

# Never fails: prints nothing when tailscale is missing or logged out, so callers can report it.
tailscale_ip() {
  { tailscale ip -4 2>/dev/null || true; } | head -n1
}

# Keys are generated once and never overwritten: clients pin them on first connect (TOFU).
make_keys() {
  install -dm700 "$CONF_DIR"
  if [[ ! -s $CONF_DIR/rsa_key.pem ]]; then
    (umask 077 && ssh-keygen -q -m pem -t rsa -b 3072 -N '' -C wayvnc -f "$CONF_DIR/rsa_key.pem")
    rm -f "$CONF_DIR/rsa_key.pem.pub"
    say "generated $CONF_DIR/rsa_key.pem (RSA-AES)"
    changed=1
  fi
  if [[ ! -s $CONF_DIR/tls_key.pem || ! -s $CONF_DIR/tls_cert.pem ]]; then
    (umask 077 && openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:secp384r1 -sha384 \
      -days 3650 -nodes -keyout "$CONF_DIR/tls_key.pem" -out "$CONF_DIR/tls_cert.pem" \
      -subj "/CN=$(uname -n)" -addext "subjectAltName=DNS:$(uname -n),IP:$1" 2>/dev/null)
    say "generated $CONF_DIR/tls_key.pem and tls_cert.pem (VeNCrypt TLS)"
    changed=1
  fi
  chmod 600 "$CONF_DIR"/rsa_key.pem "$CONF_DIR"/tls_key.pem "$CONF_DIR"/tls_cert.pem
}

# The config holds the password, so it is generated here (never in the repo) with mode 600.
# An existing password and any xkb_* lines added by hand are kept; the address follows the
# current Tailscale IP.
write_config() {
  local ip="$1" user password tmp
  user="$(conf_value username)"
  user="${user:-$USER}"
  password="$(conf_value password)"
  if [[ -z $password ]]; then
    password="$(openssl rand -base64 48 | tr -d '/+=\n' | cut -c1-32)"
    say "generated a new VNC password (show it with: $0 password)"
  fi
  tmp="$(mktemp)"
  cat >"$tmp" <<EOF
# Written by scripts/setup_remote_desktop.sh (workenv_setting). Mode 600: holds the password.
# address is the Tailscale IP only; never 0.0.0.0. Re-run the script if the IP changes.
address=$ip
port=$VNC_PORT
enable_auth=true
username=$user
password=$password
rsa_private_key_file=$CONF_DIR/rsa_key.pem
private_key_file=$CONF_DIR/tls_key.pem
certificate_file=$CONF_DIR/tls_cert.pem
relax_encryption=false
EOF
  [[ -f $CONF ]] && grep '^xkb_' "$CONF" >>"$tmp" || true
  write_if_changed "$tmp" "$CONF"
}

# listeners: wayvnc's listening sockets as "address:port", one per line.
listeners() {
  ss -Hltn "sport = :$VNC_PORT" 2>/dev/null | awk '{print $4}'
}

# Fail loudly if wayvnc listens anywhere but the Tailscale IP.
check_listen() {
  local ip="$1" l i bad=0 seen=0
  for i in $(seq 1 15); do
    [[ -n $(listeners) ]] && break
    sleep 1
  done
  while read -r l; do
    [[ -n $l ]] || continue
    seen=1
    if [[ $l != "$ip:$VNC_PORT" ]]; then
      warn "something listens on $l, not only on the Tailscale IP"
      bad=1
    fi
  done < <(listeners)
  if ((!seen)); then
    warn "nothing listens on port $VNC_PORT yet: journalctl --user -u $UNIT -n 30"
  elif ((!bad)); then
    say "wayvnc listens on $ip:$VNC_PORT only:"
    ss -Hltnp "sport = :$VNC_PORT"
  else
    die "port $VNC_PORT is open beyond tailscale0; see the warnings above"
  fi
}

setup() {
  local ip
  ip="$(tailscale_ip)"
  [[ $ip == 100.* ]] || die "no Tailscale IPv4 address; run scripts/setup_always_on.sh tailscale first"
  need_pkgs wayvnc openssl openssh
  if ! sudo ufw status | grep -q '^Status: active'; then
    die "ufw is not active, so a LAN host could reach the VNC port through this machine. Turn it on first: sudo ufw enable"
  fi

  make_keys "$ip"
  write_config "$ip"

  install -dm755 "$UNIT_DIR"
  if ! cmp -s "$SRC/systemd/user/$UNIT" "$UNIT_DIR/$UNIT" 2>/dev/null; then
    install -m644 "$SRC/systemd/user/$UNIT" "$UNIT_DIR/$UNIT"
    say "wrote $UNIT_DIR/$UNIT"
    changed=1
  fi
  systemctl --user daemon-reload
  systemctl --user enable "$UNIT"

  # Defense in depth: even bound to the Tailscale IP, Linux would accept a packet for that IP on
  # the LAN NIC. ufw's default deny drops it; only tailscale0 may reach the port. Safe to repeat.
  sudo ufw allow in on tailscale0 to any port "$VNC_PORT" proto tcp comment 'wayvnc-over-tailscale'

  if systemctl --user is-active -q graphical-session.target; then
    if ((changed)); then
      systemctl --user restart "$UNIT"
    else
      systemctl --user start "$UNIT"
    fi
    check_listen "$ip"
  else
    say "no Hyprland session is running; wayvnc starts with the next login"
  fi
  say "connect from the iPhone to $ip:$VNC_PORT (or $(uname -n):$VNC_PORT with MagicDNS)"
}

undo() {
  systemctl --user disable --now "$UNIT" 2>/dev/null || true
  if [[ -e $UNIT_DIR/$UNIT ]]; then
    rm -f "$UNIT_DIR/$UNIT"
    say "removed $UNIT_DIR/$UNIT"
  fi
  systemctl --user daemon-reload
  sudo ufw delete allow in on tailscale0 to any port "$VNC_PORT" proto tcp || true
  say "kept $CONF_DIR (keys and password); delete it by hand if you are done: rm -r $CONF_DIR"
  say "the wayvnc package stays installed: sudo pacman -Rns wayvnc"
}

status() {
  local ip
  ip="$(tailscale_ip)"
  printf 'wayvnc package:    %s\n' "$(pacman -Q wayvnc 2>/dev/null || echo missing)"
  printf 'tailscale ip:      %s\n' "${ip:-none}"
  printf 'config address:    %s\n' "$(conf_value address || true)"
  printf 'config mode:       %s\n' "$(stat -c %a "$CONF" 2>/dev/null || echo missing)"
  printf 'unit enabled:      %s\n' "$(systemctl --user is-enabled "$UNIT" 2>/dev/null || true)"
  printf 'unit active:       %s\n' "$(systemctl --user is-active "$UNIT" 2>/dev/null || true)"
  printf 'ufw vnc rule:      %s\n' "$(sudo ufw status | grep -q "^$VNC_PORT/tcp on tailscale0" && echo tailscale0 || echo missing)"
  printf 'listening on:      %s\n' "$(listeners | paste -sd' ' -)"
}

password() {
  [[ -f $CONF ]] || die "$CONF does not exist yet; run $0 first"
  printf 'user:     %s\n' "$(conf_value username)"
  printf 'password: %s\n' "$(conf_value password)"
}

main() {
  [[ $EUID -ne 0 ]] || die "run as your own user; the script calls sudo where it needs to"
  case "${1:-}" in
    '') setup ;;
    status) status ;;
    password) password ;;
    undo) undo ;;
    *) die "usage: $0 [status | password | undo]" ;;
  esac
}

main "$@"
