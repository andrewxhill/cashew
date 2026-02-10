# ESLint Architecture for TypeScript Monorepos (Flat Config)

This reference covers setting up ESLint with flat config (`eslint.config.mjs`) in a TypeScript monorepo. It is based on a production configuration running 17 plugin categories across dozens of packages and apps.

## Table of Contents

1. [Shared ESLint Config Package](#1-shared-eslint-config-package)
2. [Base Config (Strict Mode)](#2-base-config-strict-mode)
3. [Architecture Boundary Rules](#3-architecture-boundary-rules)
4. [Custom ESLint Rules](#4-custom-eslint-rules)
5. [Per-Package Configs](#5-per-package-configs)
6. [Testing Config](#6-testing-config)
7. [Dependency-Cruiser Integration](#7-dependency-cruiser-integration)
8. [Export Surface Limits](#8-export-surface-limits)

---

## 1. Shared ESLint Config Package

### Package Structure

```
packages/eslint-config/
  base.mjs          # Minimal config (TS-ESLint only, no type-checked rules)
  base.js           # Strict config (all 17 plugins, type-checked)
  library.mjs       # Extends strict base, disables boundary rules
  nextjs.js         # Extends strict base + React/Next.js/A11y plugins
  testing.js        # Vitest + Testing Library rules for test files
  index.js          # Re-exports + default combo (nextjs + testing)
  rules/
    no-direct-table-imports.js   # Custom: repository pattern enforcement
    no-local-redis-keys.js       # Custom: Redis key centralization
  package.json
  tsconfig.eslint.json
```

### package.json

```json
{
  "name": "@scope/eslint-config",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "main": "./index.js",
  "exports": {
    ".": "./index.js",
    "./base": "./base.js",
    "./nextjs": "./nextjs.js",
    "./testing": "./testing.js",
    "./library": "./library.mjs"
  },
  "dependencies": {
    "@eslint/js": "^9.0.0",
    "@next/eslint-plugin-next": "^15.0.0",
    "@typescript-eslint/eslint-plugin": "^8.0.0",
    "@typescript-eslint/parser": "^8.0.0",
    "eslint-config-prettier": "^10.0.0",
    "eslint-plugin-boundaries": "^5.0.0",
    "eslint-plugin-eslint-comments": "^3.2.0",
    "eslint-plugin-functional": "^7.0.0",
    "eslint-plugin-import-x": "^4.0.0",
    "eslint-plugin-jsdoc": "^50.0.0",
    "eslint-plugin-jsx-a11y": "^6.10.0",
    "eslint-plugin-no-secrets": "^1.1.0",
    "eslint-plugin-promise": "^7.0.0",
    "eslint-plugin-react": "^7.37.0",
    "eslint-plugin-react-hooks": "^5.0.0",
    "eslint-plugin-security": "^3.0.0",
    "eslint-plugin-sonarjs": "^3.0.0",
    "eslint-plugin-testing-library": "^7.0.0",
    "eslint-plugin-unicorn": "^56.0.0",
    "eslint-plugin-vitest": "^0.5.0",
    "eslint-import-resolver-typescript": "^4.0.0",
    "globals": "^15.0.0",
    "typescript-eslint": "^8.0.0"
  },
  "peerDependencies": {
    "eslint": "^9.0.0",
    "typescript": "^5.0.0"
  }
}
```

### 17 Plugin Categories

| # | Plugin | Purpose |
|---|--------|---------|
| 1 | `@eslint/js` | ESLint core recommended rules |
| 2 | `typescript-eslint` | TypeScript strict + stylistic type-checked |
| 3 | `eslint-plugin-import-x` | Import ordering, cycle detection, deduplication |
| 4 | `eslint-plugin-unicorn` | Modern JS idioms, filename conventions |
| 5 | `eslint-plugin-sonarjs` | Cognitive complexity, duplicate strings |
| 6 | `eslint-plugin-security` | Object injection, timing attacks, eval |
| 7 | `eslint-plugin-no-secrets` | Entropy-based secret detection |
| 8 | `eslint-plugin-promise` | Promise anti-pattern detection |
| 9 | `eslint-plugin-jsdoc` | JSDoc enforcement on public API |
| 10 | `eslint-plugin-boundaries` | Architecture layer enforcement |
| 11 | `eslint-plugin-functional` | Immutability rules (aspirational) |
| 12 | `eslint-plugin-eslint-comments` | Require descriptions on disable directives |
| 13 | `eslint-config-prettier` | Disables formatting rules that conflict with Prettier |
| 14 | `eslint-plugin-react` | React best practices (nextjs config) |
| 15 | `eslint-plugin-react-hooks` | Rules of hooks, exhaustive deps (nextjs config) |
| 16 | `eslint-plugin-jsx-a11y` | Accessibility enforcement (nextjs config) |
| 17 | `@next/eslint-plugin-next` | Next.js framework rules (nextjs config) |

Plus two test-only plugins loaded in `testing.js`:
- `eslint-plugin-vitest` - Test quality enforcement
- `eslint-plugin-testing-library` - Testing Library best practices

### index.js (Default Export)

The default export combines nextjs and testing configs for apps that need both:

```js
// index.js
export { default as base } from "./base.js";
export { default as nextjs } from "./nextjs.js";
export { default as testing } from "./testing.js";

import nextjsConfig from "./nextjs.js";
import testingConfig from "./testing.js";

export default [...nextjsConfig, ...testingConfig];
```

---

## 2. Base Config (Strict Mode)

### base.mjs -- Minimal Config (No Type-Checked Rules)

Use this when you need fast linting without a TypeScript project reference (e.g., config files, scripts). It uses `@typescript-eslint/parser` directly without `projectService`.

```js
// base.mjs
import { defineConfig, globalIgnores } from "eslint/config";
import tseslint from "@typescript-eslint/eslint-plugin";
import tsparser from "@typescript-eslint/parser";

const baseConfig = defineConfig([
  {
    files: ["**/*.ts", "**/*.tsx", "**/*.mts"],
    languageOptions: {
      parser: tsparser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
      },
    },
    plugins: {
      "@typescript-eslint": tseslint,
    },
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/explicit-function-return-type": "error",
      "@typescript-eslint/explicit-module-boundary-types": "error",
      "@typescript-eslint/no-non-null-assertion": "error",
      "no-console": ["error", { allow: ["warn", "error"] }],
      "no-debugger": "error",
      "no-alert": "error",
      "prefer-const": "error",
      "no-var": "error",
      eqeqeq: ["error", "always"],
      curly: ["error", "all"],
    },
  },
  globalIgnores(["dist/**", "node_modules/**", "*.js", "*.mjs", "*.cjs"]),
]);

export default baseConfig;
```

### base.js -- Strict Config (Full 17-Plugin Suite)

This is the comprehensive config that all TypeScript source files use. It enables type-checked rules via `projectService` and loads all quality/security plugins.

```js
// base.js
import eslint from "@eslint/js";
import prettierConfig from "eslint-config-prettier";
import fs from "node:fs";
import path from "node:path";

import boundariesPlugin from "eslint-plugin-boundaries";
import eslintCommentsPlugin from "eslint-plugin-eslint-comments";
import functionalPlugin from "eslint-plugin-functional";
import importPlugin from "eslint-plugin-import-x";
import jsdocPlugin from "eslint-plugin-jsdoc";
import noSecretsPlugin from "eslint-plugin-no-secrets";
import promisePlugin from "eslint-plugin-promise";
import securityPlugin from "eslint-plugin-security";
import sonarjsPlugin from "eslint-plugin-sonarjs";
import unicornPlugin from "eslint-plugin-unicorn";
import globals from "globals";
import tseslint from "typescript-eslint";

// Custom rules (see Section 4)
import { noDirectTableImportsRule } from "./rules/no-direct-table-imports.js";
import { noLocalRedisKeysRule } from "./rules/no-local-redis-keys.js";

const boundaryElements = [
  { type: "app", pattern: "apps/*", mode: "folder" },
  { type: "package", pattern: "packages/*", mode: "folder" },
  { type: "types-barrel", pattern: "**/types/index.ts" },
  { type: "types-internal", pattern: "**/types/*.ts" },
];

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  {
    ignores: ["**/*.snap"],
  },
  // --- Language Options ---
  {
    languageOptions: {
      globals: {
        ...globals.node,
        ...globals.es2022,
      },
      parserOptions: (() => {
        // Dynamic project resolution: prefer tsconfig.eslint.json, fall back to tsconfig.json
        // Use ESLINT_USE_TS_PROJECT=true to force project mode (faster for single-package linting)
        // Use ESLINT_USE_TS_PROJECT=packages to enable only for packages/ subdirectories
        const cwd = process.cwd();
        const envMode = process.env.ESLINT_USE_TS_PROJECT;
        const isPackage = cwd.includes(`${path.sep}packages${path.sep}`);
        const useProject =
          envMode === "true" || (envMode === "packages" && isPackage);

        if (!useProject) {
          return { projectService: true };
        }

        const findProject = (startDir) => {
          let currentDir = startDir;
          while (true) {
            const eslintCandidate = path.join(
              currentDir,
              "tsconfig.eslint.json"
            );
            if (fs.existsSync(eslintCandidate)) return eslintCandidate;
            const tsconfigCandidate = path.join(currentDir, "tsconfig.json");
            if (fs.existsSync(tsconfigCandidate)) return tsconfigCandidate;
            const parentDir = path.dirname(currentDir);
            if (parentDir === currentDir) return undefined;
            currentDir = parentDir;
          }
        };

        const localEslintProject = path.resolve(cwd, "tsconfig.eslint.json");
        const localTsconfigProject = path.resolve(cwd, "tsconfig.json");
        const project = fs.existsSync(localEslintProject)
          ? localEslintProject
          : fs.existsSync(localTsconfigProject)
            ? localTsconfigProject
            : findProject(cwd);

        return {
          projectService: false,
          project: project ? [project] : undefined,
          tsconfigRootDir: project ? path.dirname(project) : process.cwd(),
        };
      })(),
    },
  },
  // --- Main Rules Block (all TS files) ---
  {
    files: ["**/*.ts", "**/*.tsx"],
    plugins: {
      "import-x": importPlugin,
      unicorn: unicornPlugin,
      sonarjs: sonarjsPlugin,
      security: securityPlugin,
      "no-secrets": noSecretsPlugin,
      promise: promisePlugin,
      jsdoc: jsdocPlugin,
      boundaries: boundariesPlugin,
      functional: functionalPlugin,
      "eslint-comments": eslintCommentsPlugin,
      // Custom rules registered under a project-specific namespace
      "my-project": {
        rules: {
          "no-direct-table-imports": noDirectTableImportsRule,
          "no-local-redis-keys": noLocalRedisKeysRule,
        },
      },
    },
    settings: {
      "boundaries/elements": boundaryElements,
      "boundaries/ignore": ["**/*.test.ts", "**/*.spec.ts"],
      "import-x/resolver": {
        typescript: true,
      },
    },
    rules: {
      // ===================================================
      // TypeScript Strict Rules
      // ===================================================
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/explicit-function-return-type": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-misused-promises": "error",
      "@typescript-eslint/await-thenable": "error",
      "@typescript-eslint/no-unnecessary-condition": "error",
      "@typescript-eslint/prefer-nullish-coalescing": "error",
      "@typescript-eslint/prefer-optional-chain": "error",
      "@typescript-eslint/no-non-null-assertion": "error",
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports" },
      ],
      "@typescript-eslint/consistent-type-definitions": ["error", "interface"],
      "@typescript-eslint/switch-exhaustiveness-check": [
        "error",
        {
          allowDefaultCaseForExhaustiveSwitch: false,
          requireDefaultForNonUnion: true,
        },
      ],

      // ===================================================
      // Import Ordering (import-x plugin)
      // ===================================================
      // Order: builtin -> external -> @scope/* (workspace) -> @/* (app-level) -> parent -> sibling -> index
      "import-x/first": "error",
      "import-x/order": [
        "error",
        {
          groups: [
            "builtin",
            "external",
            "internal",
            "parent",
            "sibling",
            "index",
          ],
          pathGroups: [
            {
              pattern: "@scope/**",
              group: "internal",
              position: "before",
            },
            {
              pattern: "@/**",
              group: "internal",
              position: "after",
            },
          ],
          pathGroupsExcludedImportTypes: ["internal"],
          "newlines-between": "always",
          alphabetize: { order: "asc", caseInsensitive: true },
        },
      ],
      "import-x/no-duplicates": "error",
      "import-x/no-cycle": "error",
      "import-x/no-self-import": "error",
      "import-x/no-useless-path-segments": "error",

      // ===================================================
      // Restricted Imports (enforce repository pattern)
      // ===================================================
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "drizzle-orm",
              message:
                "Import from @scope/database instead of drizzle-orm (allowed only in packages/database or tests).",
            },
          ],
          patterns: [
            {
              group: ["drizzle-orm"],
              message:
                "Import from @scope/database instead of drizzle-orm (allowed only in packages/database or tests).",
            },
          ],
        },
      ],

      // ===================================================
      // Unicorn Rules
      // ===================================================
      "unicorn/prefer-node-protocol": "error",
      "unicorn/prefer-module": "error",
      "unicorn/no-array-reduce": "error",
      "unicorn/no-null": "off",
      "unicorn/prevent-abbreviations": [
        "error",
        {
          replacements: {
            props: false,
            ref: false,
            params: false,
          },
        },
      ],
      "unicorn/filename-case": ["error", { case: "kebabCase" }],

      // ===================================================
      // SonarJS Code Quality
      // ===================================================
      "sonarjs/cognitive-complexity": ["error", 15],
      "sonarjs/no-duplicate-string": ["error", { threshold: 3 }],
      "sonarjs/no-identical-functions": "error",

      // ===================================================
      // Security Rules
      // ===================================================
      "security/detect-object-injection": "error",
      "security/detect-non-literal-regexp": "error",
      "security/detect-unsafe-regex": "error",
      "security/detect-buffer-noassert": "error",
      "security/detect-eval-with-expression": "error",
      "security/detect-no-csrf-before-method-override": "error",
      "security/detect-possible-timing-attacks": "error",
      "no-secrets/no-secrets": ["error", { tolerance: 4.5 }],

      // ===================================================
      // Promise Rules
      // ===================================================
      "promise/always-return": "error",
      "promise/no-return-wrap": "error",
      "promise/param-names": "error",
      "promise/catch-or-return": "error",
      "promise/no-nesting": "error",
      "promise/no-promise-in-callback": "error",
      "promise/no-callback-in-promise": "error",

      // ===================================================
      // JSDoc Rules
      // ===================================================
      "jsdoc/require-jsdoc": [
        "error",
        {
          publicOnly: true,
          require: {
            FunctionDeclaration: true,
            MethodDefinition: true,
            ClassDeclaration: true,
          },
        },
      ],
      "jsdoc/require-description": "error",
      "jsdoc/require-param-description": "error",
      "jsdoc/require-returns-description": "error",

      // ===================================================
      // Functional Programming Rules (aspirational)
      // ===================================================
      // Disabled: conflicts with practical patterns in API routes and
      // data transformation code. Re-enable when the codebase is ready.
      "functional/no-let": "off",
      "functional/prefer-readonly-type": "off",
      "functional/immutable-data": "off",

      // ===================================================
      // ESLint Comments Rules
      // ===================================================
      "eslint-comments/no-unused-disable": "error",
      "eslint-comments/no-unused-enable": "error",
      "eslint-comments/no-duplicate-disable": "error",
      "eslint-comments/require-description": [
        "error",
        { ignore: ["eslint-enable"] },
      ],

      // ===================================================
      // Architecture Boundaries (see Section 3)
      // ===================================================
      "boundaries/element-types": [
        "error",
        {
          default: "disallow",
          rules: [
            { from: "app", allow: ["package", "types-barrel"] },
            { from: "package", allow: ["package", "types-barrel"] },
            { from: "types-barrel", allow: ["types-internal"] },
          ],
        },
      ],
      "boundaries/no-unknown": "error",
      "boundaries/no-private": ["error", { allowUncles: false }],
      "import-x/no-internal-modules": [
        "error",
        {
          forbid: [
            "@scope/*/src/**",
            "@scope/**/types/*",
            "!@scope/**/types/index",
          ],
        },
      ],

      // ===================================================
      // Domain Type Protection (see Section 4)
      // ===================================================
      "no-restricted-syntax": [
        "warn",
        {
          selector:
            "TSTypeAliasDeclaration[id.name='Timeframe'], " +
            "TSTypeAliasDeclaration[id.name='SymbolId'], " +
            "TSInterfaceDeclaration[id.name='Candle'], " +
            "TSInterfaceDeclaration[id.name='Trade']",
          message:
            "Use canonical types from @scope/core-domain instead of redefining.",
        },
      ],

      // ===================================================
      // Custom Rules (see Section 4)
      // ===================================================
      "my-project/no-direct-table-imports": "error",
      "my-project/no-local-redis-keys": "error",

      // ===================================================
      // General Rules
      // ===================================================
      "no-console": "error",
      "no-debugger": "error",
      "no-alert": "error",
      "prefer-const": "error",
      "no-var": "error",
      eqeqeq: ["error", "always"],
      curly: ["error", "all"],
    },
  },
  // --- Overrides: allow drizzle-orm in database package and tests ---
  {
    files: [
      "**/*.test.*",
      "**/*.spec.*",
      "**/__tests__/**",
      "**/smoke-tests/**",
    ],
    rules: {
      "no-restricted-imports": "off",
    },
  },
  {
    files: ["packages/database/**"],
    rules: {
      "no-restricted-imports": "off",
    },
  },
  // --- Prettier must be last to disable conflicting formatting rules ---
  prettierConfig
);
```

### Key Design Decisions

**`projectService: true` vs `project` array.** The default uses `projectService: true` which lets typescript-eslint resolve projects automatically. Set `ESLINT_USE_TS_PROJECT=true` to force explicit project resolution for faster single-package runs (CI optimization).

**`tseslint.config()` helper.** This is the flat config equivalent of `extends`. It merges multiple config objects and handles the TypeScript parser setup. Always use it as the top-level wrapper.

**Prettier is last.** `eslint-config-prettier` must be the final config object. It disables all rules that conflict with Prettier formatting. If it is not last, formatting rules from later configs will re-enable conflicts.

---

## 3. Architecture Boundary Rules

Architecture boundaries prevent dependency violations between monorepo layers. They are enforced by `eslint-plugin-boundaries` combined with `import-x/no-internal-modules`.

### Element Type Definitions

```js
const boundaryElements = [
  { type: "app", pattern: "apps/*", mode: "folder" },
  { type: "package", pattern: "packages/*", mode: "folder" },
  { type: "types-barrel", pattern: "**/types/index.ts" },
  { type: "types-internal", pattern: "**/types/*.ts" },
];
```

### Boundary Rules

```js
// Settings (required by boundaries plugin)
settings: {
  "boundaries/elements": boundaryElements,
  "boundaries/ignore": ["**/*.test.ts", "**/*.spec.ts"],
},

// Rules
"boundaries/element-types": [
  "error",
  {
    default: "disallow",
    rules: [
      // Apps can import packages and type barrels (public API)
      { from: "app", allow: ["package", "types-barrel"] },
      // Packages can import other packages and type barrels
      { from: "package", allow: ["package", "types-barrel"] },
      // Type barrels aggregate internal type files
      { from: "types-barrel", allow: ["types-internal"] },
    ],
  },
],
"boundaries/no-unknown": "error",
"boundaries/no-private": ["error", { allowUncles: false }],
```

### Internal Module Protection

The `import-x/no-internal-modules` rule prevents reaching into package internals:

```js
"import-x/no-internal-modules": [
  "error",
  {
    forbid: [
      "@scope/*/src/**",           // Cannot reach into src/ of any package
      "@scope/**/types/*",         // Cannot import individual type files
      "!@scope/**/types/index",    // EXCEPT the type barrel (re-export index)
    ],
  },
],
```

### What the Boundaries Prevent

| Import | Allowed? | Why |
|--------|----------|-----|
| `app -> @scope/database` | Yes | Apps use packages |
| `app -> @scope/database/src/schema` | No | Internal module |
| `package -> package` | Yes | Packages compose |
| `app -> types/index.ts` | Yes | Type barrel is public |
| `app -> types/candle.ts` | No | Internal type file |
| Test files | Exempt | Tests may reach into internals |

### Excluding Tests from Boundary Checking

Tests regularly need to import internals for unit testing. The `boundaries/ignore` setting excludes test files:

```js
settings: {
  "boundaries/ignore": ["**/*.test.ts", "**/*.spec.ts"],
},
```

Additionally, per-package test overrides disable `import-x/no-internal-modules`:

```js
{
  files: ["**/__tests__/**/*.ts", "**/*.test.ts", "**/*.spec.ts"],
  rules: {
    "import-x/no-internal-modules": "off",
  },
},
```

---

## 4. Custom ESLint Rules

Custom rules are written as plain JavaScript ESM modules and registered as a local plugin in the base config.

### Registration Pattern

Custom rules are registered under a project-specific plugin namespace:

```js
plugins: {
  "my-project": {
    rules: {
      "no-direct-table-imports": noDirectTableImportsRule,
      "no-local-redis-keys": noLocalRedisKeysRule,
    },
  },
},
rules: {
  "my-project/no-direct-table-imports": "error",
  "my-project/no-local-redis-keys": "error",
},
```

### Example 1: no-direct-table-imports

Prevents importing database table schemas outside the `packages/database/` package. Enforces the repository pattern where all database queries go through repository methods.

```js
// rules/no-direct-table-imports.js

/**
 * ESLint rule that prevents importing table schemas outside packages/database/.
 * Enforces the repository pattern: all DB queries go through repository methods.
 */
export const noDirectTableImportsRule = {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow importing table schemas outside packages/database",
    },
  },
  create(context) {
    const filename = context.getFilename();
    const isInDatabasePackage = filename.includes("packages/database/");
    const isTestFile =
      /\.(test|spec|smoke)\.ts$/.test(filename) ||
      filename.includes("__tests__") ||
      filename.includes("e2e-tests/");

    // Allow in database package and tests
    if (isInDatabasePackage || isTestFile) {
      return {};
    }

    // Allowlist: exports from @scope/database that are NOT table schemas.
    // These are client utilities, query helpers, and repository factories.
    const ALLOWED_FROM_ROOT = new Set([
      // Client utilities
      "createDatabaseClient",
      "DatabaseClient",
      // Drizzle query helpers (re-exported for convenience)
      "sql",
      "eq",
      "and",
      "or",
      "gte",
      "lte",
      "lt",
      "gt",
      "desc",
      "asc",
      "inArray",
      "isNotNull",
      "isNull",
      "count",
      // Repository factories
      "createCandleRepository",
      "createAnnotationRepository",
      "createOrderbookRepository",
      "createTradeRepository",
      // Repository interfaces (types)
      "CandleRepository",
      "AnnotationRepository",
      "OrderbookRepository",
      "TradeRepository",
      // Entity types
      "OhlcvCandle",
      "NewOhlcvCandle",
      "Annotation",
      "NewAnnotation",
    ]);

    return {
      ImportDeclaration(node) {
        const source = String(node.source.value);
        const isDatabaseRoot = source === "@scope/database";
        const isDatabaseSchema = source === "@scope/database/schema";

        if (!isDatabaseRoot && !isDatabaseSchema) return;

        // Block ALL imports from /schema subpath
        if (isDatabaseSchema) {
          context.report({
            node,
            message:
              "Importing from '@scope/database/schema' is not allowed outside " +
              "packages/database/ and tests. Use repository methods instead.",
          });
          return;
        }

        // For root imports, only allow the safe utilities
        if (isDatabaseRoot) {
          for (const specifier of node.specifiers) {
            if (specifier.type === "ImportSpecifier") {
              const importedName = specifier.imported.name;
              if (!ALLOWED_FROM_ROOT.has(importedName)) {
                context.report({
                  node: specifier,
                  message:
                    `Import of '${importedName}' from '@scope/database' is not ` +
                    "allowed here. Use repository methods instead.",
                });
              }
            }
          }
        }
      },
    };
  },
};

export default noDirectTableImportsRule;
```

### Example 2: no-local-redis-keys

Prevents constructing Redis keys outside a centralized schema package. Detects both literal key patterns and function names that suggest local key construction.

```js
// rules/no-local-redis-keys.js

/**
 * ESLint rule that prevents local Redis key construction outside @scope/redis-schema.
 *
 * Detects:
 * 1. Template literals containing Redis key patterns (hot:orderbook:, ranked:, etc.)
 * 2. Function declarations for building Redis keys outside the redis-schema package
 */
export const noLocalRedisKeysRule = {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow local Redis key construction outside @scope/redis-schema",
    },
    messages: {
      useRedisSchema:
        "Redis key pattern '{{pattern}}' detected. Use centralized key builders " +
        "from @scope/redis-schema instead.",
      localKeyBuilder:
        "Local Redis key builder function '{{name}}' detected. " +
        "Use @scope/redis-schema exports instead.",
    },
  },
  create(context) {
    const filename = context.getFilename();

    // Allow in redis-schema package and test files
    const isInRedisSchemaPackage = filename.includes("packages/redis-schema/");
    const isTestFile =
      /\.(test|spec|smoke)\.ts$/.test(filename) ||
      filename.includes("__tests__") ||
      filename.includes("e2e-tests/");

    if (isInRedisSchemaPackage || isTestFile) {
      return {};
    }

    // Redis key prefixes used by @scope/redis-schema
    const REDIS_KEY_PATTERNS = [
      "hot:orderbook:",
      "ranked:",
      "unwind:queued:",
      "forced_unwind:",
      "exec:interventions",
      "hot:position:",
      "feed:events:",
    ];

    // Function name patterns that suggest local Redis key construction
    const KEY_BUILDER_PATTERNS = [
      /^build(Ranked|HotStore|Unwind|Orderbook|Stream|Forced)Key$/i,
      /^buildRedis.*$/i,
      /^build.*Redis.*Key$/i,
      /^.*RedisKey$/i,
      /^createRedis.*Key$/i,
    ];

    function containsRedisKeyPattern(value) {
      return REDIS_KEY_PATTERNS.some((pattern) => value.includes(pattern));
    }

    function isKeyBuilderName(name) {
      return KEY_BUILDER_PATTERNS.some((pattern) => pattern.test(name));
    }

    function getStringValue(node) {
      if (node.type === "Literal" && typeof node.value === "string") {
        return node.value;
      }
      if (node.type === "TemplateLiteral") {
        return node.quasis.map((quasi) => quasi.value.raw).join("");
      }
      return null;
    }

    return {
      TemplateLiteral(node) {
        const value = getStringValue(node);
        if (value && containsRedisKeyPattern(value)) {
          const matchedPattern = REDIS_KEY_PATTERNS.find((p) =>
            value.includes(p)
          );
          context.report({
            node,
            messageId: "useRedisSchema",
            data: { pattern: matchedPattern },
          });
        }
      },

      Literal(node) {
        if (
          typeof node.value === "string" &&
          containsRedisKeyPattern(node.value)
        ) {
          if (node.parent && node.parent.type === "ImportDeclaration") return;
          // Skip documentation strings in object properties
          if (
            node.parent?.type === "Property" &&
            node.parent.key?.type === "Identifier" &&
            ["example", "description", "doc", "docs", "comment"].includes(
              node.parent.key.name
            )
          ) {
            return;
          }
          const matchedPattern = REDIS_KEY_PATTERNS.find((p) =>
            node.value.includes(p)
          );
          context.report({
            node,
            messageId: "useRedisSchema",
            data: { pattern: matchedPattern },
          });
        }
      },

      FunctionDeclaration(node) {
        if (node.id && isKeyBuilderName(node.id.name)) {
          context.report({
            node: node.id,
            messageId: "localKeyBuilder",
            data: { name: node.id.name },
          });
        }
      },

      VariableDeclarator(node) {
        if (
          node.id?.type === "Identifier" &&
          isKeyBuilderName(node.id.name) &&
          node.init &&
          (node.init.type === "ArrowFunctionExpression" ||
            node.init.type === "FunctionExpression")
        ) {
          context.report({
            node: node.id,
            messageId: "localKeyBuilder",
            data: { name: node.id.name },
          });
        }
      },
    };
  },
};

export default noLocalRedisKeysRule;
```

### Example 3: Domain Type Protection via no-restricted-syntax

Rather than a custom rule, canonical type protection uses the built-in `no-restricted-syntax` rule with AST selectors:

```js
"no-restricted-syntax": [
  "warn",
  {
    selector:
      "TSTypeAliasDeclaration[id.name='Timeframe'], " +
      "TSTypeAliasDeclaration[id.name='SymbolId'], " +
      "TSInterfaceDeclaration[id.name='Candle'], " +
      "TSInterfaceDeclaration[id.name='Trade']",
    message:
      "Use canonical types from @scope/core-domain instead of redefining.",
  },
],
```

This warns (not errors) when a developer accidentally creates a local `type Timeframe = ...` or `interface Candle { ... }` instead of importing from the canonical source. The `core-domain` package itself disables this rule since it IS the canonical source.

### Example 4: Restrict Imports Between Specific Packages

Use `import-x/no-restricted-paths` to prevent a standalone service from importing web app types:

```js
// In apps/coinbase-ingestor/eslint.config.mjs
{
  files: ["**/*.ts"],
  rules: {
    "import-x/no-restricted-paths": [
      "error",
      {
        zones: [
          {
            target: "./src/**/*",
            from: "@scope/core-domain/replay-lab",
            message:
              "coinbase-ingestor must not depend on replay-lab-specific types. " +
              "Use base @scope/core-domain instead.",
          },
        ],
      },
    ],
  },
},
```

### Writing Custom Rule Checklist

1. Export the rule object with `meta` (type, docs, messages) and `create(context)` function.
2. Use `context.getFilename()` to determine if the file should be exempt (package origin, test file).
3. Return an object mapping AST node types to visitor functions.
4. Use `context.report({ node, message })` or `context.report({ node, messageId, data })` for violations.
5. Register the rule in the base config under a project-scoped plugin namespace.
6. Set the rule severity in the `rules` object: `"my-project/rule-name": "error"`.

---

## 5. Per-Package Configs

Each package or app in the monorepo has its own `eslint.config.mjs` that extends one of the shared configs and adds local overrides.

### Library Package (Standard)

Most library packages use the library config unchanged:

```js
// packages/trading-math/eslint.config.mjs
import libraryConfig from "@scope/eslint-config/library";

export default [...libraryConfig];
```

The library config extends the full strict base and disables boundary rules that only apply across package borders:

```js
// library.mjs
import baseConfig from "./base.js";

export default [
  ...baseConfig,
  {
    ignores: ["dist/**", "coverage/**"],
  },
  {
    files: ["**/*.ts", "**/*.tsx"],
    rules: {
      "import-x/no-internal-modules": "off",
      "boundaries/element-types": "off",
      "boundaries/no-unknown": "off",
      "boundaries/no-private": "off",
    },
  },
];
```

### App (Node.js Service)

Node.js services extend the strict base and override rules for app-specific concerns:

```js
// apps/coinbase-ingestor/eslint.config.mjs
import baseConfig from "@scope/eslint-config/base";

export default [
  ...baseConfig,
  {
    ignores: [
      "dist/**",
      "coverage/**",
      "vitest.config.ts",
      "eslint.config.mjs",
      "scripts/**",
    ],
  },
  {
    files: ["**/*.ts"],
    rules: {
      // Allow console for CLI/server logging
      "no-console": "off",
      // Allow object injection for process.env access
      "security/detect-object-injection": "off",
      // Within an app, relative imports are valid patterns
      "import-x/no-internal-modules": "off",
      // Prevent imports from other app-specific types
      "import-x/no-restricted-paths": [
        "error",
        {
          zones: [
            {
              target: "./src/**/*",
              from: "@scope/core-domain/replay-lab",
              message:
                "This service must not depend on replay-lab-specific types.",
            },
          ],
        },
      ],
    },
  },
  // Relaxed rules for test files
  {
    files: ["**/__tests__/**/*.ts", "**/*.test.ts", "**/*.spec.ts"],
    rules: {
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/only-throw-error": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-unsafe-call": "off",
      "@typescript-eslint/no-unsafe-return": "off",
      "@typescript-eslint/no-unsafe-argument": "off",
      "@typescript-eslint/require-await": "off",
      "@typescript-eslint/explicit-function-return-type": "off",
      "@typescript-eslint/restrict-template-expressions": "off",
      "sonarjs/no-duplicate-string": "off",
      "functional/no-let": "off",
      "functional/immutable-data": "off",
      "functional/prefer-readonly-type": "off",
      "no-console": "off",
      "import-x/no-internal-modules": "off",
      "security/detect-object-injection": "off",
    },
  },
];
```

### App (Next.js)

Next.js apps extend the nextjs config which includes React, React Hooks, JSX-A11y, and Next.js rules:

```js
// apps/replay-lab/eslint.config.mjs
import nextjsConfig from "@scope/eslint-config/nextjs";

export default [
  ...nextjsConfig,
  {
    ignores: [
      ".next/**",
      "out/**",
      "build/**",
      "coverage/**",
      "**/*.snap",
      "next-env.d.ts",
      "eslint.config.mjs",
      "postcss.config.mjs",
    ],
  },
  {
    files: ["**/*.ts", "**/*.tsx"],
    rules: {
      // Allow internal module imports for Next.js and packages
      "import-x/no-internal-modules": [
        "error",
        {
          allow: [
            "next/*",
            "next/**",
            "react/*",
            "react-dom/*",
            "drizzle-orm/*",
            "drizzle-orm/**",
            "@scope/database/*",
            "@scope/database/**",
            "@scope/core-domain/*",
            "@scope/core-domain/**",
            "@/lib/**",
            "@/app/**",
            "@/components/**",
            "vitest/config",
          ],
        },
      ],
      // Allow common API parameter abbreviations
      "unicorn/prevent-abbreviations": [
        "error",
        {
          replacements: { props: false, ref: false, params: false, param: false },
          allowList: { fromParam: true, toParam: true },
        },
      ],
      // Next.js generates triple-slash reference files
      "@typescript-eslint/triple-slash-reference": "off",
      // Disable JSDoc requirements for route handlers
      "jsdoc/require-jsdoc": "off",
    },
  },
  // Restrict contracts (Zod schemas) to API routes only
  {
    files: ["src/lib/**/*.ts"],
    ignores: ["src/lib/api-*.ts", "src/lib/api/**/*.ts"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/contracts", "@/contracts/*"],
              message:
                "Contracts (Zod schemas) should only be imported in API routes or " +
                "lib/api-* files. Use @scope/core-domain for pure types.",
            },
          ],
        },
      ],
    },
  },
  // Prevent non-NEXT_PUBLIC_ env vars in client code
  {
    files: ["src/**/*.ts", "src/**/*.tsx"],
    ignores: [
      "src/app/api/**",   // Server-side API routes
      "src/lib/auth.ts",  // Server-only auth config
      "src/lib/config.ts",
      "src/**/__tests__/**",
    ],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "MemberExpression[object.object.name='process'][object.property.name='env']" +
            "[property.name!=/^NEXT_PUBLIC_/]",
          message:
            "Client-side code must use NEXT_PUBLIC_ prefixed env vars. " +
            "Server-only env vars are undefined in the browser.",
        },
      ],
    },
  },
  // Relaxed rules for test files
  {
    files: ["**/__tests__/**/*.ts", "**/*.test.ts", "**/*.spec.ts"],
    rules: {
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-unsafe-call": "off",
      "@typescript-eslint/no-unsafe-return": "off",
      "@typescript-eslint/no-unsafe-argument": "off",
      "@typescript-eslint/require-await": "off",
      "@typescript-eslint/explicit-function-return-type": "off",
      "@typescript-eslint/restrict-template-expressions": "off",
      "sonarjs/no-duplicate-string": "off",
      "functional/no-let": "off",
      "functional/immutable-data": "off",
      "functional/prefer-readonly-type": "off",
      "no-console": "off",
      "import-x/no-internal-modules": "off",
      "security/detect-object-injection": "off",
    },
  },
];
```

### core-domain Package (ZERO Dependencies)

The foundation types package enforces that it cannot import any workspace packages:

```js
// packages/core-domain/eslint.config.mjs
import libraryConfig from "@scope/eslint-config/library";

export default [
  ...libraryConfig,
  {
    files: ["**/*.ts"],
    rules: {
      // STRICT: core-domain has ZERO dependencies
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@scope/database", "@scope/database/*"],
              message:
                "core-domain cannot import from database - it must have zero dependencies",
            },
            {
              group: ["@scope/service-core", "@scope/service-core/*"],
              message:
                "core-domain cannot import from service-core - it must have zero dependencies",
            },
            {
              group: ["@scope/replay-lab", "@scope/replay-lab/*"],
              message: "core-domain cannot import from apps",
            },
          ],
        },
      ],
      // core-domain IS the canonical source for these types
      "no-restricted-syntax": "off",
    },
  },
];
```

### Root Config

The root `eslint.config.mjs` provides defaults for any file not covered by a package-specific config (e.g., root-level scripts):

```js
// eslint.config.mjs (monorepo root)
import baseConfig from "@scope/eslint-config/base";

export default [
  ...baseConfig,
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/.next/**",
      "**/coverage/**",
      "**/build/**",
      "**/*.snap",
      "**/vitest.config.ts",
      "scripts/**",
      "packages/*/scripts/**",
    ],
  },
];
```

---

## 6. Testing Config

### testing.js

The testing config is applied to test files only. It registers the Vitest and Testing Library plugins with strict quality enforcement for tests.

```js
// testing.js
import vitestPlugin from "eslint-plugin-vitest";
import testingLibraryPlugin from "eslint-plugin-testing-library";

export default [
  {
    files: [
      "**/*.test.ts",
      "**/*.test.tsx",
      "**/*.spec.ts",
      "**/*.spec.tsx",
    ],
    plugins: {
      vitest: vitestPlugin,
      "testing-library": testingLibraryPlugin,
    },
    rules: {
      // ===================================================
      // Vitest Rules
      // ===================================================

      // --- Core correctness ---
      "vitest/expect-expect": "error", // Every test must have an assertion
      "vitest/valid-expect": "error", // Expect must be called correctly
      "vitest/no-identical-title": "error", // No duplicate test names
      "vitest/no-standalone-expect": "error", // Expect only inside test blocks

      // --- Test hygiene ---
      "vitest/no-disabled-tests": "error", // No .skip (committed skips rot)
      "vitest/no-focused-tests": "error", // No .only (breaks CI)
      "vitest/no-duplicate-hooks": "error", // No duplicate beforeEach/afterEach
      "vitest/no-test-return-statement": "error", // Prevents returning from tests
      "vitest/no-conditional-expect": "error", // No expect inside if/catch
      "vitest/no-conditional-in-test": "error", // No if/switch in tests

      // --- Test structure ---
      "vitest/require-top-level-describe": "error", // All tests in a describe
      "vitest/max-expects": ["error", { max: 8 }], // Max 8 assertions per test
      "vitest/max-nested-describe": ["error", { max: 3 }], // Max 3 nesting levels

      // --- Style ---
      "vitest/prefer-to-be": "error", // .toBe() over .toEqual() for primitives
      "vitest/prefer-to-have-length": "error", // .toHaveLength() over .length check
      "vitest/prefer-strict-equal": "error", // .toStrictEqual() over .toEqual()
      "vitest/prefer-hooks-on-top": "error", // Hooks before tests
      "vitest/prefer-lowercase-title": ["error", { ignore: ["describe"] }],
      "vitest/consistent-test-it": ["error", { fn: "it" }], // Use it(), not test()
      "vitest/prefer-each": "error", // .each() over loops

      // --- Opted out ---
      "vitest/prefer-expect-assertions": "off", // Don't require expect.assertions()

      // ===================================================
      // Testing Library Rules
      // ===================================================

      // --- Async correctness ---
      "testing-library/await-async-queries": "error",
      "testing-library/await-async-utils": "error",
      "testing-library/no-await-sync-queries": "error",

      // --- Best practices ---
      "testing-library/no-container": "error", // Don't use container queries
      "testing-library/no-debugging-utils": "error", // No screen.debug() committed
      "testing-library/no-dom-import": "error", // Import from framework package
      "testing-library/no-global-regexp-flag-in-query": "error",
      "testing-library/no-manual-cleanup": "error",
      "testing-library/no-node-access": "error", // No .firstChild, .parentElement
      "testing-library/no-promise-in-fire-event": "error",
      "testing-library/no-render-in-lifecycle": "error",
      "testing-library/no-unnecessary-act": "error",

      // --- Wait patterns ---
      "testing-library/no-wait-for-multiple-assertions": "error",
      "testing-library/no-wait-for-side-effects": "error",
      "testing-library/no-wait-for-snapshot": "error",

      // --- Query preferences ---
      "testing-library/prefer-explicit-assert": "error",
      "testing-library/prefer-find-by": "error", // findBy over waitFor + getBy
      "testing-library/prefer-presence-queries": "error",
      "testing-library/prefer-query-by-disappearance": "error",
      "testing-library/prefer-screen-queries": "error", // screen.getBy over result.getBy
      "testing-library/prefer-user-event": "error", // userEvent over fireEvent
      "testing-library/render-result-naming-convention": "error",

      // ===================================================
      // Relaxed Base Rules for Tests
      // ===================================================
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-unsafe-call": "off",
      "@typescript-eslint/explicit-function-return-type": "off",
      "@typescript-eslint/restrict-template-expressions": "off",
      "jsdoc/require-jsdoc": "off",
      "no-console": "off",
    },
  },
];
```

### Why These Testing Rules Matter

**`vitest/no-conditional-in-test: "error"`** -- Tests with `if/else` or `switch` hide which branch actually ran. Force explicit test cases for each branch with separate `it()` blocks or `.each()`.

**`vitest/max-expects: ["error", { max: 8 }]`** -- Tests with dozens of assertions are testing too many things. Split into focused tests. The limit of 8 is generous enough for snapshot-like assertions while preventing test bloat.

**`vitest/max-nested-describe: ["error", { max: 3 }]`** -- Deeply nested describes indicate overly complex test organization. Three levels (`describe > describe > it`) is sufficient for most test suites.

**`vitest/prefer-each: "error"`** -- Prefer `it.each([...])` over `for` loops. Loops produce a single test that fails at the first broken case. `.each()` runs every case independently so all failures are visible at once.

**`vitest/consistent-test-it: ["error", { fn: "it" }]`** -- Enforces `it("should ...")` over `test("should ...")` for consistency across the codebase.

**`testing-library/prefer-screen-queries: "error"`** -- `screen.getByText()` is always available and does not depend on destructuring the render result. It is more resilient to refactoring.

**`testing-library/prefer-user-event: "error"`** -- `userEvent` simulates real user interactions (focus, keydown, keyup, click) whereas `fireEvent` dispatches a single synthetic event. Tests using `userEvent` catch more bugs.

### Test File Relaxations

The testing config disables these base rules for test files:

| Rule | Why Disabled in Tests |
|------|----------------------|
| `@typescript-eslint/no-explicit-any` | Mocking frequently requires `any` |
| `@typescript-eslint/no-non-null-assertion` | Test data is known to exist |
| `@typescript-eslint/no-unsafe-*` | Mock return types are often untyped |
| `@typescript-eslint/explicit-function-return-type` | Mock functions do not need return types |
| `@typescript-eslint/restrict-template-expressions` | Template literals in test data are fine |
| `jsdoc/require-jsdoc` | Test functions are self-documenting |
| `no-console` | Debug output during development |

### Applying Testing Config

The testing config is designed to be spread into any package config that has tests:

```js
// Option A: Include testing config globally via index.js default export
import config from "@scope/eslint-config";
export default [...config];

// Option B: Include testing config explicitly
import nextjsConfig from "@scope/eslint-config/nextjs";
import testingConfig from "@scope/eslint-config/testing";
export default [...nextjsConfig, ...testingConfig];
```

The testing config uses `files` globs so its rules only apply to `*.test.ts` and `*.spec.ts` files, even when spread into the top-level config array.

---

## 7. Dependency-Cruiser Integration

Dependency-cruiser provides graph-level dependency analysis that ESLint cannot. Where ESLint rules operate on a single file at a time, dependency-cruiser builds a full dependency graph and validates it against architectural rules. This catches circular dependency chains that span multiple files, orphaned modules with no consumers, and layer boundary violations across the entire monorepo.

### Installation

```bash
pnpm add -D dependency-cruiser --filter @scope/eslint-config
# Or install at the monorepo root for shared usage
pnpm add -Dw dependency-cruiser
```

### .dependency-cruiser.cjs Configuration

Place this at the monorepo root. The CommonJS format is required because dependency-cruiser does not yet support ESM configs.

```js
// .dependency-cruiser.cjs

/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    // ===================================================
    // Circular Dependencies
    // ===================================================
    {
      name: "no-circular",
      severity: "error",
      comment:
        "Circular dependencies cause unpredictable initialization order " +
        "and break tree-shaking. Refactor shared logic into a third module.",
      from: {},
      to: {
        circular: true,
      },
    },

    // ===================================================
    // Orphan Detection
    // ===================================================
    {
      name: "no-orphans",
      severity: "warn",
      comment:
        "Modules that are not imported by anything are dead code. " +
        "Remove them or wire them into the dependency graph.",
      from: {
        orphan: true,
        pathNot: [
          "(^|/)\\.[^/]+\\.(?:js|cjs|mjs|ts|tsx)$", // dotfiles
          "\\.d\\.ts$",                                // type declarations
          "(^|/)tsconfig\\..*\\.json$",                // tsconfig variants
          "(^|/)vitest\\.config\\.",                    // test configs
          "(^|/)eslint\\.config\\.",                    // lint configs
          "(^|/)index\\.ts$",                           // barrel entry points
          "__tests__/",                                 // test files
          "\\.test\\.ts$",                              // test files
          "\\.spec\\.ts$",                              // test files
        ],
      },
      to: {},
    },

    // ===================================================
    // Layer Boundary: Domain Must Not Import Infrastructure
    // ===================================================
    {
      name: "domain-not-to-infrastructure",
      severity: "error",
      comment:
        "Domain logic (core-domain, trading-math) must not depend on " +
        "infrastructure (database, redis, HTTP clients). This preserves " +
        "testability and keeps the domain portable.",
      from: {
        path: "^packages/(core-domain|trading-math)/src/",
      },
      to: {
        path: "^packages/(database|redis-schema|service-core)/src/",
      },
    },

    // ===================================================
    // Layer Boundary: Packages Must Not Import Apps
    // ===================================================
    {
      name: "packages-not-to-apps",
      severity: "error",
      comment:
        "Shared packages must never import from apps. " +
        "Dependencies flow downward: apps -> packages -> core-domain.",
      from: {
        path: "^packages/",
      },
      to: {
        path: "^apps/",
      },
    },

    // ===================================================
    // Layer Boundary: Apps Must Not Import Other Apps
    // ===================================================
    {
      name: "no-cross-app-imports",
      severity: "error",
      comment:
        "Apps must not import from other apps. Extract shared code into a package.",
      from: {
        path: "^apps/([^/]+)/",
      },
      to: {
        path: "^apps/([^/]+)/",
        pathNot: "^apps/$1/", // Allow imports within the same app
      },
    },

    // ===================================================
    // Internal Module Protection
    // ===================================================
    {
      name: "no-reaching-into-package-src",
      severity: "error",
      comment:
        "Do not import from a package's src/ directory. Use the package's " +
        "public exports defined in package.json instead.",
      from: {
        pathNot: "^packages/([^/]+)/",
      },
      to: {
        path: "^packages/([^/]+)/src/",
        pathNot: [
          "node_modules",
        ],
      },
    },
  ],

  options: {
    doNotFollow: {
      path: "node_modules",
    },

    // Use TypeScript's pre-compilation module resolution
    tsPreCompilationDeps: true,

    tsConfig: {
      fileName: "tsconfig.json",
    },

    enhancedResolveOptions: {
      exportsFields: ["exports"],
      conditionNames: ["import", "require", "default"],
      mainFields: ["module", "main", "types"],
    },

    // Report only violations, not the full dependency graph
    reporterOptions: {
      dot: {
        collapsePattern: "node_modules/(@[^/]+/[^/]+|[^/]+)",
      },
      text: {
        highlightFocused: true,
      },
    },

    // Exclude test infrastructure from production graph analysis
    exclude: {
      path: [
        "__tests__",
        "\\.test\\.ts$",
        "\\.spec\\.ts$",
        "vitest\\.config",
        "smoke-tests",
      ],
    },
  },
};
```

### Pre-Push Hook Integration

Add dependency-cruiser to the pre-push hook alongside ESLint and tests. The `err` output type exits non-zero on any `"error"` severity violation:

```bash
# In .husky/pre-push or equivalent
npx depcruise src --config .dependency-cruiser.cjs --output-type err
```

For monorepos with Turbo, run per-package analysis:

```json
{
  "tasks": {
    "lint:deps": {
      "dependsOn": ["^build"],
      "inputs": ["src/**/*.ts", ".dependency-cruiser.cjs"],
      "cache": true
    }
  }
}
```

Each package's `package.json` then defines a `lint:deps` script:

```json
{
  "scripts": {
    "lint:deps": "depcruise src --config ../../.dependency-cruiser.cjs --output-type err"
  }
}
```

Run all packages in parallel via Turbo:

```bash
pnpm turbo run lint:deps
```

### CI Integration: SVG Dependency Graph Artifact

Generate a visual dependency graph as a CI artifact for architecture review. This produces an SVG showing the full module graph with violations highlighted in red:

```yaml
# .github/workflows/ci.yml (relevant job)
dependency-graph:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: pnpm/action-setup@v4
    - uses: actions/setup-node@v4
      with:
        node-version: 22
        cache: pnpm

    - run: pnpm install --frozen-lockfile

    - name: Generate dependency graph
      run: |
        npx depcruise src \
          --config .dependency-cruiser.cjs \
          --output-type dot \
          | dot -T svg > dependency-graph.svg

    - name: Upload dependency graph
      uses: actions/upload-artifact@v4
      with:
        name: dependency-graph
        path: dependency-graph.svg

    - name: Check for violations
      run: npx depcruise src --config .dependency-cruiser.cjs --output-type err
```

### ESLint-Compatible Output

Dependency-cruiser supports an `err-long` output type that shows file paths and line numbers in a format similar to ESLint output. For CI systems that parse ESLint-style output, use a custom reporter:

```js
// scripts/depcruise-eslint-reporter.cjs

/** @param {import('dependency-cruiser').ICruiseResult} cruiseResult */
module.exports = function eslintReporter(cruiseResult) {
  const violations = cruiseResult.summary.violations;

  if (violations.length === 0) {
    return { output: "", exitCode: 0 };
  }

  const lines = violations.map((violation) => {
    const from = violation.from;
    const to = violation.to;
    const severity = violation.rule.severity === "error" ? "error" : "warning";
    return `${from}:1:1: ${severity} ${violation.rule.name}: ${from} -> ${to}`;
  });

  return {
    output: lines.join("\n") + "\n",
    exitCode: violations.some((v) => v.rule.severity === "error") ? 1 : 0,
  };
};
```

Use it with:

```bash
npx depcruise src \
  --config .dependency-cruiser.cjs \
  --output-type plugin:scripts/depcruise-eslint-reporter.cjs
```

### How Dependency-Cruiser Complements ESLint

| Concern | ESLint | Dependency-Cruiser |
|---------|--------|--------------------|
| Single-file import rules | Yes (`import-x`, `boundaries`) | No |
| Multi-file circular chains | Limited (`import-x/no-cycle` is slow) | Yes (graph-based, fast) |
| Orphan module detection | No | Yes |
| Visual dependency graph | No | Yes (SVG, dot output) |
| Architecture layer validation | Basic (boundaries plugin) | Full (regex path rules) |
| Cross-app import detection | Manual per-package config | Single centralized config |

The recommendation is to use both: ESLint for per-file rules (import ordering, type checking, security) and dependency-cruiser for graph-level architecture validation (circular deps, orphans, layer boundaries).

---

## 8. Export Surface Limits

Large export surfaces are a reliable signal of poor encapsulation. When a package exports 80 symbols from its entry point, consumers cannot tell what is public API versus internal implementation detail. Export surface limits catch this drift before it becomes entrenched.

### Why This Matters

Every exported symbol is a contract. Consumers can depend on it, which means renaming, removing, or changing its signature is a breaking change. Packages that export everything from their `src/` directory via `export * from` chains accumulate massive surfaces where most exports are internal helpers that leaked into the public API.

Practical thresholds from production monorepos:

| Surface Size | Signal |
|-------------|--------|
| < 30 exports | Healthy -- focused public API |
| 30-50 exports | Review -- may contain leaked internals |
| > 50 exports | Action required -- split the package or tighten exports |

### Export Surface Checker Script

This script uses `ts-morph` to statically analyze each package's entry point and count the number of exported symbols. It resolves `export * from` chains to count the actual symbols that reach consumers.

```ts
// scripts/check-export-surface.ts
import { Project, SyntaxKind } from "ts-morph";
import * as path from "node:path";
import * as fs from "node:fs";
import * as process from "node:process";

interface PackageResult {
  name: string;
  entryPoint: string;
  exportCount: number;
  barrelReExports: number; // Number of `export * from` statements
  status: "ok" | "warn" | "error";
}

const WARN_THRESHOLD = 30;
const ERROR_THRESHOLD = 50;

/**
 * Resolve the entry point for a package by reading its package.json exports field.
 */
function resolveEntryPoint(packageDir: string): string | null {
  const packageJsonPath = path.join(packageDir, "package.json");
  if (!fs.existsSync(packageJsonPath)) return null;

  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf-8"));

  // Skip private packages
  if (packageJson.private) return null;

  // Prefer the "." export, then "main", then "types"
  const exports = packageJson.exports;
  if (exports?.["."]?.types) {
    return path.join(packageDir, exports["."].types);
  }
  if (exports?.["."]) {
    const root = typeof exports["."] === "string" ? exports["."] : exports["."].default;
    if (root) return path.join(packageDir, root);
  }
  if (packageJson.main) {
    return path.join(packageDir, packageJson.main);
  }

  // Fall back to src/index.ts
  const srcIndex = path.join(packageDir, "src", "index.ts");
  return fs.existsSync(srcIndex) ? srcIndex : null;
}

/**
 * Count exported symbols from a source file, resolving barrel re-exports.
 */
function countExports(project: Project, filePath: string): { count: number; barrels: number } {
  const sourceFile = project.getSourceFile(filePath);
  if (!sourceFile) {
    return { count: 0, barrels: 0 };
  }

  let count = 0;
  let barrels = 0;

  // Count named exports: export function, export class, export const, export type, export interface
  for (const declaration of sourceFile.getExportedDeclarations()) {
    count += declaration[1].length;
  }

  // Count `export * from` statements (barrel re-exports)
  for (const exportDecl of sourceFile.getExportDeclarations()) {
    if (exportDecl.isNamespaceExport() && exportDecl.getModuleSpecifierValue()) {
      barrels++;
    }
  }

  return { count, barrels };
}

/**
 * Main: scan all packages and report export surface sizes.
 */
function main(): void {
  const packagesDir = path.resolve(process.cwd(), "packages");
  const packageDirs = fs
    .readdirSync(packagesDir)
    .map((name) => path.join(packagesDir, name))
    .filter((dir) => fs.statSync(dir).isDirectory());

  const project = new Project({
    tsConfigFilePath: path.resolve(process.cwd(), "tsconfig.json"),
    skipAddingFilesFromTsConfig: true,
  });

  // Add all source files for resolution
  project.addSourceFilesAtPaths("packages/*/src/**/*.ts");

  const results: PackageResult[] = [];
  let hasError = false;

  for (const packageDir of packageDirs) {
    const entryPoint = resolveEntryPoint(packageDir);
    if (!entryPoint) continue;

    const { count, barrels } = countExports(project, entryPoint);
    const status =
      count > ERROR_THRESHOLD ? "error" : count > WARN_THRESHOLD ? "warn" : "ok";

    if (status === "error") hasError = true;

    results.push({
      name: path.basename(packageDir),
      entryPoint: path.relative(process.cwd(), entryPoint),
      exportCount: count,
      barrelReExports: barrels,
      status,
    });
  }

  // Sort by export count descending
  results.sort((a, b) => b.exportCount - a.exportCount);

  // Report
  console.log("\nExport Surface Analysis");
  console.log("=".repeat(70));

  for (const result of results) {
    const icon =
      result.status === "error" ? "ERROR" : result.status === "warn" ? "WARN " : "OK   ";
    const barrelNote =
      result.barrelReExports > 0 ? ` (${result.barrelReExports} barrel re-exports)` : "";
    console.log(
      `  ${icon}  ${result.name.padEnd(30)} ${String(result.exportCount).padStart(4)} exports${barrelNote}`
    );
  }

  console.log("=".repeat(70));
  console.log(
    `  Thresholds: warn > ${WARN_THRESHOLD}, error > ${ERROR_THRESHOLD}`
  );

  if (hasError) {
    console.error(
      "\nExport surface limit exceeded. Reduce exports or split the package."
    );
    process.exit(1);
  }
}

main();
```

### Running the Check

```bash
# One-off analysis
npx tsx scripts/check-export-surface.ts

# Add to package.json
{
  "scripts": {
    "lint:exports": "tsx scripts/check-export-surface.ts"
  }
}

# Run with Turbo (from monorepo root)
pnpm turbo run lint:exports
```

### Barrel File Anti-Pattern Detection

The `export * from` pattern (barrel re-export) is the primary mechanism through which export surfaces grow uncontrolled. A single `export * from "./utils"` can silently expose dozens of internal helpers when someone adds a new export to the utils module.

The checker script counts barrel re-exports separately and flags them. To enforce a stricter policy, add a dedicated lint rule:

```js
// In eslint config rules block
"no-restricted-syntax": [
  "warn",
  {
    selector: "ExportAllDeclaration",
    message:
      "Avoid `export * from`. Use explicit named re-exports to control " +
      "the package's public API surface.",
  },
],
```

This warns on every `export * from` statement, nudging developers toward explicit `export { Foo, Bar } from "./module"` re-exports where each symbol is a conscious choice.

### Pre-Push Hook Integration

Add the export surface check to the pre-push hook to prevent surface growth from reaching the repository:

```bash
# In .husky/pre-push or equivalent hook script
echo "Checking export surfaces..."
npx tsx scripts/check-export-surface.ts
```

For faster feedback, scope the check to changed packages only:

```bash
# Only check packages with changed files
CHANGED_PACKAGES=$(git diff --name-only HEAD~1 | grep '^packages/' | cut -d/ -f2 | sort -u)
for pkg in $CHANGED_PACKAGES; do
  echo "Checking exports: $pkg"
  npx tsx scripts/check-export-surface.ts --package "$pkg"
done
```

### API Extractor

For comprehensive API surface management beyond counting exports -- including API report diffing, `.d.ts` rollup generation, and breaking change detection -- see the API Extractor setup in [architecture-analysis.md](./architecture-analysis.md). API Extractor is the heavier tool for packages with external consumers; the export surface checker here is the lightweight gate suitable for pre-push hooks.

---

## Quick Reference: Rule Severity Summary

### Errors (block CI)

- All TypeScript strict rules (`no-explicit-any`, `explicit-function-return-type`, `no-non-null-assertion`, etc.)
- Import ordering and cycle detection
- Unicorn filename and module conventions
- SonarJS complexity and duplication limits
- All security rules (object injection, timing attacks, eval, secrets)
- All promise rules (always-return, catch-or-return, no-nesting)
- JSDoc on public API (classes, methods, functions)
- ESLint comment hygiene (no unused disables, require descriptions)
- Architecture boundaries (element types, no internal modules)
- Custom rules (no-direct-table-imports, no-local-redis-keys)
- All Vitest and Testing Library rules

### Warnings (visible but non-blocking)

- Domain type protection (`no-restricted-syntax` for canonical types)

### Disabled

- `unicorn/no-null` -- null is a valid value in database and API code
- `functional/no-let`, `functional/prefer-readonly-type`, `functional/immutable-data` -- aspirational, conflicts with practical patterns
- `vitest/prefer-expect-assertions` -- counting assertions is noisy without benefit
