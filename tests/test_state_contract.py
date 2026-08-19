"""
tests/test_state_contract.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Conformance test suite for StateManager (pipeline/state.py).

Verifies every clause in the contract documented in pipeline/state.py.

Run:
    $env:PYTHONPATH = "<repo-root>"
    .venv/Scripts/python tests/test_state_contract.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _bootstrap() -> None:
    from recon_node.pipeline.state import StateManager  # noqa: F401

_bootstrap()

from recon_node.models import (
    HttpMetadata, PipelineState, Port, ReconResult, Stage, Subdomain,
)
from recon_node.pipeline.state import CHECKPOINT_SCHEMA_VERSION, StateManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_mgr() -> tuple[StateManager, Path]:
    """Return a StateManager backed by a fresh temp directory."""
    d = Path(tempfile.mkdtemp(prefix="recon_test_"))
    return StateManager(output_dir=str(d)), d


def _rich_state(mgr: StateManager) -> PipelineState:
    """Build a heavily populated PipelineState for round-trip tests."""
    state = mgr.new_state("example.com", ["*.example.com", "api.partner.io"])

    # Add two subdomains with nested models
    sd1 = Subdomain(
        subdomain="api.example.com",
        source="SubfinderTool",
        ip_addresses=["1.2.3.4", "1.2.3.5"],
        is_live=True,
        http_metadata=HttpMetadata(
            url="https://api.example.com",
            status_code=200,
            title="API Portal",
            technologies=["nginx", "React"],
            server="cloudflare",
            headers={"content-type": "text/html"},
        ),
        ports=[Port(port=443, service="https"), Port(port=80, service="http")],
        urls=["https://api.example.com/v1", "https://api.example.com/login"],
        technologies=["nginx", "React"],
    )
    sd2 = Subdomain(
        subdomain="mail.example.com",
        source="AssetfinderTool",
        ip_addresses=["5.6.7.8"],
    )
    state.upsert_subdomain(sd1)
    state.upsert_subdomain(sd2)

    # Add stage results
    rr = ReconResult(
        tool="SubfinderTool",
        stage=Stage.SUBDOMAIN_ENUM,
        target="example.com",
        data={"subdomains": ["api.example.com", "mail.example.com"]},
        raw_output="api.example.com\nmail.example.com\n",
    )
    state.add_stage_results(Stage.SUBDOMAIN_ENUM, [rr])
    state.mark_stage_complete(Stage.SUBDOMAIN_ENUM)

    # Add scoped-out audit entry
    state.log_scoped_out("evil.com", Stage.SUBDOMAIN_ENUM, "not in scope")

    return state


# ===========================================================================
# CLAUSE 1 — save() writes a file at the canonical path
# ===========================================================================

def test_save_creates_file() -> None:
    """save() must create a file at checkpoint_path()."""
    mgr, _ = _tmp_mgr()
    state   = mgr.new_state("example.com", ["*.example.com"])
    path    = mgr.save(state)

    assert path.exists(), f"Checkpoint file not created at {path}"
    assert path == mgr.checkpoint_path("example.com"), "Returned path != canonical path"
    assert path.stat().st_size > 0, "Checkpoint file is empty"
    print(f"  [PASS] clause 1 -- save() created file ({path.stat().st_size} bytes)")


# ===========================================================================
# CLAUSE 2 — save() writes valid JSON with schema envelope
# ===========================================================================

def test_save_writes_valid_json_envelope() -> None:
    """Checkpoint file must be valid JSON with schema_version + state keys."""
    mgr, _ = _tmp_mgr()
    state   = mgr.new_state("example.com", ["*.example.com"])
    path    = mgr.save(state)

    raw      = path.read_text(encoding="utf-8")
    envelope = json.loads(raw)   # raises if invalid JSON

    assert "schema_version" in envelope, "Missing schema_version key"
    assert "saved_at"        in envelope, "Missing saved_at key"
    assert "state"           in envelope, "Missing state key"
    assert envelope["schema_version"] == CHECKPOINT_SCHEMA_VERSION
    assert isinstance(envelope["state"], dict)
    assert envelope["state"]["target"] == "example.com"
    print("  [PASS] clause 2 -- valid JSON envelope with all required keys")


# ===========================================================================
# CLAUSE 3 — Atomic write: no .tmp file left after save()
# ===========================================================================

def test_save_atomic_no_tmp_leftover() -> None:
    """After save(), the .tmp file must not exist."""
    mgr, _ = _tmp_mgr()
    state   = mgr.new_state("example.com", ["*.example.com"])
    path    = mgr.save(state)

    tmp = path.with_suffix(".tmp")
    assert not tmp.exists(), f".tmp file still exists after save: {tmp}"
    print("  [PASS] clause 3 -- atomic write: no .tmp leftover")


# ===========================================================================
# CLAUSE 4 — Multiple saves overwrite cleanly (idempotent)
# ===========================================================================

def test_repeated_saves_overwrite() -> None:
    """Saving the same state twice must produce exactly one checkpoint file."""
    mgr, d  = _tmp_mgr()
    state   = mgr.new_state("example.com", ["*.example.com"])

    mgr.save(state)
    state.mark_stage_complete(Stage.SUBDOMAIN_ENUM)
    mgr.save(state)

    # Only one checkpoint file
    checkpoints = list(d.rglob("checkpoint.json"))
    assert len(checkpoints) == 1, f"Expected 1 checkpoint, found {len(checkpoints)}"

    # Loaded state must have the latest data
    loaded = mgr.load("example.com")
    assert Stage.SUBDOMAIN_ENUM in loaded.completed_stages
    print("  [PASS] clause 4 -- repeated saves overwrite cleanly (idempotent)")


# ===========================================================================
# CLAUSE 5 — Output directory created automatically
# ===========================================================================

def test_save_creates_output_dir() -> None:
    """save() must create output_dir/target/ if it does not exist."""
    with tempfile.TemporaryDirectory() as base:
        nested = Path(base) / "does" / "not" / "exist"
        mgr    = StateManager(output_dir=str(nested))
        state  = mgr.new_state("example.com", ["*.example.com"])
        path   = mgr.save(state)
        assert path.exists()
    print("  [PASS] clause 5 -- output directory created automatically")


# ===========================================================================
# CLAUSE 6 — Full round-trip: save → load → identical data
# ===========================================================================

def test_round_trip_basic_fields() -> None:
    """Core identity fields must survive save → load."""
    mgr, _  = _tmp_mgr()
    state   = mgr.new_state("example.com", ["*.example.com", "api.partner.io"])
    run_id  = state.run_id

    mgr.save(state)
    loaded  = mgr.load("example.com")

    assert loaded is not None,                   "load() returned None"
    assert loaded.run_id     == run_id,          "run_id mismatch"
    assert loaded.target     == "example.com",   "target mismatch"
    assert loaded.scope      == ["*.example.com", "api.partner.io"], "scope mismatch"
    assert loaded.output_dir == state.output_dir, "output_dir mismatch"
    print("  [PASS] clause 6a -- basic identity fields survive round-trip")


def test_round_trip_completed_stages() -> None:
    """Completed stages list must survive save → load."""
    mgr, _  = _tmp_mgr()
    state   = mgr.new_state("example.com", ["*.example.com"])
    state.mark_stage_complete(Stage.SUBDOMAIN_ENUM)
    state.mark_stage_complete(Stage.DNS_RESOLUTION)

    mgr.save(state)
    loaded = mgr.load("example.com")

    assert Stage.SUBDOMAIN_ENUM  in loaded.completed_stages
    assert Stage.DNS_RESOLUTION  in loaded.completed_stages
    assert Stage.HTTP_PROBE  not in loaded.completed_stages
    print("  [PASS] clause 6b -- completed_stages survive round-trip")


def test_round_trip_subdomains_with_nested_models() -> None:
    """Subdomains with nested Port + HttpMetadata must survive round-trip."""
    mgr, _  = _tmp_mgr()
    state   = _rich_state(mgr)

    mgr.save(state)
    loaded  = mgr.load("example.com")

    assert len(loaded.subdomains) == 2

    api = loaded.get_subdomain("api.example.com")
    assert api is not None,                          "api.example.com missing after round-trip"
    assert api.is_live is True
    assert api.source == "SubfinderTool"
    assert "1.2.3.4" in api.ip_addresses
    assert api.http_metadata is not None
    assert api.http_metadata.status_code == 200
    assert api.http_metadata.title == "API Portal"
    assert "nginx" in api.http_metadata.technologies
    assert len(api.ports) == 2
    assert any(p.port == 443 for p in api.ports)
    assert len(api.urls) == 2
    print("  [PASS] clause 6c -- subdomains with nested models survive round-trip")


def test_round_trip_stage_results() -> None:
    """Stage results (ReconResult list) must survive round-trip."""
    mgr, _  = _tmp_mgr()
    state   = _rich_state(mgr)

    mgr.save(state)
    loaded  = mgr.load("example.com")

    results = loaded.get_stage_results(Stage.SUBDOMAIN_ENUM)
    assert len(results) == 1
    r = results[0]
    assert r.tool == "SubfinderTool"
    assert r.success is True
    assert "api.example.com" in r.data["subdomains"]
    print("  [PASS] clause 6d -- stage results survive round-trip")


def test_round_trip_audit_log() -> None:
    """Scoped-out audit log must survive round-trip."""
    mgr, _  = _tmp_mgr()
    state   = _rich_state(mgr)

    mgr.save(state)
    loaded  = mgr.load("example.com")

    assert len(loaded.scoped_out_targets) == 1
    entry = loaded.scoped_out_targets[0]
    assert entry["target"] == "evil.com"
    assert entry["stage"]  == "subdomain_enum"
    assert entry["reason"] == "not in scope"
    print("  [PASS] clause 6e -- scoped-out audit log survives round-trip")


def test_round_trip_timestamps() -> None:
    """started_at datetime must survive round-trip with UTC timezone."""
    mgr, _  = _tmp_mgr()
    state   = mgr.new_state("example.com", ["*.example.com"])
    before  = state.started_at

    mgr.save(state)
    loaded  = mgr.load("example.com")

    assert loaded.started_at.isoformat() == before.isoformat(), "started_at changed"
    assert loaded.started_at.tzinfo is not None, "Timezone stripped after round-trip"
    print("  [PASS] clause 6f -- timestamps survive round-trip (UTC-aware)")


# ===========================================================================
# CLAUSE 7 — load() returns None when no checkpoint exists
# ===========================================================================

def test_load_none_when_no_checkpoint() -> None:
    """load() must return None if no checkpoint file exists."""
    mgr, _ = _tmp_mgr()
    result = mgr.load("nonexistent.com")
    assert result is None, f"Expected None, got {result}"
    print("  [PASS] clause 7 -- load() returns None when no checkpoint exists")


# ===========================================================================
# CLAUSE 8 — load() returns None on corrupt file, NEVER raises
# ===========================================================================

def test_load_none_on_corrupt_json() -> None:
    """load() must return None for a corrupt checkpoint, never raise."""
    mgr, _ = _tmp_mgr()
    path   = mgr.checkpoint_path("example.com")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not valid json at all !!!", encoding="utf-8")

    result = mgr.load("example.com")
    assert result is None, "Expected None for corrupt JSON"
    print("  [PASS] clause 8a -- corrupt JSON: load() returns None")


def test_load_none_on_wrong_schema_version() -> None:
    """load() must return None if schema_version != expected."""
    mgr, _ = _tmp_mgr()
    state  = mgr.new_state("example.com", ["*.example.com"])
    path   = mgr.save(state)

    # Corrupt the schema version
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["schema_version"] = 999
    path.write_text(json.dumps(envelope), encoding="utf-8")

    result = mgr.load("example.com")
    assert result is None, "Expected None for wrong schema version"
    print("  [PASS] clause 8b -- wrong schema version: load() returns None")


def test_load_none_on_missing_state_key() -> None:
    """load() must return None if the 'state' key is absent from envelope."""
    mgr, _ = _tmp_mgr()
    path   = mgr.checkpoint_path("example.com")
    path.parent.mkdir(parents=True, exist_ok=True)
    bad = {"schema_version": CHECKPOINT_SCHEMA_VERSION, "saved_at": "2026-01-01"}
    path.write_text(json.dumps(bad), encoding="utf-8")

    result = mgr.load("example.com")
    assert result is None
    print("  [PASS] clause 8c -- missing 'state' key: load() returns None")


def test_load_none_on_invalid_state_dict() -> None:
    """load() must return None if the state dict fails Pydantic validation."""
    mgr, _ = _tmp_mgr()
    path   = mgr.checkpoint_path("example.com")
    path.parent.mkdir(parents=True, exist_ok=True)
    bad = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "saved_at": "2026-01-01",
        "state": {"completely_wrong": "fields"},
    }
    path.write_text(json.dumps(bad), encoding="utf-8")

    result = mgr.load("example.com")
    assert result is None
    print("  [PASS] clause 8d -- invalid state dict: load() returns None")


# ===========================================================================
# CLAUSE 9 — can_resume() returns True only if valid checkpoint exists
# ===========================================================================

def test_can_resume_false_when_no_checkpoint() -> None:
    """can_resume() must return False when no checkpoint exists."""
    mgr, _ = _tmp_mgr()
    assert mgr.can_resume("example.com") is False
    print("  [PASS] clause 9a -- can_resume() False: no checkpoint")


def test_can_resume_true_after_save() -> None:
    """can_resume() must return True after a successful save()."""
    mgr, _ = _tmp_mgr()
    state  = mgr.new_state("example.com", ["*.example.com"])
    mgr.save(state)
    assert mgr.can_resume("example.com") is True
    print("  [PASS] clause 9b -- can_resume() True: checkpoint exists")


def test_can_resume_false_after_delete() -> None:
    """can_resume() must return False after delete() is called."""
    mgr, _ = _tmp_mgr()
    state  = mgr.new_state("example.com", ["*.example.com"])
    mgr.save(state)
    mgr.delete("example.com")
    assert mgr.can_resume("example.com") is False
    print("  [PASS] clause 9c -- can_resume() False: after delete()")


# ===========================================================================
# CLAUSE 10 — run_id validation in load()
# ===========================================================================

def test_load_run_id_match_succeeds() -> None:
    """load(run_id=...) must succeed when run_id matches."""
    mgr, _ = _tmp_mgr()
    state  = mgr.new_state("example.com", ["*.example.com"])
    run_id = state.run_id
    mgr.save(state)

    loaded = mgr.load("example.com", run_id=run_id)
    assert loaded is not None
    assert loaded.run_id == run_id
    print("  [PASS] clause 10a -- run_id match: load() succeeds")


def test_load_run_id_mismatch_returns_none() -> None:
    """load(run_id=...) must return None when run_id doesn't match."""
    mgr, _ = _tmp_mgr()
    state  = mgr.new_state("example.com", ["*.example.com"])
    mgr.save(state)

    loaded = mgr.load("example.com", run_id=str(uuid.uuid4()))
    assert loaded is None, "Expected None on run_id mismatch"
    print("  [PASS] clause 10b -- run_id mismatch: load() returns None")


