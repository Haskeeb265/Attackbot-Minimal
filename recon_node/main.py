"""
main.py
~~~~~~~
CLI entry point for the Attackbot-Minima recon pipeline.

Usage:
    python main.py --target example.com --scope "*.example.com"
    python main.py --target example.com --scope "*.example.com" --resume
    python main.py --target example.com --scope "*.example.com" --stages subdomain_enum,dns_resolution
    python main.py --target example.com --scope "*.example.com" --config my_config.yaml
    python main.py --target example.com --scope "*.example.com" --output-dir ./results

CONTRACT
--------
CLI Arguments:
    --target        (required) Root domain to scan
    --scope         (required) Comma-separated scope patterns
    --config        (optional) Path to config.yaml — defaults to ./config.yaml
    --output-dir    (optional) Override output_dir from config
    --stages        (optional) Comma-separated whitelist of stages to run
    --resume        (optional) Resume from last checkpoint
    --json-output   (optional) Write JSON artefacts after pipeline completes
    --db-output     (optional) Write to SQLite after pipeline completes
    --verbose       (optional) Enable DEBUG logging

Exit codes:
    0 — pipeline completed successfully
    1 — pipeline failed (at least one stage had errors)
    2 — bad CLI arguments / config
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, Set

import yaml

from recon_node.models import Stage
from recon_node.output.db import SqliteWriter
from recon_node.output.json_writer import JsonWriter
from recon_node.pipeline.runner import PipelineConfig, PipelineRunner
from recon_node.pipeline.state import StateManager


log = logging.getLogger("recon_node")


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(config_path: Optional[str] = None) -> dict:
    """
    Load config from YAML file.

    Falls back to built-in defaults if no file is found.
    NEVER raises — returns a default dict on any error.
    """
    if config_path is None:
        # Look in common locations
        candidates = [
            Path("config.yaml"),
            Path("recon_node/config.yaml"),
            Path(__file__).parent / "config.yaml",
        ]
        for p in candidates:
            if p.exists():
                config_path = str(p)
                break

    if config_path and Path(config_path).exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            log.info("Config loaded from %s", config_path)
            return raw
        except Exception as exc:
            log.warning("Failed to load config from %s: %s — using defaults", config_path, exc)
            return {}
    else:
        if config_path:
            log.warning("Config file not found: %s — using defaults", config_path)
        return {}


def build_pipeline_config(
    raw:        dict,
    output_dir: Optional[str] = None,
    stages:     Optional[Set[str]] = None,
) -> PipelineConfig:
    """
    Build a PipelineConfig from raw YAML dict + CLI overrides.

    CLI arguments take precedence over YAML values.
    """
    cfg_output_dir       = output_dir or raw.get("output_dir", "./output")
    cfg_concurrent_tools = raw.get("rate_limit", {}).get("concurrent_tools", 3)
    cfg_tool_overrides   = raw.get("tools", {}) or {}

    # Stages: merge YAML + CLI filter
    yaml_stages = raw.get("stages", {})
    stage_map = {}
    for s in Stage.ordered():
        yaml_enabled = yaml_stages.get(s.value, True)
        if stages is not None:
            # CLI filter: only enable stages in the whitelist
            stage_map[s.value] = (s.value in stages) and yaml_enabled
        else:
            stage_map[s.value] = yaml_enabled

    return PipelineConfig(
        output_dir       = cfg_output_dir,
        stages           = stage_map,
        concurrent_tools = cfg_concurrent_tools,
        tool_overrides   = cfg_tool_overrides,
    )


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging to stderr."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> dict:
    """
    Parse CLI arguments.

    Returns a dict of parsed values.  Uses argparse instead of click
    to avoid external dependency issues in testing.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="recon-node",
        description="Attackbot-Minima — modular bug bounty recon pipeline",
    )
    parser.add_argument(
        "--target", "-t",
        required=True,
        help="Root domain to scan (e.g. example.com)",
    )
    parser.add_argument(
        "--scope", "-s",
        required=True,
        help="Comma-separated scope patterns (e.g. '*.example.com,api.example.com')",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to config.yaml (default: auto-detect)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Override output directory from config",
    )
    parser.add_argument(
        "--stages",
        default=None,
        help="Comma-separated whitelist of stages to run (default: all enabled)",
    )
    parser.add_argument(
        "--resume", "-r",
        action="store_true",
        default=False,
        help="Resume from last checkpoint",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        default=True,
        help="Write JSON artefacts (default: true)",
    )
    parser.add_argument(
        "--no-json-output",
        action="store_true",
        default=False,
        help="Disable JSON output",
    )
    parser.add_argument(
        "--db-output",
        action="store_true",
        default=True,
        help="Write to SQLite database (default: true)",
    )
    parser.add_argument(
        "--no-db-output",
        action="store_true",
        default=False,
        help="Disable SQLite output",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable DEBUG logging",
    )

    args = parser.parse_args(argv)

    # Parse scope
    scope = [s.strip() for s in args.scope.split(",") if s.strip()]

    # Parse stages filter
    stage_filter: Optional[Set[str]] = None
    if args.stages:
        stage_filter = {s.strip() for s in args.stages.split(",") if s.strip()}

    return {
        "target":      args.target.strip(),
        "scope":       scope,
        "config":      args.config,
        "output_dir":  args.output_dir,
        "stages":      stage_filter,
        "resume":      args.resume,
        "json_output": args.json_output and not args.no_json_output,
        "db_output":   args.db_output and not args.no_db_output,
        "verbose":     args.verbose,
    }


