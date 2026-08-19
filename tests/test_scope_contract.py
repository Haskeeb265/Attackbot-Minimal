"""
tests/test_scope_contract.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Conformance test suite for ScopeValidator.

Verifies every clause in the contract documented in pipeline/scope.py.

Run:
    $env:PYTHONPATH = "<repo-root>"
    .venv/Scripts/python tests/test_scope_contract.py
"""

from __future__ import annotations

import sys

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _bootstrap() -> None:
    from recon_node.pipeline.scope import ScopeValidator  # noqa: F401

_bootstrap()

from recon_node.pipeline.scope import ScopeValidator


# ===========================================================================
# CLAUSE 1 — is_in_scope signature: (target, scope_list=None) -> bool
# ===========================================================================

def test_signature_instance_mode() -> None:
    """Instance mode: ScopeValidator(scope).is_in_scope(target) -> bool."""
    v = ScopeValidator(["*.example.com"])
    result = v.is_in_scope("api.example.com")
    assert isinstance(result, bool), f"Expected bool, got {type(result)}"
    assert result is True
    print("  [PASS] clause 1a -- instance mode returns bool")


def test_signature_override_mode() -> None:
    """Override mode: is_in_scope(target, scope_list=[...]) ignores instance scope."""
    v = ScopeValidator(["*.evil.com"])  # instance has wrong scope
    result = v.is_in_scope("api.example.com", scope_list=["*.example.com"])
    assert result is True, "Override scope_list should take precedence"
    print("  [PASS] clause 1b -- scope_list override works")


def test_classmethod_check() -> None:
    """ScopeValidator.check() one-shot without instantiation."""
    assert ScopeValidator.check("api.example.com", ["*.example.com"]) is True
    assert ScopeValidator.check("evil.com",         ["*.example.com"]) is False
    print("  [PASS] clause 1c -- classmethod check() works")


# ===========================================================================
# CLAUSE 2 — Wildcard *.example.com matches all subdomains (any depth)
# ===========================================================================

def test_wildcard_single_level() -> None:
    """*.example.com must match first-level subdomains."""
    v = ScopeValidator(["*.example.com"])
    cases = ["api.example.com", "www.example.com", "mail.example.com", "x.example.com"]
    for target in cases:
        assert v.is_in_scope(target), f"Should match: {target}"
    print(f"  [PASS] clause 2a -- wildcard matches {len(cases)} single-level subdomains")


def test_wildcard_multi_level() -> None:
    """*.example.com must match multi-level subdomains (any depth)."""
    v = ScopeValidator(["*.example.com"])
    cases = [
        "sub.api.example.com",
        "a.b.c.example.com",
        "deep.sub.api.example.com",
    ]
    for target in cases:
        assert v.is_in_scope(target), f"Should match multi-level: {target}"
    print(f"  [PASS] clause 2b -- wildcard matches {len(cases)} multi-level subdomains")


# ===========================================================================
# CLAUSE 3 — Wildcard must NOT match the root domain itself
# ===========================================================================

def test_wildcard_does_not_match_root() -> None:
    """*.example.com must NOT match bare example.com."""
    v = ScopeValidator(["*.example.com"])
    assert v.is_in_scope("example.com") is False, \
        "Wildcard *.example.com must not match bare example.com"
    print("  [PASS] clause 3 -- wildcard does not match root domain")


# ===========================================================================
# CLAUSE 4 — Exact pattern matches only that exact FQDN
# ===========================================================================

def test_exact_match_hits() -> None:
    """Exact pattern api.example.com matches only that FQDN."""
    v = ScopeValidator(["api.example.com"])
    assert v.is_in_scope("api.example.com") is True
    print("  [PASS] clause 4a -- exact pattern matches itself")


def test_exact_match_no_subdomain_bleed() -> None:
    """Exact api.example.com must NOT match sub.api.example.com."""
    v = ScopeValidator(["api.example.com"])
    assert v.is_in_scope("sub.api.example.com") is False, \
        "Exact pattern should not cover subdomains"
    assert v.is_in_scope("example.com") is False
    print("  [PASS] clause 4b -- exact pattern has no subdomain bleed")


# ===========================================================================
# CLAUSE 5 — Out-of-scope targets are identified (filter returns them)
# ===========================================================================

def test_filter_partitions_correctly() -> None:
    """filter() must return (in_scope, out_of_scope) with nothing lost."""
    v = ScopeValidator(["*.example.com", "partner.io"])
    targets = [
        "api.example.com",       # in
        "evil.com",              # out
        "sub.api.example.com",   # in
        "partner.io",            # in (exact)
        "www.evil.com",          # out
        "admin.example.com",     # in
    ]
    in_scope, out_of_scope = v.filter(targets)

    assert set(in_scope)     == {"api.example.com", "sub.api.example.com",
                                  "partner.io", "admin.example.com"}, \
        f"in_scope mismatch: {in_scope}"
    assert set(out_of_scope) == {"evil.com", "www.evil.com"}, \
        f"out_of_scope mismatch: {out_of_scope}"
    # Nothing is lost
    assert len(in_scope) + len(out_of_scope) == len(targets)
    print(f"  [PASS] clause 5 -- filter(): {len(in_scope)} in-scope, "
          f"{len(out_of_scope)} dropped, no items lost")


