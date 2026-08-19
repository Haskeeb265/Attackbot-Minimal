"""
tests/test_utils_contract.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Conformance test for utilities (logger, rate_limiter, dedup).

Run:
    $env:PYTHONPATH = "<repo-root>"
    .venv/Scripts/python tests/test_utils_contract.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
import tempfile
import time
from pathlib import Path

from recon_node.models import Subdomain
from recon_node.utils.dedup import (
    deduplicate_subdomains,
    deduplicate_urls,
    normalize_fqdn,
    normalize_url,
)
from recon_node.utils.logger import get_logger, reset_logging, setup_logging
from recon_node.utils.rate_limiter import TokenBucket


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_async(coro):
    return asyncio.run(coro)


# ===========================================================================
# LOGGER TESTS
# ===========================================================================

# CLAUSE 1 — setup_logging returns a logger
def test_setup_logging_returns_logger() -> None:
    reset_logging()
    logger = setup_logging(verbose=False)
    assert isinstance(logger, logging.Logger)
    assert logger.name == "recon_node"
    assert logger.level == logging.INFO
    reset_logging()
    print("  [PASS] clause 1 -- setup_logging returns recon_node Logger at INFO")


# CLAUSE 2 — verbose=True sets DEBUG
def test_setup_logging_verbose() -> None:
    reset_logging()
    logger = setup_logging(verbose=True)
    assert logger.level == logging.DEBUG
    reset_logging()
    print("  [PASS] clause 2 -- setup_logging(verbose=True) sets DEBUG level")


# CLAUSE 3 — log_file creates a file handler
def test_setup_logging_file() -> None:
    reset_logging()
    with tempfile.TemporaryDirectory(prefix="log_test_") as d:
        log_path = str(Path(d) / "test.log")
        logger = setup_logging(log_file=log_path)
        logger.info("test message from test_setup_logging_file")
        # Flush handlers
        for h in logger.handlers:
            h.flush()
        content = Path(log_path).read_text(encoding="utf-8")
        assert "test message" in content
        reset_logging()  # close file handle BEFORE temp dir cleanup
    print("  [PASS] clause 3 -- setup_logging(log_file=...) writes to file")


# CLAUSE 4 — setup_logging is idempotent
def test_setup_logging_idempotent() -> None:
    reset_logging()
    setup_logging(verbose=False)
    handler_count_1 = len(logging.getLogger("recon_node").handlers)
    setup_logging(verbose=True)  # re-call
    handler_count_2 = len(logging.getLogger("recon_node").handlers)
    assert handler_count_1 == handler_count_2, \
        f"Handlers grew: {handler_count_1} -> {handler_count_2}"
    reset_logging()
    print("  [PASS] clause 4 -- setup_logging is idempotent (no duplicate handlers)")


# CLAUSE 5 — get_logger returns child logger
def test_get_logger() -> None:
    logger = get_logger("my_module")
    assert logger.name == "recon_node.my_module"
    # Already-prefixed name
    logger2 = get_logger("recon_node.tools.subfinder")
    assert logger2.name == "recon_node.tools.subfinder"
    print("  [PASS] clause 5 -- get_logger returns child logger under recon_node")


# ===========================================================================
# RATE LIMITER TESTS
# ===========================================================================

# CLAUSE 6 — TokenBucket: starts full
def test_token_bucket_starts_full() -> None:
    bucket = TokenBucket(rate=10.0, capacity=10.0)
    assert bucket.available >= 9.9  # allow tiny float drift
    assert bucket.rate == 10.0
    assert bucket.capacity == 10.0
    print("  [PASS] clause 6 -- TokenBucket starts full")


# CLAUSE 7 — try_acquire: consumes tokens
def test_try_acquire() -> None:
    bucket = TokenBucket(rate=100.0, capacity=5.0)
    assert bucket.try_acquire(3.0) is True
    assert bucket.available < 2.1
    assert bucket.try_acquire(5.0) is False  # not enough
    print("  [PASS] clause 7 -- try_acquire consumes tokens, returns False when empty")


# CLAUSE 8 — acquire: blocks until tokens available
def test_acquire_blocks() -> None:
    async def _test():
        bucket = TokenBucket(rate=100.0, capacity=2.0)  # 100/sec refill
        bucket.try_acquire(2.0)  # drain it
        t0 = time.monotonic()
        await bucket.acquire(1.0)  # should wait ~10ms
        elapsed = time.monotonic() - t0
        assert elapsed < 0.5, f"Waited too long: {elapsed}s"
    run_async(_test())
    print("  [PASS] clause 8 -- acquire() blocks and resumes when tokens refill")


# CLAUSE 9 — capacity defaults to rate
def test_capacity_default() -> None:
    bucket = TokenBucket(rate=5.0)
    assert bucket.capacity == 5.0
    print("  [PASS] clause 9 -- capacity defaults to rate")


# CLAUSE 10 — invalid rate raises ValueError
def test_invalid_rate() -> None:
    try:
        TokenBucket(rate=0)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    try:
        TokenBucket(rate=-1)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    print("  [PASS] clause 10 -- invalid rate raises ValueError")


# ===========================================================================
# DEDUP TESTS
# ===========================================================================

# CLAUSE 11 — normalize_fqdn: lowercase + strip
def test_normalize_fqdn() -> None:
    assert normalize_fqdn("  API.Example.COM  ") == "api.example.com"
    assert normalize_fqdn("api.example.com.") == "api.example.com"   # trailing dot
    assert normalize_fqdn("https://api.example.com/path") == "api.example.com"
    assert normalize_fqdn("api.example.com:8080") == "api.example.com"
    print("  [PASS] clause 11 -- normalize_fqdn: strip, lower, remove scheme/port/dot")


# CLAUSE 12 — normalize_url: lowercase scheme+host, strip trailing slash
def test_normalize_url() -> None:
    assert normalize_url("HTTPS://API.Example.COM/") == "https://api.example.com/"
    assert normalize_url("https://api.example.com/path/") == "https://api.example.com/path"
    assert normalize_url("https://api.example.com") == "https://api.example.com/"
    print("  [PASS] clause 12 -- normalize_url: lowercase scheme+host, strip trailing /")


# CLAUSE 13 — deduplicate_subdomains: by FQDN, keeps first
def test_deduplicate_subdomains() -> None:
    subs = [
        Subdomain(subdomain="api.example.com", source="tool1"),
        Subdomain(subdomain="API.EXAMPLE.COM", source="tool2"),
        Subdomain(subdomain="mail.example.com", source="tool1"),
        Subdomain(subdomain="api.example.com.", source="tool3"),  # trailing dot
    ]
    result = deduplicate_subdomains(subs)
    assert len(result) == 2, f"Expected 2, got {len(result)}"
    assert result[0].source == "tool1"  # kept first occurrence
    names = {sd.subdomain for sd in result}
    assert "api.example.com" in names
    assert "mail.example.com" in names
    print("  [PASS] clause 13 -- deduplicate_subdomains: 4 -> 2, keeps first")


# CLAUSE 14 — deduplicate_subdomains: does not mutate input
def test_deduplicate_subdomains_no_mutate() -> None:
    original = [
        Subdomain(subdomain="a.example.com", source="t1"),
        Subdomain(subdomain="a.example.com", source="t2"),
    ]
    original_len = len(original)
    result = deduplicate_subdomains(original)
    assert len(original) == original_len, "Input list was mutated"
    assert len(result) == 1
    print("  [PASS] clause 14 -- deduplicate_subdomains does not mutate input")


# CLAUSE 15 — deduplicate_urls: by normalized form
def test_deduplicate_urls() -> None:
    urls = [
        "https://api.example.com/v1",
        "HTTPS://API.EXAMPLE.COM/v1",   # same after normalize
        "https://api.example.com/v2",
        "https://api.example.com/v1/",   # trailing slash = different path
    ]
    result = deduplicate_urls(urls)
    assert len(result) == 2, f"Expected 2, got {len(result)}: {result}"
    print(f"  [PASS] clause 15 -- deduplicate_urls: 4 -> {len(result)}")


# CLAUSE 16 — deduplicate_urls: preserves order
def test_deduplicate_urls_order() -> None:
    urls = ["https://c.com", "https://a.com", "https://b.com", "https://a.com"]
    result = deduplicate_urls(urls)
    assert result == ["https://c.com", "https://a.com", "https://b.com"]
    print("  [PASS] clause 16 -- deduplicate_urls preserves insertion order")


# ===========================================================================
# Runner
# ===========================================================================

def run_all() -> None:
    tests = [
        test_setup_logging_returns_logger,
        test_setup_logging_verbose,
        test_setup_logging_file,
        test_setup_logging_idempotent,
        test_get_logger,
        test_token_bucket_starts_full,
        test_try_acquire,
        test_acquire_blocks,
        test_capacity_default,
        test_invalid_rate,
        test_normalize_fqdn,
        test_normalize_url,
        test_deduplicate_subdomains,
        test_deduplicate_subdomains_no_mutate,
        test_deduplicate_urls,
        test_deduplicate_urls_order,
    ]

    passed = failed = 0
    print(f"\n{'='*62}")
    print("  Utilities Contract Conformance Tests")
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
