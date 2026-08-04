# Architecture

## System Overview

Attackbot_v2 is an autonomous vulnerability discovery engine targeting public HackerOne bug bounty programs. The system is built around four top-level operations:

1. **Scraping** - Pulls program metadata from HackerOne's Hacker API
2. **Recon** - Five-stage internal pipeline (not yet started)
3. **Pentesting** - Not yet started
4. **Reporting** - Not yet started

## Current Implementation

### Scraping Operation
The scraping operation is functionally complete and consists of two scrapers:

```
program_scraper.py          → Fetches and filters program handles
        ↓
program_detail_scraper.py   → Takes handles one at a time, fetches full detail
        ↓
ingest.py                   → Orchestrates scraping → mapping → persistence
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py                                   │
│  (Entry point - starts ingestion thread)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              service/scraper/ingest.py                           │
│  (Orchestrator - owns ONE connection for entire run)             │
│                                                                  │
│  run_ingestion_job()                                             │
│    ├── get_filtered_handles()  (program_scraper)                 │
│    └── for handle in handles:                                    │
│          ├── scrape_program_detail(handle)                       │
│          └── ingest_program(conn, handle)  [ONE atomic per prog] │
│                ├── bounty_master.upsert_program                  │
│                ├── bounty_detail.upsert_scope (looped)           │
│                ├── bounty_weaknesses.update_weaknesses           │
│                └── bounty_exclusions.update_exclusions           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              db/mapper/hackerone_mapper.py                       │
│  (Transforms HackerOne API response → internal format)           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              db/persistence/persistence.py                       │
│  (Persists mapped data to database)                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              db/repos/*.py                                       │
│  (Query modules - one per table)                                 │
│    ├── bounty_master.py                                          │
│    ├── bounty_detail.py                                          │
│    ├── bounty_weaknesses.py                                      │
│    └── bounty_exclusions.py                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              PostgreSQL 16 (via Docker)                          │
│  Tables: bounty_master, bounty_detail,                          │
│          bounty_weaknesses, bounty_exclusion                    │
└─────────────────────────────────────────────────────────────────┘
```

## Transaction Boundary Pattern

The system follows a strict transaction boundary pattern:

```python
# One connection for entire run
with db.get_conn() as conn:
    for handle in handles:
        try:
            # One atomic block per program
            with db.atomic(conn):
                persist_program(conn, mapped)
            # Commit happens here if no exception
        except Exception as e:
            # Rollback happens here, loop continues
            log.failed(f"[{handle}] ingestion failed: {e}")
```

**Key Invariants:**
- ONE connection for the entire ingestion run
- ONE transaction per program (atomic block)
- Failures in one program don't affect others
- Connection stays clean after rollback (savepoints)

## Database Patterns

### Write Patterns by Table

| Table | Pattern | Reason |
|-------|---------|--------|
| `bounty_master` | UPSERT (ON CONFLICT DO UPDATE) | Dedup via unique constraint on `handle` |
| `bounty_detail` | UPSERT (ON CONFLICT DO UPDATE) | Preserves row identity for downstream FK references |
| `bounty_weaknesses` | DELETE-then-INSERT (full replace) | No historical continuity needed |
| `bounty_exclusion` | DELETE-then-INSERT (full replace) | No historical continuity needed |

### Connection Management

```python
# shared/db.py
pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=2,
    max_size=10,
    kwargs={"row_factory": dict_row},
)

@contextmanager
def get_conn():
    with pool.connection() as conn:
        yield conn

@contextmanager
def atomic(conn):
    with conn.transaction():
        yield conn
```

**Unit-of-Work Rule:**
- Only top-level orchestrating code calls `get_conn()` / `atomic()`
- Query functions in `db/repos/*.py` always receive `conn` as parameter
- Query functions never open their own connection

## Future Architecture: Recon Operation

The recon operation (not yet started) will use a five-stage pipeline:

```
Stage 0: Deterministic program ingestion (no LLM)
    ↓
Stage 1: LLM classification and plan generation (reads from DB)
    ↓
Stage 2: Enumeration / horizontal
    ↓
Stage 3: Validation and fingerprinting
    ↓
Stage 4: Vulnerability testing / vertical
```

**GoalAct Loop** wraps the recon pipeline with:
- Full plan rewrite every iteration
- Three-state result system: CONFIRMED_FINDING, CONFIRMED_EMPTY, EXECUTION_FAILED
- Scratchpad as sole intra-run memory channel

## Evidence
- `service/scraper/ingest.py` - orchestrator implementation
- `shared/db.py` - connection pool and transaction management
- `db/repos/*.py` - query module patterns
- `scope.md` - architecture decisions and invariants
