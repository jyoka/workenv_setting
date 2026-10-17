"""Run scripts/setup_agent_user.sh install against stubbed system commands.

The script needs root, so it runs under `unshare -r` (an unprivileged user namespace where the
caller is uid 0). Every command that would touch users, groups, sudoers, ACLs or services is a
stub on PATH that only logs its arguments; files are only written under a temporary directory.
"""

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "setup_agent_user.sh"
AGENT = "th-test-agent"
GROUP = "th-test-agents"
OWNER = "th-test-owner"

STUBS = {
    # Users and groups already exist; GROUPS_OF_AGENT sets what `id -nG <agent>` prints.
    "id": f"""
        if [ "$1" = -nG ] && [ "$2" = {AGENT} ]; then echo "$GROUPS_OF_AGENT"; exit 0; fi
        if [ "$1" = -nG ]; then echo "{OWNER} {GROUP}"; exit 0; fi
        if [ "$1" = -gn ]; then echo {OWNER}; exit 0; fi
        exit 0
    """,
    "getent": f"""
        if [ "$1" = passwd ]; then echo "{OWNER}:x:1000:1000::$FAKE_HOME:/bin/bash"; fi
        exit 0
    """,
    "passwd": f'echo "{AGENT} L 2026-10-17 -1 -1 -1 -1"',
    "systemctl": "echo inactive",
    "pgrep": "exit 1",
    "pkill": "exit 1",
    "cmp": "exit 1",
    # preflight reads /etc/sudoers, which the namespace's root cannot read.
    "grep": """
        for a in "$@"; do last="$a"; done
        [ "$last" = /etc/sudoers ] && exit 0
        exec /usr/bin/grep "$@"
    """,
    # as_agent / as_owner: the agent has no git identity or token yet; the owner has one.
    "sudo": """
        echo "sudo $*" >>"$STUB_LOG"
        while [ $# -gt 0 ]; do
          case "$1" in -u) shift 2 ;; -*) shift ;; *) break ;; esac
        done
        case "$1" in
          git) [ "$4" = user.name ] || [ "$4" = user.email ] && [ $# -eq 4 ] && echo "Owner Name"
               exit 0 ;;
          */gh) exit 1 ;;
        esac
        exec "$@"
    """,
}
LOGGED = [
    "groupadd", "useradd", "usermod", "gpasswd", "setfacl", "chgrp", "find",
    "visudo", "install", "pacman",
]


def userns_available():
    if not shutil.which("unshare"):
        return False
    try:
        return subprocess.run(["unshare", "-r", "true"], timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@unittest.skipUnless(userns_available(), "needs unshare -r (unprivileged user namespaces)")
class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.data = self.home / ".local" / "share" / "task-hub"
        (self.data / "worktrees").mkdir(parents=True)
        (self.data / "repos").mkdir()
        (self.home / ".config").mkdir()
        self.agent_home = root / "agent-home"
        self.agent_home.mkdir()
        self.log = root / "stub.log"
        self.bin = root / "bin"
        self.bin.mkdir()
        for name, body in STUBS.items():
            self.stub(name, textwrap.dedent(body))
        for name in LOGGED:
            self.stub(name, f'echo "{name} $*" >>"$STUB_LOG"\n')

    def tearDown(self):
        self.tmp.cleanup()

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def install(self, groups_of_agent, agent_home=None):
        env = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": str(self.home),
            "STUB_LOG": str(self.log),
            "FAKE_HOME": str(self.home),
            "GROUPS_OF_AGENT": groups_of_agent,
            "AGENT_USER": AGENT,
            "AGENT_GROUP": GROUP,
            "AGENT_HOME": str(agent_home or self.agent_home),
            "TASKHUB_USER": OWNER,
        }
        result = subprocess.run(
            ["unshare", "-r", "bash", str(SCRIPT_PATH), "install"],
            env=env, capture_output=True, text=True, timeout=60,
        )
        log = self.log.read_text(encoding="utf-8") if self.log.exists() else ""
        return result, log

    def assert_ran_to_the_end(self, result, log):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("shared", result.stdout)  # step_acls
        self.assertIn(f"setfacl -m u:{AGENT}:--x {self.data}", log)
        self.assertIn("safe.directory", log)  # step_git
        self.assertIn(f"install -m440 -o root -g root", log)  # step_sudoers
        self.assertIn(f"/etc/sudoers.d/{AGENT}", log)
        self.assertIn("task-hub settings:", result.stdout)  # print_values

    def test_agent_without_extra_groups_runs_to_print_values(self):
        result, log = self.install(f"{AGENT} {GROUP}")
        self.assert_ran_to_the_end(result, log)
        self.assertNotIn("extra groups", result.stderr)

    def test_agent_with_extra_groups_warns_and_continues(self):
        result, log = self.install(f"{AGENT} {GROUP} wheel")
        self.assert_ran_to_the_end(result, log)
        self.assertIn("extra groups (wheel )", result.stderr)

    def test_unexpected_failure_names_the_line(self):
        # chmod 700 on a missing agent home fails outside any condition.
        result, _ = self.install(f"{AGENT} {GROUP}", agent_home=self.home / "missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr, r"==> ERROR: line \d+ \(step_user\): chmod 700 .* exited 1")
        self.assertNotIn("task-hub settings:", result.stdout)


if __name__ == "__main__":
    unittest.main()
