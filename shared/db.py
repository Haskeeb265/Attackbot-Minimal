import os
from contextlib import contextmanager
from datetime import datetime, timezone

from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://admin:admin12345@localhost:5432/attackbot",
)

pool = ConnectionPool(
    conninfo=_DATABASE_URL,
    min_size=1,
    max_size=10,
    kwargs={"row_factory": dict_row},
    open=True,
)

@contextmanager
def get_conn():
    with pool.connection() as conn:
        yield conn

@contextmanager
def atomic(conn):
    with conn.transaction():   # psycopg3 auto-nests as SAVEPOINT if already inside a transaction
        yield conn

def fetch_one(conn, query, params=None):
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchone()

def fetch_all(conn, query, params=None):
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchall()

def execute(conn, query, params=None):
    with conn.cursor() as cur:
        cur.execute(query, params or ())

def now():
    return datetime.now(timezone.utc)