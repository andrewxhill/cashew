# Cashew

A dev-environment bootstrap that ships Claude skills/commands plus a `dev` session/worktree manager. It does **not** enforce a specific agent; it sets defaults that are easy to override.

## Example prompts (human → Claude)

1. **Setup Cashew**
   - “Set up my dev environment using cashew.”

2. **Create a worktree to fix a README**
   - “Clone `git@github.com:user/repo.git` and make a `fix-readme` worktree.”

3. **Ask Claude to message a Pi worker**
   - “Tell the README agent how to improve the README.”

4. **Merge and push when done**
   - “Merge `fix-readme` into `main` and push.”

## Orientation (read this first)

**Observed**
- This repo contains: a `dev` CLI, Claude skills/commands, and a Pi extension.
- `dev` creates **tmux** sessions by default.
- Worktrees are stored at `~/Projects/<repo>/<worktree>`; bare repos live at `~/Projects/<repo>/.bare`.

**Assumed (defaults, not rules)**
- Claude is used for orchestration at the projects root and repo roots.
- Claude can send messages to Pi workers running in worktrees.
- Pi is used for long-running implementation work inside worktrees (often Codex-backed).

**Desired (intended workflow)**
- One repo → many worktrees → many resumable agents.
- Claude skills/commands handle repo bootstrap and session orchestration.
- Claude can message Pi workers in worktrees, so humans usually only use `dev` to reattach when they want to inspect or take over a long-running context.
- Fast context switching with predictable session names.

**Unknown**
- Your local agent stack, costs, or model choice. `dev` does not pin these.

If any of the assumptions are wrong for you, keep the tool and change the defaults. The system is built to be repurposed.

## What Cashew Actually Does

Cashew ships Claude skills/commands that call `dev`. Answering the core question:

**What `dev` gives Claude**
- **Persistent sessions** for long-running sub-agents (tmux sessions that survive disconnects).
- **Worktree-native isolation** so multiple agents can work without interfering (`dev new`, `dev wt`).
- **Predictable addressing** of agent contexts via `repo/worktree/sub` session names.
- **Agent defaults** (Pi in worktrees; Claude at repo roots).
- **Queue hooks** for Pi messaging (`dev send-pi`, `dev pi-status`, `dev queue-status`).

Humans mostly use `dev` to reattach when they want to inspect or take over a long-running context.

What it does **not** do:
- It does **not** enforce Docker usage.
- It does **not** force a specific agent.
- It does **not** manage your credentials beyond the setup step.

Checksum: **`dev` is a session/worktree manager with sane defaults; it is not a framework.**

## Operational workflows (agent-first)

### 1) Multiple agents, one repo, zero interference

**Observed**
- Each worktree has its own session and agent.

**Workflow**
- Claude creates worktrees and assigns Pi to each worktree.
- Humans rarely touch `dev` unless they need to inspect a session.

Example (what Claude runs):
```bash
dev new myapp git@github.com:user/myapp
dev wt myapp feature-auth
```

### 2) Drop into any sub-agent’s context when needed

**Observed**
- Sessions are addressable by `repo/worktree/sub`.

**Workflow**
- Use `dev` only when you need to interrupt, inspect, or manually assist.

Examples (human reattach):
```bash
dev myapp/feature-auth            # Reattach to Pi in that worktree
dev myapp/feature-auth/claude      # Reattach to a Claude helper
dev myapp/feature-auth/tests       # Reattach to long-running tests
```

### 3) Remote persistence (resume at any time)

**Observed**
- Sessions persist across SSH disconnects.

**Workflow**
- SSH in, list sessions, reattach to any agent context.

```bash
ssh myserver
dev                              # List running contexts
dev myapp/feature-auth            # Resume Pi agent
```

### Worktree → agent mapping (default, not enforced)

- `dev <repo>/<worktree>` → **Pi auto-starts** (implementation agent)
- `dev <repo>` (non-worktree repo) → **Claude auto-starts** (orchestrator)
- `dev hub/claude` → **Claude** for cross-repo coordination

## How Sessions Map to Names

**Observed**
- Session names use `_` internally; you type `/` in commands.

Example mapping:
- `dev myapp/feature-auth/claude` → session name `myapp_feature-auth_claude`

This is a constraint of session naming, not a feature. If it breaks for you, change `SEP` in `bin/dev`.

## Setup (by Claude skill)

1. **Install Claude Code**:
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

2. **Ask Claude to configure the machine**:
   ```bash
   claude --dangerously-skip-permissions
   ```
   Then say: “Set up my dev environment using cashew”.

   Claude will:
   - Ask for your projects folder name
   - Install Docker, Git, GitHub CLI, `jq`, and tmux
   - Configure SSH keys for GitHub
   - Install the `dev` command
   - Install Claude skills/commands

3. **Optional: install Pi + queue extension**:
   ```bash
   npm install -g @mariozechner/pi-coding-agent
   mkdir -p ~/.pi/agent/extensions
   cp ~/Projects/cashew/main/pi/extensions/message-queue.ts ~/.pi/agent/extensions/
   ```
   This enables: `dev send-pi`, `dev pi-status`, `dev queue-status`.

## Docker Isolation (recommended, not enforced)

**Observed**
- `dev` does not create containers or set `COMPOSE_PROJECT_NAME`.

**Assumed best practice**
- Use one Docker project per worktree to avoid cross-branch contamination.

Example:
```bash
export COMPOSE_PROJECT_NAME="myapp-feature-auth"
docker compose up -d      # Containers: myapp-feature-auth-db, etc.
docker compose down -v    # Teardown only this worktree
```

If you do not use Docker, remove this from your workflow. Nothing in `dev` depends on it.

## Screenshots (optional)

**Unknown**
- We don’t ship screenshots yet. If you want them, define which views matter:
  - `dev` list output
  - a Pi session attached to a worktree
  - a Claude hub session at `~/Projects`

If you want me to add screenshots, tell me which host and which terminal theme to capture.

## Repo Contents

```
cashew/
├── bin/
│   └── dev                      # Project session manager CLI
├── claude/
│   ├── global/
│   │   └── CLAUDE.md            # Global context for all Claude sessions
│   └── commands/
│       ├── dev.md               # /dev skill
│       └── setup.md             # /setup skill for bootstrapping
└── pi/
    └── extensions/
        └── message-queue.ts     # Queue integration for Pi
```

## Requirements

- **Node.js** (for Claude Code)
- **macOS or Linux** (setup skill handles dependencies)

## License

MIT
