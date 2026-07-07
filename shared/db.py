from contextlib import contextmanager
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class Database:

    def __init__(self, conninfo: str, min_size: int = 2, max_size: int = 10):
        self.pool = ConnectionPool(
            conninfo=conninfo,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row}
        )

    
    def open(self):
        self.pool.wait()

    def close(self):
        self.pool.close()


    @contextmanager
    def get_conn(self):
        with self.pool.Connection as conn:
            yield conn


    @contextmanager
    def atomic(self, conn):
        with conn.transaction():
            yield conn


    def fetch_one(self, conn, query: str, params: tuple=()):
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()


    def fetch_all(self, conn, query: str, params: tuple=()):
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    
    def execute(self, conn, query: str, params: tuple=()):
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount

    @staticmethod
    def now():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc)




"""fetch_one/fetch_all/execute take conn as their first argument, not self._pool — this is the mechanism that makes the whole shared-connection design work. Every table-specific function in db/queries/*.py will call db.fetch_one(conn, "...", (...)), always passing along whatever conn its caller gave it. Nothing below the top-level orchestrator ever calls get_conn().
    atomic() doesn't check out a connection — it only wraps conn.transaction(). This is the fix for the pool-exhaustion problem we walked through: one get_conn() call, one atomic() call, many query functions sharing both.
    open()/close() — added these as explicit lifecycle methods since ConnectionPool needs .wait() at startup (blocks until min_size connections are actually established, so you fail fast if Postgres isn't reachable, rather than discovering it on your first real query) and .close() at shutdown. You'll call these once in main.py — not per-request.
    now() is a staticmethod — doesn't need self, just returns a UTC-aware timestamp. Called explicitly wherever a query function sets updated_at, e.g. db.execute(conn, "UPDATE bounty_master SET updated_at = %s WHERE id = %s", (db.now(), master_id)).
"""