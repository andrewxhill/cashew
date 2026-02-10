# Pre-Commit Gates: Husky + lint-staged in a TypeScript Monorepo

This is a complete, copy-paste-able guide for setting up pre-commit hooks using Husky and lint-staged in a pnpm-based TypeScript monorepo with Turbo. It covers 12 gates that run on every commit: auto-formatting, linting, type-checking, testing, secret detection, changeset enforcement, and more.

## 1. Husky Setup

Install Husky and initialize the hooks directory:

```bash
pnpm add -D husky && pnpm exec husky
```

This creates the `.husky/` directory at the repo root.

Add the `prepare` script to your root `package.json` so Husky installs automatically after `pnpm install`:

```json
{
  "scripts": {
    "prepare": "husky"
  }
}
```

Create the pre-commit hook file:

```bash
touch .husky/pre-commit
chmod +x .husky/pre-commit
```

## 2. lint-staged Configuration

Create `lint-staged.config.mjs` at the repo root:

```js
export default {
  "**/*.{ts,tsx,js,jsx,mjs,cjs}": ["prettier --write"],
  "**/*.{json,md,yml,yaml}": ["prettier --write"],
};
```

Install lint-staged:

```bash
pnpm add -D lint-staged
```

lint-staged runs Prettier on staged files and automatically re-stages them after formatting. This means developers never need to manually run Prettier -- the hook handles it.

## 3. Complete Pre-Commit Hook Script

This is the full `.husky/pre-commit` script. It runs all gates sequentially (with parallelization where noted) and provides clear output for each gate.

