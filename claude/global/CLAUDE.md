# Global Claude Context

## Project Session Management

This environment uses `dev` - a session manager for projects in `~/projects/`.

**Key concepts:**
- Projects use git worktrees: `~/projects/<repo>/<worktree>/` (e.g., `~/projects/replay/main/`)
- Sessions use `_` separator internally but you type `/` (e.g., `dev replay/main/claude`)
- Sub-sessions like `claude`, `server`, `tests` keep long-running processes separate

**Common commands:**
```bash
dev                           # List projects and sessions
dev <repo>                    # Open main worktree session
dev <repo>/<worktree>         # Open specific worktree
dev <repo>/<worktree>/claude  # Claude sub-session
dev wt <repo> <branch>        # Add new worktree
dev kill <session>            # Kill a session
```

## Worktree Workflow

**Your role depends on which worktree you're in:**

### If you're in `main` worktree → You're the orchestrator
- Explore codebase, plan features
- Create worktrees for new features: `dev wt <repo> <feature>`
- After features complete: merge/PR, then full cleanup:
  ```bash
  # 1. Kill Docker environment for the feature
  COMPOSE_PROJECT_NAME=<repo>-<feature> docker compose down -v

  # 2. Kill the Claude session
  dev kill <repo>/<feature>/claude

  # 3. Remove the worktree
  cd ~/projects/<repo> && git worktree remove <feature>
  ```
- You manage the big picture

### If you're in a feature worktree → You're the implementer
- Focus on implementing the feature
- Commit and push your work
- When done, tell the user it's ready for main Claude to merge
- Don't worry about worktree cleanup - main handles that

For full documentation, use the `/dev` skill.

## Isolated Development Environments

**Run EVERYTHING in Docker** - app, services, tests, CI. The entire dev environment is containerized per worktree.

### What runs in Docker
- **App/services**: Web servers, APIs, workers
- **Databases**: Postgres, Redis, etc.
- **Tests/CI**: Run test suites inside containers
- **Build tools**: Compilers, bundlers, linters

The only things on the host are:
- Your code (mounted into containers)
- Docker itself
- Claude

### Naming convention
Use `COMPOSE_PROJECT_NAME=<repo>-<worktree>` to auto-prefix everything:
```bash
export COMPOSE_PROJECT_NAME="replay-main"
docker compose up -d      # All containers prefixed: replay-main-*
docker compose run test   # Tests in isolated container
docker compose down -v    # Clean teardown, only affects this worktree
```

### Docker Compose structure
```yaml
name: ${COMPOSE_PROJECT_NAME:-myapp-main}

services:
  app:
    build: .
    volumes:
      - .:/app
    depends_on: [db, redis]

  db:
    image: postgres:16
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7

  test:
    build: .
    command: npm test
    depends_on: [db, redis]
    profiles: [ci]

volumes:
  pgdata:
```

### Running CI locally
```bash
# Run full CI suite in Docker, isolated to this worktree
docker compose run --rm test
docker compose --profile ci up --abort-on-container-exit
```

### Why full Docker isolation
- Each worktree is a completely independent environment
- No port conflicts, no shared databases, no migration disasters
- `feature-x` can run destructive tests while `main` serves traffic
- Matches CI environment exactly - no "works on my machine"
- Clean teardown: `docker compose down -v` nukes everything for that worktree only

## Git Preferences

- Always use SSH URLs for git remotes (e.g., `git@github.com:user/repo.git`)
- Never use HTTPS URLs which require interactive authentication
