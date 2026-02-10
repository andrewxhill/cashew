# Pre-Push Gates Reference

The pre-push hook is the last line of defense before code leaves the developer's machine. It runs the full verification suite that mirrors CI, scoped to changed packages for speed. This hook lives at `.husky/pre-push` and is invoked automatically by Git before any `git push` completes.

## Design Principles

- **Mirror CI exactly** -- if it passes locally, it passes in CI. No surprises.
- **Scoped runs for speed** -- only check packages with changes (1-2 minutes for small changes instead of 5-8 for full suite).
- **Full run on main** -- pushing to main always runs the complete suite. No shortcuts on the critical branch.
- **Graceful degradation** -- integration tests and schema drift checks only run if the database is available. Developers without a running database can still push feature branches.
- **Clear diagnostics** -- each check prints a section header, timing, and on failure, the exact command to run to reproduce and fix the issue.
- **Never bypass** -- `--no-verify` is forbidden. Fix the issue, do not skip the gate.

## Gate Summary

| # | Gate | Scope | Conditional |
|---|------|-------|-------------|
| 1 | Remote main not ahead | Branch | Always |
| 2 | No uncommitted changes | Working tree | Always |
| 3 | Environment setup | N/A | Always |
| 4 | Package change detection | Diff | Always |
| 5 | Format check | Full or scoped | Always |
| 6 | Lint | Full or scoped | Always |
| 7 | SQL migration linting | Database package | If database changed |
| 8 | Type check | Full or scoped | Always |
| 9 | Tests with coverage | Full or scoped | Always |
| 10 | Build | Full or scoped | Always |
| 11 | App-specific tests | Per-app | If specific app changed |
| 12 | Integration tests | Full | If DATABASE_URL set |
| 13 | Schema drift detection | Database package | If DATABASE_URL set and database changed |

## Gate Details

### CHECK 1: Remote main not ahead

Fetch `origin/main` and verify the current branch is not behind. If origin/main has commits that are not in the current branch, pushing would create merge conflicts or -- worse -- silent reverts when the branch is eventually merged.

```bash
git fetch origin main --quiet
BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
if [ "$BEHIND" -gt 0 ]; then
  echo "origin/main is $BEHIND commits ahead. Rebase before pushing."
  exit 1
fi
```

**Why this matters**: If feature-B merges before feature-A and both touched the same area, feature-A's push would silently revert feature-B's changes unless feature-A rebases first. This gate prevents that class of bug entirely.

**Fix**: `git fetch origin main && git rebase origin/main`

### CHECK 2: No uncommitted changes

Verify the working tree and index are clean. Uncommitted changes mean the code being pushed does not match the code on disk, which can cause false positives (tests pass against uncommitted fixes) or false negatives (tests fail against uncommitted breakage).

```bash
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Uncommitted changes detected. Commit or stash before pushing."
  exit 1
fi
```

**Fix**: `git stash` or `git add -A && git commit`

### CHECK 3: Environment setup

Load environment variables needed by downstream checks. `DATABASE_URL` is read from `.env.local` if not already set (for integration tests and schema drift). `CI=true` ensures tools behave as they would in CI (no interactive prompts, no color codes that break log parsing). `TERM=dumb` suppresses terminal escape sequences.

```bash
if [ -z "$DATABASE_URL" ] && [ -f .env.local ]; then
  export DATABASE_URL=$(grep '^DATABASE_URL=' .env.local | cut -d'=' -f2-)
fi
export CI=true
export TERM=dumb
```

### CHECK 4: Package change detection

Compare `origin/main...HEAD` to find all changed files. Map each changed path to its package name for scoped Turbo filters. This is the key optimization that makes the hook fast for small changes.

**Path-to-package mapping**:
- `apps/my-app/**` maps to `@scope/my-app`
- `packages/my-lib/**` maps to `@scope/my-lib`
- Root config changes (`turbo.json`, `tsconfig.base.json`, `pnpm-workspace.yaml`, `.github/**`, etc.) trigger `FULL_RUN=1`
- Docs-only changes (only `.md` files outside of `src/`) exit early with success
- Pushing to `main` branch forces `FULL_RUN=1`

The detection reads `package.json` in each changed directory to get the actual npm scope and package name, so it works regardless of naming conventions.

**Fix**: No fix needed -- this is detection, not validation.

### CHECK 5: Format check

Verify all code matches Prettier formatting. In full mode, runs across the entire repo. In scoped mode, runs only against changed packages via Turbo filters.