```bash
#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# Colors and helpers
# ─────────────────────────────────────────────────────────────
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

pass()    { echo -e "${GREEN}✓${NC} $1"; }
fail()    { echo -e "${RED}✗${NC} $1"; }
warn()    { echo -e "${YELLOW}⚠${NC} $1"; }
info()    { echo -e "${CYAN}→${NC} $1"; }

# Collect staged files once (performance: avoids repeated git calls)
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)
STAGED_TS_FILES=$(echo "$STAGED_FILES" | grep -E '\.(ts|tsx)$' || true)
STAGED_JS_ALL=$(echo "$STAGED_FILES" | grep -E '\.(ts|tsx|js|jsx|mjs|cjs)$' || true)

# ─────────────────────────────────────────────────────────────
# Gate 0: lint-staged (auto-format staged files)
# ─────────────────────────────────────────────────────────────
info "Gate 0: lint-staged (auto-format)"
pnpm exec lint-staged || {
  fail "Gate 0: lint-staged failed"
  exit 1
}
pass "Gate 0: lint-staged"

# ─────────────────────────────────────────────────────────────
# Gate 0.25: Stub file detection
# ─────────────────────────────────────────────────────────────
info "Gate 0.25: Stub file detection"
STUB_FILES=$(echo "$STAGED_FILES" \
  | grep -E '(stub|stubs)\.(ts|tsx|js|jsx)$' \
  | grep -v '__tests__/' \
  | grep -v '__mocks__/' \
  | grep -v '\.test\.' \
  | grep -v '\.spec\.' \
  || true)

if [ -n "$STUB_FILES" ]; then
  fail "Gate 0.25: Stub files detected in production code:"
  echo "$STUB_FILES" | while read -r f; do echo "  $f"; done
  echo ""
  echo "Stub files belong in __tests__/, __mocks__/, or *.test.ts only."
  exit 1
fi
pass "Gate 0.25: No stub files in production code"

# ─────────────────────────────────────────────────────────────
# Gate 0.5: Stale lock file detection
# ─────────────────────────────────────────────────────────────
info "Gate 0.5: Stale lock file detection"
PKG_JSON_CHANGED=$(echo "$STAGED_FILES" | grep -E '^package\.json$|/package\.json$' || true)

if [ -n "$PKG_JSON_CHANGED" ]; then
  # Check if any dependency fields changed in the staged package.json files
  DEPS_CHANGED=false
  for pkg in $PKG_JSON_CHANGED; do
    DIFF=$(git diff --cached -- "$pkg" | grep -E '^\+.*"(dependencies|devDependencies|peerDependencies|optionalDependencies)"' || true)
    if [ -n "$DIFF" ]; then
      DEPS_CHANGED=true
      break
    fi
  done

  if [ "$DEPS_CHANGED" = true ]; then
    LOCK_STAGED=$(echo "$STAGED_FILES" | grep -E '^pnpm-lock\.yaml$' || true)
    if [ -z "$LOCK_STAGED" ]; then
      fail "Gate 0.5: package.json dependency fields changed but pnpm-lock.yaml is not staged."
      echo "  Run 'pnpm install' and stage pnpm-lock.yaml."
      exit 1
    fi
  fi
fi
pass "Gate 0.5: Lock file is consistent"

# ─────────────────────────────────────────────────────────────
# Gates 1-3: Parallel execution (lint, type-check, actionlint)
# ─────────────────────────────────────────────────────────────
info "Gates 1-3: Running lint, type-check, and actionlint in parallel"

pids=()
gate_names=()
tmpdir=$(mktemp -d)

# Gate 1: GitHub Actions workflow lint (conditional)
WORKFLOW_FILES=$(echo "$STAGED_FILES" | grep -E '^\.github/workflows/.*\.ya?ml$' || true)
if [ -n "$WORKFLOW_FILES" ]; then
  if command -v actionlint &>/dev/null; then
    (
      actionlint $WORKFLOW_FILES > "$tmpdir/gate1.log" 2>&1
    ) &
    pids+=($!)
    gate_names+=("Gate 1: actionlint")
  else
    warn "Gate 1: actionlint not installed, skipping workflow lint"
  fi
else
  pass "Gate 1: No workflow files changed, skipping"
fi

# Gate 2: ESLint (affected packages only)
(
  pnpm turbo lint --filter='...[HEAD^1]' --output-logs=errors-only > "$tmpdir/gate2.log" 2>&1
) &
pids+=($!)
gate_names+=("Gate 2: ESLint")

# Gate 3: TypeScript type-check (affected packages only)
(
  pnpm turbo type-check --filter='...[HEAD^1]' --output-logs=errors-only > "$tmpdir/gate3.log" 2>&1
) &
pids+=($!)
gate_names+=("Gate 3: TypeScript type-check")

# Wait for all parallel gates
PARALLEL_FAILED=false
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    fail "${gate_names[$i]} failed:"
    cat "$tmpdir/gate$((i+1)).log" 2>/dev/null || true
    PARALLEL_FAILED=true
  else
    pass "${gate_names[$i]}"
  fi
done

rm -rf "$tmpdir"

if [ "$PARALLEL_FAILED" = true ]; then
  fail "One or more parallel gates failed"
  exit 1
fi

# ─────────────────────────────────────────────────────────────
# Gate 3.5: Database migration linting (conditional)
# ─────────────────────────────────────────────────────────────
info "Gate 3.5: Database migration lint"
DB_FILES=$(echo "$STAGED_FILES" | grep -E '^packages/database/' || true)

if [ -n "$DB_FILES" ]; then
  MIGRATION_FILES=$(echo "$DB_FILES" | grep -E 'migrations/' || true)
  if [ -n "$MIGRATION_FILES" ]; then
    # Check migration file naming convention: NNNN_description.ts or NNNN_description.sql
    for mig in $MIGRATION_FILES; do
      basename=$(basename "$mig")
      if ! echo "$basename" | grep -qE '^[0-9]{4}_[a-z0-9_-]+\.(ts|sql)$'; then
        fail "Gate 3.5: Migration file has invalid name: $basename"
        echo "  Expected format: 0001_description.ts or 0001_description.sql"
        exit 1
      fi
    done

    # Check for destructive operations in migrations
    for mig in $MIGRATION_FILES; do
      DESTRUCTIVE=$(git diff --cached -- "$mig" | grep -iE '^\+.*(DROP TABLE|DROP COLUMN|TRUNCATE)' || true)
      if [ -n "$DESTRUCTIVE" ]; then
        warn "Gate 3.5: Destructive operation detected in $mig:"
        echo "$DESTRUCTIVE"
        echo "  Make sure this is intentional and has a rollback plan."
      fi
    done
  fi

  # Check for schema changes that need a migration
  SCHEMA_CHANGED=$(echo "$DB_FILES" | grep -E 'schema\.(ts|js)$' || true)
  if [ -n "$SCHEMA_CHANGED" ] && [ -z "$MIGRATION_FILES" ]; then
    warn "Gate 3.5: Schema files changed but no migration files staged."
    echo "  If this is a schema change, run 'drizzle-kit generate' to create a migration."
  fi

  pass "Gate 3.5: Database migration lint"
else
  pass "Gate 3.5: No database files changed, skipping"
fi

# ─────────────────────────────────────────────────────────────
# Gate 4: Unit tests (affected packages only)
# ─────────────────────────────────────────────────────────────
info "Gate 4: Unit tests"
pnpm turbo test --filter='...[HEAD^1]' --output-logs=errors-only || {
  fail "Gate 4: Unit tests failed"
  exit 1
}
pass "Gate 4: Unit tests"

# ─────────────────────────────────────────────────────────────
# Gate 5: console.log detection (WARNING only)
# ─────────────────────────────────────────────────────────────
info "Gate 5: console.log detection"
if [ -n "$STAGED_TS_FILES" ]; then
  CONSOLE_LOGS=$(echo "$STAGED_TS_FILES" \
    | grep -v '\.test\.' \
    | grep -v '\.spec\.' \
    | xargs grep -n 'console\.log' 2>/dev/null \
    || true)

  if [ -n "$CONSOLE_LOGS" ]; then
    warn "Gate 5: console.log statements found (not blocking):"
    echo "$CONSOLE_LOGS" | head -20
    CONSOLE_COUNT=$(echo "$CONSOLE_LOGS" | wc -l | tr -d ' ')
    if [ "$CONSOLE_COUNT" -gt 20 ]; then
      echo "  ... and $((CONSOLE_COUNT - 20)) more"
    fi
    echo "  Consider removing console.log before pushing."
  else
    pass "Gate 5: No console.log statements"
  fi
else
  pass "Gate 5: No TS/TSX files staged"
fi

# ─────────────────────────────────────────────────────────────
# Gate 6: Secret detection (ERROR)
# ─────────────────────────────────────────────────────────────
info "Gate 6: Secret detection"
if [ -n "$STAGED_FILES" ]; then
  # Search staged diffs for secret patterns
  SECRETS=$(git diff --cached -U0 \
    | grep -inE '^\+.*(password|secret|api_key|token|credential)\s*=\s*["\x27]' \
    | grep -v '^\+\+\+' \
    | grep -v '\.test\.' \
    | grep -v '__tests__' \
    | grep -v '\.example' \
    | grep -v '\.template' \
    | grep -v 'placeholder' \
    | grep -v 'CHANGE_ME' \
    | grep -v 'your_.*_here' \
    || true)

  if [ -n "$SECRETS" ]; then
    fail "Gate 6: Possible secrets detected in staged changes:"
    echo "$SECRETS" | head -10
    echo ""
    echo "  If these are not real secrets, use a .env file or config template."
    echo "  NEVER commit real credentials to the repository."
    exit 1
  fi
fi
pass "Gate 6: No secrets detected"

# ─────────────────────────────────────────────────────────────
# Gate 7: `any` type detection (WARNING only)
# ─────────────────────────────────────────────────────────────
info "Gate 7: \`any\` type detection"
if [ -n "$STAGED_TS_FILES" ]; then
  ANY_TYPES=$(echo "$STAGED_TS_FILES" \
    | grep -v '\.test\.' \
    | grep -v '\.spec\.' \
    | grep -v '\.d\.ts$' \
    | xargs grep -n ': any' 2>/dev/null \
    || true)

  if [ -n "$ANY_TYPES" ]; then
    ANY_COUNT=$(echo "$ANY_TYPES" | wc -l | tr -d ' ')
    warn "Gate 7: Found $ANY_COUNT instance(s) of \`: any\` (not blocking):"
    echo "$ANY_TYPES" | head -10
    if [ "$ANY_COUNT" -gt 10 ]; then
      echo "  ... and $((ANY_COUNT - 10)) more"
    fi
    echo "  Consider using a specific type instead of \`any\`."
  else
    pass "Gate 7: No \`any\` types found"
  fi
else
  pass "Gate 7: No TS/TSX files staged"
fi

# ─────────────────────────────────────────────────────────────
# Gate 8: Test assertion density (WARNING only)
# ─────────────────────────────────────────────────────────────
info "Gate 8: Test assertion density"
STAGED_TEST_FILES=$(echo "$STAGED_TS_FILES" | grep -E '\.test\.(ts|tsx)$' || true)

if [ -n "$STAGED_TEST_FILES" ]; then
  LOW_DENSITY=false
  for testfile in $STAGED_TEST_FILES; do
    if [ ! -f "$testfile" ]; then
      continue
    fi
    LINE_COUNT=$(wc -l < "$testfile" | tr -d ' ')
    EXPECT_COUNT=$(grep -c 'expect(' "$testfile" 2>/dev/null || echo "0")

    if [ "$LINE_COUNT" -gt 50 ] && [ "$EXPECT_COUNT" -lt 3 ]; then
      warn "Gate 8: Low assertion density in $testfile ($LINE_COUNT lines, $EXPECT_COUNT expects)"
      LOW_DENSITY=true
    fi
  done

  if [ "$LOW_DENSITY" = false ]; then
    pass "Gate 8: Test assertion density OK"
  else
    echo "  Tests with many lines but few assertions may not be testing enough."
  fi
else
  pass "Gate 8: No test files staged"
fi

# ─────────────────────────────────────────────────────────────
# Gate 9: Coverage gaming prevention (ERROR)
# ─────────────────────────────────────────────────────────────
info "Gate 9: Coverage gaming prevention"
VITEST_CONFIGS=$(echo "$STAGED_FILES" | grep -E 'vitest\.config\.(ts|js|mts|mjs)$' || true)

if [ -n "$VITEST_CONFIGS" ]; then
  for config in $VITEST_CONFIGS; do
    # Check the staged diff for coverage.exclude additions that target source files
    GAMING=$(git diff --cached -- "$config" \
      | grep -E '^\+.*exclude.*src/' \
      | grep -v 'node_modules' \
      | grep -v '__tests__' \
      | grep -v '\.test\.' \
      | grep -v '\.spec\.' \
      | grep -v '\.d\.ts' \
      || true)

    if [ -n "$GAMING" ]; then
      fail "Gate 9: Suspicious coverage exclusion in $config:"
      echo "$GAMING"
      echo ""
      echo "  Excluding source files from coverage is not allowed."
      echo "  Only test files, type definitions, and node_modules may be excluded."
      exit 1
    fi
  done
fi
pass "Gate 9: No coverage gaming detected"

# ─────────────────────────────────────────────────────────────
# Gate 10: Changeset enforcement (ERROR)
# ─────────────────────────────────────────────────────────────
info "Gate 10: Changeset enforcement"
PACKAGE_FILES=$(echo "$STAGED_FILES" | grep -E '^(packages|apps)/' || true)

if [ -n "$PACKAGE_FILES" ]; then
  # Find which packages have staged changes
  CHANGED_PKGS=$(echo "$PACKAGE_FILES" \
    | sed -E 's|^(packages/[^/]+|apps/[^/]+)/.*|\1|' \
    | sort -u)

  NEEDS_CHANGESET=false
  for pkg_dir in $CHANGED_PKGS; do
    if [ -f "$pkg_dir/package.json" ]; then
      IS_PRIVATE=$(node -e "
        try {
          const pkg = require('./$pkg_dir/package.json');
          console.log(pkg.private === true ? 'true' : 'false');
        } catch { console.log('true'); }
      " 2>/dev/null || echo "true")

      if [ "$IS_PRIVATE" = "false" ]; then
        NEEDS_CHANGESET=true
        break
      fi
    fi
  done

  if [ "$NEEDS_CHANGESET" = true ]; then
    CHANGESET_FILES=$(echo "$STAGED_FILES" \
      | grep -E '^\.changeset/.*\.md$' \
      | grep -v 'README\.md$' \
      || true)

    if [ -z "$CHANGESET_FILES" ]; then
      fail "Gate 10: Publishable package changed but no changeset found."
      echo ""
      echo "  Create a changeset file in .changeset/ with a unique name:"
      echo ""
      echo "    ---"
      echo "    \"@yourscope/package-name\": patch"
      echo "    ---"
      echo ""
      echo "    Brief description of the change."
      echo ""
      echo "  If no version bump is needed, create an empty changeset:"
      echo ""
      echo "    ---"
      echo "    ---"
      echo ""
      exit 1
    fi
  fi
fi
pass "Gate 10: Changeset enforcement OK"

# ─────────────────────────────────────────────────────────────
# Gate 11: Markdown location enforcement (ERROR)
# ─────────────────────────────────────────────────────────────
info "Gate 11: Markdown location enforcement"
STAGED_MD=$(echo "$STAGED_FILES" | grep -E '\.md$' || true)

if [ -n "$STAGED_MD" ]; then
  DISALLOWED_MD=""
  for mdfile in $STAGED_MD; do
    # Allow these locations:
    #   README.md (root)
    #   CLAUDE.md (root)
    #   docs/**
    #   .changeset/**
    #   packages/*/README.md
    #   apps/*/README.md
    if echo "$mdfile" | grep -qE '^README\.md$'; then continue; fi
    if echo "$mdfile" | grep -qE '^CLAUDE\.md$'; then continue; fi
    if echo "$mdfile" | grep -qE '^docs/'; then continue; fi
    if echo "$mdfile" | grep -qE '^\.changeset/'; then continue; fi
    if echo "$mdfile" | grep -qE '^packages/[^/]+/README\.md$'; then continue; fi
    if echo "$mdfile" | grep -qE '^apps/[^/]+/README\.md$'; then continue; fi

    DISALLOWED_MD="$DISALLOWED_MD\n  $mdfile"
  done

  if [ -n "$DISALLOWED_MD" ]; then
    fail "Gate 11: Markdown files in disallowed locations:"
    echo -e "$DISALLOWED_MD"
    echo ""
    echo "  Allowed locations:"
    echo "    - README.md (repo root)"
    echo "    - CLAUDE.md (repo root)"
    echo "    - docs/**"
    echo "    - .changeset/**"
    echo "    - packages/*/README.md"
    echo "    - apps/*/README.md"
    exit 1
  fi
fi
pass "Gate 11: Markdown locations OK"

# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
echo ""
pass "All pre-commit gates passed"
```

