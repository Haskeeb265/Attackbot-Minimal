# Conventions

## Naming Conventions

### Files & Modules
- **snake_case** for all Python files: `program_scraper.py`, `bounty_master.py`
- **One module per database table** in `db/repos/`: `bounty_master.py`, `bounty_detail.py`, etc.
- **Test files** prefixed with `test_` or suffixed with `_test.py`: `test_persistence.py`, `scraper_test.py`

### Functions & Variables
- **snake_case** for functions and variables: `run_ingestion_job()`, `high_handles`
- **UPPER_SNAKE_CASE** for constants: `_SEVERITY_RANK`, `DATABASE_URL`
- **Private/internal** functions prefixed with underscore: `_compute_max_severity()`

### Database
- **Table names**: snake_case, plural for collections: `bounty_master`, `bounty_detail`
- **Column names**: snake_case: `scope_count`, `max_severity`, `scope_identifier`
- **Primary keys**: `id` (integer, auto-increment)
- **Foreign keys**: `{table}_id` pattern: `master_id` (references `bounty_master.id`)

## Import Style

### Module-Qualified Imports (Required for DB Access)
```python
# ✅ Correct - module-qualified
import shared.db as db

def some_query(conn, ...):
    row = db.fetch_one(conn, "SELECT ...")
    return row

# ❌ Wrong - direct import
from shared.db import fetch_one

def some_query(conn, ...):
    row = fetch_one(conn, "SELECT ...")  # Not obvious this touches DB
```

**Rationale:** Module-qualified imports make call sites obviously DB-touching at a glance.

### Import Order
1. Standard library imports
2. Third-party imports
3. Local imports (project modules)

## Function Design

### Function-First, Not Class-First
```python
# ✅ Correct - plain functions
def add_program(conn, handle, scope_count):
    ...

def upsert_program(conn, handle, scope_count):
    ...

# ❌ Wrong - unnecessary class
class ProgramRepository:
    def __init__(self, conn):
        self.conn = conn
    
    def add(self, handle, scope_count):
        ...
```

### Query Functions Take `conn` as Parameter
```python
# ✅ Correct - receives conn from caller
def get_program_by_id(conn, master_id):
    return db.fetch_one(conn, "SELECT ...", (master_id,))

# ❌ Wrong - opens own connection
def get_program_by_id(master_id):
    with db.get_conn() as conn:
        return db.fetch_one(conn, "SELECT ...", (master_id,))
```

**Exception:** `replace_weaknesses()` and `replace_exclusions()` call `db.atomic(conn)` internally (safe to nest due to savepoints).

### Transaction Boundary Ownership
```python
# ✅ Correct - top-level orchestrator owns connection and transaction
def run_ingestion_job():
    with db.get_conn() as conn:
        for handle in handles:
            try:
                with db.atomic(conn):
                    persist_program(conn, mapped)
            except Exception as e:
                log.failed(f"[{handle}] failed: {e}")

# ❌ Wrong - query function opens own connection
def persist_program(mapped):
    with db.get_conn() as conn:
        with db.atomic(conn):
            # ... inserts
```

## Error Handling

### Exception Propagation
- Let exceptions propagate naturally from query functions
- Catch at the orchestration level (e.g., `run_ingestion_job()`)
- Use `logger.exception` for tracebacks

### Transaction Rollback
- Rely on context managers for automatic rollback
- Don't manually call `rollback()` - let `atomic()` handle it
- Named sentinel exceptions for test rollback (see `smoke_test_db.py`)

## Logging

### Use Project's Color Logger
```python
from shared.colorlog import log

log.process(f"Starting ingestion job — {len(handles)} handles queued")
log.success(f"[{handle}] ingested")
log.failed(f"[{handle}] ingestion failed: {e}")
```

### Log Levels
- `log.process()` - informational progress
- `log.success()` - successful operations
- `log.failed()` - failures and errors

## Documentation

### Docstrings
- Use triple-quoted strings for function docstrings
- Document parameters, return values, and exceptions
- Keep docstrings concise but informative

### Inline Comments
- Explain "why" not "what"
- Document non-obvious decisions
- Reference design documents (e.g., `scope.md` sections)

## Testing

### Test Organization
- Test files in `tests/` directory
- Use pytest conventions: `test_` prefix for test functions
- One test file per module: `test_persistence.py` for `persistence.py`

### Test Patterns
```python
# Smoke test with rollback
def test_database_lifecycle():
    with db.get_conn() as conn:
        with db.atomic(conn):
            # ... test operations
            raise _ForceRollback  # Rollback, don't commit
```

## Evidence
- `shared/db.py` - module-qualified imports, function-first design
- `db/repos/*.py` - query functions taking `conn` parameter
- `service/scraper/ingest.py` - transaction boundary ownership
- `scope.md` - coding conventions section (§9)