- **Full**: `pnpm format:check`
- **Scoped**: `turbo run format:check --filter=@scope/changed-pkg`

**Fix**: `pnpm format` (auto-fixes all formatting), then amend or create a new commit.

### CHECK 6: Lint

Run ESLint across all changed packages. Catches code quality issues, unused imports, type-aware lint rules.

- **Full**: `pnpm lint`
- **Scoped**: `turbo run lint --filter=@scope/changed-pkg`

**Fix**: `pnpm lint --fix` for auto-fixable issues, manual fixes for the rest.

### CHECK 7: SQL migration linting (conditional)

Only runs if the database package has changes. Uses the `squawk` SQL linter to catch dangerous migration patterns (e.g., `NOT NULL` without default on existing tables, missing `IF NOT EXISTS`, etc.). A baseline exclusion file skips known issues in legacy migrations so that only new migrations are enforced.

**Fix**: Edit the failing migration SQL to follow safe migration patterns. See squawk documentation for specific rule fixes.

### CHECK 8: Type check

Run the TypeScript compiler in `--noEmit` mode across all changed packages. Catches type errors, missing imports, incorrect function signatures.

- **Full**: `pnpm type-check`
- **Scoped**: `turbo run type-check --filter=@scope/changed-pkg`

**Fix**: Fix the TypeScript errors reported in the output.

### CHECK 9: Tests with coverage

Run the Vitest test suite with coverage collection. Coverage thresholds are enforced per-package via `vitest.config.ts`.

- **Full**: `pnpm test:coverage`
- **Scoped**: `turbo run test:coverage --filter=@scope/changed-pkg`

**Fix**: Fix failing tests. If coverage dropped, add tests for uncovered code paths.

### CHECK 10: Build

Run the full build to ensure all packages compile successfully and produce valid output artifacts. This catches issues that type-check misses (e.g., missing exports, build configuration errors, asset processing failures).

- **Full**: `pnpm build`
- **Scoped**: `turbo run build --filter=@scope/changed-pkg`

**Fix**: Fix the build errors reported in the output.

### CHECK 11: App-specific tests (conditional)

If a specific application was changed, run its dedicated test suite. Some apps have test configurations beyond the standard Vitest run (e.g., Playwright E2E tests, custom integration suites).

```bash
pnpm --filter @scope/my-app test:coverage
```

**Fix**: Fix the failing app-specific tests.

### CHECK 12: Integration tests (conditional)

Only runs if `DATABASE_URL` is set, indicating a running database is available. Runs tests tagged as integration tests that require real database connections, Redis, or other infrastructure.

```bash
pnpm test:integration
```

**Why conditional**: Developers without a running database should still be able to push feature branches. CI always has the database, so integration tests always run there. This is graceful degradation, not a loophole.

**Fix**: Start the database (`podman compose up -d postgres redis`), then fix the failing integration tests.

### CHECK 13: Schema drift detection (conditional)

Only runs if `DATABASE_URL` is set AND the database package has changes. Compares the Drizzle schema definition against the actual database schema to detect drift. Catches the case where a migration was "tested" against a manually-altered local database but the migration itself is broken.

```bash
pnpm --filter @scope/database db:check-drift
```

**Fix**: If drift is detected, either update the schema to match the migration or regenerate the migration with `drizzle-kit generate`.

## Timing Expectations

| Scenario | Expected Duration |
|----------|-------------------|
| Single package change | 1-2 minutes |
| Multiple package changes | 2-4 minutes |
| Full run (pushing to main) | 5-8 minutes |
| With integration tests | Add 1-2 minutes |

## Complete .husky/pre-push Script