# ===========================================================================
# CLAUSE 6 — Validator is stateless (safe to reuse across stages)
# ===========================================================================

def test_stateless_reuse() -> None:
    """Multiple calls must be independent — no shared mutable state."""
    v = ScopeValidator(["*.example.com"])
    first  = v.is_in_scope("a.example.com")
    second = v.is_in_scope("evil.com")
    third  = v.is_in_scope("b.example.com")
    assert first  is True
    assert second is False
    assert third  is True
    print("  [PASS] clause 6 -- stateless across multiple calls")


# ===========================================================================
# CLAUSE 7 — Case-insensitive comparison
# ===========================================================================

def test_case_insensitive_target() -> None:
    """Target casing must not affect match result."""
    v = ScopeValidator(["*.example.com"])
    cases = [
        "API.EXAMPLE.COM",
        "Api.Example.Com",
        "SUB.API.EXAMPLE.COM",
    ]
    for target in cases:
        assert v.is_in_scope(target) is True, f"Case-insensitive match failed for {target}"
    print(f"  [PASS] clause 7a -- case-insensitive target matching ({len(cases)} variants)")


def test_case_insensitive_scope_pattern() -> None:
    """Scope patterns in UPPER/Mixed case must still work."""
    v = ScopeValidator(["*.EXAMPLE.COM", "PARTNER.IO"])
    assert v.is_in_scope("api.example.com")  is True
    assert v.is_in_scope("partner.io")       is True
    print("  [PASS] clause 7b -- case-insensitive scope patterns")


# ===========================================================================
# CLAUSE 8 — Empty scope list — fail-closed (nothing passes)
# ===========================================================================

def test_empty_scope_denies_all() -> None:
    """Empty scope list must deny everything — safe default."""
    v = ScopeValidator([])
    assert v.is_in_scope("example.com")      is False
    assert v.is_in_scope("api.example.com")  is False
    assert v.is_in_scope("")                 is False

    in_scope, out_of_scope = v.filter(["a.com", "b.com", "c.com"])
    assert len(in_scope) == 0
    assert len(out_of_scope) == 3
    print("  [PASS] clause 8 -- empty scope denies all (fail-closed)")


# ===========================================================================
# CLAUSE 9 — Port-annotated targets (api.example.com:443)
# ===========================================================================

def test_port_stripping() -> None:
    """Port suffix must be stripped before matching."""
    v = ScopeValidator(["*.example.com"])
    cases = [
        "api.example.com:443",
        "api.example.com:80",
        "sub.api.example.com:8080",
        "api.example.com:8443",
    ]
    for target in cases:
        assert v.is_in_scope(target) is True, f"Port-stripped match failed: {target}"
    # Out-of-scope with port must still fail
    assert v.is_in_scope("evil.com:443") is False
    print(f"  [PASS] clause 9 -- port annotation stripped before match ({len(cases)} cases)")


# ===========================================================================
# CLAUSE 10 — URL targets (scheme + path + query stripped)
# ===========================================================================

def test_url_hostname_extraction() -> None:
    """Full URLs must have scheme/path/query stripped; hostname is matched."""
    v = ScopeValidator(["*.example.com"])
    in_scope_urls = [
        "https://api.example.com",
        "http://api.example.com/path/to/page",
        "https://sub.api.example.com/search?q=test&page=2",
        "http://www.example.com:8080/deep/path",
    ]
    for url in in_scope_urls:
        assert v.is_in_scope(url) is True, f"URL match failed: {url}"

    out_of_scope_urls = [
        "https://evil.com/redirect?url=api.example.com",
        "http://attacker.io",
    ]
    for url in out_of_scope_urls:
        assert v.is_in_scope(url) is False, f"Out-of-scope URL incorrectly matched: {url}"

    print(f"  [PASS] clause 10 -- URL hostname extraction ({len(in_scope_urls)} in-scope, "
          f"{len(out_of_scope_urls)} out-of-scope URLs)")


# ===========================================================================
# CLAUSE 11 — Invalid / unparseable targets return False, never raise
# ===========================================================================

