# TypeScript Monorepo with pnpm Workspaces and Turborepo

This reference covers the complete setup for a production-grade TypeScript monorepo using pnpm workspaces and Turborepo. Every config block is copy-paste-able.

## 1. Workspace Structure

### Directory Layout

```
my-project/
  apps/
    web/                    # Next.js app
    api/                    # Node.js service
  packages/
    core-domain/            # Shared types and domain logic
    database/               # Drizzle ORM, schema, migrations
    service-core/           # Shared service utilities
    testing/                # Test utilities and fixtures
    eslint-config/          # Shared ESLint configuration
    tsconfig/               # Shared TypeScript configuration
    ui/                     # Shared UI components (if applicable)
  .changeset/
  .husky/
  turbo.json
  pnpm-workspace.yaml
  package.json
  vitest.config.ts
  lint-staged.config.mjs
  .prettierrc
  .jscpd.json
  .squawk.toml
```

### pnpm-workspace.yaml

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

### .npmrc

```ini
auto-install-peers=true
strict-peer-dependencies=false
```

## 2. Package Patterns

### 2a. Library Package (packages/*)

Library packages build to `dist/`, source lives in `src/`, and use the nested exports pattern for development-time TypeScript resolution.

**packages/core-domain/package.json:**

```json
{
  "name": "@myorg/core-domain",
  "version": "0.1.0",
  "private": false,
  "license": "UNLICENSED",
  "type": "module",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "files": ["dist"],
  "exports": {
    ".": {
      "development": {
        "types": "./src/index.ts",
        "default": "./src/index.ts"
      },
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    },
    "./types": {
      "development": {
        "types": "./src/types/index.ts",
        "default": "./src/types/index.ts"
      },
      "types": "./dist/types/index.d.ts",
      "default": "./dist/types/index.js"
    }
  },
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "format": "prettier --write --ignore-path ../../.prettierignore .",
    "format:check": "prettier --check --ignore-path ../../.prettierignore .",
    "lint": "eslint --quiet src/",
    "type-check": "tsc --noEmit",
    "test": "vitest run --silent",
    "test:watch": "vitest",
    "clean": "rm -rf dist .turbo node_modules tsconfig.tsbuildinfo"
  },
  "dependencies": {
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "@myorg/eslint-config": "workspace:*",
    "@myorg/tsconfig": "workspace:*",
    "typescript": "^5",
    "vitest": "^2.1.0"
  }
}
```

**packages/core-domain/tsconfig.json:**

```json
{
  "extends": "@myorg/tsconfig/library.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src",
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules", "dist"]
}
```

### 2b. App Package - Next.js (apps/*)

**apps/web/package.json:**

```json
{
  "name": "@myorg/web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "next dev --port 3000",
    "build": "next build",
    "start": "next start --port 3000",
    "format": "prettier --write --ignore-path ../../.prettierignore .",
    "format:check": "prettier --check --ignore-path ../../.prettierignore .",
    "lint": "eslint --quiet",
    "type-check": "tsc --noEmit",
    "test": "vitest run --silent",
    "test:coverage": "vitest run --coverage",
    "clean": "rm -rf .next .turbo node_modules tsconfig.tsbuildinfo"
  },
  "dependencies": {
    "@myorg/core-domain": "workspace:*",
    "@myorg/database": "workspace:*",
    "@myorg/ui": "workspace:*",
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@myorg/eslint-config": "workspace:*",
    "@myorg/tsconfig": "workspace:*",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9",
    "typescript": "^5"
  }
}
```

**apps/web/tsconfig.json:**

```json
{
  "extends": "@myorg/tsconfig/nextjs.json",
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@myorg/core-domain": ["../../packages/core-domain/src/index.ts"],
      "@myorg/core-domain/*": ["../../packages/core-domain/src/*"],
      "@myorg/*": ["../../packages/*/src/index.ts"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "next-env.d.ts", ".next/types/**/*.ts"],
  "exclude": ["node_modules", ".next"]
}
```

### 2c. App Package - Node.js Service (apps/*)

**apps/api/package.json:**

