# Test Infrastructure

This reference covers the complete test infrastructure for a TypeScript monorepo: Vitest for unit and integration tests, coverage enforcement with anti-gaming measures, assertion density checks, Playwright for E2E, and smoke tests for deployed environments.

## Why Vitest

Vitest is the test runner for TypeScript monorepos. The reasons are concrete:

- **Native ESM support** -- no transpilation step, no CommonJS interop hacks. Tests run against the same module system as production code.
- **TypeScript-first** -- understands `.ts` files natively via esbuild. No `ts-jest` configuration, no `babel-jest` transforms.
- **Fast** -- uses Vite's transform pipeline. File-level caching means re-runs only process changed files.
- **Jest-compatible API** -- `describe`, `it`, `expect`, `beforeAll`, `afterAll`, `vi.fn()`, `vi.mock()` all work. Migration from Jest is mechanical.
- **Workspace-aware** -- a single root config can include test files across `packages/` and `apps/` directories.
- **In-source testing** -- supports `if (import.meta.vitest)` blocks for colocated unit tests (optional, not recommended as default).

Install at the root:

```bash
pnpm add -Dw vitest @vitest/coverage-v8
```

## Root vitest.config.ts (Unit Tests)

This is the primary test configuration. It runs all unit tests across the monorepo.

```typescript
// vitest.config.ts
// === STRICT MODE - NEVER DISABLE THESE ===
// This configuration enforces production-grade quality standards.
// Do not modify without team review.

import { defineConfig } from "vitest/config";

const isCi = process.env.CI === "true";

export default defineConfig({
  resolve: {
    // CRITICAL: "development" condition resolves workspace packages to their
    // source (src/) instead of built output (dist/). This means you don't need
    // to rebuild every dependency before running tests.
    //
    // Package exports should be structured as:
    //   "development": { "types": "./src/index.ts", "default": "./src/index.ts" }
    //   "types": "./dist/index.d.ts"
    //   "default": "./dist/index.js"
    //
    // Vitest sees "development" -> resolves to source.
    // Production build sees "default" -> resolves to dist.
    conditions: ["development", "require", "default"],
  },
  test: {
    globals: true,
    environment: "node",
    setupFiles: ["./packages/testing/src/vitest-setup.ts"],

    // Thread pool configuration
    pool: "threads",
    poolOptions: {
      threads: {
        singleThread: isCi, // Single-thread in CI for deterministic results
        isolate: true,
        minThreads: 1,
        maxThreads: isCi ? 1 : 4,
      },
    },
    fileParallelism: !isCi,

    // Coverage configuration
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      clean: false,
      cleanOnRerun: false,

      // === COVERAGE THRESHOLDS ARE NON-NEGOTIABLE ===
      // If coverage drops below these thresholds, tests fail.
      // The fix is to write tests, not to lower thresholds.
      thresholds: {
        lines: 90,
        functions: 90,
        branches: 90,
        statements: 90,
      },

      // === COVERAGE EXCLUSIONS ARE LOCKED ===
      // Adding exclusions to game coverage metrics is prohibited.
      // This list is enforced by pre-commit hook. Changes require team review.
      // If you need to exclude a file, write tests for it instead.
      exclude: [
        // Infrastructure -- never contains testable logic
        "node_modules/**",
        "**/node_modules/**",
        "**/dist/**",
        "**/generated/**",
        "**/coverage/**",
        ".next/**",

        // Type-only files -- no runtime code to test
        "**/*.d.ts",

        // Barrel exports -- re-exports only, no logic
        "**/index.ts",

        // Configuration files -- not application logic
        "**/*.config.ts",
        "**/*.config.js",
        "**/*.config.mjs",

        // Test utilities -- tests themselves, not code under test
        "packages/testing/**",
        "**/fixtures.ts",
        "**/mocks.ts",

        // Static/docs -- not code
        "public/**",
        "docs/**",
        "**/scripts/**",

        // Config-only packages -- no testable logic
        "packages/eslint-config/**",
        "packages/tsconfig/**",
      ],

      include: [
        // Explicitly list packages under coverage measurement.
        // Each package must have tests meeting the 90% threshold before
        // being added here. Do not add packages speculatively.
        "packages/core-domain/src/**/*.ts",
        "!packages/core-domain/src/**/*.test.ts",
        "!packages/core-domain/src/**/__tests__/**",

        // Add more packages as they reach coverage thresholds:
        // "packages/your-package/src/**/*.ts",
        // "!packages/your-package/src/**/*.test.ts",
        // "!packages/your-package/src/**/__tests__/**",
      ],
    },

    // Test file discovery
    include: [
      "packages/**/src/**/*.test.ts",
      "packages/**/src/**/*.test.tsx",
      "apps/**/src/**/*.test.ts",
      "apps/**/src/**/*.test.tsx",
    ],

    // Excluded from unit test runs
    exclude: [
      "node_modules",
      ".next",
      "public",
      "**/node_modules/**",
      "**/*.integration.test.ts", // Integration tests run separately
    ],
  },
});
```

### Key Decisions Explained

**`globals: true`** -- Allows `describe`, `it`, `expect` without imports. Reduces boilerplate in every test file. The tradeoff (implicit globals) is worth the ergonomics since every developer knows these are test globals.

**`conditions: ["development", "require", "default"]`** -- This is the single most important line for monorepo testing. Without it, Vitest resolves workspace packages to their `dist/` output, which means you must rebuild every dependency before running tests. With the `"development"` condition, packages resolve to source. This requires the nested export structure in each package's `package.json`:

```json
{
  "exports": {
    ".": {
      "development": {
        "types": "./src/index.ts",
        "default": "./src/index.ts"
      },
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    }
  }
}
```

**Why `"types"` is nested inside `"development"`**: TypeScript always resolves the `"types"` condition first, regardless of `customConditions`. If `"types"` is at the top level pointing to `./dist/index.d.ts`, TypeScript will use that even when `"development"` should take precedence. Nesting `"types"` inside `"development"` ensures the development condition controls type resolution during development.

**`clean: false`** -- Coverage data is not wiped between runs. This prevents a race condition where parallel Turbo tasks overwrite each other's coverage output.

