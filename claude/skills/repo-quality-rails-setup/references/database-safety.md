# Database Safety

Database safety infrastructure for TypeScript monorepos using Drizzle ORM with PostgreSQL/TimescaleDB. These gates prevent broken migrations from reaching production, detect schema drift between environments, and enforce that all database changes flow through a controlled pipeline.

## The Golden Rule

**NEVER modify the database manually.** No `ALTER TABLE`, `INSERT`, `UPDATE`, `DELETE`, `CREATE INDEX`, or any other DDL/DML run directly against any database -- local, staging, or production.

All schema changes MUST go through the migration pipeline. No exceptions. No "just this once."

**Why this matters:** Manual changes mask broken migrations. A migration that adds a column will "pass" locally if you already ran `ALTER TABLE ADD COLUMN` by hand. But that same migration will fail on every other environment -- CI, staging, production -- because the column was never actually created by the migration. The local database silently diverges from what the migration pipeline produces, and you won't find out until production breaks.

This has a name: **schema drift**. It's one of the hardest bugs to diagnose because the symptoms appear far from the cause. The developer who ran the manual change sees everything working. The production deploy fails hours or days later with a cryptic Postgres error.

The fix is architectural: make it impossible for manual changes to go undetected. That's what the rest of this document covers.

## Migration Pipeline

The migration pipeline has two sources of migrations that are applied in order:

### 1. Drizzle-Kit Schema-Driven Migrations

Drizzle ORM keeps the database schema defined in TypeScript. When you change the schema file, `drizzle-kit generate` produces a SQL migration file that transitions the database from the old schema to the new one.

```bash
# After modifying packages/database/src/schema.ts
pnpm drizzle-kit generate

# This creates a file like:
# packages/database/drizzle/0042_add_user_preferences.sql
```

These migrations are numbered sequentially and tracked in a `drizzle.__drizzle_migrations` table (or similar, depending on configuration).

### 2. Custom SQL Migrations

Some operations can't be expressed through Drizzle's schema DSL:

- TimescaleDB hypertable creation (`SELECT create_hypertable(...)`)
- Complex data backfills
- Materialized view creation
- Extension installation (`CREATE EXTENSION IF NOT EXISTS ...`)
- Partition management
- Custom index types (GIN, BRIN, partial indexes)

These go in a dedicated directory:

```
packages/database/migrations/
  0001_create_extensions.sql
  0002_create_hypertables.sql
  0003_backfill_symbol_ids.sql
```

### Migration Runner

A TypeScript migration runner applies both sets of migrations in the correct order:

```typescript
async function runMigrations(db: PostgresConnection): Promise<void> {
  // 1. Apply Drizzle-generated migrations
  await drizzleMigrate(db, {
    migrationsFolder: "./drizzle",
  });

  // 2. Apply custom SQL migrations
  const customMigrations = await getCustomMigrations("./migrations");
  for (const migration of customMigrations) {
    if (await isAlreadyApplied(db, migration.name)) continue;
    await db.execute(migration.sql);
    await markApplied(db, migration.name);
  }
}
```

Both migration sets are tracked so they are idempotent -- running the migration runner multiple times is safe.

## SQL Migration Linter

A custom TypeScript script (~500 lines) that statically analyzes SQL migration files for dangerous patterns. It parses each `.sql` file and checks for known anti-patterns that cause production incidents.

### Check Categories

Each check has a severity level:

- **ERROR** -- Blocks the commit/push. Must be fixed before the migration can proceed.
- **WARNING** -- Logged for developer attention. Does not block, but should be addressed.

### Check Functions

#### TRUNCATE_WITHOUT_CASCADE (ERROR)

Truncating a table without CASCADE will fail if other tables have foreign key references to it.

```typescript
function checkTruncateWithoutCascade(sql: string): Diagnostic[] {
  const diagnostics: Diagnostic[] = [];
  const regex = /TRUNCATE\s+(?:TABLE\s+)?(\w+)(?!\s+CASCADE)/gi;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(sql)) !== null) {
    diagnostics.push({
      rule: "TRUNCATE_WITHOUT_CASCADE",
      severity: "error",
      message: `TRUNCATE ${match[1]} without CASCADE will fail if foreign keys reference this table`,
      line: getLineNumber(sql, match.index),
      fix: `Add CASCADE: TRUNCATE TABLE ${match[1]} CASCADE`,
    });
  }
  return diagnostics;
}
```

