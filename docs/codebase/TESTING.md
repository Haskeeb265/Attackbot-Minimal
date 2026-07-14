# Testing

## Test Framework

- **Framework:** pytest (implied by file naming conventions)
- **Test Location:** `tests/` directory at project root
- **No explicit pytest configuration found** (uses default settings)

## Test Files

| File | Purpose | Key Patterns |
|------|---------|--------------|
| `tests/scraper_test.py` | Tests for `ProgramDetailScraper` service | Fetch scopes, exclusions, weaknesses |
| `tests/smoke_test_db.py` | Full database lifecycle test | Insert → read → update → replace → delete |
| `tests/test_hackerone_mapper.py` | Tests for `HackerOneMapper` | Data transformation validation |
| `tests/test_persistence.py` | Tests for `persist_program` function | Database interactions |

## Test Patterns

### Smoke Test with Rollback

The database smoke test uses a **named sentinel exception** for guaranteed rollback:

```python
class _ForceRollback(Exception):
    """Sentinel exception to force transaction rollback."""
    pass

def test_database_lifecycle():
    with db.get_conn() as conn:
        with db.atomic(conn):
            # ... perform all test operations ...
            raise _ForceRollback  # Forces rollback without catching

# Catch the sentinel at the top level
try:
    test_database_lifecycle()
except _ForceRollback:
    pass  # Expected - test passed, transaction rolled back
```

**Why this pattern:**
- Bare `finally: raise SystemExit(...)` silently swallows real assertion failures
- Named sentinel lets genuine test failures surface normally
- Guarantees rollback via the exception path

### Integration Tests

Tests interact with real PostgreSQL database (not mocked):
- Use Docker Compose PostgreSQL instance
- Run inside single transaction that gets rolled back
- Test actual SQL queries and constraints

### Unit Tests

- `test_hackerone_mapper.py` - tests data transformation logic
- No mocking observed (tests use real data structures)

## Test Organization

```
tests/
├── scraper_test.py           # Service-level tests
├── smoke_test_db.py          # Database lifecycle test
├── test_hackerone_mapper.py  # Unit tests for mapper
└── test_persistence.py       # Integration tests for persistence
```

**Naming Conventions:**
- Test files: `test_*.py` or `*_test.py`
- Test functions: `test_*` (pytest convention)
- Test classes: `Test*` (if used)

## Running Tests

### Database Tests
```bash
# Ensure PostgreSQL is running via Docker
docker-compose up -d

# Run smoke test
python -m tests.smoke_test_db
```

### All Tests
```bash
# Run with pytest (if configured)
pytest tests/

# Or run individual test files
python tests/test_persistence.py
python tests/test_hackerone_mapper.py
```

## Mocking Strategy

**Minimal mocking observed:**
- Database tests use real PostgreSQL connection
- Mapper tests use real data structures
- No external API mocking observed (scraper tests may call real API)

**Future considerations:**
- HackerOne API mocking needed for offline testing
- Rate limit mocking for scraper tests
- LLM provider mocking for recon tests (when implemented)

[TODO] Investigate if there are any mock fixtures or test utilities in the codebase

## Test Coverage

**Current coverage areas:**
- ✅ Database CRUD operations (all four tables)
- ✅ Data transformation (HackerOne mapper)
- ✅ Persistence logic (persist_program)
- ✅ Scraper service (program detail fetching)

**Missing coverage:**
- ❌ Ingestion orchestrator (`run_ingestion_job`)
- ❌ Connection pool behavior
- ❌ Error handling and rollback scenarios
- ❌ Rate limiting logic

## Evidence
- `tests/smoke_test_db.py` - database lifecycle test with rollback pattern
- `tests/test_persistence.py` - persistence integration tests
- `tests/test_hackerone_mapper.py` - mapper unit tests
- `tests/scraper_test.py` - scraper service tests
