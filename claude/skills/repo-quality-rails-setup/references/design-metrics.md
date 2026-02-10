# Design-Level Quality Metrics

Mechanical gates catch syntax. Design metrics catch structure. A codebase can pass every lint rule, every type check, every test, and every formatting gate while still being a tangled mess of god functions, circular dependencies, and leaky abstractions. Formatting tells you the code looks right. Design metrics tell you the code is shaped right.

This reference covers the missing layer between mechanical correctness and architectural quality: deterministic, enforceable metrics that measure the structural properties of code. Every metric here has a specific tool, an exact threshold, and a concrete enforcement mechanism. Nothing is aspirational. Everything is a gate.

## Table of Contents

1. [Cognitive Complexity](#1-cognitive-complexity)
2. [Function and File Size Limits](#2-function-and-file-size-limits)
3. [Coupling Metrics (Fan-In / Fan-Out)](#3-coupling-metrics-fan-in--fan-out)
4. [Export Surface Area](#4-export-surface-area)
5. [Dependency Depth](#5-dependency-depth)
6. [Circular Dependency Detection](#6-circular-dependency-detection)
7. [God File / God Function Detection](#7-god-file--god-function-detection)
8. [Ratcheting Strategy for Existing Codebases](#8-ratcheting-strategy-for-existing-codebases)
9. [Pre-push and CI Integration](#9-pre-push-and-ci-integration)
10. [Per-Language Equivalents](#10-per-language-equivalents)

---

## 1. Cognitive Complexity

### What it measures

Cognitive complexity measures how hard a function is for a human to understand. It was designed by SonarSource as a direct replacement for cyclomatic complexity, which counts execution paths but does not account for how humans actually read code.

**Cyclomatic complexity** counts decision points: each `if`, `else`, `for`, `while`, `case`, `&&`, `||` adds 1. A function with 10 sequential `if` statements and a function with 10 nested `if` statements get the same score. But the nested version is dramatically harder to understand.

**Cognitive complexity** fixes this by adding a nesting penalty. Each level of nesting multiplies the cost of a control structure. A nested `if` inside a `for` inside a `try` costs more than three sequential `if` statements, because the reader must maintain more context in working memory.

The rules:
1. **+1** for each control flow break: `if`, `else if`, `else`, `for`, `while`, `do while`, `switch`, `catch`, ternary `?`, `&&`, `||`, `??`
2. **+1 nesting penalty** for each level of nesting when a break is nested inside another break
3. **+0** for structures that aid readability: early returns, guard clauses

### ESLint `sonarjs/cognitive-complexity` Plugin Setup (Flat Config)

```bash
pnpm add -D eslint-plugin-sonarjs
```

```js
// eslint.config.mjs
import sonarjs from "eslint-plugin-sonarjs";

export default [
  {
    files: ["**/*.ts", "**/*.tsx"],
    plugins: {
      sonarjs,
    },
    rules: {
      // Warn at 15: function is getting hard to follow
      // Error at 25: function must be decomposed before merge
      "sonarjs/cognitive-complexity": ["warn", 15],
    },
  },
  // Stricter for library packages -- these are shared code with many consumers
  {
    files: ["packages/**/src/**/*.ts"],
    ignores: ["**/*.test.ts", "**/__tests__/**"],
    rules: {
      "sonarjs/cognitive-complexity": ["error", 25],
    },
  },
];
```

### Recommended Thresholds

| Level | Threshold | Meaning |
|-------|-----------|---------|
| Green | 0-10 | Function is straightforward. No action needed. |
| Warn | 11-15 | Consider decomposing. Acceptable for complex business logic with a comment explaining why. |
| Error | 16-25 | Must refactor. Extract helper functions, flatten nesting, use lookup tables. |
| Critical | 25+ | Hard block. This function is unmaintainable. No exceptions. |

### Per-File Override Strategy for Legacy Code

Do not suppress the rule globally to accommodate legacy code. Override per-file with a documented tech debt ticket:

```js
// eslint.config.mjs
export default [
  // ... base config above ...

  // Legacy overrides -- each MUST reference a tech debt ticket
  {
    files: [
      "apps/legacy-api/src/routes/giant-handler.ts", // TECH-234: decompose route handler
      "packages/old-parser/src/parse.ts",             // TECH-301: rewrite parser
    ],
    rules: {
      "sonarjs/cognitive-complexity": ["warn", 40],
    },
  },
];
```

The override raises the threshold but keeps the warning visible. The ticket number creates accountability. During sprint planning, these tickets surface naturally.

### Refactoring Guide

#### Extract early returns

```typescript
// Before: cognitive complexity 8
function processOrder(order: Order): Result {
  if (order.status === "active") {                    // +1
    if (order.items.length > 0) {                     // +1 (nesting: +1)
      if (order.payment.verified) {                   // +1 (nesting: +2)
        return fulfillOrder(order);
      } else {                                        // +1
        return { error: "Payment not verified" };
      }
    } else {                                          // +1
      return { error: "No items" };
    }
  } else {                                            // +1
    return { error: "Order not active" };
  }
}

// After: cognitive complexity 3
function processOrder(order: Order): Result {
  if (order.status !== "active") {                    // +1
    return { error: "Order not active" };
  }
  if (order.items.length === 0) {                     // +1
    return { error: "No items" };
  }
  if (!order.payment.verified) {                      // +1
    return { error: "Payment not verified" };
  }
  return fulfillOrder(order);
}
```

#### Replace switch with lookup objects

```typescript
// Before: cognitive complexity 6 (switch + 5 cases)
function getHandler(type: string): Handler {
  switch (type) {                                     // +1
    case "create": return handleCreate;
    case "update": return handleUpdate;
    case "delete": return handleDelete;
    case "archive": return handleArchive;
    case "restore": return handleRestore;
    default: throw new Error(`Unknown: ${type}`);
  }
}

// After: cognitive complexity 1
const handlers: Record<string, Handler> = {
  create: handleCreate,
  update: handleUpdate,
  delete: handleDelete,
  archive: handleArchive,
  restore: handleRestore,
};

function getHandler(type: string): Handler {
  const handler = handlers[type];
  if (!handler) {                                     // +1
    throw new Error(`Unknown: ${type}`);
  }
  return handler;
}
```

#### Decompose nested conditions

```typescript
// Before: cognitive complexity 12
function getShippingCost(country: string, weight: number, express: boolean): number {
  if (country === "US") {                             // +1
    if (weight < 1) {                                 // +1 (nesting: +1)
      return express ? 15 : 5;                        // +1 (nesting: +2)
    } else if (weight < 5) {                          // +1 (nesting: +1)
      return express ? 25 : 10;                       // +1 (nesting: +2)
    } else {                                          // +1
      return express ? 45 : 20;                       // +1 (nesting: +2)
    }
  }
  // ... more nested branches for other countries
}

// After: cognitive complexity 2
const SHIPPING_RATES: Record<string, { maxWeight: number; standard: number; express: number }[]> = {
  US: [
    { maxWeight: 1, standard: 5, express: 15 },
    { maxWeight: 5, standard: 10, express: 25 },
    { maxWeight: Infinity, standard: 20, express: 45 },
  ],
  CA: [
    { maxWeight: 1, standard: 8, express: 20 },
    { maxWeight: 5, standard: 15, express: 30 },
    { maxWeight: Infinity, standard: 25, express: 50 },
  ],
};

function getShippingCost(country: string, weight: number, express: boolean): number {
  const rates = SHIPPING_RATES[country] ?? SHIPPING_RATES["US"]!;
  const tier = rates.find((r) => weight < r.maxWeight);
  if (!tier) throw new Error(`No rate for weight ${weight}`);   // +1
  return express ? tier.express : tier.standard;                 // +1
}
```

---

## 2. Function and File Size Limits

Size limits are the bluntest design metric. They work not because short functions are inherently better, but because long functions and large files are reliable indicators that something has gone wrong structurally. A 200-line function is doing too many things. A 600-line file is mixing too many responsibilities.

### ESLint Configuration (Flat Config)

All four rules in one config block:

```js
// eslint.config.mjs
export default [
  {
    files: ["**/*.ts", "**/*.tsx"],
    rules: {
      // === FUNCTION SIZE ===
      // 50 lines: warn. You should consider splitting.
      // skipBlankLines + skipComments: measure actual logic, not formatting.
      "max-lines-per-function": [
        "warn",
        {
          max: 50,
          skipBlankLines: true,
          skipComments: true,
          IIFEs: true,
        },
      ],

      // === FILE SIZE ===
      // 300 lines: warn. File is getting large, look for split opportunities.
      "max-lines": [
        "warn",
        {
          max: 300,
          skipBlankLines: true,
          skipComments: true,
        },
      ],

      // === NESTING DEPTH ===
      // 4 levels of nesting is the hard limit.
      // If you are inside if > if > for > if, the function is too complex.
      "max-depth": ["error", 4],

      // === PARAMETER COUNT ===
      // More than 4 params = use an options object.
      // Positional parameters beyond 3 are error-prone.
      "max-params": ["error", 4],
    },
  },

  // Error at higher thresholds for library packages
  {
    files: ["packages/**/src/**/*.ts"],
    ignores: ["**/*.test.ts", "**/__tests__/**"],
    rules: {
      "max-lines-per-function": [
        "error",
        {
          max: 80,
          skipBlankLines: true,
          skipComments: true,
          IIFEs: true,
        },
      ],
      "max-lines": [
        "error",
        {
          max: 500,
          skipBlankLines: true,
          skipComments: true,
        },
      ],
    },
  },

  // Test files get relaxed function length (setup/teardown can be verbose)
  {
    files: ["**/*.test.ts", "**/*.test.tsx", "**/*.spec.ts", "**/__tests__/**"],
    rules: {
      "max-lines-per-function": [
        "warn",
        {
          max: 100,
          skipBlankLines: true,
          skipComments: true,
          IIFEs: true,
        },
      ],
      "max-lines": "off",
      "max-params": "off",
    },
  },
];
```

### Threshold Summary

| Rule | Warn | Error | Why |
|------|------|-------|-----|
| `max-lines-per-function` | 50 | 80 | Functions above 50 lines have 2x defect density. Above 80, they become untestable in isolation. |
| `max-lines` (file) | 300 | 500 | Files above 300 lines typically have more than one responsibility. Above 500, navigation becomes the bottleneck. |
| `max-depth` | -- | 4 | Each nesting level doubles the mental stack a reader must maintain. Four levels is the upper bound of working memory. |
| `max-params` | -- | 4 | Positional parameters beyond 4 are misremembered. Callers start guessing which argument goes where. |

### The `max-params` Destructuring Refactor Pattern

When a function exceeds 4 parameters, the fix is always the same -- destructured options object:

```typescript
// Before: 7 positional params, callers constantly get the order wrong
function createUser(
  name: string,
  email: string,
  role: Role,
  department: string,
  managerId: string,
  startDate: Date,
  salary: number
): User {
  // ...
}

// Caller: which argument is the managerId? Is salary before or after startDate?
createUser("Alice", "a@b.com", "eng", "platform", "mgr-42", new Date(), 120000);

// After: options object, self-documenting at call sites
interface CreateUserOptions {
  name: string;
  email: string;
  role: Role;
  department: string;
  managerId: string;
  startDate: Date;
  salary: number;
}

function createUser(options: CreateUserOptions): User {
  const { name, email, role, department, managerId, startDate, salary } = options;
  // ...
}

// Caller: every argument is labeled
createUser({
  name: "Alice",
  email: "a@b.com",
  role: "eng",
  department: "platform",
  managerId: "mgr-42",
  startDate: new Date(),
  salary: 120000,
});
```

The options object is a single parameter. It is self-documenting (named fields), order-independent, and extensible without breaking existing call sites.

---

## 3. Coupling Metrics (Fan-In / Fan-Out)

### What Fan-In and Fan-Out Measure

**Fan-out (efferent coupling):** How many other modules this module imports from. High fan-out means the module is fragile -- any change in any dependency can break it. A module with fan-out of 12 is a coordinator or god module that knows about too many things.

**Fan-in (afferent coupling):** How many other modules import this module. High fan-in means the module is risky to change -- any modification affects many consumers. A module with fan-in of 20 is a core dependency that needs careful API design.

Neither metric is bad in isolation. The dangerous combination is **high fan-in AND high instability**.

### The Instability Metric

Robert C. Martin's instability metric:

```
I = fan-out / (fan-in + fan-out)
```

- `I = 0` -- maximally stable (everything depends on it, it depends on nothing). Example: a core types package.
- `I = 1` -- maximally unstable (depends on everything, nothing depends on it). Example: an app entry point.

**The Stable Dependencies Principle**: a module should only depend on modules that are more stable than itself. When a stable module (low I) depends on an unstable module (high I), every change to the unstable module ripples into the stable core. High instability + high incoming deps = fragile module. This is the single most dangerous structural pattern in a codebase.

### dependency-cruiser Setup

```bash
pnpm add -D dependency-cruiser
```

### .dependency-cruiser.cjs

```js
/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    // ─────────────────────────────────────────────────────
    // Fan-out limit: max 10 direct dependencies per module
    // ─────────────────────────────────────────────────────
    {
      name: "max-fan-out",
      severity: "error",
      comment:
        "A module with more than 10 direct dependencies is doing too much. " +
        "Split it into focused modules with fewer responsibilities.",
      from: {
        pathNot: [
          "(^|/)node_modules/",
          "(^|/)index\\.(ts|js)$",       // Barrel files legitimately re-export many modules
          "(^|/)__tests__/",
          "\\.(test|spec)\\.(ts|js)$",
        ],
      },
      to: {},
      module: {
        numberOfDependentsLessThan: 999,
        numberOfDependenciesMoreThan: 10,
      },
    },

    // ─────────────────────────────────────────────────────
    // Circular dependencies at any level
    // ─────────────────────────────────────────────────────
    {
      name: "no-circular",
      severity: "error",
      comment: "Circular dependencies make modules impossible to understand in isolation.",
      from: {},
      to: {
        circular: true,
      },
    },

    // ─────────────────────────────────────────────────────
    // Orphan detection
    // ─────────────────────────────────────────────────────
    {
      name: "no-orphans",
      severity: "warn",
      comment: "Orphan modules are not imported by anything. Dead code candidates.",
      from: {
        orphan: true,
        pathNot: [
          "(^|/)node_modules/",
          "\\.d\\.ts$",
          "(^|/)index\\.(ts|js)$",
          "(^|/)main\\.(ts|js)$",
          "(^|/)app\\.(ts|js)$",
          "(^|/)server\\.(ts|js)$",
          "\\.config\\.(ts|js|mjs|cjs)$",
          "(^|/)__tests__/",
          "\\.(test|spec)\\.(ts|js)$",
        ],
      },
      to: {},
    },

    // ─────────────────────────────────────────────────────
    // Prevent apps from importing other apps
    // ─────────────────────────────────────────────────────
    {
      name: "no-app-to-app",
      severity: "error",
      comment: "Apps must not import from other apps. Shared code belongs in packages/.",
      from: { path: "^apps/[^/]+/" },
      to: { path: "^apps/[^/]+/", pathNot: "$1" },
    },

    // ─────────────────────────────────────────────────────
    // Prevent packages from importing apps
    // ─────────────────────────────────────────────────────
    {
      name: "no-package-to-app",
      severity: "error",
      comment: "Packages must not depend on apps. Dependency flows downward: apps -> packages.",
      from: { path: "^packages/" },
      to: { path: "^apps/" },
    },
  ],

  options: {
    doNotFollow: { path: "node_modules" },
    tsPreCompilationDeps: true,
    tsConfig: { fileName: "tsconfig.json" },
    enhancedResolveOptions: {
      exportsFields: ["exports"],
      conditionNames: ["import", "require", "node", "default"],
    },
    reporterOptions: {
      dot: {
        theme: {
          graph: { rankdir: "LR", splines: "ortho" },
          node: { shape: "box", style: "rounded,filled", fillcolor: "#ffffff" },
          dependencies: [
            { criteria: { circular: true }, attributes: { color: "#ff0000", penwidth: "2.0" } },
          ],
        },
      },
    },
  },
};
```

### Script to Run dependency-cruiser and Fail on Threshold

```bash
#!/usr/bin/env bash
# scripts/check-fan-out.sh
# Reports modules with fan-out exceeding the threshold and exits non-zero if any are found.

set -euo pipefail

THRESHOLD=${1:-10}

echo "=== Fan-Out Analysis (threshold: $THRESHOLD) ==="
echo ""

npx depcruise \
  --config .dependency-cruiser.cjs \
  --output-type json \
  packages/*/src apps/*/src 2>/dev/null \
  | node -e "
    const data = require('fs').readFileSync('/dev/stdin', 'utf8');
    const result = JSON.parse(data);
    const modules = result.modules || [];

    // Build fan-in map for instability calculation
    const fanInMap = new Map();
    for (const m of modules) {
      for (const dep of (m.dependencies || [])) {
        fanInMap.set(dep.resolved, (fanInMap.get(dep.resolved) || 0) + 1);
      }
    }

    const violations = modules
      .filter(m => !m.source.includes('node_modules'))
      .filter(m => !m.source.match(/index\.(ts|js)$/))
      .filter(m => !m.source.match(/\.(test|spec)\./))
      .map(m => {
        const fanOut = (m.dependencies || []).filter(d => !d.resolved.includes('node_modules')).length;
        const fanIn = fanInMap.get(m.source) || 0;
        const total = fanIn + fanOut;
        const instability = total === 0 ? 0 : fanOut / total;
        return { source: m.source, fanOut, fanIn, instability };
      })
      .filter(m => m.fanOut > ${THRESHOLD})
      .sort((a, b) => b.fanOut - a.fanOut);

    if (violations.length === 0) {
      console.log('All modules within fan-out threshold.');
      process.exit(0);
    }

    console.log('Modules exceeding fan-out threshold:');
    console.log('');
    console.log('  Fan-Out  Fan-In  Instability  Module');
    console.log('  -------  ------  -----------  ------');
    violations.forEach(m => {
      console.log(
        '  ' + String(m.fanOut).padStart(7) +
        '  ' + String(m.fanIn).padStart(6) +
        '  ' + m.instability.toFixed(2).padStart(11) +
        '  ' + m.source
      );
    });
    console.log('');
    console.log(violations.length + ' module(s) exceed fan-out of ${THRESHOLD}.');

    // Flag fragile modules: high fan-in (>5) AND high instability (>0.6)
    const fragile = violations.filter(m => m.fanIn > 5 && m.instability > 0.6);
    if (fragile.length > 0) {
      console.log('');
      console.log('FRAGILE MODULES (high fan-in + high instability):');
      fragile.forEach(m => {
        console.log('  ' + m.source + ' (I=' + m.instability.toFixed(2) + ', ' + m.fanIn + ' dependents)');
      });
      console.log('These modules are widely depended on but highly coupled. Stabilize them.');
    }

    process.exit(1);
  "
```

### Pre-push Hook Integration

Add to `.husky/pre-push` after lint and type-check gates:

```bash
# === CHECK: Fan-out analysis ===
echo "--- Fan-out analysis ---"
bash scripts/check-fan-out.sh 10
```

---

## 4. Export Surface Area

### Why Large Export Surfaces Indicate Poor Encapsulation

Every export is a contract. The more exports a package has, the larger its public API surface, the more things can break when you change internals, and the harder it is for consumers to discover the right function to use.

A package with 80 exports is not a package -- it is a bag of functions. Consumers end up importing internal helpers that were never intended to be public, creating invisible coupling.

The worst pattern is the re-export-everything barrel:

```typescript
// BAD: packages/utils/src/index.ts
export * from "./strings";
export * from "./arrays";
export * from "./dates";
export * from "./numbers";
export * from "./validation";
// Exports 150+ symbols. Nobody knows which are public API vs implementation detail.
```

### Custom Script Using TypeScript Compiler API to Count Exports

```typescript
// scripts/count-exports.ts
import * as ts from "typescript";
import * as path from "path";
import * as fs from "fs";
import { glob } from "glob";

const WARN_THRESHOLD = 30;
const ERROR_THRESHOLD = 50;

interface PackageExportInfo {
  packageName: string;
  entryPoint: string;
  exportCount: number;
  exports: string[];
}

function countExports(entryPoint: string): { count: number; names: string[] } {
  const configPath = ts.findConfigFile(
    path.dirname(entryPoint),
    ts.sys.fileExists,
    "tsconfig.json"
  );
  const configFile = configPath ? ts.readConfigFile(configPath, ts.sys.readFile) : { config: {} };
  const parsedConfig = ts.parseJsonConfigFileContent(
    configFile.config,
    ts.sys,
    path.dirname(configPath || entryPoint)
  );

  const program = ts.createProgram([entryPoint], { ...parsedConfig.options, noEmit: true });
  const checker = program.getTypeChecker();
  const sourceFile = program.getSourceFile(entryPoint);
  if (!sourceFile) return { count: 0, names: [] };

  const symbol = checker.getSymbolAtLocation(sourceFile);
  if (!symbol) return { count: 0, names: [] };

  const exports = checker.getExportsOfModule(symbol);
  const names = exports.map((e) => e.getName()).sort();
  return { count: names.length, names };
}

async function main(): Promise<void> {
  const packageJsonPaths = await glob("packages/*/package.json");
  const results: PackageExportInfo[] = [];
  let hasErrors = false;
  let hasWarnings = false;

  for (const pkgJsonPath of packageJsonPaths) {
    const pkgJson = JSON.parse(fs.readFileSync(pkgJsonPath, "utf8"));
    const pkgDir = path.dirname(pkgJsonPath);
    const name = pkgJson.name || path.basename(pkgDir);

    // Find entry point
    let entryPoint: string | null = null;
    if (pkgJson.exports?.["."]?.development?.default) {
      entryPoint = path.resolve(pkgDir, pkgJson.exports["."].development.default);
    } else if (pkgJson.exports?.["."]) {
      const exp = pkgJson.exports["."];
      const resolved = typeof exp === "string" ? exp : exp.default || exp.import || exp.require;
      if (resolved) entryPoint = path.resolve(pkgDir, resolved);
    } else if (pkgJson.main) {
      entryPoint = path.resolve(pkgDir, pkgJson.main);
    }

    if (!entryPoint || !fs.existsSync(entryPoint)) {
      const fallback = path.resolve(pkgDir, "src/index.ts");
      if (fs.existsSync(fallback)) entryPoint = fallback;
    }
    if (!entryPoint || !fs.existsSync(entryPoint)) continue;

    const { count, names } = countExports(entryPoint);
    results.push({ packageName: name, entryPoint, exportCount: count, exports: names });
  }

  results.sort((a, b) => b.exportCount - a.exportCount);

  console.log("=== Export Surface Area ===\n");
  console.log("  Count  Status  Package");
  console.log("  -----  ------  -------");

  for (const r of results) {
    let status: string;
    if (r.exportCount > ERROR_THRESHOLD) {
      status = "ERROR";
      hasErrors = true;
    } else if (r.exportCount > WARN_THRESHOLD) {
      status = "WARN ";
      hasWarnings = true;
    } else {
      status = "OK   ";
    }
    console.log(`  ${String(r.exportCount).padStart(5)}  ${status}  ${r.packageName}`);
  }

  if (hasErrors) {
    console.log("\nPackages exceeding ERROR threshold (" + ERROR_THRESHOLD + " exports):");
    for (const r of results.filter((r) => r.exportCount > ERROR_THRESHOLD)) {
      console.log(`\n  ${r.packageName} (${r.exportCount} exports):`);
      r.exports.forEach((name) => console.log(`    - ${name}`));
    }
    console.log("\nFix: split large packages into focused sub-packages, or use");
    console.log("explicit named exports instead of 'export * from' barrels.");
    process.exit(1);
  }

  if (hasWarnings) {
    console.log("\nPackages approaching export threshold. Consider splitting.");
  } else {
    console.log("\nAll packages within export thresholds.");
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
```

### Barrel File Analysis: Detect Re-Export-Everything Patterns

```bash
#!/usr/bin/env bash
# scripts/detect-star-reexports.sh
# Flags index.ts files that use "export * from" -- these inflate export surfaces
# and make it impossible to control what is public API.

set -euo pipefail

echo "=== Barrel Re-Export Detection ==="
echo ""

VIOLATIONS=0

while IFS= read -r file; do
  STAR_EXPORTS=$(grep -c "export \* from" "$file" 2>/dev/null || true)
  if [ "$STAR_EXPORTS" -gt 3 ]; then
    echo "  $file: $STAR_EXPORTS star re-exports"
    VIOLATIONS=$((VIOLATIONS + 1))
  fi
done < <(find packages/*/src apps/*/src -name "index.ts" -type f 2>/dev/null)

if [ "$VIOLATIONS" -gt 0 ]; then
  echo ""
  echo "$VIOLATIONS barrel files with excessive star re-exports."
  echo "Fix: replace 'export * from' with explicit named exports."
  echo "This makes the public API intentional rather than accidental."
  exit 1
fi

echo "No excessive star re-exports found."
```

### Integration with Pre-push Hooks

```bash
# In .husky/pre-push, after type-check
echo "--- Export surface area ---"
npx tsx scripts/count-exports.ts

echo "--- Barrel re-export detection ---"
bash scripts/detect-star-reexports.sh
```

---

## 5. Dependency Depth

### What It Measures

Dependency depth is the longest path from a module to a leaf node (a module with no outgoing dependencies) in the dependency graph. Deep chains mean that a change in a leaf module must propagate through many layers before reaching its consumers.

A well-layered codebase has dependency chains of 3-5 levels: entry point -> service -> domain -> utility.

### How Deep Dependency Chains Indicate Poor Layering

- **Compilation cascades** -- changing a leaf module forces recompilation of every module in the chain.
- **Rebuild amplification** -- in Turbo/Nx, cache invalidation cost is proportional to depth. A change at depth 12 invalidates 12 layers of cached output.
- **Difficult debugging** -- a bug 8 layers deep requires tracing through 8 modules to understand the call path.
- **Test setup complexity** -- testing a module deep in the chain requires mocking or instantiating every dependency in between.

### dependency-cruiser `--max-depth` Configuration

```bash
# Run dependency-cruiser with max traversal depth
npx depcruise \
  --config .dependency-cruiser.cjs \
  --max-depth 12 \
  --output-type json \
  packages/*/src apps/*/src
```

### Analysis Script

```bash
#!/usr/bin/env bash
# scripts/check-dependency-depth.sh
# Reports the maximum dependency depth in the project.

set -euo pipefail

WARN_THRESHOLD=${1:-8}
ERROR_THRESHOLD=${2:-12}

echo "=== Dependency Depth Analysis (warn: $WARN_THRESHOLD, error: $ERROR_THRESHOLD) ==="
echo ""

npx depcruise \
  --config .dependency-cruiser.cjs \
  --max-depth "$ERROR_THRESHOLD" \
  --output-type json \
  packages/*/src apps/*/src 2>/dev/null \
  | node -e "
    const data = require('fs').readFileSync('/dev/stdin', 'utf8');
    const result = JSON.parse(data);
    const modules = result.modules || [];

    // Build adjacency list
    const adj = new Map();
    for (const m of modules) {
      adj.set(m.source, (m.dependencies || []).map(d => d.resolved));
    }

    // Compute max depth from each module using DFS with memoization
    const depthCache = new Map();
    function maxDepth(mod, visited) {
      if (depthCache.has(mod)) return depthCache.get(mod);
      if (visited.has(mod)) return 0;
      visited.add(mod);

      const deps = adj.get(mod) || [];
      if (deps.length === 0) { depthCache.set(mod, 0); return 0; }

      let max = 0;
      for (const dep of deps) {
        max = Math.max(max, 1 + maxDepth(dep, new Set(visited)));
      }
      depthCache.set(mod, max);
      return max;
    }

    const depths = modules
      .map(m => ({ source: m.source, depth: maxDepth(m.source, new Set()) }))
      .sort((a, b) => b.depth - a.depth);

    const maxD = depths[0]?.depth || 0;
    const level = maxD > ${ERROR_THRESHOLD} ? 'ERROR' : maxD > ${WARN_THRESHOLD} ? 'WARN' : 'OK';

    console.log('Maximum dependency depth: ' + maxD + ' (' + level + ')');
    console.log('');

    if (maxD > ${WARN_THRESHOLD}) {
      console.log('Deepest dependency chains:');
      console.log('');
      depths.filter(d => d.depth > ${WARN_THRESHOLD}).slice(0, 10).forEach(d => {
        console.log('  depth ' + d.depth + ': ' + d.source);
      });
      console.log('');
    }

    if (maxD > ${ERROR_THRESHOLD}) {
      console.log('Dependency depth exceeds error threshold of ${ERROR_THRESHOLD}.');
      console.log('Fix: flatten dependency chains by reducing intermediary modules.');
      process.exit(1);
    }
  "
```

### Visualization

```bash
# Full graph (install graphviz first: brew install graphviz)
npx depcruise \
  --config .dependency-cruiser.cjs \
  --output-type dot \
  packages/*/src \
  | dot -Tsvg > dependency-graph.svg

# Focused on a single package
npx depcruise \
  --config .dependency-cruiser.cjs \
  --output-type dot \
  --focus "packages/core-domain/src" \
  packages/*/src \
  | dot -Tsvg > core-domain-deps.svg

# Only show problematic paths (depth > 6)
npx depcruise \
  --config .dependency-cruiser.cjs \
  --output-type dot \
  --max-depth 6 \
  --collapse "node_modules/([^/]+)" \
  packages/*/src apps/*/src \
  | dot -Tsvg > deep-paths.svg
```

---

## 6. Circular Dependency Detection

### Why Circular Dependencies Are Dangerous

Circular dependencies create three concrete problems:

1. **Tree-shaking fails.** Bundlers cannot determine which exports are unused when modules reference each other cyclically. The entire cycle must be included.

2. **Testing becomes fragile.** To test module A, you must load module B, which loads module A again. Mock boundaries become unclear. Test isolation breaks.

3. **Entangled abstractions.** If A depends on B and B depends on A, they are not two modules -- they are one module split across two files. The abstraction boundary is a lie.

### Approach 1: dependency-cruiser (Full Analysis)

The `.dependency-cruiser.cjs` config from section 3 already includes the `no-circular` rule. Run it:

```bash
npx depcruise --config .dependency-cruiser.cjs --output-type err packages/*/src apps/*/src
```

This reports all circular dependencies with the full cycle path.

### Approach 2: madge (Quick Visual Check)

madge is lighter-weight and gives a fast circular dependency report:

```bash
pnpm add -D madge
```

```bash
# List circular dependencies (exits non-zero if any found)
npx madge --circular --extensions ts packages/*/src apps/*/src

# Generate dependency graph image
npx madge --image dependency-graph.png --extensions ts packages/core-domain/src

# JSON output for scripting
npx madge --circular --extensions ts --json packages/*/src
```

### Approach 3: ESLint import/no-cycle (Lint-Time Detection)

For catching circulars at lint time (faster feedback than a full dependency-cruiser run):

```bash
pnpm add -D eslint-plugin-import-x
```

```js
// eslint.config.mjs
import importPlugin from "eslint-plugin-import-x";

export default [
  {
    files: ["**/*.ts", "**/*.tsx"],
    plugins: {
      "import-x": importPlugin,
    },
    rules: {
      // Detect circular dependencies at lint time.
      // maxDepth 5 limits how far the algorithm searches (higher = slower).
      // ignoreExternal skips node_modules (much faster).
      "import-x/no-cycle": [
        "error",
        {
          maxDepth: 5,
          ignoreExternal: true,
        },
      ],
    },
    settings: {
      "import-x/resolver": {
        typescript: { alwaysTryTypes: true },
      },
    },
  },
];
```

**Performance note:** `import/no-cycle` can be slow on large codebases because it traces the full import graph for every file. Set `maxDepth: 5` to limit the search. For large monorepos, run this only in pre-push or CI, not in the editor.

### Pre-commit Hook: Fast Circular Dependency Check

```bash
# In .husky/pre-commit or lint-staged config
# Only checks directories containing changed files, not the whole codebase

CHANGED_TS=$(git diff --cached --name-only --diff-filter=ACMR | grep '\.tsx\?$' || true)
if [ -n "$CHANGED_TS" ]; then
  echo "--- Circular dependency check (changed files) ---"
  DIRS=$(echo "$CHANGED_TS" | xargs -I{} dirname {} | sort -u | head -20)
  for dir in $DIRS; do
    if npx madge --circular --extensions ts "$dir" 2>/dev/null | grep -q "Circular"; then
      echo "Circular dependency detected in $dir"
      npx madge --circular --extensions ts "$dir"
      exit 1
    fi
  done
fi
```

### When You Find a Circular Dependency

Circular dependencies are always fixable. The question is which direction the dependency should flow:

1. **Extract the shared type.** If A imports a type from B and B imports a type from A, extract both types into a shared module C that both A and B depend on.
2. **Dependency inversion.** If A depends on B's implementation and B depends on A's implementation, introduce an interface. A defines the interface, B implements it.
3. **Event-based decoupling.** If A calls B and B calls A, replace one direction with an event emitter. The dependency becomes A -> EventEmitter <- B, with no cycle.
4. **Merge the modules.** If they cannot exist without each other, they are one module pretending to be two. Merge them.

---

## 7. God File / God Function Detection

### Combining Metrics to Detect Design Hotspots

A god file is not just a large file. It is a file that is simultaneously:

- **Large** (> 500 lines) -- it contains a lot of logic
- **Highly coupled** (fan-out > 10) -- it knows about many other modules
- **Broadly exported** (exports > 20) -- many other modules depend on it

Any one of these alone is manageable. All three together create a module that is impossible to change without ripple effects, impossible to test in isolation, and impossible to understand without reading the entire file.

### God File Detection Script

This script cross-references multiple metrics to flag design hotspots:

```bash
#!/usr/bin/env bash
# scripts/detect-god-files.sh
# Cross-references size, fan-out, and export count to flag design hotspots.
# A god file meets ALL THREE criteria simultaneously.

set -euo pipefail

LINE_THRESHOLD=${1:-500}
FANOUT_THRESHOLD=${2:-10}
EXPORT_THRESHOLD=${3:-20}

echo "=== God File Detection ==="
echo "  Criteria: lines > $LINE_THRESHOLD AND fan-out > $FANOUT_THRESHOLD AND exports > $EXPORT_THRESHOLD"
echo ""

# Get fan-out per module from dependency-cruiser
FANOUT_JSON=$(npx depcruise \
  --config .dependency-cruiser.cjs \
  --output-type json \
  packages/*/src apps/*/src 2>/dev/null)

echo "$FANOUT_JSON" | node -e "
  const fs = require('fs');
  const data = fs.readFileSync('/dev/stdin', 'utf8');
  const result = JSON.parse(data);
  const modules = result.modules || [];

  const godFiles = [];

  for (const m of modules) {
    const source = m.source;

    // Skip non-TS files, test files, node_modules
    if (!source.endsWith('.ts') && !source.endsWith('.tsx')) continue;
    if (source.includes('.test.') || source.includes('__tests__')) continue;
    if (source.includes('node_modules')) continue;

    // Fan-out (non-node_modules dependencies only)
    const fanOut = (m.dependencies || []).filter(d => !d.resolved.includes('node_modules')).length;
    if (fanOut <= ${FANOUT_THRESHOLD}) continue;

    // Line count
    let lines = 0;
    try {
      const content = fs.readFileSync(source, 'utf8');
      lines = content.split('\n').length;
    } catch { continue; }
    if (lines <= ${LINE_THRESHOLD}) continue;

    // Export count (heuristic: count export statements)
    let exportCount = 0;
    try {
      const content = fs.readFileSync(source, 'utf8');
      const exportMatches = content.match(/^export\s/gm) || [];
      exportCount = exportMatches.length;
    } catch { continue; }
    if (exportCount <= ${EXPORT_THRESHOLD}) continue;

    godFiles.push({ source, lines, fanOut, exportCount });
  }

  if (godFiles.length === 0) {
    console.log('No god files detected.');
    process.exit(0);
  }

  godFiles.sort((a, b) => b.lines - a.lines);

  console.log('GOD FILES DETECTED:');
  console.log('');
  console.log('  Lines  Fan-Out  Exports  File');
  console.log('  -----  -------  -------  ----');
  for (const g of godFiles) {
    console.log(
      '  ' + String(g.lines).padStart(5) +
      '  ' + String(g.fanOut).padStart(7) +
      '  ' + String(g.exportCount).padStart(7) +
      '  ' + g.source
    );
  }
  console.log('');
  console.log(godFiles.length + ' god file(s) found. These are the highest-priority refactoring targets.');
  process.exit(1);
"
```

### Churn x Complexity Analysis

The most valuable refactoring targets are not just complex -- they are complex AND frequently changed. A complex file that nobody touches is stable tech debt. A complex file that changes every sprint is a ticking time bomb.

```bash
#!/usr/bin/env bash
# scripts/churn-complexity.sh
# Combines git change frequency with complexity scores to identify
# the highest-impact refactoring targets.
#
# Output: sorted list of files by churn * complexity, highest first.
# Refactor the top 5 and you will measurably reduce defect rate.

set -euo pipefail

SINCE=${1:-"6 months ago"}

echo "=== Churn x Complexity Analysis (since: $SINCE) ==="
echo ""

# Get change frequency per file
CHURN=$(git log --since="$SINCE" --format=format: --name-only \
  | grep '\.tsx\?$' \
  | grep -v 'node_modules\|dist\|\.test\.' \
  | sort | uniq -c | sort -rn)

echo "  Score   Churn  Lines  Depth  File"
echo "  ------  -----  -----  -----  ----"

echo "$CHURN" | head -50 | while read -r count file; do
  [ -f "$file" ] || continue

  # Line count
  LINES=$(wc -l < "$file" | tr -d ' ')

  # Max nesting depth (proxy for structural complexity)
  MAX_DEPTH=$(awk '{ match($0, /^[[:space:]]*/); depth=RLENGTH/2; if(depth>max) max=depth } END { print max+0 }' "$file")

  # Composite score: churn * (lines / 100) * (max_depth + 1)
  SCORE=$(echo "$count * ($LINES / 100) * ($MAX_DEPTH + 1)" | bc -l 2>/dev/null | cut -d. -f1)
  SCORE=${SCORE:-0}

  printf "  %6s  %5s  %5s  %5s  %s\n" "$SCORE" "$count" "$LINES" "$MAX_DEPTH" "$file"
done | sort -rn -k1 | head -20

echo ""
echo "Priority algorithm: score = changes * (lines / 100) * (nesting_depth + 1)"
echo ""
echo "  High churn + high complexity = refactor immediately"
echo "  High churn + low complexity  = leave alone (team is productive here)"
echo "  Low churn + high complexity  = schedule for later (stable tech debt)"
echo "  Low churn + low complexity   = ignore"
```

### Priority Algorithm

The priority formula is:

```
priority = changes_in_last_6_months * (lines / 100) * (max_nesting_depth + 1)
```

- **High churn + high complexity** = refactor immediately. These files generate the most bugs and slow down the most developers.
- **High churn + low complexity** = leave alone. Frequently changed but simple means the team is productive here.
- **Low churn + high complexity** = schedule for later. Complex but stable means it works and nobody is touching it.
- **Low churn + low complexity** = ignore. No problem here.

Refactoring the top 5 entries in this list reduces more defect risk than refactoring 50 files chosen at random.

---

## 8. Ratcheting Strategy for Existing Codebases

### The Problem

You cannot adopt strict design metrics in a large existing codebase all at once. Setting `max-lines-per-function: 50` on day one will produce 500 ESLint errors and nobody will fix them. The rules get disabled, and the effort is wasted.

### The Solution: Snapshot and Ratchet

1. Run all metrics against the current codebase and save the results as a baseline.
2. On every push, run the same metrics and compare against the baseline.
3. Fail if any metric got worse. Allow (and celebrate) improvements.
4. Periodically tighten the baseline by lowering thresholds.

The codebase can only get better, never worse. No team-wide cleanup sprint required.

### scripts/design-metrics-snapshot.sh

```bash
#!/usr/bin/env bash
# scripts/design-metrics-snapshot.sh
# Captures current design metric values as a JSON baseline.
# Run this once to establish the baseline, then periodically to tighten.

set -euo pipefail

BASELINE_FILE="${1:-.design-metrics-baseline.json}"

echo "=== Capturing Design Metrics Baseline ==="

# Metric 1: Files exceeding line thresholds
LARGE_FILES=$(find packages/*/src apps/*/src -name "*.ts" -o -name "*.tsx" 2>/dev/null \
  | grep -v node_modules | grep -v dist | grep -v '.test.' | grep -v '__tests__' \
  | while read -r f; do
    lines=$(wc -l < "$f" | tr -d ' ')
    [ "$lines" -gt 300 ] && echo "$f"
  done | wc -l | tr -d ' ')

# Metric 2: Circular dependencies
CIRCULARS=$(npx madge --circular --extensions ts --json packages/*/src apps/*/src 2>/dev/null \
  | node -e "
    const d=require('fs').readFileSync('/dev/stdin','utf8');
    const r=JSON.parse(d);
    console.log(r.length||0);
  " 2>/dev/null || echo 0)

# Metric 3: Fan-out violations (modules with fan-out > 10)
FANOUT_VIOLATIONS=$(npx depcruise \
  --config .dependency-cruiser.cjs \
  --output-type json \
  packages/*/src apps/*/src 2>/dev/null \
  | node -e "
    const d=require('fs').readFileSync('/dev/stdin','utf8');
    const r=JSON.parse(d);
    const v=(r.modules||[]).filter(m=>(m.dependencies||[]).length>10).length;
    console.log(v);
  " 2>/dev/null || echo 0)

# Metric 4: Max dependency depth
MAX_DEPTH=$(npx depcruise \
  --config .dependency-cruiser.cjs \
  --output-type json \
  --max-depth 20 \
  packages/*/src apps/*/src 2>/dev/null \
  | node -e "
    const d=require('fs').readFileSync('/dev/stdin','utf8');
    const r=JSON.parse(d);
    const mods=r.modules||[];
    const adj=new Map();
    for(const m of mods){adj.set(m.source,(m.dependencies||[]).map(d=>d.resolved));}
    const cache=new Map();
    function depth(s,v=new Set()){if(cache.has(s))return cache.get(s);if(v.has(s))return 0;v.add(s);const ds=adj.get(s)||[];let mx=0;for(const d of ds)mx=Math.max(mx,1+depth(d,new Set(v)));cache.set(s,mx);return mx;}
    let max=0;for(const m of mods)max=Math.max(max,depth(m.source));
    console.log(max);
  " 2>/dev/null || echo 0)

# Metric 5: Total ESLint design-rule warnings
ESLINT_DESIGN_WARNINGS=$(npx eslint --format json packages/*/src apps/*/src 2>/dev/null \
  | node -e "
    const d=require('fs').readFileSync('/dev/stdin','utf8');
    const r=JSON.parse(d);
    const rules=['max-lines-per-function','max-lines','max-depth','max-params','sonarjs/cognitive-complexity'];
    let count=0;
    for(const f of r){for(const m of(f.messages||[])){if(rules.includes(m.ruleId))count++;}}
    console.log(count);
  " 2>/dev/null || echo 0)

# Write baseline
cat > "$BASELINE_FILE" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "commit": "$(git rev-parse HEAD)",
  "metrics": {
    "large_files_over_300_lines": $LARGE_FILES,
    "circular_dependencies": $CIRCULARS,
    "fan_out_violations": $FANOUT_VIOLATIONS,
    "max_dependency_depth": $MAX_DEPTH,
    "eslint_design_warnings": $ESLINT_DESIGN_WARNINGS
  }
}
EOF

echo ""
echo "Baseline saved to $BASELINE_FILE:"
cat "$BASELINE_FILE"
echo ""
echo "Commit this file. Future pushes will be compared against it."
```

### scripts/design-metrics-check.sh

```bash
#!/usr/bin/env bash
# scripts/design-metrics-check.sh
# Compares current design metrics against the saved baseline.
# Fails if any metric has regressed (gotten worse).

set -euo pipefail

BASELINE_FILE="${1:-.design-metrics-baseline.json}"

if [ ! -f "$BASELINE_FILE" ]; then
  echo "No baseline found at $BASELINE_FILE. Run design-metrics-snapshot.sh first."
  echo "Skipping design metrics check."
  exit 0
fi

echo "=== Design Metrics Regression Check ==="
echo ""

# Capture current metrics (same logic as snapshot)
LARGE_FILES=$(find packages/*/src apps/*/src -name "*.ts" -o -name "*.tsx" 2>/dev/null \
  | grep -v node_modules | grep -v dist | grep -v '.test.' | grep -v '__tests__' \
  | while read -r f; do
    lines=$(wc -l < "$f" | tr -d ' ')
    [ "$lines" -gt 300 ] && echo "$f"
  done | wc -l | tr -d ' ')

CIRCULARS=$(npx madge --circular --extensions ts --json packages/*/src apps/*/src 2>/dev/null \
  | node -e "const d=require('fs').readFileSync('/dev/stdin','utf8');console.log(JSON.parse(d).length||0)" 2>/dev/null || echo 0)

FANOUT_VIOLATIONS=$(npx depcruise \
  --config .dependency-cruiser.cjs --output-type json \
  packages/*/src apps/*/src 2>/dev/null \
  | node -e "const d=require('fs').readFileSync('/dev/stdin','utf8');const r=JSON.parse(d);console.log((r.modules||[]).filter(m=>(m.dependencies||[]).length>10).length)" 2>/dev/null || echo 0)

# Compare against baseline
node -e "
  const fs = require('fs');
  const baseline = JSON.parse(fs.readFileSync('${BASELINE_FILE}', 'utf8'));
  const current = {
    large_files_over_300_lines: ${LARGE_FILES},
    circular_dependencies: ${CIRCULARS},
    fan_out_violations: ${FANOUT_VIOLATIONS},
  };

  const base = baseline.metrics;
  let regressions = 0;

  console.log('  Metric                       Baseline  Current  Delta');
  console.log('  ------                       --------  -------  -----');

  for (const [key, baseVal] of Object.entries(base)) {
    const curVal = current[key];
    if (curVal === undefined) continue;

    const delta = curVal - baseVal;
    const status = delta > 0 ? 'REGRESSED' : delta < 0 ? 'IMPROVED' : 'UNCHANGED';
    const deltaStr = delta > 0 ? '+' + delta : String(delta);

    console.log(
      '  ' + key.padEnd(31) +
      String(baseVal).padStart(8) +
      String(curVal).padStart(9) +
      deltaStr.padStart(7) +
      '  ' + status
    );

    if (delta > 0) regressions++;
  }

  console.log('');

  if (regressions > 0) {
    console.log(regressions + ' metric(s) regressed. Fix the regressions before pushing.');
    console.log('If intentional, update the baseline: bash scripts/design-metrics-snapshot.sh');
    process.exit(1);
  }

  console.log('No regressions detected. Design metrics are stable or improving.');
"
```

### How to Tighten Thresholds Over Time

Every 2-4 weeks (or once per sprint), re-run the snapshot after the team has improved metrics:

```bash
# After a sprint of cleanup work
bash scripts/design-metrics-snapshot.sh

# Review the delta
git diff .design-metrics-baseline.json

# Commit the tighter baseline
git add .design-metrics-baseline.json
git commit -m "chore: tighten design metrics baseline"
```

The rule: **baselines only move in one direction** -- toward stricter values. If a metric improved from 45 to 38, the new baseline is 38. The codebase never regresses back to 45. Target a 5% reduction per sprint -- this is aggressive enough to show progress but gradual enough to avoid burnout.

### Grandfathering: Per-File Overrides with Documented Tech Debt

For legacy files that cannot be fixed immediately, create explicit overrides with tech debt tickets and expiration dates:

```json
{
  "grandfathered": {
    "packages/old-parser/src/parse.ts": {
      "max_lines": 800,
      "cognitive_complexity": 35,
      "ticket": "TECH-301",
      "reason": "Parser rewrite scheduled for Q2",
      "expires": "2026-06-01"
    },
    "apps/legacy-api/src/routes/handler.ts": {
      "max_lines": 600,
      "fan_out": 14,
      "ticket": "TECH-234",
      "reason": "Route handler decomposition in progress",
      "expires": "2026-04-15"
    }
  }
}
```

The `expires` field ensures grandfathered exceptions are revisited. Add a CI check that reports on expired grandfathers:

```bash
#!/usr/bin/env bash
# scripts/check-expired-grandfathers.sh
# Fails if any grandfathered exception has passed its expiration date.

set -euo pipefail

GRANDFATHERED_FILE=".design-metrics-grandfathered.json"

if [ ! -f "$GRANDFATHERED_FILE" ]; then
  exit 0
fi

TODAY=$(date +%Y-%m-%d)

node -e "
  const fs = require('fs');
  const data = JSON.parse(fs.readFileSync('${GRANDFATHERED_FILE}', 'utf8'));
  const today = '${TODAY}';
  let expired = 0;

  for (const [file, overrides] of Object.entries(data.grandfathered || {})) {
    if (overrides.expires && overrides.expires <= today) {
      console.log('EXPIRED: ' + file);
      console.log('  Ticket: ' + overrides.ticket);
      console.log('  Reason: ' + overrides.reason);
      console.log('  Expired: ' + overrides.expires);
      console.log('');
      expired++;
    }
  }

  if (expired > 0) {
    console.log(expired + ' grandfathered exception(s) have expired.');
    console.log('Fix: resolve the tech debt or extend the expiration with team approval.');
    process.exit(1);
  }

  console.log('No expired grandfathered exceptions.');
"
```

---

## 9. Pre-push and CI Integration

### Which Metrics Run Where

Not every metric is fast enough for pre-push. The expensive ones belong in CI where they do not block the developer's flow.

| Metric | Pre-push | CI | Why |
|--------|----------|-----|-----|
| Cognitive complexity (ESLint) | Yes | Yes | Fast -- runs with regular lint pass |
| Function/file size (ESLint) | Yes | Yes | Fast -- runs with regular lint pass |
| Max depth / max params (ESLint) | Yes | Yes | Fast -- runs with regular lint pass |
| Circular dependency (madge) | Yes | Yes | Fast on scoped files (~2s) |
| Fan-out analysis | No | Yes | Requires full dependency graph (~15s) |
| Export surface area | No | Yes | Requires TypeScript compiler API (~10s) |
| Dependency depth | No | Yes | Requires full graph traversal (~15s) |
| God file detection | No | Yes | Combines multiple slow metrics |
| Churn x complexity | No | Yes | Requires git history analysis (~20s) |
| Baseline regression check | Yes | Yes | Fast comparison against JSON (~3s) |

### Turbo Integration for Scoped Analysis

Use Turbo's `--filter` to run only the metrics relevant to changed packages:

```bash
# In pre-push hook -- only lint changed packages with design rules
CHANGED_PACKAGES=$(git diff --name-only origin/main...HEAD \
  | grep -E '^(packages|apps)/' \
  | cut -d/ -f1-2 \
  | sort -u)

for pkg_path in $CHANGED_PACKAGES; do
  pkg_name=$(node -e "console.log(require('./$pkg_path/package.json').name)")
  echo "--- Design metrics for $pkg_name ---"
  pnpm turbo run lint --filter="$pkg_name"
done
```

### GitHub Actions Job that Posts Metric Diffs as PR Comments

```yaml
# .github/workflows/design-metrics.yml
name: Design Metrics

on:
  pull_request:
    branches: [main]

jobs:
  design-metrics:
    name: Design Quality Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for churn analysis

      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      # Fast gates (same as pre-push)
      - name: Lint (includes design rules)
        run: pnpm lint

      - name: Circular dependencies
        run: npx madge --circular --extensions ts packages/*/src apps/*/src

      # Slow gates (CI only)
      - name: Fan-out analysis
        id: fanout
        run: bash scripts/check-fan-out.sh 10 2>&1 | tee /tmp/fanout.txt
        continue-on-error: true

      - name: Dependency depth
        id: depth
        run: bash scripts/check-dependency-depth.sh 8 12 2>&1 | tee /tmp/depth.txt
        continue-on-error: true

      - name: Export surface area
        id: exports
        run: npx tsx scripts/count-exports.ts 2>&1 | tee /tmp/exports.txt
        continue-on-error: true

      - name: God file detection
        id: godfiles
        run: bash scripts/detect-god-files.sh 500 10 20 2>&1 | tee /tmp/godfiles.txt
        continue-on-error: true

      - name: Baseline regression check
        id: baseline
        run: bash scripts/design-metrics-check.sh 2>&1 | tee /tmp/baseline.txt
        continue-on-error: true

      - name: Churn x complexity report
        run: bash scripts/churn-complexity.sh "6 months ago" 2>&1 | tee /tmp/churn.txt
        continue-on-error: true

      # Post metrics as PR comment
      - name: Post metrics to PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');

            function readFile(path) {
              try { return fs.readFileSync(path, 'utf8').trim(); }
              catch { return 'No output'; }
            }

            const fanout = readFile('/tmp/fanout.txt');
            const depth = readFile('/tmp/depth.txt');
            const exports = readFile('/tmp/exports.txt');
            const godfiles = readFile('/tmp/godfiles.txt');
            const baseline = readFile('/tmp/baseline.txt');
            const churn = readFile('/tmp/churn.txt');

            const body = [
              '## Design Metrics Report',
              '',
              '<details>',
              '<summary>Fan-Out Analysis</summary>',
              '',
              '```',
              fanout,
              '```',
              '</details>',
              '',
              '<details>',
              '<summary>Dependency Depth</summary>',
              '',
              '```',
              depth,
              '```',
              '</details>',
              '',
              '<details>',
              '<summary>Export Surface Area</summary>',
              '',
              '```',
              exports,
              '```',
              '</details>',
              '',
              '<details>',
              '<summary>God File Detection</summary>',
              '',
              '```',
              godfiles,
              '```',
              '</details>',
              '',
              '<details>',
              '<summary>Baseline Comparison</summary>',
              '',
              '```',
              baseline,
              '```',
              '</details>',
              '',
              '<details>',
              '<summary>Churn x Complexity (Top 20)</summary>',
              '',
              '```',
              churn,
              '```',
              '</details>',
            ].join('\n');

            // Find existing comment to update (avoid spam on re-push)
            const { data: comments } = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
            });

            const existing = comments.find(c =>
              c.user.login === 'github-actions[bot]' &&
              c.body.includes('## Design Metrics Report')
            );

            if (existing) {
              await github.rest.issues.updateComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                comment_id: existing.id,
                body,
              });
            } else {
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                body,
              });
            }

      # Fail the job if any gate failed
      - name: Check gate results
        run: |
          FAILED=0
          [ "${{ steps.fanout.outcome }}" = "failure" ] && echo "Fan-out check failed" && FAILED=1
          [ "${{ steps.depth.outcome }}" = "failure" ] && echo "Dependency depth check failed" && FAILED=1
          [ "${{ steps.exports.outcome }}" = "failure" ] && echo "Export surface check failed" && FAILED=1
          [ "${{ steps.baseline.outcome }}" = "failure" ] && echo "Baseline regression check failed" && FAILED=1
          [ "$FAILED" -eq 1 ] && exit 1
          echo "All design metric gates passed."
```

### Badge Generation for README

```bash
#!/usr/bin/env bash
# scripts/generate-design-badge.sh
# Generates a shields.io badge URL based on the baseline metrics.

set -euo pipefail

BASELINE_FILE=".design-metrics-baseline.json"

if [ ! -f "$BASELINE_FILE" ]; then
  echo "https://img.shields.io/badge/design_metrics-no_baseline-lightgrey"
  exit 0
fi

TOTAL_ISSUES=$(node -e "
  const b = JSON.parse(require('fs').readFileSync('$BASELINE_FILE','utf8'));
  const m = b.metrics;
  const total = (m.large_files_over_300_lines || 0) +
                (m.circular_dependencies || 0) +
                (m.fan_out_violations || 0);
  console.log(total);
")

if [ "$TOTAL_ISSUES" -eq 0 ]; then
  COLOR="brightgreen"
  LABEL="clean"
elif [ "$TOTAL_ISSUES" -lt 10 ]; then
  COLOR="yellow"
  LABEL="${TOTAL_ISSUES}_issues"
else
  COLOR="red"
  LABEL="${TOTAL_ISSUES}_issues"
fi

echo "https://img.shields.io/badge/design_health-${LABEL}-${COLOR}"
```

Usage in README:

```markdown
![Design Health](https://img.shields.io/badge/design_health-clean-brightgreen)
```

---

## 10. Per-Language Equivalents

The metrics in this reference are universal. The tools change per language but the concepts are identical: cognitive complexity, coupling, depth, circulars, and size limits apply everywhere.

### Python

```bash
pip install radon pylint wily
```

**radon -- complexity analysis:**

```bash
# Cyclomatic complexity, only show functions rated C or worse
radon cc src/ -a -nc --min C

# Cognitive complexity (requires radon >= 5.1)
radon cc src/ -s -a

# Maintainability index per file
radon mi src/ -s

# JSON output for scripting
radon cc src/ -j | python -m json.tool
```

**wily -- complexity tracking over time:**

```bash
# Index git history (run once, then incrementally)
wily build src/

# Show complexity trend for a file
wily report src/module.py

# Compare complexity across commits
wily diff src/ HEAD~10 HEAD

# Rank modules by maintainability (worst first)
wily rank src/ --threshold B
```

**pylint design metrics (pyproject.toml):**

```toml
[tool.pylint.design]
max-args = 5
max-locals = 15
max-returns = 6
max-branches = 12
max-statements = 50
max-parents = 7
max-attributes = 10
max-bool-expr = 5
max-public-methods = 20
min-public-methods = 1
max-module-lines = 300
max-nested-blocks = 4
```

```bash
# Run pylint design checks only
pylint --disable=all \
  --enable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements,too-many-return-statements,too-many-instance-attributes,too-few-public-methods,too-many-public-methods \
  src/

# Circular dependency detection
pylint --disable=all --enable=cyclic-import src/

# Dependency graph
pip install pydeps
pydeps src/mypackage --cluster --max-bacon 3 -o deps.svg
```

### Go

```bash
go install github.com/fzipp/gocyclo/cmd/gocyclo@latest
go install github.com/uudashr/gocognit/cmd/gocognit@latest
go install github.com/go-critic/go-critic/cmd/gocritic@latest
```

**Direct tool usage:**

```bash
# Cyclomatic complexity
gocyclo -over 15 ./...              # Report functions with CC > 15
gocyclo -top 20 ./...               # Show top 20 most complex functions
gocyclo -avg ./...                  # Show average complexity

# Cognitive complexity
gocognit -over 15 ./...             # Report functions above threshold
gocognit -top 20 ./...              # Show top 20

# go-critic (includes complexity + many design checks)
gocritic check -enableAll ./...
```

**golangci-lint (aggregator, recommended for CI):**

```yaml
# .golangci.yml
linters:
  enable:
    - gocyclo
    - gocognit
    - gocritic
    - funlen
    - cyclop
    - nestif
    - maintidx

linters-settings:
  gocyclo:
    min-complexity: 15
  gocognit:
    min-complexity: 15
  funlen:
    lines: 80
    statements: 50
  cyclop:
    max-complexity: 15
    package-average: 5.0
  nestif:
    min-complexity: 4
  maintidx:
    under: 20

issues:
  max-issues-per-linter: 50
  max-same-issues: 10
```

```bash
golangci-lint run ./...
```

**Dependency visualization:**

```bash
go install github.com/loov/goda@latest
goda graph ./... | dot -Tsvg -o deps.svg
```

### Rust

```bash
cargo install cargo-geiger
```

**cargo-geiger -- unsafe code tracking (Rust-specific but critical):**

```bash
cargo geiger                         # Report unsafe code in all dependencies
cargo geiger --update-readme         # Update README badge with unsafe count
```

**clippy with complexity lints (clippy.toml):**

```toml
cognitive-complexity-threshold = 15
too-many-arguments-threshold = 5
too-many-lines-threshold = 80
type-complexity-threshold = 250
```

```bash
cargo clippy -- \
  -W clippy::cognitive_complexity \
  -W clippy::too_many_arguments \
  -W clippy::too_many_lines \
  -W clippy::type_complexity \
  -W clippy::excessive_nesting
```

**Dependency analysis:**

```bash
cargo install cargo-depgraph
cargo depgraph | dot -Tsvg -o deps.svg

# Duplicate dependency detection (different versions of the same crate)
cargo tree --duplicates

# Show dependency tree to depth 8
cargo tree --depth 8
```

### Java

**PMD -- design rules (pmd-design-rules.xml):**

```xml
<?xml version="1.0"?>
<ruleset name="Design Metrics"
  xmlns="http://pmd.sourceforge.net/ruleset/2.0.0">
  <rule ref="category/java/design.xml/CyclomaticComplexity">
    <properties>
      <property name="classReportLevel" value="80" />
      <property name="methodReportLevel" value="15" />
    </properties>
  </rule>
  <rule ref="category/java/design.xml/CognitiveComplexity">
    <properties>
      <property name="reportLevel" value="15" />
    </properties>
  </rule>
  <rule ref="category/java/design.xml/TooManyMethods">
    <properties>
      <property name="maxmethods" value="20" />
    </properties>
  </rule>
  <rule ref="category/java/design.xml/TooManyFields">
    <properties>
      <property name="maxfields" value="10" />
    </properties>
  </rule>
  <rule ref="category/java/design.xml/ExcessiveParameterList">
    <properties>
      <property name="minimum" value="5" />
    </properties>
  </rule>
  <rule ref="category/java/design.xml/GodClass" />
  <rule ref="category/java/design.xml/CouplingBetweenObjects">
    <properties>
      <property name="threshold" value="10" />
    </properties>
  </rule>
</ruleset>
```

**SpotBugs (successor to FindBugs):**

```groovy
// build.gradle
plugins {
    id 'com.github.spotbugs' version '6.0.0'
}

spotbugs {
    effort = 'max'
    reportLevel = 'medium'
}
```

```bash
./gradlew spotbugsMain
```

**ArchUnit -- architecture enforcement in unit tests:**

```java
// build.gradle: testImplementation 'com.tngtech.archunit:archunit-junit5:1.2.1'

import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.*;

@AnalyzeClasses(packages = "com.example")
class DesignMetricsTest {

    @ArchTest
    static final ArchRule layer_dependencies =
        noClasses()
            .that().resideInAPackage("..domain..")
            .should().dependOnClassesThat()
            .resideInAPackage("..infrastructure..");

    @ArchTest
    static final ArchRule no_cycles =
        slices().matching("com.example.(*)..")
            .should().beFreeOfCycles();
}
```

### Summary Table

| Metric | TypeScript | Python | Go | Rust | Java |
|--------|-----------|--------|-----|------|------|
| Cognitive complexity | sonarjs ESLint plugin | radon | gocognit | clippy | PMD / SonarQube |
| Cyclomatic complexity | sonarjs ESLint plugin | radon | gocyclo | clippy | PMD |
| Function size | max-lines-per-function | pylint | funlen | clippy | Checkstyle |
| Param count | max-params | pylint | go-critic | clippy | PMD |
| Nesting depth | max-depth | pylint | nestif | clippy | PMD |
| Circular deps | dependency-cruiser / madge | pylint | goda | -- | ArchUnit |
| Coupling (fan-out) | dependency-cruiser | pylint | go-critic | -- | PMD / ArchUnit |
| Complexity tracking | baseline JSON / ratchet | wily | -- | -- | SonarQube |
| Unsafe tracking | -- | -- | -- | cargo-geiger | SpotBugs |

---

## Summary

Design metrics are the structural backbone of a quality-gated codebase. Mechanical gates ensure the code is correct. Design metrics ensure the code stays maintainable.

| Metric | Tool (TypeScript) | Threshold | Layer |
|--------|------------------|-----------|-------|
| Cognitive complexity | eslint-plugin-sonarjs | warn 15, error 25 | Pre-commit |
| Function length | ESLint `max-lines-per-function` | warn 50, error 80 | Pre-commit |
| File length | ESLint `max-lines` | warn 300, error 500 | Pre-commit |
| Parameter count | ESLint `max-params` | error 4 | Pre-commit |
| Nesting depth | ESLint `max-depth` | error 4 | Pre-commit |
| Fan-out | dependency-cruiser | error > 10 | CI |
| Export surface | custom script (TS compiler API) | warn 30, error 50 | CI |
| Dependency depth | dependency-cruiser | warn 8, error 12 | CI |
| Circular deps (file) | import-x/no-cycle | 0 | Pre-push |
| Circular deps (package) | dependency-cruiser | 0 | CI |
| God files | custom script (combined metrics) | lines > 500 + fan-out > 10 + exports > 20 | CI |
| Baseline regression | snapshot + check scripts | no regression allowed | Pre-push + CI |

Every threshold is a starting point. Use the ratcheting strategy to adapt to existing codebases. The goal is not perfection on day one -- it is a one-way ratchet toward structural quality that never slips backward.
