# Structure

## Directory Layout

```
Attackbot-Minimal/
├── main.py                     # Application entry point
├── config.py                   # Root-level configuration (DATABASE_URL, env vars)
├── requirements.txt            # Python dependencies
├── docker-compose.yml          # PostgreSQL service definition
├── Dockerfile                  # Container definition (empty)
├── alembic.ini                 # Alembic migration configuration
├── scope.md                    # Project context & architecture reference
│
├── shared/                     # Cross-cutting utilities
│   ├── db.py                   # Database connection pool & query primitives
│   ├── colorlog.py             # Colored logging utilities
│   └── connectors/             # External API clients (bug bounty sources)
│       ├── base.py             # BaseConnector — platform-agnostic source interface
│       └── hackerone_client.py # HackerOneConnector — HackerOne API v1 client
│
├── service/                    # Business logic services
│   └── scraper/                # Data ingestion from HackerOne
│       ├── config.py           # Scraper-specific configuration
│       ├── ingest.py           # Ingestion orchestrator
│       ├── program_scraper.py  # Fetches program handles (via connector)
│       ├── program_detail_scraper.py  # Fetches program details (via connector)
│       ├── __init__.py
│       └── helpers/
│           └── __init__.py
│
├── db/                         # Database layer
│   ├── init/
│   │   └── 001_schema.sql      # Initial schema (runs on container boot)
│   ├── mapper/
│   │   └── hackerone_mapper.py # Maps HackerOne data to internal format
│   ├── persistence/
│   │   └── persistence.py      # Persistence logic for mapped data
│   ├── migrations/             # Alembic migrations
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 0001_baseline_schema.py
│   │       └── 0002_moving_max_severity_to_bounty_detail_table.py
│   └── repos/                  # Query modules (one per table)
│       ├── bounty_master.py
│       ├── bounty_detail.py
│       ├── bounty_weaknesses.py
│       └── bounty_exclusions.py
│
├── tests/                      # Test suite
│   ├── scraper_test.py
│   ├── smoke_test_db.py
│   ├── test_hackerone_mapper.py
│   └── test_persistence.py
│
├── docs/                       # Documentation
│   └── codebase/               # Generated codebase documentation
│       ├── STACK.md
│       ├── STRUCTURE.md
│       ├── ARCHITECTURE.md
│       ├── CONVENTIONS.md
│       ├── INTEGRATIONS.md
│       ├── TESTING.md
│       └── CONCERNS.md
│
└── ai-agent-workspace/         # Skills and agent configuration
    └── SKILLS/
        └── acquire-codebase-knowledge/
            └── SKILL.md
```

## Entry Points

| File | Purpose | How to Run |
|------|---------|------------|
| `main.py` | Application entry point | `python main.py` |
| `tests/smoke_test_db.py` | Database lifecycle test | `python -m tests.smoke_test_db` |

## Key Files

### Core Infrastructure
- **`config.py`** - Loads environment variables, constructs `DATABASE_URL`
- **`shared/db.py`** - Database connection pool, query primitives (`get_conn`, `atomic`, `fetch_one`, etc.)
- **`shared/colorlog.py`** - Colored logging for terminal output

### Scraper Service
- **`service/scraper/ingest.py`** - Orchestrates ingestion job (main workflow)
- **`service/scraper/program_scraper.py`** - Fetches and filters program handles
- **`service/scraper/program_detail_scraper.py`** - Fetches full program details per handle
- **`shared/connectors/base.py`** - `BaseConnector` abstract source interface; the scraper depends only on this, never on platform specifics
- **`shared/connectors/hackerone_client.py`** - `HackerOneConnector` — HackerOne API v1 implementation of `BaseConnector`

### Database Layer
- **`db/repos/*.py`** - Query modules (one per table): `bounty_master`, `bounty_detail`, `bounty_weaknesses`, `bounty_exclusions`
- **`db/mapper/hackerone_mapper.py`** - Maps HackerOne API response to internal format
- **`db/persistence/persistence.py`** - Persists mapped data to database
- **`db/init/001_schema.sql`** - Initial schema (auto-runs on container boot)

### Configuration
- **`docker-compose.yml`** - PostgreSQL service definition
- **`alembic.ini`** - Alembic migration configuration

## Evidence
- File tree exploration via `list_directory` and `glob`
- `main.py` - entry point implementation
- `shared/db.py` - database connection pool
- `service/scraper/ingest.py` - ingestion orchestrator
- `db/repos/` - all four query modules