```json
{
  "name": "@myorg/api",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "engines": {
    "node": ">=20"
  },
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsc",
    "start": "node dist/index.js",
    "format": "prettier --write --ignore-path ../../.prettierignore .",
    "format:check": "prettier --check --ignore-path ../../.prettierignore .",
    "lint": "eslint --quiet .",
    "type-check": "tsc --noEmit",
    "test": "vitest run --silent",
    "test:watch": "vitest",
    "clean": "rm -rf dist node_modules tsconfig.tsbuildinfo"
  },
  "dependencies": {
    "@myorg/core-domain": "workspace:*",
    "@myorg/database": "workspace:*",
    "dotenv": "^16.4.5",
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "@myorg/eslint-config": "workspace:*",
    "@myorg/testing": "workspace:*",
    "@myorg/tsconfig": "workspace:*",
    "@types/node": "^20",
    "tsx": "^4.19.0",
    "typescript": "^5",
    "vitest": "^2.1.0"
  }
}
```

**apps/api/tsconfig.json:**

```json
{
  "extends": "@myorg/tsconfig/library.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src",
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules", "dist"]
}
```

### 2d. Config Package - tsconfig

**packages/tsconfig/package.json:**

```json
{
  "name": "@myorg/tsconfig",
  "version": "0.0.0",
  "private": true,
  "license": "MIT",
  "files": [
    "base.json",
    "nextjs.json",
    "library.json"
  ]
}
```

### 2e. Config Package - eslint-config

**packages/eslint-config/package.json:**

```json
{
  "name": "@myorg/eslint-config",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "main": "./index.js",
  "exports": {
    ".": "./index.js",
    "./base": "./base.mjs",
    "./nextjs": "./nextjs.js",
    "./library": "./library.mjs",
    "./testing": "./testing.js"
  },
  "dependencies": {
    "@eslint/js": "^9.0.0",
    "@next/eslint-plugin-next": "^15.0.0",
    "@typescript-eslint/eslint-plugin": "^8.0.0",
    "@typescript-eslint/parser": "^8.0.0",
    "eslint-config-prettier": "^10.0.0",
    "eslint-plugin-import-x": "^4.0.0",
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

**packages/eslint-config/base.mjs:**

```javascript
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
      "eqeqeq": ["error", "always"],
      "curly": ["error", "all"],
    },
  },
  globalIgnores(["dist/**", "node_modules/**", "*.js", "*.mjs", "*.cjs"]),
]);

