#!/bin/bash
# Give task-hub's coding agents their own unprivileged Linux user (see agent-user.md).
# Run on the Omarchy machine from the repo root, with sudo, as the task-hub user (joka):
#
#   sudo scripts/setup_agent_user.sh            # create/repair the user, group, sudoers and ACLs
#   sudo scripts/setup_agent_user.sh status     # show what is in place, change nothing
#   sudo scripts/setup_agent_user.sh check      # run the acceptance checks (sudo, worktree, home)
#   sudo scripts/setup_agent_user.sh uninstall  # undo everything: ACLs, sudoers, group, user
#
# The agent user can be reached from the task-hub user only (sudo -u task-agent, never root),
# shares a group and default ACLs with it on task-hub's worktrees, can read (not write) the
# repos the worktrees belong to, and can only pass through the task-hub user's HOME to get there. Every command is safe to run again; rerunning
# the install also repairs permissions that drifted. Names and paths can be overridden:
#   sudo AGENT_USER=task-agent AGENT_GROUP=task-agents scripts/setup_agent_user.sh
set -euo pipefail

AGENT_USER="${AGENT_USER:-task-agent}"
AGENT_GROUP="${AGENT_GROUP:-task-agents}"
AGENT_HOME="${AGENT_HOME:-/var/lib/$AGENT_USER}"
OWNER="${TASKHUB_USER:-${SUDO_USER:-}}"
SUDOERS="/etc/sudoers.d/$AGENT_USER"

say() { printf '==> %s\n' "$*"; }
warn() { printf '==> WARNING: %s\n' "$*" >&2; }
die() {
  printf '==> ERROR: %s\n' "$*" >&2
  exit 1
}

# Run from / so neither user needs access to the caller's working directory.
as_agent() { (cd / && sudo -u "$AGENT_USER" -H "$@"); }
as_owner() { (cd / && sudo -u "$OWNER" -H "$@"); }

setup_vars() {
  local n
  for n in "$AGENT_USER" "$AGENT_GROUP"; do
    [[ $n =~ ^[a-z_][a-z0-9_-]*$ ]] || die "invalid user/group name '$n'"
  done
  [[ -n $OWNER && $OWNER != root ]] ||
    die "run with sudo from the task-hub user's account (or set TASKHUB_USER=joka)"
  id "$OWNER" &>/dev/null || die "no such user '$OWNER'"
  [[ $OWNER != "$AGENT_USER" ]] || die "AGENT_USER must differ from the task-hub user"
  OWNER_HOME="$(getent passwd "$OWNER" | cut -d: -f6)"
  OWNER_GROUP="$(id -gn "$OWNER")"
  DATA="${TASKHUB_DATA:-$OWNER_HOME/.local/share/task-hub}"
  # The agent edits files in its worktree (read/write, shared group). Git in a worktree also
  # reads the main repository's .git under repos/, but the agent must not write there: a hook or
  # a .git/config entry (core.hooksPath, core.fsmonitor) would run as the task-hub user during
  # task-hub's own git steps. So repos/ is read-only for the agent.
  SHARED=("$DATA/worktrees")
  READONLY=("$DATA/repos")
}

