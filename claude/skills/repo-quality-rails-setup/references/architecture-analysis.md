# Architecture Analysis: Dependency Graphs, API Surfaces, and Structural Metrics

Individual lint rules catch local problems. Architecture analysis catches systemic ones. A repo can pass every ESLint rule, every type-check, and every unit test while harboring circular dependency chains, god packages that everything depends on, and an API surface that grows without bound. You only notice these problems when someone tries to extract a package, upgrade a major dependency, or onboard a new team -- and then it is too late.

Architecture analysis turns "code review intuition" into automated gates. Instead of relying on a senior engineer to eyeball the dependency graph, you encode the invariants and let CI enforce them.

Three tools form the core:

- **dependency-cruiser** -- graph analysis. Validates import rules, detects cycles, computes structural metrics.
- **api-extractor** -- surface tracking. Extracts the public API of each package into a reviewable file. API changes become visible in PR diffs.
- **Custom scripts** -- cohesion metrics. Measure fan-in, fan-out, instability, and cohesion per package. Track erosion over time.

---

## 1. Dependency-Cruiser: Full Setup

### Install

```bash
pnpm add -D dependency-cruiser
```

### Configuration

Create `.dependency-cruiser.cjs` at the repo root. This is the complete config for a TypeScript monorepo with `apps/` and `packages/` directories.

```js
// .dependency-cruiser.cjs
/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    // ─────────────────────────────────────────────────────────
    // No circular dependencies at any level
    // ─────────────────────────────────────────────────────────
    {
      name: "no-circular",
      severity: "error",
      comment: "Circular dependencies create coupling that makes packages impossible to extract or test independently.",
      from: {},
      to: {
        circular: true,
      },
    },

    // ─────────────────────────────────────────────────────────
    // No orphan modules (files nothing imports)
    // ─────────────────────────────────────────────────────────
    {
      name: "no-orphans",
      severity: "warn",
      comment: "Orphan modules are dead code. They add to bundle size and cognitive load without providing value.",
      from: {
        orphan: true,
        pathNot: [
          // Entry points are never imported, they are the root
          "(^|/)index\\.ts$",
          "\\.d\\.ts$",
          "(^|/)main\\.ts$",
          // Config files
          "\\.config\\.(ts|js|mjs|cjs)$",
          // Test files
          "\\.test\\.ts$",
          "\\.spec\\.ts$",
          "__tests__/",
          // Next.js conventions
          "(^|/)page\\.tsx?$",
          "(^|/)layout\\.tsx?$",
          "(^|/)loading\\.tsx?$",
          "(^|/)error\\.tsx?$",
          "(^|/)not-found\\.tsx?$",
          "(^|/)route\\.ts$",
          "(^|/)middleware\\.ts$",
        ],
      },
      to: {},
    },

    // ─────────────────────────────────────────────────────────
    // No importing from dist/ (use source via development condition)
    // ─────────────────────────────────────────────────────────
    {
      name: "no-dist-imports",
      severity: "error",
      comment: "Import from source, not compiled output. Use package.json exports with development condition.",
      from: {},
      to: {
        path: "/dist/",
        pathNot: "node_modules",
      },
    },

    // ─────────────────────────────────────────────────────────
    // No importing deprecated packages
    // ─────────────────────────────────────────────────────────
    {
      name: "no-deprecated",
      severity: "warn",
      comment: "Deprecated packages will be removed. Migrate away before they break.",
      from: {},
      to: {
        dependencyTypes: ["deprecated"],
      },
    },

    // ─────────────────────────────────────────────────────────
    // Apps cannot import from other apps
    // ─────────────────────────────────────────────────────────
    {
      name: "no-app-to-app",
      severity: "error",
      comment: "Apps are deployment units. They must not depend on each other. Extract shared logic into a package.",
      from: {
        path: "^apps/([^/]+)/",
      },
      to: {
        path: "^apps/([^/]+)/",
        pathNot: "^apps/$1/",
      },
    },

    // ─────────────────────────────────────────────────────────
    // Packages cannot import from apps
    // ─────────────────────────────────────────────────────────
    {
      name: "no-package-to-app",
      severity: "error",
      comment: "Packages are shared libraries. They must not depend on apps. Invert the dependency.",
      from: {
        path: "^packages/",
      },
      to: {
        path: "^apps/",
      },
    },

    // ─────────────────────────────────────────────────────────
    // No reaching into node_modules subdirectories
    // ─────────────────────────────────────────────────────────
    {
      name: "no-node-modules-subpath",
      severity: "error",
      comment: "Use package entry points, not deep imports into node_modules. Deep imports break when packages restructure.",
      from: {},
      to: {
        dependencyTypes: ["npm"],
        pathNot: "node_modules/[^/]+$",
        path: "node_modules/.+/.+",
      },
    },

    // ─────────────────────────────────────────────────────────
    // No dev dependencies in production code
    // ─────────────────────────────────────────────────────────
    {
      name: "no-dev-deps-in-production",
      severity: "error",
      comment: "Dev dependencies are not installed in production. Importing them causes runtime crashes.",
      from: {
        pathNot: [
          "\\.test\\.ts$",
          "\\.spec\\.ts$",
          "__tests__/",
          "\\.config\\.(ts|js|mjs|cjs)$",
          "vitest\\..*",
          "scripts/",
        ],
      },
      to: {
        dependencyTypes: ["npm-dev"],
      },
    },
  ],

  options: {
    doNotFollow: {
      path: "node_modules",
    },

    tsPreCompilationDeps: true,

    tsConfig: {
      fileName: "tsconfig.json",
    },

    enhancedResolveOptions: {
      exportsFields: ["exports"],
      conditionNames: ["import", "require", "node", "default", "types"],
      mainFields: ["module", "main", "types"],
    },

    reporterOptions: {
      dot: {
        collapsePattern: "node_modules/(@[^/]+/[^/]+|[^/]+)",
        theme: {
          graph: {
            splines: "ortho",
            rankdir: "TB",
            fontname: "Helvetica",
          },
          node: {
            fontname: "Helvetica",
            fontsize: "10",
          },
          edge: {
            fontname: "Helvetica",
            fontsize: "8",
          },
          modules: [
            {
              criteria: { source: "^apps/" },
              attributes: { fillcolor: "#ccddff", style: "filled" },
            },
            {
              criteria: { source: "^packages/" },
              attributes: { fillcolor: "#ddffdd", style: "filled" },
            },
          ],
          dependencies: [
            {
              criteria: { resolved: "^apps/" },
              attributes: { color: "#4477aa" },
            },
            {
              criteria: { resolved: "^packages/" },
              attributes: { color: "#44aa44" },
            },
            {
              criteria: { circular: true },
              attributes: { color: "red", penwidth: "2.0" },
            },
          ],
        },
      },
      archi: {
        collapsePattern: "^(apps|packages)/[^/]+",
        theme: {
          graph: {
            splines: "ortho",
            rankdir: "TB",
          },
          modules: [
            {
              criteria: { source: "^apps/" },
              attributes: { fillcolor: "#ccddff", style: "filled" },
            },
            {
              criteria: { source: "^packages/" },
              attributes: { fillcolor: "#ddffdd", style: "filled" },
            },
          ],
        },
      },
    },

    cache: {
      strategy: "content",
      folder: "node_modules/.cache/dependency-cruiser",
    },

    progress: { type: "performance-log" },
  },
};
```

