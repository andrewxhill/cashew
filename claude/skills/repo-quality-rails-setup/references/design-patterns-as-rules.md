# Design Patterns as Deterministic Rules

Most design principles are treated as suggestions. Code reviewers say "this should use the Result pattern" or "you should code to interfaces" and then the advice is ignored in the next PR. The insight behind this reference is that nearly every widely-accepted design principle CAN be enforced deterministically through lint rules, type system features, and architectural analysis tools. "Good design" is not subjective -- it is a set of constraints that machines can verify faster and more consistently than humans.

This reference covers ten design principles, each with concrete enforcement mechanisms: custom ESLint rules, TypeScript configuration, dependency-cruiser configs, and CI scripts. Every code block is intended to be working, copy-paste-able configuration.

## Table of Contents

1. [Error Taxonomy: Typed Errors as a Design Gate](#1-error-taxonomy-typed-errors-as-a-design-gate)
2. [Result Pattern: Explicit Nullability](#2-result-pattern-explicit-nullability)
3. [Interface-First Enforcement](#3-interface-first-enforcement)
4. [Command/Query Separation (CQS)](#4-commandquery-separation-cqs)
5. [Single Responsibility via File Naming Conventions](#5-single-responsibility-via-file-naming-conventions)
6. [Immutability by Default](#6-immutability-by-default)
7. [Dependency Direction Rules](#7-dependency-direction-rules)
8. [API Surface Minimization](#8-api-surface-minimization)
9. [Nullability Rules](#9-nullability-rules)
10. [Design Rules Per Language](#10-design-rules-per-language)

---

## 1. Error Taxonomy: Typed Errors as a Design Gate

### The Problem

`throw new Error("something broke")` is a design smell. It tells the caller nothing about what failed, provides no structured data for error handling, and makes exhaustive error handling impossible. Callers end up parsing error message strings, which is brittle and untestable.

### The Pattern: Discriminated Union Errors

Define all possible errors as a discriminated union. Each variant carries structured data specific to that failure mode.

```typescript
// src/errors.ts
export type AppError =
  | { code: "NOT_FOUND"; entity: string; id: string }
  | { code: "VALIDATION"; field: string; message: string; value: unknown }
  | { code: "UNAUTHORIZED"; requiredRole?: string }
  | { code: "CONFLICT"; entity: string; conflictField: string }
  | { code: "RATE_LIMITED"; retryAfterMs: number }
  | { code: "EXTERNAL_SERVICE"; service: string; statusCode: number; body: string };

export function notFound(entity: string, id: string): AppError {
  return { code: "NOT_FOUND", entity, id };
}

export function validation(field: string, message: string, value: unknown): AppError {
  return { code: "VALIDATION", field, message, value };
}

// Exhaustive handler -- TypeScript enforces every variant is covered
export function toHttpStatus(error: AppError): number {
  switch (error.code) {
    case "NOT_FOUND": return 404;
    case "VALIDATION": return 400;
    case "UNAUTHORIZED": return 401;
    case "CONFLICT": return 409;
    case "RATE_LIMITED": return 429;
    case "EXTERNAL_SERVICE": return 502;
  }
  // No default needed -- TypeScript knows this is exhaustive.
  // Adding a new error code without handling it here is a compile error.
}
```

### ESLint Rule: Ban `throw new Error(string)`

```js
// rules/no-untyped-errors.js
export const noUntypedErrorsRule = {
  meta: {
    type: "problem",
    docs: { description: "Ban throw new Error(string) in favor of typed error constructors" },
    messages: {
      untypedError:
        "Do not throw untyped Error objects. Use a typed error constructor " +
        "(e.g., notFound(), validation()) from src/errors.ts instead.",
    },
    schema: [],
  },
  create(context) {
    return {
      ThrowStatement(node) {
        if (
          node.argument?.type === "NewExpression" &&
          node.argument.callee.type === "Identifier" &&
          ["Error", "TypeError", "RangeError", "SyntaxError"].includes(node.argument.callee.name)
        ) {
          context.report({ node, messageId: "untypedError" });
        }
      },
    };
  },
};
```

Register it and disable for test files:

```js
// eslint.config.mjs (flat config)
import { noUntypedErrorsRule } from "./rules/no-untyped-errors.js";

export default [
  {
    plugins: { "my-project": { rules: { "no-untyped-errors": noUntypedErrorsRule } } },
    rules: { "my-project/no-untyped-errors": "error" },
  },
  {
    files: ["**/*.test.ts", "**/*.spec.ts", "**/__tests__/**"],
    rules: { "my-project/no-untyped-errors": "off" },
  },
];
```

### Benefits

- **Exhaustive handling**: `switch-exhaustiveness-check` ensures every error code is covered.
- **Error catalogs**: Generate documentation from the union type automatically.
- **Structured logging**: `logger.error("Request failed", { error })` gives machine-parseable fields.
- **HTTP mapping**: One function maps the entire taxonomy to status codes -- no scattered `res.status(404)`.

---

## 2. Result Pattern: Explicit Nullability

### The Problem

The type signature `getUser(id: string): User` is a lie -- it might return `null`, throw a `NotFoundError`, or throw a connection error. Callers have no way to know without reading the implementation.

### The Pattern

```typescript
// src/result.ts
export type Result<T, E = AppError> =
  | { ok: true; value: T }
  | { ok: false; error: E };

export function ok<T>(value: T): Result<T, never> {
  return { ok: true, value };
}

export function err<E>(error: E): Result<never, E> {
  return { ok: false, error };
}

export function unwrap<T, E>(result: Result<T, E>): T {
  if (result.ok) return result.value;
  throw new Error(`Unwrap called on error result: ${JSON.stringify(result.error)}`);
}

export function map<T, U, E>(result: Result<T, E>, fn: (value: T) => U): Result<U, E> {
  return result.ok ? ok(fn(result.value)) : result;
}

export function flatMap<T, U, E>(
  result: Result<T, E>,
  fn: (value: T) => Result<U, E>
): Result<U, E> {
  return result.ok ? fn(result.value) : result;
}
```

### When to Use and When NOT to Use

**Use Result for:** parsing, validation, database lookups, external API calls -- any function where failure is an expected, normal path.

**Do NOT use Result for:** truly exceptional conditions (out of memory), programming errors (wrong types at runtime), infrastructure failures with no meaningful recovery.

The boundary is: if the caller can and should do something meaningful with the failure, use Result. If the failure means "something is fundamentally broken," throw.

### ESLint Rule: `no-throw-in-domain-code`

Domain functions should return Result, not throw. This rule bans `throw` in files under `src/domain/`, `src/services/`, and `src/use-cases/`.

```js
// rules/no-throw-in-domain-code.js
export const noThrowInDomainCodeRule = {
  meta: {
    type: "suggestion",
    docs: { description: "Domain functions must return Result<T, E>, not throw exceptions" },
    messages: {
      noThrow: "Do not throw in domain code. Return a Result<T, E> instead.",
    },
    schema: [],
  },
  create(context) {
    const filename = context.filename ?? context.getFilename();
    const isDomainCode =
      /\/src\/(domain|services|use-cases)\//.test(filename) &&
      !/\.(test|spec)\.(ts|tsx)$/.test(filename);
    if (!isDomainCode) return {};

    return {
      ThrowStatement(node) { context.report({ node, messageId: "noThrow" }); },
    };
  },
};
```

### TypeScript: Force Callers to Check

TypeScript's type narrowing makes Result safe by default. Accessing `.value` without checking `.ok` is a type error -- no additional config needed beyond `strictNullChecks: true`.

```typescript
const result = parseEmail(input);
// Type error: Property 'value' does not exist on type '{ ok: false; error: AppError }'
const email = result.value;

// Correct: narrow first
if (result.ok) {
  const email = result.value; // string
}
```

---

## 3. Interface-First Enforcement

### The Problem

When modules export concrete classes, consumers couple to implementation details. Testing requires mocking concrete constructors. Swapping implementations means touching every import site.

### The Pattern: Export Interface + Factory

```typescript
// Public contract -- this is what consumers depend on
export interface UserRepository {
  findById(id: string): Promise<Result<User>>;
  create(data: CreateUserInput): Promise<Result<User>>;
}

// Private implementation -- consumers never import this
class PostgresUserRepository implements UserRepository {
  constructor(private db: Database) {}
  async findById(id: string): Promise<Result<User>> { /* ... */ }
  async create(data: CreateUserInput): Promise<Result<User>> { /* ... */ }
}

// Factory function -- the only way to create an instance
export function createUserRepository(db: Database): UserRepository {
  return new PostgresUserRepository(db);
}
```

### ESLint Rule: `no-class-export`

```js
// rules/no-class-export.js
export const noClassExportRule = {
  meta: {
    type: "suggestion",
    docs: { description: "Classes should not be exported. Export interfaces and factory functions." },
    messages: {
      noClassExport: "Do not export classes directly. Export an interface + factory function.",
    },
    schema: [],
  },
  create(context) {
    const filename = context.filename ?? context.getFilename();
    if (/\.(test|spec)\.(ts|tsx)$/.test(filename)) return {};
    if (/\/(di|container|bootstrap)\.(ts|tsx)$/.test(filename)) return {};

    return {
      ExportNamedDeclaration(node) {
        if (node.declaration?.type === "ClassDeclaration") {
          context.report({ node, messageId: "noClassExport" });
        }
      },
      ExportDefaultDeclaration(node) {
        if (node.declaration?.type === "ClassDeclaration") {
          context.report({ node, messageId: "noClassExport" });
        }
      },
    };
  },
};
```

### ESLint Rule: `no-direct-instantiation`

Ban `new ServiceName()` in consuming code. All creation goes through factories or DI.

```js
// rules/no-direct-instantiation.js
const BANNED_CONSTRUCTORS = ["UserRepository", "OrderService", "PaymentGateway"];

export const noDirectInstantiationRule = {
  meta: {
    type: "problem",
    docs: { description: "Ban direct instantiation of service classes." },
    messages: {
      noDirectNew: "Do not use 'new {{ name }}()'. Use create{{ name }}() or DI instead.",
    },
    schema: [],
  },
  create(context) {
    const filename = context.filename ?? context.getFilename();
    if (/\.(test|spec)\.(ts|tsx)$/.test(filename)) return {};
    if (/\/(di|container|bootstrap|factory)\.(ts|tsx)$/.test(filename)) return {};

    return {
      NewExpression(node) {
        if (node.callee.type === "Identifier" && BANNED_CONSTRUCTORS.includes(node.callee.name)) {
          context.report({ node, messageId: "noDirectNew", data: { name: node.callee.name } });
        }
      },
    };
  },
};
```

### Architecture Boundary: Domain Purity

Domain packages export only types and pure functions. Enforce with dependency-cruiser (see Section 7 for full config):

```js
// .dependency-cruiser.cjs (partial)
{ name: "domain-no-infrastructure", severity: "error",
  from: { path: "^packages/domain/" },
  to: { path: ["^packages/database/", "^node_modules/(pg|redis|express|next)", "^node:fs"] } }
```

---

## 4. Command/Query Separation (CQS)

### The Problem

When a function both reads data and modifies state, it creates bugs that are hard to trace: caching a "query" that also updates a timestamp, retrying a "get" that also increments a counter.

### Naming Convention Enforcement

| Prefix | Type | Returns | Side Effects |
|--------|------|---------|--------------|
| `get*`, `find*`, `list*`, `count*`, `check*`, `is*`, `has*` | Query | Data | None |
| `create*`, `update*`, `delete*`, `set*`, `add*`, `remove*`, `send*` | Command | void/Result | Yes |

### ESLint Rule: Query Functions Must Not Mutate

```js
// rules/cqs-query-no-mutation.js
const QUERY_PREFIXES = ["get", "find", "list", "count", "check", "is", "has", "fetch"];
const MUTATION_METHODS = [
  "insert", "update", "delete", "remove", "set", "push", "pop", "shift",
  "unshift", "splice", "sort", "save", "destroy", "execute", "mutate", "send", "emit",
];

function isQueryFunction(name) {
  return QUERY_PREFIXES.some(
    (p) => name.startsWith(p) && name[p.length]?.toUpperCase() === name[p.length]
  );
}

export const cqsQueryNoMutationRule = {
  meta: {
    type: "problem",
    docs: { description: "Query functions (get/find/list/count) must not call mutation methods" },
    messages: {
      queryCallsMutation:
        "Query function '{{ funcName }}' calls mutation method '{{ methodName }}'. " +
        "Split into a separate command function.",
    },
    schema: [],
  },
  create(context) {
    let currentQueryFunction = null;

    function enterFunction(node) {
      const name = node.id?.name
        || (node.parent?.type === "VariableDeclarator" ? node.parent.id?.name : null)
        || (node.parent?.type === "MethodDefinition" ? node.parent.key?.name : null);
      if (name && isQueryFunction(name)) currentQueryFunction = name;
    }
    function exitFunction() { currentQueryFunction = null; }

    return {
      FunctionDeclaration: enterFunction, "FunctionDeclaration:exit": exitFunction,
      ArrowFunctionExpression: enterFunction, "ArrowFunctionExpression:exit": exitFunction,
      CallExpression(node) {
        if (!currentQueryFunction) return;
        const methodName = node.callee.property?.name ?? node.callee.name;
        if (methodName && MUTATION_METHODS.some((m) => methodName.startsWith(m))) {
          context.report({ node, messageId: "queryCallsMutation",
            data: { funcName: currentQueryFunction, methodName } });
        }
      },
    };
  },
};
```

### TypeScript: Readonly Return Types for Queries

```typescript
interface UserRepository {
  findById(id: string): Promise<Result<Readonly<User>>>;
  listByOrg(orgId: string): Promise<Result<ReadonlyArray<User>>>;
  create(data: CreateUserInput): Promise<Result<{ id: string }>>;
  delete(id: string): Promise<Result<void>>;
}
```

### CQS at the API Level

GET endpoints must be idempotent. Enforce with read-only database transactions for query routes:

```typescript
export function cqsGuard(req: Request, handler: () => Promise<Response>): Promise<Response> {
  if (req.method === "GET" || req.method === "HEAD" || req.method === "OPTIONS") {
    return withReadOnlyTransaction(handler);
  }
  return handler();
}
```

---

## 5. Single Responsibility via File Naming Conventions

### The Pattern: One Concept Per File

| Suffix | Purpose | Expected Exports |
|--------|---------|------------------|
| `*.repository.ts` | Data access | One interface + one factory |
| `*.service.ts` | Business logic orchestration | One interface + one factory |
| `*.handler.ts` | HTTP/event handler | One handler function |
| `*.validator.ts` | Input validation | Validation schemas + parse function |
| `*.mapper.ts` | Data transformation | Mapping functions for one entity |
| `*.types.ts` | Type definitions | Only types and interfaces |

### ESLint Rule: `max-exports-per-file`

```js
// rules/max-exports-per-file.js
export const maxExportsPerFileRule = {
  meta: {
    type: "suggestion",
    docs: { description: "Limit exports per file to enforce single responsibility" },
    messages: {
      tooManyExports: "File has {{ count }} exports (max {{ max }}). Consider splitting.",
    },
    schema: [{ type: "object", properties: {
      max: { type: "number", default: 5 },
      ignoreTypeExports: { type: "boolean", default: true },
    }, additionalProperties: false }],
  },
  create(context) {
    const { max = 5, ignoreTypeExports = true } = context.options[0] || {};
    let exportCount = 0;
    let lastNode = null;

    return {
      ExportNamedDeclaration(node) {
        if (ignoreTypeExports) {
          if (node.exportKind === "type") return;
          if (node.declaration?.type === "TSTypeAliasDeclaration" ||
              node.declaration?.type === "TSInterfaceDeclaration") return;
        }
        exportCount += node.specifiers?.length
          ? node.specifiers.filter((s) => !ignoreTypeExports || s.exportKind !== "type").length
          : 1;
        lastNode = node;
      },
      ExportDefaultDeclaration() { exportCount += 1; },
      "Program:exit"() {
        if (exportCount > max && lastNode) {
          context.report({ node: lastNode, messageId: "tooManyExports",
            data: { count: String(exportCount), max: String(max) } });
        }
      },
    };
  },
};
```

Configure with different limits per directory:

```js
export default [
  { files: ["src/**/*.ts"], rules: {
    "my-project/max-exports-per-file": ["error", { max: 5, ignoreTypeExports: true }] } },
  { files: ["src/**/*.types.ts", "src/**/types/index.ts"], rules: {
    "my-project/max-exports-per-file": "off" } },
  { files: ["src/**/index.ts"], rules: {
    "my-project/max-exports-per-file": "off" } },
];
```

---

## 6. Immutability by Default

### The Problem

Mutable state is the number one source of subtle bugs. A function receives an array, mutates it, and the caller's original data is corrupted.

### TypeScript Enforcement

```typescript
interface User {
  readonly id: string;
  readonly email: string;
  readonly name: string;
}

function getActiveUsers(): ReadonlyArray<User> { /* ... */ }

type DeepReadonly<T> = {
  readonly [K in keyof T]: T[K] extends object ? DeepReadonly<T[K]> : T[K];
};

const SUPPORTED_EXCHANGES = ["coinbase", "binance", "kraken"] as const;
type Exchange = (typeof SUPPORTED_EXCHANGES)[number];
```

### ESLint Rules: Immutability Suite

```js
import functionalPlugin from "eslint-plugin-functional";

export default [
  {
    plugins: { functional: functionalPlugin },
    rules: {
      "prefer-const": "error",
      "no-var": "error",
      "functional/no-let": ["error", { allowInForLoopInit: false }],
      "functional/immutable-data": ["error", {
        ignoreClasses: true,
        ignoreImmediateMutation: true,
        ignoreAccessorPattern: ["this.*", "module.*"],
      }],
      "functional/no-loop-statements": "warn",
    },
  },
  { files: ["**/*.test.ts", "**/*.spec.ts", "**/__tests__/**"], rules: {
    "functional/no-let": "off", "functional/immutable-data": "off",
    "functional/no-loop-statements": "off" } },
];
```

### When Mutation is OK

1. **Performance-critical inner loops** where allocation overhead matters.
2. **Builder patterns** where the object is mutable during construction but frozen before return.
3. **Local mutation** where the mutable variable never escapes the function scope.

Use an inline disable with a required explanation (enforced by `eslint-comments/require-description`):

```typescript
// eslint-disable-next-line functional/no-let -- performance: tight loop over 1M+ candles
let sum = 0;
for (const candle of candles) { sum += candle.volume; }
```

### Freezing in Tests

Shared fixtures should be frozen to catch accidental mutation:

```typescript
export const SAMPLE_USER = Object.freeze({
  id: "user-001", email: "test@example.com", name: "Test User",
}) as User;
// TypeError at runtime if any test accidentally mutates this
```

---

## 7. Dependency Direction Rules

### Layer Definitions

```
Domain        (types, pure functions, business rules)
  ^
Application   (use cases, orchestration, Result types)
  ^
Infrastructure (database, HTTP, file system, caches)
  ^
Presentation  (UI components, API routes, CLI)
```

Each layer can only depend on layers below it. Domain depends on nothing.

### dependency-cruiser Configuration

```bash
pnpm add -D dependency-cruiser
```

```js
// .dependency-cruiser.cjs
/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    { name: "domain-must-not-depend-on-application", severity: "error",
      from: { path: "^src/domain/" },
      to: { path: "^src/(application|infrastructure|presentation)/" } },
    { name: "domain-must-not-depend-on-infrastructure", severity: "error",
      from: { path: "^src/domain/" },
      to: { path: ["^src/infrastructure/",
        "^node_modules/(pg|mysql2|redis|ioredis|drizzle-orm|prisma)",
        "^node_modules/(express|fastify|koa|hono|next)",
        "^node:(fs|net|http|https)"] } },
    { name: "application-must-not-depend-on-infrastructure", severity: "error",
      from: { path: "^src/application/" },
      to: { path: ["^src/infrastructure/", "^node_modules/(pg|mysql2|redis|ioredis)"] } },
    { name: "application-must-not-depend-on-presentation", severity: "error",
      from: { path: "^src/application/" },
      to: { path: "^src/presentation/" } },
    { name: "packages-must-not-import-apps", severity: "error",
      from: { path: "^packages/" }, to: { path: "^apps/" } },
    { name: "no-circular-dependencies", severity: "error",
      from: {}, to: { circular: true } },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsPreCompilationDeps: true,
    tsConfig: { fileName: "tsconfig.json" },
  },
};
```

```json
{ "scripts": {
  "arch:check": "depcruise src --config .dependency-cruiser.cjs",
  "arch:graph": "depcruise src --config .dependency-cruiser.cjs --output-type dot | dot -T svg > dependency-graph.svg"
} }
```

### ESLint `no-restricted-imports` Per Directory

For simpler enforcement without dependency-cruiser:

```js
export default [
  { files: ["src/domain/**/*.ts"], rules: { "no-restricted-imports": ["error", {
    patterns: [
      { group: ["drizzle-orm*"], message: "Domain must not import database ORM" },
      { group: ["node:fs*", "node:net*", "node:http*"], message: "Domain must not import Node I/O" },
      { group: ["../infrastructure/*", "../presentation/*"], message: "Domain can only import from domain" },
    ] }] } },
  { files: ["src/application/**/*.ts"], rules: { "no-restricted-imports": ["error", {
    patterns: [
      { group: ["../infrastructure/*"], message: "Application must depend on interfaces, not infrastructure" },
      { group: ["../presentation/*"], message: "Application must not import presentation code" },
    ] }] } },
];
```

---

## 8. API Surface Minimization

### Package `exports` Field: The Definitive Public Surface

If a path is not listed in `exports`, it cannot be imported by consumers.

```json
{ "name": "@scope/user-service",
  "exports": {
    ".": { "types": "./dist/index.d.ts", "default": "./dist/index.js" },
    "./testing": { "types": "./dist/testing.d.ts", "default": "./dist/testing.js" }
  } }
```

### `@internal` JSDoc Tag

Mark symbols exported for technical reasons (e.g., used by sibling packages) but not intended for external consumers:

```typescript
/** @internal Exported for use by @scope/user-api only. */
export function _buildUserQuery(filters: UserFilters): QueryBuilder { /* ... */ }
```

### api-extractor for Public API Validation

```bash
pnpm add -D @microsoft/api-extractor
```

```json
// api-extractor.json
{ "$schema": "https://developer.microsoft.com/json-schemas/api-extractor/v7/api-extractor.schema.json",
  "mainEntryPointFilePath": "<projectFolder>/dist/index.d.ts",
  "apiReport": { "enabled": true, "reportFolder": "<projectFolder>/api-reports/" },
  "dtsRollup": { "enabled": true, "untrimmedFilePath": "<projectFolder>/dist/index.d.ts" },
  "messages": { "extractorMessageReporting": {
    "ae-missing-release-tag": { "logLevel": "warning" },
    "ae-forgotten-export": { "logLevel": "error" } } } }
```

The `ae-forgotten-export` message fires when a public API references a type that is not explicitly exported.

### ESLint Rule: Warn on Re-Export Everything

Barrel files that re-export everything (`export * from`) make it impossible to know what is public.

```js
{ files: ["src/**/index.ts"], rules: {
  "no-restricted-syntax": ["warn", {
    selector: "ExportAllDeclaration:not([exported])",
    message: "Avoid 'export * from'. Use explicit named exports to control the public API surface.",
  }] } }
```

---

## 9. Nullability Rules

### TypeScript Configuration: Non-Negotiable Settings

```json
{ "compilerOptions": {
  "strict": true,
  "strictNullChecks": true,
  "noUncheckedIndexedAccess": true,
  "exactOptionalPropertyTypes": true
} }
```

- **`strictNullChecks`**: `null`/`undefined` not assignable to other types. Must use `string | null` explicitly.
- **`noUncheckedIndexedAccess`**: `arr[0]` returns `T | undefined`. Catches out-of-bounds at compile time.
- **`exactOptionalPropertyTypes`**: `{ name?: string }` means absent or `string` -- cannot assign `undefined`.

### Ban Non-Null Assertion (`!`)

```js
{ rules: { "@typescript-eslint/no-non-null-assertion": "error" } }
// Allow in test files:
{ files: ["**/*.test.ts", "**/*.spec.ts"],
  rules: { "@typescript-eslint/no-non-null-assertion": "off" } }
```

### Pattern: Explicit Narrowing over Assertion

```typescript
// Bad
const user = users.find((u) => u.id === id)!;

// Good
const user = users.find((u) => u.id === id);
if (!user) return err(notFound("User", id));
// TypeScript narrows: user is User here
```

### Custom Rule: Ban Dangerous Nullish Fallbacks

`?? 0` and `?? ""` often mask missing data that should be an error:

```js
// rules/no-nullish-zero-fallback.js
export const noNullishZeroFallbackRule = {
  meta: {
    type: "problem",
    docs: { description: "Ban ?? 0, ?? '', and ?? [] as they often mask missing data" },
    messages: { nullishZero: "Using ?? with a zero/empty fallback can mask missing data. Handle null explicitly." },
    schema: [],
  },
  create(context) {
    return {
      LogicalExpression(node) {
        if (node.operator !== "??") return;
        const r = node.right;
        if ((r.type === "Literal" && (r.value === 0 || r.value === "")) ||
            (r.type === "ArrayExpression" && r.elements.length === 0)) {
          context.report({ node, messageId: "nullishZero" });
        }
      },
    };
  },
};
```

### Combined Nullability Ruleset

```js
{ rules: {
  "@typescript-eslint/no-non-null-assertion": "error",
  "@typescript-eslint/no-unnecessary-condition": "error",
  "@typescript-eslint/prefer-nullish-coalescing": "error",
  "@typescript-eslint/strict-boolean-expressions": ["error", {
    allowString: false, allowNumber: false, allowNullableObject: true,
    allowNullableBoolean: false, allowNullableString: false,
    allowNullableNumber: false, allowAny: false }],
  "my-project/no-nullish-zero-fallback": "warn",
} }
```

---

## 10. Design Rules Per Language

The principles above are universal. The enforcement mechanisms differ by language.

### Python

```toml
# pyproject.toml -- mypy strict
[tool.mypy]
strict = true
disallow_untyped_defs = true
no_implicit_optional = true

# import-linter -- architecture enforcement
[tool.importlinter]
root_packages = ["myapp"]
[[tool.importlinter.contracts]]
name = "Domain must not import infrastructure"
type = "forbidden"
source_modules = ["myapp.domain"]
forbidden_modules = ["myapp.infrastructure", "sqlalchemy", "redis", "httpx"]

[[tool.importlinter.contracts]]
name = "Layered architecture"
type = "layers"
layers = ["myapp.presentation", "myapp.infrastructure", "myapp.application", "myapp.domain"]

# pylint design limits
[tool.pylint.design]
max-args = 5
max-locals = 15
max-branches = 12
max-attributes = 7
```

Immutability: use `@dataclass(frozen=True)`. Result pattern: use the `returns` library or a simple `Ok`/`Err` discriminated union with frozen dataclasses.

### Go

```yaml
# .golangci.yml
linters:
  enable: [errcheck, govet, staticcheck, gocritic, revive, depguard, cyclop, gocognit]
linters-settings:
  depguard:
    rules:
      domain:
        files: ["**/domain/**"]
        deny:
          - { pkg: "database/sql", desc: "Domain must not import database packages" }
          - { pkg: "net/http", desc: "Domain must not import HTTP packages" }
  cyclop:
    max-complexity: 15
  revive:
    rules:
      - { name: max-public-structs, severity: warning, arguments: [3] }
```

Compile-time interface compliance: `var _ Repository = (*UserRepository)(nil)`. Error handling: `errcheck ./...` ensures all errors are handled. Immutability: return values not pointers for read-only data.

### Rust

Rust enforces most principles at the language level. The compiler IS the linter.

```toml
# Cargo.toml
[lints.clippy]
pedantic = { level = "warn", priority = -1 }

# clippy.toml
cognitive-complexity-threshold = 15
too-many-arguments-threshold = 5
```

`Result<T, E>` is built-in. Immutability is the default (`let` is immutable, `let mut` required for mutation). `#[must_use]` makes ignoring return values a warning. Module visibility enforces architecture boundaries. `#![deny(unsafe_code)]` bans unsafe blocks.

### Java

```java
// ArchUnit: architecture rules as tests
@Test void layeredArchitecture() {
    Architectures.layeredArchitecture().consideringAllDependencies()
        .layer("Domain").definedBy("com.example.domain..")
        .layer("Application").definedBy("com.example.application..")
        .layer("Infrastructure").definedBy("com.example.infrastructure..")
        .whereLayer("Domain").mayNotAccessAnyLayer()
        .whereLayer("Application").mayOnlyAccessLayers("Domain")
        .check(classes);
}

@Test void servicesMustBeInterfaces() {
    ArchRuleDefinition.classes().that().resideInAPackage("com.example.application..")
        .and().haveSimpleNameEndingWith("Service")
        .should().beInterfaces()
        .check(classes);
}
```

Nullability: NullAway + Error-Prone compiler plugin. All parameters are `@NonNull` by default; use `@Nullable` explicitly. Error-prone catches `ReturnValueIgnored`, `ImmutableEnumChecker`, `MustBeClosedChecker` at compile time.

---

## Summary: The Enforcement Matrix

| Principle | TypeScript | ESLint | dependency-cruiser | CI Script |
|-----------|-----------|--------|-------------------|-----------|
| Typed Errors | Discriminated unions | `no-untyped-errors` | -- | -- |
| Result Pattern | `Result<T, E>` type | `no-throw-in-domain-code` | -- | -- |
| Interface-First | Export interfaces | `no-class-export`, `no-direct-instantiation` | `domain-no-infrastructure` | -- |
| CQS | `Readonly<T>` returns | `cqs-query-no-mutation` | -- | -- |
| Single Responsibility | -- | `max-exports-per-file` | -- | -- |
| Immutability | `readonly`, `as const` | `functional/no-let`, `functional/immutable-data` | -- | -- |
| Dependency Direction | -- | `no-restricted-imports` | Layer rules | `pnpm arch:check` |
| API Surface | `exports` field | `no-restricted-syntax` (export *) | -- | api-extractor |
| Nullability | `strictNullChecks`, `noUncheckedIndexedAccess` | `no-non-null-assertion`, `strict-boolean-expressions` | -- | -- |

Every row in this matrix is a principle that most teams agree on but few enforce automatically. The tools exist. The configurations are straightforward. The only reason these rules are not enforced in most codebases is that nobody set them up.

Set them up.