## 4. Parallelization Technique

Gates 1, 2, and 3 (actionlint, ESLint, TypeScript type-check) are independent of each other and can run in parallel. This significantly reduces hook execution time since lint and type-check are typically the slowest gates.

The technique uses bash background processes and `wait`:

```bash
pids=()
gate_names=()
tmpdir=$(mktemp -d)

# Start each gate as a background process
(
  pnpm turbo lint --filter='...[HEAD^1]' --output-logs=errors-only > "$tmpdir/gate2.log" 2>&1
) &
pids+=($!)
gate_names+=("Gate 2: ESLint")

(
  pnpm turbo type-check --filter='...[HEAD^1]' --output-logs=errors-only > "$tmpdir/gate3.log" 2>&1
) &
pids+=($!)
gate_names+=("Gate 3: TypeScript type-check")

# Wait for all to complete, fail if any failed
PARALLEL_FAILED=false
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    fail "${gate_names[$i]} failed:"
    cat "$tmpdir/gate$((i+1)).log" 2>/dev/null || true
    PARALLEL_FAILED=true
  else
    pass "${gate_names[$i]}"
  fi
done

rm -rf "$tmpdir"

if [ "$PARALLEL_FAILED" = true ]; then
  exit 1
fi
```

Key details:

- Each background process redirects output to a temp file so it does not interleave with other processes.
- `wait "$pid"` returns the exit code of the background process.
- All parallel gates are allowed to finish before checking results -- this gives you all errors at once rather than failing on the first one.