### Package scripts

Add these to the root `package.json`:

```json
{
  "scripts": {
    "dep:check": "depcruise --config .dependency-cruiser.cjs apps/ packages/",
    "dep:graph": "depcruise --config .dependency-cruiser.cjs --output-type dot apps/ packages/ | dot -T svg > reports/dependency-graph.svg",
    "dep:graph:archi": "depcruise --config .dependency-cruiser.cjs --output-type archi apps/ packages/ | dot -T svg > reports/architecture-graph.svg",
    "dep:html": "depcruise --config .dependency-cruiser.cjs --output-type html apps/ packages/ > reports/dependency-report.html",
    "dep:json": "depcruise --config .dependency-cruiser.cjs --output-type json apps/ packages/ > reports/dependency-data.json"
  }
}
```

Create the reports directory and add it to `.gitignore`:

```bash
mkdir -p reports
echo "reports/" >> .gitignore
```

- **`dep:check`** -- rule validation only. Fast. Use in pre-push hooks and CI.
- **`dep:graph`** -- full module-level SVG graph. Shows every file and its imports.
- **`dep:graph:archi`** -- collapsed architecture-level graph. Shows package-to-package dependencies only. Best for PR comments and dashboards.
- **`dep:html`** -- interactive HTML report. Click any module to see its dependencies.
- **`dep:json`** -- raw JSON output. Feed this into custom metric scripts.

### Key config decisions

**`tsPreCompilationDeps: true`** tells dependency-cruiser to resolve imports from TypeScript source files rather than compiled JavaScript. This is essential for monorepos that use `exports` conditions to serve source during development.

**`cache.strategy: "content"`** caches analysis results based on file content hashes. Repeated runs against unchanged files are near-instant.

**Reporter themes** color-code apps (blue) and packages (green) so the graph is immediately readable. Circular dependencies render in red with double-width edges.

**The `archi` reporter** collapses all files within each `apps/*` or `packages/*` directory into a single node. The resulting graph shows inter-package dependencies without the noise of individual files.

---

## 2. Dependency Graph Visualization on CI

Generate the architecture-level SVG on every PR and upload it as an artifact.

```yaml
# Add to .github/workflows/ci.yml or create .github/workflows/dependency-graph.yml
dependency-graph:
  name: Dependency graph
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    - uses: pnpm/action-setup@v4
      with:
        version: 9

    - uses: actions/setup-node@v4
      with:
        node-version: 20
        cache: pnpm

    - run: pnpm install --frozen-lockfile

    - name: Install Graphviz
      run: sudo apt-get install -y graphviz

    - name: Generate dependency graph
      run: |
        mkdir -p reports
        pnpm dep:graph:archi
        pnpm dep:graph

    - uses: actions/upload-artifact@v4
      with:
        name: dependency-graph
        path: |
          reports/dependency-graph.svg
          reports/architecture-graph.svg
        retention-days: 30
```

### Post the graph as a PR comment (optional)

Use `actions/github-script` to post the architecture graph directly in the PR conversation. Requires encoding the SVG to base64 and embedding it, or uploading to an image host.

A simpler approach: post a text summary with a link to the artifact.

