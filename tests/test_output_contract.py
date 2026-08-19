"""
tests/test_output_contract.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Conformance test for output writers (JsonWriter, SqliteWriter).

Run:
    $env:PYTHONPATH = "<repo-root>"
    .venv/Scripts/python tests/test_output_contract.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from recon_node.models import (
    HttpMetadata, PipelineState, Port, ReconResult, Stage, StageStats, Subdomain,
)
from recon_node.output.json_writer import JsonWriter
from recon_node.output.db import SqliteWriter


# ---------------------------------------------------------------------------
# Fixture: build a realistic PipelineState
# ---------------------------------------------------------------------------

def _make_state() -> PipelineState:
    """Build a fully-populated PipelineState for testing."""
    state = PipelineState(
        run_id=str(uuid.uuid4()),
        target="example.com",
        scope=["*.example.com", "example.com"],
        output_dir="./output_test",
    )

    # Subdomain 1: live, with HTTP metadata, ports, URLs, technologies
    sd1 = state.upsert_subdomain(Subdomain(
        subdomain="api.example.com",
        source="SubfinderTool",
        ip_addresses=["1.2.3.4"],
        is_live=True,
        in_scope=True,
    ))
    sd1.http_metadata = HttpMetadata(
        url="https://api.example.com",
        status_code=200,
        title="API Server",
        technologies=["nginx", "Go"],
        server="nginx/1.20",
    )
    sd1.ports = [
        Port(port=443, protocol="tcp", service="https"),
        Port(port=8080, protocol="tcp", service="http-proxy"),
    ]
    sd1.urls = ["https://api.example.com/v1/health", "https://api.example.com/docs"]
    sd1.technologies = ["nginx", "Go"]

    # Subdomain 2: NOT live (no HTTP metadata)
    state.upsert_subdomain(Subdomain(
        subdomain="mail.example.com",
        source="AssetfinderTool",
        ip_addresses=["5.6.7.8"],
        is_live=False,
        in_scope=True,
    ))

    # Subdomain 3: live but out-of-scope
    sd3 = state.upsert_subdomain(Subdomain(
        subdomain="cdn.example.com",
        source="AmassTool",
        is_live=True,
        in_scope=False,
    ))

    # Stage results
    state.add_stage_results(Stage.SUBDOMAIN_ENUM, [
        ReconResult(tool="SubfinderTool", stage=Stage.SUBDOMAIN_ENUM,
                    target="example.com", data={"subdomains": ["api.example.com"]}),
    ])
    state.add_stage_results(Stage.HTTP_PROBE, [
        ReconResult(tool="HttpxTool", stage=Stage.HTTP_PROBE,
                    target="(batch)", data={"live_hosts": [{"host": "api.example.com"}]}),
    ])

    # Mark stages complete
    state.mark_stage_complete(Stage.SUBDOMAIN_ENUM)
    state.mark_stage_complete(Stage.HTTP_PROBE)

    # Stage stats
    now = datetime.now(timezone.utc)
    state.stage_stats[Stage.SUBDOMAIN_ENUM.value] = StageStats(
        stage=Stage.SUBDOMAIN_ENUM, started_at=now, completed_at=now,
        tools_run=["SubfinderTool"], tools_failed=[],
        items_in=1, items_out=3, items_scoped_out=0,
    )

    state.completed_at = now
    return state


# ===========================================================================
# JSONWRITER TESTS
# ===========================================================================

# CLAUSE 1 — write() returns dict of name → Path
def test_json_write_returns_dict() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="json_test_") as d:
        writer = JsonWriter(output_dir=d)
        result = writer.write(state)
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert len(result) >= 6, f"Expected 6+ files, got {len(result)}: {list(result.keys())}"
    print("  [PASS] clause 1 -- write() returns dict with 6+ entries")


# CLAUSE 2 — All 6 expected files produced
def test_json_all_files_produced() -> None:
    expected_names = {"subdomains", "live_hosts", "urls", "ports", "summary", "full_state"}
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="json_test_") as d:
        writer = JsonWriter(output_dir=d)
        result = writer.write(state)
        for name in expected_names:
            assert name in result, f"Missing file: {name}"
            assert result[name].exists(), f"File not on disk: {result[name]}"
    print(f"  [PASS] clause 2 -- all 6 files produced: {expected_names}")


# CLAUSE 3 — subdomains.json contains all subdomains
def test_json_subdomains_complete() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="json_test_") as d:
        writer = JsonWriter(output_dir=d)
        result = writer.write(state)
        data = json.loads(result["subdomains"].read_text("utf-8"))
        names = {s["subdomain"] for s in data}
        assert "api.example.com" in names
        assert "mail.example.com" in names
        assert "cdn.example.com" in names
        assert len(data) == 3
    print("  [PASS] clause 3 -- subdomains.json has all 3 subdomains")


# CLAUSE 4 — live_hosts.json contains only live subdomains
def test_json_live_hosts_filter() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="json_test_") as d:
        writer = JsonWriter(output_dir=d)
        result = writer.write(state)
        data = json.loads(result["live_hosts"].read_text("utf-8"))
        names = {s["subdomain"] for s in data}
        assert "api.example.com" in names
        assert "cdn.example.com" in names   # live but out-of-scope — still written
        assert "mail.example.com" not in names  # not live
    print("  [PASS] clause 4 -- live_hosts.json filters to is_live=True only")


# CLAUSE 5 — urls.json keyed by host
def test_json_urls_by_host() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="json_test_") as d:
        writer = JsonWriter(output_dir=d)
        result = writer.write(state)
        data = json.loads(result["urls"].read_text("utf-8"))
        assert "api.example.com" in data
        assert isinstance(data["api.example.com"], list)
        assert len(data["api.example.com"]) == 2
        # mail.example.com has no URLs — should NOT appear
        assert "mail.example.com" not in data
    print("  [PASS] clause 5 -- urls.json keyed by host, only hosts with URLs")


# CLAUSE 6 — ports.json keyed by host
def test_json_ports_by_host() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="json_test_") as d:
        writer = JsonWriter(output_dir=d)
        result = writer.write(state)
        data = json.loads(result["ports"].read_text("utf-8"))
        assert "api.example.com" in data
        assert len(data["api.example.com"]) == 2
        ports = {p["port"] for p in data["api.example.com"]}
        assert 443 in ports
        assert 8080 in ports
    print("  [PASS] clause 6 -- ports.json keyed by host with correct ports")


# CLAUSE 7 — summary.json has expected keys
def test_json_summary_keys() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="json_test_") as d:
        writer = JsonWriter(output_dir=d)
        result = writer.write(state)
        data = json.loads(result["summary"].read_text("utf-8"))
        for key in ("run_id", "target", "scope", "total_subdomains",
                     "live_subdomains", "completed_stages"):
            assert key in data, f"Missing summary key: {key}"
        assert data["total_subdomains"] == 3
        assert data["live_subdomains"] == 2  # api + cdn
    print("  [PASS] clause 7 -- summary.json contains all expected keys")


# CLAUSE 8 — full_state.json is valid PipelineState JSON
def test_json_full_state_roundtrip() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="json_test_") as d:
        writer = JsonWriter(output_dir=d)
        result = writer.write(state)
        data = json.loads(result["full_state"].read_text("utf-8"))
        # Must be re-loadable as PipelineState
        reloaded = PipelineState.model_validate(data)
        assert reloaded.run_id == state.run_id
        assert reloaded.target == state.target
        assert len(reloaded.subdomains) == 3
    print("  [PASS] clause 8 -- full_state.json round-trips to PipelineState")


# CLAUSE 9 — Files are in per-target subdirectory
def test_json_per_target_dir() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="json_test_") as d:
        writer = JsonWriter(output_dir=d)
        result = writer.write(state)
        for name, path in result.items():
            assert "example.com" in str(path.parent.name), \
                f"{name} not in per-target directory: {path}"
    print("  [PASS] clause 9 -- files written to per-target subdirectory")


# CLAUSE 10 — Atomic writes (no .tmp files left behind)
def test_json_no_tmp_files() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="json_test_") as d:
        writer = JsonWriter(output_dir=d)
        writer.write(state)
        for f in Path(d).rglob("*.tmp"):
            assert False, f"Leftover .tmp file: {f}"
    print("  [PASS] clause 10 -- no .tmp files left after write")


# ===========================================================================
# SQLITEWRITER TESTS
# ===========================================================================

# CLAUSE 11 — write() returns db path
def test_sqlite_write_returns_path() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="db_test_") as d:
        db_path = str(Path(d) / "recon.db")
        writer = SqliteWriter(db_path=db_path)
        try:
            result = writer.write(state)
            assert result is not None
            assert result.exists()
        finally:
            writer.close()
    print("  [PASS] clause 11 -- write() returns valid db path")


# CLAUSE 12 — runs table populated correctly
def test_sqlite_runs_table() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="db_test_") as d:
        db_path = str(Path(d) / "recon.db")
        writer = SqliteWriter(db_path=db_path)
        try:
            writer.write(state)
            runs = writer.query_runs()
            assert len(runs) == 1
            assert runs[0]["run_id"] == state.run_id
            assert runs[0]["target"] == "example.com"
            scope = json.loads(runs[0]["scope"])
            assert "*.example.com" in scope
        finally:
            writer.close()
    print("  [PASS] clause 12 -- runs table has correct data")


# CLAUSE 13 — subdomains table populated correctly
def test_sqlite_subdomains_table() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="db_test_") as d:
        db_path = str(Path(d) / "recon.db")
        writer = SqliteWriter(db_path=db_path)
        try:
            writer.write(state)
            subs = writer.query_subdomains(state.run_id)
            assert len(subs) == 3
            names = {s["subdomain"] for s in subs}
            assert "api.example.com" in names
            assert "mail.example.com" in names
            # Check api.example.com has correct details
            api = [s for s in subs if s["subdomain"] == "api.example.com"][0]
            assert api["is_live"] == 1
            assert api["http_status"] == 200
            assert api["urls_count"] == 2
        finally:
            writer.close()
    print("  [PASS] clause 13 -- subdomains table has correct data")


# CLAUSE 14 — recon_results table populated
def test_sqlite_results_table() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="db_test_") as d:
        db_path = str(Path(d) / "recon.db")
        writer = SqliteWriter(db_path=db_path)
        try:
            writer.write(state)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM recon_results WHERE run_id = ?",
                (state.run_id,),
            ).fetchall()
            conn.close()
            assert len(rows) == 2  # SUBDOMAIN_ENUM + HTTP_PROBE results
            tools = {r["tool"] for r in rows}
            assert "SubfinderTool" in tools
            assert "HttpxTool" in tools
        finally:
            writer.close()
    print("  [PASS] clause 14 -- recon_results table has correct data")


# CLAUSE 15 — query_runs() filtered by target
def test_sqlite_query_runs_filtered() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="db_test_") as d:
        db_path = str(Path(d) / "recon.db")
        writer = SqliteWriter(db_path=db_path)
        try:
            writer.write(state)
            found = writer.query_runs(target="example.com")
            assert len(found) == 1
            not_found = writer.query_runs(target="nonexistent.com")
            assert len(not_found) == 0
        finally:
            writer.close()
    print("  [PASS] clause 15 -- query_runs() filters by target correctly")


# CLAUSE 16 — Duplicate run_id uses INSERT OR REPLACE (idempotent)
def test_sqlite_idempotent_write() -> None:
    state = _make_state()
    with tempfile.TemporaryDirectory(prefix="db_test_") as d:
        db_path = str(Path(d) / "recon.db")
        writer = SqliteWriter(db_path=db_path)
        try:
            writer.write(state)
            writer.write(state)  # second write with same run_id
            runs = writer.query_runs()
            assert len(runs) == 1, f"Expected 1 run after idempotent write, got {len(runs)}"
        finally:
            writer.close()
    print("  [PASS] clause 16 -- duplicate write is idempotent for runs table")


# CLAUSE 17 — close() is safe to call multiple times
def test_sqlite_close_idempotent() -> None:
    with tempfile.TemporaryDirectory(prefix="db_test_") as d:
        db_path = str(Path(d) / "recon.db")
        writer = SqliteWriter(db_path=db_path)
        writer.close()
        writer.close()  # must not raise
    print("  [PASS] clause 17 -- close() is safe to call multiple times")


# CLAUSE 18 — db_path property
def test_sqlite_db_path_property() -> None:
    with tempfile.TemporaryDirectory(prefix="db_test_") as d:
        db_path = str(Path(d) / "recon.db")
        writer = SqliteWriter(db_path=db_path)
        assert writer.db_path == Path(db_path).resolve()
        writer.close()
    print("  [PASS] clause 18 -- db_path property returns resolved path")


# ===========================================================================
# Runner
# ===========================================================================

def run_all() -> None:
    tests = [
        test_json_write_returns_dict,
        test_json_all_files_produced,
        test_json_subdomains_complete,
        test_json_live_hosts_filter,
        test_json_urls_by_host,
        test_json_ports_by_host,
        test_json_summary_keys,
        test_json_full_state_roundtrip,
        test_json_per_target_dir,
        test_json_no_tmp_files,
        test_sqlite_write_returns_path,
        test_sqlite_runs_table,
        test_sqlite_subdomains_table,
        test_sqlite_results_table,
        test_sqlite_query_runs_filtered,
        test_sqlite_idempotent_write,
        test_sqlite_close_idempotent,
        test_sqlite_db_path_property,
    ]

    passed = failed = 0
    print(f"\n{'='*62}")
    print("  Output Writers Contract Conformance Tests")
    print(f"{'='*62}")

    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as exc:
            import traceback
            print(f"  [FAIL] {fn.__name__}: {exc}")
            traceback.print_exc()
            failed += 1

    print(f"{'='*62}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print(f"{'='*62}\n")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