# Directories from the HOME down to DATA that the agent has to pass through (execute only).
path_components() {
  [[ $DATA == "$OWNER_HOME"/* ]] || return 0
  local p="$OWNER_HOME" part rel="${DATA#"$OWNER_HOME"/}"
  echo "$p"
  local IFS=/
  for part in $rel; do
    p="$p/$part"
    echo "$p"
  done
}

# Every entry next to that path (dotfiles, ~/.claude, ~/.config, ...) except the path itself and
# the shared directories. Many of them are world-readable, so once the agent can pass through
# HOME they need an explicit "no access" ACL entry (named-user entries take precedence over other).
side_entries() {
  local dirs next d e s keep i
  mapfile -t dirs < <(path_components)
  for ((i = 0; i < ${#dirs[@]}; i++)); do
    d="${dirs[i]}"
    next="${dirs[i + 1]:-}"
    for e in "$d"/* "$d"/.*; do
      [[ -e $e && ! -L $e ]] || continue
      [[ ${e##*/} != . && ${e##*/} != .. ]] || continue
      [[ $e != "$next" ]] || continue
      keep=0
      for s in "${SHARED[@]}" "${READONLY[@]}"; do [[ $e != "$s" ]] || keep=1; done
      ((keep)) || echo "$e"
    done
  done
}

step_user() {
  if ! getent group "$AGENT_GROUP" >/dev/null; then
    groupadd --system "$AGENT_GROUP"
    say "created group $AGENT_GROUP"
  fi
  if ! id "$AGENT_USER" &>/dev/null; then
    # A system user: no password (locked), no sudo, no extra groups. It has a real shell
    # because sudo sets SHELL to it and agents (Claude Code's Bash tool) run commands with it.
    useradd --system --user-group --create-home --home-dir "$AGENT_HOME" \
      --shell /bin/bash --comment "task-hub coding agent" "$AGENT_USER"
    say "created user $AGENT_USER (home $AGENT_HOME)"
  fi
  chmod 700 "$AGENT_HOME"
  if [[ $(passwd -S "$AGENT_USER" | awk '{print $2}') != L ]]; then
    usermod -L "$AGENT_USER"
    say "locked the password of $AGENT_USER"
  fi
  local u
  for u in "$OWNER" "$AGENT_USER"; do
    if ! id -nG "$u" | tr ' ' '\n' | grep -qx "$AGENT_GROUP"; then
      gpasswd -a "$u" "$AGENT_GROUP" >/dev/null
      say "added $u to $AGENT_GROUP"
    fi
  done
  local extra
  extra="$(id -nG "$AGENT_USER" | tr ' ' '\n' | grep -vx -e "$AGENT_USER" -e "$AGENT_GROUP" | tr '\n' ' ')"
  [[ -z $extra ]] || warn "$AGENT_USER is in extra groups ($extra); wheel or docker would let it become root"
}

step_sudoers() {
  grep -Eqs '^[@#]includedir[[:space:]]+/etc/sudoers\.d' /etc/sudoers ||
    die "/etc/sudoers does not include /etc/sudoers.d; add '@includedir /etc/sudoers.d' with visudo"
  local tmp
  tmp="$(mktemp)"
  # Run-as list is only the agent user: no root, no other user, no -g group. CWD=* allows
  # `sudo -D <worktree>`; the agent still only reaches what its permissions allow.
  cat >"$tmp" <<EOF
# Managed by workenv_setting scripts/setup_agent_user.sh (see agent-user.md).
# $OWNER may run anything as $AGENT_USER without a password, and nothing as root.
$OWNER ALL=($AGENT_USER) CWD=* NOPASSWD: ALL
EOF
  if ! visudo -cqf "$tmp"; then
    rm -f "$tmp"
    die "generated sudoers drop-in does not parse"
  fi
  if ! cmp -s "$tmp" "$SUDOERS"; then
    install -m440 -o root -g root "$tmp" "$SUDOERS"
    say "wrote $SUDOERS"
  fi
  rm -f "$tmp"
  visudo -cq || die "sudoers configuration is invalid after writing $SUDOERS; fix it with visudo"
}

step_acls() {
  local d spec="u:$OWNER:rwX,u:$AGENT_USER:rwX,g:$AGENT_GROUP:rwX"
  for d in "${SHARED[@]}"; do
    [[ -d $d ]] || install -d -m755 -o "$OWNER" -g "$OWNER_GROUP" "$d"
    # Group ownership and setgid so new files stay in the shared group; access ACLs on what
    # exists and default ACLs on directories so new files get them too. The named-user entries
    # work even before the task-hub user logs in again and picks up the new group.
    find "$d" ! -type l ! -group "$AGENT_GROUP" -exec chgrp "$AGENT_GROUP" {} +
    find "$d" -type d ! -perm -2000 -exec chmod g+s {} +
    find "$d" ! -type l -exec setfacl -m "$spec" {} +
    find "$d" -type d -exec setfacl -d -m "u::rwX,g::rwX,o::rX,$spec" {} +
    say "shared $d with $AGENT_GROUP"
  done
  for d in "${READONLY[@]}"; do
    [[ -d $d ]] || install -d -m755 -o "$OWNER" -g "$OWNER_GROUP" "$d"
    find "$d" ! -type l -exec setfacl -m "u:$AGENT_USER:rX" {} +
    find "$d" -type d -exec setfacl -d -m "u:$AGENT_USER:rX" {} +
    say "$d: read-only for $AGENT_USER"
  done
  local p
  while read -r p; do
    setfacl -m "u:$AGENT_USER:--x" "$p"
  done < <(path_components)
  while read -r p; do
    setfacl -m "u:$AGENT_USER:---" "$p"
  done < <(side_entries)
  [[ $DATA != "$OWNER_HOME"/* ]] || say "$AGENT_USER can pass through $OWNER_HOME to $DATA but not list or read it"
}

step_git() {
  # Worktrees and repos belong to the task-hub user; without this git refuses them as
  # "dubious ownership" when the agent runs it.
  local have p
  have="$(as_agent git config --global --get-all safe.directory || true)"
  for p in "$DATA/worktrees/*" "$DATA/repos/*"; do
    if ! grep -qxF "$p" <<<"$have"; then
      as_agent git config --global --add safe.directory "$p"
      say "git: safe.directory $p for $AGENT_USER"
    fi
  done
  as_agent git config --global user.email >/dev/null ||
    warn "$AGENT_USER has no git identity yet (see agent-user.md)"
}

print_values() {
  cat <<EOF

task-hub settings:
  agent user   $AGENT_USER
  agent group  $AGENT_GROUP
  agent home   $AGENT_HOME
  shared dirs  ${SHARED[*]} (read/write)
  read-only    ${READONLY[*]}
  run a command as the agent:  sudo -n -u $AGENT_USER -H -D <worktree> -- <command>

Log out and in again (or reboot) so $OWNER's sessions and user services pick up the group.
Then: sudo $0 check
EOF
}

step_install() {
  say "install: user $AGENT_USER, group $AGENT_GROUP, sudoers, ACLs for $OWNER"
  command -v setfacl >/dev/null || pacman -S --needed --noconfirm acl
  step_user
  step_sudoers
  step_acls
  step_git
  print_values
}

step_status() {
  say "user: $(id "$AGENT_USER" 2>/dev/null || echo missing)"
  say "group $AGENT_GROUP: $(getent group "$AGENT_GROUP" || echo missing)"
  if [[ -f $SUDOERS ]]; then
    say "sudoers: $(grep -v '^#' "$SUDOERS")"
  else
    say "sudoers: $SUDOERS missing"
  fi
  local d
  for d in "${SHARED[@]}"; do
    if getfacl -cp "$d" 2>/dev/null | grep -q "^default:user:$AGENT_USER:rw"; then
      say "$d: shared"
    else
      say "$d: not shared (run install)"
    fi
  done
  for d in "${READONLY[@]}"; do
    if getfacl -cp "$d" 2>/dev/null | grep -q "^default:user:$AGENT_USER:r-x"; then
      say "$d: read-only for $AGENT_USER"
    else
      say "$d: not readable for $AGENT_USER (run install)"
    fi
  done
  id "$AGENT_USER" &>/dev/null || return 0
  leaks || true
  say "git identity of $AGENT_USER: $(as_agent git config --global user.email || echo none)"
}

# leaks: entries in the task-hub user's HOME that the agent can read (should be none).
leaks() {
  local e found=0
  while read -r e; do
    if as_agent test -r "$e"; then
      warn "$AGENT_USER can read $e (rerun install)"
      found=1
    fi
  done < <(side_entries)
  ((found)) || say "$AGENT_USER cannot read anything in $OWNER_HOME outside ${SHARED[*]} ${READONLY[*]}"
  return "$found"
}

step_check() {
  id "$AGENT_USER" &>/dev/null || die "user $AGENT_USER does not exist (run install)"
  local fail=0
  ok() { say "ok: $*"; }
  bad() {
    printf '==> FAIL: %s\n' "$*" >&2
    fail=1
  }

  # -k makes the inner sudo ignore a cached password, so only NOPASSWD rules can pass.
  if as_owner sudo -k -n -u "$AGENT_USER" true; then
    ok "$OWNER: sudo -u $AGENT_USER -n true works without a password"
  else
    bad "$OWNER cannot run sudo -u $AGENT_USER -n true"
  fi
  if as_owner sudo -k -n -u root true 2>/dev/null; then
    bad "$OWNER can run commands as root without a password (not from $SUDOERS, check the other sudoers files)"
  else
    ok "$OWNER: sudo -u root -n is refused"
  fi
  local rules
  rules="$(grep -v '^#' "$SUDOERS" 2>/dev/null || true)"
  if grep -q "($AGENT_USER)" <<<"$rules" && ! grep -Eq 'root|\(ALL' <<<"$rules"; then
    ok "$SUDOERS grants $AGENT_USER only"
  else
    bad "$SUDOERS is missing or grants more than $AGENT_USER"
  fi

  local wt="$DATA/worktrees" t
  t="$(as_owner mktemp -d "$wt/.agent-check.XXXXXX")"
  # mktemp -d makes it 0700, which sets the ACL mask to --- and locks the
  # agent out; g+rwx widens the mask back (as a normal tool's mkdir would)
  as_owner chmod g+rwx "$t"
  if as_owner sh -c 'echo owner >"$1/a"' _ "$t" &&
    as_agent sh -c 'cat "$1/a" >/dev/null && echo agent >>"$1/a" && mkdir "$1/d" && echo agent >"$1/d/b"' _ "$t" &&
    as_owner sh -c 'cat "$1/d/b" >/dev/null && echo owner >>"$1/d/b" && echo owner >"$1/d/c"' _ "$t" &&
    as_agent sh -c 'echo agent >>"$1/d/c"' _ "$t"; then
    ok "$OWNER and $AGENT_USER read and write each other's files in $wt"
  else
    bad "shared read/write in $wt failed"
  fi
  as_owner rm -rf "$t" || bad "$OWNER could not remove $t (files made by $AGENT_USER)"

  local repo
  repo="$(find "$wt" -mindepth 2 -maxdepth 2 -name .git -printf '%h\n' -quit)"
  if [[ -n $repo ]]; then
    if as_agent git -C "$repo" status --short >/dev/null; then
      ok "$AGENT_USER can run git status in $repo"
    else
      bad "$AGENT_USER cannot run git in $repo"
    fi
  fi
  local g
  g="$(find "${READONLY[@]}" -mindepth 1 -maxdepth 4 -name .git -type d -print -quit 2>/dev/null)"
  if [[ -n $g ]]; then
    if as_agent test -w "$g" || as_agent test -w "$g/config" || as_agent test -w "$g/hooks"; then
      bad "$AGENT_USER can write $g (hooks or config would run as $OWNER)"
    else
      ok "$AGENT_USER can read but not write $g"
    fi
  fi

  if as_agent ls "$OWNER_HOME" &>/dev/null; then
    bad "$AGENT_USER can list $OWNER_HOME"
  else
    ok "$AGENT_USER cannot list $OWNER_HOME"
  fi
  leaks || fail=1

  ((fail == 0)) || die "some checks failed"
  say "all checks passed"
}

step_uninstall() {
  say "uninstall: ACLs, $SUDOERS, group $AGENT_GROUP, user $AGENT_USER and $AGENT_HOME"
  if [[ -f $SUDOERS ]]; then
    rm -f "$SUDOERS"
    say "removed $SUDOERS"
  fi
  local d p
  if id "$AGENT_USER" &>/dev/null; then
    pkill -u "$AGENT_USER" 2>/dev/null || true
    for d in "${SHARED[@]}"; do
      [[ -d $d ]] || continue
      # Hand files made by the agent back to the task-hub user before the uid goes away.
      chown -R -h --from="$AGENT_USER" "$OWNER" "$d"
    done
    while read -r p; do
      setfacl -x "u:$AGENT_USER" "$p" 2>/dev/null || true
    done < <(path_components; side_entries)
    for d in "${READONLY[@]}"; do
      [[ -d $d ]] || continue
      find "$d" ! -type l -exec setfacl -x "u:$AGENT_USER" {} + 2>/dev/null || true
      find "$d" -type d -exec setfacl -d -x "u:$AGENT_USER" {} + 2>/dev/null || true
      say "$d: removed read access for $AGENT_USER"
    done
  fi
  for d in "${SHARED[@]}"; do
    [[ -d $d ]] || continue
    find "$d" ! -type l -exec setfacl -b {} +
    find "$d" -type d -perm -2000 -exec chmod g-s {} +
    if getent group "$AGENT_GROUP" >/dev/null; then
      find "$d" ! -type l -group "$AGENT_GROUP" -exec chgrp "$OWNER_GROUP" {} +
    fi
    say "unshared $d"
  done
  if id "$AGENT_USER" &>/dev/null; then
    userdel "$AGENT_USER"
    rm -rf "$AGENT_HOME"
    say "removed user $AGENT_USER and $AGENT_HOME"
  fi
  if getent group "$AGENT_GROUP" >/dev/null; then
    groupdel "$AGENT_GROUP"
    say "removed group $AGENT_GROUP"
  fi
}

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

cmd="${1:-install}"
case "$cmd" in
  -h | --help | help) usage 0 ;;
  install | status | check | uninstall) ;;
  *) usage 1 ;;
esac
[[ $EUID -eq 0 ]] || die "run with sudo: sudo $0 $cmd"
setup_vars
"step_$cmd"
