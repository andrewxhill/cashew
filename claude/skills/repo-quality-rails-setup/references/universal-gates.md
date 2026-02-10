# Universal Quality Gates for Any Language

This reference maps every quality gate from the TypeScript monorepo setup to its language-agnostic equivalent. The three-layer structure (pre-commit, pre-push, CI) is identical regardless of language. What changes is the tooling.

## 1. Philosophy

Quality gates exist to catch problems before they compound. The further a bug travels from the developer's machine, the more expensive it is to fix. A type error caught at commit time costs seconds. The same error caught in production costs hours.

The gates are the same regardless of language:

1. **Formatting** -- eliminate style debates, auto-fix on commit
2. **Linting** -- catch bugs and anti-patterns statically
3. **Type checking** -- verify correctness at compile time (or its equivalent)
4. **Testing with coverage** -- prove the code works, measure completeness
5. **Build verification** -- confirm the artifact compiles and packages correctly
6. **Secret detection** -- prevent credentials from entering the repository
7. **Dependency management** -- keep lock files in sync, deduplicate

Every repo, in every language, should have all seven. The tools differ. The discipline does not.

## 2. Formatting

Every language has a canonical formatter. The correct answer is almost always "use the one the community agreed on." Do not invent your own style. Do not argue about tabs vs. spaces. Let the tool decide and move on.

| Language | Tool | Config File | Install |
|----------|------|-------------|---------|
| TypeScript/JavaScript | Prettier | `.prettierrc` | `pnpm add -D prettier` |
| Python | Black + isort (or Ruff format) | `pyproject.toml` | `pip install black isort` or `pip install ruff` |
| Go | gofmt / goimports | (built-in, zero config) | Included with Go toolchain |
| Rust | rustfmt | `rustfmt.toml` | `rustup component add rustfmt` |
| Java/Kotlin | google-java-format / ktlint | `.editorconfig` | Gradle/Maven plugin |
| C/C++ | clang-format | `.clang-format` | `apt install clang-format` or `brew install clang-format` |
| Ruby | RuboCop (formatting mode) | `.rubocop.yml` | `gem install rubocop` |
| Swift | swift-format | `.swift-format` | `brew install swift-format` |
| Elixir | mix format | `.formatter.exs` | Built into Mix |

**The principle**: Formatting is auto-fixed on commit via pre-commit hook. Never argue about style. If two developers disagree about formatting, neither of them gets to decide -- the formatter decides.

**Pre-commit integration**: The formatter runs on staged files only, rewrites them in place, and re-stages the result. The developer never needs to think about formatting manually.

```bash
# Generic pattern for any language's pre-commit formatting step:
# 1. Get staged files matching the language extension
# 2. Run the formatter in write mode
# 3. Re-stage the formatted files
STAGED=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$')
if [ -n "$STAGED" ]; then
  echo "$STAGED" | xargs black --quiet
  echo "$STAGED" | xargs isort --quiet
  echo "$STAGED" | xargs git add
fi
```

### Example configurations

**Python (pyproject.toml):**

```toml
[tool.black]
line-length = 100
target-version = ["py312"]

[tool.isort]
profile = "black"
line_length = 100
```

**Rust (rustfmt.toml):**

```toml
edition = "2021"
max_width = 100
tab_spaces = 4
use_field_init_shorthand = true
```

**Go**: No configuration needed. `gofmt` is opinionated by design. Run `goimports` for automatic import management:

```bash
goimports -w $(git diff --cached --name-only --diff-filter=ACM | grep '\.go$')
```

## 3. Linting

Static analysis catches bugs before runtime. Linters enforce code quality rules, detect unused variables, flag suspicious patterns, and prevent common mistakes that compilers and type checkers miss.

