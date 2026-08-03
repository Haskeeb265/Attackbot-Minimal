from dotenv import load_dotenv
import os
from pathlib import Path

# Always load the root .env regardless of the current working directory.
# override=True keeps .env authoritative so stale shell/env vars (e.g. old Aura
# NEO4J_*) can never silently override the local-dev configuration.
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

# ---- Postgres (db layer) ----
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")

DATABASE_URL = (
    f"postgresql://{POSTGRES_USER}:"
    f"{POSTGRES_PASSWORD}@"
    f"{POSTGRES_HOST}:"
    f"{POSTGRES_PORT}/"
    f"{POSTGRES_DB}"
)

# ---- Scraper (HackerOne API) ----
HACKERONE_USERNAME = os.getenv("HACKERONE_USERNAME")
HACKERONE_TOKEN = os.getenv("HACKERONE_TOKEN")
HACKERONE_BASE_URL = "https://api.hackerone.com/v1/"
HACKERONE_AUTH = (HACKERONE_USERNAME, HACKERONE_TOKEN)

# ---- Recon graph (Neo4j) ----
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")

# ---- Recon cache/queue (Redis) ----
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")