export default baseConfig;
```

## 3. Turbo Pipeline

### turbo.json

```json
{
  "$schema": "https://turbo.build/schema.json",
  "ui": "tui",
  "globalEnv": [
    "DATABASE_URL",
    "NODE_ENV"
  ],
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "inputs": ["$TURBO_DEFAULT$", ".env*"],
      "outputs": [".next/**", "!.next/cache/**", "dist/**"]
    },
    "lint": {
      "inputs": ["$TURBO_DEFAULT$", "^$TURBO_DEFAULT$", ".env*"],
      "outputs": []
    },
    "format": {
      "outputs": [],
      "cache": true
    },
    "format:check": {
      "outputs": [],
      "cache": true
    },
    "type-check": {
      "inputs": ["$TURBO_DEFAULT$", "^$TURBO_DEFAULT$"],
      "outputs": ["*.tsbuildinfo"]
    },
    "test": {
      "inputs": ["$TURBO_DEFAULT$", ".env*"],
      "outputs": ["coverage/**"]
    },
    "test:coverage": {
      "inputs": ["$TURBO_DEFAULT$", ".env*"],
      "outputs": ["coverage/**"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "clean": {
      "cache": false
    },
    "db:push": {
      "dependsOn": ["^build"],
      "cache": false
    },
    "db:migrate:sql": {
      "dependsOn": ["^build"],
      "cache": false
    }
  }
}
```

**Key design decisions:**

- `build` depends on `^build` (upstream packages must build first).
- `lint` and `type-check` use `^$TURBO_DEFAULT$` to re-run when upstream source changes.
- `format` and `format:check` are cached but produce no output files (side-effect-only).
- `dev` is never cached and marked `persistent` for long-running dev servers.
- `db:push` and `db:migrate:sql` are never cached (always run fresh against the database).
- `clean` is never cached (destructive operation).

## 4. TypeScript Configuration

### packages/tsconfig/base.json

The foundation for all packages. Strict mode, modern target, bundler resolution.

```json
{
  "$schema": "https://json.schemastore.org/tsconfig",
  "display": "Base - Strict TypeScript Configuration",
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "customConditions": ["development"],
    "resolveJsonModule": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "incremental": true,

    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "exactOptionalPropertyTypes": true,
    "noPropertyAccessFromIndexSignature": true,
    "forceConsistentCasingInFileNames": true,
    "verbatimModuleSyntax": false
  }
}
```

**Critical setting: `customConditions: ["development"]`** -- This tells TypeScript to resolve the `"development"` condition in package exports, which points to `./src/` source files instead of `./dist/` build artifacts. This enables live type-checking across packages without rebuilding.

### packages/tsconfig/library.json

For library packages that compile to `dist/`.

```json
{
  "$schema": "https://json.schemastore.org/tsconfig",
  "display": "Library Package Configuration",
  "extends": "./base.json",
  "compilerOptions": {
    "customConditions": ["development"],
    "outDir": "./dist",
    "rootDir": "./src",
    "declaration": true,
    "declarationMap": true,

    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

### packages/tsconfig/nextjs.json

For Next.js applications.

```json
{
  "$schema": "https://json.schemastore.org/tsconfig",
  "display": "Next.js Application Configuration",
  "extends": "./base.json",
  "compilerOptions": {
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "jsx": "preserve",
    "noEmit": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowJs": true,
    "verbatimModuleSyntax": false,

    "plugins": [
      {
        "name": "next"
      }
    ],

    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@myorg/*": ["../../packages/*/src/index.ts"]
    }
  }
}
```

## 5. Package Exports Pattern (CRITICAL)

### The Problem

TypeScript ALWAYS resolves the `"types"` condition first in package exports, regardless of `customConditions`. This means if you write:

```json
{
  "exports": {
    ".": {
      "development": { "types": "./src/index.ts", "default": "./src/index.ts" },
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    }
  }
}
```

TypeScript will skip `"development"` entirely and jump to `"types": "./dist/index.d.ts"`. If `dist/` does not exist (because you have not built yet), type-checking fails.

### The Fix

Nest `"types"` INSIDE the `"development"` condition. TypeScript resolves `"development"` first (because `customConditions` matches), and then finds `"types"` within it:

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

**Resolution order with `customConditions: ["development"]`:**

1. TypeScript sees `"development"` -- matches `customConditions` -- enters the block.
2. Inside, it finds `"types": "./src/index.ts"` -- resolves types from source.
3. The outer `"types": "./dist/index.d.ts"` is the fallback for production builds or consumers without `customConditions`.

**Resolution order WITHOUT `customConditions`:**

1. TypeScript skips `"development"` (no match).
2. Finds `"types": "./dist/index.d.ts"` -- resolves from built output.
3. Falls through to `"default": "./dist/index.js"` for runtime.

### Multiple Sub-path Exports

Apply the same pattern to every export:

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
    },
    "./types": {
      "development": {
        "types": "./src/types/index.ts",
        "default": "./src/types/index.ts"
      },
      "types": "./dist/types/index.d.ts",
      "default": "./dist/types/index.js"
    },
    "./utils": {
      "development": {
        "types": "./src/utils/index.ts",
        "default": "./src/utils/index.ts"
      },
      "types": "./dist/utils/index.d.ts",
      "default": "./dist/utils/index.js"
    }
  }
}
```

### Validation Test

Add this test to your workspace to catch incorrect export structures:

```typescript
// packages/testing/src/__tests__/workspace-exports.test.ts
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";

function getPackageDirs(): string[] {
  const packagesDir = path.resolve(__dirname, "../../../../packages");
  return fs
    .readdirSync(packagesDir)
    .map((name) => path.join(packagesDir, name))
    .filter((dir) => fs.statSync(dir).isDirectory())
    .filter((dir) => fs.existsSync(path.join(dir, "package.json")));
}

