# Dev - Project Session Manager

Use the `dev` command to manage tmux-backed project sessions in `~/projects/`.

**Note:** Session names use `_` internally, but you always type `/` in commands.

**Auto-start:** New sessions start their auto-command (`pi` for worktrees, `claude` for regular repos) automatically.
**Detached by default:** Creating a new session always creates it detached and prints how to attach. Running `dev` against an existing session attaches to it. This means agents can safely create sessions without needing a terminal.
**Pi runs in sub-sessions:** Pi always runs in `/pi` sub-sessions (e.g., `dev repo/worktree/pi`), not the base session. This is consistent across `dev wt`, `dev reboot`, and manual session creation.
**Important:** For worktree agents, use `/pi` sub-sessions (not `/claude`) so message tools target the correct agent session.
**Rule:** Never nudge a worktree agent without reading its last message first:
```bash
dev pi-status <session> --messages 1
# optionally check pending queue
dev queue-status <session> -m
# if you need to wait for completion
dev pi-subscribe <session> -f
```

**Messaging rule:** Use `dev send-pi <session> <message>` to queue messages for worktree Pi agents. Only use `dev send` for raw tmux key input when you explicitly need keystrokes (e.g., Enter/Ctrl-C).


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
dev cleanup <repo>/<worktree>    # Remove worktree + branch + session (requires --force if unmerged)
dev kill <session>               # Kill a specific session
dev kill-all                     # Kill all sessions
dev kw <repo> <name>             # Start a knowledge-worker session
dev kw-list [repo]               # List knowledge workers
dev kw-tags <repo>/<name> <tags> # Set knowledge-worker tags
dev kw-note <repo>/<name> <note> # Set knowledge-worker note
dev pi-status <session>          # Check agent status/last messages
dev queue-status <session> -m    # Check pending queue
dev pi-subscribe <session>       # Wait for the next completion entry (default)
dev pi-subscribe <session> -f    # Follow final agent messages (done events)
dev pi-subscribe <session> --last # Show the last completion and exit
dev send <session> <keys>        # Send raw tmux keys (direct input)
dev send-pi <session> <message>  # Queue a message for a Pi agent (preferred)
dev send-pi <session> --await "..." # Send and wait for next completion
dev reboot [--dry-run]           # Recreate baseline sessions after reboot
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
| `dev myapp/main/kw-arch` | `myapp_main_kw-arch` | Knowledge-worker session |

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
dev wt myapp feature-auth    # create worktree + start pi in /pi sub-session (detached)
dev myapp/feature-auth/pi    # attach to pi sub-session
```

### SSH reconnection
```bash
ssh myserver
dev                          # see what's running
dev myapp/main/pi            # attach to existing Pi session
```

## Worktree Workflow

Worktree branches are local by default. You do **not** need to push them to a remote just to coordinate. Merge by switching to `main` and merging locally.

**Main session = orchestrator**, feature sessions = focused implementation.

### Starting a feature
1. In main Claude session, create worktree (pi starts detached in `/pi` sub-session):
   ```bash
   dev wt <repo> <feature-branch>
   # Output: pi started in session: dev <repo>/<feature-branch>/pi (detached)
   ```
2. User attaches to feature session: `dev <repo>/<feature-branch>/pi`
3. Feature Claude: implement and commit locally

### Completing a feature
1. Feature Claude: final commits, notify user it's ready
2. User switches back: `dev <repo>/main/pi`
3. Main Claude merges locally, then full cleanup:
   ```bash
   # Merge the feature (local branch)
   git merge <feature-branch>

   # Full cleanup (in this order):
   # 1. Tear down Docker environment (from worktree directory)
   cd ~/projects/<repo>/<feature-branch>
   COMPOSE_PROJECT_NAME=<repo>-<feature-branch> docker compose down -v

   # 2. Remove worktree + branch + session
   # Run without --force first. If warned about commits not in main,
   # decide whether the branch was merged or should be discarded, then re-run with --force if needed.
   dev cleanup <repo>/<feature-branch>
   ```

### Why this pattern?
- **Feature Claude** stays focused on implementation
- **Main Claude** handles integration and project management
- Avoids Claude deleting its own worktree mid-session
- Clean separation of concerns

## Knowledge Workers (long-running domain agents)
Knowledge workers are persistent Pi sessions anchored on `main` that focus on design, review, risk analysis, and planning.
They are **not** PM or worktree implementation agents.
(Requires the `kw-role` extension for role reminders and `/kw-*` commands.)

**Start one (uses default bootstrap if omitted):**
```bash
dev kw <repo> <name> --tags "arch,api"
# or override with a custom bootstrap
dev kw <repo> <name> --tags "arch,api" --bootstrap "Review auth architecture and keep a running design guide."
```

**List them:**
```bash
dev kw-list <repo>
```

**Update metadata (from shell):**
```bash
dev kw-tags <repo>/<name> "arch,api"
dev kw-note <repo>/<name> "Owns auth architecture and cross-service contracts"
```

**Update metadata (inside the kw session):**
```
/kw-tags arch,api
/kw-note Owns auth architecture and cross-service contracts
```
(If a KW includes `/kw-tags` or `/kw-note` in a response, the kw-role extension will apply it automatically.)

**Message + wait (PM usage examples):**
```bash
# Ask for design guidance
dev send-pi <repo>/main/kw-<name> "Given this plan, where are the architecture risks and what constraints must we respect?"
# Ask for QA lens
dev send-pi <repo>/main/kw-<name> "Review this change for data-timeliness risks and missing checks."
# Send + wait in one call
dev send-pi <repo>/main/kw-<name> --await "Review the plan and respond with risks."
# Wait for the next completion (default)
dev pi-subscribe <repo>/main/kw-<name>
# Show the last completion
dev pi-subscribe <repo>/main/kw-<name> --last
# Or follow all completions
dev pi-subscribe <repo>/main/kw-<name> -f
```

**PM workflow (example):**
1. PM drafts plan or change proposal.
2. PM asks KW for design risks + QA lens.
3. KW responds with constraints/tests/edge cases.
4. PM adapts plan and sends guidance to worktree agent.

**Role boundaries:**
- Knowledge workers are on-demand advisors, not proactive monitors. They answer PM/agent questions.
- No worktree creation/cleanup, no merges, no destructive dev commands.
- Provide guidance, reviews, and plans. If asked to implement, answer with advice and a safe plan instead.

## Reviewing a worktree agent (do this before merging)

Use the **review loop** from the PM session:
```bash
dev review-loop
```

Important: execute the loop manually. The last step must be:
```bash
bash sleep 300
```
Run it in the foreground, then return to step 1 and repeat. Do **not** write scripts, nohup, or background loops.

Quick version:
1. Read the agent's latest message so you don't merge mid-stream:
   ```bash
   dev pi-status <session> --messages 1
   dev queue-status <session> -m
   dev pi-subscribe <session> -f
   ```
2. Check for session requirements/notes if they were set:
   ```bash
   dev requirements <session>
   ```
3. If the agent asked for feedback or is mid-task, reply before merging. Only review commits once the agent says it's complete.

## Tips

1. Always use sub-sessions for long-running processes (Claude, servers)
2. Use `dev send-pi <session> <message>` when messaging worktree agents; it queues safely. Use `dev send` only for raw keystrokes.
3. After reboot, run `dev reboot` to recreate baseline sessions (hub pi/claude, repo main pi/claude, feature worktree pi).
4. `dev cleanup` now blocks if the branch has commits not in main; re-run with `--force` only after deciding it's safe to discard.
5. The session persists even if you close SSH or terminal (until reboot)
6. Use `dev` with no args to see all projects and active sessions
7. Worktree repos let you work on multiple branches simultaneously
8. Main Claude is your "project manager" - use it to orchestrate features
