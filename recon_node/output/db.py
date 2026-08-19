"""
output/db.py
~~~~~~~~~~~~
SqliteWriter — persists pipeline output to a SQLite database.

CONTRACT
--------
SqliteWriter(db_path)
    ``db_path`` — path to the SQLite database file.  Created if it does
    not exist.  Schemas are auto-migrated on first write.

write(state) -> Path
    Persist the entire PipelineState to the database.
    Creates/updates three tables:
    1. ``runs``        — one row per pipeline run (run_id, target, scope, timestamps)
    2. ``subdomains``  — one row per subdomain per run
    3. ``recon_results`` — one row per ReconResult per run

    Writes are wrapped in a single transaction — if any INSERT fails,
    the entire write is rolled back.
    Returns the database path.

    NEVER raises on I/O or SQL errors — all errors are caught and logged.

query_runs(target=None) -> List[dict]
    Query all pipeline runs, optionally filtered by target.

close()
    Explicitly close the database connection.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from recon_node.models import PipelineState

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    target          TEXT NOT NULL,
    scope           TEXT NOT NULL,          -- JSON array
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    completed_stages TEXT NOT NULL,         -- JSON array
    skipped_stages  TEXT NOT NULL,          -- JSON array
    summary         TEXT NOT NULL           -- JSON object
);

CREATE TABLE IF NOT EXISTS subdomains (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    subdomain       TEXT NOT NULL,
    source          TEXT NOT NULL,
    ip_addresses    TEXT NOT NULL,          -- JSON array
    is_live         INTEGER NOT NULL DEFAULT 0,
    in_scope        INTEGER NOT NULL DEFAULT 1,
    http_status     INTEGER,
    http_title      TEXT,
    technologies    TEXT NOT NULL,          -- JSON array
    ports           TEXT NOT NULL,          -- JSON array
    urls_count      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS recon_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    tool            TEXT NOT NULL,
    stage           TEXT NOT NULL,
    target          TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    success         INTEGER NOT NULL DEFAULT 1,
    error           TEXT,
    data            TEXT NOT NULL,          -- JSON object
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_subdomains_run ON subdomains(run_id);
CREATE INDEX IF NOT EXISTS idx_subdomains_fqdn ON subdomains(subdomain);
CREATE INDEX IF NOT EXISTS idx_results_run ON recon_results(run_id);
CREATE INDEX IF NOT EXISTS idx_results_stage ON recon_results(stage);
"""


class SqliteWriter:
    """
    Persists pipeline output to a SQLite database.

    Parameters
    ----------
    db_path:
        Path to the SQLite file.  Created if it does not exist.
        Parent directories are created automatically.
    """

    def __init__(self, db_path: str = "./output/recon.db") -> None:
        self._db_path = Path(db_path).resolve()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Lazy-init connection and apply schema."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_SCHEMA)
        return self._conn

    def close(self) -> None:
        """Explicitly close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, state: PipelineState) -> Optional[Path]:
        """
        Persist the entire PipelineState to the database.

        Returns the database path on success, None on failure.
        NEVER raises.
        """
        try:
            conn = self._connect()
            with conn:
                self._insert_run(conn, state)
                self._insert_subdomains(conn, state)
                self._insert_results(conn, state)
            log.info(
                "SqliteWriter: persisted run %s to %s",
                state.run_id, self._db_path,
            )
            return self._db_path
        except Exception as exc:
            log.error("SqliteWriter.write() failed: %s", exc)
            return None

    def query_runs(self, target: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query pipeline runs.

        Returns a list of dicts with run metadata.
        NEVER raises — returns [] on error.
        """
        try:
            conn = self._connect()
            if target:
                rows = conn.execute(
                    "SELECT * FROM runs WHERE target = ? ORDER BY started_at DESC",
                    (target,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM runs ORDER BY started_at DESC",
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            log.error("SqliteWriter.query_runs() failed: %s", exc)
            return []

    def query_subdomains(self, run_id: str) -> List[Dict[str, Any]]:
        """Query subdomains for a specific run."""
        try:
            conn = self._connect()
            rows = conn.execute(
                "SELECT * FROM subdomains WHERE run_id = ? ORDER BY subdomain",
                (run_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            log.error("SqliteWriter.query_subdomains() failed: %s", exc)
            return []

    @property
    def db_path(self) -> Path:
        """Return the resolved database file path."""
        return self._db_path

    # ------------------------------------------------------------------
    # Internal INSERT helpers
    # ------------------------------------------------------------------

    def _insert_run(self, conn: sqlite3.Connection, state: PipelineState) -> None:
        conn.execute(
            """INSERT OR REPLACE INTO runs
               (run_id, target, scope, started_at, completed_at,
                completed_stages, skipped_stages, summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                state.run_id,
                state.target,
                json.dumps(state.scope),
                state.started_at.isoformat(),
                state.completed_at.isoformat() if state.completed_at else None,
                json.dumps([s.value for s in state.completed_stages]),
                json.dumps([s.value for s in state.skipped_stages]),
                json.dumps(state.summary(), default=str),
            ),
        )

    def _insert_subdomains(self, conn: sqlite3.Connection, state: PipelineState) -> None:
        for sd in state.subdomains:
            conn.execute(
                """INSERT INTO subdomains
                   (run_id, subdomain, source, ip_addresses, is_live, in_scope,
                    http_status, http_title, technologies, ports, urls_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    state.run_id,
                    sd.subdomain,
                    sd.source,
                    json.dumps(sd.ip_addresses),
                    int(sd.is_live),
                    int(sd.in_scope),
                    sd.http_metadata.status_code if sd.http_metadata else None,
                    sd.http_metadata.title if sd.http_metadata else None,
                    json.dumps(sd.technologies),
                    json.dumps([json.loads(p.model_dump_json()) for p in sd.ports]),
                    len(sd.urls),
                ),
            )

    def _insert_results(self, conn: sqlite3.Connection, state: PipelineState) -> None:
        for stage_key, results in state.stage_results.items():
            for r in results:
                conn.execute(
                    """INSERT INTO recon_results
                       (run_id, tool, stage, target, timestamp, success, error, data)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        state.run_id,
                        r.tool,
                        r.stage.value,
                        r.target,
                        r.timestamp.isoformat(),
                        int(r.success),
                        r.error,
                        json.dumps(r.data, default=str),
                    ),
                )
