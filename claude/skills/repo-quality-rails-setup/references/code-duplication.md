# Code Duplication Detection (CPD)

## Why detect duplication

Duplicated code is a maintenance burden. When a bug is fixed in one copy, the other copies remain broken. Every duplicate is a future divergence waiting to happen -- one copy gets updated, the others silently rot.

In a monorepo, duplication across packages is especially dangerous because it suggests missing shared abstractions. If two apps contain the same validation logic, that logic belongs in a shared package. Copy-paste duplication is the strongest signal that your package boundaries are wrong.

Concrete costs of duplication:

- **Bug fixes multiply.** A security patch applied to one copy must be found and applied to every other copy. Miss one and you ship a vulnerability.
- **Refactors become archaeology.** Changing a duplicated pattern means finding every instance, understanding whether each copy has diverged, and updating them all consistently.
- **Code review noise.** Reviewers cannot distinguish intentional duplication from accidental duplication without tooling.
- **Binary and bundle size.** In frontend monorepos, duplicated utility code ships to users multiple times.

Automated copy-paste detection (CPD) catches duplication at commit time, before it compounds.

## Tool: jscpd

[jscpd](https://github.com/kucherenko/jscpd) (JS Copy/Paste Detector) is a language-agnostic duplication detector that works well in JavaScript and TypeScript monorepos.

### Install

```bash
pnpm add -D jscpd
```

### Key features

- Supports TypeScript, JavaScript, and 150+ other languages
- Configurable thresholds for percentage of allowed duplication
- Multiple reporters: console, JSON, HTML, and more
- Ignore patterns for generated code, tests, and vendor files
- Token-based detection (catches renamed-variable clones, not just exact matches)

## Configuration

Create a `.jscpd.json` file at the repository root:

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

### Configuration explained

| Field | Value | Purpose |
|---|---|---|
| `threshold` | `5` | Maximum percentage of duplicated code allowed. The tool exits non-zero if duplication exceeds this value. Start at 5% and tighten over time. |
| `minTokens` | `50` | Minimum number of tokens for a code block to count as a clone. This prevents trivial matches like single import lines or short variable declarations from being flagged. |
| `minLines` | `5` | Minimum number of lines for a code block to count as a clone. Works in conjunction with `minTokens` -- both thresholds must be met. |
| `reporters` | `["console", "json", "html"]` | Console for local dev feedback, JSON for CI parsing, HTML for human-readable reports. |
| `output` | `"./reports/duplication"` | Directory where JSON and HTML reports are written. Add this to `.gitignore`. |
| `ignore` | (see above) | Patterns to exclude from analysis. |
| `format` | `["typescript", "typescriptreact"]` | Languages to scan. Restricts detection to your source language. |
| `absolute` | `true` | Report absolute file paths for easier navigation. |
| `gitignore` | `true` | Automatically respect `.gitignore` rules in addition to the explicit ignore list. |

### Why ignore test files

Tests legitimately repeat setup patterns, assertions, and fixture construction. Flagging test duplication creates noise that obscures real production code duplication. Keep test files out of the scan.

### Why ignore generated code

Generated files (Drizzle migrations, GraphQL codegen output, compiled assets) are not authored by humans and should not be refactored. Including them inflates the duplication percentage and creates false positives.

## Package scripts

Add these scripts to the root `package.json`:

```json
{
  "scripts": {
    "cpd": "jscpd apps/ packages/ --config .jscpd.json",
    "cpd:report": "jscpd apps/ packages/ --config .jscpd.json --reporters html",
    "cpd:ci": "jscpd apps/ packages/ --config .jscpd.json"
  }
}
```

- **`pnpm cpd`** -- Run locally during development. Console output shows clones inline.
- **`pnpm cpd:report`** -- Generate an HTML report in `reports/duplication/`. Open it in a browser to visually inspect detected clones with side-by-side diffs.
- **`pnpm cpd:ci`** -- Same as `cpd`, intended for CI pipelines. The process exits non-zero when duplication exceeds the threshold.

Note that jscpd receives the directories to scan as positional arguments (`apps/ packages/`). This ensures it only scans source code, not root config files, scripts, or documentation.

## Integration points

### Local development

Run `pnpm cpd` before opening a pull request. If you introduced duplication, extract the shared code into a package before pushing.

### CI pipeline

Add `pnpm cpd:ci` as a step in your CI workflow. Two strategies:

1. **Non-blocking (initial rollout).** Run the check but allow the pipeline to continue on failure. This gives visibility without blocking merges while the team reduces existing duplication.

   ```yaml
   - name: Check duplication
     run: pnpm cpd:ci
     continue-on-error: true
   ```

2. **Blocking (steady state).** Once duplication is under the threshold, remove `continue-on-error` so new duplication breaks the build.

   ```yaml
   - name: Check duplication
     run: pnpm cpd:ci
   ```

### Pre-push hook

Once the baseline is clean, consider adding CPD to the pre-push hook so duplication never reaches the remote:

```bash
pnpm cpd:ci
```

This adds a few seconds to the push but prevents duplication from entering the codebase at all.

### HTML report artifact

In CI, upload the HTML report as a build artifact so reviewers can inspect detected clones without running the tool locally:

```yaml
- name: Upload duplication report
  uses: actions/upload-artifact@v4
  with:
    name: duplication-report
    path: reports/duplication/
  if: always()
```

## Interpreting results

### Below threshold

No action needed. The codebase has acceptable duplication levels.

### Above threshold

Duplication exceeds the allowed percentage. Common culprits:

- **Config patterns.** Multiple packages define similar configuration objects (logger setup, database connections, API client initialization).
- **API response handling.** Similar fetch-parse-validate-transform chains repeated across apps.
- **Validation logic.** The same input validation duplicated in multiple API routes.
- **Type guards and parsers.** Identical runtime type checking scattered across packages.

### How to fix duplication

1. **Identify the clones.** Run `pnpm cpd:report` and open the HTML report. Each clone pair shows the two file locations and the duplicated code.

2. **Extract to a shared package.** Move the duplicated logic into an appropriate shared package. In a typical monorepo structure:
   - Utility functions go into a shared utilities package (e.g., `packages/shared-utils`)
   - Domain logic goes into a domain package (e.g., `packages/core-domain`)
   - Service patterns go into a service core package (e.g., `packages/service-core`)

3. **Import from the shared package.** Replace both copies with imports from the new shared location.

4. **Re-run the check.** Verify that `pnpm cpd` now passes.

### Adjusting the threshold

If the initial scan shows 15% duplication, do not set the threshold to 15% and call it done. Instead:

1. Set the threshold slightly below the current level (e.g., 14%).
2. Fix the worst offenders to get under that threshold.
3. Ratchet the threshold down over time (14% to 10% to 7% to 5%).

This creates a one-way ratchet: duplication can only decrease.

## For non-TypeScript repos

jscpd supports 150+ languages out of the box. Change the `format` field in `.jscpd.json` to match your stack:

| Stack | Format value |
|---|---|
| Python | `["python"]` |
| Go | `["go"]` |
| Rust | `["rust"]` |
| Java | `["java"]` |
| Ruby | `["ruby"]` |
| Mixed JS/TS | `["javascript", "typescript", "typescriptreact", "javascriptreact"]` |

The rest of the configuration (threshold, minTokens, minLines, ignore patterns) applies regardless of language. Adjust ignore patterns to match your ecosystem (e.g., `**/venv/**` for Python, `**/target/**` for Rust).
