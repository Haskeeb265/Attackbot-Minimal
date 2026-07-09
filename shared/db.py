from config import DATABASE_URL
from contextlib import contextmanager
from datetime import datetime, timezone

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# Pool is created eagerly at import time (ConnectionPool opens connections
# in the background by default). Call close() once at process shutdown.
pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=2,
    max_size=10,
    kwargs={"row_factory": dict_row},
)


def close():
    """Call once at process shutdown to release pooled connections cleanly."""
    pool.close()


@contextmanager
def get_conn():
    with pool.connection() as conn:
        yield conn


@contextmanager
def atomic(conn):
    with conn.transaction():
        yield conn


def fetch_one(conn, query: str, params: tuple = ()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()


def fetch_all(conn, query: str, params: tuple = ()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def execute(conn, query: str, params: tuple = ()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.rowcount


def now():
    return datetime.now(timezone.utc)