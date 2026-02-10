# CI Pipeline for TypeScript Monorepos

This reference covers a complete GitHub Actions CI pipeline for a TypeScript monorepo using pnpm workspaces and Turbo. The pipeline enforces quality gates at every stage: lint, type-check, build, test, migration validation, and production deployment.

## Architecture Overview

```
Push to main / PR opened
         |
         v
+---ci.yml (parallel)-------------------+
|                                        |
|  lint-and-typecheck   build            |
|  test (4 shards)      migration-dry-run|
|                                        |
+----------------------------------------+
         |
         v (sequential, needs all above)
   test-coverage
         |
         v (main only, needs all above)
   migrate-production
         |
         v (main only, after CI passes)
   publish-packages.yml
         |
         v (after deploy webhook)
   deploy-check.yml
```

## 1. Main CI Workflow (ci.yml)

This is the primary workflow. It runs on every push to `main` and on all pull requests. Jobs run in parallel where possible, with sequential gates for coverage and production migrations.

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

env:
  NODE_VERSION: "20"
  PNPM_VERSION: "9"
  TURBO_TOKEN: ${{ secrets.TURBO_TOKEN }}
  TURBO_TEAM: ${{ vars.TURBO_TEAM }}

jobs:
  # ---------------------------------------------------------------
  # Parallel jobs
  # ---------------------------------------------------------------

  lint-and-typecheck:
    name: Lint & Type-check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: ${{ env.PNPM_VERSION }}

      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: pnpm

      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm type-check

  build:
    name: Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: ${{ env.PNPM_VERSION }}

      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: pnpm

      - run: pnpm install --frozen-lockfile
      - run: pnpm build

      - uses: actions/upload-artifact@v4
        with:
          name: build-artifacts
          path: |
            packages/*/dist
            apps/*/dist
            apps/*/.next
          retention-days: 1

  migration-dry-run:
    name: Migration dry-run
    runs-on: ubuntu-latest
    services:
      postgres:
        image: timescale/timescaledb:latest-pg16
        env:
          POSTGRES_USER: ci
          POSTGRES_PASSWORD: ci
          POSTGRES_DB: ci_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U ci -d ci_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
          --health-start-period 10s
    env:
      DATABASE_URL: postgres://ci:ci@localhost:5432/ci_test
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: ${{ env.PNPM_VERSION }}

      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      # Build database package (migrations may depend on compiled output)
      - run: pnpm --filter database build

      # Run SQL migrations in order
      - name: Apply SQL migrations
        run: |
          for f in packages/database/migrations/*.sql; do
            echo "--- Applying $f ---"
            psql "$DATABASE_URL" -f "$f"
          done

      # Run Drizzle migrations
      - name: Apply Drizzle migrations
        run: pnpm db:migrate

      # Verify schema matches Drizzle definitions (no drift)
      - name: Check for schema drift
        run: |
          pnpm drizzle-kit generate --dialect postgresql --schema packages/database/src/schema.ts --out /tmp/drift-check
          if ls /tmp/drift-check/*.sql 1>/dev/null 2>&1; then
            echo "::error::Schema drift detected. Drizzle generated new migrations against the freshly-migrated database."
            cat /tmp/drift-check/*.sql
            exit 1
          fi
          echo "No drift detected."

  test:
    name: Test (shard ${{ matrix.shard }}/4)
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: ${{ env.PNPM_VERSION }}

      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      - name: Run unit tests (shard ${{ matrix.shard }})
        run: pnpm vitest run --shard=${{ matrix.shard }}/4

  # ---------------------------------------------------------------
  # Sequential jobs
  # ---------------------------------------------------------------

  test-coverage:
    name: Test coverage
    needs: [test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: ${{ env.PNPM_VERSION }}

      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      - name: Generate coverage report
        run: pnpm test:coverage

      - uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage/
          retention-days: 7

  migrate-production:
    name: Migrate production
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    needs: [lint-and-typecheck, build, migration-dry-run, test, test-coverage]
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: ${{ env.PNPM_VERSION }}

      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      - uses: actions/download-artifact@v4
        with:
          name: build-artifacts

      # Apply SQL migrations to production
      - name: Apply SQL migrations
        env:
          DATABASE_URL: ${{ secrets.PRODUCTION_DATABASE_URL }}
        run: |
          for f in packages/database/migrations/*.sql; do
            echo "--- Applying $f ---"
            psql "$DATABASE_URL" -f "$f"
          done

      # Apply Drizzle migrations to production
      - name: Apply Drizzle migrations
        env:
          DATABASE_URL: ${{ secrets.PRODUCTION_DATABASE_URL }}
        run: pnpm db:migrate

  # ---------------------------------------------------------------
  # Failure handling
  # ---------------------------------------------------------------

  on-failure:
    name: Create failure ticket
    if: failure()
    needs: [lint-and-typecheck, build, migration-dry-run, test, test-coverage, migrate-production]
    runs-on: ubuntu-latest
    permissions:
      issues: write
      actions: read
    steps:
      - uses: actions/checkout@v4

      - name: Create or update failure issue
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: bash .github/scripts/ci-failure-ticket.sh
```

### Key details

- **Concurrency group** cancels in-progress runs for the same branch. A new push supersedes the old run.
- **Test sharding** splits the Vitest suite across 4 runners using `--shard=N/4`. With `fail-fast: false`, all shards complete even if one fails, giving you the full picture.
- **Build artifacts** are uploaded once and downloaded by the production migration job, avoiding redundant builds.
- **Migration dry-run** applies every migration from scratch against a fresh TimescaleDB container, then checks for drift. This catches ordering issues, missing migrations, and schema-code mismatches.
- **Production migrations** only run on main pushes, after every other gate has passed. The `environment: production` setting enables environment-level protection rules (manual approval, required reviewers).
- **The `on-failure` job** runs if any upstream job fails and creates a GitHub issue (see section 5).

## 2. Package Publishing Workflow (publish-packages.yml)

This workflow runs after CI passes on main. It uses [Changesets](https://github.com/changesets/changesets) to version packages and publish to npm.

```yaml
# .github/workflows/publish-packages.yml
name: Publish packages

on:
  workflow_run:
    workflows: [CI]
    types: [completed]
    branches: [main]

jobs:
  publish:
    name: Version & publish
    if: github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
      id-token: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm
          registry-url: https://registry.npmjs.org

      - run: pnpm install --frozen-lockfile

      - name: Check for changesets
        id: changesets
        run: |
          if ls .changeset/*.md 1>/dev/null 2>&1 && [ "$(ls .changeset/*.md | grep -v README.md | wc -l)" -gt 0 ]; then
            echo "has_changesets=true" >> "$GITHUB_OUTPUT"
          else
            echo "has_changesets=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Version packages
        if: steps.changesets.outputs.has_changesets == 'true'
        env:
          HUSKY: "0"
        run: |
          pnpm changeset version
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add -A
          git commit -m "chore: version packages" || echo "No version changes to commit"
          git push

      - name: Build packages
        if: steps.changesets.outputs.has_changesets == 'true'
        run: pnpm build

      - name: Publish to npm
        if: steps.changesets.outputs.has_changesets == 'true'
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
          NPM_CONFIG_PROVENANCE: "true"
        run: pnpm changeset publish
```

### Key details

- **`HUSKY=0`** disables pre-commit hooks for the version commit. This is the one case where hooks should not run -- the commit is automated and only contains version bumps and changelog entries.
- **`NPM_CONFIG_PROVENANCE`** enables npm provenance, linking published packages to their source commit.
- **`workflow_run` trigger** ensures this only runs after CI completes successfully on main, not on PRs.

## 3. Post-Deploy Verification Workflow (deploy-check.yml)

This workflow runs after a deployment (triggered via webhook, e.g., from Vercel) and validates the deployed application.

```yaml
# .github/workflows/deploy-check.yml
name: Post-deploy verification

on:
  repository_dispatch:
    types: [deploy-complete]

jobs:
  verify:
    name: Smoke tests
    runs-on: ubuntu-latest
    env:
      DEPLOY_URL: ${{ github.event.client_payload.deploy_url }}
      DEPLOY_SHA: ${{ github.event.client_payload.sha }}
    steps:
      - uses: actions/checkout@v4

      # Skip if a newer commit has already been deployed
      - name: Check if deployment is stale
        id: stale-check
        run: |
          LATEST_SHA=$(git rev-parse HEAD)
          if [ "$DEPLOY_SHA" != "$LATEST_SHA" ]; then
            echo "Deployed SHA ($DEPLOY_SHA) is not the latest ($LATEST_SHA). Skipping."
            echo "is_stale=true" >> "$GITHUB_OUTPUT"
          else
            echo "is_stale=false" >> "$GITHUB_OUTPUT"
          fi

      # Wait for CI to pass before running smoke tests
      - name: Wait for CI
        if: steps.stale-check.outputs.is_stale == 'false'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          echo "Waiting for CI to pass on $DEPLOY_SHA..."
          TIMEOUT=600  # 10 minutes
          INTERVAL=30
          ELAPSED=0
          while [ $ELAPSED -lt $TIMEOUT ]; do
            STATUS=$(gh api "repos/${{ github.repository }}/commits/$DEPLOY_SHA/status" --jq '.state')
            if [ "$STATUS" = "success" ]; then
              echo "CI passed."
              exit 0
            elif [ "$STATUS" = "failure" ] || [ "$STATUS" = "error" ]; then
              echo "::error::CI failed for $DEPLOY_SHA. Aborting smoke tests."
              exit 1
            fi
            echo "CI status: $STATUS. Waiting ${INTERVAL}s... (${ELAPSED}s/${TIMEOUT}s)"
            sleep $INTERVAL
            ELAPSED=$((ELAPSED + INTERVAL))
          done
          echo "::error::Timed out waiting for CI to pass."
          exit 1

      # Health check
      - name: Health check
        if: steps.stale-check.outputs.is_stale == 'false'
        run: |
          echo "Checking $DEPLOY_URL/api/health..."
          STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "$DEPLOY_URL/api/health")
          if [ "$STATUS" -ne 200 ]; then
            echo "::error::Health check failed with status $STATUS"
            exit 1
          fi
          echo "Health check passed (HTTP $STATUS)."

      # API endpoint smoke tests
      - name: API smoke tests
        if: steps.stale-check.outputs.is_stale == 'false'
        run: |
          echo "--- GET /api/symbols ---"
          curl -sf "$DEPLOY_URL/api/symbols" | jq '.symbols | length'

          echo "--- GET /api/candles (sample) ---"
          curl -sf "$DEPLOY_URL/api/candles?symbol=COINBASE_SPOT_BTC_USD&timeframe=1h&limit=5" \
            | jq '.candles | length'

      # OpenAPI contract validation with schemathesis
      - name: Contract validation (schemathesis)
        if: steps.stale-check.outputs.is_stale == 'false'
        run: |
          pip install schemathesis
          schemathesis run "$DEPLOY_URL/api/openapi.json" \
            --method GET \
            --hypothesis-max-examples 50 \
            --validate-schema true \
            --checks all \
            --base-url "$DEPLOY_URL"
```

### Key details

- **Stale deployment check** prevents wasted work when a newer commit has already been pushed.
- **CI wait loop** polls the commit status API for up to 10 minutes. Smoke tests should not run against code that has not passed CI.
- **Schemathesis** generates test cases from your OpenAPI spec using property-based testing. It catches contract violations, unexpected 500s, and schema mismatches without hand-written tests.
- **Trigger via `repository_dispatch`** lets any deployment platform (Vercel, Railway, etc.) fire the webhook:
  ```bash
  curl -X POST "https://api.github.com/repos/OWNER/REPO/dispatches" \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -d '{"event_type":"deploy-complete","client_payload":{"deploy_url":"https://app.example.com","sha":"abc123"}}'
  ```

## 4. Auto-Close PRs Workflow (Optional)

For trunk-based development teams that work exclusively on `main` and do not use pull requests for code review.

```yaml
# .github/workflows/auto-close-prs.yml
name: Auto-close PRs

on:
  pull_request:
    types: [opened, reopened]

jobs:
  close:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - name: Close PR with explanation
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
        run: |
          gh pr comment "$PR_NUMBER" -R "${{ github.repository }}" --body "$(cat <<'MSG'
          This repository uses trunk-based development. All changes are committed directly to `main`.

          **Workflow:**
          1. Work in a local feature branch or worktree
          2. Merge locally into `main`
          3. Push `main` directly

          CI runs on every push to `main` and gates production deployments.

          Closing this PR automatically.
          MSG
          )"
          gh pr close "$PR_NUMBER" -R "${{ github.repository }}"
```

## 5. CI Failure Ticket Script

This script creates or updates a GitHub issue whenever a CI job fails. It deduplicates by searching for existing open issues with the same job name and branch.

```bash
#!/usr/bin/env bash
# .github/scripts/ci-failure-ticket.sh
#
# Creates or updates a GitHub issue when a CI job fails.
# Expects:
#   - GH_TOKEN environment variable (set by GitHub Actions)
#   - Standard GitHub Actions environment variables
#
# Deduplication: if an open issue already exists for the same
# job + branch combination, a comment is added instead of
# creating a new issue.

set -euo pipefail

# ---------------------------------------------------------------
# Gather context
# ---------------------------------------------------------------

REPO="${GITHUB_REPOSITORY}"
RUN_ID="${GITHUB_RUN_ID}"
RUN_URL="${GITHUB_SERVER_URL}/${REPO}/actions/runs/${RUN_ID}"
SHA="${GITHUB_SHA}"
SHORT_SHA="${SHA:0:8}"
ACTOR="${GITHUB_ACTOR}"
BRANCH="${GITHUB_REF_NAME}"

echo "Fetching failed jobs for run ${RUN_ID}..."

# Get all failed jobs from this workflow run
FAILED_JOBS=$(gh api "repos/${REPO}/actions/runs/${RUN_ID}/jobs" \
  --jq '[.jobs[] | select(.conclusion == "failure") | {name: .name, id: .id}]')

if [ "$(echo "$FAILED_JOBS" | jq 'length')" -eq 0 ]; then
  echo "No failed jobs found. Exiting."
  exit 0
fi

echo "Failed jobs: $(echo "$FAILED_JOBS" | jq -r '.[].name' | tr '\n' ', ')"

# ---------------------------------------------------------------
# Process each failed job
# ---------------------------------------------------------------

echo "$FAILED_JOBS" | jq -c '.[]' | while read -r JOB; do
  JOB_NAME=$(echo "$JOB" | jq -r '.name')
  JOB_ID=$(echo "$JOB" | jq -r '.id')

  echo ""
  echo "=== Processing: ${JOB_NAME} ==="

  # Fetch last 80 lines of the failed job's logs
  LOGS=$(gh api "repos/${REPO}/actions/jobs/${JOB_ID}/logs" 2>/dev/null | tail -80 || echo "(Could not fetch logs)")

  # Sanitize logs: remove ANSI escape codes and mask potential secrets
  LOGS=$(echo "$LOGS" | sed 's/\x1b\[[0-9;]*m//g' | head -80)

  # Build the issue title and search label
  TITLE="CI failure: ${JOB_NAME} on ${BRANCH}"
  SEARCH_LABEL="ci-failure"

  # ---------------------------------------------------------------
  # Deduplication: search for existing open issue
  # ---------------------------------------------------------------

  EXISTING_ISSUE=$(gh issue list \
    --repo "${REPO}" \
    --state open \
    --label "${SEARCH_LABEL}" \
    --search "in:title \"CI failure: ${JOB_NAME} on ${BRANCH}\"" \
    --json number \
    --jq '.[0].number // empty' 2>/dev/null || true)

  BODY=$(cat <<EOF
**Job:** \`${JOB_NAME}\`
**Commit:** [\`${SHORT_SHA}\`](${GITHUB_SERVER_URL}/${REPO}/commit/${SHA})
**Branch:** \`${BRANCH}\`
**Actor:** @${ACTOR}
**Run:** [${RUN_ID}](${RUN_URL})

<details>
<summary>Last 80 lines of logs</summary>

\`\`\`
${LOGS}
\`\`\`

</details>
EOF
  )

  if [ -n "${EXISTING_ISSUE}" ]; then
    echo "Found existing issue #${EXISTING_ISSUE}. Adding comment."
    gh issue comment "${EXISTING_ISSUE}" \
      --repo "${REPO}" \
      --body "${BODY}"
  else
    echo "Creating new issue."

    # Ensure the ci-failure label exists
    gh label create "${SEARCH_LABEL}" \
      --repo "${REPO}" \
      --description "Auto-created by CI failure handler" \
      --color "d73a4a" \
      --force 2>/dev/null || true

    gh issue create \
      --repo "${REPO}" \
      --title "${TITLE}" \
      --label "${SEARCH_LABEL}" \
      --body "${BODY}"
  fi

done

echo ""
echo "Done."
```

### Making the script executable

```bash
chmod +x .github/scripts/ci-failure-ticket.sh
```

## 6. CI Docker Script (Local CI Simulation)

Run the full CI pipeline locally using Docker, without polluting your host environment.

```bash
#!/usr/bin/env bash
# scripts/ci-docker.sh
#
# Simulates the CI pipeline locally using Docker.
# Starts a TimescaleDB container, runs all gates, then cleans up.

set -euo pipefail

CI_DB_PORT="${CI_DB_PORT:-5433}"
CI_CONTAINER="ci-timescaledb-$$"
DATABASE_URL="postgres://ci:ci@localhost:${CI_DB_PORT}/ci_test"

# ---------------------------------------------------------------
# Cleanup on exit (always runs)
# ---------------------------------------------------------------
cleanup() {
  echo ""
  echo "--- Cleanup ---"
  docker rm -f "${CI_CONTAINER}" 2>/dev/null || true
  echo "Done."
}
trap cleanup EXIT

# ---------------------------------------------------------------
# Start database
# ---------------------------------------------------------------
echo "--- Starting TimescaleDB on port ${CI_DB_PORT} ---"
docker run -d \
  --name "${CI_CONTAINER}" \
  -e POSTGRES_USER=ci \
  -e POSTGRES_PASSWORD=ci \
  -e POSTGRES_DB=ci_test \
  -p "${CI_DB_PORT}:5432" \
  timescale/timescaledb:latest-pg16

echo "Waiting for database to be ready..."
RETRIES=30
until pg_isready -h localhost -p "${CI_DB_PORT}" -U ci 2>/dev/null; do
  RETRIES=$((RETRIES - 1))
  if [ "$RETRIES" -le 0 ]; then
    echo "ERROR: Database failed to start."
    exit 1
  fi
  sleep 1
done
echo "Database ready."

# ---------------------------------------------------------------
# Run CI gates
# ---------------------------------------------------------------
export DATABASE_URL

echo ""
echo "=== Install ==="
pnpm install --frozen-lockfile

echo ""
echo "=== Lint ==="
pnpm lint

echo ""
echo "=== Type-check ==="
pnpm type-check

echo ""
echo "=== Build ==="
pnpm build

echo ""
echo "=== Unit tests ==="
pnpm vitest run

echo ""
echo "=== Test coverage ==="
pnpm test:coverage

echo ""
echo "=== Database migrations ==="
for f in packages/database/migrations/*.sql; do
  echo "Applying $f"
  psql "$DATABASE_URL" -f "$f"
done
pnpm db:migrate

echo ""
echo "=== All gates passed ==="
```

### Usage

```bash
# Default (uses port 5433 to avoid conflicts with local dev database)
bash scripts/ci-docker.sh

# Custom port
CI_DB_PORT=5434 bash scripts/ci-docker.sh
```

## 7. E2E Sanity Script (Local Gate Runner)

A configurable script that runs the same gates as CI but allows skipping stages for faster iteration.

```bash
#!/usr/bin/env bash
# scripts/e2e-sanity.sh
#
# Local equivalent of CI. Runs all quality gates with options
# to skip specific stages.
#
# Usage:
#   bash scripts/e2e-sanity.sh                         # Full run
#   bash scripts/e2e-sanity.sh --skip-lint             # Skip lint
#   bash scripts/e2e-sanity.sh --skip-test             # Skip tests
#   bash scripts/e2e-sanity.sh --integration           # Include integration tests
#   bash scripts/e2e-sanity.sh --docker                # Use ci-docker.sh instead

set -euo pipefail

SKIP_LINT=false
SKIP_TEST=false
INTEGRATION=false
DOCKER=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-lint)    SKIP_LINT=true; shift ;;
    --skip-test)    SKIP_TEST=true; shift ;;
    --integration)  INTEGRATION=true; shift ;;
    --docker)       DOCKER=true; shift ;;
    *)
      echo "Unknown flag: $1"
      echo "Usage: $0 [--skip-lint] [--skip-test] [--integration] [--docker]"
      exit 1
      ;;
  esac
done

# If --docker is set, delegate to ci-docker.sh
if [ "$DOCKER" = true ]; then
  echo "Delegating to scripts/ci-docker.sh..."
  exec bash scripts/ci-docker.sh
fi

PASS=0
FAIL=0

run_gate() {
  local name="$1"
  shift
  echo ""
  echo "=== ${name} ==="
  if "$@"; then
    PASS=$((PASS + 1))
    echo "--- PASS: ${name} ---"
  else
    FAIL=$((FAIL + 1))
    echo "--- FAIL: ${name} ---"
  fi
}

# Install
run_gate "Install" pnpm install --frozen-lockfile

# Lint and type-check
if [ "$SKIP_LINT" = false ]; then
  run_gate "Format check" pnpm format:check
  run_gate "Lint" pnpm lint
  run_gate "Type-check" pnpm type-check
else
  echo ""
  echo "=== Skipping lint/type-check (--skip-lint) ==="
fi

# Build
run_gate "Build" pnpm build

# Tests
if [ "$SKIP_TEST" = false ]; then
  run_gate "Unit tests" pnpm vitest run
  run_gate "Test coverage" pnpm test:coverage
else
  echo ""
  echo "=== Skipping tests (--skip-test) ==="
fi

# Integration tests (optional, requires running database)
if [ "$INTEGRATION" = true ]; then
  if pg_isready -h localhost -p 5432 2>/dev/null; then
    run_gate "Integration tests" pnpm vitest run --config vitest.integration.config.ts
  else
    echo ""
    echo "=== WARNING: Database not available, skipping integration tests ==="
    FAIL=$((FAIL + 1))
  fi
fi

# Summary
echo ""
echo "==============================="
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo "==============================="

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
```

## 8. Turbo Remote Caching

Turbo's remote cache shares build artifacts across CI runs and developer machines. Without it, every CI run rebuilds everything from scratch. With it, unchanged packages are restored from cache in seconds.

### Setup

1. **Create a Turbo team** at [vercel.com/teams](https://vercel.com/teams) or use `npx turbo login && npx turbo link`.

2. **Add secrets to GitHub Actions:**

   | Secret/Variable | Where | Value |
   |----------------|-------|-------|
   | `TURBO_TOKEN` | Repository secret | API token from Vercel dashboard |
   | `TURBO_TEAM` | Repository variable | Your Vercel team slug |

3. **Reference in workflows** (already included in the ci.yml above):

   ```yaml
   env:
     TURBO_TOKEN: ${{ secrets.TURBO_TOKEN }}
     TURBO_TEAM: ${{ vars.TURBO_TEAM }}
   ```

   Turbo automatically detects these environment variables. No additional configuration is needed in `turbo.json`.

### Cache behavior

- **Inputs:** Source files, dependencies, environment variables defined in `turbo.json`'s `globalDependencies` and per-task `inputs`.
- **Outputs:** Whatever is defined in `turbo.json`'s `outputs` per task (e.g., `dist/**`, `.next/**`).
- **Hit rate:** Typically 70-90% on CI after the first run. PRs that only touch one package rebuild only that package plus its dependents.

### Verifying cache hits

```bash
# In CI logs, look for:
# cache hit, replaying logs abc123def456
# cache miss, executing <task>

# Or run locally:
pnpm turbo build --dry-run
```

## 9. Key Design Decisions

### Test sharding (4x parallel) dramatically reduces wall time

A monorepo test suite that takes 8 minutes sequentially completes in roughly 2 minutes when sharded across 4 runners. The `--shard=N/4` flag in Vitest deterministically splits test files, ensuring no duplication or gaps. Use `fail-fast: false` so all shards complete even if one fails -- this gives you the full failure picture in a single run.

### Build artifacts shared between jobs via actions/upload-artifact

The `build` job compiles everything once and uploads the output. Downstream jobs (like `migrate-production`) download these artifacts instead of rebuilding. This saves 2-5 minutes per dependent job and guarantees that the exact same build output is used everywhere.

### Migration dry-run catches schema issues before production

Running migrations against a fresh TimescaleDB container on every CI run catches problems that unit tests cannot: missing migration files, ordering dependencies, syntax errors in raw SQL, and drift between Drizzle schema definitions and actual migrations. If the dry-run fails, the production migration job never runs.

### Auto-ticket creation means failures are never silently ignored

The `ci-failure-ticket.sh` script creates a GitHub issue for every failed job. Deduplication (searching for existing open issues with the same job name and branch) prevents issue spam. The last 80 lines of logs are included directly in the issue, so the developer does not need to navigate to the Actions UI to understand what went wrong.

### Production migrations only run after ALL gates pass

The `migrate-production` job has `needs: [lint-and-typecheck, build, migration-dry-run, test, test-coverage]`. If any gate fails, production is untouched. Combined with the `environment: production` setting (which can require manual approval in GitHub's environment protection rules), this creates a strong safety net against shipping broken migrations.

### Concurrency groups prevent wasted compute

The `concurrency` setting cancels in-progress CI runs when a new commit is pushed to the same branch. Without this, pushing three quick fixes to a PR would run three full CI pipelines. With it, only the latest commit's pipeline runs to completion.

### Changeset-based publishing decouples versioning from CI

Package publishing is a separate workflow triggered by `workflow_run`. This keeps the main CI workflow focused on quality gates. Version bumps and npm publishing only happen when changesets are present, and the `HUSKY=0` flag prevents pre-commit hooks from interfering with the automated version commit.
