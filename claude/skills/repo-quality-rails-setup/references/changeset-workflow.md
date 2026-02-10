# Changeset Workflow for Version Management

## What Changesets Solve

In a TypeScript monorepo with interdependent packages, version management is a coordination problem. When a change to `@scope/core` affects `@scope/api` and `@scope/cli`, all three may need version bumps, but developers working on individual packages often forget to bump dependents. Breaking changes slip through without major version bumps. Changelogs fall out of date or never get written.

`@changesets/cli` solves this by making version intent explicit at commit time. Each pull request includes a small markdown file (a "changeset") declaring which packages changed and what kind of bump they need. At release time, changesets are consumed to automatically bump versions, update changelogs, and publish to npm.

Without changesets:
- A breaking change to a shared package gets published as a patch
- Downstream packages silently break because their dependency range still matches
- Changelogs are empty or written retroactively from git logs
- Nobody knows which packages were actually affected by a PR

With changesets:
- The author declares intent (`major`, `minor`, `patch`) per package at PR time
- CI enforces that publishable package changes include a changeset
- `changeset version` bumps all affected packages and writes changelogs
- `changeset publish` publishes only the packages that changed

## Setup

Install the CLI as a dev dependency at the monorepo root:

```bash
pnpm add -D @changesets/cli
```

Initialize the `.changeset/` directory:

```bash
pnpm changeset init
```

This creates `.changeset/config.json` and `.changeset/README.md`. Configure the config file:

```json
{
  "$schema": "https://unpkg.com/@changesets/config@3.1.2/schema.json",
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

Key config options:

| Option | Purpose |
|--------|---------|
| `changelog` | Changelog generation strategy. `@changesets/cli/changelog` is the built-in default. |
| `commit` | If `true`, `changeset version` auto-commits. Set to `false` for CI control. |
| `fixed` | Groups of packages that always share the same version number. |
| `linked` | Groups of packages whose versions are linked (bump together when any changes). |
| `access` | `"restricted"` for private npm packages, `"public"` for open source. |
| `baseBranch` | The branch changesets are compared against (usually `main`). |
| `updateInternalDependencies` | When a dependency bumps, bump dependents by at least this level. |
| `ignore` | Packages to exclude from changeset requirements entirely. |

## Creating Changesets

### Non-Interactive (Agent-Friendly)

Write a markdown file to `.changeset/` with a unique name. The filename can be anything ending in `.md` except `README.md`, which is reserved.

```markdown
---
"@scope/package-name": patch
---

Brief description of the change.
```

The YAML frontmatter maps package names to bump types. The body becomes the changelog entry.

### Bump Types

| Type | Semver | When to Use |
|------|--------|-------------|
| `patch` | 0.0.X | Bug fixes, minor internal changes |
| `minor` | 0.X.0 | New features, non-breaking additions |
| `major` | X.0.0 | Breaking changes to public API |

### Multiple Packages in One Changeset

When a single change affects multiple packages, list them all in one file:

```markdown
---
"@scope/indicators": minor
"@scope/trading-math": patch
---

