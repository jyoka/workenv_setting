#!/bin/bash
# Make the Omarchy machine an always-on host for task-hub (see always-on.md).
# Run on the Omarchy machine from the repo root, in a terminal (sudo asks for the password):
#
#   scripts/setup_always_on.sh                 # every step, in order
#   scripts/setup_always_on.sh idle linger     # only these steps
#   scripts/setup_always_on.sh status          # show what is in place, change nothing
#   scripts/setup_always_on.sh undo initramfs  # roll one step back (idle | ssh | initramfs)
#
# Steps: idle linger tailscale ssh initramfs. Every step is safe to run again: files are only
# rewritten when they differ, and the initramfs is only rebuilt when one of its inputs is newer
# than the last successful build (so a failed rebuild is retried on the next run).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO/config/linux/always-on"
UNLOCK_DIR=/etc/dropbear-initramfs
# Written after limine-mkinitcpio succeeds; inputs newer than this mean the image is stale.
UNLOCK_STAMP="$UNLOCK_DIR/initramfs-built.stamp"
# Kernel `ip=` for the initramfs network (mkinitcpio-netconf). The initramfs has no udev
# net-naming rules, so the wired NIC is eth0 there, not eno1. Name the device: netconf only
# takes down (before switch_root) the device in field 6, and plain `dhcp` has none.
UNLOCK_IP="${UNLOCK_IP:-:::::eth0:dhcp}"
UNLOCK_KEYS="${UNLOCK_KEYS:-$HOME/.ssh/authorized_keys}"

changed=0

say() { printf '==> %s\n' "$*"; }
warn() { printf '==> WARNING: %s\n' "$*" >&2; }
die() {
  printf '==> ERROR: %s\n' "$*" >&2
  exit 1
}

# install_file <src> <dest> [mode]: copy only when the content differs; sets changed=1.
install_file() {
  local src="$1" dest="$2" mode="${3:-644}"
  if sudo test -f "$dest" && sudo cmp -s "$src" "$dest"; then
    return 0
  fi
  sudo install -Dm"$mode" "$src" "$dest"
  say "wrote $dest"
  changed=1
}

