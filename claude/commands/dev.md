# Dev - Project Session Manager

Use the `dev` command to manage tmux-backed project sessions in `~/projects/`.

**Note:** Session names use `_` internally, but you always type `/` in commands.

**Auto-start:** New worktree sessions start `pi` automatically; non-worktree repo sessions start `claude --dangerously-skip-permissions`.
**Important:** For worktree agents, use `/pi` sub-sessions (not `/claude`) so message tools target the correct agent session.
**Rule:** Never nudge a worktree agent without reading its last message first:
```bash
dev pi-status <session> --messages 1
# optionally check pending queue
dev queue-status <session> -m
```


## Quick Reference

```bash
dev                              # List all projects and active sessions
dev hub                          # Open hub session at ~/projects root
dev hub/<sub>                    # Hub sub-session (e.g., hub/claude)
dev <repo>                       # Open main session for a repo
dev <repo>/<worktree>            # Open specific worktree (for worktree-based repos)
dev <repo>/<worktree>/<sub>      # Open sub-session (prefer /pi for worktrees)
dev new <repo> <git-url>         # Clone repo with worktree structure
dev wt <repo> <branch> [base]    # Add a new worktree for a branch
dev kill <session>               # Kill a specific session
dev kill-all                     # Kill all sessions
dev pi-status <session>          # Check agent status/last messages
dev queue-status <session> -m    # Check pending queue
```

## Project Structure

### Worktree-based repos (recommended)
```
~/projects/<repo>/
├── .bare/           # bare git repository
├── main/            # main branch worktree
├── feature-x/       # feature branch worktree
└── bugfix-y/        # another worktree
```

### Regular repos
```
~/projects/<repo>/
├── .git/
└── (files)
```

## Session Naming Convention

| You Type | Session Name | Use Case |
|----------|--------------|----------|
| `dev hub` | `hub` | Root session at ~/projects |
| `dev hub/claude` | `hub_claude` | Claude sub-session at root |
| `dev myapp` | `myapp` | Regular repo main session |
| `dev myapp/main` | `myapp_main` | Worktree main session |
| `dev myapp/main/pi` | `myapp_main_pi` | Preferred Pi sub-session (worktrees) |
| `dev myapp/main/claude` | `myapp_main_claude` | Claude sub-session |

Common sub-session names:
- `pi` - Preferred worktree agent session
- `claude` - Claude Code (avoid for worktree agents)
- `server` - Dev server
- `tests` - Running tests
- `build` - Build processes

## Workflow Examples

### Using the hub (projects root)
```bash
dev hub                      # session at ~/projects root
dev hub/claude               # claude session for managing projects
```

### Starting a new project
```bash
dev new myapp git@github.com:user/myapp
dev myapp                    # opens main worktree
```

### Working on a feature branch
```bash
dev wt myapp feature-auth    # create worktree
dev myapp/feature-auth       # open session (pi auto-starts)
dev myapp/feature-auth/pi     # preferred pi sub-session
```

### SSH reconnection
```bash
ssh myserver
dev                          # see what's running
dev myapp/main/pi            # reconnect to Pi session (preferred)
```

## Worktree Workflow

Worktree branches are local by default. You do **not** need to push them to a remote just to coordinate. Merge by switching to `main` and merging locally (push only when you actually want a remote branch or PR).

**Main session = orchestrator**, feature sessions = focused implementation.

### Starting a feature
1. In main Claude session, create worktree:
   ```bash
   dev wt <repo> <feature-branch>
   ```
2. User switches to feature session: `dev <repo>/<feature>/pi`
3. Feature Claude: implement, commit, push to remote

### Completing a feature
1. Feature Claude: final commits, push, notify user it's ready
2. User switches back: `dev <repo>/main/pi`
3. Main Claude merges (or creates PR), then full cleanup:
   ```bash
   # Merge the feature (local branch)
   git merge <feature-branch>
   # Push only if you want a remote branch or PR
   # gh pr create ...

   # Full cleanup (in this order):
   # 1. Tear down Docker environment (from worktree directory)
   cd ~/projects/<repo>/<feature-branch>
   COMPOSE_PROJECT_NAME=<repo>-<feature-branch> docker compose down -v

   # 2. Kill the Claude session
   dev kill <repo>/<feature-branch>/pi

   # 3. Remove the worktree and branch
   cd ~/projects/<repo>
   git worktree remove <feature-branch>
   git branch -d <feature-branch>  # if merged
   ```

### Why this pattern?
- **Feature Claude** stays focused on implementation
- **Main Claude** handles integration and project management
- Avoids Claude deleting its own worktree mid-session
- Clean separation of concerns

## Tips

1. Always use sub-sessions for long-running processes (Claude, servers)
2. The session persists even if you close SSH or terminal
3. Use `dev` with no args to see all projects and active sessions
4. Worktree repos let you work on multiple branches simultaneously
5. Main Claude is your "project manager" - use it to orchestrate features