**Explicit `include` for coverage** -- Rather than measuring coverage across everything and excluding what you don't want, explicitly list what IS under coverage measurement. This prevents new packages from silently dragging down the overall number. Each package is added only when it has tests meeting the threshold.

**Negation patterns (`!`) in coverage include** -- Test files themselves should not be measured for coverage. The `!**/*.test.ts` and `!**/__tests__/**` patterns exclude test files from coverage measurement while still allowing them to run.

## Integration Test Config (vitest.integration.config.ts)

Integration tests require external services (databases, caches) and must run separately from unit tests.

```typescript
// vitest.integration.config.ts
// === INTEGRATION TEST CONFIGURATION ===
// Runs *.integration.test.ts files that require database or external services.
// These tests are NOT run in pre-commit (too slow) but run in pre-push and CI.

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    conditions: ["development", "require", "default"],
  },
  test: {
    globals: true,
    environment: "node",
    setupFiles: ["./packages/testing/src/integration-setup.ts"],
    globalSetup: [],
    globalTeardown: "./packages/testing/src/global-teardown.ts",

    // CRITICAL: Integration tests MUST run single-threaded.
    // Database tests cannot safely parallelize -- they share tables,
    // create/delete rows, and rely on transaction isolation.
    pool: "threads",
    poolOptions: {
      threads: {
        singleThread: true,
        isolate: true,
        minThreads: 1,
        maxThreads: 2,
      },
    },
    fileParallelism: false,

    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      thresholds: {
        lines: 90,
        functions: 90,
        branches: 90,
        statements: 90,
      },
      exclude: [
        "node_modules/**",
        "**/node_modules/**",
        "**/generated/**",
        "**/*.d.ts",
        "**/index.ts",
        "**/*.config.ts",
        "**/*.config.js",
        "**/*.config.mjs",
        ".next/**",
        "**/dist/**",
        "public/**",
        "docs/**",
        "**/coverage/**",
        "**/scripts/**",
        "packages/eslint-config/**",
        "packages/tsconfig/**",
        "**/fixtures.ts",
        "**/mocks.ts",
        "packages/testing/**",
      ],
      include: [
        "packages/*/src/**/*.ts",
        "apps/*/src/**/*.ts",
      ],
    },

    // ONLY integration test files
    include: [
      "packages/**/src/**/*.integration.test.ts",
      "packages/**/src/**/*.integration.test.tsx",
      "apps/**/src/**/*.integration.test.ts",
      "apps/**/src/**/*.integration.test.tsx",
    ],
    exclude: [
      "node_modules",
      ".next",
      "public",
      "**/node_modules/**",
    ],
  },
});
```

### Running Integration Tests

```bash
# Run with the integration config
pnpm vitest run --config vitest.integration.config.ts

# Requires DATABASE_URL to be set
DATABASE_URL="postgres://user:pass@localhost:5432/mydb" \
  pnpm vitest run --config vitest.integration.config.ts
```

Add a convenience script to the root `package.json`:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:integration": "vitest run --config vitest.integration.config.ts",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage"
  }
}
```

### Why Single-Threaded

Database integration tests share mutable state. Even with transaction isolation, tests that truncate tables, seed data, or rely on specific row counts will flake when run in parallel. The performance cost of single-threading is acceptable because:

1. Integration tests are fewer in number than unit tests.
2. They run in pre-push (not pre-commit), so the slower speed is tolerable.
3. Deterministic results are worth more than fast flaky results.

## Per-Package Vitest Configs

Individual packages can have their own `vitest.config.ts` for package-specific settings. These are used when running tests for a single package (e.g., via Turbo's `--filter`).

### Simple Package Config

Most packages need minimal configuration:

```typescript
// packages/indicators/vitest.config.ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
  },
});
```

This inherits global settings when run from the root config, but also works standalone when Turbo runs `pnpm test` inside the package directory.

### App Config with Workspace Aliases

Apps often use path aliases (`@/`) and may depend on other workspace packages via source. These need explicit alias resolution:

```typescript
// apps/my-app/vitest.config.ts
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      // Resolve @/ to this app's source directory
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      // Resolve workspace packages to their source for testing
      "@scope/shared-lib": fileURLToPath(
        new URL("../../packages/shared-lib/src", import.meta.url)
      ),
    },
  },
  test: {
    testTimeout: 15000,
    hookTimeout: 15000,
    globals: true,
    environment: "node",
    pool: "threads",
    poolOptions: {
      threads: {
        singleThread: false,
        isolate: true,
      },
    },
    fileParallelism: true,
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    exclude: [
      "node_modules",
      ".next",
      "public",
      "**/node_modules/**",
      "**/*.integration.test.ts",
    ],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      thresholds: {
        // Per-package thresholds can be STRICTER than root, never looser.
        // Lock these in after a test sprint -- they only go up.
        lines: 80,
        functions: 85,
        branches: 85,
        statements: 80,
      },
      exclude: [
        "node_modules/**",
        "**/*.d.ts",
        "**/*.test.ts",
        "**/__tests__/**",
        "**/types.ts",
        "**/index.ts",
        "src/app/**",         // Next.js app router (tested via E2E)
        "src/components/**",  // React components (tested via E2E)
        ".next/**",
      ],
      include: [
        "src/lib/**/*.ts",
        "src/jobs/**/*.ts",
        "src/contracts/**/*.ts",
      ],
    },
  },
});
```

### Service App Config with Entry Point Exclusions

Services like workers and ingestors have entry points (`index.ts`, `worker.ts`, `service.ts`) that bootstrap the process. These are tested via integration tests, not unit tests:

```typescript
// apps/my-ingestor/vitest.config.ts
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    testTimeout: 15000,
    hookTimeout: 15000,
    globals: true,
    environment: "node",
    pool: "threads",
    poolOptions: {
      threads: {
        singleThread: false,
        isolate: true,
      },
    },
    fileParallelism: true,
    setupFiles: ["src/__tests__/test-setup.ts"],
    include: ["src/**/*.test.ts"],
    exclude: ["node_modules", "dist"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      thresholds: {
        lines: 78,
        functions: 92,
        branches: 84,
        statements: 78,
      },
      exclude: [
        "node_modules/**",
        "dist/**",
        "**/*.d.ts",
        "**/*.test.ts",
        "**/__tests__/**",
        "scripts/**",
        "src/index.ts", // Main entry point (tested via integration)
      ],
      include: ["src/**/*.ts"],
    },
  },
});
```

### Per-Package Threshold Rules

1. **Never lower thresholds** -- they only go up. After a test sprint that raises coverage, lock in the new numbers.
2. **Comment the current actual coverage** -- e.g., `lines: 78, // Current: 80.36%`. This makes it clear the threshold is a floor, not a target.
3. **Critical packages get stricter thresholds** -- core domain logic, financial calculations, and data processing should aim for 93%+ lines.
4. **Entry points are the only legitimate exclusions** -- files like `src/index.ts` that only call `app.listen()` or `worker.start()` are infrastructure, not logic. Everything else gets tested.

