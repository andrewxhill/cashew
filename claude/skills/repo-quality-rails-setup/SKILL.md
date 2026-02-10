---
name: repo-quality-rails-setup
description: >
  Comprehensive quality infrastructure setup for TypeScript monorepos and any software project.
  Sets up deterministic quality gates that make it impossible for broken code to advance through
  the pipeline. Use this skill whenever someone wants to: set up a new monorepo, add quality gates,
  configure pre-commit or pre-push hooks, set up CI pipelines, add test coverage enforcement,
  configure linting/formatting, add architecture boundary checks, set up changeset workflows,
  add migration safety checks, or turn an existing codebase into a production-grade system with
  ungameable quality enforcement. Also use when someone says things like "add hooks", "set up CI",
  "enforce code quality", "add linting", "configure testing", "monorepo setup", or "prevent bad
  code from shipping". Even if they just mention wanting "better code quality" or "stop bugs from
  reaching production", this is the right skill.
---

# Repo Quality Rails Setup

This skill sets up deterministic, ungameable quality infrastructure that prevents broken code from
advancing through any stage of the development pipeline. The philosophy: every quality check is a
hard gate that blocks forward progress when violated. Warnings are for things humans should notice;
errors are for things the system must enforce.

## How This Skill Works

There are two modes based on what the repo needs:

1. **TypeScript monorepo** (prescriptive): Exact tools, exact configs, exact rules. Read
   `references/typescript-monorepo.md` for the complete setup.

2. **Any language** (architectural): Same gate structure and hook infrastructure, but with
   guidance on choosing equivalent tools. Read `references/universal-gates.md`.

Both modes share the same three-layer enforcement model:

```
Layer 1: Pre-commit     -> Fast feedback on staged files (seconds)
Layer 2: Pre-push       -> Full verification before code leaves the machine (minutes)
Layer 3: CI             -> Authoritative verification on clean infrastructure (minutes)
```

The rule: **if CI would reject it, a local gate should have caught it first.** Developers should
never be surprised by CI failures. The pre-push hook mirrors CI exactly.

## Decision: TypeScript or Universal?

Before doing anything, determine the repo's primary language and structure:

- If the repo has `tsconfig.json` or `package.json` with TypeScript dependencies -> **TypeScript mode**
- If setting up a new project and the user wants TypeScript -> **TypeScript mode**
- Otherwise -> **Universal mode**

For TypeScript mode, also determine:
- **Monorepo or single-package?** Look for `pnpm-workspace.yaml`, `lerna.json`, `turbo.json`, or
  multiple `package.json` files. If monorepo, the full setup applies. If single-package, skip the
  Turbo orchestration and workspace-specific boundary rules.

## The Three Layers

### Layer 1: Pre-Commit Gates

Pre-commit gates run on staged files only and must complete in seconds. Their job is immediate
feedback on the code being committed.

**Hard failures** (block the commit):
1. **Auto-formatting** - Fix formatting on staged files automatically (Prettier for TS)
2. **Linting** - Static analysis on affected packages
3. **Type checking** - Type safety on affected packages
4. **Secret detection** - Scan for hardcoded credentials
5. **Stub/mock file detection** - Prevent test doubles in production code
6. **Lock file sync** - Ensure dependency lock file matches manifests
7. **Migration safety** - Lint SQL migrations for dangerous patterns (if applicable)
8. **Changeset enforcement** - Require version bump coordination for publishable packages
9. **Coverage gaming prevention** - Block attempts to exclude source files from coverage metrics
10. **Documentation location enforcement** - Keep docs in designated locations