Added new indicator and fixed calculation in trading-math.
```

This produces a single changelog entry in each package, keeping the narrative coherent.

### Filename Conventions

Use any unique, descriptive name:

```
.changeset/fix-orderbook-calc.md
.changeset/add-websocket-relay.md
.changeset/cool-pandas-dance.md
```

The interactive `pnpm changeset` command generates random names like `fuzzy-cats-jump.md`. For agent workflows, descriptive names are clearer.

## Empty Changesets

When a change to a publishable package does not warrant a version bump, create an empty changeset to satisfy the pre-commit hook:

```markdown
---
---
```

No packages listed, no description. This tells the tooling "I considered versioning and determined no bump is needed."

Use empty changesets for:
- Internal refactoring with no API changes
- Code comments or documentation within source files
- Dev-only changes (test utilities, build config tweaks)
- Dependency updates that do not affect the public API

An empty changeset is consumed by `changeset version` without producing any version bump or changelog entry.

## Pre-Commit Enforcement

Add a pre-commit hook that enforces changeset presence when publishable packages are modified. The logic:

1. Determine which files are staged (`git diff --cached --name-only`)
2. Filter to files under `packages/` or `apps/`
3. For each affected package, check if `package.json` contains `"private": true`
4. If any non-private (publishable) package has staged changes, require at least one `.changeset/*.md` file (excluding `README.md`) to be present
5. Exit 1 if no changeset is found

Example hook script (`.husky/pre-commit` or equivalent):

```bash
#!/bin/sh

# Get staged files in packages/ or apps/
STAGED_PKG_FILES=$(git diff --cached --name-only -- 'packages/**' 'apps/**')

if [ -z "$STAGED_PKG_FILES" ]; then
  exit 0
fi

# Check if any changed package is publishable
HAS_PUBLISHABLE=false
for file in $STAGED_PKG_FILES; do
  pkg_dir=$(echo "$file" | cut -d'/' -f1-2)
  pkg_json="$pkg_dir/package.json"
  if [ -f "$pkg_json" ]; then
    is_private=$(node -p "try{JSON.parse(require('fs').readFileSync('$pkg_json','utf8')).private??false}catch{false}")
    if [ "$is_private" = "false" ]; then
      HAS_PUBLISHABLE=true
      break
    fi
  fi
done

if [ "$HAS_PUBLISHABLE" = "false" ]; then
  exit 0
fi

# Check for changeset files (not README.md)
CHANGESETS=$(find .changeset -name '*.md' ! -name 'README.md' 2>/dev/null)

if [ -z "$CHANGESETS" ]; then
  echo "ERROR: Publishable package changes detected but no changeset found."
  echo ""
  echo "Create a changeset:"
  echo "  pnpm changeset"
  echo ""
  echo "Or create an empty changeset if no version bump is needed:"
  echo "  echo '---\n---' > .changeset/empty-changeset.md"
  exit 1
fi
```

Recovery when the hook fails:
- Run `pnpm changeset` to create one interactively
- Or write a changeset file manually to `.changeset/`
- Or create an empty changeset if no version bump is warranted

## When NOT to Create Changesets

Skip changesets entirely for changes that do not touch publishable package source code:

- **Private packages** (`"private": true` in `package.json`) -- these are never published, so versioning is irrelevant
- **Documentation-only changes** -- README files, `docs/` directories, markdown outside packages
- **Test-only changes** -- new or modified tests that do not change the package's public API or behavior
- **CI/tooling changes** -- GitHub Actions workflows, linter configs, build scripts outside of packages
- **Root-level config** -- `tsconfig.base.json`, `.prettierrc`, `turbo.json`, `pnpm-workspace.yaml`

The pre-commit hook should already skip these by only checking for changeset presence when publishable package files are staged.

## CI Publishing Workflow

After CI passes on the `main` branch, automate the version-and-publish cycle:

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    branches: [main]

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: pnpm/action-setup@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      - name: Check for pending changesets
        id: check
        run: |
          if pnpm changeset status 2>&1 | grep -q "No changesets present"; then
            echo "has_changesets=false" >> $GITHUB_OUTPUT
          else
            echo "has_changesets=true" >> $GITHUB_OUTPUT
          fi

      - name: Version packages
        if: steps.check.outputs.has_changesets == 'true'
        run: |
          pnpm changeset version
          HUSKY=0 git add -A
          HUSKY=0 git commit -m "chore: version packages"

      - name: Build
        if: steps.check.outputs.has_changesets == 'true'
        run: pnpm build

      - name: Publish
        if: steps.check.outputs.has_changesets == 'true'
        run: pnpm changeset publish
        env:
          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}

      - name: Push version commits and tags
        if: steps.check.outputs.has_changesets == 'true'
        run: git push --follow-tags
```

The workflow:

1. **Check** for pending changesets. If none exist, skip the release entirely.
2. **Version**: `changeset version` consumes all pending changeset files, bumps `package.json` versions, updates `CHANGELOG.md` in each affected package, and updates internal dependency ranges.
3. **Commit**: The version changes are committed with `HUSKY=0` to skip pre-commit hooks. This is the one acceptable case for skipping hooks -- automated version-only commits that contain no source changes.
4. **Build**: Rebuild all packages with the new version numbers.
5. **Publish**: `changeset publish` publishes each bumped package to the npm registry and creates git tags.
6. **Push**: Push the version commit and tags back to the repository.

## Root package.json Scripts

Add these scripts to the root `package.json` for convenience:

```json
{
  "scripts": {
    "changeset": "changeset",
    "changeset:status": "changeset status",
    "changeset:version": "changeset version",
    "changeset:publish": "changeset publish"
  }
}
```

| Script | Purpose |
|--------|---------|
| `pnpm changeset` | Create a new changeset (interactive) |
| `pnpm changeset:status` | Show pending changesets and their projected version bumps |
| `pnpm changeset:version` | Consume changesets, bump versions, update changelogs |
| `pnpm changeset:publish` | Publish bumped packages to npm |

## Quick Reference

### Agent creating a changeset for a bug fix:

```bash
cat > .changeset/fix-price-calc.md << 'EOF'
---
"@scope/trading-math": patch
---

Fix off-by-one error in tick size rounding.
EOF
```

### Agent creating an empty changeset for a refactor:

```bash
cat > .changeset/refactor-internals.md << 'EOF'
---
---
EOF
```

### Checking what will be released:

```bash
pnpm changeset:status
```

### Verifying changesets exist before committing:

```bash
ls .changeset/*.md | grep -v README.md
```
