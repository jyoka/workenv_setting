#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook: a prompt made only of @mentions opens them in VS Code.

`@aerospace.md` + Enter  -> opens the file in VS Code; the prompt is not sent to the model.
`@config/` + Enter       -> opens the folder in a VS Code window.
Any other text in the prompt -> normal prompt, nothing opens.

Install: cp scripts/open_mention.py ~/.claude/hooks/open_mention.py
"""
import json
import os
import re
import subprocess
import sys

# Full path on purpose: `code` on PATH may belong to Cursor instead.
VSCODE = "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
MENTION = re.compile(r'@"([^"]+)"|@(\S+)')
LINE_SUFFIX = re.compile(r"#L(\d+)(?:-\d+)?$")


def find_targets(prompt, cwd):
    """Return [(abs_path, line)] if the prompt is only @mentions of existing paths, else None."""
    if not prompt.strip() or MENTION.sub("", prompt).strip():
        return None
    targets = []
    for quoted, bare in MENTION.findall(prompt):
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


def main():
    data = json.load(sys.stdin)
    targets = find_targets(data.get("prompt", ""), data.get("cwd") or os.getcwd())
    if not targets:
        return
    for path, line in targets:
        if os.path.isdir(path):
            args = [VSCODE, path]
        else:
            args = [VSCODE, "-r", "-g", f"{path}:{line}" if line else path]
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    names = ", ".join(os.path.basename(p.rstrip("/")) or p for p, _ in targets)
    print(json.dumps({"decision": "block", "reason": f"Opened in VS Code: {names}"}))


if __name__ == "__main__":
    main()
