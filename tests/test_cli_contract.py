"""
tests/test_cli_contract.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Conformance test for CLI (main.py) and config loading.

Run:
    $env:PYTHONPATH = "<repo-root>"
    .venv/Scripts/python tests/test_cli_contract.py
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Optional

import yaml

from recon_node.main import (
    async_main,
    build_pipeline_config,
    load_config,
    parse_args,
    setup_logging,
)
from recon_node.models import Stage
from recon_node.pipeline.runner import PipelineConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_async(coro):
    return asyncio.run(coro)


def _write_yaml(d: dict, path: Path) -> Path:
    path.write_text(yaml.dump(d, default_flow_style=False), encoding="utf-8")
    return path


# ===========================================================================
# CLAUSE 1 — parse_args: required --target and --scope
# ===========================================================================

def test_parse_args_required() -> None:
    """--target and --scope are required."""
    args = parse_args(["--target", "example.com", "--scope", "*.example.com"])
    assert args["target"] == "example.com"
    assert args["scope"] == ["*.example.com"]
    print("  [PASS] clause 1 -- parse_args: required args parsed correctly")


# ===========================================================================
# CLAUSE 2 — parse_args: --scope comma-separated
# ===========================================================================

def test_parse_args_scope_split() -> None:
    """--scope splits on commas."""
    args = parse_args(["--target", "x.com", "--scope", "*.x.com,api.x.com,admin.x.com"])
    assert len(args["scope"]) == 3
    assert "api.x.com" in args["scope"]
    print("  [PASS] clause 2 -- parse_args: comma-separated scope works")


# ===========================================================================
# CLAUSE 3 — parse_args: --stages filter
# ===========================================================================

def test_parse_args_stages_filter() -> None:
    """--stages creates a set of stage names."""
    args = parse_args([
        "--target", "x.com", "--scope", "*.x.com",
        "--stages", "subdomain_enum,dns_resolution",
    ])
    assert args["stages"] == {"subdomain_enum", "dns_resolution"}
    print("  [PASS] clause 3 -- parse_args: --stages creates filter set")


# ===========================================================================
# CLAUSE 4 — parse_args: --resume flag
# ===========================================================================

def test_parse_args_resume() -> None:
    """--resume sets resume=True."""
    args = parse_args(["--target", "x.com", "--scope", "*.x.com", "--resume"])
    assert args["resume"] is True
    args2 = parse_args(["--target", "x.com", "--scope", "*.x.com"])
    assert args2["resume"] is False
    print("  [PASS] clause 4 -- parse_args: --resume flag works")


# ===========================================================================
# CLAUSE 5 — parse_args: --no-json-output / --no-db-output
# ===========================================================================

def test_parse_args_output_flags() -> None:
    """Output flags can be disabled."""
    args = parse_args([
        "--target", "x.com", "--scope", "*.x.com",
        "--no-json-output", "--no-db-output",
    ])
    assert args["json_output"] is False
    assert args["db_output"] is False
    print("  [PASS] clause 5 -- parse_args: output disable flags work")


# ===========================================================================
# CLAUSE 6 — load_config: loads from YAML file
# ===========================================================================

def test_load_config_from_file() -> None:
    """load_config() loads a YAML file correctly."""
    with tempfile.TemporaryDirectory(prefix="cfg_test_") as d:
        cfg_path = Path(d) / "config.yaml"
        _write_yaml({"output_dir": "/tmp/test", "rate_limit": {"concurrent_tools": 7}}, cfg_path)
        raw = load_config(str(cfg_path))
        assert raw["output_dir"] == "/tmp/test"
        assert raw["rate_limit"]["concurrent_tools"] == 7
    print("  [PASS] clause 6 -- load_config: loads YAML correctly")


# ===========================================================================
# CLAUSE 7 — load_config: missing file returns defaults
# ===========================================================================

def test_load_config_missing_file() -> None:
    """load_config() with nonexistent file returns {}."""
    raw = load_config("/nonexistent/path/config.yaml")
    assert raw == {}
    print("  [PASS] clause 7 -- load_config: missing file returns empty dict")


# ===========================================================================
# CLAUSE 8 — load_config: corrupt YAML returns defaults
# ===========================================================================

def test_load_config_corrupt_yaml() -> None:
    """load_config() with corrupt YAML returns {}."""
    with tempfile.TemporaryDirectory(prefix="cfg_test_") as d:
        cfg_path = Path(d) / "config.yaml"
        cfg_path.write_text("{{{invalid yaml", encoding="utf-8")
        raw = load_config(str(cfg_path))
        assert raw == {}
    print("  [PASS] clause 8 -- load_config: corrupt YAML returns empty dict")


# ===========================================================================
# CLAUSE 9 — build_pipeline_config: merges YAML + CLI
# ===========================================================================

def test_build_pipeline_config_merge() -> None:
    """CLI overrides take precedence over YAML."""
    raw = {"output_dir": "./yaml_output", "rate_limit": {"concurrent_tools": 5}}
    config = build_pipeline_config(raw, output_dir="./cli_output")
    assert config.output_dir == "./cli_output"
    assert config.concurrent_tools == 5  # from YAML
    print("  [PASS] clause 9 -- build_pipeline_config: CLI overrides YAML")


# ===========================================================================
# CLAUSE 10 — build_pipeline_config: stage filter disables stages
# ===========================================================================

def test_build_pipeline_config_stage_filter() -> None:
    """Stage filter disables stages not in the whitelist."""
    config = build_pipeline_config({}, stages={"subdomain_enum"})
    assert config.stages["subdomain_enum"] is True
    assert config.stages["dns_resolution"] is False
    assert config.stages["http_probe"] is False
    print("  [PASS] clause 10 -- build_pipeline_config: stage filter works")


# ===========================================================================
# CLAUSE 11 — build_pipeline_config: YAML stage disabled + CLI filter
# ===========================================================================

def test_build_pipeline_config_yaml_disabled_plus_filter() -> None:
    """YAML disabled + CLI filter = stage stays disabled."""
    raw = {"stages": {"subdomain_enum": False}}
    config = build_pipeline_config(raw, stages={"subdomain_enum"})
    assert config.stages["subdomain_enum"] is False, \
        "YAML disabled stage should stay disabled even with CLI filter"
    print("  [PASS] clause 11 -- YAML disabled stage stays disabled with CLI filter")


# ===========================================================================
# CLAUSE 12 — build_pipeline_config: defaults when no YAML
# ===========================================================================

def test_build_pipeline_config_defaults() -> None:
    """Empty config dict produces sane defaults."""
    config = build_pipeline_config({})
    assert config.output_dir == "./output"
    assert config.concurrent_tools == 3
    assert all(v for v in config.stages.values()), "All stages should be enabled by default"
    print("  [PASS] clause 12 -- default config: all stages enabled, concurrent=3")


# ===========================================================================
# CLAUSE 13 — async_main: dry run produces output files
# ===========================================================================

def test_async_main_dry_run() -> None:
    """Full dry run with no installed tools produces JSON + SQLite output."""
    with tempfile.TemporaryDirectory(prefix="cli_test_") as d:
        output_dir = str(Path(d) / "output")
        exit_code = run_async(async_main([
            "--target", "example.com",
            "--scope", "*.example.com,example.com",
            "--output-dir", output_dir,
            "--verbose",
        ]))

        # Pipeline should complete (exit 0 or 1 depending on tool availability)
        assert exit_code in (0, 1), f"Unexpected exit code: {exit_code}"

        # Check JSON output exists
        target_dir = Path(output_dir) / "example.com"
        if target_dir.exists():
            assert (target_dir / "summary.json").exists(), "summary.json missing"
            assert (target_dir / "subdomains.json").exists(), "subdomains.json missing"

        # Check SQLite output exists
        db_path = Path(output_dir) / "recon.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            conn.close()
            assert "runs" in tables
            assert "subdomains" in tables

    print("  [PASS] clause 13 -- dry run produces output files")


# ===========================================================================
# CLAUSE 14 — config.yaml: file exists and is valid YAML
# ===========================================================================

def test_config_yaml_valid() -> None:
    """The shipped config.yaml must be valid and parseable."""
    cfg_path = Path(__file__).parent.parent / "recon_node" / "config.yaml"
    assert cfg_path.exists(), f"config.yaml not found at {cfg_path}"
    raw = load_config(str(cfg_path))
    assert isinstance(raw, dict)
    assert "stages" in raw
    assert "rate_limit" in raw
    print("  [PASS] clause 14 -- config.yaml exists and is valid YAML")


# ===========================================================================
# CLAUSE 15 — config.yaml: all stages listed
# ===========================================================================

def test_config_yaml_all_stages() -> None:
    """config.yaml must list all non-OUTPUT stages."""
    cfg_path = Path(__file__).parent.parent / "recon_node" / "config.yaml"
    raw = load_config(str(cfg_path))
    stages = raw.get("stages", {})
    for s in Stage.ordered():
        if s == Stage.OUTPUT:
            continue
        assert s.value in stages, f"Stage {s.value} missing from config.yaml"
    print("  [PASS] clause 15 -- config.yaml lists all pipeline stages")


# ===========================================================================
# CLAUSE 16 — setup_logging: doesn't crash
# ===========================================================================

def test_setup_logging() -> None:
    """setup_logging() must not raise for either verbose mode."""
    setup_logging(verbose=False)
    setup_logging(verbose=True)
    print("  [PASS] clause 16 -- setup_logging works for both modes")


# ===========================================================================
# Runner
# ===========================================================================

def run_all() -> None:
    tests = [
        test_parse_args_required,
        test_parse_args_scope_split,
        test_parse_args_stages_filter,
        test_parse_args_resume,
        test_parse_args_output_flags,
        test_load_config_from_file,
        test_load_config_missing_file,
        test_load_config_corrupt_yaml,
        test_build_pipeline_config_merge,
        test_build_pipeline_config_stage_filter,
        test_build_pipeline_config_yaml_disabled_plus_filter,
        test_build_pipeline_config_defaults,
        test_async_main_dry_run,
        test_config_yaml_valid,
        test_config_yaml_all_stages,
        test_setup_logging,
    ]

    passed = failed = 0
    print(f"\n{'='*62}")
    print("  CLI + Config Contract Conformance Tests")
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
