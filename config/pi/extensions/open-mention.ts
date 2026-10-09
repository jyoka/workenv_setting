// A Pi prompt made only of @mentions opens them in VS Code instead of reaching the model.
// The matching logic lives in the shared script, which Claude Code and Codex call as a hook.
// Install: cp config/pi/extensions/open-mention.ts ~/.pi/agent/extensions/
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { homedir } from "node:os";
import { join } from "node:path";

const SCRIPT = join(homedir(), ".config/agent-hooks/open_mention.py");

export default function (pi: ExtensionAPI) {
  pi.on("input", async (event, ctx) => {
    if (event.source !== "interactive" || !event.text.includes("@")) return { action: "continue" };
    const result = await pi.exec("python3", [SCRIPT, "--prompt", event.text, "--cwd", ctx.cwd], { timeout: 10000 });
    if (result.code !== 0) return { action: "continue" };
    ctx.ui.notify(result.stdout.trim(), "info");
    return { action: "handled" };
  });
}