| Language | Tool | Config File | Install |
|----------|------|-------------|---------|
| TypeScript/JavaScript | ESLint (flat config) | `eslint.config.mjs` | `pnpm add -D eslint` |
| Python | Ruff (replaces flake8 + pylint + isort + pyflakes) | `pyproject.toml` | `pip install ruff` |
| Go | golangci-lint | `.golangci.yml` | `go install github.com/golangci-lint/golangci-lint/cmd/golangci-lint@latest` |
| Rust | clippy | (built-in) | `rustup component add clippy` |
| Java | SpotBugs / ErrorProne | `build.gradle` | Gradle/Maven plugin |
| Kotlin | detekt | `detekt.yml` | Gradle plugin |
| Ruby | RuboCop | `.rubocop.yml` | `gem install rubocop` |
| Swift | SwiftLint | `.swiftlint.yml` | `brew install swiftlint` |
| Elixir | Credo | `.credo.exs` | `mix deps.get` |
| C/C++ | clang-tidy | `.clang-tidy` | `apt install clang-tidy` |

**The principle**: Lint errors are hard failures. No committing code with lint errors. If a rule produces too many false positives, disable that specific rule with justification in the config file -- do not skip the linter entirely.

**Recommended strictness**: Enable the strictest preset available and selectively disable rules that do not apply, rather than starting permissive and hoping to tighten later. You never tighten later.

### Example configurations

**Python (pyproject.toml with Ruff):**

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
  "E",    # pycodestyle errors
  "W",    # pycodestyle warnings
  "F",    # pyflakes
  "I",    # isort
  "N",    # pep8-naming
  "UP",   # pyupgrade
  "B",    # flake8-bugbear
  "SIM",  # flake8-simplify
  "TCH",  # flake8-type-checking
  "RUF",  # ruff-specific rules
  "S",    # flake8-bandit (security)
  "C4",   # flake8-comprehensions
  "DTZ",  # flake8-datetimez
  "T20",  # flake8-print (no print statements)
  "PT",   # flake8-pytest-style
]
ignore = []

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # Allow assert in tests
```

**Go (.golangci.yml):**

```yaml
run:
  timeout: 5m

linters:
  enable:
    - errcheck
    - govet
    - staticcheck
    - unused
    - gosimple
    - ineffassign
    - typecheck
    - gofmt
    - goimports
    - revive
    - misspell
    - unconvert
    - unparam
    - prealloc
    - depguard

linters-settings:
  depguard:
    rules:
      main:
        deny:
          - pkg: "io/ioutil"
            desc: "deprecated: use io and os packages instead"
  revive:
    rules:
      - name: exported
      - name: var-naming
      - name: error-return
```

**Rust**: Clippy runs with `cargo clippy`. For strictest checking:

```bash
cargo clippy -- -D warnings -W clippy::pedantic
```

## 4. Type Checking

Static type verification catches entire categories of bugs at compile time. For languages with built-in type systems, this is part of the compilation step. For gradually-typed languages, it requires explicit opt-in and discipline.

| Language | Tool | Config | Notes |
|----------|------|--------|-------|
| TypeScript | `tsc --noEmit` | `tsconfig.json` | Built into language |
| Python | mypy or pyright | `pyproject.toml` or `pyrightconfig.json` | Requires type annotations |
| Go | `go vet` + staticcheck | `.golangci.yml` | Built-in, plus third-party analyzers |
| Rust | `cargo check` | (built-in) | Part of the compiler; also catches borrow checker errors |
| Java | javac (compile-time) | (built-in) | Generics + nullability annotations for stronger checks |
| Kotlin | kotlinc (compile-time) | (built-in) | Null safety built into the type system |
| C# | csc / dotnet build | `.csproj` with `<Nullable>enable</Nullable>` | Nullable reference types for stricter checking |
| Swift | swiftc (compile-time) | (built-in) | Strong type system with optionals |

**The principle**: Strict mode always. No escape hatches without justification.

- **TypeScript**: `"strict": true`, no `any` without a comment explaining why
- **Python**: `strict = true` in mypy, no `# type: ignore` without a comment explaining why
- **Go**: `go vet` on every build, `staticcheck` for deeper analysis
- **Rust**: The compiler is already strict; do not use `unsafe` without justification

### Example configurations

**Python (pyproject.toml with mypy):**

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

**Python (pyrightconfig.json):**

```json
{
  "typeCheckingMode": "strict",
  "pythonVersion": "3.12",
  "reportMissingTypeStubs": "warning",
  "reportUnusedImport": "error",
  "reportUnusedVariable": "error"
}
```