# remove_file <dest>: delete if present; sets changed=1.
remove_file() {
  if sudo test -e "$1"; then
    sudo rm -f "$1"
    say "removed $1"
    changed=1
  fi
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

step_idle() {
  say "idle: never suspend or hibernate; the screensaver and lock stay as they are"
  install_file "$SRC/systemd/sleep.conf.d/always-on.conf" /etc/systemd/sleep.conf.d/always-on.conf
  install_file "$SRC/systemd/logind.conf.d/always-on.conf" /etc/systemd/logind.conf.d/always-on.conf
  # sleep.conf is read on every sleep request; logind reads its drop-in at the next boot.
  if omarchy-toggle-idle status 2>/dev/null | grep -q '"enabled":true'; then
    warn "Omarchy 'Stay Awake' is on, so the screen will not lock. Turn it off: omarchy toggle idle allow-idle"
  fi
}

step_linger() {
  say "linger: start $USER's user services at boot, without a login"
  if [[ $(loginctl show-user "$USER" -p Linger --value 2>/dev/null) != yes ]]; then
    sudo loginctl enable-linger "$USER"
  fi
  if systemctl --user cat task-hub-watch.service &>/dev/null; then
    systemctl --user enable task-hub-watch.service
  else
    warn "task-hub-watch.service is not installed for $USER yet; linger is on, enable the unit when it is"
  fi
  watch_token_check
}

# With nobody logged in, gnome-keyring stays locked, so gh's keyring token is unreadable.
# The watcher needs a token from GH_TOKEN (an EnvironmentFile= drop-in) or hosts.yml.
watch_token_check() {
  local hosts="${GH_CONFIG_DIR:-$HOME/.config/gh}/hosts.yml" env f
  if [[ -f $hosts ]] && grep -q 'oauth_token:' "$hosts"; then
    say "gh token is in $hosts: the watcher can use it without a login"
    return 0
  fi
  env="$(systemctl --user show task-hub-watch.service -p Environment --value 2>/dev/null || true)"
  if [[ $env == *GH_TOKEN=* ]]; then
    say "task-hub-watch.service sets GH_TOKEN"
    return 0
  fi
  while read -r f; do
    f="${f#-}"
    if [[ -n $f && -r $f ]] && grep -q '^GH_TOKEN=.' "$f"; then
      say "task-hub-watch.service reads GH_TOKEN from $f"
      return 0
    fi
  done < <(systemctl --user show task-hub-watch.service -p EnvironmentFiles --value 2>/dev/null |
    tr ' ' '\n' | grep '^-\?/' || true)
  warn "the gh token is only in gnome-keyring, which stays locked until someone logs in."
  warn "  Without a login, every 'task watch' cycle fails to call gh (see always-on.md, linger section)."
}

step_tailscale() {
  say "tailscale: install, enable, and log in"
  need_pkgs tailscale
  sudo systemctl enable --now tailscaled.service
  if ! tailscale status &>/dev/null; then
    say "open the login URL below on any device (then disable key expiry for this machine in the admin console)"
    sudo tailscale up
  fi
  tailscale ip -4
}

step_ssh() {
  say "ssh: OpenSSH with keys only, reachable over tailscale0 only"
  need_pkgs openssh
  if ! sudo ufw status | grep -q '^Status: active'; then
    die "ufw is not active, so sshd would be open to the whole LAN. Turn it on first: sudo ufw enable"
  fi
  if [[ ! -s $HOME/.ssh/authorized_keys ]]; then
    warn "$HOME/.ssh/authorized_keys is empty: add the phone/laptop public keys, or SSH will refuse every login"
  fi
  install_file "$SRC/ssh/sshd_config.d/10-always-on.conf" /etc/ssh/sshd_config.d/10-always-on.conf
  sudo sshd -t
  # ufw skips a rule that already exists, so this is safe to repeat.
  sudo ufw allow in on tailscale0 to any port 22 proto tcp comment 'ssh-over-tailscale'
  sudo systemctl enable sshd.service
  if ((changed)); then
    sudo systemctl restart sshd.service
  else
    sudo systemctl start sshd.service
  fi
}

step_initramfs() {
  say "initramfs: SSH (dropbear, port 2222) at the LUKS prompt; the keyboard prompt stays"
  [[ -s $UNLOCK_KEYS ]] || die "$UNLOCK_KEYS is empty: these keys may unlock the disk. Set UNLOCK_KEYS=<file> or fill it first"
  sudo test -s /etc/mkinitcpio.conf.d/zz_bluetooth.conf ||
    warn "/etc/mkinitcpio.conf.d/zz_bluetooth.conf is missing: the Bluetooth keyboard will not work at the prompt"
  need_pkgs dropbear psmisc mkinitcpio-netconf mkinitcpio-utils

  # Host key for the initramfs only: never the main sshd's (it would sit unencrypted on the ESP).
  if ! sudo test -s "$UNLOCK_DIR/dropbear_ed25519_host_key"; then
    sudo install -dm700 "$UNLOCK_DIR"
    sudo dropbearkey -t ed25519 -f "$UNLOCK_DIR/dropbear_ed25519_host_key" >/dev/null
    say "generated $UNLOCK_DIR/dropbear_ed25519_host_key"
    changed=1
  fi
  install_file "$UNLOCK_KEYS" "$UNLOCK_DIR/authorized_keys" 600

  install_file "$SRC/initcpio/install/unlock-sshd" /etc/initcpio/install/unlock-sshd
  install_file "$SRC/initcpio/hooks/unlock-sshd" /etc/initcpio/hooks/unlock-sshd
  install_file "$SRC/mkinitcpio.conf.d/zz_remote_unlock.conf" /etc/mkinitcpio.conf.d/zz_remote_unlock.conf
  # A real file, not <(...): sudo closes inherited file descriptors.
  local cmdline
  cmdline="$(mktemp)"
  printf 'KERNEL_CMDLINE[default]+=" ip=%s netconf_timeout=10"\n' "$UNLOCK_IP" >"$cmdline"
  install_file "$cmdline" /etc/limine-entry-tool.d/remote-unlock.conf
  rm -f "$cmdline"

  # Decide from the stamp, not from this run's diff: if an earlier rebuild failed after the
  # files were written, they now compare equal but are still newer than the stamp.
  if ((changed)) || ! sudo test -f "$UNLOCK_STAMP" ||
    [[ -n $(sudo find "$UNLOCK_DIR" /etc/initcpio/install/unlock-sshd /etc/initcpio/hooks/unlock-sshd \
      /etc/mkinitcpio.conf.d /etc/limine-entry-tool.d -type f -newer "$UNLOCK_STAMP" 2>/dev/null) ]]; then
    say "rebuilding the initramfs and Limine entries"
    sudo limine-mkinitcpio
    sudo touch "$UNLOCK_STAMP"
  else
    say "initramfs is up to date with its inputs; not rebuilding"
  fi
  say "initramfs host key (compare on first connect):"
  sudo dropbearkey -y -f "$UNLOCK_DIR/dropbear_ed25519_host_key" | grep '^Fingerprint'
}

undo() {
  case "${1:-}" in
    idle)
      remove_file /etc/systemd/sleep.conf.d/always-on.conf
      remove_file /etc/systemd/logind.conf.d/always-on.conf
      ;;
    ssh)
      sudo ufw delete allow in on tailscale0 to any port 22 proto tcp || true
      remove_file /etc/ssh/sshd_config.d/10-always-on.conf
      sudo systemctl disable --now sshd.service
      ;;
    initramfs)
      remove_file /etc/mkinitcpio.conf.d/zz_remote_unlock.conf
      remove_file /etc/limine-entry-tool.d/remote-unlock.conf
      remove_file /etc/initcpio/install/unlock-sshd
      remove_file /etc/initcpio/hooks/unlock-sshd
      # The stamp is removed only after a successful rebuild, so a failed undo is retried.
      if ((changed)) || sudo test -f "$UNLOCK_STAMP"; then
        sudo limine-mkinitcpio
        sudo rm -f "$UNLOCK_STAMP"
      fi
      say "kept $UNLOCK_DIR (host key); delete it by hand if you are done with remote unlock"
      ;;
    *) die "undo takes one of: idle ssh initramfs" ;;
  esac
}