#### UNSAFE_ADD_COLUMN (ERROR)

Adding a column without `IF NOT EXISTS` or exception handling makes migrations non-idempotent. If the migration is interrupted and re-run, it will fail.

```typescript
function checkUnsafeAddColumn(sql: string): Diagnostic[] {
  const diagnostics: Diagnostic[] = [];
  const regex = /ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(?!IF\s+NOT\s+EXISTS)/gi;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(sql)) !== null) {
    // Check if wrapped in exception handler
    if (isInsideExceptionBlock(sql, match.index)) continue;

    diagnostics.push({
      rule: "UNSAFE_ADD_COLUMN",
      severity: "error",
      message: `ADD COLUMN on ${match[1]} without IF NOT EXISTS is not idempotent`,
      line: getLineNumber(sql, match.index),
      fix: `Use: ALTER TABLE ${match[1]} ADD COLUMN IF NOT EXISTS ...`,
    });
  }
  return diagnostics;
}
```

#### MISSING_IF_NOT_EXISTS (WARNING)

`CREATE TABLE` and `CREATE INDEX` without `IF NOT EXISTS` will fail if the object already exists.

```typescript
function checkMissingIfNotExists(sql: string): Diagnostic[] {
  const diagnostics: Diagnostic[] = [];
  const regex = /CREATE\s+(TABLE|INDEX)\s+(?!IF\s+NOT\s+EXISTS)(\w+)/gi;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(sql)) !== null) {
    diagnostics.push({
      rule: "MISSING_IF_NOT_EXISTS",
      severity: "warning",
      message: `CREATE ${match[1]} ${match[2]} without IF NOT EXISTS`,
      line: getLineNumber(sql, match.index),
    });
  }
  return diagnostics;
}
```

#### UNSAFE_DROP (ERROR)

Dropping tables, columns, or indexes without `IF EXISTS` makes migrations fail when re-run.

```typescript
function checkUnsafeDrop(sql: string): Diagnostic[] {
  const diagnostics: Diagnostic[] = [];
  const regex = /DROP\s+(TABLE|INDEX|COLUMN)\s+(?!IF\s+EXISTS)(\w+)/gi;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(sql)) !== null) {
    diagnostics.push({
      rule: "UNSAFE_DROP",
      severity: "error",
      message: `DROP ${match[1]} ${match[2]} without IF EXISTS is not idempotent`,
      line: getLineNumber(sql, match.index),
      fix: `Use: DROP ${match[1]} IF EXISTS ${match[2]}`,
    });
  }
  return diagnostics;
}
```

#### UNSAFE_SET_NOT_NULL (WARNING)

Setting a column to `NOT NULL` without first ensuring all rows have values will fail if any NULLs exist.

```typescript
function checkUnsafeSetNotNull(sql: string): Diagnostic[] {
  const diagnostics: Diagnostic[] = [];
  const regex = /ALTER\s+TABLE\s+(\w+)\s+ALTER\s+COLUMN\s+(\w+)\s+SET\s+NOT\s+NULL/gi;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(sql)) !== null) {
    // Check if preceded by an UPDATE that sets default values
    const preceding = sql.slice(0, match.index);
    const hasBackfill = new RegExp(
      `UPDATE\\s+${match[1]}\\s+SET\\s+${match[2]}`,
      "i"
    ).test(preceding);

    if (!hasBackfill) {
      diagnostics.push({
        rule: "UNSAFE_SET_NOT_NULL",
        severity: "warning",
        message: `SET NOT NULL on ${match[1]}.${match[2]} without preceding UPDATE to fill NULLs`,
        line: getLineNumber(sql, match.index),
        fix: `Add UPDATE ${match[1]} SET ${match[2]} = <default> WHERE ${match[2]} IS NULL before SET NOT NULL`,
      });
    }
  }
  return diagnostics;
}
```

#### UNBATCHED_BACKFILL (WARNING)

Large UPDATE statements without batching can lock tables for extended periods. Backfills on large tables should use a batched `DO $$ ... LOOP` pattern.