## 5. Testing with Coverage Enforcement

Tests prove the code works. Coverage thresholds prove you tested enough of it. Both are required.

| Language | Test Runner | Coverage Tool | Recommended Threshold |
|----------|------------|---------------|----------------------|
| TypeScript | Vitest | @vitest/coverage-v8 | 90% all metrics |
| Python | pytest | pytest-cov | 90% |
| Go | `go test` | `go test -cover` | 80% (Go community convention) |
| Rust | `cargo test` | cargo-tarpaulin or cargo-llvm-cov | 80% |
| Java | JUnit 5 | JaCoCo | 80% |
| Kotlin | JUnit 5 / Kotest | JaCoCo / Kover | 80% |
| Ruby | RSpec / Minitest | SimpleCov | 90% |
| C# | xUnit / NUnit | coverlet | 80% |
| Elixir | ExUnit | excoveralls | 90% |
| Swift | XCTest | Xcode coverage | 80% |

**The principle**: Coverage thresholds are enforced in CI. Dropping below the threshold fails the build. There is no "we will add tests later." Later never comes.

**Anti-gaming**: The pre-commit hook detects attempts to exclude source files from coverage configuration. Only test files, type definitions, generated code, and third-party code may be excluded. Excluding your own source files to meet the threshold is cheating and is blocked.

```bash
# Generic pre-commit check for coverage gaming
# Adapt the config file name for your language
COVERAGE_CONFIGS=$(git diff --cached --name-only | grep -E '(vitest\.config|pytest\.ini|pyproject\.toml|\.coveragerc|jacoco.*\.xml|build\.gradle)' || true)
if [ -n "$COVERAGE_CONFIGS" ]; then
  GAMING=$(git diff --cached -- $COVERAGE_CONFIGS | grep -E '^\+.*exclude.*src/' | grep -v 'test' | grep -v 'node_modules' || true)
  if [ -n "$GAMING" ]; then
    echo "Suspicious coverage exclusion detected. Do not exclude source files."
    exit 1
  fi
fi
```

### Example configurations

**Python (pyproject.toml with pytest-cov):**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=90"

[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "*/migrations/*"]

[tool.coverage.report]
fail_under = 90
show_missing = true
exclude_lines = [
  "pragma: no cover",
  "if TYPE_CHECKING:",
  "if __name__ == .__main__.",
]
```

**Go**: Coverage is built into the test runner:

```bash
go test -coverprofile=coverage.out -covermode=atomic ./...
go tool cover -func=coverage.out

# Enforce threshold in CI
COVERAGE=$(go tool cover -func=coverage.out | grep total | awk '{print substr($3, 1, length($3)-1)}')
if (( $(echo "$COVERAGE < 80.0" | bc -l) )); then
  echo "Coverage $COVERAGE% is below 80% threshold"
  exit 1
fi
```

**Rust (with cargo-tarpaulin):**

```bash
cargo tarpaulin --fail-under 80 --out Html --out Lcov
```

**Java (build.gradle with JaCoCo):**

```groovy
jacocoTestCoverageVerification {
    violationRules {
        rule {
            limit {
                minimum = 0.80
            }
        }
    }
}

check.dependsOn jacocoTestCoverageVerification
```

### Test assertion density

Regardless of language, watch for thin tests -- files with many lines but few assertions. A 200-line test file with two assertions is likely testing setup code, not behavior.

```bash
# Generic assertion density check (adapt the assertion pattern)
# Python: assert / assertEqual / assertTrue / assertRaises
# Go: t.Error / t.Fatal / require. / assert.
# Rust: assert! / assert_eq! / assert_ne!
for testfile in $(git diff --cached --name-only | grep -E '(test_.*\.py|_test\.go|.*_test\.rs)'); do
  LINES=$(wc -l < "$testfile" | tr -d ' ')
  ASSERTS=$(grep -cE '(assert|expect|require\.|t\.Error|t\.Fatal)' "$testfile" 2>/dev/null || echo 0)
  if [ "$LINES" -gt 50 ] && [ "$ASSERTS" -lt 3 ]; then
    echo "Warning: Low assertion density in $testfile ($LINES lines, $ASSERTS assertions)"
  fi