describe("workspace exports", () => {
  it("publishable packages nest types inside development condition", () => {
    for (const dir of getPackageDirs()) {
      const pkg = JSON.parse(fs.readFileSync(path.join(dir, "package.json"), "utf-8"));
      if (pkg.private) continue;
      if (!pkg.exports) continue;

      for (const [subpath, config] of Object.entries(pkg.exports)) {
        if (typeof config === "string") continue;
        const entry = config as Record<string, unknown>;

        if (entry.development) {
          const dev = entry.development as Record<string, string>;
          expect(dev.types, `${pkg.name} ${subpath} development.types`).toBeDefined();
          expect(dev.types).toMatch(/\.\/src\//);
        }

        if (entry.types) {
          expect(entry.types).toMatch(/\.\/dist\//);
        }
      }
    }
  });
});
```

## 6. Root package.json

```json
{
  "name": "my-project",
  "version": "0.1.0",
  "private": true,
  "packageManager": "pnpm@9.15.0",
  "scripts": {
    "build": "turbo run build --output-logs=errors-only",
    "dev": "turbo run dev",
    "lint": "turbo run lint --output-logs=errors-only",
    "format": "prettier --write --ignore-path .prettierignore '*.md' '*.json' '*.yaml' '*.yml' '.vscode/**' && turbo run format",
    "format:check": "prettier --check --ignore-path .prettierignore '*.md' '*.json' '*.yaml' '*.yml' '.vscode/**' && turbo run format:check",
    "test": "turbo run test --output-logs=errors-only",
    "test:unit": "turbo run build --filter=./packages/** && vitest run",
    "test:coverage": "mkdir -p coverage/.tmp && turbo run build --filter=./packages/** && vitest run --coverage",
    "test:integration": "vitest run --config vitest.integration.config.ts --silent",
    "type-check": "turbo run type-check --output-logs=errors-only",
    "clean": "turbo run clean && rm -rf node_modules",
    "prepare": "husky",
    "qa:quick": "pnpm lint && pnpm type-check",
    "qa": "pnpm lint && pnpm type-check && pnpm test && pnpm build",
    "ci": "pnpm qa",
    "cpd": "jscpd apps/ packages/ --config .jscpd.json",
    "cpd:report": "jscpd apps/ packages/ --config .jscpd.json --reporters html",
    "lint:sql": "squawk --config .squawk.toml packages/database/drizzle/*.sql packages/database/migrations/*.sql",
    "changeset": "changeset",
    "changeset:status": "changeset status",
    "changeset:version": "changeset version",
    "changeset:publish": "changeset publish",
    "db:push": "turbo run db:push",
    "db:migrate:sql": "turbo run db:migrate:sql"
  },
  "devDependencies": {
    "@changesets/cli": "^2.29.0",
    "@vitest/coverage-v8": "^2.1.0",
    "husky": "^9.1.0",
    "jscpd": "^4.0.7",
    "lint-staged": "^16.2.0",
    "prettier": "^3.5.0",
    "squawk-cli": "^2.36.0",
    "tsx": "^4.19.0",
    "turbo": "^2.3.0",
    "typescript": "^5",
    "vitest": "^2.1.0"
  }
}
```

**Script breakdown:**

| Script | Purpose |
|--------|---------|
| `build` | Build all packages and apps via Turbo (errors-only output for cleanliness) |
| `dev` | Start all dev servers in parallel via Turbo |
| `lint` | ESLint all packages via Turbo |
| `format` | Run Prettier on root files, then Turbo-delegated format per package |
| `format:check` | Same as format but check-only (CI gate) |
| `test` | Run all package test suites via Turbo |
| `test:unit` | Build packages first, then run vitest from root |
| `test:coverage` | Build packages, run vitest with coverage thresholds |
| `test:integration` | Run integration tests (separate vitest config, requires DATABASE_URL) |
| `type-check` | TypeScript type-checking for all packages via Turbo |
| `clean` | Remove all dist, .turbo, node_modules |
| `qa:quick` | Fast local check: lint + type-check only |
| `qa` | Full quality gate: lint + type-check + test + build |
| `ci` | Alias for qa (matches CI pipeline exactly) |
| `cpd` | Copy-paste detection across all source files |
| `lint:sql` | Lint SQL migration files with squawk |
| `changeset` | Create a new changeset for version management |
| `db:push` | Push Drizzle schema to dev database |
| `db:migrate:sql` | Run SQL migrations |

## 7. Formatter Configuration

### .prettierrc

```json
{
  "semi": true,
  "singleQuote": false,
  "trailingComma": "es5",
  "tabWidth": 2,
  "printWidth": 100
}
```

### .prettierignore

```
node_modules
dist
.next
coverage
pnpm-lock.yaml
*.min.js
*.min.css
drizzle/**
```

## 8. Lint-Staged Configuration

### lint-staged.config.mjs

```javascript
export default {
  "**/*.{ts,tsx,js,jsx,mjs,cjs}": ["prettier --write --ignore-path .prettierignore"],
  "**/*.{json,md,yml,yaml}": ["prettier --write --ignore-path .prettierignore"],
};
```

ESLint is NOT run by lint-staged. It runs via `turbo lint` in the pre-commit hook, which executes from each package's directory so per-package ESLint configs work correctly.

## 9. Vitest Configuration

### vitest.config.ts (root)

```typescript
import { defineConfig } from "vitest/config";

const isCi = process.env.CI === "true";

export default defineConfig({
  resolve: {
    conditions: ["development", "require", "default"],
  },
  ssr: {
    resolve: {
      conditions: ["development", "require", "default"],
    },
  },
  test: {
    globals: true,
    environment: "node",
    pool: "threads",
    poolOptions: {
      threads: {
        singleThread: isCi,
        isolate: true,
        minThreads: 1,
        maxThreads: isCi ? 1 : 4,
      },
    },
    fileParallelism: !isCi,
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      clean: false,
      cleanOnRerun: false,
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
        "packages/testing/**",
      ],
      include: [
        "packages/*/src/**/*.ts",
        "!packages/*/src/**/*.test.ts",
        "!packages/*/src/**/__tests__/**",
      ],
    },
    include: [
      "packages/**/src/**/*.test.ts",
      "packages/**/src/**/*.test.tsx",
      "apps/*/src/**/*.test.ts",
      "apps/*/src/**/*.test.tsx",
    ],
    exclude: [
      "node_modules",
      ".next",
      "**/node_modules/**",
      "**/*.integration.test.ts",
    ],
  },
});
```

**Key decisions:**

- `conditions: ["development"]` in resolve so vitest imports source from `./src/` via the nested exports pattern.
- CI mode runs single-threaded to avoid flaky parallel failures.
- Coverage thresholds at 90% for all metrics.
- Integration tests (`*.integration.test.ts`) are excluded from unit test runs and have their own config.

### vitest.integration.config.ts (root)

```typescript
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    conditions: ["development", "require", "default"],
  },
  test: {
    globals: true,
    environment: "node",
    include: ["**/*.integration.test.ts"],
    testTimeout: 30_000,
  },
});
```

## 10. Copy-Paste Detection

### .jscpd.json

```json
{
  "threshold": 5,
  "reporters": ["console", "json", "html"],
  "output": "./reports/duplication",
  "ignore": [
    "**/node_modules/**",
    "**/dist/**",
    "**/.next/**",
    "**/coverage/**",
    "**/__tests__/**",
    "**/*.test.ts",
    "**/*.test.tsx",
    "**/*.spec.ts",
    "**/generated/**",
    "**/drizzle/**",
    "**/.turbo/**"
  ],
  "format": ["typescript", "typescriptreact"],
  "minTokens": 50,
  "minLines": 5,
  "absolute": true,
  "gitignore": true
}
```

## 11. SQL Migration Linting

### .squawk.toml

```toml
# Only applicable if your project uses PostgreSQL migrations.
# Squawk catches dangerous migration patterns before they hit production.