```yaml
    - name: Comment on PR
      if: github.event_name == 'pull_request'
      uses: actions/github-script@v7
      with:
        script: |
          const fs = require('fs');

          // Read the dep:check output for any violations
          const { execSync } = require('child_process');
          let violations = '';
          try {
            execSync('pnpm dep:check', { stdio: 'pipe' });
            violations = 'No dependency rule violations found.';
          } catch (e) {
            violations = '**Dependency rule violations detected:**\n```\n' +
              e.stdout.toString().slice(0, 3000) + '\n```';
          }

          const body = [
            '## Dependency Graph',
            '',
            violations,
            '',
            'Download the full graph from the **dependency-graph** artifact in this workflow run.',
          ].join('\n');

          // Find and update existing comment, or create new one
          const { data: comments } = await github.rest.issues.listComments({
            owner: context.repo.owner,
            repo: context.repo.repo,
            issue_number: context.issue.number,
          });

          const botComment = comments.find(c =>
            c.user.type === 'Bot' && c.body.includes('## Dependency Graph')
          );

          if (botComment) {
            await github.rest.issues.updateComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              comment_id: botComment.id,
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
```

---

## 3. Graph Metrics with Thresholds

dependency-cruiser validates rules but does not compute structural metrics. Write a post-processing script that parses the JSON output and computes them.

### The metrics

| Metric | What it measures | Threshold |
|--------|-----------------|-----------|
| Circular dependencies | Cycles in the import graph | 0 (hard fail) |
| Orphan modules | Files nothing imports | 0 (warning) |
| Max dependency depth | Longest chain from any module to a leaf | 6 for apps, 3 for packages |
| Average fan-out | Mean number of direct dependencies per module | Alert if +10% between releases |
| Instability (I) | I = fan-out / (fan-in + fan-out). 0 = maximally stable, 1 = maximally unstable | Flag concrete + stable packages |

### Instability explained

Robert C. Martin's instability metric tells you how resilient a package is to change.

- **I near 0 (stable):** Many packages depend on this one. Changes here ripple everywhere. Stable packages should be abstract -- interfaces, types, contracts.
- **I near 1 (unstable):** This package depends on many others but nothing depends on it. Changes are local. Unstable packages should be concrete -- implementations, apps.
- **I near 0 but concrete:** Danger zone. This package is hard to change (everything depends on it) but full of implementation details. Refactoring it breaks the world. Flag these.

### Metric computation script

```js
#!/usr/bin/env node
// scripts/dep-metrics.mjs
//
// Computes structural metrics from dependency-cruiser JSON output.
//
// Usage:
//   pnpm dep:json
//   node scripts/dep-metrics.mjs reports/dependency-data.json
//
// Exits non-zero if any threshold is violated.

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";

// ─────────────────────────────────────────────────────────
// Thresholds
// ─────────────────────────────────────────────────────────
const THRESHOLDS = {
  maxCircular: 0,
  maxOrphans: 0, // warning only, does not fail
  maxDepthApps: 6,
  maxDepthPackages: 3,
  fanOutIncreasePercent: 10,
  maxFanOutPerPR: 3, // max fan-out increase for a single package in one PR
};

// ─────────────────────────────────────────────────────────
// Parse input
// ─────────────────────────────────────────────────────────
const inputPath = process.argv[2];
if (!inputPath) {
  console.error("Usage: node scripts/dep-metrics.mjs <dependency-cruiser-json>");
  process.exit(1);
}

const raw = JSON.parse(readFileSync(resolve(inputPath), "utf-8"));
const modules = raw.modules || [];

// ─────────────────────────────────────────────────────────
// Compute per-module metrics
// ─────────────────────────────────────────────────────────

// fan-out: number of modules this module imports
// fan-in: number of modules that import this module
const fanOut = new Map();
const fanIn = new Map();
const circularSets = [];
const orphans = [];

for (const mod of modules) {
  const source = mod.source;
  const deps = (mod.dependencies || []).filter(
    (d) => !d.resolved.includes("node_modules")
  );

  fanOut.set(source, deps.length);

  if (!fanIn.has(source)) {
    fanIn.set(source, 0);
  }

  for (const dep of deps) {
    fanIn.set(dep.resolved, (fanIn.get(dep.resolved) || 0) + 1);

    if (dep.circular) {
      circularSets.push({ from: source, to: dep.resolved });
    }
  }

  if (mod.orphan) {
    orphans.push(source);
  }
}

// ─────────────────────────────────────────────────────────
// Compute per-package metrics
// ─────────────────────────────────────────────────────────

function getPackageName(filePath) {
  const match = filePath.match(/^(apps|packages)\/([^/]+)/);
  return match ? `${match[1]}/${match[2]}` : null;
}

const packageModules = new Map(); // packageName -> Set<module>
const packageFanOut = new Map(); // packageName -> Set<external package deps>
const packageFanIn = new Map(); // packageName -> Set<packages that depend on it>

for (const mod of modules) {
  const pkg = getPackageName(mod.source);
  if (!pkg) continue;

  if (!packageModules.has(pkg)) {
    packageModules.set(pkg, new Set());
    packageFanOut.set(pkg, new Set());
    packageFanIn.set(pkg, new Set());
  }
  packageModules.get(pkg).add(mod.source);

  for (const dep of mod.dependencies || []) {
    const depPkg = getPackageName(dep.resolved);
    if (depPkg && depPkg !== pkg) {
      packageFanOut.get(pkg).add(depPkg);
      if (!packageFanIn.has(depPkg)) {
        packageFanIn.set(depPkg, new Set());
      }
      packageFanIn.get(depPkg).add(pkg);
    }
  }
}

// ─────────────────────────────────────────────────────────
// Compute dependency depth per package (BFS from leaves)
// ─────────────────────────────────────────────────────────

function computeMaxDepth(pkg, visited = new Set()) {
  if (visited.has(pkg)) return 0;
  visited.add(pkg);

  const deps = packageFanOut.get(pkg);
  if (!deps || deps.size === 0) return 0;

  let maxChildDepth = 0;
  for (const dep of deps) {
    const childDepth = computeMaxDepth(dep, visited);
    if (childDepth > maxChildDepth) {
      maxChildDepth = childDepth;
    }
  }
  return maxChildDepth + 1;
}

// ─────────────────────────────────────────────────────────
// Build report
// ─────────────────────────────────────────────────────────

const packageMetrics = [];
let hasErrors = false;
const errors = [];
const warnings = [];

for (const [pkg] of packageModules) {
  const fo = packageFanOut.get(pkg)?.size || 0;
  const fi = packageFanIn.get(pkg)?.size || 0;
  const instability = fo + fi === 0 ? 0 : fo / (fo + fi);
  const depth = computeMaxDepth(pkg);
  const moduleCount = packageModules.get(pkg)?.size || 0;
  const isApp = pkg.startsWith("apps/");
  const maxDepth = isApp ? THRESHOLDS.maxDepthApps : THRESHOLDS.maxDepthPackages;

  const status = [];
  if (depth > maxDepth) {
    status.push(`depth ${depth} > ${maxDepth}`);
    errors.push(`${pkg}: dependency depth ${depth} exceeds threshold ${maxDepth}`);
    hasErrors = true;
  }
  if (instability < 0.3 && moduleCount > 5 && fo > 0) {
    // Concrete and stable -- potential problem
    status.push("concrete+stable");
    warnings.push(`${pkg}: instability ${instability.toFixed(2)} is low but package has ${moduleCount} modules (consider abstracting)`);
  }

  packageMetrics.push({
    package: pkg,
    modules: moduleCount,
    fanIn: fi,
    fanOut: fo,
    depth,
    instability: Number(instability.toFixed(2)),
    status: status.length > 0 ? status.join(", ") : "ok",
  });
}

// Check circular dependencies
if (circularSets.length > THRESHOLDS.maxCircular) {
  hasErrors = true;
  errors.push(`Found ${circularSets.length} circular dependency pair(s)`);
  for (const c of circularSets.slice(0, 10)) {
    errors.push(`  ${c.from} <-> ${c.to}`);
  }
}

// Check orphans
if (orphans.length > THRESHOLDS.maxOrphans) {
  for (const o of orphans) {
    warnings.push(`Orphan module: ${o}`);
  }
}

// ─────────────────────────────────────────────────────────
// Compare against previous snapshot (if exists)
// ─────────────────────────────────────────────────────────

const snapshotPath = resolve("reports/dep-metrics-snapshot.json");
if (existsSync(snapshotPath)) {
  const previous = JSON.parse(readFileSync(snapshotPath, "utf-8"));
  const prevByPkg = new Map(previous.packages?.map((p) => [p.package, p]) || []);

  for (const current of packageMetrics) {
    const prev = prevByPkg.get(current.package);
    if (!prev) continue;

    const fanOutDelta = current.fanOut - prev.fanOut;
    if (fanOutDelta > THRESHOLDS.maxFanOutPerPR) {
      errors.push(
        `${current.package}: fan-out increased by ${fanOutDelta} (was ${prev.fanOut}, now ${current.fanOut}). Threshold: ${THRESHOLDS.maxFanOutPerPR} per PR.`
      );
      hasErrors = true;
    }
  }

  // Total cross-package dependencies
  const prevTotal = previous.packages?.reduce((s, p) => s + p.fanOut, 0) || 0;
  const currentTotal = packageMetrics.reduce((s, p) => s + p.fanOut, 0);
  if (prevTotal > 0) {
    const increasePercent = ((currentTotal - prevTotal) / prevTotal) * 100;
    if (increasePercent > THRESHOLDS.fanOutIncreasePercent) {
      errors.push(
        `Total cross-package dependencies increased by ${increasePercent.toFixed(1)}% (was ${prevTotal}, now ${currentTotal}). Threshold: ${THRESHOLDS.fanOutIncreasePercent}%.`
      );
      hasErrors = true;
    }
  }
}

// ─────────────────────────────────────────────────────────
// Output
// ─────────────────────────────────────────────────────────

console.log("\n=== Dependency Metrics ===\n");

// Table
console.log(
  "| Package | Modules | Fan-in | Fan-out | Depth | Instability | Status |"
);
console.log(
  "|---------|---------|--------|---------|-------|-------------|--------|"
);
for (const p of packageMetrics.sort((a, b) => a.package.localeCompare(b.package))) {
  console.log(
    `| ${p.package} | ${p.modules} | ${p.fanIn} | ${p.fanOut} | ${p.depth} | ${p.instability.toFixed(2)} | ${p.status} |`
  );
}

console.log(`\nCircular dependencies: ${circularSets.length}`);
console.log(`Orphan modules: ${orphans.length}`);
console.log(`Total packages: ${packageModules.size}`);

if (warnings.length > 0) {
  console.log("\n--- Warnings ---");
  for (const w of warnings) {
    console.log(`  WARN: ${w}`);
  }
}

if (errors.length > 0) {
  console.log("\n--- Errors ---");
  for (const e of errors) {
    console.log(`  ERROR: ${e}`);
  }
}

// ─────────────────────────────────────────────────────────
// Save current snapshot
// ─────────────────────────────────────────────────────────

const snapshot = {
  timestamp: new Date().toISOString(),
  circularCount: circularSets.length,
  orphanCount: orphans.length,
  packages: packageMetrics,
};

writeFileSync(resolve("reports/dep-metrics-current.json"), JSON.stringify(snapshot, null, 2));
console.log("\nSnapshot written to reports/dep-metrics-current.json");

if (hasErrors) {
  console.log("\nFAILED: threshold violations detected.");
  process.exit(1);
} else {
  console.log("\nPASSED: all thresholds met.");
}
```

### CI step for metric computation

```yaml
    - name: Compute dependency metrics
      run: |
        mkdir -p reports
        pnpm dep:json
        node scripts/dep-metrics.mjs reports/dependency-data.json
```

---

## 4. API Surface Tracking with api-extractor

### What it does

`@microsoft/api-extractor` reads the `.d.ts` files produced by `tsc` and extracts the public API of a package into a single `.api.md` file. This file is committed to the repo. When a PR changes a package's public API, the `.api.md` file changes, making the API delta visible in the PR diff. Reviewers see exactly what was added, removed, or modified.

### Install

```bash
pnpm add -D @microsoft/api-extractor
```

### Per-package configuration

Each publishable package gets its own `api-extractor.json`:

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/api-extractor/v7/api-extractor.schema.json",
  "projectFolder": ".",
  "mainEntryPointFilePath": "<projectFolder>/dist/index.d.ts",
  "compiler": {
    "tsconfigFilePath": "<projectFolder>/tsconfig.json"
  },
  "apiReport": {
    "enabled": true,
    "reportFileName": "<unscopedPackageName>.api.md",
    "reportFolder": "<projectFolder>/",
    "reportTempFolder": "<projectFolder>/temp/"
  },
  "docModel": {
    "enabled": false
  },
  "dtsRollup": {
    "enabled": false
  },
  "tsdocMetadata": {
    "enabled": false
  },
  "messages": {
    "compilerMessageReporting": {
      "default": {
        "logLevel": "warning"
      }
    },
    "extractorMessageReporting": {
      "default": {
        "logLevel": "warning"
      },
      "ae-missing-release-tag": {
        "logLevel": "none"
      }
    },
    "tsdocMessageReporting": {
      "default": {
        "logLevel": "none"
      }
    }
  }
}
```

### Workflow

1. **Build the package** -- api-extractor works on `.d.ts` files, so `tsc` must run first.
2. **Run locally** -- `api-extractor run --local` updates the `.api.md` file without failing on changes.
3. **Commit the `.api.md`** -- it becomes part of the repo.
4. **In CI** -- `api-extractor run` (without `--local`) fails if the `.api.md` is out of date.

### Package scripts

Add to each publishable package's `package.json`:

```json
{
  "scripts": {
    "api:extract": "api-extractor run --local --verbose",
    "api:check": "api-extractor run --verbose"
  }
}
```

And to the root `package.json` for monorepo-wide execution:

```json
{
  "scripts": {
    "api:extract": "turbo run api:extract",
    "api:check": "turbo run api:check"
  }
}
```

### CI job

```yaml
  api-surface:
    name: API surface check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm

      - run: pnpm install --frozen-lockfile
      - run: pnpm build

      - name: Check API surface
        run: pnpm api:check
```

If a developer changes a package's public API but forgets to update the `.api.md` file, this job fails with a clear message showing the diff. The fix: run `pnpm api:extract` locally and commit the updated file.

### What the review gate catches

- Accidental public API additions (a new export that was meant to be internal)
- Breaking changes to function signatures
- Type changes that affect consumers
- Removed exports

Without this gate, API changes are invisible in code review -- a reviewer has to mentally reconstruct the public API from scattered file changes. The `.api.md` file makes the API surface explicit.

---

## 5. Package Cohesion Analysis

A cohesive package has exports that are all related to a single purpose. A package that exports both HTTP handlers and database queries is not cohesive. It should be split.

### Proxy metric: connected export clusters

For each pair of exports, check if they share any internal dependencies. If the exports form two or more disjoint clusters (groups of exports that share no internal dependencies with each other), the package should be split.

### Analysis script

```js
#!/usr/bin/env node
// scripts/cohesion-analysis.mjs
//
// Analyzes export cohesion for each package in the monorepo.
// Uses dependency-cruiser JSON output to build internal dependency graphs.
//
// Usage:
//   pnpm dep:json
//   node scripts/cohesion-analysis.mjs reports/dependency-data.json

import { readFileSync } from "node:fs";
import { resolve, relative } from "node:path";

const inputPath = process.argv[2];
if (!inputPath) {
  console.error("Usage: node scripts/cohesion-analysis.mjs <dependency-cruiser-json>");
  process.exit(1);
}

const raw = JSON.parse(readFileSync(resolve(inputPath), "utf-8"));
const modules = raw.modules || [];

// ─────────────────────────────────────────────────────────
// Build per-package internal dependency graphs
// ─────────────────────────────────────────────────────────

function getPackageRoot(filePath) {
  const match = filePath.match(/^(apps|packages)\/[^/]+/);
  return match ? match[0] : null;
}

// For each package, find its index/barrel exports and their dependency trees
const packageData = new Map();

for (const mod of modules) {
  const pkgRoot = getPackageRoot(mod.source);
  if (!pkgRoot) continue;

  if (!packageData.has(pkgRoot)) {
    packageData.set(pkgRoot, { modules: new Map(), exports: [] });
  }

  const pkg = packageData.get(pkgRoot);
  const internalDeps = (mod.dependencies || [])
    .filter((d) => d.resolved.startsWith(pkgRoot + "/"))
    .map((d) => d.resolved);

  pkg.modules.set(mod.source, {
    source: mod.source,
    internalDeps,
  });

  // Identify exports: files that re-export from index.ts or are the index themselves
  const isBarrel =
    mod.source.endsWith("/index.ts") || mod.source.endsWith("/index.tsx");

  if (isBarrel && mod.source.split("/").length <= 4) {
    // This is a top-level barrel -- its imports are the package's exports
    for (const dep of internalDeps) {
      pkg.exports.push(dep);
    }
  }
}

// ─────────────────────────────────────────────────────────
// Compute transitive dependency sets for each export
// ─────────────────────────────────────────────────────────

function getTransitiveDeps(pkgModules, startModule, visited = new Set()) {
  if (visited.has(startModule)) return visited;
  visited.add(startModule);

  const mod = pkgModules.get(startModule);
  if (!mod) return visited;

  for (const dep of mod.internalDeps) {
    getTransitiveDeps(pkgModules, dep, visited);
  }
  return visited;
}

// ─────────────────────────────────────────────────────────
// Union-Find for clustering exports by shared dependencies
// ─────────────────────────────────────────────────────────

class UnionFind {
  constructor(elements) {
    this.parent = new Map();
    this.rank = new Map();
    for (const e of elements) {
      this.parent.set(e, e);
      this.rank.set(e, 0);
    }
  }

  find(x) {
    if (this.parent.get(x) !== x) {
      this.parent.set(x, this.find(this.parent.get(x)));
    }
    return this.parent.get(x);
  }

  union(x, y) {
    const rootX = this.find(x);
    const rootY = this.find(y);
    if (rootX === rootY) return;

    const rankX = this.rank.get(rootX);
    const rankY = this.rank.get(rootY);
    if (rankX < rankY) {
      this.parent.set(rootX, rootY);
    } else if (rankX > rankY) {
      this.parent.set(rootY, rootX);
    } else {
      this.parent.set(rootY, rootX);
      this.rank.set(rootX, rankX + 1);
    }
  }

  clusters() {
    const groups = new Map();
    for (const [element] of this.parent) {
      const root = this.find(element);
      if (!groups.has(root)) groups.set(root, []);
      groups.get(root).push(element);
    }
    return [...groups.values()];
  }
}

// ─────────────────────────────────────────────────────────
// Analyze each package
// ─────────────────────────────────────────────────────────

console.log("\n=== Package Cohesion Analysis ===\n");

let hasWarnings = false;
const results = [];

for (const [pkgRoot, pkg] of packageData) {
  if (pkg.exports.length < 2) continue; // Need at least 2 exports to analyze

  // Compute transitive deps for each export
  const exportDeps = new Map();
  for (const exp of pkg.exports) {
    exportDeps.set(exp, getTransitiveDeps(pkg.modules, exp));
  }

  // Cluster exports that share internal dependencies
  const uf = new UnionFind(pkg.exports);

  for (let i = 0; i < pkg.exports.length; i++) {
    for (let j = i + 1; j < pkg.exports.length; j++) {
      const depsA = exportDeps.get(pkg.exports[i]);
      const depsB = exportDeps.get(pkg.exports[j]);

      // Check if they share any internal dependency
      for (const d of depsA) {
        if (depsB.has(d)) {
          uf.union(pkg.exports[i], pkg.exports[j]);
          break;
        }
      }
    }
  }

  const clusters = uf.clusters();
  const status =
    clusters.length === 1
      ? "cohesive"
      : `${clusters.length} disjoint clusters`;

  if (clusters.length > 1) {
    hasWarnings = true;
  }

  results.push({
    package: pkgRoot,
    exports: pkg.exports.length,
    clusters: clusters.length,
    status,
    clusterDetails:
      clusters.length > 1
        ? clusters.map((c) =>
            c.map((f) => relative(pkgRoot, f))
          )
        : undefined,
  });
}

// Output table
console.log("| Package | Exports | Clusters | Status |");
console.log("|---------|---------|----------|--------|");
for (const r of results.sort((a, b) => b.clusters - a.clusters)) {
  console.log(`| ${r.package} | ${r.exports} | ${r.clusters} | ${r.status} |`);
}

// Detail for packages with multiple clusters
for (const r of results.filter((r) => r.clusters > 1)) {
  console.log(`\n--- ${r.package} (${r.clusters} clusters) ---`);
  for (let i = 0; i < r.clusterDetails.length; i++) {
    console.log(`  Cluster ${i + 1}:`);
    for (const f of r.clusterDetails[i]) {
      console.log(`    ${f}`);
    }
  }
  console.log(
    `  Consider splitting into ${r.clusters} packages.`
  );
}

if (hasWarnings) {
  console.log("\nWARNING: packages with low cohesion detected.");
}
```

### Interpreting results

A cohesive package shows 1 cluster. A package with 2+ clusters contains groups of exports that have no shared internal dependencies -- they are effectively separate libraries bundled together.

This is a warning, not a hard failure. Some packages intentionally bundle related-but-independent utilities (e.g., a `utils` package). But if `core-domain` shows 3 disjoint clusters, that is a strong signal it should be split.

---

## 6. Workspace Dependency Health Dashboard

A script that generates a markdown health report for the entire monorepo.

```js
#!/usr/bin/env node
// scripts/health-dashboard.mjs
//
// Generates a markdown health report for the monorepo.
//
// Usage:
//   pnpm dep:json
//   node scripts/health-dashboard.mjs reports/dependency-data.json > reports/health-report.md

import { readFileSync, readdirSync, existsSync } from "node:fs";
import { resolve, join } from "node:path";

const inputPath = process.argv[2];
if (!inputPath) {
  console.error("Usage: node scripts/health-dashboard.mjs <dependency-cruiser-json>");
  process.exit(1);
}

const raw = JSON.parse(readFileSync(resolve(inputPath), "utf-8"));
const modules = raw.modules || [];

// ─────────────────────────────────────────────────────────
// Reuse metric computation from dep-metrics
// ─────────────────────────────────────────────────────────

function getPackageName(filePath) {
  const match = filePath.match(/^(apps|packages)\/([^/]+)/);
  return match ? `${match[1]}/${match[2]}` : null;
}

const packageModules = new Map();
const packageFanOut = new Map();
const packageFanIn = new Map();
let circularCount = 0;
let orphanCount = 0;

for (const mod of modules) {
  const pkg = getPackageName(mod.source);
  if (!pkg) continue;

  if (!packageModules.has(pkg)) {
    packageModules.set(pkg, new Set());
    packageFanOut.set(pkg, new Set());
    packageFanIn.set(pkg, new Set());
  }
  packageModules.get(pkg).add(mod.source);

  if (mod.orphan) orphanCount++;

  for (const dep of mod.dependencies || []) {
    if (dep.circular) circularCount++;

    const depPkg = getPackageName(dep.resolved);
    if (depPkg && depPkg !== pkg) {
      packageFanOut.get(pkg).add(depPkg);
      if (!packageFanIn.has(depPkg)) packageFanIn.set(depPkg, new Set());
      packageFanIn.get(depPkg).add(pkg);
    }
  }
}

function computeMaxDepth(pkg, visited = new Set()) {
  if (visited.has(pkg)) return 0;
  visited.add(pkg);
  const deps = packageFanOut.get(pkg);
  if (!deps || deps.size === 0) return 0;
  let max = 0;
  for (const dep of deps) {
    max = Math.max(max, computeMaxDepth(dep, visited));
  }
  return max + 1;
}

// ─────────────────────────────────────────────────────────
// Count exports per package (from package.json exports field)
// ─────────────────────────────────────────────────────────

function countExports(pkgDir) {
  const pkgJsonPath = join(pkgDir, "package.json");
  if (!existsSync(pkgJsonPath)) return "?";
  try {
    const pkgJson = JSON.parse(readFileSync(pkgJsonPath, "utf-8"));
    if (pkgJson.exports) {
      return Object.keys(pkgJson.exports).length;
    }
    return pkgJson.main ? 1 : 0;
  } catch {
    return "?";
  }
}

// ─────────────────────────────────────────────────────────
// Generate markdown
// ─────────────────────────────────────────────────────────

const now = new Date().toISOString().split("T")[0];
const lines = [];

lines.push(`# Workspace Health Report`);
lines.push(``);
lines.push(`Generated: ${now}`);
lines.push(``);
lines.push(`## Summary`);
lines.push(``);
lines.push(`- **Packages:** ${packageModules.size}`);
lines.push(`- **Total modules:** ${modules.length}`);
lines.push(`- **Circular dependencies:** ${circularCount}`);
lines.push(`- **Orphan modules:** ${orphanCount}`);
lines.push(``);
lines.push(`## Package Metrics`);
lines.push(``);
lines.push(
  `| Package | Exports | Modules | Fan-in | Fan-out | Depth | Instability | Status |`
);
lines.push(
  `|---------|---------|---------|--------|---------|-------|-------------|--------|`
);

const rows = [];
for (const [pkg] of packageModules) {
  const fo = packageFanOut.get(pkg)?.size || 0;
  const fi = packageFanIn.get(pkg)?.size || 0;
  const instability = fo + fi === 0 ? 0 : fo / (fo + fi);
  const depth = computeMaxDepth(pkg);
  const moduleCount = packageModules.get(pkg)?.size || 0;
  const exports = countExports(pkg);
  const isApp = pkg.startsWith("apps/");

  let status = "ok";
  if (depth > (isApp ? 6 : 3)) {
    status = "depth exceeded";
  } else if (instability < 0.2 && moduleCount > 10) {
    status = "rigid foundation";
  } else if (instability > 0.8 && fi > 3) {
    status = "unstable but depended on";
  } else if (isApp && instability < 0.5) {
    status = "app should be unstable";
  } else if (!isApp && fi === 0 && fo === 0) {
    status = "isolated";
  }

  rows.push({
    pkg,
    exports,
    moduleCount,
    fi,
    fo,
    depth,
    instability: instability.toFixed(2),
    status,
  });
}

for (const r of rows.sort((a, b) => a.pkg.localeCompare(b.pkg))) {
  lines.push(
    `| ${r.pkg} | ${r.exports} | ${r.moduleCount} | ${r.fi} | ${r.fo} | ${r.depth} | ${r.instability} | ${r.status} |`
  );
}

lines.push(``);
lines.push(`## Dependency Direction`);
lines.push(``);
lines.push(`Packages listed with their dependents (who imports them) and dependencies (who they import).`);
lines.push(``);

for (const [pkg] of [...packageModules].sort(([a], [b]) => a.localeCompare(b))) {
  const dependents = [...(packageFanIn.get(pkg) || [])].sort();
  const dependencies = [...(packageFanOut.get(pkg) || [])].sort();

  if (dependents.length === 0 && dependencies.length === 0) continue;

  lines.push(`### ${pkg}`);
  if (dependents.length > 0) {
    lines.push(`- **Depended on by:** ${dependents.join(", ")}`);
  }
  if (dependencies.length > 0) {
    lines.push(`- **Depends on:** ${dependencies.join(", ")}`);
  }
  lines.push(``);
}

console.log(lines.join("\n"));
```

### Run weekly in CI

```yaml
# .github/workflows/health-report.yml
name: Health report

on:
  schedule:
    - cron: "0 9 * * 1" # Every Monday at 9am UTC
  workflow_dispatch: # Allow manual trigger

jobs:
  report:
    runs-on: ubuntu-latest
    permissions:
      discussions: write
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      - name: Generate health report
        run: |
          mkdir -p reports
          pnpm dep:json
          node scripts/health-dashboard.mjs reports/dependency-data.json > reports/health-report.md

      - uses: actions/upload-artifact@v4
        with:
          name: health-report
          path: reports/health-report.md
          retention-days: 90

      # Optional: post to a GitHub Discussion
      - name: Post to GitHub Discussions
        if: github.event_name == 'schedule'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const body = fs.readFileSync('reports/health-report.md', 'utf-8');

            // Find or create "Architecture Health" discussion category
            // This requires the discussion category to already exist
            await github.rest.repos.createDispatchEvent({
              owner: context.repo.owner,
              repo: context.repo.repo,
              event_type: 'health-report',
              client_payload: { body: body.slice(0, 60000) },
            });
```

---

## 7. Detecting Architecture Erosion Over Time

Track metrics across commits. Store snapshots in the repo. CI compares current metrics against the last known good state.

### Snapshot management

After each successful main build, save the current metrics as the baseline:

```yaml
    - name: Update metrics snapshot
      if: github.ref == 'refs/heads/main'
      run: |
        mkdir -p reports
        pnpm dep:json
        node scripts/dep-metrics.mjs reports/dependency-data.json
        cp reports/dep-metrics-current.json reports/dep-metrics-snapshot.json

    - name: Commit snapshot
      if: github.ref == 'refs/heads/main'
      run: |
        git config user.name "github-actions[bot]"
        git config user.email "github-actions[bot]@users.noreply.github.com"
        git add reports/dep-metrics-snapshot.json
        git diff --cached --quiet || git commit -m "chore: update dependency metrics snapshot"
        git push
```

### PR comparison

On pull requests, the `dep-metrics.mjs` script automatically compares against the committed snapshot (the `existsSync(snapshotPath)` block in the script above). It fails if:

- A new circular dependency appears
- A package's fan-out increases by more than 3 in a single PR
- The total number of cross-package dependencies increases by more than 10%

These thresholds are configured in the `THRESHOLDS` object at the top of `dep-metrics.mjs`. Adjust them to match your codebase's growth rate.

### Erosion detection script (standalone)

For teams that want a dedicated erosion check separate from the full metrics script:

```bash
#!/usr/bin/env bash
# scripts/check-erosion.sh
#
# Compares current dependency metrics against the last snapshot.
# Fails if architecture has degraded.
#
# Usage: bash scripts/check-erosion.sh

set -euo pipefail

SNAPSHOT="reports/dep-metrics-snapshot.json"
CURRENT="reports/dep-metrics-current.json"

if [ ! -f "$SNAPSHOT" ]; then
  echo "No snapshot found at $SNAPSHOT. Generating baseline."
  mkdir -p reports
  pnpm dep:json
  node scripts/dep-metrics.mjs reports/dependency-data.json
  cp "$CURRENT" "$SNAPSHOT"
  echo "Baseline created. Commit $SNAPSHOT to the repo."
  exit 0
fi

# Generate current metrics
mkdir -p reports
pnpm dep:json
node scripts/dep-metrics.mjs reports/dependency-data.json

echo ""
echo "=== Erosion Check ==="

# Compare circular dependencies
PREV_CIRCULAR=$(jq '.circularCount' "$SNAPSHOT")
CURR_CIRCULAR=$(jq '.circularCount' "$CURRENT")

if [ "$CURR_CIRCULAR" -gt "$PREV_CIRCULAR" ]; then
  echo "ERROR: Circular dependencies increased from $PREV_CIRCULAR to $CURR_CIRCULAR"
  exit 1
fi

# Compare orphan count
PREV_ORPHANS=$(jq '.orphanCount' "$SNAPSHOT")
CURR_ORPHANS=$(jq '.orphanCount' "$CURRENT")

if [ "$CURR_ORPHANS" -gt "$PREV_ORPHANS" ]; then
  echo "WARNING: Orphan modules increased from $PREV_ORPHANS to $CURR_ORPHANS"
fi

echo "Circular: $PREV_CIRCULAR -> $CURR_CIRCULAR"
echo "Orphans: $PREV_ORPHANS -> $CURR_ORPHANS"
echo ""
echo "Erosion check passed."
```

---

## 8. Integration into the Three Layers

Architecture analysis is too slow for pre-commit (it needs the full dependency graph). Here is where each tool fits.

### Pre-commit: none

Architecture analysis requires parsing the entire module graph. This takes 5-30 seconds depending on codebase size. Too slow for commit-time feedback.

### Pre-push

Add dependency rule checking to the pre-push hook. Rule validation (without graph generation) is fast -- typically under 10 seconds.

```bash
# Add to .husky/pre-push after other gates
info "Gate: Dependency rules"
pnpm dep:check || {
  fail "Dependency rule violations detected"
  exit 1
}
pass "Dependency rules"
```

### CI

CI runs the full suite:

```yaml
  architecture:
    name: Architecture analysis
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      - name: Install Graphviz
        run: sudo apt-get install -y graphviz

      - name: Dependency rule check
        run: pnpm dep:check

      - name: Generate graphs and metrics
        run: |
          mkdir -p reports
          pnpm dep:json
          pnpm dep:graph:archi
          node scripts/dep-metrics.mjs reports/dependency-data.json

      - name: Build and check API surface
        run: |
          pnpm build
          pnpm api:check

      - name: Cohesion analysis
        run: node scripts/cohesion-analysis.mjs reports/dependency-data.json
        continue-on-error: true

      - uses: actions/upload-artifact@v4
        with:
          name: architecture-reports
          path: |
            reports/architecture-graph.svg
            reports/dep-metrics-current.json
            reports/dependency-data.json
          retention-days: 30
        if: always()
```

### Summary table

| Tool | Pre-commit | Pre-push | CI |
|------|-----------|----------|-----|
| dependency-cruiser (rules) | -- | Yes | Yes |
| dependency-cruiser (graph) | -- | -- | Yes |
| dep-metrics.mjs | -- | -- | Yes |
| api-extractor | -- | -- | Yes |
| cohesion-analysis.mjs | -- | -- | Yes (warning only) |
| health-dashboard.mjs | -- | -- | Weekly |

---

## 9. Language-Specific Equivalents

The concepts (graph analysis, API surface tracking, cohesion metrics, erosion detection) apply to every language. The tools differ.

### Python

| Concern | Tool | Notes |
|---------|------|-------|
| Graph visualization | `pydeps` | Generates SVG from import graph. `pip install pydeps` |
| Boundary rules | `import-linter` | Define contracts in `setup.cfg` or `.importlinter`. Forbid cycles, enforce layers. |
| Dead code | `vulture` | Finds unused functions, variables, imports. |
| API surface | `griffe` | Extracts API from Python packages. Use with `mkdocstrings` for tracking. |
| Dependency health | `pip-audit` | Checks for known vulnerabilities in dependencies. |

```ini
# .importlinter (example)
[importlinter]
root_package = myapp

[importlinter:contract:layers]
name = Architecture layers
type = layers
layers =
    myapp.api
    myapp.domain
    myapp.infrastructure
```

### Go

| Concern | Tool | Notes |
|---------|------|-------|
| Layer rules | `go-arch-lint` | Define allowed imports per package in YAML. |
| Graph visualization | `godepgraph` | Generates Graphviz DOT output. |
| Unused dependencies | `go mod tidy` | Built-in. Also: `depguard` for import restrictions. |
| Dependency health | `govulncheck` | Official Go vulnerability scanner. |
| Dead code | `deadcode` | From `golang.org/x/tools`. |

```yaml
# .go-arch-lint.yml (example)
allow:
  depOnAnyVendor: false
deps:
  internal/api:
    canImport:
      - internal/domain
      - internal/service
  internal/domain:
    canImport: []
  internal/service:
    canImport:
      - internal/domain
      - internal/repository
```

### Rust

| Concern | Tool | Notes |
|---------|------|-------|
| Structure visualization | `cargo-modules` | Shows module tree and dependency graph. |
| Unused dependencies | `cargo-udeps` | Finds crates declared but not used. |
| Dependency rules | `cargo-deny` | License checking, vulnerability auditing, ban specific crates. |
| Duplicate dependencies | `cargo-deny` | Detects multiple versions of the same crate. |
| Dead code | Built-in | `#[warn(dead_code)]` is on by default. |

```toml
# deny.toml (example)
[bans]
multiple-versions = "deny"
wildcards = "deny"
highlight = "all"

[[bans.deny]]
name = "openssl"
wrappers = ["openssl-sys"]

[advisories]
vulnerability = "deny"
unmaintained = "warn"
```

### Java / Kotlin

| Concern | Tool | Notes |
|---------|------|-------|
| Architecture tests | ArchUnit | Write architecture rules as unit tests. Enforce layer dependencies, naming conventions, cycle-freedom. |
| Metrics | JDepend | Computes instability, abstractness, distance from main sequence per package. |
| Graph visualization | Sonargraph | Commercial. Also: `jdeps` (built into JDK) for module dependencies. |
| API surface | `japicmp` | Compares two JARs and reports binary/source compatibility changes. |

```java
// ArchUnit example
@AnalyzeClasses(packages = "com.example")
public class ArchitectureTest {

    @ArchTest
    static final ArchRule noCircularDependencies =
        slices().matching("com.example.(*)..")
            .should().beFreeOfCycles();

    @ArchTest
    static final ArchRule layerDependencies =
        layeredArchitecture()
            .consideringAllDependencies()
            .layer("API").definedBy("..api..")
            .layer("Service").definedBy("..service..")
            .layer("Repository").definedBy("..repository..")
            .whereLayer("API").mayNotBeAccessedByAnyLayer()
            .whereLayer("Service").mayOnlyBeAccessedByLayers("API")
            .whereLayer("Repository").mayOnlyBeAccessedByLayers("Service");
}
```

---

## 10. Quick Reference

### New project setup checklist

```bash
# 1. Install dependency-cruiser
pnpm add -D dependency-cruiser

# 2. Create config
# Copy .dependency-cruiser.cjs from Section 1

# 3. Create reports directory
mkdir -p reports && echo "reports/" >> .gitignore

# 4. Add scripts to package.json
# dep:check, dep:graph, dep:graph:archi, dep:html, dep:json

# 5. Create metric scripts
# scripts/dep-metrics.mjs (Section 3)
# scripts/cohesion-analysis.mjs (Section 5)
# scripts/health-dashboard.mjs (Section 6)

# 6. (Optional) Install api-extractor for publishable packages
pnpm add -D @microsoft/api-extractor

# 7. Add to pre-push hook
# pnpm dep:check

# 8. Add CI jobs
# architecture (Section 8)
# health-report (Section 6, weekly)

# 9. Generate initial snapshot
pnpm dep:json && node scripts/dep-metrics.mjs reports/dependency-data.json
cp reports/dep-metrics-current.json reports/dep-metrics-snapshot.json
git add reports/dep-metrics-snapshot.json
```

### Commands at a glance

| Command | What it does | When to run |
|---------|-------------|-------------|
| `pnpm dep:check` | Validate dependency rules (no cycles, no app-to-app, etc.) | Pre-push, CI |
| `pnpm dep:graph` | Generate full module-level SVG | On demand |
| `pnpm dep:graph:archi` | Generate package-level SVG | CI (upload as artifact) |
| `pnpm dep:json` | Generate raw JSON for scripts | Before running metric scripts |
| `node scripts/dep-metrics.mjs` | Compute and enforce structural metrics | CI |
| `node scripts/cohesion-analysis.mjs` | Analyze export cohesion per package | CI (warning only) |
| `node scripts/health-dashboard.mjs` | Generate markdown health report | Weekly CI |
| `pnpm api:extract` | Update .api.md files locally | After changing public API |
| `pnpm api:check` | Verify .api.md files are up to date | CI |