## Coverage Enforcement: Anti-Gaming

Coverage metrics are only useful if they cannot be gamed. The pre-commit hook enforces this.

### Pre-Commit Hook: Block Coverage Exclusion Gaming

This hook detects when someone adds source files to `coverage.exclude` in any `vitest.config.ts`:

```bash
# In .husky/pre-commit (or equivalent)

# Block coverage exclusion gaming
# Adding source files to coverage.exclude to cheat metrics is prohibited.
# However, test files (*.test.ts, __tests__) should legitimately be excluded from
# coverage since they're tests, not production code to be covered.
if git diff --cached --name-only | grep -q 'vitest.config.ts'; then
  # Check for new lines added that look like source file exclusions (not test files)
  # Allow: *.test.ts, *.test.tsx, __tests__, and negation patterns in include (!)
  GAMING_EXCLUSIONS=$(git diff --cached vitest.config.ts | \
    grep '^+' | \
    grep -E "^\+\s*'" | \
    grep -v '// ===' | \
    grep -v '\.test\.' | \
    grep -v '__tests__' | \
    grep -v "^\+\s*'!" || true)

  if [ -n "$GAMING_EXCLUSIONS" ]; then
    echo "BLOCKED: Coverage exclusion gaming detected in vitest.config.ts"
    echo "   Adding source files to coverage.exclude to game metrics is prohibited."
    echo "   If coverage is failing, write tests instead of excluding files."
    echo ""
    echo "   Note: Test file exclusions (*.test.ts, __tests__) are allowed since"
    echo "   test files are not production code to be measured for coverage."
    echo ""
    echo "   Suspicious additions:"
    echo "$GAMING_EXCLUSIONS"
    exit 1
  fi
fi
```

### What This Catches

The hook detects lines added to `vitest.config.ts` that look like source file exclusion patterns. It explicitly allows:

- **Test file exclusions**: `*.test.ts`, `*.test.tsx`, `__tests__/` -- these are tests, not production code.
- **Negation patterns**: Lines starting with `!` in coverage `include` arrays (used to exclude test files from coverage measurement).
- **Comment lines**: Lines starting with `// ===` (section headers in the config).

It blocks:

- Adding `"src/lib/hard-to-test-module.ts"` to exclusions.
- Adding `"**/some-directory/**"` to exclusions.
- Any new glob pattern that would exclude source code from coverage measurement.

### Philosophy

The correct response to failing coverage is always to write tests. Excluding files from coverage measurement hides the problem. If a file is genuinely untestable (rare), the path forward is refactoring to make it testable, not excluding it from metrics.

The only files that should ever be excluded from coverage are:

1. **Infrastructure files** that have no runtime logic (type declarations, config files, barrel exports).
2. **Test utilities** (fixtures, mocks, test setup) -- these are part of the test infrastructure, not production code.
3. **Entry points** that are pure bootstrapping (`index.ts` that calls `app.listen()`).
4. **Generated code** that is not hand-maintained.

Everything else gets tested.

## Test Assertion Density Check

A test file with 200 lines and zero `expect()` calls is not a test -- it is a script that happens to run in a test harness. The assertion density check catches this.

### Pre-Commit Hook: Thin Test Detection

```bash
# In .husky/pre-commit (or equivalent)

# Check test assertion density (warning for thin tests)
STAGED_TESTS=$(git diff --cached --name-only -- '*.test.ts' '*.test.tsx' || true)
if [ -n "$STAGED_TESTS" ]; then
  for file in $STAGED_TESTS; do
    if [ -f "$file" ]; then
      LINES=$(wc -l < "$file" | tr -d ' ')
      EXPECTS=$(grep -c 'expect(' "$file" 2>/dev/null || echo "0")
      if [ "$LINES" -gt 50 ] && [ "$EXPECTS" -lt 3 ]; then
        echo "WARNING: Low assertion density in $file ($EXPECTS expects in $LINES lines)"
      fi
    fi
  done
fi
```

### Why a Warning, Not an Error

This is intentionally a warning because some tests legitimately have few `expect()` calls:

- **Snapshot tests** use `toMatchSnapshot()` or `toMatchInlineSnapshot()` -- one call covers many assertions.
- **Error boundary tests** that verify a function throws -- one `expect().toThrow()` is sufficient.
- **Type-level tests** that verify TypeScript compilation succeeds -- the test passing IS the assertion.
- **Integration tests** with complex setup where the assertion count is low but each assertion is high-value.

The warning makes developers conscious of thin tests without blocking legitimate patterns.

### Thresholds

- **50 lines minimum** -- files shorter than 50 lines are likely simple, focused tests where few assertions are expected.
- **3 expect() minimum** -- for files over 50 lines, at least 3 assertions should exist. This is a very low bar; most well-written test files have 10-30+ assertions.

## Playwright for E2E Tests

Playwright tests verify that the application works end-to-end: API endpoints return valid responses, UI loads correctly, and interactive features function as expected.

### Configuration

```typescript
// apps/my-app/playwright.config.ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-tests",
  fullyParallel: true,
  forbidOnly: !!process.env["CI"],
  retries: process.env["CI"] ? 2 : 0,
  ...(process.env["CI"] && { workers: 1 }),
  reporter: "html",

  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  // Start dev server before tests if not already running
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env["CI"],
    timeout: 120 * 1000,
  },
});
```

Install Playwright:

```bash
pnpm add -Dw @playwright/test
pnpm exec playwright install chromium
```

Add scripts to the app's `package.json`:

```json
{
  "scripts": {
    "test:e2e": "playwright test",
    "test:e2e:headed": "playwright test --headed",
    "test:e2e:ui": "playwright test --ui",
    "test:e2e:update-snapshots": "playwright test --update-snapshots"
  }
}
```

### What E2E Tests Should Verify

**Direct API tests:**

```typescript
// e2e-tests/api.spec.ts
import { test, expect } from "@playwright/test";

test("health endpoint returns ok", async ({ request }) => {
  const response = await request.get("/api/health");
  expect(response.ok()).toBe(true);
  const body = await response.json();
  expect(body.status).toBe("ok");
});

test("chart endpoint returns valid PNG", async ({ request }) => {
  const response = await request.get(
    "/api/charts/BTC_USD/image?timeframe=1h&from=2025-01-01T00:00:00Z&to=2025-01-02T00:00:00Z",
    { headers: { "X-API-Key": "test-key" } }
  );
  expect(response.ok()).toBe(true);
  expect(response.headers()["content-type"]).toContain("image/png");

  // Verify PNG magic bytes
  const body = await response.body();
  expect(body[0]).toBe(0x89);
  expect(body[1]).toBe(0x50); // P
  expect(body[2]).toBe(0x4e); // N
  expect(body[3]).toBe(0x47); // G
});
```

**UI tests:**

```typescript
// e2e-tests/docs-ui.spec.ts
import { test, expect } from "@playwright/test";

test("docs page loads", async ({ page }) => {
  await page.goto("/docs");
  await expect(page.locator("h1")).toBeVisible();
});

test("interactive API explorer works", async ({ page }) => {
  await page.goto("/docs");
  await page.click("text=Try it");
  await page.fill('[placeholder="API Key"]', "test-key");
  await page.click("button:has-text('Send')");
  await expect(page.locator(".response-panel")).toBeVisible();
});
```

**Visual regression tests:**

```typescript
// e2e-tests/visual.spec.ts
import { test, expect } from "@playwright/test";

test("chart renders correctly", async ({ page }) => {
  await page.goto("/charts/BTC_USD?timeframe=1h");
  await page.waitForSelector("canvas");
  await expect(page).toHaveScreenshot("btc-1h-chart.png", {
    maxDiffPixelRatio: 0.01,
  });
});
```

### When E2E Tests Run

E2E tests are NOT part of pre-commit or pre-push hooks. They are too slow and require a running dev server:

- **Local development**: Run manually with `pnpm test:e2e` after making UI or API changes.
- **CI**: Run after deployment to a preview/staging environment.
- **Visual regression**: Snapshots are committed to the repo and compared in CI.

## Smoke Tests for Deployed Environments

Smoke tests verify that a deployed environment is functioning. They run after deployment, not before.

### Shell Script Pattern

```bash
#!/usr/bin/env bash
set -euo pipefail

# Required environment variables
: "${BASE_URL:?BASE_URL required}"
: "${API_KEY:?API_KEY required}"

echo "Running smoke tests against ${BASE_URL}"
echo ""

# 1. Health endpoint
echo "1/5 Checking /api/health..."
curl -fsS "${BASE_URL}/api/health" | jq -e '.status == "ok"' > /dev/null
echo "    OK - Health check passed"

# 2. Homepage renders HTML
echo "2/5 Checking homepage..."
curl -fsS "${BASE_URL}/" | grep -q '<html' || { echo "FAIL: Homepage missing <html"; exit 1; }
echo "    OK - Homepage renders"

# 3. API returns data
echo "3/5 Checking data API..."
curl -fsS -H "X-API-Key: ${API_KEY}" \
  "${BASE_URL}/api/data?limit=5" \
  | jq -e '.items | length > 0' > /dev/null
echo "    OK - Data API returns results"

# 4. Auth is enforced
echo "4/5 Checking auth enforcement..."
STATUS=$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/api/data?limit=5")
if [ "$STATUS" != "401" ] && [ "$STATUS" != "403" ]; then
  echo "FAIL: Unauthenticated request returned $STATUS (expected 401 or 403)"
  exit 1
fi
echo "    OK - Auth is enforced"

# 5. Contract tests via Vitest
echo "5/5 Running contract smoke tests..."
BASE_URL="${BASE_URL}" API_KEY="${API_KEY}" \
  pnpm vitest run smoke-tests/contracts.smoke.ts
echo "    OK - Contract smoke tests passed"

echo ""
echo "All smoke tests passed!"
```

### Vitest-Based Smoke Tests

For more complex validations, use Vitest files that run against the deployed environment:

```typescript
// smoke-tests/data-quality.smoke.ts
import { describe, it, expect } from "vitest";

const BASE_URL = process.env.BASE_URL!;
const API_KEY = process.env.API_KEY!;

describe("data quality smoke tests", () => {
  it("returns candles with valid OHLCV structure", async () => {
    const response = await fetch(
      `${BASE_URL}/api/ohlcv/BTC_USD?timeframe=1h&limit=5`,
      { headers: { "X-API-Key": API_KEY } }
    );
    expect(response.ok).toBe(true);

    const data = await response.json();
    expect(data.candles.length).toBeGreaterThan(0);

    for (const candle of data.candles) {
      expect(candle.high).toBeGreaterThanOrEqual(candle.low);
      expect(candle.high).toBeGreaterThanOrEqual(candle.open);
      expect(candle.high).toBeGreaterThanOrEqual(candle.close);
      expect(candle.low).toBeLessThanOrEqual(candle.open);
      expect(candle.low).toBeLessThanOrEqual(candle.close);
      expect(candle.volume).toBeGreaterThanOrEqual(0);
    }
  });

  it("returns valid error for unknown symbol", async () => {
    const response = await fetch(
      `${BASE_URL}/api/ohlcv/FAKE_SYMBOL?timeframe=1h&limit=5`,
      { headers: { "X-API-Key": API_KEY } }
    );
    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toBeDefined();
  });
});
```

### When Smoke Tests Run

Smoke tests run in CI after deployment completes:

```yaml
# In CI pipeline (e.g., GitHub Actions)
deploy-production:
  # ... deployment steps ...

smoke-test:
  needs: deploy-production
  steps:
    - run: |
        BASE_URL=${{ vars.PRODUCTION_URL }} \
        API_KEY=${{ secrets.SMOKE_TEST_API_KEY }} \
        bash scripts/smoke-test-deployed.sh
```