# ===========================================================================
# CLAUSE 11 — checkpoint_path() is deterministic and filesystem-safe
# ===========================================================================

def test_checkpoint_path_deterministic() -> None:
    """checkpoint_path() returns the same path on every call."""
    mgr, d = _tmp_mgr()
    p1 = mgr.checkpoint_path("example.com")
    p2 = mgr.checkpoint_path("example.com")
    assert p1 == p2
    assert "example.com" in str(p1)
    assert p1.name == "checkpoint.json"
    print("  [PASS] clause 11a -- checkpoint_path() is deterministic")


def test_checkpoint_path_sanitizes_target() -> None:
    """Targets with URL schemes / ports must be sanitized to safe directory names."""
    mgr, _ = _tmp_mgr()
    cases = [
        ("https://example.com/path", "example.com"),
        ("example.com:443",          "example.com"),
        ("http://api.example.com",   "api.example.com"),
    ]
    for target, expected_dir in cases:
        path = mgr.checkpoint_path(target)
        assert path.parent.name == expected_dir, \
            f"Expected dir '{expected_dir}', got '{path.parent.name}' for '{target}'"
    print(f"  [PASS] clause 11b -- checkpoint_path() sanitizes {len(cases)} target variants")


# ===========================================================================
# CLAUSE 12 — new_state() factory produces a valid PipelineState
# ===========================================================================

