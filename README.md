# Cashew

A batteries-included dev environment bootstrap for Claude skills + commands, with multi-agent workflows and Docker isolation.

Cashew gives you a single `dev` command to manage worktrees, sessions, and agents. It ships Claude skills/commands for setup, but you can run any agent. Defaults are tuned for Claude (project orchestration) and Pi (long-running implementation).

## What Cashew Does (Quick Tour)

- **Worktree-first workflows**: each feature branch becomes a directory (`~/projects/<repo>/<worktree>`).
- **Automatic agent sessions**:
  - Worktree sessions auto-start **`pi`** (great for long-running implementation loops).
  - Non-worktree repos auto-start **`claude --dangerously-skip-permissions`**.
- **Resume anything**: sessions are persistent, so agents are resumable at any time.
- **Infinite agents per worktree**: create additional sub-sessions like `dev repo/feature/claude`, `dev repo/feature/pi`, or `dev repo/feature/tests` (any agent, any time).
- **Full Docker isolation**: each worktree runs isolated containers (no shared DBs, no port clashes).

## Setup

1. **Install Claude Code** (the only manual step):
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

2. **Ask Claude to set up your environment**:
   ```bash
   claude --dangerously-skip-permissions
   ```
   Then say: "Set up my dev environment using cashew"

   Claude will:
   - Ask what you want to call your projects folder
   - Install Docker, Git, GitHub CLI, `jq`, and tmux
   - Configure SSH keys for GitHub
   - Install the `dev` command
   - Set up Claude skills and context

3. **(Optional) Install Pi + message queue extension**:
   ```bash
   npm install -g @mariozechner/pi-coding-agent
   mkdir -p ~/.pi/agent/extensions
   cp ~/projects/cashew/main/pi/extensions/message-queue.ts ~/.pi/agent/extensions/
   ```
   This enables `dev send-pi`, `dev pi-status`, and `dev queue-status`.

That's it. Claude handles the rest.

## How the `dev` Tool Works

`dev` is the control plane for projects, worktrees, and agent sessions. It works with any agent, but the defaults assume:

- **Claude** runs at `~/projects` (hub) and in repo roots for orchestration.
- **Pi** runs in worktrees for long-running implementation (often connected to Codex).

Use `dev hub/claude` to keep a global Claude orchestrator in your projects folder, and `dev <repo>` to start Claude at a repo root when it isn't a worktree repo.

- **New sessions** are created in **tmux**.
- **Existing Zellij sessions** are still discovered and attached for backward compatibility.
- **Session names** use `_` internally, but you type `/` in commands.

### Common Commands

```bash
dev                              # List all projects and sessions
dev hub                          # Hub session at ~/projects
dev hub/claude                   # Claude session at projects root

dev new myapp git@github.com:user/myapp   # Clone with worktree structure
dev myapp                        # Open main worktree (pi auto-starts)
dev myapp/main/claude            # Claude sub-session in main

# Regular (non-worktree) repo
dev myscript                     # Claude auto-starts in repo root
```

### Worktree → Agent Mapping

- `dev <repo>/<worktree>` → **Pi auto-starts** (implementation agent, often Codex-backed)
- `dev <repo>` (non-worktree repo) → **Claude auto-starts** (orchestrator)
- `dev hub/claude` → **Claude in ~/Projects** for cross-repo coordination

You can always create more sessions:

```bash
dev myapp/feature-auth/pi         # Another Pi agent
dev myapp/feature-auth/claude      # Claude in same worktree
dev myapp/feature-auth/tests       # Long-running test session
```

### Feature Development Flow

```bash
dev wt myapp feature-auth        # Create feature branch worktree
dev myapp/feature-auth            # Pi auto-starts in the feature

dev myapp/feature-auth/claude     # Claude helper in the same worktree

# When done, switch back to main Claude for merge
dev myapp/main/claude
```

### Session Management

```bash
dev kill myapp/feature-auth/claude   # Kill specific session
dev kill-all                          # Kill all sessions
```

## Project Structure

```
~/projects/
├── myapp/
│   ├── .bare/           # Git data
│   ├── main/            # Main branch worktree
│   └── feature-auth/    # Feature branch worktree
└── another-project/
    └── ...
```

## Docker Isolation

Each worktree gets fully isolated Docker containers:

```bash
export COMPOSE_PROJECT_NAME="myapp-feature-auth"
docker compose up -d      # Containers: myapp-feature-auth-db, etc.
docker compose down -v    # Clean teardown, only affects this worktree
```

## Claude Workflow

### Main Claude (Orchestrator)
- Explores codebase, plans features
- Creates worktrees for new features
- Merges completed features
- Cleans up worktrees, sessions, and Docker environments

### Feature Claude (Implementer)
- Focuses solely on implementing the feature
- Commits and pushes work
- Signals when ready for merge
- Doesn't worry about cleanup

## What's in This Repo

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
└── README.md
```

## Requirements

- **Node.js** - To install Claude Code
- **macOS or Linux** - Setup skill handles the rest

## License

MIT
