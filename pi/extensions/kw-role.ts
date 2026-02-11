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
  const metaFile = process.env.PI_KW_META_FILE || "";
  let currentTags = parseTags(process.env.PI_KW_TAGS);
  let currentDescription = "";

  function updateStatus(ctx: { hasUI: boolean; ui: any }) {
    if (!ctx.hasUI) return;
    const label = ["KW", name || "unknown"].filter(Boolean).join(": ");
    const tagsText = currentTags.length > 0 ? `(${currentTags.join(", ")})` : "";
    ctx.ui.setStatus("kw-role", `${label} ${tagsText}`.trim());
  }

  pi.on("session_start", async (_event, ctx) => {
    updateStatus(ctx);
  });

  pi.on("before_agent_start", async (event) => {
    const roleNote = [
      "You are a knowledge-worker agent.",
      "Your job: build durable understanding of the system, review plans/PRs, and advise the PM.",
      "You are NOT a worktree implementation agent and NOT the PM.",
      "Do not create/cleanup worktrees, do not merge branches, and do not run destructive dev commands.",
      "If asked to implement, respond with guidance and propose a plan or review instead.",
      "To update tags or notes, run /kw-tags and /kw-note in your own session (not in a response).",
    ].join(" ");

    return { systemPrompt: `${event.systemPrompt}\n\n${roleNote}` };
  });

  if (metaFile) {
    pi.registerCommand("kw-tags", {
      description: "Set knowledge-worker tags (comma-separated)",
      handler: async (args, ctx) => {
        const tagList = parseTags(args);
        currentTags = tagList;
        updateMeta(metaFile, (current) => ({
          ...current,
          tags: tagList,
          updatedAt: new Date().toISOString(),
        }));
        updateStatus(ctx);
      },
    });

    pi.registerCommand("kw-note", {
      description: "Set knowledge-worker description/note",
      handler: async (args, ctx) => {
        currentDescription = args || currentDescription;
        updateMeta(metaFile, (current) => ({
          ...current,
          description: args || current.description || "",
          updatedAt: new Date().toISOString(),
        }));
        updateStatus(ctx);
      },
    });
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

  function applyInlineMeta(text: string, ctx: { hasUI: boolean; ui: any }) {
    if (!metaFile || !text) return;

    const tagMatch = text.match(/^\s*\/kw-tags\s+(.+)$/m);
    const noteMatch = text.match(/^\s*\/kw-note\s+(.+)$/m);

    if (tagMatch) {
      const tagList = parseTags(tagMatch[1]);
      currentTags = tagList;
      updateMeta(metaFile, (current) => ({
        ...current,
        tags: tagList,
        updatedAt: new Date().toISOString(),
      }));
      updateStatus(ctx);
    }

    if (noteMatch) {
      const noteText = noteMatch[1].trim();
      currentDescription = noteText || currentDescription;
      updateMeta(metaFile, (current) => ({
        ...current,
        description: noteText || current.description || "",
        updatedAt: new Date().toISOString(),
      }));
    }
  }

  pi.on("agent_end", async (event, ctx) => {
    if (!metaFile) return;
    const messages = event.messages ?? [];
    const lastAssistant = [...messages].reverse().find((message: any) => message?.role === "assistant");
    if (!lastAssistant) return;
    const text = extractText(lastAssistant.content);
    applyInlineMeta(text, ctx);
  });

  pi.registerCommand("kw-info", {
    description: "Show knowledge-worker role info",
    handler: async (_args, ctx) => {
      const info = [
        `role: knowledge-worker`,
        `repo: ${repo || "(unknown)"}`,
        `name: ${name || "(unknown)"}`,
        `tags: ${currentTags.length > 0 ? currentTags.join(", ") : "(none)"}`,
      ];
      if (ctx.hasUI) {
        ctx.ui.notify(info.join(" | "), "info");
      }
    },
  });
}