```typescript
function checkUnbatchedBackfill(sql: string): Diagnostic[] {
  const diagnostics: Diagnostic[] = [];
  const regex = /UPDATE\s+(\w+)\s+SET/gi;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(sql)) !== null) {
    // Skip if inside a DO $$ LOOP block
    if (isInsideBatchedLoop(sql, match.index)) continue;

    // Skip if the UPDATE has a tight WHERE clause (small scope)
    const statement = extractStatement(sql, match.index);
    if (hasLimitedScope(statement)) continue;

    diagnostics.push({
      rule: "UNBATCHED_BACKFILL",
      severity: "warning",
      message: `UPDATE on ${match[1]} may lock the table. Consider batched DO $$ LOOP for large tables`,
      line: getLineNumber(sql, match.index),
    });
  }
  return diagnostics;
}
```

#### HYPERTABLE_PK_MISSING_TIME_COLUMN (ERROR)

TimescaleDB requires the time partitioning column to be included in all unique indexes and primary keys. Forgetting this produces a Postgres error at migration time.

```typescript
function checkHypertablePkMissingTimeColumn(
  sql: string,
  knownHypertables: Set<string>
): Diagnostic[] {
  const diagnostics: Diagnostic[] = [];
  const regex =
    /(?:PRIMARY\s+KEY|UNIQUE)\s*\(([^)]+)\).*?(?:ON|TABLE)\s+(\w+)/gi;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(sql)) !== null) {
    const columns = match[1];
    const table = match[2];

    if (knownHypertables.has(table) && !columns.includes("time")) {
      diagnostics.push({
        rule: "HYPERTABLE_PK_MISSING_TIME_COLUMN",
        severity: "error",
        message: `Unique constraint on hypertable ${table} must include the time partitioning column`,
        line: getLineNumber(sql, match.index),
      });
    }
  }
  return diagnostics;
}
```

#### DRIZZLE_CONCURRENT_INDEX (ERROR)

Drizzle-generated migrations run inside a transaction. `CREATE INDEX CONCURRENTLY` cannot run inside a transaction -- it will fail at runtime.

```typescript
function checkDrizzleConcurrentIndex(
  sql: string,
  isDrizzleMigration: boolean
): Diagnostic[] {
  if (!isDrizzleMigration) return [];

  const diagnostics: Diagnostic[] = [];
  const regex = /CREATE\s+INDEX\s+CONCURRENTLY/gi;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(sql)) !== null) {
    diagnostics.push({
      rule: "DRIZZLE_CONCURRENT_INDEX",
      severity: "error",
      message: "CONCURRENTLY is not allowed inside transactional Drizzle migrations",
      line: getLineNumber(sql, match.index),
      fix: "Move this to a custom migration file outside the Drizzle transaction",
    });
  }
  return diagnostics;
}
```

#### HYPERTABLE_CONCURRENT_INDEX (ERROR)

TimescaleDB does not support `CREATE INDEX CONCURRENTLY` on hypertables. It will fail at runtime.

```typescript
function checkHypertableConcurrentIndex(
  sql: string,
  knownHypertables: Set<string>
): Diagnostic[] {
  const diagnostics: Diagnostic[] = [];
  const regex =
    /CREATE\s+INDEX\s+CONCURRENTLY\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+ON\s+(\w+)/gi;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(sql)) !== null) {
    const table = match[2];
    if (knownHypertables.has(table)) {
      diagnostics.push({
        rule: "HYPERTABLE_CONCURRENT_INDEX",
        severity: "error",
        message: `CONCURRENTLY is not supported on hypertable ${table}`,
        line: getLineNumber(sql, match.index),
        fix: `Use CREATE INDEX (without CONCURRENTLY) on hypertable ${table}`,
      });
    }
  }
  return diagnostics;
}
```

#### NONCONCURRENT_INDEX (ERROR)

On regular (non-hypertable) tables, index creation should use `CONCURRENTLY` to avoid locking the table during index builds. This check only applies to custom (non-Drizzle) migrations, since Drizzle migrations are transactional and cannot use `CONCURRENTLY`.

```typescript
function checkNonconcurrentIndex(
  sql: string,
  knownHypertables: Set<string>,
  isDrizzleMigration: boolean
): Diagnostic[] {
  if (isDrizzleMigration) return [];

  const diagnostics: Diagnostic[] = [];
  const regex =
    /CREATE\s+INDEX\s+(?!CONCURRENTLY)(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+ON\s+(\w+)/gi;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(sql)) !== null) {
    const table = match[2];
    if (knownHypertables.has(table)) continue; // Hypertables can't use CONCURRENTLY

    diagnostics.push({
      rule: "NONCONCURRENT_INDEX",
      severity: "error",
      message: `CREATE INDEX on ${table} without CONCURRENTLY will lock the table`,
      line: getLineNumber(sql, match.index),
      fix: `Use: CREATE INDEX CONCURRENTLY ...`,
    });
  }
  return diagnostics;
}
```

