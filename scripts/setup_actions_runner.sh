#!/bin/bash
# Make the Omarchy machine a self-hosted GitHub Actions runner (see actions-runner.md).
# Run on the Omarchy machine from the repo root, as yourself (not root), in a terminal:
# sudo asks for the password, and `gh` must be logged in with admin access to the repos.
#
#   scripts/setup_actions_runner.sh install               # user, packages, units, runner download
#   scripts/setup_actions_runner.sh add jyoka/some-repo   # register a runner for the repo, start it
#   scripts/setup_actions_runner.sh remove jyoka/some-repo
#   scripts/setup_actions_runner.sh status                # show what is in place, change nothing
#   scripts/setup_actions_runner.sh uninstall             # remove every runner, the units and the user
#
# GitHub has no user-level runners for personal accounts, so each repo gets its own runner
# (directory + systemd instance), all under one unprivileged user and one resource-limited
# slice. Every command is safe to run again. Registration tokens come from `gh api` at run
# time and are passed to the runner through the environment, never through argv or a file.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO/config/linux/actions-runner"
RUNNER_USER=github-runner
RUNNER_HOME=/var/lib/github-runner
RUNNERS="$RUNNER_HOME/runners"
CACHE="$RUNNER_HOME/cache"
UNIT=actions-runner@.service
SLICE=ci.slice
# Extra labels; the runner adds self-hosted, Linux and X64 itself.
RUNNER_LABELS="${RUNNER_LABELS:-omarchy}"
RUNNER_NAME="${RUNNER_NAME:-$(hostname)}"

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

# Run from / so the runner user never needs access to the caller's working directory.
as_runner() { (cd / && sudo -u "$RUNNER_USER" -H "$@"); }

# runner_write <file> <content>: write a file as the runner user only when it differs;
# sets runner_changed=1.
runner_write() {
  if [[ $(as_runner cat "$1" 2>/dev/null) != "$2" ]]; then
    as_runner bash -c 'printf "%s\n" "$2" >"$1"' _ "$1" "$2"
    runner_changed=1
  fi
}

daemon_reload() {
  if ((changed)); then
    sudo systemctl daemon-reload
    changed=0
  fi
}

# slug_check <owner/repo>: sets OWNER, NAME, INSTANCE and DIR.
slug_check() {
  [[ ${1:-} =~ ^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$ ]] || die "expected owner/repo, got '${1:-}'"
  OWNER="${BASH_REMATCH[1]}"
  NAME="${BASH_REMATCH[2]}"
  INSTANCE="${OWNER}__${NAME}"
  DIR="$RUNNERS/$INSTANCE"
}

need_gh() {
  command -v gh >/dev/null || die "gh is not on PATH"
  gh auth status &>/dev/null || die "gh is not logged in (gh auth login)"
}

# latest_tarball: download the newest actions/runner release into the cache if it is not
# there yet, check its SHA-256 against the release notes, and print its path.
latest_tarball() {
  local release tag version file sha tmp
  release="$(gh api repos/actions/runner/releases/latest)"
  tag="$(jq -r .tag_name <<<"$release")"
  version="${tag#v}"
  file="$CACHE/actions-runner-linux-x64-$version.tar.gz"
  if sudo test -f "$file"; then
    echo "$file"
    return 0
  fi
  sha="$(jq -r .body <<<"$release" |
    sed -n 's/.*BEGIN SHA linux-x64 -->\([0-9a-f]\{64\}\)<!-- END SHA linux-x64.*/\1/p' | head -n1)"
  [[ -n $sha ]] || die "no linux-x64 SHA-256 in the $tag release notes"
  tmp="$(mktemp -d)"
  say "downloading actions/runner $tag" >&2
  curl -fsSL --retry 3 -o "$tmp/runner.tar.gz" \
    "https://github.com/actions/runner/releases/download/$tag/actions-runner-linux-x64-$version.tar.gz"
  if ! echo "$sha  $tmp/runner.tar.gz" | sha256sum -c --quiet - >&2; then
    rm -rf "$tmp"
    die "SHA-256 mismatch for $tag"
  fi
  sudo install -Dm644 -o "$RUNNER_USER" -g "$RUNNER_USER" "$tmp/runner.tar.gz" "$file"
  rm -rf "$tmp"
  # Keep only the newest tarball; configured runners update themselves in place.
  sudo find "$CACHE" -maxdepth 1 -name 'actions-runner-linux-x64-*.tar.gz' ! -path "$file" -delete
  echo "$file"
}

