/**
 * Message Queue Extension for Pi
 *
 * Enables external processes to send messages to a running pi agent.
 * Messages are read from ~/.pi/queues/<cwd-hash>.jsonl
 *
 * Usage from shell:
 *   dev send-pi <session> "your message here"
 *   dev send-pi <session> --steer "interrupt with this"
 *
 * Queue file format (JSONL):
 *   {"message": "text", "mode": "followUp"}
 *   {"message": "text", "mode": "steer"}
 */

import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { readFileSync, writeFileSync, existsSync, appendFileSync } from "fs";

export default function (pi: ExtensionAPI) {
  let queueFile: string;
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  // Convert cwd to queue file path (same format as session dirs - lowercase)
  function getQueueFile(cwd: string): string {
    const safePath = cwd.toLowerCase().replace(/\//g, "-").replace(/^-/, "");
    return `${process.env.HOME}/.pi/queues/${safePath}.jsonl`;
  }

  function processQueue() {
    if (!existsSync(queueFile)) return;

    const deadLetterFile = `${queueFile}.dead-letter`;

    try {
      const content = readFileSync(queueFile, "utf-8");
      if (!content.trim()) return;

      const lines = content.split("\n").filter((line) => line.trim());
      if (lines.length === 0) return;

      const retryLines: string[] = [];

      for (const line of lines) {
        try {
          const parsed = JSON.parse(line);
          const message = typeof parsed.message === "string" ? parsed.message : "";
          const mode = parsed.mode === "steer" ? "steer" : "followUp";

          if (!message) {
            appendFileSync(deadLetterFile, `${line}\n`);
            continue;
          }

          try {
            pi.sendUserMessage(message, {
              deliverAs: mode,
            });
          } catch (error) {
            retryLines.push(line);
          }
        } catch (error) {
          appendFileSync(deadLetterFile, `${line}\n`);
        }
      }

      if (retryLines.length > 0) {
        writeFileSync(queueFile, `${retryLines.join("\n")}\n`);
      } else {
        writeFileSync(queueFile, "");
      }
    } catch (error) {
      // File read/write error, ignore
    }
  }

  pi.on("session_start", async (event, ctx) => {
    queueFile = getQueueFile(ctx.cwd);

    // Poll every 500ms for new messages
    pollInterval = setInterval(() => {
      processQueue();
    }, 500);
  });

  pi.on("session_shutdown", async () => {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  });

  // Register /queue command to show queue status
  pi.registerCommand("queue", {
    description: "Show message queue file path",
    handler: async (args, ctx) => {
      const file = getQueueFile(ctx.cwd);
      ctx.ui.notify(`Queue: ${file}`, "info");
    },
  });
}
