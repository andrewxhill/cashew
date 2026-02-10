# Mutation Testing

Coverage measures execution. Mutation testing measures verification. A test suite with 90% line coverage and 40% mutation score is a test suite that runs most of the code but checks almost none of it. This reference covers why coverage lies, how to set up mutation testing in a TypeScript monorepo and other languages, and how to integrate it into the quality gate pipeline.

Mutation testing is the single most powerful test quality gate. It is the only metric that answers the question: "Do my tests actually catch bugs?"

## Table of Contents

1. [Why Coverage Lies](#1-why-coverage-lies)
2. [Stryker for TypeScript/JavaScript](#2-stryker-for-typescriptjavascript)
3. [Interpreting Results](#3-interpreting-results)
4. [Thresholds and Enforcement](#4-thresholds-and-enforcement)
5. [Incremental Mutation Testing](#5-incremental-mutation-testing)
6. [Property-Based Testing as a Complement](#6-property-based-testing-as-a-complement)
7. [Contract Testing](#7-contract-testing)
8. [Pre-push and CI Integration](#8-pre-push-and-ci-integration)
9. [Per-Language Equivalents](#9-per-language-equivalents)
10. [Anti-Gaming](#10-anti-gaming)

## 1. Why Coverage Lies

90% line coverage means 90% of lines were *executed* during tests. It does not mean 90% of behavior was *verified*. A test that calls a function and never asserts the result gets full coverage credit.

Consider this function:

```typescript
function add(a: number, b: number): number {
  return a + b;
}
```

This test gives 100% line, branch, function, and statement coverage:

```typescript
it("calls add", () => {
  add(1, 2);
});
```

No assertion. No verification. 100% coverage. The function could return `a - b`, `a * b`, `0`, or `"hello"` and this test would still pass. Coverage says everything is fine. Coverage is wrong.

A more realistic example:

```typescript
function calculateDiscount(price: number, quantity: number): number {
  if (quantity > 100) {
    return price * 0.2;
  }
  if (quantity > 10) {
    return price * 0.1;
  }
  return 0;
}
```

This test achieves 100% line and branch coverage:

```typescript
it("handles all discount tiers", () => {
  expect(calculateDiscount(100, 150)).toBeGreaterThan(0);
  expect(calculateDiscount(100, 50)).toBeGreaterThan(0);
  expect(calculateDiscount(100, 5)).toBe(0);
});
```

But the assertions are too loose. The first assertion passes whether the discount is 20, 10, 1, or 99. Change `price * 0.2` to `price * 0.9` and every test still passes. The test *executed* the code but did not *verify* the behavior.

### How Mutation Testing Fixes This

Mutation testing asks a different question: **"If I change the code, does a test fail?"**

A mutation testing tool creates *mutants* -- deliberate, small changes to the source code. Each mutant is a version of the code with one specific modification:

- `a + b` becomes `a - b`
- `quantity > 100` becomes `quantity >= 100`
- `return price * 0.2` becomes `return price * 0.1`
- `return 0` becomes `return 1`
- `if (condition)` becomes `if (true)` or `if (false)`

For each mutant, the tool runs your test suite. If a test fails, the mutant is **killed** -- your tests caught the change. If no test fails, the mutant **survived** -- your tests have a gap.

**Mutation score** = killed mutants / total mutants.

A function with 100% code coverage but 50% mutation score has tests that run every line but only actually verify half the behavior. The surviving mutants tell you exactly which behaviors are untested.

For the loose-assertion example above, a mutation tool would:
1. Change `price * 0.2` to `price * 0.1` -- mutant survives (test only checks `> 0`)
2. Change `price * 0.2` to `price * 0.9` -- mutant survives (test only checks `> 0`)
3. Change `quantity > 100` to `quantity >= 100` -- mutant survives (no test at boundary)
4. Change `quantity > 100` to `quantity < 100` -- mutant killed (test with quantity=150 now returns 0)

Three surviving mutants. Three gaps in your tests. Coverage told you nothing.

### Why Mutation Score Is the Only Honest Measure

Coverage metrics can be satisfied by accident. Run a function as a side effect of testing something else, and coverage goes up. Mutation score cannot be inflated by accident. Every killed mutant requires a test that:

1. Exercises the specific code path
2. Depends on the exact behavior at that location
3. Asserts the result precisely enough to detect a change

No other metric demands all three. Assertion density catches tests with no assertions but misses loose assertions. Branch coverage catches dead branches but misses wrong computations. Only mutation testing catches everything.

## 2. Stryker for TypeScript/JavaScript

[Stryker](https://stryker-mutator.io/) is the mutation testing framework for JavaScript and TypeScript. It integrates with Vitest, supports TypeScript type checking, and generates HTML reports.

### Installation

```bash
pnpm add -Dw @stryker-mutator/core @stryker-mutator/vitest-runner @stryker-mutator/typescript-checker
```

### Root Configuration

Create `stryker.config.mjs` at the repository root:

```javascript
// stryker.config.mjs
// === MUTATION TESTING CONFIGURATION ===
// Measures test verification quality, not just execution.
// If a mutant survives, your tests have a gap.

/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
const config = {
  // === Test Runner ===
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

  // === Mutator Configuration ===
  // All operators enabled by default. List explicitly for visibility.
  mutator: {
    plugins: null, // null = all built-in plugins

    // Files to mutate. Only production source code -- never tests,
    // configs, or generated files.
    includedMutations: [
      "ArithmeticOperator",    // + to -, * to /, etc.
      "ArrayDeclaration",      // [1,2,3] to []
      "AssignmentOperator",    // += to -=, etc.
      "BlockStatement",        // { code } to {}
      "BooleanLiteral",        // true to false
      "ConditionalExpression", // > to >=, > to <, condition to true/false
      "EqualityOperator",      // === to !==
      "LogicalOperator",       // && to ||
      "ObjectLiteral",         // { key: val } to {}
      "OptionalChaining",      // ?. to .
      "StringLiteral",         // "hello" to ""
      "UnaryOperator",         // -a to a, !a to a
      "UpdateOperator",        // i++ to i--
    ],
  },

  // === File Patterns ===
  // Production code only -- never tests, configs, or generated files.
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
  // Dramatically faster for day-to-day development.
  incremental: true,
  incrementalFile: ".stryker-incremental.json",

  // === Concurrency ===
  // Each mutant runs the full test suite, so this is CPU-bound.
  // Default is (cpuCount - 1). Reduce if your tests are memory-heavy.
  concurrency: 4,

  // === Timeouts ===
  // If a mutant causes an infinite loop, kill it after this duration.
  // Default factor is 1.5x the normal test run time.
  timeoutMS: 60000,
  timeoutFactor: 2,

  // === Reporting ===
  reporters: ["html", "clear-text", "progress", "json"],
  htmlReporter: {
    fileName: "reports/mutation/index.html",
  },
  jsonReporter: {
    fileName: "reports/mutation/mutation-report.json",
  },

  // === Dashboard Reporter (optional) ===
  // Sends results to https://dashboard.stryker-mutator.io/
  // Requires STRYKER_DASHBOARD_API_KEY environment variable.
  // Uncomment to enable:
  // reporters: ["html", "clear-text", "progress", "json", "dashboard"],
  // dashboard: {
  //   project: "github.com/your-org/your-repo",
  //   version: "main",
  //   module: "root",
  //   baseUrl: "https://dashboard.stryker-mutator.io/api/reports",
  // },

  // === Logging ===
  logLevel: "info",
  fileLogLevel: "trace",

  // === Temp Dir ===
  tempDirName: ".stryker-tmp",
};

export default config;
```

### Per-Package Stryker Configs

For monorepos, you have two strategies. Use the root config with `--mutate` globs for simplicity, or per-package configs for independent thresholds.

**Strategy 1: Root config with --mutate overrides (simpler)**

```bash
# Mutate only core-domain from the repo root
pnpm stryker run --mutate "packages/core-domain/src/**/*.ts,!**/*.test.ts"
```

**Strategy 2: Per-package configs (recommended for different thresholds)**

```javascript
// packages/core-domain/stryker.config.mjs
/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
const config = {
  testRunner: "vitest",
  vitest: {
    configFile: "vitest.config.ts",
    dir: ".",
  },
  checkers: ["typescript"],
  mutate: [
    "src/**/*.ts",
    "!src/**/*.test.ts",
    "!src/**/__tests__/**",
    "!src/**/*.d.ts",
    "!src/index.ts",
  ],
  // Core domain gets a HIGHER threshold -- this is the most critical code
  thresholds: {
    high: 85,
    low: 70,
    break: 70,
  },
  incremental: true,
  incrementalFile: ".stryker-incremental.json",
  concurrency: 4,
  reporters: ["html", "clear-text", "progress"],
  htmlReporter: {
    fileName: "reports/mutation/index.html",
  },
};

export default config;
```

### Package Scripts

Root `package.json`:

```json
{
  "scripts": {
    "mutation-test": "stryker run",
    "mutation-test:incremental": "stryker run --incremental",
    "mutation-test:report": "stryker run && open reports/mutation/index.html"
  }
}
```

Per-package `package.json`:

```json
{
  "scripts": {
    "mutation-test": "stryker run --configFile stryker.config.mjs"
  }
}
```

Turbo pipeline (`turbo.json`):

```json
{
  "tasks": {
    "mutation-test": {
      "dependsOn": ["^build"],
      "outputs": ["reports/mutation/**"],
      "cache": false
    }
  }
}
```

Mutation tests should not be cached because they depend on the full source + test content, and the incremental file handles its own caching.

### Stryker Dashboard Reporter

For tracking mutation scores over time across branches and PRs, use the [Stryker Dashboard](https://dashboard.stryker-mutator.io/):

1. Sign in with GitHub at dashboard.stryker-mutator.io
2. Enable your repository
3. Copy the API key and set it as `STRYKER_DASHBOARD_API_KEY` in CI secrets
4. Add the dashboard reporter to your config:

```javascript
reporters: ["html", "clear-text", "progress", "json", "dashboard"],
dashboard: {
  project: "github.com/your-org/your-repo",
  version: "main",          // or use process.env.BRANCH_NAME
  module: "root",           // or per-package module names
  baseUrl: "https://dashboard.stryker-mutator.io/api/reports",
},
```

The dashboard provides historical trending, per-module breakdowns, and badge URLs for README files.

### Sample Output

```
  All tests
    core-domain
      ✓ calculateDiscount > returns 20% discount for quantity over 100  (2ms)
      ✓ calculateDiscount > returns 10% discount for quantity over 10   (1ms)
      ✓ calculateDiscount > returns 0 for quantity 10 or below          (1ms)

Mutation testing  [=====================] 100% (elapsed: 45s, remaining: ~0s)
   42 Mutant(s) tested
   36 Mutant(s) killed
    4 Mutant(s) survived
    2 Mutant(s) timed out (killed)

Mutation score: 90.48%
Threshold: 60% (break), 80% (high)
Status: PASS

Survived mutants:
  src/pricing.ts:12  ArithmeticOperator: replaced * with /
  src/pricing.ts:15  ConditionalExpression: replaced > with >=
  src/pricing.ts:18  ConditionalExpression: replaced > with >=
  src/pricing.ts:24  BooleanLiteral: replaced true with false
```

Each survived mutant is a test you need to write.

## 3. Interpreting Results

### Mutant Statuses

Every mutant gets one of these statuses after a run:

| Status | Meaning | Good or Bad? |
|---|---|---|
| **Killed** | A test failed when this mutation was applied | Good -- your test caught the bug |
| **Survived** | All tests passed with the mutation in place | Bad -- your tests have a gap |
| **No coverage** | The mutated code was never executed by any test | Bad -- untested code |
| **Timeout** | The mutation caused an infinite loop or hang | Counts as killed (tests detected something wrong) |
| **Compile error** | The mutation broke TypeScript compilation | Filtered out (not counted in score) |
| **Runtime error** | The mutation caused a runtime crash | Counts as killed |

### How to Read the HTML Report

Open `reports/mutation/index.html` after a run. The report has three levels:

1. **Directory overview** -- mutation score per directory, color-coded (green >= 80%, yellow >= 60%, red < 60%)
2. **File list** -- mutation score per file, with mutant count breakdown (killed, survived, no coverage, timeout)
3. **File detail** -- each line of source code with mutant indicators. Click a mutant to see the original code, the mutated code, and its status.

Start from the file detail view. For each surviving mutant, the report shows the exact line and character position, plus what the mutation changed. This is your todo list.

### Mutation Operators and What They Catch

| Operator | Original | Mutant | What It Tests |
|---|---|---|---|
| ArithmeticOperator | `a + b` | `a - b` | Math correctness |
| ArithmeticOperator | `a * b` | `a / b` | Multiplication vs division |
| ArithmeticOperator | `a % b` | `a * b` | Modulo logic |
| ConditionalExpression | `a > b` | `a >= b` | Boundary conditions (off-by-one) |
| ConditionalExpression | `a > b` | `a < b` | Comparison direction |
| ConditionalExpression | `a > b` | `true` | Branch necessity |
| ConditionalExpression | `a > b` | `false` | Branch necessity |
| BooleanLiteral | `true` | `false` | Boolean logic paths |
| BooleanLiteral | `false` | `true` | Default/fallback behavior |
| StringLiteral | `"hello"` | `""` | String handling, empty string edge case |
| ArrayDeclaration | `[1, 2, 3]` | `[]` | Collection handling, empty array edge case |
| BlockStatement | `{ doWork(); }` | `{}` | Side effect verification (is the work needed?) |
| EqualityOperator | `===` | `!==` | Equality check correctness |
| EqualityOperator | `!==` | `===` | Inequality check correctness |
| LogicalOperator | `a && b` | `a \|\| b` | Boolean composition |
| LogicalOperator | `a \|\| b` | `a && b` | Fallback vs requirement logic |
| UnaryOperator | `-a` | `a` | Sign handling, negation |
| UnaryOperator | `!a` | `a` | Boolean negation |
| UpdateOperator | `i++` | `i--` | Loop direction, counter logic |
| UpdateOperator | `i--` | `i++` | Decrement logic |
| AssignmentOperator | `x += 1` | `x -= 1` | Compound assignment correctness |
| ObjectLiteral | `{ key: value }` | `{}` | Object construction, property necessity |
| OptionalChaining | `obj?.prop` | `obj.prop` | Null safety (is the `?` needed?) |

### Common Survived Mutants and What They Mean

**Boundary mutations (`<` vs `<=`) survive** -- You have no test at the boundary value. If the condition is `quantity > 100`, you need tests at exactly 100, 101, and 99.

**Conditional removal (replaced with `true` or `false`) survives** -- The test does not depend on the condition. Either the condition is dead code, or your tests do not exercise both branches.

**String mutations (replaced with `""`) survive** -- The test does not verify string content. You are using `toThrow()` instead of `toThrow("specific message")`, or you never assert on the string output at all.

**Return value mutations survive** -- The test ignores return values. You are calling functions without inspecting what they return.

**Arithmetic mutations (`*` vs `/`) survive** -- Assertions are too loose. You are using `toBeGreaterThan(0)` when you should use `toBe(20)`.

**Block statement removal survives** -- Removing an entire block of code does not cause any test to fail. The block is either dead code, or your tests do not verify its side effects.

### Fixing Survived Mutants: Patterns

#### Pattern 1: Missing boundary tests

```
ConditionalExpression: replaced > with >= at line 12
```

```typescript
// Source
function isAdult(age: number): boolean {
  return age > 18;
}

// BAD: no boundary test
expect(isAdult(25)).toBe(true);
expect(isAdult(10)).toBe(false);

// GOOD: test the boundary
expect(isAdult(18)).toBe(false);  // exact boundary
expect(isAdult(19)).toBe(true);   // boundary + 1
```

#### Pattern 2: Loose assertions

```
ArithmeticOperator: replaced * with / at line 8
```

```typescript
// Source
function calculateTax(amount: number, rate: number): number {
  return amount * rate;
}

// BAD: 100 / 0.1 = 1000, also greater than 0
expect(calculateTax(100, 0.1)).toBeGreaterThan(0);

// GOOD: assert exact value
expect(calculateTax(100, 0.1)).toBe(10);
expect(calculateTax(200, 0.25)).toBe(50);
```

#### Pattern 3: Missing negative path

```
BooleanLiteral: replaced false with true at line 15
```

```typescript
// Source
function isValidEmail(email: string): boolean {
  if (!email.includes("@")) return false;
  return true;
}

// BAD: only happy path
expect(isValidEmail("user@example.com")).toBe(true);

// GOOD: test the rejection path
expect(isValidEmail("invalid-email")).toBe(false);
expect(isValidEmail("")).toBe(false);
```

#### Pattern 4: Verifying calls but not results

```
BlockStatement: removed block at line 22
```

```typescript
// BAD: only checks that a function was called
expect(mockSave).toHaveBeenCalled();

// GOOD: verify what was passed and what was returned
expect(mockSave).toHaveBeenCalledWith(
  expect.objectContaining({ price: expect.any(Number) })
);
expect(result.id).toBe(1);
```

#### Pattern 5: String literal in error messages

```
StringLiteral: replaced "Invalid input" with "" at line 5
```

```typescript
// BAD: toThrow() matches any error
expect(() => process(null)).toThrow();

// GOOD: match the error message
expect(() => process(null)).toThrow("Invalid input");
// or for resilience:
expect(() => process(null)).toThrow(/[Ii]nvalid/);
```

## 4. Thresholds and Enforcement

### Recommended Thresholds

| Codebase State | break | low (warn) | high (green) |
|---|---|---|---|
| Legacy (no mutation testing before) | 30 | 40 | 60 |
| Some test coverage (70%+ lines) | 50 | 60 | 80 |
| Well-tested (90%+ lines, good assertions) | 80 | 85 | 95 |

### Per-Package Thresholds

Different packages warrant different thresholds based on risk:

| Package Type | Minimum break Threshold |
|---|---|
| Financial calculations | 85 |
| Data processing / ETL | 80 |
| Core domain logic | 75 |
| API routes / controllers | 60 |
| UI components | 50 |
| Infrastructure / config | 40 |

### Enforcement Script

This script runs Stryker and enforces thresholds with clear output. Use it in pre-push hooks and CI.

```bash
#!/usr/bin/env bash
# scripts/mutation-check.sh
# Runs mutation testing and enforces score thresholds.
# Usage: ./scripts/mutation-check.sh [threshold]
# Exit code 0 = pass, 1 = score below threshold, 2 = stryker error.
set -euo pipefail

REPORT_FILE="reports/mutation/mutation-report.json"
DEFAULT_BREAK_THRESHOLD=60

# Accept an optional threshold override
BREAK_THRESHOLD="${1:-$DEFAULT_BREAK_THRESHOLD}"

echo "=== Mutation Testing ==="
echo "Break threshold: ${BREAK_THRESHOLD}%"
echo ""

# Run Stryker
if ! pnpm stryker run; then
  echo ""
  echo "ERROR: Stryker run failed."
  echo "Check the output above for details."
  exit 2
fi

# Verify report exists
if [ ! -f "$REPORT_FILE" ]; then
  echo "ERROR: Mutation report not found at $REPORT_FILE"
  echo "Stryker may have failed silently. Check logs."
  exit 2
fi

# Extract score from JSON report
SCORE=$(node -e "
  const report = require('./$REPORT_FILE');
  const files = report.files || {};
  let killed = 0, total = 0;
  for (const f of Object.values(files)) {
    for (const m of f.mutants) {
      total++;
      if (m.status === 'Killed' || m.status === 'Timeout') killed++;
    }
  }
  const score = total > 0 ? (killed / total * 100) : 100;
  console.log(score.toFixed(1));
")

SURVIVED=$(node -e "
  const report = require('./$REPORT_FILE');
  const files = report.files || {};
  let survived = 0;
  for (const f of Object.values(files)) {
    for (const m of f.mutants) {
      if (m.status === 'Survived') survived++;
    }
  }
  console.log(survived);
")

echo ""
echo "Mutation score: ${SCORE}%"
echo "Survived mutants: ${SURVIVED}"
echo "Break threshold: ${BREAK_THRESHOLD}%"
echo ""

# Compare as integers (bash does not do float comparison)
SCORE_INT=$(echo "$SCORE" | cut -d. -f1)

if [ "$SCORE_INT" -lt "$BREAK_THRESHOLD" ]; then
  echo "FAIL: Mutation score ${SCORE}% is below threshold ${BREAK_THRESHOLD}%"
  echo ""
  echo "To investigate:"
  echo "  open reports/mutation/index.html"
  echo ""
  echo "To fix:"
  echo "  1. Open the HTML report and find survived mutants"
  echo "  2. Write tests that verify the specific behaviors"
  echo "  3. Re-run: pnpm mutation-test"
  exit 1
fi

echo "PASS: Mutation score ${SCORE}% meets threshold ${BREAK_THRESHOLD}%"
```

Make it executable: `chmod +x scripts/mutation-check.sh`

### Ratcheting: Locking In Improvements

Ratcheting prevents regression. After a quality sprint that improves mutation score, lock in the new floor so it can never drop back.

```bash
#!/usr/bin/env bash
# scripts/ratchet-mutation-threshold.sh
# Reads current mutation score and prints the new threshold values.
# Run after each quality improvement cycle.
set -euo pipefail

STRYKER_CONFIG="stryker.config.mjs"
REPORT_FILE="reports/mutation/mutation-report.json"

if [ ! -f "$REPORT_FILE" ]; then
  echo "No mutation report found. Run 'pnpm mutation-test' first."
  exit 1
fi

# Extract current score from the JSON report
CURRENT_SCORE=$(node -e "
  const report = require('./$REPORT_FILE');
  const files = report.files || {};
  let killed = 0, total = 0;
  for (const f of Object.values(files)) {
    for (const m of f.mutants) {
      total++;
      if (m.status === 'Killed' || m.status === 'Timeout') killed++;
    }
  }
  console.log(total > 0 ? Math.floor(killed / total * 100) : 0);
")

# Read current break threshold
CURRENT_THRESHOLD=$(node -e "
  import('file://$PWD/$STRYKER_CONFIG').then(m => {
    const config = m.default;
    console.log(config.thresholds?.break || 0);
  });
")

echo "Current mutation score: ${CURRENT_SCORE}%"
echo "Current break threshold: ${CURRENT_THRESHOLD}%"

# Ratchet: set threshold to 5% below current score (floor for safety margin)
NEW_THRESHOLD=$((CURRENT_SCORE - 5))

if [ "$NEW_THRESHOLD" -le "$CURRENT_THRESHOLD" ]; then
  echo "Threshold already at or above ratchet target ($CURRENT_THRESHOLD% >= $NEW_THRESHOLD%)."
  echo "No change needed."
  exit 0
fi

echo ""
echo "Ratcheting break threshold: ${CURRENT_THRESHOLD}% -> ${NEW_THRESHOLD}%"
echo ""
echo "Update $STRYKER_CONFIG:"
echo "  thresholds: {"
echo "    high: $((NEW_THRESHOLD + 20)),"
echo "    low: $((NEW_THRESHOLD + 10)),"
echo "    break: $NEW_THRESHOLD,"
echo "  }"
```

### Ratcheting Rules

1. **Thresholds only go up.** After a quality sprint that improves mutation score, lock in the new floor. Never lower a threshold.
2. **New packages start at 80% break.** There is no excuse for low mutation coverage on new code. The tests and the code are written together.
3. **Critical packages get priority ratcheting.** Financial calculations and data processing packages should reach 85%+ before anything else.
4. **Review surviving mutants in sprint retros.** The mutation report is a better conversation starter than coverage reports because it shows *specific* untested behaviors.
5. **Track the trend.** Keep a log of mutation scores over time. If the score drops on a PR, that PR introduced untested behavior.

## 5. Incremental Mutation Testing

Full mutation testing is slow. A codebase with 500 source files might generate 5,000+ mutants, each requiring a full test suite run. This can take 30 minutes to several hours.

Incremental mutation testing solves this by only mutating files that changed.

### How Stryker Incremental Works

Stryker's incremental mode stores results in a JSON file (`.stryker-incremental.json`). On subsequent runs, it:

1. Compares the current source files against the stored state
2. Only generates mutants for files that changed
3. Reuses results for unchanged files
4. Updates the incremental file with new results

### Configuration

Already included in the root config:

```javascript
{
  incremental: true,
  incrementalFile: ".stryker-incremental.json",
}
```

### Commit the Incremental File

Add `.stryker-incremental.json` to version control. This allows CI to reuse results from previous runs and avoids re-mutating the entire codebase on every PR.

```bash
git add .stryker-incremental.json
git commit -m "chore: add stryker incremental baseline"
```

Add the tmp directory to `.gitignore`:

```
# .gitignore
.stryker-tmp/
reports/mutation/
```

### Git Diff Integration

For pre-push hooks, you want to mutate only files changed since the base branch. This is faster than even Stryker's built-in incremental mode because it skips file comparison entirely and limits the mutation surface to exactly the changed code.

```bash
#!/usr/bin/env bash
# scripts/mutation-incremental.sh
# Runs mutation testing ONLY on files changed since the base branch.
# Intended for pre-push hooks where speed matters.
# Usage: ./scripts/mutation-incremental.sh [base-branch] [threshold]
set -euo pipefail

BASE_BRANCH="${1:-origin/main}"
BREAK_THRESHOLD="${2:-60}"

echo "=== Incremental Mutation Testing ==="
echo "Base: ${BASE_BRANCH}"
echo "Threshold: ${BREAK_THRESHOLD}%"
echo ""

# Get changed TypeScript files (production code only)
CHANGED_FILES=$(git diff --name-only --diff-filter=ACMR "${BASE_BRANCH}...HEAD" -- \
  'packages/*/src/**/*.ts' 'apps/*/src/**/*.ts' \
  | grep -v '\.test\.ts$' \
  | grep -v '\.spec\.ts$' \
  | grep -v '__tests__/' \
  | grep -v '\.d\.ts$' \
  | grep -v 'index\.ts$' \
  | grep -v '\.config\.' \
  || true)

if [ -z "$CHANGED_FILES" ]; then
  echo "No production TypeScript files changed. Skipping mutation testing."
  exit 0
fi

# Count and display files
FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')
echo "Changed files ($FILE_COUNT):"
echo "$CHANGED_FILES" | while read -r f; do echo "  $f"; done
echo ""

# Build the --mutate argument (comma-separated for Stryker)
MUTATE_ARG=$(echo "$CHANGED_FILES" | paste -sd, -)

# Run Stryker with explicit mutate targets
pnpm stryker run --mutate "$MUTATE_ARG" --incremental

echo ""
echo "Incremental mutation testing complete."
echo "Open reports/mutation/index.html for details."
```

Make it executable: `chmod +x scripts/mutation-incremental.sh`

### Run Strategies

| Context | Command | What It Does | Duration |
|---|---|---|---|
| Development | `pnpm mutation-test:incremental` | Mutates changed files only | 1-5 min |
| Pre-push | `scripts/mutation-incremental.sh` | Git-diff scoped, fail on threshold | 1-3 min |
| CI (PR) | `stryker run --incremental` | Mutates changed packages | 2-10 min |
| CI (nightly) | `stryker run --incremental=false` | Full mutation run, update baseline | 30-120 min |

### Nightly Full Run

Schedule a full mutation run nightly to catch accumulated drift and update the incremental baseline:

```yaml
# .github/workflows/mutation-nightly.yml
name: Nightly Mutation Testing

on:
  schedule:
    - cron: "0 3 * * *"  # 3 AM UTC daily
  workflow_dispatch:

jobs:
  mutation-test:
    runs-on: ubuntu-latest
    timeout-minutes: 180
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: "pnpm"

      - run: pnpm install --frozen-lockfile

      # Full mutation test (no incremental)
      - name: Run full mutation testing
        run: pnpm stryker run --incremental=false
        continue-on-error: true

      # Upload HTML report
      - name: Upload mutation report
        uses: actions/upload-artifact@v4
        with:
          name: mutation-report
          path: reports/mutation/
        if: always()

      # Update incremental baseline
      - name: Commit updated incremental file
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add .stryker-incremental.json
          git diff --cached --quiet || git commit -m "chore: update stryker incremental baseline"
          git push
```

## 6. Property-Based Testing as a Complement

Property-based testing and mutation testing are natural partners. Property-based tests generate hundreds of random inputs, which means they exercise far more code paths than hand-written example tests. This dramatically improves mutation scores because mutants that survive hand-written edge cases often get caught by the sheer volume and diversity of generated inputs.

### Setup with fast-check

[fast-check](https://github.com/dubzzz/fast-check) is the property-based testing library for TypeScript/JavaScript. It integrates directly with Vitest.

```bash
pnpm add -Dw fast-check @fast-check/vitest
```

### Pattern 1: Roundtrip (encode/decode)

If you have a pair of functions where one reverses the other, the roundtrip property guarantees they are inverses for *all* inputs. Not three example inputs -- *all* inputs.

```typescript
import fc from "fast-check";

describe("price formatting roundtrip", () => {
  it("formatPrice and parsePrice are inverses", () => {
    fc.assert(
      fc.property(
        fc.float({ min: 0, max: 1_000_000, noNaN: true }),
        (price) => {
          const formatted = formatPrice(price);
          const parsed = parsePrice(formatted);
          expect(parsed).toBeCloseTo(price, 2);
        }
      )
    );
  });

  it("serialization roundtrip preserves order data", () => {
    fc.assert(
      fc.property(
        fc.record({
          symbol: fc.constantFrom("BTC-USD", "ETH-USD", "SOL-USD"),
          price: fc.float({ min: 0.01, max: 100000, noNaN: true }),
          quantity: fc.float({ min: 0.001, max: 1000, noNaN: true }),
          side: fc.constantFrom("buy", "sell"),
        }),
        (order) => {
          const serialized = serializeOrder(order);
          const deserialized = deserializeOrder(serialized);
          expect(deserialized).toEqual(order);
        }
      )
    );
  });
});
```

**Why this kills mutants:** If `formatPrice` uses `*` instead of `/` somewhere, the roundtrip breaks for most inputs. Hand-written tests might only check `formatPrice(10.50)` and miss the bug for other values.

### Pattern 2: Invariants (output properties that always hold)

```typescript
describe("sorting invariants", () => {
  it("output is always sorted", () => {
    fc.assert(
      fc.property(fc.array(fc.integer()), (arr) => {
        const sorted = mySort(arr);
        for (let i = 1; i < sorted.length; i++) {
          expect(sorted[i]).toBeGreaterThanOrEqual(sorted[i - 1]);
        }
      })
    );
  });

  it("output has same length as input", () => {
    fc.assert(
      fc.property(fc.array(fc.integer()), (arr) => {
        const sorted = mySort(arr);
        expect(sorted).toHaveLength(arr.length);
      })
    );
  });

  it("output contains same elements as input", () => {
    fc.assert(
      fc.property(fc.array(fc.integer()), (arr) => {
        const sorted = mySort(arr);
        expect(sorted.slice().sort()).toEqual(arr.slice().sort());
      })
    );
  });
});
```

**Why this kills mutants:** A mutant that changes the comparison operator in the sort would produce unsorted output, caught by the ordering invariant. A mutant that drops elements would be caught by the length invariant.

### Pattern 3: Oracle (compare with a reference implementation)

When you have a fast, simple reference implementation and an optimized one, property tests verify they agree on all inputs.

```typescript
describe("optimized price formatter matches reference", () => {
  // Simple, obviously-correct reference implementation
  function referencePriceFormat(cents: number): string {
    return "$" + (cents / 100).toFixed(2);
  }

  it("matches reference for all valid cent values", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 99999999 }),
        (cents) => {
          const optimized = optimizedPriceFormat(cents);
          const reference = referencePriceFormat(cents);
          expect(optimized).toBe(reference);
        }
      ),
      { numRuns: 10000 }
    );
  });
});
```

### Real Example: Testing a Price Formatter with fast-check

This demonstrates how property-based tests kill mutants that hand-written tests miss:

```typescript
import fc from "fast-check";

// The function under test
function formatPrice(cents: number): string {
  const dollars = Math.floor(cents / 100);
  const remainder = cents % 100;
  return `$${dollars}.${remainder.toString().padStart(2, "0")}`;
}

describe("formatPrice", () => {
  // Hand-written tests -- good start but miss edge cases
  it("formats $10.50", () => {
    expect(formatPrice(1050)).toBe("$10.50");
  });

  it("formats $0.00", () => {
    expect(formatPrice(0)).toBe("$0.00");
  });

  // Property-based tests -- kill the remaining mutants
  it("always starts with $", () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 9999999 }), (cents) => {
        expect(formatPrice(cents)).toMatch(/^\$/);
      })
    );
  });

  it("always has exactly 2 decimal places", () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 9999999 }), (cents) => {
        const result = formatPrice(cents);
        const parts = result.replace("$", "").split(".");
        expect(parts).toHaveLength(2);
        expect(parts[1]).toHaveLength(2);
      })
    );
  });

  it("dollars and cents sum to original value", () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 9999999 }), (cents) => {
        const result = formatPrice(cents);
        const numeric = parseFloat(result.replace("$", ""));
        expect(Math.round(numeric * 100)).toBe(cents);
      })
    );
  });
});
```

The last property test (`dollars and cents sum to original value`) kills every arithmetic mutant in `formatPrice`. If `Math.floor` becomes `Math.ceil`, or `/ 100` becomes `* 100`, or `% 100` becomes `+ 100`, the roundtrip breaks for most inputs.

### Integration with Vitest

fast-check works with Vitest out of the box -- `fc.assert` throws on failure, which Vitest catches as a test failure. No special configuration needed.

For better ergonomics, use the `@fast-check/vitest` adapter:

```typescript
import { test } from "@fast-check/vitest";
import fc from "fast-check";

test.prop([fc.integer(), fc.integer()])("addition is commutative", (a, b) => {
  expect(add(a, b)).toBe(add(b, a));
});

test.prop([fc.array(fc.integer())])("sort is idempotent", (arr) => {
  const once = mySort(arr);
  const twice = mySort(once);
  expect(twice).toEqual(once);
});
```

## 7. Contract Testing

Contract testing verifies that services agree on their shared interfaces. Where unit tests verify internal behavior and mutation testing verifies test quality, contract tests verify that the *boundaries* between services are correct. A mutation in an API response shape that unit tests miss will be caught by a contract test.

### Why Contract Tests Catch Interface Mutations That Unit Tests Miss

Consider an API endpoint that returns order data. Unit tests for the endpoint mock the database and verify the response shape. Unit tests for the consumer mock the API and verify the parsing logic. If the producer changes the response shape, *both* sides' unit tests still pass because they are mocking the old contract. The bug ships.

Contract tests solve this by having both sides agree on a shared contract. When the producer mutates its response, the contract check fails -- even though all unit tests pass.

### Pact Setup for TypeScript

[Pact](https://docs.pact.io/) is the standard contract testing framework. It supports consumer-driven contracts where the consumer defines what it expects, and the provider verifies it can satisfy those expectations.

```bash
# Consumer side
pnpm add -Dw @pact-foundation/pact

# Producer side
pnpm add -Dw @pact-foundation/pact-core
```

### Consumer Test (the API client)

The consumer defines its expectations:

```typescript
// apps/frontend/src/__tests__/orders-api.pact.test.ts
import { PactV4, MatchersV3 } from "@pact-foundation/pact";

const { like, eachLike, integer, string, decimal } = MatchersV3;

const provider = new PactV4({
  consumer: "OrdersDashboard",
  provider: "OrdersAPI",
  dir: "./pacts",
});

describe("Orders API Contract", () => {
  it("returns a list of orders", async () => {
    await provider
      .addInteraction()
      .given("orders exist")
      .uponReceiving("a request for orders")
      .withRequest("GET", "/api/orders", (builder) => {
        builder.headers({ Accept: "application/json" });
      })
      .willRespondWith(200, (builder) => {
        builder
          .headers({ "Content-Type": "application/json" })
          .jsonBody(
            eachLike({
              id: integer(1),
              symbol: string("BTC-USD"),
              price: decimal(50000.0),
              quantity: decimal(0.5),
              side: string("buy"),
              status: string("filled"),
            })
          );
      })
      .executeTest(async (mockServer) => {
        const client = new OrdersClient(mockServer.url);
        const orders = await client.getOrders();

        expect(orders).toHaveLength(1);
        expect(orders[0].symbol).toBe("BTC-USD");
        expect(orders[0].side).toBe("buy");
      });
  });
});
```

### Provider Verification (the API server)

The provider verifies it satisfies the consumer's contract:

```typescript
// apps/api/src/__tests__/orders.pact-verify.test.ts
import { Verifier } from "@pact-foundation/pact";
import { app } from "../app";

describe("Orders API Provider Verification", () => {
  let server: ReturnType<typeof app.listen>;

  beforeAll(() => {
    server = app.listen(0);
  });

  afterAll(() => {
    server.close();
  });

  it("satisfies all consumer contracts", async () => {
    const address = server.address();
    const port = typeof address === "object" ? address?.port : 0;

    const verifier = new Verifier({
      providerBaseUrl: `http://localhost:${port}`,
      pactUrls: ["./pacts/OrdersDashboard-OrdersAPI.json"],
      stateHandlers: {
        "orders exist": async () => {
          await seedTestOrders();
        },
      },
    });

    await verifier.verifyProvider();
  });
});
```

### How Contract Tests Complement Mutation Testing

Mutation testing catches weak assertions within a service. Contract testing catches interface drift between services. Together they cover the full spectrum:

| What It Catches | Unit Tests | Mutation Testing | Contract Testing |
|---|---|---|---|
| Logic errors in a service | Sometimes | Always (if test exists) | No |
| Weak assertions | No | Yes | No |
| Interface shape drift | No | No | Yes |
| Missing error paths | Sometimes | Yes | Sometimes |
| Cross-service type changes | No | No | Yes |

Use mutation testing for internal quality. Use contract testing for boundary quality. Neither replaces the other.

## 8. Pre-push and CI Integration

### Pre-Push Hook Integration

Add incremental mutation testing to the pre-push hook. This runs after unit tests pass (no point mutating code with failing tests).

Add this block to `.husky/pre-push` after the tests-with-coverage check (CHECK 9 in the pre-push gates reference):

```bash
# ============================================================================
# CHECK 9b: Incremental mutation testing
# ============================================================================
header "9b" "Mutation testing (incremental)"
CHECK_START=$(date +%s)

# Only run if stryker is configured
if [ -f "stryker.config.mjs" ]; then
  # Prefer git-diff scoped mutation for speed
  if [ -f "scripts/mutation-incremental.sh" ]; then
    if bash scripts/mutation-incremental.sh "$BASE_BRANCH" 60; then
      pass $CHECK_START
    else
      fail $CHECK_START "Mutation testing failed (score below threshold)"
      echo -e "${RED}  Fix: Run 'pnpm mutation-test:report' to see surviving mutants${RESET}"
      echo -e "${RED}  Write tests that verify the specific behaviors flagged in the report.${RESET}"
    fi
  elif pnpm stryker run --incremental; then
    pass $CHECK_START
  else
    fail $CHECK_START "Mutation testing failed (score below threshold)"
    echo -e "${RED}  Fix: Run 'pnpm mutation-test:report' to see surviving mutants${RESET}"
    echo -e "${RED}  Write tests that verify the specific behaviors flagged in the report.${RESET}"
  fi
else
  skip "No stryker.config.mjs found"
fi
```

### CI Workflow (PR Check)

```yaml
# .github/workflows/mutation-pr.yml
name: Mutation Testing (PR)

on:
  pull_request:
    branches: [main]

jobs:
  mutation-test:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Need full history for incremental comparison

      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: "pnpm"

      - run: pnpm install --frozen-lockfile

      # Run incremental mutation testing
      - name: Run mutation testing
        run: pnpm stryker run --incremental

      # Upload HTML report as artifact
      - name: Upload mutation report
        uses: actions/upload-artifact@v4
        with:
          name: mutation-report
          path: reports/mutation/
        if: always()

      # Post mutation score as PR comment
      - name: Post mutation score
        if: always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const reportPath = 'reports/mutation/mutation-report.json';
            if (!fs.existsSync(reportPath)) return;

            const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
            const files = report.files || {};
            let killed = 0, survived = 0, timeout = 0, noCoverage = 0, total = 0;

            for (const f of Object.values(files)) {
              for (const m of f.mutants) {
                total++;
                if (m.status === 'Killed') killed++;
                else if (m.status === 'Timeout') timeout++;
                else if (m.status === 'Survived') survived++;
                else if (m.status === 'NoCoverage') noCoverage++;
              }
            }

            const score = total > 0
              ? ((killed + timeout) / total * 100).toFixed(1)
              : 'N/A';

            let body = `## Mutation Testing Results\n\n`;
            body += `| Metric | Value |\n|---|---|\n`;
            body += `| **Score** | ${score}% |\n`;
            body += `| Killed | ${killed} |\n`;
            body += `| Timeout (killed) | ${timeout} |\n`;
            body += `| **Survived** | **${survived}** |\n`;
            body += `| No coverage | ${noCoverage} |\n`;
            body += `| Total | ${total} |\n\n`;

            if (survived > 0) {
              body += `**${survived} mutant(s) survived.** `;
              body += `Download the HTML report from workflow artifacts for details.\n`;
            } else {
              body += `All mutants killed or timed out. Tests are thorough.\n`;
            }

            await github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body
            });
```

### Timing Expectations

| Scenario | Expected Duration |
|---|---|
| Pre-push (git-diff scoped, few files) | 1-3 minutes |
| CI PR (incremental, full packages) | 2-10 minutes |
| CI nightly (full, all packages) | 30-120 minutes |
| Local full run (development machine) | 15-60 minutes |

## 9. Per-Language Equivalents

### Python -- mutmut

[mutmut](https://github.com/boxed/mutmut) is the standard mutation testing tool for Python. Simple, fast, and opinionated.

**Install:**

```bash
pip install mutmut
```

**Run:**

```bash
mutmut run --paths-to-mutate=src/ --tests-dir=tests/
```

**View results:**

```bash
# Summary
mutmut results

# Show a specific surviving mutant
mutmut show 42

# HTML report
mutmut html
open html/index.html
```

**Configuration in `pyproject.toml`:**

```toml
[tool.mutmut]
paths_to_mutate = "src/"
tests_dir = "tests/"
runner = "python -m pytest -x --tb=short -q"
dict_synonyms = "Struct, NamedStruct"

# Exclude files from mutation
[tool.mutmut.exclude]
files = [
    "src/generated/*",
    "src/migrations/*",
    "src/__init__.py",
]
```

**CI integration:**

```bash
# Run and fail if any mutants survive
mutmut run --CI --paths-to-mutate=src/ --tests-dir=tests/

# Or with a threshold check:
mutmut run --paths-to-mutate=src/ --tests-dir=tests/
SURVIVED=$(mutmut results | grep -c "survived" || true)
if [ "$SURVIVED" -gt 0 ]; then
  echo "FAIL: $SURVIVED mutants survived"
  mutmut results
  exit 1
fi
```

### Python -- cosmic-ray

[cosmic-ray](https://github.com/sixty-north/cosmic-ray) is an alternative Python mutation tester with a database-backed architecture that supports distributed execution across machines.

**Install:**

```bash
pip install cosmic-ray
```

**Configuration (`cosmic-ray.toml`):**

```toml
[cosmic-ray]
module-path = "src/mypackage"
timeout = 30.0
test-command = "python -m pytest tests/ -x --tb=short -q"
excluded-modules = [
    "src/mypackage/generated/*",
    "src/mypackage/migrations/*",
]

[cosmic-ray.distributor]
name = "local"
```

**Run:**

```bash
# Initialize the mutation database
cosmic-ray init cosmic-ray.toml session.sqlite

# Execute mutations
cosmic-ray exec cosmic-ray.toml session.sqlite

# View results
cosmic-ray dump session.sqlite | cr-report

# HTML report
cr-html session.sqlite > report.html
```

cosmic-ray is better for large Python codebases where distributed execution matters. For most projects, mutmut is simpler and sufficient.

### Go -- gremlins

[gremlins](https://github.com/go-gremlins/gremlins) is the actively maintained mutation testing tool for Go.

**Install:**

```bash
go install github.com/go-gremlins/gremlins/cmd/gremlins@latest
```

**Run:**

```bash
gremlins unleash ./...
```

**Configuration (`gremlins.toml`):**

```toml
[unleash]
tags = ""
timeout = 10

[unleash.threshold]
efficacy = 70.0

[unleash.mutants]
arithmetic_base = true
conditionals_boundary = true
conditionals_negation = true
increment_decrement = true
invert_negatives = true
invert_logical = true
invert_loopctrl = true
invert_bitwise = true
invert_bwassign = true
remove_self_assignments = true
```

### Go -- go-mutesting

[go-mutesting](https://github.com/zimmski/go-mutesting) is an older but stable Go mutation tester with fine-grained control over mutation operators.

**Install:**

```bash
go install github.com/zimmski/go-mutesting/cmd/go-mutesting@latest
```

**Run:**

```bash
# Mutate a specific package
go-mutesting ./pkg/pricing/...

# With a custom test command
go-mutesting --exec "go test -count=1 -timeout 30s" ./pkg/pricing/...

# Only show surviving mutants
go-mutesting ./pkg/pricing/... 2>&1 | grep "FAIL"
```

### Go -- ooze

[ooze](https://github.com/gtramontina/ooze) takes a different approach -- it runs mutation testing as a Go test, integrating directly into `go test`. No separate tool required.

**Install:**

```bash
go get github.com/gtramontina/ooze
```

**Usage (in a test file):**

```go
// mutation_test.go
package mypackage_test

import (
    "testing"
    "github.com/gtramontina/ooze"
)

func TestMutation(t *testing.T) {
    ooze.New(
        ooze.WithRepository("."),
        ooze.WithTestCommand("go test -count=1 ./..."),
        ooze.WithMinimumThreshold(0.7),
        ooze.Parallel(),
    ).Test(t)
}
```

**Run:**

```bash
go test -v -run TestMutation -tags=mutation -timeout 30m
```

The advantage is that mutation testing is just another `go test` target. No separate tool, no separate CI step.

### Rust -- cargo-mutants

[cargo-mutants](https://github.com/sourcefrog/cargo-mutants) is mutation testing for Rust. It has first-class support for cargo workspaces and git-diff scoping.

**Install:**

```bash
cargo install cargo-mutants
```

**Run:**

```bash
# Full run
cargo mutants --timeout 30

# Only mutate changed files (the killer feature for CI)
cargo mutants --in-diff $(git diff origin/main...HEAD)

# Run on specific package in a workspace
cargo mutants -p my-crate --timeout 30
```

**Configuration (`mutants.toml`):**

```toml
# Exclude files from mutation
exclude_globs = [
    "src/generated/**",
    "tests/**",
    "benches/**",
]

# Exclude specific functions (e.g., Display impls, trivial getters)
exclude_re = [
    "impl.*Display.*for",
    "fn fmt\\(",
]

# Timeout per mutant
timeout = 60
```

**CI integration:**

```yaml
- name: Mutation testing
  run: |
    cargo install cargo-mutants
    cargo mutants --timeout 60 --in-diff $(git diff origin/main...HEAD)
```

**Output:**

```
Found 142 mutants to test
   ok   src/lib.rs:42  replace add -> sub
 MISSED src/lib.rs:55  replace > with >=
   ok   src/lib.rs:68  replace && with ||
 MISSED src/lib.rs:80  delete call to validate()

142 mutants tested: 128 killed, 12 missed, 2 timeout
Mutation score: 91.5%
```

### Java -- PIT (pitest)

[PIT](https://pitest.org/) is the gold standard for JVM mutation testing. It is the most mature, most widely used mutation testing tool in any language. If your team uses Java or Kotlin, start here.

**Gradle plugin (`build.gradle.kts`):**

```kotlin
plugins {
    id("info.solidsoft.pitest") version "1.15.0"
}

pitest {
    junit5PluginVersion.set("1.2.1")
    targetClasses.set(listOf("com.example.myapp.*"))
    targetTests.set(listOf("com.example.myapp.*Test"))
    mutators.set(listOf("DEFAULTS"))
    outputFormats.set(listOf("HTML", "XML"))
    timestampedReports.set(false)
    threads.set(4)

    // Thresholds
    mutationThreshold.set(60)
    coverageThreshold.set(80)

    // Incremental analysis -- PIT's killer feature for large codebases
    withHistory.set(true)
    historyInputLocation.set(file("build/pitest-history.bin"))
    historyOutputLocation.set(file("build/pitest-history.bin"))
}
```

**Run:**

```bash
./gradlew pitest
```

**Maven plugin (`pom.xml`):**

```xml
<plugin>
    <groupId>org.pitest</groupId>
    <artifactId>pitest-maven</artifactId>
    <version>1.15.3</version>
    <configuration>
        <targetClasses>
            <param>com.example.myapp.*</param>
        </targetClasses>
        <targetTests>
            <param>com.example.myapp.*Test</param>
        </targetTests>
        <mutationThreshold>60</mutationThreshold>
        <threads>4</threads>
        <outputFormats>
            <param>HTML</param>
            <param>XML</param>
        </outputFormats>
        <!-- Incremental analysis -->
        <withHistory>true</withHistory>
        <historyInputFile>target/pitest-history.bin</historyInputFile>
        <historyOutputFile>target/pitest-history.bin</historyOutputFile>
    </configuration>
    <dependencies>
        <dependency>
            <groupId>org.pitest</groupId>
            <artifactId>pitest-junit5-plugin</artifactId>
            <version>1.2.1</version>
        </dependency>
    </dependencies>
</plugin>
```

**Run:**

```bash
mvn org.pitest:pitest-maven:mutationCoverage
```

PIT's advantage is maturity and the `withHistory` incremental mode. For advanced mutation operators and GitHub integration, see [Arcmutate](https://www.arcmutate.com/).

### Ruby -- mutant

[mutant](https://github.com/mbj/mutant) is the mutation testing tool for Ruby. It is the strictest tool on this list -- every surviving mutant is a failure. There is no threshold concept. If a mutant survives, your tests are insufficient.

**Install:**

```ruby
# Gemfile
group :test do
  gem "mutant"
  gem "mutant-rspec"  # For RSpec integration
end
```

```bash
bundle install
```

**Run against a specific class:**

```bash
bundle exec mutant run --use rspec -- 'MyApp::PriceCalculator'
```

**Run against a module:**

```bash
bundle exec mutant run --use rspec -- 'MyApp*'
```

**Configuration (`.mutant.yml`):**

```yaml
integration:
  name: rspec

matcher:
  subjects:
    - "MyApp::PriceCalculator"
    - "MyApp::OrderValidator"
    - "MyApp::DiscountEngine"

  ignore:
    - "MyApp::Config#*"
    - "MyApp::Logger#*"

isolation:
  name: fork

mutation:
  timeout: 10.0

coverage_criteria:
  test_result: true
```

**Output:**

```
MyApp::PriceCalculator
  ::calculate
    evil:MyApp::PriceCalculator::calculate:/app/lib/price_calculator.rb:12:42d4a
    @@ -12,7 +12,7 @@
    -    price * rate
    +    price / rate
    (1/3) FAIL

Kills:           142
Alive:           3
Runtime:         45.23s
Coverage:        97.93%
```

mutant's "alive" mutants are what other tools call "survived." The philosophy is that every alive mutant should be fixed before merging. Stricter than other tools, but produces the highest test quality.

## 10. Anti-Gaming

Coverage can be gamed. Mutation testing is much harder to game -- but not impossible. Understand the vectors and close them.

### Why Coverage Is Gameable

To increase code coverage, you can:

- Call functions without asserting anything
- Write tests that exercise code paths but never check results
- Use `expect(true).toBe(true)` after running code to satisfy assertion density checks
- Add `/* istanbul ignore next */` or `/* v8 ignore next */` comments
- Exclude files from coverage measurement

Every one of these tactics increases the coverage number without improving test quality.

### Why Mutation Testing Is Resistant to Gaming

To kill a mutant, you must write a test that:

1. Executes the mutated line (same as coverage)
2. Produces a different result because of the mutation
3. Asserts that result, causing the test to fail

There is no shortcut. You cannot kill the mutant `a + b -> a - b` without asserting the actual arithmetic result. You cannot kill the mutant `> -> >=` without testing the boundary value. You cannot kill the mutant `true -> false` without testing both branches.

The *only* way to improve a mutation score is to write better tests. This is why mutation testing is the ultimate quality gate -- it measures what actually matters.

### The One Gaming Vector: Stryker Disable Comments

Stryker supports inline disable comments:

```typescript
// Stryker disable next-line all: logging is not behavior
logger.info("Processing order", { orderId });
```

These are the `// eslint-disable` of mutation testing. They are sometimes legitimate (logging statements, debug code, performance counters) but they are easily abused to hide weak tests.

**Every `// Stryker disable` comment should be code-reviewed.** The justification must explain why the mutant is genuinely untestable, not why the developer does not want to write a test.

### Lint Rule to Flag Disable Comments

Create a custom ESLint rule that surfaces every Stryker disable comment in code review:

```javascript
// eslint-plugin-local-rules/no-stryker-disable.js
module.exports = {
  meta: {
    type: "suggestion",
    docs: {
      description: "Flag Stryker disable comments for code review",
    },
    messages: {
      strykerDisable:
        "Stryker disable comment found. " +
        "These must include a justification and be approved in code review.",
    },
    schema: [],
  },
  create(context) {
    const sourceCode = context.sourceCode || context.getSourceCode();
    return {
      Program() {
        const comments = sourceCode.getAllComments();
        for (const comment of comments) {
          if (comment.value.includes("Stryker disable")) {
            context.report({
              node: comment,
              messageId: "strykerDisable",
            });
          }
        }
      },
    };
  },
};
```

**ESLint config:**

```javascript
// eslint.config.mjs
import localRules from "./eslint-plugin-local-rules/index.js";

export default [
  {
    plugins: { "local-rules": localRules },
    rules: {
      "local-rules/no-stryker-disable": "warn",
    },
  },
];
```

This will not block the commit, but it will surface every disable comment in code review. Reviewers should demand a clear justification for each one.

### Coverage-Only Tests: The #1 Gaming Pattern

The most common gaming pattern is tests that achieve coverage without verification:

```typescript
// This test gives full coverage but tests NOTHING
it("runs without error", () => {
  const result = complexCalculation(input);
  expect(result).toBeDefined();
});
```

Mutation testing catches this automatically. Every mutant in `complexCalculation` survives because `toBeDefined()` passes regardless of what the function returns. But you can also detect this pattern statically with assertion density checks.

### Assertion Density as a Complementary Metric

**Assertion density = assertions per test block.** A test with 0-1 assertions per `it()` block is suspicious. A test with 3+ assertions per block is likely verifying real behavior.

Assertion density and mutation score reinforce each other:

| Assertion Density | Mutation Score | Diagnosis |
|---|---|---|
| Low | Low | Tests are hollow shells. Write real assertions. |
| Low | High | Unlikely. If true, assertions are very precise despite being few. |
| High | Low | Assertions exist but are too loose (`toBeDefined`, `toBeGreaterThan(0)`). Tighten them. |
| High | High | Tests are thorough. This is the goal. |

**Script to check assertion density:**

```bash
#!/usr/bin/env bash
# scripts/check-assertion-density.sh
# Flags test files with suspiciously low assertion density.
# Usage: ./scripts/check-assertion-density.sh [min-density]
set -euo pipefail

MIN_DENSITY="${1:-2}"  # Minimum assertions per test block
VIOLATIONS=0

echo "=== Assertion Density Check ==="
echo "Minimum: ${MIN_DENSITY} assertions per test"
echo ""

for file in $(find packages apps -name "*.test.ts" -o -name "*.test.tsx" 2>/dev/null); do
  # Count test blocks (it/test calls)
  TEST_COUNT=$(grep -cE '^\s*(it|test)\(' "$file" 2>/dev/null || echo 0)

  # Count assertions (expect calls)
  ASSERT_COUNT=$(grep -cE '\bexpect\(' "$file" 2>/dev/null || echo 0)

  if [ "$TEST_COUNT" -eq 0 ]; then
    continue
  fi

  DENSITY=$((ASSERT_COUNT / TEST_COUNT))

  if [ "$DENSITY" -lt "$MIN_DENSITY" ]; then
    echo "LOW: $file (${ASSERT_COUNT} assertions / ${TEST_COUNT} tests = ${DENSITY}/test)"
    VIOLATIONS=$((VIOLATIONS + 1))
  fi
done

echo ""
if [ "$VIOLATIONS" -gt 0 ]; then
  echo "WARNING: $VIOLATIONS file(s) with low assertion density."
  echo "These tests may be achieving coverage without verification."
  echo "Run mutation testing to confirm: pnpm mutation-test"
  exit 1
fi

echo "PASS: All test files meet minimum assertion density."
```

### The Relationship Between Coverage and Mutation Score

Coverage is a prerequisite for mutation testing, not a substitute. Code that is not executed cannot be mutated. A line with 0% coverage has 0% mutation score by definition.

The useful mental model:

```
Coverage tells you: "This code ran during tests."
Mutation score tells you: "This code's behavior was verified by tests."
```

A healthy codebase has:
- **90%+ line coverage** (most code is executed during tests)
- **80%+ mutation score** (most executed code is actually verified)

A codebase with 95% coverage and 40% mutation score is a ticking time bomb. Half the "tested" code has never had its behavior checked. Any refactor, any change to logic, any off-by-one error will slip through.

### When to Investigate

| Coverage | Mutation Score | Diagnosis |
|---|---|---|
| Low | Low | Tests are missing entirely. Write more tests. |
| High | Low | Tests execute code but do not verify it. Tighten assertions. |
| High | High | Tests are thorough. Maintain the standard. |
| Low | High | Unusual. The tested code is well-verified, but most code is untested. Expand coverage. |

The second row (high coverage, low mutation score) is the most dangerous because it creates false confidence. Coverage dashboards look green. PRs get merged. Bugs ship. Mutation testing is the only tool that catches this state.