If smoke tests fail, the deployment should be rolled back automatically or the team alerted immediately.

## Testing Utilities Package (packages/testing)

A shared testing package centralizes test helpers, fixtures, mocks, and integration test setup. This prevents every package from reinventing the same utilities.

### Package Structure

```
packages/testing/
  src/
    index.ts              # Barrel export
    vitest-setup.ts       # Global test setup (runs before every test file)
    integration-setup.ts  # Database connection setup for integration tests
    global-teardown.ts    # Cleanup after all tests complete
    fixtures.ts           # Shared test data factories
    mocks.ts              # Mock utilities (wraps vitest-mock-extended)
    query-counter.ts      # N+1 query detection utility
  package.json
  tsconfig.json
```

### package.json

```json
{
  "name": "@scope/testing",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "development": {
        "types": "./src/index.ts",
        "default": "./src/index.ts"
      },
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js",
      "import": "./dist/index.js"
    }
  },
  "scripts": {
    "build": "tsc",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "@scope/core-domain": "workspace:*",
    "@scope/database": "workspace:*",
    "fast-check": "^4.4.0",
    "vitest-mock-extended": "^2.0.2"
  },
  "devDependencies": {
    "@scope/tsconfig": "workspace:*",
    "typescript": "^5",
    "vitest": "^2.1.8"
  }
}
```

### vitest-setup.ts

Runs before every test file. Keep this minimal to avoid slowing down test startup:

```typescript
// packages/testing/src/vitest-setup.ts
// Global test setup. Keep side effects minimal to avoid heavy deps.
// Only add setup here that EVERY test file needs.
```

If you need custom matchers or global mocks, add them here. But resist the urge to make this file heavy -- it runs before every single test file.

### integration-setup.ts

Sets up database connections for integration tests:

```typescript
// packages/testing/src/integration-setup.ts
import { beforeAll, afterAll } from "vitest";
import type { DatabaseClient } from "@scope/database";

type DatabaseClientFactory = (databaseUrl: string) => { db: DatabaseClient };

interface DatabaseModule {
  createDatabaseClient: DatabaseClientFactory;
}

let globalDatabaseClient: { db: DatabaseClient } | null = null;

/**
 * Gets the global database client for integration tests.
 * Must be called after setupIntegrationTests() has run.
 */
export function getDatabaseClient(): DatabaseClient {
  if (!globalDatabaseClient) {
    throw new Error(
      "Database client not initialized. Ensure setupIntegrationTests() runs in beforeAll."
    );
  }
  return globalDatabaseClient.db;
}

/**
 * Sets up database connection for integration tests.
 */
export function setupIntegrationTests(): void {
  beforeAll(async () => {
    const databaseUrl = process.env["DATABASE_URL"];
    if (!databaseUrl) {
      throw new Error(
        "DATABASE_URL environment variable is required for integration tests"
      );
    }

    const { createDatabaseClient } = (await import(
      "@scope/database"
    )) as DatabaseModule;
    globalDatabaseClient = createDatabaseClient(databaseUrl);
  });

  afterAll(() => {
    // Do NOT close the database connection here.
    // The database client is a global singleton shared across all test files.
    // Closing it here would break subsequent test files.
    // The connection is closed in global-teardown.ts which runs once
    // after ALL test files complete.
    globalDatabaseClient = null;
  });
}
```

### global-teardown.ts

Runs once after all test files complete. Cleans up shared resources:

```typescript
// packages/testing/src/global-teardown.ts
import type { createDatabaseClient } from "@scope/database";

type DatabaseClientResult = ReturnType<typeof createDatabaseClient>;

declare global {
  var __databaseClient: DatabaseClientResult | undefined;
}

/**
 * Closes the shared database connection after all tests complete.
 */
export default async function globalTeardown(): Promise<void> {
  if (global.__databaseClient) {
    await global.__databaseClient.client.end();
    global.__databaseClient = undefined;
  }
}
```

### fixtures.ts

Typed factory functions for creating test data:

```typescript
// packages/testing/src/fixtures.ts
import type { Entity, EntityId, Timestamp } from "@scope/core-domain";
import { EntityId as IdHelper, Timestamp as TsHelper } from "@scope/core-domain";

export const mockEntityId: EntityId = IdHelper.create("TEST:ENTITY/1");

export const createMockEntity = (overrides: Partial<Entity> = {}): Entity => ({
  id: overrides.id ?? mockEntityId,
  timestamp: overrides.timestamp ?? TsHelper.now(),
  value: overrides.value ?? 100,
  // ... other fields with sensible defaults
});

export const createMockEntities = (
  count: number,
  baseTimestamp?: Timestamp
): readonly Entity[] => {
  const base = baseTimestamp ?? TsHelper.create(1700000000000);
  return Array.from({ length: count }, (_, index) =>
    createMockEntity({
      timestamp: TsHelper.create((base as number) + index * 60000),
    })
  );
};
```

### mocks.ts

Wraps `vitest-mock-extended` for consistent mock creation:

```typescript
// packages/testing/src/mocks.ts
import { mock, mockDeep, mockReset, mockClear } from "vitest-mock-extended";

export { mock, mockDeep, mockReset, mockClear };
export type MockProxy<T> = ReturnType<typeof mock<T>>;
export type DeepMockProxy<T> = ReturnType<typeof mockDeep<T>>;

export const createMockFunction = (): ReturnType<typeof mock> => mock();
export const createDeepMock = <T extends object>(): DeepMockProxy<T> => mockDeep<T>();
```

### query-counter.ts

Detects N+1 query problems in integration tests:

```typescript
// packages/testing/src/query-counter.ts

let queryLog: string[] = [];
let loggingEnabled = false;

export function enableQueryLogging(): void {
  loggingEnabled = true;
}

export function disableQueryLogging(): void {
  loggingEnabled = false;
}

export function clearQueryLog(): void {
  queryLog = [];
}

export function getQueryCount(): number {
  return queryLog.length;
}

export function getQueryLog(): readonly string[] {
  return [...queryLog];
}

export function logQuery(query: string): void {
  if (loggingEnabled) {
    queryLog.push(query);
  }
}

/**
 * Asserts that the query count does not exceed a maximum.
 * Use this to catch N+1 queries: if fetching 100 items should
 * take 2 queries (one for items, one for relations), assert max 3.
 */
export function assertMaxQueries(max: number, message?: string): void {
  const count = getQueryCount();
  if (count > max) {
    const details = queryLog
      .map((q, i) => `${i + 1}. ${q}`)
      .join("\n");
    const base = `Expected at most ${max} queries but found ${count}`;
    const full = message ? `${message}: ${base}` : base;
    throw new Error(`${full}\n\nQueries:\n${details}`);
  }
}

/**
 * Asserts that the query count is exactly a specific number.
 */
export function assertQueryCount(expected: number, message?: string): void {
  const count = getQueryCount();
  if (count !== expected) {
    const details = queryLog
      .map((q, i) => `${i + 1}. ${q}`)
      .join("\n");
    const base = `Expected exactly ${expected} queries but found ${count}`;
    const full = message ? `${message}: ${base}` : base;
    throw new Error(`${full}\n\nQueries:\n${details}`);
  }
}

export interface QueryLogger {
  logQuery(query: string, parameters: unknown[]): void;
}

/**
 * Creates a query logger that integrates with Drizzle's logging system.
 * Pass this to your Drizzle client configuration in integration tests.
 */
export function createQueryLogger(): QueryLogger {
  return {
    logQuery(query: string, parameters: unknown[]): void {
      const formatted =
        parameters.length > 0
          ? `${query} -- params: ${JSON.stringify(parameters)}`
          : query;
      logQuery(formatted);
    },
  };
}
```

### index.ts (Barrel Export)

```typescript
// packages/testing/src/index.ts
export { mock, mockDeep, mockFn, mockClear, mockReset } from "vitest-mock-extended";
export type { MockProxy, DeepMockProxy } from "vitest-mock-extended";
export * as fc from "fast-check";

// Fixture factories
export { createMockEntity, createMockEntities, mockEntityId } from "./fixtures.js";

// Integration test utilities
export { setupIntegrationTests, getDatabaseClient } from "./integration-setup.js";

// Query counter for N+1 detection
export {
  enableQueryLogging,
  disableQueryLogging,
  clearQueryLog,
  getQueryCount,
  getQueryLog,
  logQuery,
  assertMaxQueries,
  assertQueryCount,
  createQueryLogger,
  type QueryLogger,
} from "./query-counter.js";
```

## Mutation Testing with Stryker

Mutation testing introduces real bugs into your source code -- small, deliberate changes called *mutants* -- and then runs your test suite against each mutant. If a test fails, the mutant is **killed** (your tests caught the bug). If no test fails, the mutant **survived** (your tests have a gap). The mutation score (killed / total) measures how well your tests actually verify behavior, not just execute code.

This matters because 100% code coverage with a 60% mutation score means 40% of your "covered" code has never had its behavior checked. Coverage measures execution. Mutation testing measures verification.

See `references/mutation-testing.md` for the full deep-dive: threshold strategies, per-language equivalents (Python, Go, Rust, Java), anti-gaming analysis, and ratcheting workflows.

### Installation

```bash
pnpm add -Dw @stryker-mutator/core @stryker-mutator/vitest-runner @stryker-mutator/typescript-checker
```

### Root Configuration

Create `stryker.config.mjs` at the repository root. This integrates with Vitest and the pnpm monorepo structure:

```javascript
// stryker.config.mjs
// === MUTATION TESTING CONFIGURATION ===
// Measures test verification quality, not just execution.
// If a mutant survives, your tests have a gap.

/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
const config = {
  // === Test Runner ===
  // Uses the same Vitest config as your unit tests.
  // No separate test setup required.
  testRunner: "vitest",
  vitest: {
    configFile: "vitest.config.ts",
    dir: ".",
  },

  // === TypeScript Checker ===
  // Filters out mutants that would cause compile errors.
  // Without this, Stryker wastes time on mutants that TypeScript
  // would catch at compile time (e.g., changing a number to a string).
  checkers: ["typescript"],
  tpinitTimeout: 120000,

  // === File Patterns ===
  // What gets mutated (production code only).
  // Same exclusion philosophy as coverage: tests, configs, generated
  // files, and barrel exports are never mutated.
  mutate: [
    "packages/*/src/**/*.ts",
    "apps/*/src/**/*.ts",
    "!**/*.test.ts",
    "!**/*.spec.ts",
    "!**/__tests__/**",
    "!**/*.d.ts",
    "!**/index.ts",
    "!**/*.config.ts",
    "!**/*.config.mjs",
    "!**/generated/**",
    "!**/fixtures/**",
    "!**/mocks/**",
  ],

  // === Thresholds ===
  // high: score at or above this is green in the report
  // low: score between low and high is yellow (warning)
  // break: score below this FAILS the run (exit code 1)
  thresholds: {
    high: 80,
    low: 60,
    break: 60,
  },

  // === Incremental Mode ===
  // Only mutate files that changed since the last run.
  // Dramatically faster for local development.
  incremental: true,
  incrementalFile: ".stryker-incremental.json",

  // === Reporting ===
  reporters: ["html", "clear-text", "progress", "json"],
  htmlReporter: {
    fileName: "reports/mutation/index.html",
  },
  jsonReporter: {
    fileName: "reports/mutation/mutation-report.json",
  },
};

export default config;
```

### Key Configuration Decisions

**`testRunner: "vitest"`** -- Stryker runs your existing Vitest suite against each mutant. No separate test framework, no duplicate configuration. The same tests that run in `pnpm test` verify mutants.

**`checkers: ["typescript"]`** -- The TypeScript checker eliminates mutants that produce compile errors before running tests against them. Without it, Stryker generates mutants like changing a number to a string, then wastes 5-10 seconds per mutant discovering that TypeScript would have caught the error. On a codebase with 2,000+ mutants, the checker saves 30-60 minutes per full run.

**`incremental: true`** -- Stores results in `.stryker-incremental.json`. On subsequent runs, only files that changed since the last run are mutated. A full run that takes 45 minutes drops to 2-3 minutes for a typical PR. Commit the incremental file to version control so CI can reuse previous results.