**Warnings** (inform but don't block):
11. **Console.log detection** - Flag forgotten debug statements
12. **`any` type detection** - Flag type safety gaps (TS only)
13. **Test assertion density** - Flag tests with too few assertions

Read `references/pre-commit-gates.md` for implementation details.

### Layer 2: Pre-Push Gates

Pre-push gates run the full verification suite. They mirror CI exactly so developers are never
surprised by remote failures.

**Sequence:**
1. Check remote main is not ahead (prevent merge conflicts)
2. Check for uncommitted changes (prevent dirty-state false positives)
3. Detect changed packages and scope checks (monorepo optimization)
4. Format check
5. Lint (scoped to changed packages)
6. SQL migration linting (if database package changed)
7. Type check (scoped to changed packages)
8. Unit tests with coverage (scoped)
9. Build all (verifies compilation)
10. Integration tests (if database available)
11. Schema drift detection (if database available)

Read `references/pre-push-gates.md` for implementation details.

### Layer 3: CI Pipeline

CI runs on clean infrastructure with no local state. It is the authoritative source of truth.

**Parallel jobs:**
- Lint + type-check
- Build (with artifact upload)
- Migration dry-run (against fresh database container)
- Unit tests (sharded across N workers)
- Test coverage (after unit tests pass)

**Sequential gates (main branch only):**
- Production migration (after all checks pass)
- Post-deploy smoke tests

Read `references/ci-pipeline.md` for implementation details.

## Design Quality

Beyond catching broken code, quality gates can enforce design health — preventing the gradual
erosion that turns clean codebases into unmaintainable ones. These gates measure structural
properties of the code and fail when thresholds are exceeded.

**Design metrics as gates.** Cognitive complexity, fan-in/fan-out coupling, file and function size
limits, export surface area, dependency depth, and circular dependency detection — all enforced as
hard failures in pre-commit or pre-push hooks. Read `references/design-metrics.md` for thresholds
and ESLint rule configurations.

**Mutation testing.** Coverage only measures whether lines executed during tests. Mutation testing
verifies tests actually *detect* bugs by introducing small changes (mutants) and checking that at
least one test fails. This is the ultimate test quality gate — a codebase with 95% coverage but
weak assertions will have a low mutation score. Read `references/mutation-testing.md` for Stryker
setup and ratcheting strategy.

**Architecture analysis.** Dependency graph visualization with graph metrics (instability,
abstractness, distance from main sequence), API surface tracking across versions, and architecture
erosion detection via baseline comparison. Read `references/architecture-analysis.md` for tooling
and CI integration.

**Refactoring playbook.** When inheriting an existing codebase, you need an assessment strategy:
churn-times-complexity priority algorithm, ratcheting thresholds that only tighten, and strangler
fig patterns for incremental migration. Read `references/refactoring-playbook.md` for assessment
scripts and step-by-step workflows.

**Design principles as rules.** Error taxonomy enforcement (no stringly-typed errors), Result
pattern for expected failures, interface-first design, CQS, and immutability by default — encoded
as deterministic ESLint rules that fail the build. Read `references/design-patterns-as-rules.md`
for rule definitions and examples.

| Reference | When to read |
|-----------|-------------|
| `references/design-metrics.md` | Setting up complexity, coupling, and size limit gates |
| `references/mutation-testing.md` | Setting up Stryker or equivalent mutation testing |
| `references/architecture-analysis.md` | Dependency graph analysis, API surface tracking |
| `references/refactoring-playbook.md` | Assessing and incrementally improving existing codebases |
| `references/design-patterns-as-rules.md` | Encoding design principles as enforceable lint rules |

## TypeScript Monorepo: The Full Stack

For TypeScript monorepos, read these references in order:

| Reference | What It Covers |
|-----------|---------------|
| `references/typescript-monorepo.md` | Workspace structure, package patterns, Turbo pipeline |
| `references/eslint-architecture.md` | Shared ESLint config, boundary rules, custom rules |
| `references/test-infrastructure.md` | Vitest setup, coverage thresholds, assertion density |
| `references/pre-commit-gates.md` | Husky + lint-staged + custom gate scripts |
| `references/pre-push-gates.md` | Full verification pipeline |
| `references/ci-pipeline.md` | GitHub Actions / CI service configuration |
| `references/database-safety.md` | Migration linting, schema drift, SQL safety |
| `references/changeset-workflow.md` | Version management for publishable packages |
| `references/code-duplication.md` | Copy-paste detection and enforcement |
| `references/design-metrics.md` | Complexity, coupling, and size limit gates |
| `references/mutation-testing.md` | Stryker mutation testing setup and ratcheting |
| `references/architecture-analysis.md` | Dependency graph analysis, API surface tracking |
| `references/refactoring-playbook.md` | Codebase assessment and incremental improvement |
| `references/design-patterns-as-rules.md` | Design principles encoded as lint rules |

## Universal Mode: Any Language

For non-TypeScript repos, read `references/universal-gates.md` which maps every quality gate
to its language-agnostic equivalent and provides guidance on tool selection.

## Anti-Gaming Philosophy

The most important design principle: **quality gates must be ungameable.** This means:

1. **No `--no-verify`** - Hooks cannot be bypassed. If they fail, fix the underlying issue.
2. **No coverage exclusions for source files** - The pre-commit hook detects attempts to add
   source files to coverage.exclude and blocks the commit.
3. **No disabling lint rules without explanation** - ESLint comments require descriptions.
4. **No stub files in production** - Detected and blocked at commit time.
5. **No shadow imports** - Package boundaries are enforced by lint rules.
6. **No manual database changes** - All schema changes go through the migration pipeline.
7. **Warnings exist for human judgment** - But errors are non-negotiable.

The goal is not to make developers' lives harder. It's to make broken code impossible to ship
by accident. Every gate that exists prevents a class of bugs that has actually happened.