### Linter Entry Point

The linter reads all `.sql` files under the migration directories and runs every check:

```typescript
interface Diagnostic {
  rule: string;
  severity: "error" | "warning";
  message: string;
  line: number;
  fix?: string;
}

async function lintMigrations(migrationPaths: string[]): Promise<{
  errors: Diagnostic[];
  warnings: Diagnostic[];
}> {
  const knownHypertables = loadHypertableList(); // from config or schema
  const allDiagnostics: Diagnostic[] = [];

  for (const filePath of migrationPaths) {
    const sql = await readFile(filePath, "utf-8");
    const isDrizzle = filePath.includes("/drizzle/");

    const checks = [
      checkTruncateWithoutCascade(sql),
      checkUnsafeAddColumn(sql),
      checkMissingIfNotExists(sql),
      checkUnsafeDrop(sql),
      checkUnsafeSetNotNull(sql),
      checkUnbatchedBackfill(sql),
      checkHypertablePkMissingTimeColumn(sql, knownHypertables),
      checkDrizzleConcurrentIndex(sql, isDrizzle),
      checkHypertableConcurrentIndex(sql, knownHypertables),
      checkNonconcurrentIndex(sql, knownHypertables, isDrizzle),
    ];

    for (const diagnostics of checks) {
      for (const d of diagnostics) {
        allDiagnostics.push({ ...d, file: filePath });
      }
    }
  }

  return {
    errors: allDiagnostics.filter((d) => d.severity === "error"),
    warnings: allDiagnostics.filter((d) => d.severity === "warning"),
  };
}
```

Exit code 1 if any errors exist. Warnings are printed but do not block.

## Squawk SQL Linter

