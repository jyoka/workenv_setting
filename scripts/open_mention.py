#!/usr/bin/env python3
"""Prompt hook shared by coding agents: a prompt made only of @mentions opens them in VS Code.

`@aerospace.md` + Enter  -> opens the file in VS Code; the prompt is not sent to the model.
`@config/` + Enter       -> opens the folder in a VS Code window.
Any other text in the prompt -> normal prompt, nothing opens.

Hook mode (Claude Code, Codex): JSON {"prompt", "cwd"} on stdin; prints a block decision when it opens.
CLI mode (Pi extension): --prompt TEXT --cwd DIR; prints a message and exits 0 when it opens, else exits 1.
--bare-paths: also accept paths without @ (Codex's @ picker inserts plain paths).

Install: cp scripts/open_mention.py ~/.config/agent-hooks/open_mention.py
"""
import argparse
import json
import os
import re
import subprocess
import sys

# Full path on purpose: `code` on PATH may belong to Cursor instead.
VSCODE = "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
MENTION = re.compile(r'@"([^"]+)"|@(\S+)')
TOKEN = re.compile(r'@?"([^"]+)"|@?(\S+)')
LINE_SUFFIX = re.compile(r"#L(\d+)(?:-\d+)?$")


def find_targets(prompt, cwd, bare_paths=False):
    """Return [(abs_path, line)] if the prompt is only mentions of existing paths, else None."""
    pattern = TOKEN if bare_paths else MENTION
    if not prompt.strip() or pattern.sub("", prompt).strip():
        return None
    targets = []
    for quoted, bare in pattern.findall(prompt):
        raw = quoted or bare
        line = None
        m = LINE_SUFFIX.search(raw)
        if m:
            raw, line = raw[: m.start()], m.group(1)
        path = os.path.join(cwd, os.path.expanduser(raw))
        if not os.path.exists(path):
            return None
        targets.append((os.path.normpath(path), line))
    return targets


def open_targets(targets):
    for path, line in targets:
        if os.path.isdir(path):
            args = [VSCODE, path]
        else:
            args = [VSCODE, "-r", "-g", f"{path}:{line}" if line else path]
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    names = ", ".join(os.path.basename(p.rstrip("/")) or p for p, _ in targets)
    return f"Opened in VS Code: {names}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bare-paths", action="store_true")
    parser.add_argument("--prompt")
    parser.add_argument("--cwd")
    args = parser.parse_args()

    if args.prompt is not None:
        targets = find_targets(args.prompt, args.cwd or os.getcwd(), args.bare_paths)
        if not targets:
            return 1
        print(open_targets(targets))
        return 0

    data = json.load(sys.stdin)
    targets = find_targets(data.get("prompt", ""), data.get("cwd") or os.getcwd(), args.bare_paths)
    if targets:
        print(json.dumps({"decision": "block", "reason": open_targets(targets)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