assume_in_transaction = false
pg_version = "15.0"

excluded_rules = [
  "prefer-bigint-over-int",
  "prefer-bigint-over-smallint",
  "require-timeout-settings",
  "prefer-robust-stmts",
]
```

## 12. Git Hooks

### .husky/pre-commit

```bash
#!/usr/bin/env bash

# 0. Lint-staged (Prettier auto-fix on staged files)
pnpm exec lint-staged || { echo "lint-staged failed"; exit 1; }

# 1. Lockfile consistency check
STAGED_PACKAGE_JSON=$(git diff --cached --name-only -- 'package.json' 'pnpm-workspace.yaml' 'apps/**/package.json' 'packages/**/package.json' || true)
if [ -n "$STAGED_PACKAGE_JSON" ]; then
  DEPS_CHANGED=$(git diff --cached -- $STAGED_PACKAGE_JSON | grep -E '^\+.*"(dependencies|devDependencies|peerDependencies|optionalDependencies)"' || true)
  if [ -n "$DEPS_CHANGED" ]; then
    if ! git diff --cached --name-only -- 'pnpm-lock.yaml' | grep -q 'pnpm-lock.yaml'; then
      echo "pnpm-lock.yaml is not staged but package.json dependency changes are staged"
      echo "   Run: pnpm install"
      exit 1
    fi
  fi
fi