step_install() {
  say "install: user $RUNNER_USER, packages, systemd units, runner tarball"
  # icu and krb5 are the runner's own (.NET) dependencies; the rest is what jobs commonly need.
  need_pkgs git jq curl tar unzip zip icu krb5 base-devel
  # mise is in extra; mise-bin (AUR) also provides /usr/bin/mise, so only install if neither is there.
  [[ -x /usr/bin/mise ]] || need_pkgs mise

  if ! id "$RUNNER_USER" &>/dev/null; then
    # A system user with no login shell, no sudo, and no supplementary groups (not docker).
    sudo useradd --system --user-group --create-home --home-dir "$RUNNER_HOME" \
      --shell /usr/bin/nologin --comment "GitHub Actions runner" "$RUNNER_USER"
    say "created user $RUNNER_USER (home $RUNNER_HOME)"
  fi
  sudo chmod 750 "$RUNNER_HOME"
  sudo install -d -m750 -o "$RUNNER_USER" -g "$RUNNER_USER" "$RUNNERS" "$CACHE"
  if [[ -n $(id -nG "$RUNNER_USER" | tr ' ' '\n' | grep -vx "$RUNNER_USER") ]]; then
    warn "$RUNNER_USER is in extra groups ($(id -nG "$RUNNER_USER")); docker or wheel would let jobs become root"
  fi

  install_file "$SRC/systemd/$SLICE" "/etc/systemd/system/$SLICE"
  install_file "$SRC/systemd/$UNIT" "/etc/systemd/system/$UNIT"
  daemon_reload

  need_gh
  latest_tarball >/dev/null
}

step_add() {
  slug_check "${1:-}"
  need_gh
  step_install
  say "add: runner for $OWNER/$NAME ($INSTANCE)"

  if sudo test -f "$DIR/.runner"; then
    say "already registered ($DIR/.runner); not registering again"
  else
    local tarball token
    tarball="$(latest_tarball)"
    as_runner mkdir -p "$DIR"
    if ! sudo test -x "$DIR/config.sh"; then
      as_runner tar -xzf "$tarball" -C "$DIR"
    fi
    token="$(gh api -X POST "repos/$OWNER/$NAME/actions/runners/registration-token" --jq .token)" ||
      die "could not get a registration token (do you have admin access to $OWNER/$NAME?)"
    # The token travels on stdin and into ACTIONS_RUNNER_INPUT_TOKEN, so it never shows in `ps`.
    # --replace takes over a runner of the same name left behind by an earlier install.
    as_runner bash -c 'read -r ACTIONS_RUNNER_INPUT_TOKEN; export ACTIONS_RUNNER_INPUT_TOKEN
      cd "$1" && ./config.sh --unattended --replace --url "$2" --name "$3" --labels "$4" --work _work' \
      _ "$DIR" "https://github.com/$OWNER/$NAME" "$RUNNER_NAME" "$RUNNER_LABELS" <<<"$token"
  fi

  # Service wrapper (what svc.sh install does), PATH and env for jobs.
  runner_changed=0
  if ! as_runner cmp -s "$DIR/bin/runsvc.sh" "$DIR/runsvc.sh"; then
    as_runner install -m755 "$DIR/bin/runsvc.sh" "$DIR/runsvc.sh"
    runner_changed=1
  fi
  runner_write "$DIR/.path" "$RUNNER_HOME/.local/share/mise/shims:/usr/local/bin:/usr/bin:/bin"
  # Jobs run `mise install` in fresh checkouts; trust their mise.toml without a prompt.
  if ! as_runner grep -qs '^MISE_TRUSTED_CONFIG_PATHS=' "$DIR/.env"; then
    as_runner bash -c 'echo "MISE_TRUSTED_CONFIG_PATHS=$1" >>"$2/.env"' _ "$RUNNERS" "$DIR"
    runner_changed=1
  fi

  local svc="actions-runner@$INSTANCE.service"
  sudo systemctl enable "$svc"
  if ! systemctl is-active -q "$svc"; then
    sudo systemctl start "$svc"
  elif ((runner_changed)); then
    # Picks up the new settings; a job in progress gets up to TimeoutStopSec to finish.
    sudo systemctl restart "$svc"
  fi
  sleep 5
  gh_status "$OWNER/$NAME"
}