## 5. Key Design Decisions

### Affected-package scoping with Turbo

The `--filter='...[HEAD^1]'` flag tells Turbo to only run the task on packages that have changed since the last commit. This keeps the hook fast even in large monorepos. Without this, every lint/test/type-check would run across all packages on every commit.

### Warning vs. Error gates

| Gate | Behavior | Rationale |
|------|----------|-----------|
| Gate 0: lint-staged | **ERROR** | Auto-fixes formatting; failure means Prettier itself is broken |
| Gate 0.25: Stub detection | **ERROR** | Stub files in production code are always a mistake |
| Gate 0.5: Stale lock file | **ERROR** | Inconsistent lockfile breaks CI for everyone |
| Gate 1: actionlint | **ERROR** | Broken workflows waste CI minutes |
| Gate 2: ESLint | **ERROR** | Lint errors should be fixed before committing |
| Gate 3: TypeScript | **ERROR** | Type errors should be fixed before committing |
| Gate 3.5: Migration lint | **ERROR** (naming) / **WARNING** (destructive, missing migration) | Naming is mechanical; intent requires human judgment |
| Gate 4: Unit tests | **ERROR** | Broken tests should not be committed |
| Gate 5: console.log | **WARNING** | Useful during development; clean up before push |
| Gate 6: Secret detection | **ERROR** | Secrets in the repo are a security incident |
| Gate 7: `any` types | **WARNING** | Progressive typing; blocking would slow development |
| Gate 8: Assertion density | **WARNING** | Low-density tests are a smell, not always wrong |
| Gate 9: Coverage gaming | **ERROR** | Excluding source files from coverage undermines quality |
| Gate 10: Changeset enforcement | **ERROR** | Publishable packages need version tracking |
| Gate 11: Markdown location | **ERROR** | Prevents doc sprawl; keeps the repo organized |