# 2. Lint affected packages (parallel with type-check)
pnpm turbo lint --filter='...[HEAD^1]' --output-logs=errors-only &
LINT_PID=$!

# 3. Type-check affected packages
pnpm turbo type-check --filter='...[HEAD^1]' --output-logs=errors-only &
TYPE_CHECK_PID=$!

# Wait for parallel checks
wait "$LINT_PID" || { echo "Lint failed"; exit 1; }
wait "$TYPE_CHECK_PID" || { echo "Type check failed"; exit 1; }

# 4. Test affected packages
pnpm turbo test --filter='...[HEAD^1]' --output-logs=errors-only || { echo "Tests failed"; exit 1; }

# 5. Secret detection
STAGED_FILES=$(git diff --cached --name-only || true)
if [ -n "$STAGED_FILES" ]; then
  SECRETS_FOUND=$(echo "$STAGED_FILES" | xargs grep -l -E "(password|secret|api[_-]?key|token|credential)\s*[:=]\s*['\"][^'\"]+['\"]" 2>/dev/null || true)
  if [ -n "$SECRETS_FOUND" ]; then
    echo "Hardcoded secrets detected:"
    echo "$SECRETS_FOUND"
    exit 1
  fi
fi

# 6. Check for 'any' types (warning only)
STAGED_TS=$(git diff --cached --name-only -- '*.ts' '*.tsx' | grep -v '.test.' | grep -v '.d.ts' || true)
if [ -n "$STAGED_TS" ]; then
  ANY_FOUND=$(echo "$STAGED_TS" | xargs grep -l ': any' 2>/dev/null || true)
  if [ -n "$ANY_FOUND" ]; then
    echo "Warning: 'any' type found in staged files"
  fi
fi

# 7. Test assertion density (warning for thin tests)
STAGED_TESTS=$(git diff --cached --name-only -- '*.test.ts' '*.test.tsx' || true)
if [ -n "$STAGED_TESTS" ]; then
  for file in $STAGED_TESTS; do
    if [ -f "$file" ]; then
      LINES=$(wc -l < "$file" | tr -d ' ')
      EXPECTS=$(grep -c 'expect(' "$file" 2>/dev/null || echo "0")
      if [ "$LINES" -gt 50 ] && [ "$EXPECTS" -lt 3 ]; then
        echo "Warning: Low assertion density in $file ($EXPECTS expects in $LINES lines)"
      fi
    fi
  done
fi

# 8. Changeset enforcement for publishable packages
STAGED_PKG_DIRS=$(git diff --cached --name-only -- 'packages/**' 'apps/**' | sed -E 's#^((packages|apps)/[^/]+)/.*#\1#' | sort -u || true)
NEEDS_CHANGESET=false

for pkg_dir in $STAGED_PKG_DIRS; do
  if [ -f "$pkg_dir/package.json" ]; then
    IS_PRIVATE=$(grep -E '"private"\s*:\s*true' "$pkg_dir/package.json" || true)
    if [ -z "$IS_PRIVATE" ]; then
      NEEDS_CHANGESET=true
    fi
  fi
done