**`thresholds.break: 60`** -- The build fails if the mutation score drops below 60%. Start conservatively and ratchet up as tests improve. A well-tested codebase should aim for `break: 80` on critical packages.

### Package Scripts

```json
{
  "scripts": {
    "test:mutation": "stryker run",
    "test:mutation:incremental": "stryker run --incremental"
  }
}
```

Use `test:mutation:incremental` during development -- it only mutates files that changed since the last run. Use `test:mutation` in CI for the authoritative check.

### How Mutation Score Complements Coverage

Coverage and mutation score answer different questions:

```
Coverage:        "Did this line execute during tests?"
Mutation score:  "Did any test actually verify what this line does?"
```

A concrete example. This function has 100% line, branch, function, and statement coverage with the test below it:

```typescript
function clampPrice(price: number, min: number, max: number): number {
  if (price < min) return min;
  if (price > max) return max;
  return price;
}

it("handles all branches", () => {
  expect(clampPrice(5, 0, 10)).toBeDefined();
  expect(clampPrice(-1, 0, 10)).toBeDefined();
  expect(clampPrice(99, 0, 10)).toBeDefined();
});
```

Coverage: 100%. Mutation score: ~30%. The assertions are too loose -- `toBeDefined()` passes regardless of the return value. Stryker would generate mutants like `price < min -> price <= min`, `return min -> return max`, `return price -> return 0`, and every one of them would survive because no test checks the actual values.

Fixing the test to assert exact values (`toBe(5)`, `toBe(0)`, `toBe(10)`) kills all the mutants. The coverage number does not change. The mutation score jumps to 100%.

## Property-Based Testing with fast-check

Property-based testing generates random inputs and verifies that properties (invariants) hold for every input. Instead of writing individual test cases with specific values, you describe *what should always be true* and let the framework find counterexamples.

This is fundamentally different from example-based testing. An example-based test says "when I pass 5, I get 10." A property-based test says "for any positive integer, the result is always even" -- and then generates hundreds of random positive integers to verify.

### Installation

`fast-check` is the standard property-based testing library for TypeScript. The `@fast-check/vitest` package adds first-class Vitest integration.

```bash
pnpm add -Dw fast-check @fast-check/vitest
```

If you have a shared testing package, add `fast-check` there so every package can use it without individual installation:

```json
{
  "dependencies": {
    "fast-check": "^4.4.0",
    "@fast-check/vitest": "^0.1.3"
  }
}
```

### Core Pattern 1: Roundtrip (Encode/Decode)

If you encode a value and decode it, you should get the original value back. This property catches serialization bugs, off-by-one errors in parsers, and encoding edge cases.

```typescript
import { describe, it, expect } from "vitest";
import fc from "fast-check";

describe("URL-safe base64 encoding", () => {
  it("roundtrips any string", () => {
    fc.assert(
      fc.property(fc.string(), (original) => {
        const encoded = toUrlSafeBase64(original);
        const decoded = fromUrlSafeBase64(encoded);
        expect(decoded).toBe(original);
      })
    );
  });

  it("roundtrips any byte array", () => {
    fc.assert(
      fc.property(fc.uint8Array({ minLength: 0, maxLength: 1024 }), (bytes) => {
        const encoded = encodeBytes(bytes);
        const decoded = decodeBytes(encoded);
        expect(decoded).toEqual(bytes);
      })
    );
  });
});
```

The roundtrip pattern applies to any encode/decode, serialize/deserialize, or format/parse pair: JSON serialization, URL encoding, date formatting, binary protocols, compression.

### Core Pattern 2: Invariant (Output Properties)

Some functions produce output that must always satisfy a property regardless of input. Sorting must produce a sorted array. Clamping must produce a value within bounds. Normalization must produce a value between 0 and 1.

```typescript
describe("sorting", () => {
  it("always produces a sorted array", () => {
    fc.assert(
      fc.property(fc.array(fc.integer()), (arr) => {
        const sorted = mySort(arr);
        for (let i = 1; i < sorted.length; i++) {
          expect(sorted[i]).toBeGreaterThanOrEqual(sorted[i - 1]);
        }
      })
    );
  });

  it("preserves array length", () => {
    fc.assert(
      fc.property(fc.array(fc.integer()), (arr) => {
        expect(mySort(arr)).toHaveLength(arr.length);
      })
    );
  });

  it("preserves all elements", () => {
    fc.assert(
      fc.property(fc.array(fc.integer()), (arr) => {
        const sorted = mySort(arr);
        expect(sorted.slice().sort()).toEqual(arr.slice().sort());
      })
    );
  });
});

describe("clamp", () => {
  it("always returns a value within bounds", () => {
    fc.assert(
      fc.property(
        fc.double({ noNaN: true }),
        fc.double({ noNaN: true }),
        fc.double({ noNaN: true }),
        (value, a, b) => {
          const min = Math.min(a, b);
          const max = Math.max(a, b);
          const result = clamp(value, min, max);
          expect(result).toBeGreaterThanOrEqual(min);
          expect(result).toBeLessThanOrEqual(max);
        }
      )
    );
  });
});
```

### Core Pattern 3: Oracle (Reference Implementation)

Compare your optimized implementation against a known-correct reference. This is especially useful when you have a simple-but-slow implementation and a fast-but-complex one.

```typescript
describe("fast median calculation", () => {
  // Simple reference implementation (O(n log n))
  function referenceMedian(values: number[]): number {
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 === 0
      ? (sorted[mid - 1] + sorted[mid]) / 2
      : sorted[mid];
  }

  it("matches the reference implementation for any non-empty array", () => {
    fc.assert(
      fc.property(
        fc.array(fc.double({ noNaN: true, noDefaultInfinity: true }), {
          minLength: 1,
          maxLength: 1000,
        }),
        (values) => {
          const fast = fastMedian(values);
          const reference = referenceMedian(values);
          expect(fast).toBeCloseTo(reference, 10);
        }
      )
    );
  });
});
```

The oracle pattern works for any case where two implementations should agree: a new parser vs. the old one, a cached result vs. a fresh computation, a vectorized calculation vs. a scalar loop.

### Custom Arbitraries for Domain Types

Build arbitraries that match your domain types. This ensures generated values are realistic and satisfy type constraints:

```typescript
import fc from "fast-check";
import type { OhlcvCandle, SymbolId, Timeframe } from "@scope/core-domain";

// Arbitrary for a valid OHLCV candle
const arbOhlcvCandle: fc.Arbitrary<OhlcvCandle> = fc
  .record({
    open: fc.double({ min: 0.01, max: 100000, noNaN: true }),
    close: fc.double({ min: 0.01, max: 100000, noNaN: true }),
    volume: fc.double({ min: 0, max: 1e12, noNaN: true }),
    timestamp: fc.date({ min: new Date("2020-01-01"), max: new Date("2030-01-01") }),
  })
  .chain(({ open, close, volume, timestamp }) => {
    // high must be >= max(open, close), low must be <= min(open, close)
    const ceiling = Math.max(open, close);
    const floor = Math.min(open, close);
    return fc.record({
      open: fc.constant(open),
      close: fc.constant(close),
      high: fc.double({ min: ceiling, max: ceiling * 1.5, noNaN: true }),
      low: fc.double({ min: floor * 0.5, max: floor, noNaN: true }),
      volume: fc.constant(volume),
      timestamp: fc.constant(timestamp),
    });
  }) as fc.Arbitrary<OhlcvCandle>;

// Arbitrary for valid symbol IDs
const arbSymbolId: fc.Arbitrary<SymbolId> = fc.constantFrom(
  "COINBASE_SPOT_BTC_USD",
  "COINBASE_SPOT_ETH_USD",
  "COINBASE_SPOT_SOL_USD"
) as fc.Arbitrary<SymbolId>;

// Arbitrary for valid timeframes
const arbTimeframe: fc.Arbitrary<Timeframe> = fc.constantFrom(
  "1m", "5m", "15m", "1h", "4h", "1d"
) as fc.Arbitrary<Timeframe>;

// Use in tests
describe("candle aggregation", () => {
  it("aggregated high is always >= any constituent high", () => {
    fc.assert(
      fc.property(
        fc.array(arbOhlcvCandle, { minLength: 2, maxLength: 100 }),
        (candles) => {
          const aggregated = aggregateCandles(candles);
          const maxHigh = Math.max(...candles.map((c) => c.high));
          expect(aggregated.high).toBeCloseTo(maxHigh, 10);
        }
      )
    );
  });
});
```

### Vitest Integration with @fast-check/vitest

The `@fast-check/vitest` package provides `test.prop` for cleaner syntax:

```typescript
import { test } from "@fast-check/vitest";
import fc from "fast-check";

test.prop([fc.string()], "encoded string is always valid base64", ([input]) => {
  const encoded = toBase64(input);
  expect(() => atob(encoded)).not.toThrow();
});

test.prop(
  [fc.integer({ min: 0 }), fc.integer({ min: 0 })],
  "addition is commutative",
  ([a, b]) => {
    expect(add(a, b)).toBe(add(b, a));
  }
);

test.prop(
  [fc.array(fc.integer(), { minLength: 1 })],
  "max element is always in the original array",
  ([arr]) => {
    const result = findMax(arr);
    expect(arr).toContain(result);
  }
);
```

`test.prop` handles the `fc.assert(fc.property(...))` boilerplate and integrates with Vitest's test runner, including `.skip`, `.only`, and `.each` modifiers.

### When to Use Property-Based Testing

Property-based testing is most effective for **pure functions** -- functions where the output depends only on the input, with no side effects. The best candidates:

| Category | Examples | Properties to Test |
|----------|----------|--------------------|
| Parsers | URL parser, CSV parser, date parser | Roundtrip with formatter, no crashes on random input |
| Formatters | Currency formatter, date formatter | Roundtrip with parser, output matches regex pattern |
| Calculators | Tax calculation, PnL, statistics | Invariants (e.g., total >= 0), oracle against reference |
| Serializers | JSON codec, protobuf, binary protocol | Roundtrip, encoded size > 0 |
| Validators | Email validator, schema validator | Valid inputs pass, invalid inputs fail, no crashes |
| Data structures | Sort, filter, merge, deduplicate | Output invariants (sorted, subset, unique) |

Property-based testing is less useful for functions with complex side effects (database writes, API calls) or functions where the correct output is not easily described as a property.

### Coverage Boost: Property Tests and Mutation Scores

Property-based tests dramatically improve mutation scores because they test edge cases that humans do not think of. A property test for a sorting function generates empty arrays, single-element arrays, arrays with duplicates, arrays with negative numbers, arrays with `Number.MAX_SAFE_INTEGER`, and thousands of other combinations.

Each of these generated inputs exercises boundary conditions that kill mutants. Where an example-based test with 5 hand-picked inputs might kill 70% of mutants, a property-based test generating 100 random inputs typically kills 90%+.

The combination is powerful: use example-based tests for specific known scenarios and regression cases, then use property-based tests to cover the space between your examples. Together they produce mutation scores that are difficult to achieve with either approach alone.

## Summary: What Runs Where

| Layer | What Runs | Speed | Trigger |
|-------|-----------|-------|---------|
| Pre-commit | Unit tests (affected packages only) | Seconds | `git commit` |
| Pre-commit | Assertion density check (warning) | Instant | `git commit` |
| Pre-commit | Coverage gaming detection | Instant | `git commit` |
| Pre-push | Unit tests with coverage | Minutes | `git push` |
| Pre-push | Integration tests (if DB available) | Minutes | `git push` |
| Pre-push | Mutation testing (incremental) | Minutes | `git push` |
| CI | Unit tests (sharded) | Minutes | PR / push |
| CI | Integration tests (fresh DB) | Minutes | PR / push |
| CI | Mutation testing (incremental) | Minutes | PR / push |
| CI (nightly) | Mutation testing (full) | Hours | Scheduled |
| CI | Playwright E2E | Minutes | Post-deploy |
| Post-deploy | Smoke tests | Seconds | After deployment |

The goal: every layer catches a different class of problem. Unit tests catch logic errors. Property-based tests catch edge cases in pure functions. Mutation testing catches weak assertions and untested behaviors. Integration tests catch database interaction errors. E2E tests catch rendering and API contract errors. Smoke tests catch deployment and infrastructure errors. No single layer is sufficient on its own, but together they make it extremely difficult for broken code to reach users.
