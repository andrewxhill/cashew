import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

function resolveWebAccessPath(): string | null {
  const home = process.env.HOME || "";
  const nodeVersion = process.version.replace(/^v/, "");

  const candidates = [
    path.join(home, ".nvm", "versions", "node", `v${nodeVersion}`, "lib", "node_modules", "pi-web-access", "index.ts"),
    path.join(home, ".nvm", "versions", "node", nodeVersion, "lib", "node_modules", "pi-web-access", "index.ts"),
    "/usr/local/lib/node_modules/pi-web-access/index.ts",
    "/opt/homebrew/lib/node_modules/pi-web-access/index.ts",
  ];

  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }

  return null;
}

export default function (pi: ExtensionAPI) {
  const entry = resolveWebAccessPath();
  if (!entry) {
    console.error("pi-web-access-wrapper: Could not find pi-web-access index.ts");
    return;
  }

  try {
    const require = createRequire(import.meta.url);
    const { createJiti } = require("jiti");
    const jiti = createJiti(import.meta.url, { cache: false, interopDefault: true });
    const mod = jiti(entry);
    if (typeof mod?.default === "function") {
      mod.default(pi);
    } else {
      console.error("pi-web-access-wrapper: default export not a function");
    }
  } catch (err) {
    console.error("pi-web-access-wrapper: failed to load", err);
  }
}