### lint-staged handles formatting

Developers never need to run Prettier manually. lint-staged runs it on staged files during the commit and re-stages the result. This eliminates "fix formatting" commits entirely.

### Gate ordering

1. **Formatting first** (Gate 0) -- auto-fix before any analysis runs.
2. **Fast checks next** (Gates 0.25, 0.5) -- file name and lock file checks are instant.
3. **Parallel analysis** (Gates 1-3) -- the slowest gates run concurrently.
4. **Conditional checks** (Gate 3.5) -- only when relevant files change.
5. **Tests** (Gate 4) -- after lint/types pass, so failures are genuine test failures.
6. **Grep-based checks** (Gates 5-9) -- fast, no build step required.
7. **Repo hygiene** (Gates 10-11) -- changeset and markdown location enforcement.

## 6. Installation Checklist

```bash
# 1. Install dependencies
pnpm add -D husky lint-staged prettier

# 2. Initialize Husky
pnpm exec husky

# 3. Add prepare script to root package.json
# "prepare": "husky"

# 4. Create lint-staged.config.mjs (see Section 2)

# 5. Create .husky/pre-commit (see Section 3)
chmod +x .husky/pre-commit

# 6. Optional: install actionlint for Gate 1
# macOS: brew install actionlint
# Linux: go install github.com/rhysd/actionlint/cmd/actionlint@latest

# 7. Verify it works
git add -A && git commit -m "test: verify pre-commit hooks"
```

## 7. Troubleshooting

**Hook does not run:**
- Verify `.husky/pre-commit` is executable: `chmod +x .husky/pre-commit`
- Verify Husky is installed: `ls .husky/_/husky.sh` (Husky v9+) or check `.git/hooks/pre-commit`
- Run `pnpm exec husky` again if needed

**Hook is too slow:**
- The `--filter='...[HEAD^1]'` flag should scope to changed packages. If everything runs, check that your Turbo pipeline is configured correctly.
- Gates 1-3 run in parallel. If you are seeing sequential execution, check that your shell supports background processes.

**lint-staged changes files unexpectedly:**
- This is by design. lint-staged runs Prettier and re-stages the formatted files. If you do not want this, remove the `--write` flag and use `--check` instead (but then developers must format manually).

**"No changeset found" error on private packages:**
- Gate 10 checks `"private": true` in `package.json`. If your package is private, this gate should skip it. Verify the package.json field is correct.

**Secret detection false positives:**
- The pattern matches `password=`, `secret=`, `api_key=`, `token=`, and `credential=` followed by quoted values. Common exclusions (`.example`, `.template`, `CHANGE_ME`, `your_*_here`) are already filtered. For persistent false positives, adjust the grep pattern in Gate 6 or add more exclusion patterns.
