# Dev - Project Session Manager

Use the `dev` command to manage Zellij sessions for projects in `~/projects/`.

**Note:** Session names use `_` internally (Zellij limitation), but you always type `/` in commands.

## Quick Reference

```bash
dev                              # List all projects and active sessions
dev hub                          # Open hub session at ~/projects root
dev hub/<sub>                    # Hub sub-session (e.g., hub/claude)
dev <repo>                       # Open main session for a repo
dev <repo>/<worktree>            # Open specific worktree (for worktree-based repos)
dev <repo>/<worktree>/<sub>      # Open sub-session (e.g., claude, server, tests)
dev new <repo> <git-url>         # Clone repo with worktree structure
dev wt <repo> <branch> [base]    # Add a new worktree for a branch
dev kill <session>               # Kill a specific session
dev kill-all                     # Kill all Zellij sessions
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

| You Type | Zellij Session | Use Case |
|----------|----------------|----------|
| `dev hub` | `hub` | Root session at ~/projects |
| `dev hub/claude` | `hub_claude` | Claude sub-session at root |
| `dev myapp` | `myapp` | Regular repo main session |
| `dev myapp/main` | `myapp_main` | Worktree main session |
| `dev myapp/main/claude` | `myapp_main_claude` | Sub-session for Claude |

Common sub-session names:
- `claude` - Running Claude Code
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
dev myapp/feature-auth       # open session
dev myapp/feature-auth/claude # claude sub-session
```

### SSH reconnection
```bash
ssh myserver
dev                          # see what's running
dev myapp/main/claude        # reconnect to Claude session
# Ctrl+o d to detach
```

## Zellij Keybindings

- `Ctrl+o d` - Detach from session (keeps it running)
- `Ctrl+o w` - Session manager
- `Ctrl+p n` - New pane
- `Ctrl+t n` - New tab

## Worktree Workflow

**Main session = orchestrator**, feature sessions = focused implementation.

### Starting a feature
1. In main Claude session, create worktree:
   ```bash
   dev wt <repo> <feature-branch>
   ```
2. User switches to feature session: `dev <repo>/<feature>/claude`
3. Feature Claude: implement, commit, push to remote

### Completing a feature
1. Feature Claude: final commits, push, notify user it's ready
2. User switches back: `dev <repo>/main/claude`
3. Main Claude merges (or creates PR), then full cleanup:
   ```bash
   # Merge the feature
   git fetch origin
   git merge origin/<feature-branch>
   # Or create PR: gh pr create ...

   # Full cleanup (in this order):
   # 1. Tear down Docker environment (from worktree directory)
   cd ~/projects/<repo>/<feature-branch>
   COMPOSE_PROJECT_NAME=<repo>-<feature-branch> docker compose down -v

   # 2. Kill the Claude session
   dev kill <repo>/<feature-branch>/claude

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
