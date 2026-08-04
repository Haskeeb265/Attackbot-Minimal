# Integrations

## External APIs

### HackerOne Hacker API v1

**Purpose:** Fetch bug bounty program metadata, scopes, weaknesses, and exclusions.

**Key Endpoints:**
| Endpoint | Purpose | Rate Limit |
|----------|---------|------------|
| `/hackers/programs` | List all programs (paginated) | General read limit |
| `/{handle}/structured_scopes` | Fetch program scopes | **Separate** rate limit |
| `/{handle}/scope_exclusions` | Fetch program exclusions | General read limit |
| `/{handle}/weaknesses` | Fetch program weaknesses | General read limit |

**Client Implementation:**
- `shared/connectors/hackerone_client.py` - HackerOne API client
- `service/scraper/helpers/send_request.py` - HTTP request utilities

**Important Notes:**
- `/hackers/programs` requires explicit `page[number]` / `links.next` pagination handling
- `structured_scopes` has its own separate rate limit (not shared with other endpoints)
- Both priority-bucket filtering methods on `program_scraper` must share a single `_fetch_all_programs()` call

**Configuration:**
- API credentials stored in environment variables (loaded via `config.py`)
- Rate limits centrally managed via root `config.py` (shared across all services)

## Databases

### PostgreSQL 16 Alpine

**Purpose:** Primary data store for program metadata, scopes, weaknesses, and exclusions.

**Connection Details:**
- **Host:** localhost (via Docker)
- **Port:** 5432 (configurable via `POSTGRES_PORT`)
- **Driver:** psycopg3 + psycopg_pool
- **Connection Pool:** `min_size=2`, `max_size=10`
- **Row Factory:** `dict_row` (returns dictionaries)

**Schema Tables:**
| Table | Purpose | Write Pattern |
|-------|---------|---------------|
| `bounty_master` | One row per program | UPSERT (ON CONFLICT DO UPDATE) |
| `bounty_detail` | Scoped assets per program | UPSERT (ON CONFLICT DO UPDATE) |
| `bounty_weaknesses` | Weakness rulesets | DELETE-then-INSERT (full replace) |
| `bounty_exclusion` | Exclusion rulesets | DELETE-then-INSERT (full replace) |

**Docker Configuration:**
```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: attackbot_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d
```

**Initialization:**
- `db/init/001_schema.sql` auto-runs on first container boot
- Creates all four tables with constraints and indexes

## LLM Providers

### Cerebras (Primary)

**Purpose:** Primary LLM provider for recon operation (not yet started).

**Model:** llama-3.3-70b

**Rate Limits:** Shared across all services, centrally managed.

### Groq (Fallback)

**Purpose:** Fallback LLM provider when Cerebras is unavailable.

**Model:** llama-3.3-70b-versatile

**Rate Limits:** Shared with Cerebras (same quota pool).

**Configuration:**
- Both providers configured in root `config.py`
- Rate limits managed centrally (all services draw from one quota)

## Authentication

### HackerOne API

- API credentials stored in environment variables
- Loaded via `config.py` using `python-dotenv`
- Never committed to version control

### PostgreSQL

- Credentials stored in environment variables
- Loaded via `config.py` using `python-dotenv`
- Docker Compose passes credentials to container

## Monitoring & Logging

### Application Logging

- Python's standard `logging` module
- Custom colored logging via `shared/colorlog.py`
- Log levels: `process` (info), `success` (success), `failed` (error)

### Docker Health Checks

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
  interval: 5s
  timeout: 5s
  retries: 5
```

## Future Integrations (Planned)

### Discord Webhook

**Purpose:** Alert on findings (planned for recon operation).

**Status:** Not yet implemented.

### FastAPI

**Purpose:** Frontend API layer (planned for future).

**Status:** Deliberately deferred - not being built now.

## Evidence
- `shared/connectors/hackerone_client.py` - HackerOne API client
- `service/scraper/helpers/send_request.py` - HTTP request utilities
- `docker-compose.yml` - PostgreSQL service definition
- `config.py` - environment variable loading
- `scope.md` - integration decisions and rate limit notes
