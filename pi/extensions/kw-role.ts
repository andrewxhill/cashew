/**
 * Knowledge Worker Role Extension
 *
 * Ensures knowledge-worker sessions are always aware of their role and boundaries.
 * Enabled when PI_ROLE=knowledge-worker or PI_KW_ROLE=1 is set.
 */

import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { readFileSync, writeFileSync } from "fs";

const ROLE_MARKER = "knowledge-worker";

function isKnowledgeWorker(): boolean {
  return process.env.PI_ROLE === ROLE_MARKER || process.env.PI_KW_ROLE === "1";
}

function parseTags(raw: string | undefined): string[] {
  if (!raw) return [];
  return raw
    .split(/[;,]/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function updateMeta(metaFile: string, updater: (current: any) => any) {
  let current: any = {};
  try {
    const raw = readFileSync(metaFile, "utf-8");
    current = JSON.parse(raw);
  } catch {
    current = {};
  }

  const updated = updater(current) ?? current;
  try {
    writeFileSync(metaFile, `${JSON.stringify(updated, null, 2)}\n`);
  } catch {
    // ignore
  }
}

export default function (pi: ExtensionAPI) {
  if (!isKnowledgeWorker()) return;

  const name = process.env.PI_KW_NAME || "";
  const repo = process.env.PI_KW_REPO || "";
  const tags = parseTags(process.env.PI_KW_TAGS);
  const metaFile = process.env.PI_KW_META_FILE || "";

  pi.on("session_start", async (_event, ctx) => {
    if (ctx.hasUI) {
      const label = ["KW", name || "unknown"].filter(Boolean).join(": ");
      const tagsText = tags.length > 0 ? `(${tags.join(", ")})` : "";
      ctx.ui.setStatus("kw-role", `${label} ${tagsText}`.trim());
    }
  });

  pi.on("before_agent_start", async (event) => {
    const roleNote = [
      "You are a knowledge-worker agent.",
      "Your job: build durable understanding of the system, review plans/PRs, and advise the PM.",
      "You are NOT a worktree implementation agent and NOT the PM.",
      "Do not create/cleanup worktrees, do not merge branches, and do not run destructive dev commands.",
      "If asked to implement, respond with guidance and propose a plan or review instead.",
    ].join(" ");

    return { systemPrompt: `${event.systemPrompt}\n\n${roleNote}` };
  });

  if (metaFile) {
    pi.registerCommand("kw-tags", {
      description: "Set knowledge-worker tags (comma-separated)",
      handler: async (args) => {
        const tagList = parseTags(args);
        updateMeta(metaFile, (current) => ({
          ...current,
          tags: tagList,
          updatedAt: new Date().toISOString(),
        }));
      },
    });

    pi.registerCommand("kw-note", {
      description: "Set knowledge-worker description/note",
      handler: async (args) => {
        updateMeta(metaFile, (current) => ({
          ...current,
          description: args || current.description || "",
          updatedAt: new Date().toISOString(),
        }));
      },
    });
  }

  pi.registerCommand("kw-info", {
    description: "Show knowledge-worker role info",
    handler: async (_args, ctx) => {
      const info = [
        `role: knowledge-worker`,
        `repo: ${repo || "(unknown)"}`,
        `name: ${name || "(unknown)"}`,
        `tags: ${tags.length > 0 ? tags.join(", ") : "(none)"}`,
      ];
      if (ctx.hasUI) {
        ctx.ui.notify(info.join(" | "), "info");
      }
    },
  });
}