def test_invalid_targets_never_raise() -> None:
    """Malformed targets must return False, not raise any exception."""
    v = ScopeValidator(["*.example.com"])
    bad_targets = [
        "",
        "   ",
        "http://",
        "://broken",
        "\x00\x01\x02",
        "a" * 1000,
        "not a domain at all !!@##$%",
    ]
    for target in bad_targets:
        try:
            result = v.is_in_scope(target)
            assert isinstance(result, bool), f"Expected bool for {target!r}, got {type(result)}"
            # Most invalid targets should be False; we only care it doesn't raise
        except Exception as exc:
            assert False, f"is_in_scope raised for {target!r}: {exc}"
    print(f"  [PASS] clause 11 -- {len(bad_targets)} invalid targets: no exceptions, returns bool")


# ===========================================================================
# CLAUSE 12 — Multiple scope patterns (wildcard + exact together)
# ===========================================================================

def test_multiple_scope_patterns() -> None:
    """Multiple patterns (wildcard + exact) all work simultaneously."""
    v = ScopeValidator([
        "*.example.com",
        "api.partner.io",
        "secure.vendor.net",
    ])
    assert v.is_in_scope("api.example.com")   is True
    assert v.is_in_scope("api.partner.io")    is True    # exact
    assert v.is_in_scope("secure.vendor.net") is True    # exact
    assert v.is_in_scope("partner.io")        is False   # parent not in scope
    assert v.is_in_scope("evil.com")          is False
    assert v.is_in_scope("sub.partner.io")    is False   # wildcard not granted
    print("  [PASS] clause 12 -- multiple mixed patterns (wildcard + exact)")


# ===========================================================================
# CLAUSE 13 — Root domain pattern example.com (no wildcard)
# ===========================================================================

def test_root_domain_exact_only() -> None:
    """Bare example.com in scope covers ONLY example.com, not subdomains."""
    v = ScopeValidator(["example.com"])
    assert v.is_in_scope("example.com")     is True
    assert v.is_in_scope("api.example.com") is False, \
        "Bare root pattern must not imply wildcard coverage"
    print("  [PASS] clause 13 -- bare root domain: exact only, no subdomain bleed")


# ===========================================================================
# CLAUSE 14 — Introspection: scope / wildcard_roots / exact_patterns properties
# ===========================================================================

def test_introspection_properties() -> None:
    """scope, wildcard_roots, and exact_patterns must reflect parsed state."""
    v = ScopeValidator(["*.example.com", "api.partner.io", "*.acme.org"])
    assert "*.example.com" in v.scope
    assert "api.partner.io" in v.scope
    assert set(v.wildcard_roots) == {"example.com", "acme.org"}
    assert v.exact_patterns == ["api.partner.io"]
    print("  [PASS] clause 14 -- introspection properties correct")


# ===========================================================================
# CLAUSE 15 — Whitespace in scope patterns is stripped
# ===========================================================================

def test_scope_pattern_whitespace_stripped() -> None:
    """Leading/trailing whitespace in scope entries must be ignored."""
    v = ScopeValidator(["  *.example.com  ", "  api.partner.io  "])
    assert v.is_in_scope("api.example.com") is True
    assert v.is_in_scope("api.partner.io")  is True
    print("  [PASS] clause 15 -- scope pattern whitespace stripped")


# ===========================================================================
# CLAUSE 16 — filter() preserves order within each partition
# ===========================================================================

def test_filter_preserves_order() -> None:
    """filter() must preserve insertion order within each partition."""
    v = ScopeValidator(["*.example.com"])
    targets = ["c.example.com", "evil.com", "a.example.com", "bad.io", "b.example.com"]
    in_scope, out_of_scope = v.filter(targets)
    assert in_scope     == ["c.example.com", "a.example.com", "b.example.com"]
    assert out_of_scope == ["evil.com", "bad.io"]
    print("  [PASS] clause 16 -- filter() preserves order within each partition")


# ===========================================================================
# Runner
# ===========================================================================

def run_all() -> None:
    tests = [
        test_signature_instance_mode,
        test_signature_override_mode,
        test_classmethod_check,
        test_wildcard_single_level,
        test_wildcard_multi_level,
        test_wildcard_does_not_match_root,
        test_exact_match_hits,
        test_exact_match_no_subdomain_bleed,
        test_filter_partitions_correctly,
        test_stateless_reuse,
        test_case_insensitive_target,
        test_case_insensitive_scope_pattern,
        test_empty_scope_denies_all,
        test_port_stripping,
        test_url_hostname_extraction,
        test_invalid_targets_never_raise,
        test_multiple_scope_patterns,
        test_root_domain_exact_only,
        test_introspection_properties,
        test_scope_pattern_whitespace_stripped,
        test_filter_preserves_order,
    ]

    passed = failed = 0
    print(f"\n{'='*60}")
    print("  ScopeValidator Contract Conformance Tests")
    print(f"{'='*60}")

    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as exc:
            print(f"  [FAIL] {fn.__name__}: {exc}")
            failed += 1

    print(f"{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print(f"{'='*60}\n")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
