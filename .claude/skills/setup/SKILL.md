---
name: setup
description: >
  Bootstrap the Cashew dev environment on this machine. Use this skill whenever
  the user says "set up cashew", "bootstrap my environment", or anything about
  initial setup. If the user is in this repo and asking for setup, they have
  everything they need — just run the steps.
---

# Setup - Bootstrap Dev Environment

You are running from inside the cashew repo. This IS cashew. Setup means:
pull the latest, symlink everything into place, and install Pi extensions.

## End State

| Component | Location | Purpose |
|-----------|----------|---------|
| dev script | `/usr/local/bin/dev` → `bin/dev` | Project session manager |
| cashew launcher | `/usr/local/bin/cashew` → `bin/cashew` | tmux + fzf TUI launcher |
| Global Claude config | `~/.claude/CLAUDE.md` | Cashew context block appended |
| /dev command | `~/.claude/commands/dev.md` → `claude/commands/dev.md` | Session manager docs |
| /prompting-worktree-agents | `~/.claude/skills/prompting-worktree-agents/` → `claude/skills/prompting-worktree-agents/` | Socratic prompting for worktree agents |
| /repo-quality-rails-setup | `~/.claude/skills/repo-quality-rails-setup/` → `claude/skills/repo-quality-rails-setup/` | Optional quality rails setup |
| Pi extensions | `~/.pi/agent/extensions/` → `pi/extensions/` | message-queue, pi-subscribe, kw-role |
| Projects folder | `~/<user-choice>` | Where all projects live |

Everything is symlinked back to this repo. `git pull` updates the whole machine.

## Step 1: Ask the User

Use the AskUserQuestion tool to ask:

1. **What should your projects folder be called?** (default: `~/projects`)
2. **Install the optional Repo Quality Rails skill?** (sets up quality gates for repos)

## Step 2: Pull Latest

```bash
git pull
```

## Step 3: Create Projects Directory

```bash
mkdir -p ~/<projects-folder>
```

## Step 4: Symlink Binaries

```bash
CASHEW_ROOT="$(git rev-parse --show-toplevel)"
sudo ln -sf "$CASHEW_ROOT/bin/dev" /usr/local/bin/dev
sudo ln -sf "$CASHEW_ROOT/bin/cashew" /usr/local/bin/cashew
```

## Step 5: Install Claude Config and Skills

Append the Cashew context block to `~/.claude/CLAUDE.md` if it's not already
there. Idempotent — running it twice won't duplicate the block.

The setup skill itself is NOT symlinked. It lives in `.claude/skills/` and is
only available when Claude is in this repo.

```bash
CASHEW_ROOT="$(git rev-parse --show-toplevel)"
mkdir -p ~/.claude/commands ~/.claude/skills
TARGET=~/.claude/CLAUDE.md

if ! grep -q "BEGIN CASHEW GLOBAL CONTEXT" "$TARGET" 2>/dev/null; then
  {
    echo ""
    echo "<!-- BEGIN CASHEW GLOBAL CONTEXT -->"
    sed "s|<cashew-root>|$CASHEW_ROOT|g" "$CASHEW_ROOT/claude/global/CLAUDE.md"
    echo "<!-- END CASHEW GLOBAL CONTEXT -->"
  } >> "$TARGET"
fi

# Global command
ln -sf "$CASHEW_ROOT/claude/commands/dev.md" ~/.claude/commands/dev.md

# Global skills
ln -sf "$CASHEW_ROOT/claude/skills/prompting-worktree-agents" ~/.claude/skills/prompting-worktree-agents

# Optional: Repo Quality Rails (only if user opted in during Step 1)
ln -sf "$CASHEW_ROOT/claude/skills/repo-quality-rails-setup" ~/.claude/skills/repo-quality-rails-setup
```

## Step 6: Install Pi Extensions

Pi must be installed (`npm install -g @mariozechner/pi-coding-agent`). If `pi`
isn't on the PATH, install it first.

These extensions enable `dev send-pi` messaging, pub/sub coordination, and
knowledge worker roles. Symlinked so `git pull` updates them.

```bash
CASHEW_ROOT="$(git rev-parse --show-toplevel)"

# Install Pi if missing
command -v pi || npm install -g @mariozechner/pi-coding-agent

mkdir -p ~/.pi/agent/extensions
ln -sf "$CASHEW_ROOT/pi/extensions/message-queue.ts" ~/.pi/agent/extensions/message-queue.ts
ln -sf "$CASHEW_ROOT/pi/extensions/pi-subscribe.ts" ~/.pi/agent/extensions/pi-subscribe.ts
ln -sf "$CASHEW_ROOT/pi/extensions/kw-role.ts" ~/.pi/agent/extensions/kw-role.ts
```

## Step 7: Verify

Report what passed/failed — don't run silently.

```bash
dev --help
pi --version
ls -l ~/.pi/agent/extensions/
ls -l ~/.claude/commands/dev.md
ls -l ~/.claude/skills/prompting-worktree-agents
```

## Step 8: Tell the User What to Do Next

After verification, walk the user through how to start using Cashew:

1. **Go to your projects folder:**
   ```bash
   cd ~/<projects-folder>
   ```

2. **Bootstrap initial sessions** (creates hub and baseline sessions):
   ```bash
   dev reboot
   ```

3. **Or start a new project** — run Claude from the projects folder and ask it
   to use `dev` to set up a repo. It will clone, configure worktrees, and
   create sessions:
   ```bash
   claude
   # "Use dev to set up git@github.com:user/myapp"
   ```

4. **Talk to a project's PM** — each project has a Claude session on `main`
   that acts as the orchestrator:
   ```bash
   dev <project>/main/claude
   ```

5. **Tell the PM what to build** — the PM uses the `/dev` command to create
   worktrees, task and monitor worktree agents, and bootstrap knowledge workers.

6. **Drop in anytime** — use `dev` to rejoin any session. Attach to a worktree
   agent to interact directly, check on a knowledge worker, or rejoin the PM
   to continue planning:
   ```bash
   dev                              # see everything running
   dev <project>/main/claude        # rejoin PM
   dev <project>/<feature>/pi       # drop into a worktree agent
   dev <project>/main/kw-<name>     # check on a knowledge worker
   ```