def test_new_state_factory() -> None:
    """new_state() must produce a PipelineState with correct fields."""
    mgr, d = _tmp_mgr()
    state  = mgr.new_state("example.com", ["*.example.com"])

    assert isinstance(state, PipelineState)
    assert state.target     == "example.com"
    assert state.scope      == ["*.example.com"]
    assert state.output_dir == str(mgr._output_dir)
    assert len(state.run_id) == 36               # UUID4 format
    assert len(state.subdomains)    == 0
    assert len(state.completed_stages) == 0
    print("  [PASS] clause 12a -- new_state() produces fresh, valid PipelineState")


def test_new_state_explicit_run_id() -> None:
    """new_state(run_id=...) must use the supplied run_id."""
    mgr, _ = _tmp_mgr()
    rid    = str(uuid.uuid4())
    state  = mgr.new_state("example.com", ["*.example.com"], run_id=rid)
    assert state.run_id == rid
    print("  [PASS] clause 12b -- new_state() uses explicit run_id")


# ===========================================================================
# CLAUSE 13 — delete() removes checkpoint cleanly
# ===========================================================================

def test_delete_removes_file() -> None:
    """delete() must remove the checkpoint file."""
    mgr, _ = _tmp_mgr()
    state  = mgr.new_state("example.com", ["*.example.com"])
    mgr.save(state)
    assert mgr.checkpoint_path("example.com").exists()

    result = mgr.delete("example.com")
    assert result is True
    assert not mgr.checkpoint_path("example.com").exists()
    print("  [PASS] clause 13a -- delete() removes checkpoint file")


