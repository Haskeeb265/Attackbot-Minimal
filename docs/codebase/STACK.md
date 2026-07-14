# Stack

## Language & Runtime
- **Language:** Python 3.14
- **Runtime:** CPython (standard Python implementation)
- **OS:** Windows (developed via PowerShell)

## Core Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| psycopg[binary] | 3.x | PostgreSQL database driver |
| psycopg_pool | 3.x | Connection pooling for psycopg |
| sqlalchemy | - | Schema diffing only (Alembic), never imported at runtime |
| alembic | - | Database migration versioning |
| python-dotenv | - | Environment variable loading from .env files |

## Database
- **PostgreSQL 16 Alpine** via Docker Compose
- **Container:** `attackbot_postgres`
- **Connection:** `psycopg_pool.ConnectionPool` with `min_size=2, max_size=10`
- **Row factory:** `psycopg.rows.dict_row` (returns dictionaries instead of tuples)

## LLM Providers
| Provider | Role | Model |
|----------|------|-------|
| Cerebras | Primary | llama-3.3-70b |
| Groq | Fallback | llama-3.3-70b-versatile |

Rate limits are shared across all services and centrally managed via root `config.py`.

[ASK USER] Are there specific rate limit values or quotas we should document?

## External APIs
- **HackerOne Hacker API v1** - bug bounty program data

## Infrastructure
- Docker Compose for PostgreSQL
- No web framework yet (FastAPI planned for future frontend)

## Evidence
- `requirements.txt` - lists Python dependencies
- `docker-compose.yml` - PostgreSQL service definition
- `shared/db.py` - psycopg3 connection pool setup
- `config.py` - DATABASE_URL construction
- `scope.md` - documents LLM provider decisions
