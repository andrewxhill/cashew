# Global Claude Context

## Project Session Management

This environment uses `dev` - a session manager for projects in `~/projects/`.

**Key concepts:**
- Projects use git worktrees: `~/projects/<repo>/<worktree>/` (e.g., `~/projects/replay/main/`)
- Sessions use `_` separator internally but you type `/` (e.g., `dev replay/main/pi`)
- Sub-sessions like `pi`, `server`, `tests` keep long-running processes separate
- Use `/pi` for worktree agents (avoid `/claude` for worktree agent sessions)

**Common commands:**
```bash
dev                           # List projects and sessions
dev <repo>                    # Open main worktree session

dev <repo>/<worktree>         # Open specific worktree (pi auto-starts)
dev <repo>/<worktree>/pi      # Preferred pi sub-session
dev wt <repo> <branch>        # Add new worktree
dev cleanup <repo>/<worktree> # Remove worktree + branch + session
dev kill <session>            # Kill a session
dev pi-status <session>       # Check agent status/last messages
dev queue-status <session> -m # Check pending queue
```

**Rule:** Never nudge a worktree agent without reading its last message first:
```bash
dev pi-status <session> --messages 1
# optional queue check
dev queue-status <session> -m
```

**Before merging or reviewing worktree output:**
```bash
dev review-loop
```
Run the loop manually. Always execute:
```bash
bash sleep 300
```
Run it in the foreground, then return to step 1 and repeat. Do **not** write scripts, nohup, or background loops.

Only review commits once the agent confirms it's done or asks for review.

## Worktree Workflow

Worktree branches are local by default. You do **not** need to push them to remote to coordinate. Merge locally into `main` when ready.

**Your role depends on which worktree you're in:**

### If you're in `main` worktree → You're the orchestrator
- Explore codebase, plan features
- Create worktrees for new features: `dev wt <repo> <feature>`
- After features complete: merge locally, then full cleanup:
  ```bash
  # Merge the feature branch locally
  cd ~/projects/<repo>/main
  git merge <feature>

  # 1. Kill Docker environment for the feature
  COMPOSE_PROJECT_NAME=<repo>-<feature> docker compose down -v

  # 2. Remove worktree + branch + session
  dev cleanup <repo>/<feature>
  ```
- You manage the big picture

### If you're in a feature worktree → You're the implementer
- Focus on implementing the feature
- Commit your work locally
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

### Port conflicts (host bindings)
`COMPOSE_PROJECT_NAME` only prefixes container names; it does **not** change host ports. Avoid hardcoded host bindings like `5432:5432` across worktrees.

**Recommended (env‑configurable ports):**
```yaml
services:
  db:
    ports:
      - "${DB_HOST_PORT:-5432}:5432"
  redis:
    ports:
      - "${REDIS_HOST_PORT:-6379}:6379"
```
Then set per worktree:
```bash
export DB_HOST_PORT=5433
export REDIS_HOST_PORT=6380
export DATABASE_URL="postgres://candles:candles@localhost:${DB_HOST_PORT}/candles"
```

**Alternative:** remove host port bindings entirely and run everything inside the Docker network (preferred for tests/CI).

**Optional scheme:** assign static port offsets per worktree (e.g., `main=5432/6379`, `feature-*=5433+N/6380+N`).

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

## Podman/Docker Machine Safety

**CRITICAL: Never disrupt shared infrastructure.**

- **NEVER restart or stop the Podman machine** (`podman machine stop/restart`) - other critical workloads may be running
- **NEVER stop or remove containers from other projects** - only manage containers in YOUR project's compose namespace
- **Only use `docker compose down`** for your own `COMPOSE_PROJECT_NAME` - never kill containers you didn't create
- If you encounter resource issues, ask the user before taking any action that affects the shared Podman machine

When in doubt, use `docker ps` to see what's running and confirm with the user before stopping anything outside your project scope.

## Replay Monorepo Infrastructure

The replay monorepo runs databases and services locally via Docker/Podman containers.

**CRITICAL: The Podman machine is shared across ALL projects. NEVER stop or restart it.**

### Starting Infrastructure

```bash
# Check if Podman machine is running
/opt/podman/bin/podman machine list

# If Podman machine is not running, start it (this is SAFE - it doesn't affect other containers)
/opt/podman/bin/podman machine start

# ❌ NEVER DO THIS - other projects depend on the running machine:
# /opt/podman/bin/podman machine stop
# /opt/podman/bin/podman machine rm

# Start databases from the repo root
cd ~/projects/replay/main
/opt/podman/bin/podman compose up -d postgres redis

# Verify databases are running
/opt/podman/bin/podman ps
pg_isready -h localhost -p 5432
```

### Required Services for Tests

| Service | Port | Required For |
|---------|------|--------------|
| PostgreSQL (TimescaleDB) | 5432 | Integration tests, schema drift checks |
| Redis | 6379 | Some integration tests, caching |

### Checking Service Health

```bash
# PostgreSQL
pg_isready -h localhost -p 5432

# Redis
redis-cli ping

# All containers
/opt/podman/bin/podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Common Issues

**Integration tests fail with ECONNREFUSED:5432**
- PostgreSQL isn't running
- Fix: `/opt/podman/bin/podman compose up -d postgres`

**Podman can't connect**
- Podman machine isn't running
- Fix: `/opt/podman/bin/podman machine start`

**Pre-push hook fails on integration tests**
- DATABASE_URL is set but database isn't running
- Fix: Start the database containers before pushing

## Git Preferences

- Never use HTTPS URLs which require interactive authentication

### CRITICAL: Never Bypass Git Hooks

**NEVER use `--no-verify` on commit or push. No exceptions. No rationalizations.**

```bash
# ❌ FORBIDDEN - These commands are NEVER acceptable
git commit --no-verify
git push --no-verify
git commit -n  # -n is shorthand for --no-verify

# ✅ CORRECT - Fix what the hooks are telling you
# If pre-commit fails: fix lint/format/type errors
# If pre-push fails: fix failing tests
```

**Why this matters:**
- Hooks exist to catch problems BEFORE they reach the repository
- A failing hook is telling you something is broken that YOU need to fix
- Bypassing hooks creates broken commits that waste everyone's time
- "It works on my machine" is not an excuse - fix the tests

**When hooks fail:**
1. Read the error output carefully
2. Fix the underlying issue (lint, types, tests, etc.)
3. Re-run the commit/push
4. If tests require infrastructure (database, Redis), ensure it's running
5. If you're stuck, ask for help - but NEVER bypass