[Squawk](https://squawkhq.com/) is an external SQL linter that catches additional dangerous migration patterns -- particularly around Postgres-specific operational risks like acquiring `ACCESS EXCLUSIVE` locks.

### Configuration (.squawk.toml)

```toml
# .squawk.toml
# Squawk SQL linter configuration
# Docs: https://squawkhq.com/docs/rules

# Exclude rules that conflict with our patterns or are handled by the custom linter.
[excluded_rules]

# We use Drizzle-generated migrations which are transactional.
# Drizzle wraps each migration in BEGIN/COMMIT, so adding a non-nullable column
# with a default is safe within the transaction boundary.
"adding-not-nullable-field" = "Drizzle migrations are transactional; NOT NULL + DEFAULT is atomic"

# Our custom linter handles CONCURRENTLY checks with hypertable awareness.
# Squawk doesn't know which tables are hypertables.
"prefer-create-index-concurrently" = "Handled by custom linter with hypertable awareness"

# We require explicit IF NOT EXISTS in our custom linter.
# Squawk's version of this check has different semantics.
"adding-field-with-default" = "Safe inside Drizzle transactions; custom linter handles idempotency"
```

### Baseline File (.squawk-baseline.txt)

Legacy migrations that are already in production cannot be changed. The baseline file tells Squawk to skip them:

```
# .squawk-baseline.txt
# Migrations already applied to production. Do not modify.
# One migration filename per line. Lines starting with # are comments.
#
# Format: relative path from repo root
packages/database/drizzle/0001_initial_schema.sql
packages/database/drizzle/0002_add_candles_table.sql
packages/database/drizzle/0003_add_annotations.sql
packages/database/drizzle/0004_add_ingestion_batches.sql
packages/database/migrations/0001_create_extensions.sql
packages/database/migrations/0002_create_hypertables.sql
```

Only migrations NOT in the baseline are checked. When a migration ships to production, add it to the baseline.

### Running Squawk

```bash
# Lint only new migrations (not in baseline)
squawk --config .squawk.toml \
  --baseline .squawk-baseline.txt \
  packages/database/drizzle/*.sql \
  packages/database/migrations/*.sql
```

## Schema Drift Detection

A script that compares the actual database schema against what the codebase expects. This catches manual changes, failed migrations, and environment divergence.

### How It Works

1. The script maintains a list of expected tables and their columns, derived from the Drizzle schema or a separate manifest:

```typescript
// Expected schema, derived from Drizzle schema definitions
const expectedSchema: TableDefinition[] = [
  {
    table: "ohlcv_candles",
    columns: [
      "time", "symbol_id", "timeframe", "open", "high", "low", "close",
      "volume", "source", "batch_id", "created_at",
    ],
  },
  {
    table: "annotations",
    columns: [
      "id", "symbol_id", "annotator_source", "time_start", "time_end",
      "timeframe", "schema_version", "payload", "created_at",
    ],
  },
  // ... all tables
];
```

2. The script queries `information_schema.tables` and `information_schema.columns` to get the actual state:

```typescript
async function getActualSchema(db: PostgresConnection): Promise<Map<string, string[]>> {
  const tables = await db.query(`
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE'
  `);

  const schema = new Map<string, string[]>();
  for (const { table_name } of tables.rows) {
    const columns = await db.query(`
      SELECT column_name
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = $1
      ORDER BY ordinal_position
    `, [table_name]);

    schema.set(table_name, columns.rows.map((r) => r.column_name));
  }
  return schema;
}
```

3. It compares expected vs. actual and reports differences:

```typescript
function detectDrift(
  expected: TableDefinition[],
  actual: Map<string, string[]>
): DriftReport {
  const missingTables: string[] = [];
  const missingColumns: { table: string; column: string }[] = [];
  const extraColumns: { table: string; column: string }[] = [];

  for (const { table, columns } of expected) {
    const actualColumns = actual.get(table);
    if (!actualColumns) {
      missingTables.push(table);
      continue;
    }

    for (const col of columns) {
      if (!actualColumns.includes(col)) {
        missingColumns.push({ table, column: col });
      }
    }

    for (const col of actualColumns) {
      if (!columns.includes(col)) {
        extraColumns.push({ table, column: col });
      }
    }
  }

  return { missingTables, missingColumns, extraColumns };
}
```

### What It Catches

- **Missing tables**: Expected table doesn't exist in the database. A migration probably failed.
- **Missing columns**: Expected column doesn't exist. Migration was skipped or failed partway.
- **Extra columns**: Column exists in database but not in expected schema. Someone ran a manual `ALTER TABLE ADD COLUMN`, or a migration was applied but the schema manifest wasn't updated.

Extra columns are the most insidious. They indicate manual changes that bypassed the pipeline.

## Migration Dry-Run in CI

CI runs all migrations against a fresh PostgreSQL container to verify they work from scratch. This catches migrations that "pass" locally because the developer's database was manually altered.

### CI Job

```yaml
# .github/workflows/ci.yml (migration dry-run job)
migration-dry-run:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: timescale/timescaledb:latest-pg16
      env:
        POSTGRES_USER: test
        POSTGRES_PASSWORD: test
        POSTGRES_DB: test
      ports:
        - 5432:5432
      options: >-
        --health-cmd pg_isready
        --health-interval 5s
        --health-timeout 5s
        --health-retries 10

  steps:
    - uses: actions/checkout@v4

    - uses: pnpm/action-setup@v4

    - uses: actions/setup-node@v4
      with:
        node-version: 20
        cache: pnpm

    - run: pnpm install --frozen-lockfile

    - name: Run all migrations from scratch
      env:
        DATABASE_URL: postgres://test:test@localhost:5432/test
      run: pnpm db:migrate:sql

    - name: Run schema drift detection
      env:
        DATABASE_URL: postgres://test:test@localhost:5432/test
      run: pnpm db:check-drift
```

If any migration fails against the fresh database, the CI job fails. This is the authoritative test -- if it doesn't work on a clean database, it doesn't work.

## Migration Repair Script

Sometimes migrations get into an inconsistent state. The repair script handles edge cases:

- **Fresh databases**: If the migration tracking table (`__drizzle_migrations` or custom) doesn't exist, the script skips repair and lets the normal migration runner create it.
- **Out-of-order application**: If migrations were applied in a different order than expected (e.g., due to branch merging), the repair script reconciles the tracking state.
- **Partial failures**: If a migration was partially applied (some statements succeeded, others failed), the repair script can mark it as unapplied so it runs again.

```typescript
async function repairMigrations(db: PostgresConnection): Promise<void> {
  // Check if migration tracking table exists
  const trackingTableExists = await db.query(`
    SELECT EXISTS (
      SELECT FROM information_schema.tables
      WHERE table_schema = 'drizzle'
        AND table_name = '__drizzle_migrations'
    )
  `);

  if (!trackingTableExists.rows[0].exists) {
    console.log("No migration tracking table found. Fresh database -- skipping repair.");
    return;
  }

  // Get applied migrations from tracking table
  const applied = await db.query(`
    SELECT hash, created_at FROM drizzle.__drizzle_migrations ORDER BY created_at
  `);

  // Get migration files on disk
  const onDisk = await getMigrationFiles("./drizzle");

  // Find discrepancies
  const appliedSet = new Set(applied.rows.map((r) => r.hash));
  const onDiskSet = new Set(onDisk.map((f) => f.hash));

  // Migrations in tracking table but not on disk (deleted/moved)
  for (const row of applied.rows) {
    if (!onDiskSet.has(row.hash)) {
      console.warn(`Migration ${row.hash} is tracked but file not found on disk`);
    }
  }

  // Migrations on disk but not in tracking table (need to be applied)
  for (const file of onDisk) {
    if (!appliedSet.has(file.hash)) {
      console.log(`Migration ${file.name} needs to be applied`);
    }
  }
}
```

## Pre-Commit Integration

The migration linter runs as part of the pre-commit hook when database files are staged.

```bash
#!/usr/bin/env bash
# Inside the pre-commit hook (Husky)

# Check if any database migration files are staged
STAGED_MIGRATIONS=$(git diff --cached --name-only --diff-filter=ACM | grep -E 'packages/database/(drizzle|migrations)/.*\.sql$')

if [ -n "$STAGED_MIGRATIONS" ]; then
  echo "Database migrations staged -- running migration linter..."

  # Run custom migration linter
  pnpm --filter @recallnet/database run lint:migrations $STAGED_MIGRATIONS

  if [ $? -ne 0 ]; then
    echo ""
    echo "Migration linter found errors. Fix them before committing."
    echo "See packages/database/scripts/lint-migrations.ts for rule details."
    exit 1
  fi
fi
```

This gate runs only when migration files are staged, keeping the pre-commit hook fast for non-database changes.

## Pre-Push Integration

The pre-push hook runs heavier database checks that require a running database or more time.

```bash
#!/usr/bin/env bash
# Inside the pre-push hook

# Check if database package has changes compared to remote
DB_CHANGED=$(git diff --name-only origin/main...HEAD | grep -c 'packages/database/')

if [ "$DB_CHANGED" -gt 0 ]; then
  echo "Database package changed -- running extended checks..."

  # 1. Run Squawk SQL linter with baseline
  echo "Running Squawk SQL linter..."
  squawk --config .squawk.toml \
    --baseline .squawk-baseline.txt \
    packages/database/drizzle/*.sql \
    packages/database/migrations/*.sql

  if [ $? -ne 0 ]; then
    echo "Squawk found issues in new migrations."
    exit 1
  fi

  # 2. Schema drift detection (only if database is available)
  if [ -n "$DATABASE_URL" ]; then
    echo "Running schema drift detection..."
    pnpm --filter @recallnet/database run check:drift

    if [ $? -ne 0 ]; then
      echo ""
      echo "Schema drift detected! Your local database does not match the expected schema."
      echo "This usually means manual ALTER TABLE commands were run outside the migration pipeline."
      echo ""
      echo "To fix:"
      echo "  1. Drop and recreate your local database"
      echo "  2. Run all migrations: pnpm db:migrate:sql"
      echo "  3. Verify: pnpm --filter @recallnet/database run check:drift"
      exit 1
    fi
  else
    echo "DATABASE_URL not set -- skipping schema drift detection"
    echo "(Set DATABASE_URL to enable local drift checks)"
  fi
fi
```

## Summary of Gates

| Gate | Where | Trigger | Blocks On |
|------|-------|---------|-----------|
| Migration linter | Pre-commit | SQL files staged | ERROR-level diagnostics |
| Squawk SQL linter | Pre-push | Database package changed | Any squawk violations |
| Schema drift detection | Pre-push | Database package changed + DB available | Missing/extra tables or columns |
| Migration dry-run | CI | Always (on PR) | Any migration failure on fresh DB |
| Migration repair | Runtime | Before migration runner | N/A (diagnostic only) |

These gates form a layered defense. The pre-commit hook catches obvious SQL anti-patterns in seconds. The pre-push hook catches drift and subtler issues. CI provides the authoritative test against a clean database. Together, they make it extremely difficult for a broken migration to reach production.