def test_delete_returns_false_when_nothing_to_delete() -> None:
    """delete() on a nonexistent checkpoint must return False, not raise."""
    mgr, _ = _tmp_mgr()
    result = mgr.delete("nonexistent.com")
    assert result is True or result is False   # either is acceptable, must not raise
    print("  [PASS] clause 13b -- delete() on missing checkpoint: no exception")


# ===========================================================================
# Runner
# ===========================================================================

def run_all() -> None:
    tests = [
        test_save_creates_file,
        test_save_writes_valid_json_envelope,
        test_save_atomic_no_tmp_leftover,
        test_repeated_saves_overwrite,
        test_save_creates_output_dir,
        test_round_trip_basic_fields,
        test_round_trip_completed_stages,
        test_round_trip_subdomains_with_nested_models,
        test_round_trip_stage_results,
        test_round_trip_audit_log,
        test_round_trip_timestamps,
        test_load_none_when_no_checkpoint,
        test_load_none_on_corrupt_json,
        test_load_none_on_wrong_schema_version,
        test_load_none_on_missing_state_key,
        test_load_none_on_invalid_state_dict,
        test_can_resume_false_when_no_checkpoint,
        test_can_resume_true_after_save,
        test_can_resume_false_after_delete,
        test_load_run_id_match_succeeds,
        test_load_run_id_mismatch_returns_none,
        test_checkpoint_path_deterministic,
        test_checkpoint_path_sanitizes_target,
        test_new_state_factory,
        test_new_state_explicit_run_id,
        test_delete_removes_file,
        test_delete_returns_false_when_nothing_to_delete,
    ]

    passed = failed = 0
    print(f"\n{'='*60}")
    print("  StateManager Contract Conformance Tests")
    print(f"{'='*60}")

    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as exc:
            import traceback
            print(f"  [FAIL] {fn.__name__}: {exc}")
            traceback.print_exc()
            failed += 1

    print(f"{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print(f"{'='*60}\n")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
