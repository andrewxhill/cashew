# Refactoring Playbook: Systematic Codebase Improvement with Deterministic Gates

This reference covers incremental refactoring of existing codebases using measurable, automated quality gates. It is not a theoretical guide -- every recommendation has a concrete script, configuration, or code example that you can run today. The core principle: refactoring without measurement is just moving code around. Refactoring with measurement is engineering.

## Table of Contents

1. [Assessment: Measuring Where You Are](#1-assessment-measuring-where-you-are)
2. [The Ratchet: Never Allow Regression](#2-the-ratchet-never-allow-regression)
3. [Churn x Complexity: The Priority Algorithm](#3-churn-x-complexity-the-priority-algorithm)
4. [The Strangler Fig Pattern for Gradual Rewrites](#4-the-strangler-fig-pattern-for-gradual-rewrites)
5. [Extract-and-Delegate Patterns](#5-extract-and-delegate-patterns)
6. [Dependency Inversion for Testability](#6-dependency-inversion-for-testability)
7. [Safe Refactoring Workflow](#7-safe-refactoring-workflow)
8. [Incremental Adoption for Greenfield Standards](#8-incremental-adoption-for-greenfield-standards)
9. [Architecture Decision Records (ADRs) for Refactoring](#9-architecture-decision-records-adrs-for-refactoring)
10. [Anti-Patterns to Avoid](#10-anti-patterns-to-avoid)

---

## 1. Assessment: Measuring Where You Are

Before you change anything, measure everything. An assessment tells you where the codebase stands today so you can track progress and prioritize work. Running this blind is how teams spend six months refactoring the wrong files.

### The Assessment Script

Create `scripts/assess-codebase.sh` at your repo root. This script runs all design metrics and produces a JSON scorecard.

```bash
#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# scripts/assess-codebase.sh
# Automated codebase assessment. Outputs JSON scorecard.
# Usage: ./scripts/assess-codebase.sh [--compare baseline.json]
# ─────────────────────────────────────────────────────────────

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

REPO_ROOT="$(git rev-parse --show-toplevel)"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
COMPARE_FILE=""

if [[ "${1:-}" == "--compare" && -n "${2:-}" ]]; then
  COMPARE_FILE="$2"
fi

# ─────────────────────────────────────────────────────────────
# Metric 1: ESLint violation count
# ─────────────────────────────────────────────────────────────
echo -e "${CYAN}[1/7]${NC} Counting ESLint violations..."
ESLINT_VIOLATIONS=0
if command -v pnpm &>/dev/null && [ -f "$REPO_ROOT/eslint.config.mjs" ] || [ -f "$REPO_ROOT/eslint.config.js" ]; then
  ESLINT_OUTPUT=$(pnpm eslint --format json . 2>/dev/null || true)
  ESLINT_VIOLATIONS=$(echo "$ESLINT_OUTPUT" | node -e "
    const data = JSON.parse(require('fs').readFileSync('/dev/stdin','utf8'));
    console.log(data.reduce((sum, f) => sum + f.errorCount + f.warningCount, 0));
  " 2>/dev/null || echo "0")
fi

# ─────────────────────────────────────────────────────────────
# Metric 2: Circular dependency count
# ─────────────────────────────────────────────────────────────
echo -e "${CYAN}[2/7]${NC} Detecting circular dependencies..."
CIRCULAR_DEPS=0
if command -v npx &>/dev/null; then
  CIRCULAR_DEPS=$(npx depcruise --no-config --output-type err-long src/ 2>/dev/null \
    | grep -c "circular" || echo "0")
fi

# ─────────────────────────────────────────────────────────────
# Metric 3: God file count (files > 500 lines of code)
# ─────────────────────────────────────────────────────────────
echo -e "${CYAN}[3/7]${NC} Counting god files (>500 LoC)..."
GOD_FILES=0
GOD_FILE_LIST=""
while IFS= read -r file; do
  LOC=$(wc -l < "$file" | tr -d ' ')
  if [ "$LOC" -gt 500 ]; then
    GOD_FILES=$((GOD_FILES + 1))
    GOD_FILE_LIST="${GOD_FILE_LIST}    \"${file#$REPO_ROOT/}\" ($LOC lines)\n"
  fi
done < <(find "$REPO_ROOT/src" "$REPO_ROOT/packages" "$REPO_ROOT/apps" \
  -name "*.ts" -o -name "*.tsx" 2>/dev/null | grep -v node_modules | grep -v dist | grep -v '.test.')

# ─────────────────────────────────────────────────────────────
# Metric 4: Max dependency depth
# ─────────────────────────────────────────────────────────────
echo -e "${CYAN}[4/7]${NC} Measuring dependency depth..."
MAX_DEPTH=0
if command -v npx &>/dev/null; then
  MAX_DEPTH=$(npx depcruise --no-config --output-type text src/ 2>/dev/null \
    | awk -F'→' '{print NF-1}' | sort -rn | head -1 || echo "0")
fi

# ─────────────────────────────────────────────────────────────
# Metric 5: Test coverage percentage
# ─────────────────────────────────────────────────────────────
echo -e "${CYAN}[5/7]${NC} Checking test coverage..."
COVERAGE_PCT=0
if [ -f "$REPO_ROOT/coverage/coverage-summary.json" ]; then
  COVERAGE_PCT=$(node -e "
    const data = require('$REPO_ROOT/coverage/coverage-summary.json');
    console.log(Math.round(data.total.lines.pct));
  " 2>/dev/null || echo "0")
fi

# ─────────────────────────────────────────────────────────────
# Metric 6: Cognitive complexity (via ESLint sonarjs)
# ─────────────────────────────────────────────────────────────
echo -e "${CYAN}[6/7]${NC} Measuring cognitive complexity..."
HIGH_COMPLEXITY_COUNT=0
if command -v pnpm &>/dev/null; then
  HIGH_COMPLEXITY_COUNT=$(pnpm eslint --format json --rule '{"sonarjs/cognitive-complexity": ["warn", 15]}' . 2>/dev/null \
    | node -e "
      const data = JSON.parse(require('fs').readFileSync('/dev/stdin','utf8'));
      const count = data.reduce((sum, f) =>
        sum + f.messages.filter(m => m.ruleId === 'sonarjs/cognitive-complexity').length, 0);
      console.log(count);
    " 2>/dev/null || echo "0")
fi

# ─────────────────────────────────────────────────────────────
# Metric 7: TypeScript `any` usage count
# ─────────────────────────────────────────────────────────────
echo -e "${CYAN}[7/7]${NC} Counting \`any\` type usage..."
ANY_COUNT=$(grep -r --include="*.ts" --include="*.tsx" -c ': any' "$REPO_ROOT/src" "$REPO_ROOT/packages" "$REPO_ROOT/apps" 2>/dev/null \
  | awk -F: '{sum+=$NF} END {print sum+0}' || echo "0")

# ─────────────────────────────────────────────────────────────
# Grading
# ─────────────────────────────────────────────────────────────
grade_metric() {
  local name="$1" value="$2" a="$3" b="$4" c="$5" d="$6"
  # Lower is better for all metrics except coverage
  if [ "$name" = "coverage" ]; then
    if [ "$value" -ge "$a" ]; then echo "A"
    elif [ "$value" -ge "$b" ]; then echo "B"
    elif [ "$value" -ge "$c" ]; then echo "C"
    elif [ "$value" -ge "$d" ]; then echo "D"
    else echo "F"; fi
  else
    if [ "$value" -le "$a" ]; then echo "A"
    elif [ "$value" -le "$b" ]; then echo "B"
    elif [ "$value" -le "$c" ]; then echo "C"
    elif [ "$value" -le "$d" ]; then echo "D"
    else echo "F"; fi
  fi
}

GRADE_ESLINT=$(grade_metric "violations" "$ESLINT_VIOLATIONS" 0 10 50 200)
GRADE_CIRCULAR=$(grade_metric "circular" "$CIRCULAR_DEPS" 0 2 5 15)
GRADE_GOD=$(grade_metric "god_files" "$GOD_FILES" 0 3 10 25)
GRADE_DEPTH=$(grade_metric "depth" "$MAX_DEPTH" 5 8 12 20)
GRADE_COVERAGE=$(grade_metric "coverage" "$COVERAGE_PCT" 90 75 60 40)
GRADE_COMPLEXITY=$(grade_metric "complexity" "$HIGH_COMPLEXITY_COUNT" 0 5 20 50)
GRADE_ANY=$(grade_metric "any" "$ANY_COUNT" 0 5 25 100)

# Overall grade: worst individual grade
overall_grade() {
  local worst="A"
  for grade in "$@"; do
    case "$grade" in
      F) worst="F"; return ;;
      D) [ "$worst" != "F" ] && worst="D" ;;
      C) [ "$worst" != "F" ] && [ "$worst" != "D" ] && worst="C" ;;
      B) [ "$worst" = "A" ] && worst="B" ;;
    esac
  done
  echo "$worst"
}

OVERALL=$(overall_grade "$GRADE_ESLINT" "$GRADE_CIRCULAR" "$GRADE_GOD" \
  "$GRADE_DEPTH" "$GRADE_COVERAGE" "$GRADE_COMPLEXITY" "$GRADE_ANY")

# ─────────────────────────────────────────────────────────────
# Output JSON
# ─────────────────────────────────────────────────────────────
OUTPUT_FILE="$REPO_ROOT/.quality/assessment-$(date +%Y%m%d-%H%M%S).json"
mkdir -p "$REPO_ROOT/.quality"

cat > "$OUTPUT_FILE" <<EOF
{
  "timestamp": "$TIMESTAMP",
  "commit": "$(git rev-parse HEAD)",
  "overall_grade": "$OVERALL",
  "metrics": {
    "eslint_violations": { "value": $ESLINT_VIOLATIONS, "grade": "$GRADE_ESLINT" },
    "circular_dependencies": { "value": $CIRCULAR_DEPS, "grade": "$GRADE_CIRCULAR" },
    "god_files": { "value": $GOD_FILES, "grade": "$GRADE_GOD" },
    "max_dependency_depth": { "value": $MAX_DEPTH, "grade": "$GRADE_DEPTH" },
    "test_coverage_pct": { "value": $COVERAGE_PCT, "grade": "$GRADE_COVERAGE" },
    "high_complexity_functions": { "value": $HIGH_COMPLEXITY_COUNT, "grade": "$GRADE_COMPLEXITY" },
    "any_type_usage": { "value": $ANY_COUNT, "grade": "$GRADE_ANY" }
  }
}
EOF

echo ""
echo "═══════════════════════════════════════════════════"
echo "  CODEBASE ASSESSMENT: $OVERALL"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  ESLint violations:       $ESLINT_VIOLATIONS ($GRADE_ESLINT)"
echo "  Circular dependencies:   $CIRCULAR_DEPS ($GRADE_CIRCULAR)"
echo "  God files (>500 LoC):    $GOD_FILES ($GRADE_GOD)"
echo "  Max dependency depth:    $MAX_DEPTH ($GRADE_DEPTH)"
echo "  Test coverage:           ${COVERAGE_PCT}% ($GRADE_COVERAGE)"
echo "  High complexity funcs:   $HIGH_COMPLEXITY_COUNT ($GRADE_COMPLEXITY)"
echo "  \`any\` type usage:        $ANY_COUNT ($GRADE_ANY)"
echo ""
echo "  Saved: $OUTPUT_FILE"

# ─────────────────────────────────────────────────────────────
# Comparison mode
# ─────────────────────────────────────────────────────────────
if [ -n "$COMPARE_FILE" ] && [ -f "$COMPARE_FILE" ]; then
  echo ""
  echo "─── Comparison with $(basename "$COMPARE_FILE") ───"
  node -e "
    const prev = require('$COMPARE_FILE');
    const curr = require('$OUTPUT_FILE');
    const metrics = Object.keys(curr.metrics);
    for (const m of metrics) {
      const p = prev.metrics[m]?.value ?? 'N/A';
      const c = curr.metrics[m].value;
      const dir = m === 'test_coverage_pct'
        ? (c > p ? '↑ improved' : c < p ? '↓ regressed' : '= same')
        : (c < p ? '↑ improved' : c > p ? '↓ regressed' : '= same');
      console.log('  ' + m.padEnd(28) + p.toString().padStart(5) + ' → ' + c.toString().padStart(5) + '  ' + dir);
    }
    console.log('');
    console.log('  Overall: ' + prev.overall_grade + ' → ' + curr.overall_grade);
  "
fi
```

### Grading Thresholds

The letter grades are deliberately strict. This is intentional -- a grade of "A" means the metric is at zero violations or at full coverage. "B" means minor issues exist. The thresholds:

| Metric | A | B | C | D | F |
|--------|---|---|---|---|---|
| ESLint violations | 0 | <=10 | <=50 | <=200 | >200 |
| Circular deps | 0 | <=2 | <=5 | <=15 | >15 |
| God files (>500 LoC) | 0 | <=3 | <=10 | <=25 | >25 |
| Max dep depth | <=5 | <=8 | <=12 | <=20 | >20 |
| Test coverage | >=90% | >=75% | >=60% | >=40% | <40% |
| High complexity funcs | 0 | <=5 | <=20 | <=50 | >50 |
| `any` usage | 0 | <=5 | <=25 | <=100 | >100 |

**Overall grade** is the worst individual grade. A single F pulls the whole scorecard to F. This is correct behavior -- a codebase with 95% coverage but 30 circular dependencies has a structural problem that coverage cannot compensate for.

### Running the Assessment

```bash
# First assessment (creates baseline)
chmod +x scripts/assess-codebase.sh
./scripts/assess-codebase.sh

# Later assessment with comparison
./scripts/assess-codebase.sh --compare .quality/assessment-20260101-120000.json
```

Add `.quality/` to `.gitignore` -- assessments are local artifacts, not checked-in state.

---

## 2. The Ratchet: Never Allow Regression

The ratchet is the most important concept in this playbook. New code must meet the standard. Old code gets grandfathered with a shrinking budget. The budget only goes down, never up.

### How the Ratchet Works

1. Capture a baseline: count every violation in every file
2. On every commit/push, re-count violations
3. If any count went UP, fail the build
4. If any count went DOWN, update the baseline to the new (lower) number
5. Periodically, subtract N from every budget to force improvement

The effect: violations can only ever decrease. Every developer who touches a file can make it better or leave it alone, but they cannot make it worse.

### The Ratchet Script

```bash
#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# scripts/quality-ratchet.sh
# Captures baseline and blocks regressions.
# Usage:
#   ./scripts/quality-ratchet.sh baseline   # Capture current state
#   ./scripts/quality-ratchet.sh check      # Compare against baseline
#   ./scripts/quality-ratchet.sh tighten 5  # Reduce budgets by N
# ─────────────────────────────────────────────────────────────

REPO_ROOT="$(git rev-parse --show-toplevel)"
BASELINE_FILE="$REPO_ROOT/.quality/ratchet-baseline.json"
ACTION="${1:-check}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Count violations per file using ESLint JSON output
count_violations() {
  local output_file="$1"
  pnpm eslint --format json . 2>/dev/null | node -e "
    const data = JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8'));
    const result = {};
    for (const file of data) {
      const rel = file.filePath.replace(process.cwd() + '/', '');
      const count = file.errorCount + file.warningCount;
      if (count > 0) {
        result[rel] = count;
      }
    }
    require('fs').writeFileSync('$output_file', JSON.stringify(result, null, 2));
    console.log(Object.keys(result).length + ' files with violations');
  "
}

# Count `any` usage per file
count_any_per_file() {
  local output_file="$1"
  node -e "
    const { execSync } = require('child_process');
    const result = {};
    const output = execSync(
      'grep -rn --include=\"*.ts\" --include=\"*.tsx\" \": any\" src/ packages/ apps/ 2>/dev/null || true',
      { encoding: 'utf8' }
    );
    for (const line of output.split('\n').filter(Boolean)) {
      const file = line.split(':')[0];
      result[file] = (result[file] || 0) + 1;
    }
    require('fs').writeFileSync('$output_file', JSON.stringify(result, null, 2));
  "
}

case "$ACTION" in
  baseline)
    mkdir -p "$REPO_ROOT/.quality"
    echo "Capturing ratchet baseline..."

    ESLINT_FILE="$REPO_ROOT/.quality/ratchet-eslint.json"
    ANY_FILE="$REPO_ROOT/.quality/ratchet-any.json"

    count_violations "$ESLINT_FILE"
    count_any_per_file "$ANY_FILE"

    # Combine into single baseline
    node -e "
      const eslint = require('$ESLINT_FILE');
      const any = require('$ANY_FILE');
      const baseline = {
        timestamp: new Date().toISOString(),
        commit: '$(git rev-parse HEAD)',
        eslint_violations: eslint,
        any_usage: any,
        totals: {
          eslint: Object.values(eslint).reduce((a,b) => a+b, 0),
          any: Object.values(any).reduce((a,b) => a+b, 0)
        }
      };
      require('fs').writeFileSync('$BASELINE_FILE', JSON.stringify(baseline, null, 2));
      console.log('Baseline saved: ' + baseline.totals.eslint + ' ESLint violations, ' + baseline.totals.any + ' any usages');
    "

    rm -f "$ESLINT_FILE" "$ANY_FILE"
    ;;

  check)
    if [ ! -f "$BASELINE_FILE" ]; then
      echo -e "${YELLOW}No baseline found. Run: ./scripts/quality-ratchet.sh baseline${NC}"
      exit 0
    fi

    echo "Checking for regressions against baseline..."
    CURRENT_ESLINT="$REPO_ROOT/.quality/ratchet-current-eslint.json"
    CURRENT_ANY="$REPO_ROOT/.quality/ratchet-current-any.json"

    count_violations "$CURRENT_ESLINT"
    count_any_per_file "$CURRENT_ANY"

    REGRESSIONS=$(node -e "
      const baseline = require('$BASELINE_FILE');
      const currentEslint = require('$CURRENT_ESLINT');
      const currentAny = require('$CURRENT_ANY');
      let regressions = [];
      let improvements = [];

      // Check ESLint regressions
      for (const [file, count] of Object.entries(currentEslint)) {
        const prev = baseline.eslint_violations[file] || 0;
        if (count > prev) {
          regressions.push('ESLint: ' + file + ' (' + prev + ' → ' + count + ')');
        } else if (count < prev) {
          improvements.push('ESLint: ' + file + ' (' + prev + ' → ' + count + ')');
        }
      }

      // Check any regressions
      for (const [file, count] of Object.entries(currentAny)) {
        const prev = baseline.any_usage[file] || 0;
        if (count > prev) {
          regressions.push('any: ' + file + ' (' + prev + ' → ' + count + ')');
        } else if (count < prev) {
          improvements.push('any: ' + file + ' (' + prev + ' → ' + count + ')');
        }
      }

      if (improvements.length > 0) {
        console.error('Improvements (' + improvements.length + '):');
        improvements.forEach(i => console.error('  ↓ ' + i));
      }

      if (regressions.length > 0) {
        console.error('REGRESSIONS (' + regressions.length + '):');
        regressions.forEach(r => console.error('  ↑ ' + r));
        console.log(regressions.length);
      } else {
        console.log(0);
      }
    ")

    rm -f "$CURRENT_ESLINT" "$CURRENT_ANY"

    if [ "$REGRESSIONS" -gt 0 ]; then
      echo -e "${RED}RATCHET FAILED: $REGRESSIONS regressions detected.${NC}"
      echo "Fix the regressions or update the baseline with: ./scripts/quality-ratchet.sh baseline"
      exit 1
    else
      echo -e "${GREEN}Ratchet passed. No regressions.${NC}"
    fi
    ;;

  tighten)
    AMOUNT="${2:-5}"
    if [ ! -f "$BASELINE_FILE" ]; then
      echo "No baseline to tighten."
      exit 1
    fi

    node -e "
      const baseline = require('$BASELINE_FILE');

      let tightened = 0;
      for (const [file, count] of Object.entries(baseline.eslint_violations)) {
        const newCount = Math.max(0, count - $AMOUNT);
        if (newCount !== count) tightened++;
        if (newCount === 0) delete baseline.eslint_violations[file];
        else baseline.eslint_violations[file] = newCount;
      }
      for (const [file, count] of Object.entries(baseline.any_usage)) {
        const newCount = Math.max(0, count - $AMOUNT);
        if (newCount !== count) tightened++;
        if (newCount === 0) delete baseline.any_usage[file];
        else baseline.any_usage[file] = newCount;
      }

      baseline.totals.eslint = Object.values(baseline.eslint_violations).reduce((a,b) => a+b, 0);
      baseline.totals.any = Object.values(baseline.any_usage).reduce((a,b) => a+b, 0);
      baseline.tightened_at = new Date().toISOString();

      require('fs').writeFileSync('$BASELINE_FILE', JSON.stringify(baseline, null, 2));
      console.log('Tightened ' + tightened + ' budgets by $AMOUNT each.');
      console.log('New totals: ' + baseline.totals.eslint + ' ESLint, ' + baseline.totals.any + ' any');
    "
    ;;

  *)
    echo "Usage: $0 {baseline|check|tighten [N]}"
    exit 1
    ;;
esac
```

### Baseline JSON Format

The baseline file is a per-file snapshot. This is important -- it tells you exactly which files have violations and how many, not just a global total.

```json
{
  "timestamp": "2026-02-10T14:30:00Z",
  "commit": "abc123def",
  "eslint_violations": {
    "src/legacy/parser.ts": 12,
    "src/legacy/transformer.ts": 8,
    "packages/core/src/utils.ts": 3
  },
  "any_usage": {
    "src/legacy/parser.ts": 7,
    "src/api/handlers.ts": 2
  },
  "totals": {
    "eslint": 23,
    "any": 9
  }
}
```

### Pre-Push Hook Integration

Add the ratchet check to your pre-push hook so regressions are blocked before they reach the remote:

```bash
# In .husky/pre-push, add:
info "Running quality ratchet check..."
if [ -f "$REPO_ROOT/.quality/ratchet-baseline.json" ]; then
  ./scripts/quality-ratchet.sh check || {
    fail "Quality ratchet failed. Fix regressions before pushing."
    exit 1
  }
  pass "Quality ratchet passed"
fi
```

### How to Tighten the Ratchet

Every sprint (or every two weeks, or every month -- pick a cadence), reduce every file's budget:

```bash
# Reduce every file's violation budget by 5
./scripts/quality-ratchet.sh tighten 5

# Commit the updated baseline
git add .quality/ratchet-baseline.json
git commit -m "chore: tighten quality ratchet by 5"
```

Files that were already at zero are unaffected. Files that had 3 violations now have a budget of 0, meaning their next change must fix all remaining violations. This creates steady, predictable pressure toward zero violations without requiring a heroic cleanup sprint.

---

## 3. Churn x Complexity: The Priority Algorithm

Not all files deserve refactoring equally. A 1000-line file that nobody touches is stable legacy -- leave it alone. A 200-line file that changes every sprint and has high complexity is a source of bugs and should be refactored first.

The priority algorithm: `churn x complexity`. Files that change often AND are complex are the highest value targets.

### Why This Works

- **High churn, high complexity**: Every change risks introducing bugs. Every developer who touches this file pays a cognitive tax. Refactor immediately.
- **High churn, low complexity**: Changes frequently but is easy to understand. Low risk, low priority.
- **Low churn, high complexity**: Complex but stable. It works. Leave it alone until you need to change it.
- **Low churn, low complexity**: Healthy code. No action needed.

### The Churn-Complexity Script

```bash
#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# scripts/churn-complexity.sh
# Identifies high-priority refactoring targets using
# churn (git log) x complexity (eslint cognitive-complexity).
# Usage: ./scripts/churn-complexity.sh [--days 180] [--top 20]
# ─────────────────────────────────────────────────────────────

REPO_ROOT="$(git rev-parse --show-toplevel)"
DAYS="${DAYS:-180}"
TOP="${TOP:-20}"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --days) DAYS="$2"; shift 2 ;;
    --top) TOP="$2"; shift 2 ;;
    *) shift ;;
  esac
done

SINCE="$(date -v-${DAYS}d +%Y-%m-%d 2>/dev/null || date -d "$DAYS days ago" +%Y-%m-%d)"

echo "Analyzing churn since $SINCE (${DAYS} days)..."
echo ""

# ─────────────────────────────────────────────────────────────
# Step 1: Get churn data (number of commits touching each file)
# ─────────────────────────────────────────────────────────────
CHURN_FILE=$(mktemp)
git log --since="$SINCE" --pretty=format: --name-only \
  | grep -E '\.(ts|tsx)$' \
  | grep -v node_modules \
  | grep -v dist \
  | grep -v '.test.' \
  | grep -v '.spec.' \
  | sort \
  | uniq -c \
  | sort -rn \
  | awk '{print $2 "\t" $1}' \
  > "$CHURN_FILE"

# ─────────────────────────────────────────────────────────────
# Step 2: Get complexity data per file
# ─────────────────────────────────────────────────────────────
COMPLEXITY_FILE=$(mktemp)

# Use ESLint with sonarjs cognitive-complexity to get per-file complexity
pnpm eslint --format json \
  --rule '{"sonarjs/cognitive-complexity": ["warn", 1]}' \
  . 2>/dev/null | node -e "
    const data = JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8'));
    const result = {};
    for (const file of data) {
      const rel = file.filePath.replace(process.cwd() + '/', '');
      // Sum all cognitive complexity warnings as a proxy for total complexity
      const complexityMessages = file.messages.filter(
        m => m.ruleId === 'sonarjs/cognitive-complexity'
      );
      if (complexityMessages.length > 0) {
        // Each message means a function exceeds the threshold; count = number of complex functions
        result[rel] = complexityMessages.length;
      }
    }
    const lines = Object.entries(result).map(([f, c]) => f + '\t' + c).join('\n');
    require('fs').writeFileSync('$COMPLEXITY_FILE', lines);
  "

# ─────────────────────────────────────────────────────────────
# Step 3: Combine and score
# ─────────────────────────────────────────────────────────────
node -e "
  const fs = require('fs');

  // Parse churn
  const churnLines = fs.readFileSync('$CHURN_FILE', 'utf8').trim().split('\n').filter(Boolean);
  const churn = {};
  let maxChurn = 0;
  for (const line of churnLines) {
    const [file, count] = line.split('\t');
    churn[file] = parseInt(count, 10);
    maxChurn = Math.max(maxChurn, churn[file]);
  }

  // Parse complexity
  const complexLines = fs.readFileSync('$COMPLEXITY_FILE', 'utf8').trim().split('\n').filter(Boolean);
  const complexity = {};
  let maxComplexity = 0;
  for (const line of complexLines) {
    const [file, count] = line.split('\t');
    complexity[file] = parseInt(count, 10);
    maxComplexity = Math.max(maxComplexity, complexity[file]);
  }

  // All files that appear in either dataset
  const allFiles = new Set([...Object.keys(churn), ...Object.keys(complexity)]);

  // Score: normalized churn (0-1) x normalized complexity (0-1)
  const scored = [];
  for (const file of allFiles) {
    const c = churn[file] || 0;
    const x = complexity[file] || 0;
    if (c === 0 || x === 0) continue; // Only care about files with BOTH
    const normChurn = maxChurn > 0 ? c / maxChurn : 0;
    const normComplexity = maxComplexity > 0 ? x / maxComplexity : 0;
    const score = normChurn * normComplexity;
    scored.push({ file, churn: c, complexity: x, score: Math.round(score * 1000) / 1000 });
  }

  scored.sort((a, b) => b.score - a.score);
  const top = scored.slice(0, $TOP);

  // Output table
  console.log('PRIORITY  CHURN  COMPLEXITY  FILE');
  console.log('────────  ─────  ──────────  ────');
  for (const { file, churn, complexity, score } of top) {
    console.log(
      score.toFixed(3).padStart(8) + '  ' +
      churn.toString().padStart(5) + '  ' +
      complexity.toString().padStart(10) + '  ' +
      file
    );
  }

  console.log('');
  console.log('Files shown: ' + top.length + ' of ' + scored.length + ' with both churn and complexity.');
  console.log('These are your refactoring backlog. Start from the top.');

  // Save as JSON for scripting
  const outputPath = '$REPO_ROOT/.quality/churn-complexity.json';
  fs.writeFileSync(outputPath, JSON.stringify({ generated: new Date().toISOString(), results: scored }, null, 2));
  console.log('Full results saved: ' + outputPath);
"

rm -f "$CHURN_FILE" "$COMPLEXITY_FILE"
```

### How to Interpret the Output

```
PRIORITY  CHURN  COMPLEXITY  FILE
────────  ─────  ──────────  ────
   1.000     47          12  src/engine/order-matcher.ts
   0.723     38           9  src/api/handlers/trade.ts
   0.541     22          11  packages/core/src/validator.ts
   0.312     31           4  src/engine/position-tracker.ts
   0.289     15           8  src/api/middleware/auth.ts
```

The top 10 files are your refactoring backlog for the current sprint. Do not refactor anything else until these are addressed. The math is simple: these files cause the most pain because they change the most and are the hardest to change safely.

### Automating the Priority Review

Add this to your CI pipeline or sprint planning workflow:

```json
{
  "scripts": {
    "quality:assess": "./scripts/assess-codebase.sh",
    "quality:ratchet": "./scripts/quality-ratchet.sh check",
    "quality:priorities": "./scripts/churn-complexity.sh --days 90 --top 10"
  }
}
```

---

## 4. The Strangler Fig Pattern for Gradual Rewrites

Named after the strangler fig tree that grows around and eventually replaces its host tree. The pattern: build the new module alongside the old one. Gradually migrate callers. Delete the old module when it has zero imports.

This is the only safe way to rewrite a module. Big bang rewrites fail because they require everything to work perfectly on day one. The strangler fig requires nothing to be perfect -- it just requires steady progress.

### Step-by-Step Process

1. **Create the new module** alongside the old one with the improved API
2. **Route new callers** to the new module
3. **Migrate existing callers** one at a time, with tests at each step
4. **Track fan-in** of the old module -- when it reaches zero, delete it
5. **Block new imports** of the old module with ESLint rules

### Example: Replacing a Legacy Parser

Old module: `src/legacy/parser.ts` -- 800 lines, no types, no tests.

New module: `src/parser/index.ts` -- clean API, full types, full test coverage.

```typescript
// src/parser/index.ts -- New module
// This replaces src/legacy/parser.ts via the strangler fig pattern.
// See ADR-007: Parser Rewrite for context.

export interface ParseResult {
  readonly tokens: ReadonlyArray<Token>;
  readonly errors: ReadonlyArray<ParseError>;
}

export function parse(input: string): ParseResult {
  // Clean implementation with proper error handling
  // ...
}
```

### ESLint: Block New Imports of the Deprecated Module

Add a `no-restricted-imports` rule to prevent new code from importing the old module:

```js
// In eslint.config.mjs or your shared config
{
  rules: {
    "no-restricted-imports": ["error", {
      patterns: [
        {
          group: ["**/legacy/parser", "**/legacy/parser.ts"],
          message: "Use 'src/parser' instead. The legacy parser is deprecated (ADR-007)."
        }
      ]
    }]
  }
}
```

### dependency-cruiser: Track Fan-In and Flag Deprecated Imports

Create a dependency-cruiser rule that flags any remaining imports of the deprecated module:

```js
// .dependency-cruiser.cjs
module.exports = {
  forbidden: [
    {
      name: "no-deprecated-parser",
      severity: "warn",  // Start as warn, promote to error when ready
      comment: "Strangler fig: migrate to src/parser/. See ADR-007.",
      from: {},
      to: {
        path: "^src/legacy/parser\\.ts$"
      }
    }
  ],
  options: {
    doNotFollow: {
      path: "node_modules"
    },
    tsPreCompilationDeps: true,
    tsConfig: {
      fileName: "tsconfig.json"
    }
  }
};
```

Run the fan-in check:

```bash
# Count remaining imports of the deprecated module
npx depcruise --config .dependency-cruiser.cjs --output-type err src/

# Or get a count directly
npx depcruise --config .dependency-cruiser.cjs --output-type json src/ \
  | node -e "
    const data = JSON.parse(require('fs').readFileSync('/dev/stdin','utf8'));
    const violations = data.summary.violations.filter(v => v.rule.name === 'no-deprecated-parser');
    console.log('Remaining imports of legacy parser: ' + violations.length);
    violations.forEach(v => console.log('  ' + v.from + ' → ' + v.to));
  "
```

### Completion Criteria

The strangler fig is complete when:

1. Fan-in of the old module is **zero** (no imports remain)
2. All tests pass with the new module
3. The old module is deleted
4. The ESLint restriction is removed (no longer needed)
5. The dependency-cruiser rule is removed
6. The ADR is updated to status "completed"

```bash
# Final verification before deletion
npx depcruise --output-type json src/ | node -e "
  const data = JSON.parse(require('fs').readFileSync('/dev/stdin','utf8'));
  const deps = data.modules.find(m => m.source === 'src/legacy/parser.ts');
  if (!deps || deps.dependents.length === 0) {
    console.log('Safe to delete: zero remaining dependents.');
  } else {
    console.log('NOT safe to delete: ' + deps.dependents.length + ' remaining dependents:');
    deps.dependents.forEach(d => console.log('  ' + d));
  }
"
```

---

## 5. Extract-and-Delegate Patterns

These are the mechanical refactoring patterns you will use most often. Each pattern has a before/after example and a clear trigger condition.

### Pattern 1: God Function -- Extract Pure Functions

**Trigger**: A function longer than 30 lines or with cognitive complexity > 10.

**Before**:

```typescript
// 87 lines, cognitive complexity: 23
function processOrder(order: Order, inventory: Inventory, user: User): OrderResult {
  // Validate order
  if (!order.items || order.items.length === 0) {
    throw new Error("Empty order");
  }
  for (const item of order.items) {
    if (item.quantity <= 0) {
      throw new Error(`Invalid quantity for ${item.productId}`);
    }
    if (!inventory.has(item.productId)) {
      throw new Error(`Product not found: ${item.productId}`);
    }
    if (inventory.get(item.productId)!.stock < item.quantity) {
      throw new Error(`Insufficient stock for ${item.productId}`);
    }
  }

  // Calculate totals
  let subtotal = 0;
  for (const item of order.items) {
    const product = inventory.get(item.productId)!;
    subtotal += product.price * item.quantity;
  }
  const discount = user.tier === "premium" ? subtotal * 0.1 : 0;
  const tax = (subtotal - discount) * 0.08;
  const total = subtotal - discount + tax;

  // Update inventory
  for (const item of order.items) {
    const product = inventory.get(item.productId)!;
    product.stock -= item.quantity;
  }

  return { orderId: generateId(), total, tax, discount, status: "confirmed" };
}
```

**After**:

```typescript
// Each extracted function is pure, testable, and has a single responsibility.

function validateOrder(order: Order, inventory: Inventory): void {
  if (!order.items || order.items.length === 0) {
    throw new Error("Empty order");
  }
  for (const item of order.items) {
    validateOrderItem(item, inventory);
  }
}

function validateOrderItem(item: OrderItem, inventory: Inventory): void {
  if (item.quantity <= 0) {
    throw new Error(`Invalid quantity for ${item.productId}`);
  }
  const product = inventory.get(item.productId);
  if (!product) {
    throw new Error(`Product not found: ${item.productId}`);
  }
  if (product.stock < item.quantity) {
    throw new Error(`Insufficient stock for ${item.productId}`);
  }
}

function calculateTotals(
  items: ReadonlyArray<OrderItem>,
  inventory: Inventory,
  userTier: string
): { subtotal: number; discount: number; tax: number; total: number } {
  const subtotal = items.reduce((sum, item) => {
    const product = inventory.get(item.productId)!;
    return sum + product.price * item.quantity;
  }, 0);
  const discount = userTier === "premium" ? subtotal * 0.1 : 0;
  const tax = (subtotal - discount) * 0.08;
  return { subtotal, discount, tax, total: subtotal - discount + tax };
}

function deductInventory(items: ReadonlyArray<OrderItem>, inventory: Inventory): void {
  for (const item of items) {
    const product = inventory.get(item.productId)!;
    product.stock -= item.quantity;
  }
}

function processOrder(order: Order, inventory: Inventory, user: User): OrderResult {
  validateOrder(order, inventory);
  const totals = calculateTotals(order.items, inventory, user.tier);
  deductInventory(order.items, inventory);
  return { orderId: generateId(), ...totals, status: "confirmed" };
}
```

The orchestrator (`processOrder`) is now 5 lines. Each extracted function is independently testable. `calculateTotals` is a pure function -- no side effects, easy to test with any inputs.

### Pattern 2: God File -- Extract by Responsibility

**Trigger**: A file longer than 500 lines, or a file that contains multiple unrelated concepts.

**Before**: `src/utils.ts` -- 800 lines containing date formatting, string manipulation, validation, HTTP helpers, and math utilities.

**After**:

```
src/utils/
  dates.ts          # formatDate, parseISO, addDays
  strings.ts        # capitalize, truncate, slugify
  validation.ts     # isEmail, isUrl, isPositive
  http.ts           # buildUrl, parseQueryString
  math.ts           # clamp, lerp, roundTo
  index.ts          # re-exports everything for backward compatibility
```

The `index.ts` barrel ensures existing imports still work:

```typescript
// src/utils/index.ts
export { formatDate, parseISO, addDays } from "./dates.js";
export { capitalize, truncate, slugify } from "./strings.js";
export { isEmail, isUrl, isPositive } from "./validation.js";
export { buildUrl, parseQueryString } from "./http.js";
export { clamp, lerp, roundTo } from "./math.js";
```

### Pattern 3: Deep Nesting -- Early Returns and Guard Clauses

**Trigger**: Nesting depth > 3 levels.

**Before**:

```typescript
function getDiscount(user: User, order: Order): number {
  if (user) {
    if (user.isActive) {
      if (order.total > 100) {
        if (user.tier === "premium") {
          return order.total * 0.2;
        } else {
          return order.total * 0.1;
        }
      } else {
        return 0;
      }
    } else {
      return 0;
    }
  } else {
    return 0;
  }
}
```

**After**:

```typescript
function getDiscount(user: User | null, order: Order): number {
  if (!user) return 0;
  if (!user.isActive) return 0;
  if (order.total <= 100) return 0;

  return user.tier === "premium" ? order.total * 0.2 : order.total * 0.1;
}
```

Same logic, maximum nesting depth of 1. Each guard clause handles one invalid case and exits early.

### Pattern 4: Long Parameter Lists -- Options Objects

**Trigger**: More than 3 parameters on a function.

**Before**:

```typescript
function createUser(
  name: string,
  email: string,
  role: string,
  department: string,
  managerId: string | null,
  startDate: Date,
  isContractor: boolean
): User {
  // ...
}

// Call site is unreadable:
createUser("Alice", "alice@co.com", "engineer", "platform", "mgr-1", new Date(), false);
```

**After**:

```typescript
interface CreateUserOptions {
  readonly name: string;
  readonly email: string;
  readonly role: string;
  readonly department: string;
  readonly managerId: string | null;
  readonly startDate: Date;
  readonly isContractor: boolean;
}

function createUser(options: CreateUserOptions): User {
  // ...
}

// Call site is self-documenting:
createUser({
  name: "Alice",
  email: "alice@co.com",
  role: "engineer",
  department: "platform",
  managerId: "mgr-1",
  startDate: new Date(),
  isContractor: false,
});
```

### Pattern 5: Feature Envy -- Move Method to Data Owner

**Trigger**: A function that accesses more properties from another object than from its own context.

**Before**:

```typescript
// This function lives in order-processor.ts but accesses nothing except user properties
function calculateUserDiscount(user: User): number {
  if (user.tier === "premium" && user.ordersThisMonth > 5) {
    return user.lifetimeSpend > 10000 ? 0.2 : 0.15;
  }
  if (user.tier === "standard" && user.ordersThisMonth > 10) {
    return 0.05;
  }
  return 0;
}
```

**After**: Move to a user-related module or make it a method on the User type:

```typescript
// src/domain/user-pricing.ts
export function calculateDiscount(user: User): number {
  if (user.tier === "premium" && user.ordersThisMonth > 5) {
    return user.lifetimeSpend > 10000 ? 0.2 : 0.15;
  }
  if (user.tier === "standard" && user.ordersThisMonth > 10) {
    return 0.05;
  }
  return 0;
}
```

The test for feature envy: if you could delete the function's host file and it would compile identically in the data owner's file, it belongs there.

---

## 6. Dependency Inversion for Testability

Hard dependencies -- direct imports of database clients, HTTP libraries, file system modules -- make code impossible to test in isolation. Dependency inversion means: accept your dependencies as parameters instead of importing them directly.

### The Problem

```typescript
// src/services/user-service.ts -- HARD TO TEST
import { db } from "../database/client.js";
import { sendEmail } from "../email/mailer.js";
import { logger } from "../observability/logger.js";

export async function createUser(data: CreateUserInput): Promise<User> {
  const user = await db.insert(users).values(data).returning();
  await sendEmail({ to: data.email, subject: "Welcome" });
  logger.info("User created", { userId: user.id });
  return user;
}
```

Testing this function requires:
- A real database (or mocking the module system)
- A real email service (or mocking the module system)
- Dealing with logger output

Module-level mocking (`vi.mock("../database/client")`) is fragile, couples tests to file paths, and breaks when you rename files.

### The Solution: Constructor/Function Injection

```typescript
// src/services/user-service.ts -- EASY TO TEST
export interface UserServiceDeps {
  readonly db: {
    insert(table: typeof users): InsertBuilder;
  };
  readonly sendEmail: (options: EmailOptions) => Promise<void>;
  readonly logger: {
    info(message: string, context?: Record<string, unknown>): void;
  };
}

export function createUserService(deps: UserServiceDeps) {
  return {
    async createUser(data: CreateUserInput): Promise<User> {
      const user = await deps.db.insert(users).values(data).returning();
      await deps.sendEmail({ to: data.email, subject: "Welcome" });
      deps.logger.info("User created", { userId: user.id });
      return user;
    },
  };
}
```

### Testing with Injected Dependencies

```typescript
// src/services/__tests__/user-service.test.ts
import { describe, it, expect, vi } from "vitest";
import { createUserService } from "../user-service.js";

describe("createUserService", () => {
  function buildDeps(overrides?: Partial<UserServiceDeps>): UserServiceDeps {
    return {
      db: {
        insert: vi.fn().mockReturnValue({
          values: vi.fn().mockReturnValue({
            returning: vi.fn().mockResolvedValue({ id: "user-1", email: "a@b.com" }),
          }),
        }),
      },
      sendEmail: vi.fn().mockResolvedValue(undefined),
      logger: { info: vi.fn() },
      ...overrides,
    };
  }

  it("inserts user into database", async () => {
    const deps = buildDeps();
    const service = createUserService(deps);

    await service.createUser({ email: "a@b.com", name: "Alice" });

    expect(deps.db.insert).toHaveBeenCalled();
  });

  it("sends welcome email after creation", async () => {
    const deps = buildDeps();
    const service = createUserService(deps);

    await service.createUser({ email: "a@b.com", name: "Alice" });

    expect(deps.sendEmail).toHaveBeenCalledWith({
      to: "a@b.com",
      subject: "Welcome",
    });
  });

  it("logs user creation", async () => {
    const deps = buildDeps();
    const service = createUserService(deps);

    await service.createUser({ email: "a@b.com", name: "Alice" });

    expect(deps.logger.info).toHaveBeenCalledWith("User created", { userId: "user-1" });
  });
});
```

No module mocking. No database. No email service. Tests run in milliseconds. Each test verifies one behavior.

### Production Wiring

The real dependencies get wired at the composition root -- the entry point of your application:

```typescript
// src/main.ts -- Composition root
import { db } from "./database/client.js";
import { sendEmail } from "./email/mailer.js";
import { logger } from "./observability/logger.js";
import { createUserService } from "./services/user-service.js";

const userService = createUserService({ db, sendEmail, logger });

// Use userService in your routes/handlers
```

### ESLint Rule: Enforce the Boundary

Prevent domain/service code from directly importing infrastructure:

```js
// In eslint.config.mjs
{
  files: ["src/services/**/*.ts", "src/domain/**/*.ts"],
  rules: {
    "no-restricted-imports": ["error", {
      patterns: [
        {
          group: ["**/database/client*", "**/email/mailer*", "**/observability/logger*"],
          message: "Domain/service code must not import infrastructure directly. Accept dependencies via constructor injection."
        }
      ]
    }]
  }
}
```

This rule ensures that the boundary stays clean. New developers who try to import the database directly from a service file get an immediate, actionable error message.

---

## 7. Safe Refactoring Workflow

Refactoring without tests is gambling. Refactoring with tests is engineering. This workflow ensures every refactoring step is verified.

### Step 1: Write Characterization Tests

A characterization test captures the current behavior of existing code, including its bugs. The goal is not to test correctness -- it is to detect unintended changes.

```typescript
// src/legacy/__tests__/parser.characterization.test.ts
// Characterization tests for legacy parser.
// These tests capture CURRENT behavior (including known bugs).
// They exist to detect unintended changes during refactoring.
// DO NOT fix bugs in these tests. File bug reports instead.

import { describe, it, expect } from "vitest";
import { legacyParse } from "../parser.js";

describe("legacy parser characterization", () => {
  // Capture normal behavior
  it("parses simple expression", () => {
    expect(legacyParse("1 + 2")).toEqual({
      type: "binary",
      op: "+",
      left: { type: "number", value: 1 },
      right: { type: "number", value: 2 },
    });
  });

  // Capture edge cases -- even if the behavior seems wrong
  it("treats empty string as null (known bug, see ISSUE-123)", () => {
    expect(legacyParse("")).toBeNull();
  });

  // Capture error behavior
  it("throws on unmatched parenthesis", () => {
    expect(() => legacyParse("(1 + 2")).toThrow("Unexpected end of input");
  });

  // Generate tests from production data if available
  const PRODUCTION_SAMPLES = [
    { input: "price > 100 AND quantity < 50", desc: "compound filter" },
    { input: "name LIKE '%test%'", desc: "like pattern" },
    { input: "date BETWEEN '2026-01-01' AND '2026-12-31'", desc: "date range" },
  ];

  for (const { input, desc } of PRODUCTION_SAMPLES) {
    it(`handles production sample: ${desc}`, () => {
      // First run: capture output with toMatchSnapshot()
      // Later runs: detect changes
      expect(legacyParse(input)).toMatchSnapshot();
    });
  }
});
```

### Step 2: Verify Tests Pass on Unchanged Code

```bash
pnpm vitest run src/legacy/__tests__/parser.characterization.test.ts
```

If any test fails, you have a bug in the test, not in the code. Fix the test. Every characterization test must pass BEFORE you touch the production code.

### Step 3: Refactor in Small Steps, Test After Each

Each step is a single, mechanical transformation:

```bash
# Step 3a: Extract validation into separate function
# Edit the file...
pnpm vitest run src/legacy/__tests__/parser.characterization.test.ts
git add -A && git commit -m "refactor: extract validation from parser"

# Step 3b: Replace mutable accumulator with reduce
# Edit the file...
pnpm vitest run src/legacy/__tests__/parser.characterization.test.ts
git add -A && git commit -m "refactor: use reduce in parser tokenizer"

# Step 3c: Add explicit return types
# Edit the file...
pnpm vitest run src/legacy/__tests__/parser.characterization.test.ts
git add -A && git commit -m "refactor: add return types to parser functions"
```

Each commit is independently valid. If any step breaks the tests, revert that single commit and try a smaller step.

### Step 4: Verify Mutation Score Did Not Drop

If you have mutation testing set up (see the mutation-testing reference), verify that your refactoring did not weaken the test suite:

```bash
# Before refactoring: capture mutation score
npx stryker run --reporters json > .quality/mutation-before.json

# After refactoring: compare
npx stryker run --reporters json > .quality/mutation-after.json

node -e "
  const before = require('./.quality/mutation-before.json');
  const after = require('./.quality/mutation-after.json');
  const scoreBefore = before.thresholds?.score ?? before.mutationScore;
  const scoreAfter = after.thresholds?.score ?? after.mutationScore;
  if (scoreAfter < scoreBefore) {
    console.error('Mutation score dropped: ' + scoreBefore + '% → ' + scoreAfter + '%');
    process.exit(1);
  }
  console.log('Mutation score maintained: ' + scoreBefore + '% → ' + scoreAfter + '%');
"
```

### Step 5: Update Design Metrics Baseline

After a successful refactoring, update the ratchet baseline to lock in the improvement:

```bash
./scripts/quality-ratchet.sh baseline
git add .quality/ratchet-baseline.json
git commit -m "chore: update quality baseline after parser refactoring"
```

### Git Workflow Summary

```
[characterization tests] → commit
[refactor step 1] → test → commit
[refactor step 2] → test → commit
[refactor step 3] → test → commit
[update baseline] → commit
```

Every commit passes CI independently. If you need to revert, you revert one small step, not the entire refactoring.

---

## 8. Incremental Adoption for Greenfield Standards

You cannot go from zero quality gates to full enforcement overnight. This is a four-week adoption schedule that takes a codebase from no enforcement to full ratchet mode.

### Week 1: Observe and Measure

**Goal**: Enable all metrics in warning mode. Capture the baseline. Do not block anything.

```bash
# Run initial assessment
chmod +x scripts/assess-codebase.sh
./scripts/assess-codebase.sh

# Capture ratchet baseline
chmod +x scripts/quality-ratchet.sh
./scripts/quality-ratchet.sh baseline

# Run churn x complexity to identify priorities
chmod +x scripts/churn-complexity.sh
./scripts/churn-complexity.sh --days 90 --top 20
```

Add ESLint rules in warn mode so developers see the issues without being blocked:

```js
// Temporary: warning mode for new rules
{
  rules: {
    "sonarjs/cognitive-complexity": ["warn", 15],
    "@typescript-eslint/no-explicit-any": "warn",
    "import-x/no-cycle": "warn",
  }
}
```

**Deliverable**: Assessment JSON, ratchet baseline, prioritized file list shared with the team.

### Week 2: Block Regressions and Fix Easy Wins

**Goal**: Enable the ratchet in pre-push hooks. Fix the violations that take less than 30 minutes each.

```bash
# Add ratchet to pre-push
# In .husky/pre-push:
./scripts/quality-ratchet.sh check

# Fix easy violations (unused variables, missing return types, etc.)
# These are typically mechanical fixes that don't require understanding the code
pnpm eslint --fix .

# Recapture baseline after fixes
./scripts/quality-ratchet.sh baseline
```

Promote easy rules from warn to error:

```js
{
  rules: {
    "@typescript-eslint/no-explicit-any": "error",  // Promoted from warn
    "sonarjs/cognitive-complexity": ["warn", 15],    // Still warn (needs refactoring)
    "import-x/no-cycle": "warn",                    // Still warn (needs architecture work)
  }
}
```

**Deliverable**: Ratchet active in pre-push. Easy violations fixed. Updated baseline committed.

### Week 3: Refactor Priority Files

**Goal**: Apply the safe refactoring workflow (Section 7) to the top 5 files from the churn x complexity report.

For each file:
1. Write characterization tests
2. Apply extract-and-delegate patterns (Section 5)
3. Run tests after each step
4. Update the baseline

```bash
# For each priority file:
# 1. Write characterization tests
# 2. Refactor
# 3. Update baseline
./scripts/quality-ratchet.sh baseline
./scripts/churn-complexity.sh --days 90 --top 20
# Verify the refactored files dropped off the top of the list
```

**Deliverable**: Top 5 files refactored. Characterization tests added. Baseline updated.

### Week 4: Tighten and Repeat

**Goal**: Tighten the ratchet by 10%. Promote more rules from warn to error. Establish the monthly cadence.

```bash
# Tighten budgets
./scripts/quality-ratchet.sh tighten 3

# Promote cognitive complexity to error (after refactoring reduced the count)
# In ESLint config:
# "sonarjs/cognitive-complexity": ["error", 15]

# Run full assessment to compare with Week 1
./scripts/assess-codebase.sh --compare .quality/assessment-week1.json
```

**Deliverable**: Tightened baseline. Before/after assessment comparison. Monthly cadence established.

### Presenting Progress to Stakeholders

Generate a simple trend from your assessment history:

```bash
#!/usr/bin/env bash
# scripts/quality-trend.sh
# Outputs a markdown table showing quality progression over time.

REPO_ROOT="$(git rev-parse --show-toplevel)"

echo "| Date | Grade | ESLint | Circular | God Files | Coverage | Complexity | any |"
echo "|------|-------|--------|----------|-----------|----------|------------|-----|"

for file in "$REPO_ROOT"/.quality/assessment-*.json; do
  [ -f "$file" ] || continue
  node -e "
    const d = require('$file');
    const m = d.metrics;
    const date = d.timestamp.split('T')[0];
    console.log('| ' + date + ' | ' + d.overall_grade + ' | ' +
      m.eslint_violations.value + ' | ' +
      m.circular_dependencies.value + ' | ' +
      m.god_files.value + ' | ' +
      m.test_coverage_pct.value + '% | ' +
      m.high_complexity_functions.value + ' | ' +
      m.any_type_usage.value + ' |');
  "
done
```

Output:

```
| Date       | Grade | ESLint | Circular | God Files | Coverage | Complexity | any |
|------------|-------|--------|----------|-----------|----------|------------|-----|
| 2026-01-13 | D     | 187    | 8        | 14        | 42%      | 31         | 89  |
| 2026-01-27 | C     | 94     | 5        | 10        | 58%      | 18         | 43  |
| 2026-02-10 | B     | 12     | 1        | 3         | 78%      | 4          | 7   |
```

Numbers going down, grades going up. This is the only stakeholder communication that matters.

---

## 9. Architecture Decision Records (ADRs) for Refactoring

Refactoring decisions are architecture decisions. When you change module boundaries, replace a dependency, or restructure a public API, that decision should be documented so future developers understand why.

### Why Document Refactoring Decisions

- Code shows **what** was done. ADRs explain **why**.
- Six months from now, someone will ask "why did we split this module?" The ADR answers that.
- ADRs prevent re-litigation. If the team decided to use the strangler fig pattern for the parser rewrite, that is a settled question -- documented, reviewed, committed.

### ADR Template

```markdown
# ADR-NNN: [Title]

## Status

[Proposed | Accepted | Deprecated | Superseded by ADR-NNN]

## Context

[What is the problem? Why does this need to change? Include metrics from the assessment
if relevant (e.g., "src/legacy/parser.ts has a churn-complexity score of 0.91 and a
cognitive complexity of 47").]

## Decision

[What are we going to do? Be specific about the pattern (strangler fig, extract-and-delegate,
dependency inversion) and the timeline.]

## Consequences

### Positive
- [Expected benefits]

### Negative
- [Expected costs, risks, or tradeoffs]

### Metrics
- [How will we measure success? Reference specific metrics from the ratchet baseline.]
```

### Example ADR

```markdown
# ADR-007: Replace Legacy Parser with Typed Parser Module

## Status

Accepted

## Context

`src/legacy/parser.ts` is 823 lines with no type safety and no tests. It has a
churn-complexity score of 0.91 (highest in the codebase) -- it changes in 47 out
of the last 180 days and has 12 functions with cognitive complexity > 15.

Every bug fix in this file risks introducing new regressions. The last three P1
incidents (INC-041, INC-043, INC-048) traced back to changes in this file.

## Decision

Replace `src/legacy/parser.ts` using the strangler fig pattern:

1. Create `src/parser/` with a clean, typed API
2. Add ESLint `no-restricted-imports` for `src/legacy/parser`
3. Migrate callers one at a time over 3 sprints
4. Delete `src/legacy/parser.ts` when fan-in reaches zero

## Consequences

### Positive
- Type-safe parser reduces runtime errors
- Smaller, focused files reduce cognitive load
- Full test coverage enables safe future changes

### Negative
- Two parser modules exist during migration (3 sprints)
- Developers need to learn which parser to use (ESLint rule handles this)

### Metrics
- churn-complexity score target: < 0.2 for new parser module
- cognitive complexity target: < 10 per function
- test coverage target: 95% for `src/parser/`
```

### Where to Store ADRs

```
docs/
  adr/
    0001-use-typescript-strict-mode.md
    0002-adopt-vitest-over-jest.md
    ...
    0007-replace-legacy-parser.md
    template.md
```

Number ADRs sequentially. Never reuse numbers. Deprecated ADRs stay in the directory with their status updated -- they are part of the historical record.

### When to Write an ADR

Write an ADR when the refactoring:
- Changes module boundaries (splitting, merging, renaming)
- Changes a public API that other modules depend on
- Introduces a new pattern or library
- Deletes a significant module
- Takes more than one sprint to complete

Do NOT write an ADR for:
- Renaming a variable
- Extracting a function within the same file
- Adding tests
- Fixing a bug

---

## 10. Anti-Patterns to Avoid

These are the mistakes that make refactoring fail. Every one of these has been observed in production codebases. Learn from other people's pain.

### Anti-Pattern 1: Big Bang Rewrites

**The mistake**: "Let's rewrite the whole module from scratch. It'll take two months. We'll switch over on release day."

**Why it fails**: Two months of development with no production validation. The new code has zero battle-testing. The switch-over day reveals 47 edge cases nobody anticipated. The team spends the next month firefighting. The rewrite is abandoned, and the old code gets patched back in.

**The fix**: Strangler fig (Section 4). Always. No exceptions. If someone proposes a big bang rewrite, show them this section and ask them to name the last big bang rewrite that succeeded. They cannot.

### Anti-Pattern 2: Refactoring Without Tests

**The mistake**: "I know this code well enough. I don't need tests. I'll just be careful."

**Why it fails**: You are not as careful as you think. The code has edge cases you do not know about. The refactoring changes behavior in a way that is invisible during code review but visible in production at 3 AM.

**The fix**: Characterization tests first (Section 7, Step 1). If you cannot write characterization tests because the code is too coupled, that is the first refactoring: make it testable (Section 6).

### Anti-Pattern 3: Over-Abstracting

**The mistake**: "This function is used in one place, but someday we might need to configure it differently. Let me create a factory that returns a strategy that implements an interface."

**Why it fails**: Abstractions have a cost -- indirection makes code harder to read, debug, and modify. An abstraction that serves one use case is not an abstraction; it is an obstruction.

**The rule**: Do not create an abstraction until you have three concrete use cases. Two is a coincidence. Three is a pattern.

```typescript
// WRONG: Abstraction for one use case
interface PriceCalculator {
  calculate(items: Item[]): number;
}
class StandardPriceCalculator implements PriceCalculator {
  calculate(items: Item[]): number {
    return items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  }
}
// ...used in exactly one place

// RIGHT: Direct code for one use case
function calculatePrice(items: ReadonlyArray<Item>): number {
  return items.reduce((sum, item) => sum + item.price * item.quantity, 0);
}
```

### Anti-Pattern 4: Refactoring Everything at Once

**The mistake**: "The codebase has 200 ESLint violations. Let's fix them all in one PR."

**Why it fails**: A 200-file PR is unreviewable. Reviewers approve it because they cannot possibly read it all. Bugs hide in the noise. And if you need to revert, you revert everything.

**The fix**: Churn x complexity prioritization (Section 3). Fix the top 5 files. Then the next 5. Each PR touches at most 3 files. Each PR is reviewable in 15 minutes.

### Anti-Pattern 5: "Clean Code" Zealotry

**The mistake**: Spending two hours making a function "cleaner" when it works correctly, has tests, and nobody needs to change it.

**Why it fails**: Refactoring is not free. Every change has a risk of introducing bugs. If the code works, is tested, and is not in the high-churn list, leave it alone. Your time is better spent on the files that actually cause problems.

**The rule**: Three lines of clear code are better than one line of clever code. But zero lines of changed working code are better than three lines of unnecessary refactoring.

```typescript
// This is fine. Do not refactor it "for fun."
function isEligible(user: User): boolean {
  if (user.age < 18) return false;
  if (!user.hasVerifiedEmail) return false;
  if (user.isBanned) return false;
  return true;
}

// This is "cleaner" but harder to debug and add breakpoints to:
const isEligible = (u: User): boolean =>
  u.age >= 18 && u.hasVerifiedEmail && !u.isBanned;
```

### Anti-Pattern 6: Refactoring Without Measuring

**The mistake**: "I refactored the auth module. It's much better now." How do you know? "It feels better."

**Why it fails**: Feelings are not metrics. The assessment script (Section 1) exists so you can prove the refactoring improved the codebase. Without before/after numbers, you cannot distinguish productive refactoring from code tourism.

**The fix**: Run the assessment before and after. If the numbers did not improve, the refactoring did not work. Revert it.

```bash
# Before
./scripts/assess-codebase.sh
# Refactor...
# After
./scripts/assess-codebase.sh --compare .quality/assessment-BEFORE.json
```

### Anti-Pattern 7: Ignoring the Ratchet

**The mistake**: "The ratchet is too strict. Let's disable it for this PR because we're in a hurry."

**Why it fails**: Every exception becomes precedent. If you disable the ratchet once, you will disable it again. Within a month, the ratchet is meaningless. Within three months, the codebase is worse than before you started.

**The fix**: The ratchet is never disabled. If a developer cannot make the ratchet pass, they have two options: fix their regressions, or do not merge. There is no third option.

---

## Summary: The Refactoring Decision Tree

```
Is the file in the top 10 churn x complexity list?
├── No → Leave it alone. Fix something that matters.
└── Yes → Does it have characterization tests?
    ├── No → Write characterization tests first (Section 7).
    └── Yes → Is it a god file (>500 LoC)?
        ├── Yes → Extract by responsibility (Section 5, Pattern 2).
        └── No → Is it a god function (>30 lines)?
            ├── Yes → Extract pure functions (Section 5, Pattern 1).
            └── No → Is it deeply nested (>3 levels)?
                ├── Yes → Early returns and guard clauses (Section 5, Pattern 3).
                └── No → Is it hard to test due to direct imports?
                    ├── Yes → Dependency inversion (Section 6).
                    └── No → Is it a full module that needs replacement?
                        ├── Yes → Strangler fig (Section 4). Write an ADR (Section 9).
                        └── No → Apply the specific extract pattern that fits.

After EVERY refactoring step:
1. Run characterization tests
2. Commit
3. Update the ratchet baseline
```