done
```

## 6. Secret Detection

Secret detection is universal. It does not matter what language you write -- an API key committed to Git is a security incident regardless of whether it is in a Python file or a Rust file.

### Tools

| Tool | Type | Notes |
|------|------|-------|
| gitleaks | Pre-commit + CI | Comprehensive, configurable, actively maintained |
| detect-secrets (Yelp) | Pre-commit | Baseline-aware, good for existing repos with legacy secrets |
| truffleHog | CI scanner | Deep history scanning |
| Custom regex in hook | Pre-commit | Lightweight, no external dependency |

### Recommended: gitleaks

Install via pre-commit framework or standalone:

```bash
# Standalone
brew install gitleaks  # macOS
# or download from https://github.com/gitleaks/gitleaks/releases

# Verify
gitleaks detect --source . --no-git
```

**`.gitleaks.toml` configuration:**

```toml
[allowlist]
description = "Global allowlist"
paths = [
  '''\.test\.''',
  '''__tests__''',
  '''testdata''',
  '''fixtures''',
  '''\.example''',
  '''\.template''',
]
```

### Fallback: simple regex in pre-commit hook

If you cannot install external tools, a regex-based check catches the most common patterns:

```bash
STAGED_DIFF=$(git diff --cached -U0)
SECRETS=$(echo "$STAGED_DIFF" \
  | grep -inE '^\+.*(password|secret|api[_-]?key|token|credential|private[_-]?key)\s*[:=]\s*["\x27][^"\x27]{8,}' \
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
  echo "Possible secrets detected in staged changes:"
  echo "$SECRETS" | head -10
  echo "NEVER commit real credentials to the repository."
  exit 1
fi
```

### High-entropy string detection

Beyond pattern matching, scan for high-entropy strings that look like API keys or tokens:

```bash
# gitleaks handles this automatically
# For custom checks, look for base64-like strings of 20+ characters
grep -nE '[A-Za-z0-9+/=]{40,}' "$file"
```

**The principle**: Secret detection is a hard failure on commit. No exceptions. If the detector has a false positive, add it to the allowlist with an explanation -- do not disable the check.

## 7. Pre-Commit Hook Framework

For non-JavaScript/TypeScript repos, use the `pre-commit` framework (https://pre-commit.com). It is language-agnostic, manages tool versions, and has a rich ecosystem of hooks.

### Installation

```bash
pip install pre-commit
# or
brew install pre-commit
```

### .pre-commit-config.yaml

```yaml
repos:
  # Universal hooks (all languages)
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-toml
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: detect-private-key
      - id: check-merge-conflict
      - id: no-commit-to-branch
        args: ['--branch', 'main']

  # Secret detection
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks

  # Python
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff          # linting
        args: ['--fix']
      - id: ruff-format   # formatting

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: []  # add stubs here

  # Go
  - repo: https://github.com/dnephin/pre-commit-golang
    rev: v0.5.1
    hooks:
      - id: go-fmt
      - id: go-vet
      - id: go-imports

  - repo: https://github.com/golangci/golangci-lint
    rev: v1.59.0
    hooks:
      - id: golangci-lint

  # Rust
  - repo: https://github.com/doublify/pre-commit-rust
    rev: v1.0
    hooks:
      - id: fmt
      - id: cargo-check
      - id: clippy
```

### Activating hooks

```bash
# Install hooks into .git/hooks/
pre-commit install
pre-commit install --hook-type pre-push

# Run against all files (useful for first-time setup)
pre-commit run --all-files

# Update hook versions
pre-commit autoupdate
```

### For JavaScript/TypeScript repos

Use Husky + lint-staged instead. See the pre-commit-gates reference for the complete setup. The `pre-commit` framework and Husky serve the same purpose -- do not use both in the same repo.

## 8. Pre-Push Hook

The pre-push hook is the last line of defense before code leaves the developer's machine. It runs the full verification suite. The structure is identical regardless of language.

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== PRE-PUSH: Running full verification ==="

# ── CHECK 1: Remote main not ahead ────────────────────────
git fetch origin main --quiet 2>/dev/null || true
BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
if [ "$BEHIND" -gt 0 ]; then
  echo "origin/main is $BEHIND commits ahead. Rebase before pushing."
  echo "  Fix: git fetch origin main && git rebase origin/main"
  exit 1
fi

# ── CHECK 2: No uncommitted changes ──────────────────────
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Uncommitted changes detected. Commit or stash before pushing."
  exit 1
fi

# ── CHECK 3: Format check ────────────────────────────────
echo "--- Format check ---"
# Python:  ruff format --check .
# Go:      test -z "$(gofmt -l .)"
# Rust:    cargo fmt --check
# Java:    ./gradlew spotlessCheck
FORMAT_CMD="your-format-check-command-here"
$FORMAT_CMD || { echo "Format check failed. Run your formatter."; exit 1; }

# ── CHECK 4: Lint ─────────────────────────────────────────
echo "--- Lint ---"
# Python:  ruff check .
# Go:      golangci-lint run ./...
# Rust:    cargo clippy -- -D warnings
# Java:    ./gradlew spotbugsMain
LINT_CMD="your-lint-command-here"
$LINT_CMD || { echo "Lint failed."; exit 1; }

# ── CHECK 5: Type check (if applicable) ──────────────────
echo "--- Type check ---"
# Python:  mypy src/
# Go:      go vet ./...
# Rust:    cargo check
# Java:    (covered by build)
TYPE_CMD="your-type-check-command-here"
$TYPE_CMD || { echo "Type check failed."; exit 1; }

# ── CHECK 6: Tests with coverage ─────────────────────────
echo "--- Tests ---"
# Python:  pytest --cov=src --cov-fail-under=90
# Go:      go test -cover ./...
# Rust:    cargo tarpaulin --fail-under 80
# Java:    ./gradlew test jacocoTestCoverageVerification
TEST_CMD="your-test-command-here"
$TEST_CMD || { echo "Tests or coverage failed."; exit 1; }

# ── CHECK 7: Build ────────────────────────────────────────
echo "--- Build ---"
# Python:  python -m build (or poetry build)
# Go:      go build ./...
# Rust:    cargo build --release
# Java:    ./gradlew build
BUILD_CMD="your-build-command-here"
$BUILD_CMD || { echo "Build failed."; exit 1; }

# ── CHECK 8: Integration tests (if infrastructure available) ──
echo "--- Integration tests ---"
if [ -n "${DATABASE_URL:-}" ]; then
  INTEGRATION_CMD="your-integration-test-command-here"
  $INTEGRATION_CMD || { echo "Integration tests failed."; exit 1; }
else
  echo "Skipping (DATABASE_URL not set)"
fi

echo "=== PRE-PUSH: All checks passed ==="
```

**Key design decisions:**

- Checks 1-2 are fast guards that abort immediately. No point running a 5-minute test suite if the branch is behind origin.
- Checks 3-7 mirror CI exactly. If it passes locally, it passes in CI.
- Check 8 degrades gracefully. Developers without infrastructure can still push feature branches. CI always has the infrastructure.
- Never bypass. `--no-verify` is forbidden. Fix the issue, do not skip the gate.

## 9. CI Pipeline

The CI pipeline runs the same checks as the pre-push hook but on clean infrastructure with full parallelization. The structure is the same for every language.

### Parallel job structure

```
                    ┌─────────────────┐
                    │   Trigger: PR    │
                    │   or push to     │
                    │   main           │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌────────────┐  ┌────────────┐  ┌────────────┐
     │  Job 1:    │  │  Job 2:    │  │  Job 3:    │
     │  Lint +    │  │  Build     │  │  Test      │
     │  Type Check│  │            │  │  (sharded) │
     └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           ▼
                  ┌────────────────┐
                  │  Job 4:        │
                  │  Coverage      │
                  │  Report        │
                  └───────┬────────┘
                          ▼
                  ┌────────────────┐
                  │  Job 5:        │
                  │  Deploy Gate   │
                  │  (main only)   │
                  └────────────────┘
```

### GitHub Actions example (Python)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff mypy
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy src/

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build
      - run: python -m build

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[test]"
      - run: pytest --cov=src --cov-report=xml --cov-fail-under=90
      - uses: actions/upload-artifact@v4
        with:
          name: coverage
          path: coverage.xml

  deploy-gate:
    if: github.ref == 'refs/heads/main'
    needs: [lint, build, test]
    runs-on: ubuntu-latest
    steps:
      - run: echo "All gates passed. Ready to deploy."
```

### GitHub Actions example (Go)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: "1.22"
      - uses: golangci/golangci-lint-action@v6
        with:
          version: latest

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: "1.22"
      - run: go build ./...

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: "1.22"
      - run: go test -coverprofile=coverage.out -covermode=atomic ./...
      - name: Check coverage threshold
        run: |
          COVERAGE=$(go tool cover -func=coverage.out | grep total | awk '{print substr($3, 1, length($3)-1)}')
          echo "Coverage: $COVERAGE%"
          if (( $(echo "$COVERAGE < 80.0" | bc -l) )); then
            echo "Coverage $COVERAGE% is below 80% threshold"
            exit 1
          fi

  deploy-gate:
    if: github.ref == 'refs/heads/main'
    needs: [lint, build, test]
    runs-on: ubuntu-latest
    steps:
      - run: echo "All gates passed. Ready to deploy."
```

### GitHub Actions example (Rust)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with:
          components: rustfmt, clippy
      - run: cargo fmt --check
      - run: cargo clippy -- -D warnings

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo build --release

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo install cargo-tarpaulin
      - run: cargo tarpaulin --fail-under 80 --out xml

  deploy-gate:
    if: github.ref == 'refs/heads/main'
    needs: [lint, build, test]
    runs-on: ubuntu-latest
    steps:
      - run: echo "All gates passed. Ready to deploy."
```

## 10. Architecture Boundaries

Large codebases need rules about what can import what. Without enforcement, the dependency graph becomes a hairball and every change touches everything.

| Language | Tool | What It Enforces |
|----------|------|-----------------|
| TypeScript | eslint-plugin-boundaries | Package import rules in monorepos |
| Python | import-linter | Layer and module boundaries |
| Go | depguard (via golangci-lint) | Package import rules |
| Java | ArchUnit | Class and package dependency rules |
| Kotlin | ArchUnit (Kotlin variant) | Same as Java |
| Rust | cargo features + visibility | Feature-gated dependencies, `pub(crate)` |
| C# | NDepend / ArchUnitNET | Assembly and namespace boundaries |

### Example: Python import-linter

```ini
# .importlinter
[importlinter]
root_package = myapp

[importlinter:contract:layers]
name = Enforce layered architecture
type = layers
layers =
    myapp.api
    myapp.service
    myapp.domain
    myapp.infrastructure
```

This enforces that `api` can import from `service`, `service` can import from `domain`, but `domain` cannot import from `api`. Violations fail the build.

### Example: Go depguard

```yaml
# .golangci.yml
linters-settings:
  depguard:
    rules:
      main:
        deny:
          - pkg: "github.com/myorg/myapp/internal/api"
            desc: "domain layer must not import api layer"
        files:
          - "**/domain/**"
```

### Example: Java ArchUnit

```java
@AnalyzeClasses(packages = "com.myorg.myapp")
class ArchitectureTest {
    @ArchTest
    static final ArchRule domainShouldNotDependOnInfra =
        noClasses().that().resideInAPackage("..domain..")
            .should().dependOnClassesThat().resideInAPackage("..infrastructure..");
}
```

## 11. Dependency Management

Lock files ensure reproducible builds. If two developers or CI get different dependency versions, bugs become impossible to reproduce.

| Language | Lock File | Install Command | Dedup Command |
|----------|-----------|----------------|---------------|
| TypeScript (pnpm) | `pnpm-lock.yaml` | `pnpm install` | `pnpm dedupe` |
| TypeScript (npm) | `package-lock.json` | `npm ci` | `npm dedupe` |
| Python (pip-tools) | `requirements.txt` (compiled) | `pip install -r requirements.txt` | `pip-compile` |
| Python (Poetry) | `poetry.lock` | `poetry install` | `poetry lock` |
| Python (uv) | `uv.lock` | `uv sync` | `uv lock` |
| Go | `go.sum` | `go mod download` | `go mod tidy` |
| Rust | `Cargo.lock` | N/A (built-in) | `cargo update` |
| Java (Gradle) | `gradle.lockfile` | `./gradlew dependencies --write-locks` | N/A |
| Ruby | `Gemfile.lock` | `bundle install` | `bundle lock` |
| Elixir | `mix.lock` | `mix deps.get` | N/A |

**Rules**:

1. Lock files MUST be committed to the repository.
2. CI MUST use the locked versions (e.g., `npm ci` not `npm install`, `pip install -r requirements.txt` not `pip install`).
3. Pre-commit hook checks that the lock file is staged when dependency fields change.
4. Deduplication checks run periodically (weekly CI job or pre-push).

### Lock file freshness check (pre-commit)

```bash
# Generic pattern: if dependency manifest changed, lock file must be staged too
MANIFEST_CHANGED=$(git diff --cached --name-only | grep -E '(package\.json|pyproject\.toml|go\.mod|Cargo\.toml|Gemfile|mix\.exs|build\.gradle)' || true)
if [ -n "$MANIFEST_CHANGED" ]; then
  LOCK_STAGED=$(git diff --cached --name-only | grep -E '(pnpm-lock\.yaml|package-lock\.json|requirements\.txt|poetry\.lock|uv\.lock|go\.sum|Cargo\.lock|Gemfile\.lock|mix\.lock|gradle\.lockfile)' || true)
  if [ -z "$LOCK_STAGED" ]; then
    echo "Dependency manifest changed but lock file is not staged."
    echo "Run your package manager's install/lock command and stage the lock file."
    exit 1
  fi
fi
```

## 12. Copy-Paste Detection

Duplicated code is a maintenance liability. When a bug is fixed in one copy but not the other, the fix is incomplete. Copy-paste detection catches this before it becomes a problem.

| Tool | Languages | Notes |
|------|-----------|-------|
| jscpd | 150+ languages | Universal, language-agnostic |
| PMD CPD | Java, Kotlin, C/C++, others | Part of PMD suite |
| Ruff (pylint rules) | Python | `PLR0801` (duplicate code) |
| dupl | Go | Go-specific |
| cargo-deny | Rust | Detects duplicate crate versions |

**Recommended**: jscpd works across all languages with a single configuration.

```json
{
  "threshold": 5,
  "reporters": ["console"],
  "ignore": [
    "**/node_modules/**",
    "**/dist/**",
    "**/build/**",
    "**/__pycache__/**",
    "**/target/**",
    "**/vendor/**",
    "**/*.test.*",
    "**/*_test.*",
    "**/test_*",
    "**/tests/**",
    "**/generated/**"
  ],
  "minTokens": 50,
  "minLines": 5,
  "absolute": true,
  "gitignore": true
}
```

**Threshold**: 5% maximum duplication in production code. Test code is excluded because test setups often share structure legitimately.

## 13. Database Safety

If your application uses a database, schema changes need their own quality gates. Manual `ALTER TABLE` commands run against a live database are the source of an entire category of bugs: the migration appears to work locally (because the database was already manually altered) but fails in CI or production (because the migration is the only thing that runs there).

### Rules

1. **All schema changes through migrations** -- never run DDL directly against any database.
2. **SQL linting** -- catch dangerous patterns before they reach production.
3. **Schema drift detection** -- compare the declared schema against the actual database.
4. **Migration dry-run in CI** -- apply migrations against a fresh database to verify they work.

### SQL linting tools

| Database | Tool | Config File |
|----------|------|-------------|
| PostgreSQL | squawk | `.squawk.toml` |
| PostgreSQL | pg-lint | N/A |
| MySQL | SQLFluff | `.sqlfluff` |
| Any SQL | SQLFluff | `.sqlfluff` |

**What SQL linters catch**:

- `NOT NULL` added to existing column without default (locks table)
- `DROP COLUMN` without checking dependencies
- Missing `IF NOT EXISTS` / `IF EXISTS` guards
- Non-concurrent index creation on large tables
- Type changes that require full table rewrite

### Schema drift detection

```bash
# Run in CI against a fresh database
# 1. Start empty database
# 2. Run all migrations
# 3. Compare resulting schema against declared schema
# 4. If they differ, the migration pipeline is broken

# Drizzle ORM (TypeScript)
pnpm drizzle-kit check

# Alembic (Python/SQLAlchemy)
alembic check

# golang-migrate (Go)
migrate -source file://migrations -database $DATABASE_URL up
# then compare with schema definition

# Flyway (Java)
flyway validate
```

### Migration naming convention

Enforce consistent naming in the pre-commit hook:

```bash
MIGRATION_FILES=$(git diff --cached --name-only | grep -E 'migrations/' || true)
for mig in $MIGRATION_FILES; do
  basename=$(basename "$mig")
  # Enforce: NNNN_description.sql or NNNN_description.py
  if ! echo "$basename" | grep -qE '^[0-9]{4}_[a-z0-9_-]+\.(sql|py|ts|go)$'; then
    echo "Migration file has invalid name: $basename"
    echo "Expected format: 0001_description.sql"
    exit 1
  fi
done
```

## 14. The Minimum Viable Quality Gate Set

For ANY repo, in ANY language, these seven gates are the non-negotiable minimum. If you have nothing else, implement these.

| # | Gate | When | Severity | What It Prevents |
|---|------|------|----------|-----------------|
| 1 | Auto-formatting on commit | Pre-commit | Auto-fix | Style debates, inconsistent formatting |
| 2 | Linting on commit | Pre-commit | Hard failure | Common bugs, anti-patterns, unused code |
| 3 | Secret detection on commit | Pre-commit | Hard failure | Credentials in the repository |
| 4 | Full test suite on push | Pre-push | Hard failure | Regressions, broken functionality |
| 5 | Build verification on push | Pre-push | Hard failure | Compilation errors, missing dependencies |
| 6 | Coverage threshold in CI | CI | Hard failure | Untested code paths |
| 7 | All of the above in CI on clean infrastructure | CI | Hard failure | "Works on my machine" failures |

### Implementation order

If you are adding gates to an existing repo, add them in this order:

1. **Formatting** (Gate 1) -- zero controversy, immediate value, auto-fixes everything.
2. **Secret detection** (Gate 3) -- security-critical, easy to implement, no false positives on new code.
3. **Linting** (Gate 2) -- may require initial cleanup. Start with a small rule set and expand.
4. **Tests on push** (Gate 4) -- requires having tests. If you do not have tests, start writing them.
5. **Build on push** (Gate 5) -- trivial if you already have a build step.
6. **CI pipeline** (Gate 7) -- replicates local gates on clean infrastructure.
7. **Coverage threshold** (Gate 6) -- add last, after the test suite is mature enough to meet the threshold.

### Quick setup for a new repo

```bash
# 1. Install pre-commit framework
pip install pre-commit

# 2. Create .pre-commit-config.yaml with formatting + linting + secrets
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: detect-private-key
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
  # Add language-specific hooks here
EOF

# 3. Install hooks
pre-commit install
pre-commit install --hook-type pre-push

# 4. Create pre-push hook (see Section 8)

# 5. Create CI pipeline (see Section 9)

# 6. Verify everything works
pre-commit run --all-files
```

### What to add after the minimum

Once the seven minimum gates are in place and passing, consider adding:

- **Type checking** (Section 4) -- if your language supports it
- **Architecture boundaries** (Section 10) -- when the codebase grows beyond a single module
- **Copy-paste detection** (Section 12) -- when duplication starts creeping in
- **Database safety gates** (Section 13) -- if your application uses a database
- **Dependency auditing** -- `npm audit`, `pip-audit`, `go vuln check`, `cargo audit`
- **License compliance** -- `license-checker`, `pip-licenses`, `cargo-deny`
- **Binary/large file prevention** -- `check-added-large-files` hook with a low threshold
- **Commit message linting** -- `commitlint` for conventional commits enforcement