status() {
  local f
  printf 'suspend allowed:   %s\n' "$(sudo test -f /etc/systemd/sleep.conf.d/always-on.conf && echo no || echo yes)"
  printf 'omarchy idle:      %s\n' "$(omarchy-toggle-idle status 2>/dev/null || echo unknown)"
  printf 'linger:            %s\n' "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null || echo unknown)"
  printf 'task-hub-watch:    %s\n' "$(systemctl --user is-active task-hub-watch.service 2>/dev/null || true)"
  printf 'tailscaled:        %s\n' "$(systemctl is-active tailscaled.service 2>/dev/null || true)"
  printf 'tailscale ip:      %s\n' "$(tailscale ip -4 2>/dev/null || echo none)"
  printf 'sshd:              %s\n' "$(systemctl is-active sshd.service 2>/dev/null || true)"
  printf 'ufw ssh rule:      %s\n' "$(sudo ufw status | grep -q 'on tailscale0' && echo tailscale0 || echo missing)"
  for f in /etc/mkinitcpio.conf.d/zz_remote_unlock.conf /etc/limine-entry-tool.d/remote-unlock.conf \
    /etc/initcpio/install/unlock-sshd "$UNLOCK_DIR/authorized_keys" "$UNLOCK_DIR/dropbear_ed25519_host_key"; do
    printf 'remote unlock:     %s %s\n' "$(sudo test -s "$f" && echo ok || echo missing)" "$f"
  done
}

main() {
  [[ $EUID -ne 0 ]] || die "run as your own user; the script calls sudo where it needs to"
  if (($# == 0)); then
    set -- idle linger tailscale ssh initramfs
  fi
  case "$1" in
    status) status ;;
    undo) undo "${2:-}" ;;
    *)
      for step in "$@"; do
        case "$step" in
          idle | linger | tailscale | ssh | initramfs)
            changed=0
            "step_$step"
            ;;
          *) die "unknown step: $step (idle linger tailscale ssh initramfs status undo)" ;;
        esac
      done
      ;;
  esac
}

main "$@"