```bash
#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Pre-push hook: last line of defense before code leaves the machine.
# Mirrors CI exactly. Scoped to changed packages for speed.
# ============================================================================

HOOK_START=$(date +%s)
ERRORS=()

# Color output (disabled in CI / dumb terminals)
if [ "${TERM:-dumb}" != "dumb" ] && [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  CYAN='\033[0;36m'
  BOLD='\033[1m'
  RESET='\033[0m'
else
  RED='' GREEN='' YELLOW='' CYAN='' BOLD='' RESET=''
fi

header() {
  echo ""
  echo -e "${CYAN}${BOLD}━━━ CHECK $1: $2 ━━━${RESET}"
}

pass() {
  local ELAPSED=$(($(date +%s) - $1))
  echo -e "${GREEN}  PASS${RESET} ($ELAPSED s)"
}

fail() {
  local ELAPSED=$(($(date +%s) - $1))
  echo -e "${RED}  FAIL${RESET} ($ELAPSED s)"
  ERRORS+=("$2")
}

skip() {
  echo -e "${YELLOW}  SKIP${RESET} ($1)"
}

# ============================================================================
# CHECK 1: Remote main not ahead
# ============================================================================
header 1 "Remote main not ahead"
CHECK_START=$(date +%s)

git fetch origin main --quiet 2>/dev/null || true
BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)

if [ "$BEHIND" -gt 0 ]; then
  fail $CHECK_START "origin/main is $BEHIND commits ahead"
  echo -e "${RED}  origin/main is $BEHIND commits ahead of your branch.${RESET}"
  echo -e "${RED}  Rebase before pushing: git fetch origin main && git rebase origin/main${RESET}"
  echo ""
  echo "Aborting push."
  exit 1
else
  pass $CHECK_START
fi

# ============================================================================
# CHECK 2: No uncommitted changes
# ============================================================================
header 2 "No uncommitted changes"
CHECK_START=$(date +%s)

if ! git diff --quiet || ! git diff --cached --quiet; then
  fail $CHECK_START "Uncommitted changes detected"
  echo -e "${RED}  Working tree is dirty. Commit or stash before pushing.${RESET}"
  echo -e "${RED}  Fix: git stash  OR  git add -A && git commit${RESET}"
  echo ""
  echo "Aborting push."
  exit 1
else
  pass $CHECK_START
fi

# ============================================================================
# CHECK 3: Environment setup
# ============================================================================
header 3 "Environment setup"
CHECK_START=$(date +%s)

if [ -z "${DATABASE_URL:-}" ] && [ -f .env.local ]; then
  DB_LINE=$(grep '^DATABASE_URL=' .env.local 2>/dev/null || true)
  if [ -n "$DB_LINE" ]; then
    export DATABASE_URL="${DB_LINE#DATABASE_URL=}"
    echo "  Loaded DATABASE_URL from .env.local"
  fi
fi

export CI=true
export TERM=dumb

if [ -n "${DATABASE_URL:-}" ]; then
  echo "  DATABASE_URL is set (integration tests will run)"
else
  echo "  DATABASE_URL not set (integration tests will be skipped)"
fi

pass $CHECK_START

# ============================================================================
# CHECK 4: Package change detection
# ============================================================================
header 4 "Package change detection"
CHECK_START=$(date +%s)

# Determine the current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "  Branch: $CURRENT_BRANCH"

# Determine if this is a push to main
PUSHING_TO_MAIN=0
if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
  PUSHING_TO_MAIN=1
fi

# Get changed files relative to origin/main
MERGE_BASE=$(git merge-base HEAD origin/main 2>/dev/null || git rev-parse HEAD~1)
CHANGED_FILES=$(git diff --name-only "$MERGE_BASE"...HEAD 2>/dev/null || true)

if [ -z "$CHANGED_FILES" ]; then
  echo "  No changed files detected."
  pass $CHECK_START
  echo ""
  echo -e "${GREEN}${BOLD}All checks passed (no changes to verify).${RESET}"
  exit 0
fi

echo "  Changed files: $(echo "$CHANGED_FILES" | wc -l | tr -d ' ')"

# Check if docs-only change
DOCS_ONLY=1
while IFS= read -r file; do
  case "$file" in
    *.md|docs/*|*.txt|LICENSE|.gitignore)
      ;; # documentation/meta file, continue
    *)
      DOCS_ONLY=0
      break
      ;;
  esac
done <<< "$CHANGED_FILES"

if [ "$DOCS_ONLY" -eq 1 ] && [ "$PUSHING_TO_MAIN" -eq 0 ]; then
  pass $CHECK_START
  echo "  Docs-only change detected. Skipping remaining checks."
  echo ""
  echo -e "${GREEN}${BOLD}All checks passed (docs-only).${RESET}"
  exit 0
fi

# Detect if full run is needed
FULL_RUN=0
ROOT_CONFIG_PATTERNS="turbo.json|tsconfig.base.json|tsconfig.json|pnpm-workspace.yaml|pnpm-lock.yaml|\.github/|\.husky/|\.eslintrc|prettier\.config|vitest\.config|vitest\.workspace"

while IFS= read -r file; do
  if echo "$file" | grep -qE "^($ROOT_CONFIG_PATTERNS)"; then
    FULL_RUN=1
    echo "  Root config changed: $file -> forcing full run"
    break
  fi
done <<< "$CHANGED_FILES"

if [ "$PUSHING_TO_MAIN" -eq 1 ]; then
  FULL_RUN=1
  echo "  Pushing to main -> forcing full run"
fi

# Build list of changed packages (Turbo filter args)
CHANGED_PACKAGES=()
CHANGED_DIRS=()
DATABASE_CHANGED=0

if [ "$FULL_RUN" -eq 0 ]; then
  while IFS= read -r file; do
    PKG_DIR=""
    case "$file" in
      apps/*)
        PKG_DIR=$(echo "$file" | cut -d'/' -f1-2)
        ;;
      packages/*)
        PKG_DIR=$(echo "$file" | cut -d'/' -f1-2)
        ;;
    esac

    if [ -n "$PKG_DIR" ] && [ -f "$PKG_DIR/package.json" ]; then
      # Deduplicate
      if [[ ! " ${CHANGED_DIRS[*]:-} " =~ " $PKG_DIR " ]]; then
        CHANGED_DIRS+=("$PKG_DIR")
        PKG_NAME=$(node -p "require('./$PKG_DIR/package.json').name" 2>/dev/null || true)
        if [ -n "$PKG_NAME" ]; then
          CHANGED_PACKAGES+=("$PKG_NAME")
          echo "  Changed package: $PKG_NAME ($PKG_DIR)"
        fi

        # Track if database package changed
        if echo "$PKG_DIR" | grep -q "database"; then
          DATABASE_CHANGED=1
        fi
      fi
    fi
  done <<< "$CHANGED_FILES"

  if [ ${#CHANGED_PACKAGES[@]} -eq 0 ]; then
    echo "  No package changes detected (root-only files). Forcing full run."
    FULL_RUN=1
  fi
else
  # In full run mode, still detect if database changed
  if echo "$CHANGED_FILES" | grep -q "packages/database"; then
    DATABASE_CHANGED=1
  fi
fi

# Build Turbo filter flags
TURBO_FILTERS=""
if [ "$FULL_RUN" -eq 0 ]; then
  for pkg in "${CHANGED_PACKAGES[@]}"; do
    TURBO_FILTERS="$TURBO_FILTERS --filter=$pkg"
  done
  echo "  Turbo filters:$TURBO_FILTERS"
else
  echo "  Running full suite (no filters)"
fi

pass $CHECK_START

# ============================================================================
# CHECK 5: Format check
# ============================================================================
header 5 "Format check"
CHECK_START=$(date +%s)

if [ "$FULL_RUN" -eq 1 ]; then
  if pnpm format:check; then
    pass $CHECK_START
  else
    fail $CHECK_START "Format check failed"
    echo -e "${RED}  Fix: pnpm format${RESET}"
  fi
else
  if pnpm turbo run format:check $TURBO_FILTERS; then
    pass $CHECK_START
  else
    fail $CHECK_START "Format check failed"
    echo -e "${RED}  Fix: pnpm format${RESET}"
  fi
fi

# ============================================================================
# CHECK 6: Lint
# ============================================================================
header 6 "Lint"
CHECK_START=$(date +%s)

if [ "$FULL_RUN" -eq 1 ]; then
  if pnpm lint; then
    pass $CHECK_START
  else
    fail $CHECK_START "Lint failed"
    echo -e "${RED}  Fix: pnpm lint --fix${RESET}"
  fi
else
  if pnpm turbo run lint $TURBO_FILTERS; then
    pass $CHECK_START
  else
    fail $CHECK_START "Lint failed"
    echo -e "${RED}  Fix: pnpm lint --fix${RESET}"
  fi
fi

# ============================================================================
# CHECK 7: SQL migration linting (conditional)
# ============================================================================
header 7 "SQL migration linting"
CHECK_START=$(date +%s)

if [ "$DATABASE_CHANGED" -eq 1 ]; then
  MIGRATION_DIR="packages/database/migrations"
  if [ -d "$MIGRATION_DIR" ]; then
    # Find new or changed migration files
    CHANGED_MIGRATIONS=$(echo "$CHANGED_FILES" | grep "^$MIGRATION_DIR/.*\.sql$" || true)

    if [ -n "$CHANGED_MIGRATIONS" ]; then
      echo "  Linting changed migrations:"

      SQUAWK_FAILED=0
      while IFS= read -r migration; do
        echo "    $migration"
        # Run squawk with baseline exclusions for legacy migrations
        if [ -f ".squawk-baseline.json" ]; then
          if ! npx squawk "$migration" --exclude-path=.squawk-baseline.json 2>&1; then
            SQUAWK_FAILED=1
          fi
        else
          if ! npx squawk "$migration" 2>&1; then
            SQUAWK_FAILED=1
          fi
        fi
      done <<< "$CHANGED_MIGRATIONS"

      if [ "$SQUAWK_FAILED" -eq 1 ]; then
        fail $CHECK_START "SQL migration lint failed"
        echo -e "${RED}  Fix: Edit migration SQL to follow safe migration patterns${RESET}"
      else
        pass $CHECK_START
      fi
    else
      skip "No changed migration SQL files"
    fi
  else
    skip "No migrations directory found"
  fi
else
  skip "Database package not changed"
fi

# ============================================================================
# CHECK 8: Type check
# ============================================================================
header 8 "Type check"
CHECK_START=$(date +%s)

if [ "$FULL_RUN" -eq 1 ]; then
  if pnpm type-check; then
    pass $CHECK_START
  else
    fail $CHECK_START "Type check failed"
    echo -e "${RED}  Fix: Review TypeScript errors above${RESET}"
  fi
else
  if pnpm turbo run type-check $TURBO_FILTERS; then
    pass $CHECK_START
  else
    fail $CHECK_START "Type check failed"
    echo -e "${RED}  Fix: Review TypeScript errors above${RESET}"
  fi
fi

# ============================================================================
# CHECK 9: Tests with coverage
# ============================================================================
header 9 "Tests with coverage"
CHECK_START=$(date +%s)

if [ "$FULL_RUN" -eq 1 ]; then
  if pnpm test:coverage; then
    pass $CHECK_START
  else
    fail $CHECK_START "Tests failed"
    echo -e "${RED}  Fix: pnpm test to see failures${RESET}"
  fi
else
  if pnpm turbo run test:coverage $TURBO_FILTERS; then
    pass $CHECK_START
  else
    fail $CHECK_START "Tests failed"
    echo -e "${RED}  Fix: pnpm test to see failures${RESET}"
  fi
fi

# ============================================================================
# CHECK 10: Build
# ============================================================================
header 10 "Build"
CHECK_START=$(date +%s)

if [ "$FULL_RUN" -eq 1 ]; then
  if pnpm build; then
    pass $CHECK_START
  else
    fail $CHECK_START "Build failed"
    echo -e "${RED}  Fix: Review build errors above${RESET}"
  fi
else
  if pnpm turbo run build $TURBO_FILTERS; then
    pass $CHECK_START
  else
    fail $CHECK_START "Build failed"
    echo -e "${RED}  Fix: Review build errors above${RESET}"
  fi
fi

# ============================================================================
# CHECK 11: App-specific tests (conditional)
# ============================================================================
header 11 "App-specific tests"
CHECK_START=$(date +%s)

APP_TESTS_RAN=0
if [ "$FULL_RUN" -eq 0 ]; then
  for pkg in "${CHANGED_PACKAGES[@]}"; do
    # Check if this is an app with a dedicated test suite
    for dir in "${CHANGED_DIRS[@]}"; do
      if [[ "$dir" == apps/* ]]; then
        PKG_IN_DIR=$(node -p "require('./$dir/package.json').name" 2>/dev/null || true)
        if [ "$PKG_IN_DIR" = "$pkg" ]; then
          # Check if app has test:coverage script
          HAS_TEST=$(node -p "Boolean(require('./$dir/package.json').scripts?.['test:coverage'])" 2>/dev/null || echo "false")
          if [ "$HAS_TEST" = "true" ]; then
            echo "  Running tests for $pkg"
            APP_TESTS_RAN=1
            if ! pnpm --filter "$pkg" test:coverage; then
              fail $CHECK_START "App tests failed for $pkg"
              echo -e "${RED}  Fix: pnpm --filter $pkg test${RESET}"
            fi
          fi
        fi
      fi
    done
  done
fi

if [ "$APP_TESTS_RAN" -eq 0 ]; then
  skip "No app-specific tests to run"
else
  pass $CHECK_START
fi

# ============================================================================
# CHECK 12: Integration tests (conditional)
# ============================================================================
header 12 "Integration tests"
CHECK_START=$(date +%s)

if [ -n "${DATABASE_URL:-}" ]; then
  # Verify database is reachable before running
  if pg_isready -h localhost -p 5432 -q 2>/dev/null; then
    if pnpm test:integration; then
      pass $CHECK_START
    else
      fail $CHECK_START "Integration tests failed"
      echo -e "${RED}  Fix: pnpm test:integration to see failures${RESET}"
    fi
  else
    skip "DATABASE_URL set but database not reachable"
  fi
else
  skip "DATABASE_URL not set"
fi

# ============================================================================
# CHECK 13: Schema drift detection (conditional)
# ============================================================================
header 13 "Schema drift detection"
CHECK_START=$(date +%s)

if [ -n "${DATABASE_URL:-}" ] && [ "$DATABASE_CHANGED" -eq 1 ]; then
  if pg_isready -h localhost -p 5432 -q 2>/dev/null; then
    DB_PKG_NAME=$(node -p "require('./packages/database/package.json').name" 2>/dev/null || true)
    if [ -n "$DB_PKG_NAME" ]; then
      if pnpm --filter "$DB_PKG_NAME" db:check-drift; then
        pass $CHECK_START
      else
        fail $CHECK_START "Schema drift detected"
        echo -e "${RED}  Fix: Regenerate migration with drizzle-kit generate${RESET}"
        echo -e "${RED}  NEVER alter the database manually.${RESET}"
      fi
    else
      skip "Could not resolve database package name"
    fi
  else
    skip "DATABASE_URL set but database not reachable"
  fi
elif [ -z "${DATABASE_URL:-}" ]; then
  skip "DATABASE_URL not set"
else
  skip "Database package not changed"
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
HOOK_ELAPSED=$(($(date +%s) - HOOK_START))

if [ ${#ERRORS[@]} -gt 0 ]; then
  echo -e "${RED}${BOLD}Pre-push failed (${HOOK_ELAPSED}s). ${#ERRORS[@]} check(s) failed:${RESET}"
  for err in "${ERRORS[@]}"; do
    echo -e "${RED}  - $err${RESET}"
  done
  echo ""
  echo -e "${RED}Fix the issues above and try again. Do NOT use --no-verify.${RESET}"
  exit 1
else
  echo -e "${GREEN}${BOLD}All pre-push checks passed (${HOOK_ELAPSED}s).${RESET}"
  exit 0
fi
```

