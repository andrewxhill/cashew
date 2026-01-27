# Cashew

A dev environment bootstrap for AI-assisted development with Claude Code and Docker.

## Philosophy

- **Worktree-based development**: Each feature branch gets its own directory via git worktrees
- **Session persistence**: Sessions survive disconnects - SSH in, detach, reconnect anytime
- **Full Docker isolation**: Every worktree runs its own containers - no shared databases, no migration conflicts
- **Claude orchestration**: Main branch Claude manages the project, feature branch Claudes focus on implementation

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

## Usage

Once set up:

New sessions auto-start agents: worktree sessions run `pi`, while non-worktree repo sessions run `claude --dangerously-skip-permissions`.

`dev` uses tmux for new sessions but will still attach to any existing Zellij sessions for backward compatibility.

```bash
dev                              # List all projects and sessions
dev hub                          # Hub session at ~/projects
dev hub/claude                   # Claude session at projects root

dev new myapp git@github.com:user/myapp   # Clone with worktree structure
dev myapp                        # Open main worktree
dev myapp/main/claude            # Claude sub-session
```

### Feature Development

```bash
dev wt myapp feature-auth        # Create feature branch worktree
dev myapp/feature-auth/claude    # Claude in the feature

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
