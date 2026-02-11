/**
 * Pi Subscribe Extension
 *
 * Writes the final assistant message for each agent turn to a status log
 * so other processes can subscribe to "done" events.
 *
 * Log file: ~/.pi/status/<cwd-hash>.jsonl
 * Entry format:
 *   {"timestamp": 1710000000000, "status": "done", "message": "...", ...}
 */

import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { appendFileSync, mkdirSync } from "fs";
import path from "path";

const MAX_MESSAGE_CHARS = 4000;

export default function (pi: ExtensionAPI) {
  let statusFile = "";

  function safePathFromCwd(cwd: string): string {
    return cwd.toLowerCase().replace(/\//g, "-").replace(/^-/, "");
  }

  function getStatusFile(cwd: string): string {
    const override = process.env.PI_STATUS_FILE;
    if (override) return override;
    const safePath = safePathFromCwd(cwd);
    return `${process.env.HOME}/.pi/status/${safePath}.jsonl`;
  }

  function ensureDir(filePath: string) {
    mkdirSync(path.dirname(filePath), { recursive: true });
  }

  function extractText(content: any): string {
    if (!content) return "";
    if (typeof content === "string") return content;
    if (Array.isArray(content)) {
      return content
        .filter((part) => part && part.type === "text")
        .map((part) => part.text || "")
        .join(" ")
        .trim();
    }
    return "";
  }

  function truncateMessage(message: string): { text: string; truncated: boolean } {
    if (message.length <= MAX_MESSAGE_CHARS) return { text: message, truncated: false };
    return { text: `${message.slice(0, MAX_MESSAGE_CHARS)}…`, truncated: true };
  }

  pi.on("session_start", async (_event, ctx) => {
    statusFile = getStatusFile(ctx.cwd);
    ensureDir(statusFile);
  });

  pi.on("agent_end", async (event, ctx) => {
    if (!statusFile) return;

    const messages = event.messages ?? [];
    const lastAssistant = [...messages].reverse().find((message: any) => message?.role === "assistant");

    if (!lastAssistant) return;

    const rawText = extractText(lastAssistant.content);
    const { text, truncated } = truncateMessage(rawText);

    const entry = {
      timestamp: Date.now(),
      status: "done",
      role: "assistant",
      stopReason: lastAssistant.stopReason ?? null,
      errorMessage: lastAssistant.errorMessage ?? null,
      truncated,
      message: text,
      cwd: ctx.cwd,
      sessionFile: ctx.sessionManager.getSessionFile() ?? null,
    };

    appendFileSync(statusFile, `${JSON.stringify(entry)}\n`);
  });
}