if [ "$NEEDS_CHANGESET" = true ]; then
  CHANGESETS=$(find .changeset -name "*.md" ! -name "README.md" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$CHANGESETS" -eq 0 ]; then
    echo "No changeset found but publishable package code is being committed"
    echo "   Run: pnpm changeset"
    exit 1
  fi
fi

echo "Pre-commit passed"
```

### .husky/pre-push

```bash
#!/usr/bin/env sh

# Ensure local branch is not behind origin/main
git fetch origin main --quiet 2>/dev/null
BEHIND_COUNT=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
if [ "$BEHIND_COUNT" != "0" ]; then
  echo "Pre-push blocked: origin/main is $BEHIND_COUNT commit(s) ahead"
  echo "   Fix: git fetch origin main && git rebase origin/main"
  exit 1
fi

# No uncommitted changes
UNCOMMITTED=$(git status --porcelain 2>/dev/null)
if [ -n "$UNCOMMITTED" ]; then
  echo "Pre-push blocked: uncommitted changes detected"
  echo "   Fix: commit or stash changes before pushing"
  exit 1
fi

export CI=true
export TERM=dumb

# Full QA suite
pnpm format:check || { echo "Format check failed - run 'pnpm format'"; exit 1; }
pnpm lint || { echo "Lint failed"; exit 1; }
pnpm type-check || { echo "Type check failed"; exit 1; }
pnpm test:coverage || { echo "Tests or coverage failed"; exit 1; }
pnpm build || { echo "Build failed"; exit 1; }

# Integration tests if database is available
if [ -n "$DATABASE_URL" ]; then
  pnpm test:integration || { echo "Integration tests failed"; exit 1; }
fi

echo "Pre-push passed"
```

## 13. Changesets

### .changeset/config.json

```json
{
  "$schema": "https://unpkg.com/@changesets/config@3.0.0/schema.json",
  "changelog": "@changesets/cli/changelog",
  "commit": false,
  "fixed": [],
  "linked": [],
  "access": "restricted",
  "baseBranch": "main",
  "updateInternalDependencies": "patch",
  "ignore": []
}
```

### Creating a Changeset (Non-Interactive)

Write a markdown file to `.changeset/` with a unique name:

```markdown
---
"@myorg/core-domain": patch
---

Fixed type resolution for nested exports.
```

**Bump types:**

- `patch` -- Bug fixes, minor changes (0.0.X)
- `minor` -- New features, non-breaking changes (0.X.0)
- `major` -- Breaking changes (X.0.0)

**Empty changeset (no version bump needed):**

```markdown
---
---
```

## 14. Complete Dependency List

### Root devDependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `turbo` | `^2.3.0` | Monorepo build orchestration |
| `typescript` | `^5` | TypeScript compiler (root-level for editor support) |
| `prettier` | `^3.5.0` | Code formatting |
| `eslint` | `^9.0.0` | Linting (peer dependency, installed per-app) |
| `vitest` | `^2.1.0` | Test runner |
| `@vitest/coverage-v8` | `^2.1.0` | Coverage provider |
| `husky` | `^9.1.0` | Git hooks |
| `lint-staged` | `^16.2.0` | Run formatters on staged files |
| `tsx` | `^4.19.0` | TypeScript execution for scripts |
| `@changesets/cli` | `^2.29.0` | Version management and changelogs |
| `jscpd` | `^4.0.7` | Copy-paste detection |
| `squawk-cli` | `^2.36.0` | SQL migration linting |

### Per-Package devDependencies (Library)

```json
{
  "@myorg/eslint-config": "workspace:*",
  "@myorg/tsconfig": "workspace:*",
  "typescript": "^5",
  "vitest": "^2.1.0"
}
```

### Per-Package devDependencies (Node.js App)

```json
{
  "@myorg/eslint-config": "workspace:*",
  "@myorg/testing": "workspace:*",
  "@myorg/tsconfig": "workspace:*",
  "@types/node": "^20",
  "tsx": "^4.19.0",
  "typescript": "^5",
  "vitest": "^2.1.0"
}
```

### Per-Package devDependencies (Next.js App)

```json
{
  "@myorg/eslint-config": "workspace:*",
  "@myorg/tsconfig": "workspace:*",
  "@types/node": "^20",
  "@types/react": "^19",
  "@types/react-dom": "^19",
  "eslint": "^9",
  "typescript": "^5"
}
```

## 15. Quick Setup Checklist

1. **Initialize the repo:**
   ```bash
   mkdir my-project && cd my-project
   git init
   pnpm init
   ```

2. **Create pnpm-workspace.yaml** (see Section 1).

3. **Install root devDependencies:**
   ```bash
   pnpm add -D turbo typescript prettier vitest @vitest/coverage-v8 \
     husky lint-staged tsx @changesets/cli jscpd squawk-cli
   ```

4. **Create config packages first:**
   - `packages/tsconfig/` with `base.json`, `library.json`, `nextjs.json`
   - `packages/eslint-config/` with `base.mjs`, `library.mjs`, `nextjs.js`

5. **Create library packages** following the exports pattern in Section 5.

6. **Create app packages** referencing workspace dependencies with `workspace:*`.

7. **Add config files** at root: `turbo.json`, `.prettierrc`, `lint-staged.config.mjs`, `vitest.config.ts`, `.jscpd.json`.

8. **Set up git hooks:**
   ```bash
   pnpm exec husky init
   ```
   Write `.husky/pre-commit` and `.husky/pre-push` (see Section 12).

9. **Initialize changesets:**
   ```bash
   pnpm changeset init
   ```

10. **Verify everything works:**
    ```bash
    pnpm install
    pnpm qa
    ```