## Failure Recovery

When a pre-push check fails, Git aborts the push. The hook output tells you exactly which check failed and what command to run to fix it.

### Common failure patterns

**Format check fails**:
```bash
pnpm format           # auto-fix everything
git add -A && git commit -m "style: format"
git push
```

**Lint fails**:
```bash
pnpm lint --fix       # auto-fix what's possible
# Manually fix remaining errors
git add -A && git commit -m "fix: lint errors"
git push
```

**Type check fails**:
```bash
pnpm type-check       # see full error output
# Fix TypeScript errors
git add -A && git commit -m "fix: type errors"
git push
```

**Tests fail**:
```bash
pnpm test             # run in watch mode to iterate
# Fix failing tests
git add -A && git commit -m "fix: failing tests"
git push
```

**Integration tests fail (database not running)**:
```bash
# Start infrastructure
podman compose up -d postgres redis
# Wait for readiness
pg_isready -h localhost -p 5432
# Retry
git push
```

**Schema drift detected**:
```bash
cd packages/database
pnpm drizzle-kit generate  # regenerate migration from schema
# Review the generated SQL
git add -A && git commit -m "fix: regenerate migration"
git push
```

**Origin/main is ahead**:
```bash
git fetch origin main
git rebase origin/main
# Resolve any conflicts
git push
```

## Relationship to CI

The pre-push hook and CI run the same checks. The only differences are:

| Aspect | Pre-push | CI |
|--------|----------|-----|
| Scope | Changed packages only (unless pushing to main) | Full suite always |
| Integration tests | Only if DATABASE_URL is set | Always (database in CI) |
| Schema drift | Only if DATABASE_URL is set and database changed | Always |
| Parallelism | Sequential (single machine) | Parallel jobs |
| Failure cost | Seconds to fix locally | Minutes waiting for CI + context switch |

The goal is to catch everything locally so CI never fails. A green push should mean a green CI run.

## Bypassing (Do Not)

The `--no-verify` flag is **forbidden** in this repository. The CLAUDE.md and global instructions both enforce this. If you are tempted to bypass:

1. The hook is telling you something is broken.
2. Fix the broken thing.
3. If infrastructure is missing (database not running), start it or push from a branch where integration tests are skipped.
4. If you genuinely believe the hook has a false positive, file an issue against the hook itself -- do not bypass it.