step_remove() {
  slug_check "${1:-}"
  say "remove: runner for $OWNER/$NAME ($INSTANCE)"
  sudo systemctl disable --now "actions-runner@$INSTANCE.service" 2>/dev/null || true
  if sudo test -f "$DIR/.runner"; then
    need_gh
    local token
    if token="$(gh api -X POST "repos/$OWNER/$NAME/actions/runners/remove-token" --jq .token)"; then
      as_runner bash -c 'read -r ACTIONS_RUNNER_INPUT_TOKEN; export ACTIONS_RUNNER_INPUT_TOKEN
        cd "$1" && ./config.sh remove' _ "$DIR" <<<"$token" ||
        warn "deregistering failed; delete the runner by hand: https://github.com/$OWNER/$NAME/settings/actions/runners"
    else
      warn "no remove token; delete the runner by hand: https://github.com/$OWNER/$NAME/settings/actions/runners"
    fi
  fi
  if sudo test -d "$DIR"; then
    sudo rm -rf "$DIR"
    say "removed $DIR"
  fi
}

step_uninstall() {
  say "uninstall: every runner, the systemd units and user $RUNNER_USER"
  local d
  if sudo test -d "$RUNNERS"; then
    for d in $(sudo find "$RUNNERS" -mindepth 1 -maxdepth 1 -type d -printf '%f\n'); do
      [[ $d == *__* ]] || continue
      step_remove "${d%%__*}/${d#*__}"
    done
  fi
  remove_file "/etc/systemd/system/$UNIT"
  remove_file "/etc/systemd/system/$SLICE"
  daemon_reload
  if id "$RUNNER_USER" &>/dev/null; then
    sudo pkill -u "$RUNNER_USER" 2>/dev/null || true
    sudo userdel "$RUNNER_USER"
    sudo rm -rf "$RUNNER_HOME"
    say "removed user $RUNNER_USER and $RUNNER_HOME"
  fi
  say "packages (git, jq, icu, mise, ...) stay installed"
}

# gh_status <owner/repo>: how GitHub sees this machine's runner for the repo.
gh_status() {
  local s
  s="$(gh api "repos/$1/actions/runners" \
    --jq ".runners[] | select(.name == \"$RUNNER_NAME\") | \"\(.status) busy=\(.busy) labels=\([.labels[].name] | join(\",\"))\"" \
    2>/dev/null)" || s="(gh api failed)"
  printf '    GitHub: %s\n' "${s:-not registered}"
}

step_status() {
  say "user: $(id "$RUNNER_USER" 2>/dev/null || echo "missing")"
  local f
  for f in "$UNIT" "$SLICE"; do
    if [[ -f /etc/systemd/system/$f ]]; then
      if cmp -s "$SRC/systemd/$f" "/etc/systemd/system/$f"; then
        say "$f: installed"
      else
        say "$f: installed, differs from the repo (run install)"
      fi
    else
      say "$f: missing"
    fi
  done
  say "slice: $(systemctl show "$SLICE" -p CPUQuotaPerSecUSec -p MemoryMax -p MemoryCurrent | tr '\n' ' ')"
  local units
  units="$(systemctl list-units --all --plain --no-legend 'actions-runner@*.service' | awk '{print $1}')"
  if [[ -z $units ]]; then
    say "runners: none (add one: scripts/setup_actions_runner.sh add owner/repo)"
    return 0
  fi
  local u inst
  for u in $units; do
    inst="${u#actions-runner@}"
    inst="${inst%.service}"
    say "$u: $(systemctl is-active "$u") / $(systemctl is-enabled "$u" 2>/dev/null)"
    if command -v gh >/dev/null; then
      gh_status "${inst%%__*}/${inst#*__}"
    fi
  done
}

usage() {
  sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

[[ $EUID -ne 0 ]] || die "run as your own user, not root (gh needs your login; sudo is used where needed)"
cmd="${1:-}"
shift || true
case "$cmd" in
  install) step_install ;;
  add)
    (($#)) || usage 1
    for slug in "$@"; do step_add "$slug"; done
    ;;
  remove)
    (($#)) || usage 1
    for slug in "$@"; do step_remove "$slug"; done
    ;;
  status) step_status ;;
  uninstall) step_uninstall ;;
  -h | --help | help | "") usage 0 ;;
  *) usage 1 ;;
esac