async def async_main(argv: list[str] | None = None) -> int:
    """
    Async entry point — parse args, build pipeline, run, write output.

    Returns exit code (0=success, 1=errors, 2=bad config).
    """
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return 2

    setup_logging(args["verbose"])

    log.info("=" * 60)
    log.info("Attackbot-Minima Recon Pipeline")
    log.info("Target: %s", args["target"])
    log.info("Scope:  %s", args["scope"])
    log.info("=" * 60)

    # Load config
    raw_config = load_config(args["config"])
    pipeline_config = build_pipeline_config(
        raw_config,
        output_dir=args["output_dir"],
        stages=args["stages"],
    )

    # Build pipeline
    state_mgr = StateManager(output_dir=pipeline_config.output_dir)
    runner    = PipelineRunner(config=pipeline_config, state_manager=state_mgr)

    # Build stage filter
    stage_filter: Optional[Set[Stage]] = None
    if args["stages"]:
        stage_filter = set()
        for s_name in args["stages"]:
            try:
                stage_filter.add(Stage(s_name))
            except ValueError:
                log.error("Unknown stage: %s", s_name)
                return 2

    # Run pipeline
    log.info("Starting pipeline...")
    state = await runner.run(
        target       = args["target"],
        scope        = args["scope"],
        resume       = args["resume"],
        stage_filter = stage_filter,
    )

    # Write outputs
    if args["json_output"]:
        try:
            json_writer = JsonWriter(output_dir=pipeline_config.output_dir)
            written = json_writer.write(state)
            log.info("JSON output: %d files written", len(written))
            for name, path in written.items():
                log.info("  %s → %s", name, path)
        except Exception as exc:
            log.error("JSON output failed: %s", exc)

    if args["db_output"]:
        try:
            db_path = str(
                Path(pipeline_config.output_dir) / raw_config.get("database", "recon.db")
            )
            db_writer = SqliteWriter(db_path=db_path)
            result = db_writer.write(state)
            if result:
                log.info("SQLite output: %s", result)
            db_writer.close()
        except Exception as exc:
            log.error("SQLite output failed: %s", exc)

    # Final summary
    summary = state.summary()
    log.info("=" * 60)
    log.info("Pipeline Complete")
    log.info("  Target:           %s", summary["target"])
    log.info("  Run ID:           %s", summary["run_id"])
    log.info("  Subdomains:       %d total, %d live", summary["total_subdomains"], summary["live_subdomains"])
    log.info("  URLs discovered:  %d", summary["total_urls"])
    log.info("  Ports found:      %d", summary["total_ports"])
    log.info("  Stages completed: %s", summary["completed_stages"])
    log.info("  Stages skipped:   %s", summary["skipped_stages"])
    log.info("=" * 60)

    # Exit code
    has_errors = any(
        not r.success
        for results in state.stage_results.values()
        for r in results
    )
    return 1 if has_errors else 0


def main(argv: list[str] | None = None) -> int:
    """Synchronous wrapper for async_main."""
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    sys.exit(main())
