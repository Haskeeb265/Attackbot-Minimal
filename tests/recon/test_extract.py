"""
Hermetic tests for extraction + normalization (recon.md 5.3 /
IMPLEMENTATION_PLAN Stage 3). Pure functions + fixtures — no network, no infra.
Follows the PASS/FAIL + exit-code style of test_repository.py.

Usage:
    python tests/recon/test_extract.py
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_EXTRACT_DIR = _ROOT / "service" / "recon-pipeline" / "extract"
sys.path.insert(0, str(_EXTRACT_DIR))

import normalize  # noqa: E402
import extractors  # noqa: E402
import candidate  # noqa: E402
from candidate import (  # noqa: E402
    TYPE_CLOUD_RESOURCE, TYPE_DOMAIN, TYPE_ENDPOINT, TYPE_IP, TYPE_SECRET,
    TYPE_URL, TYPE_WILDCARD, Candidate,
)

PASS = []
FAIL = []


def check(label, condition, detail=""):
    if condition:
        PASS.append(label)
        print(f"  [PASS] {label}")
    else:
        FAIL.append(label)
        print(f"  [FAIL] {label}  {detail}")


def values(cands, asset_type):
    return {c.canonical_value for c in cands if c.asset_type == asset_type}


def test_normalize_hostname():
    print("\n--- normalize_hostname ---")
    n = normalize.normalize_hostname
    check("lowercase + trailing dot", n("API.Example.COM.") == "api.example.com")
    check("wildcard base", n("*.Example.com") == "example.com")
    check("scheme + port + path stripped", n("https://host.example.com:443/a/b") == "host.example.com")
    check("userinfo stripped", n("user:pass@host.example.com") == "host.example.com")
    check("single label rejected", n("localhost") is None)
    check("junk rejected", n("not a host") is None)


def test_normalize_ip():
    print("\n--- normalize_ip ---")
    n = normalize.normalize_ip
    check("ipv4 passthrough", n("192.168.1.1") == "192.168.1.1")
    check("ipv4 leading-zero octet rejected", n("192.168.001.1") is None)  # ambiguous octal
    check("ipv6 compressed", n("2001:0db8:0000:0000:0000:0000:0000:0001") == "2001:db8::1")
    check("loopback v6", n("::1") == "::1")
    check("invalid ipv4 rejected", n("999.1.1.1") is None)
    check("not-an-ip rejected", n("example.com") is None)


def test_normalize_url():
    print("\n--- normalize_url ---")
    n = normalize.normalize_url
    check("scheme+host lowercased, default port + fragment stripped, path/query kept",
          n("HTTP://Example.COM:80/Path?a=1#frag") == "http://example.com/Path?a=1",
          detail=n("HTTP://Example.COM:80/Path?a=1#frag"))
    check("https default port stripped", n("https://example.com:443/") == "https://example.com/")
    check("non-default port kept", n("https://example.com:8443/x") == "https://example.com:8443/x")
    check("no host -> None", n("not a url") is None)
    check("url_host pivot", normalize.url_host("https://api.example.com/x") == "api.example.com")
    check("url_endpoint host+path", normalize.url_endpoint("https://api.example.com/v1/login") == "api.example.com/v1/login")


def test_registrable_and_hash():
    print("\n--- registrable_domain + content_hash ---")
    r = normalize.registrable_domain
    check("plain apex", r("api.example.com") == "example.com", detail=r("api.example.com"))
    check("multi-label ccTLD", r("a.b.co.uk") == "b.co.uk", detail=r("a.b.co.uk"))
    check("hosted zone (github.io)", r("foo.github.io") == "foo.github.io", detail=r("foo.github.io"))
    check("deep ccTLD", r("a.b.c.co.uk") == "c.co.uk", detail=r("a.b.c.co.uk"))
    h1 = normalize.content_hash("hello")
    check("content_hash is sha256 hex", len(h1) == 64 and h1 == normalize.content_hash("hello"))
    check("content_hash differs on different input", h1 != normalize.content_hash("hello2"))


def test_extract_hostnames():
    print("\n--- extract_hostnames ---")
    text = "visit foo.example.com and bar.example.org, load jquery.min.js and logo.png plus 1.2.3.4"
    out = extractors.extract_hostnames(text)
    got = values(out, TYPE_DOMAIN)
    check("real hostnames extracted", {"foo.example.com", "bar.example.org"} <= got, detail=str(got))
    check("file-extension pseudo-hosts rejected", "jquery.min.js" not in got and "logo.png" not in got, detail=str(got))
    check("bare IPv4 not treated as hostname", "1.2.3.4" not in got, detail=str(got))


def test_extract_ips():
    print("\n--- extract_ips ---")
    out = extractors.extract_ips("hosts: 1.2.3.4, 999.1.1.1, ::1, 2001:db8::1")
    got = values(out, TYPE_IP)
    check("valid v4 kept", "1.2.3.4" in got, detail=str(got))
    check("invalid v4 dropped", "999.1.1.1" not in got, detail=str(got))
    check("v6 canonicalized", {"::1", "2001:db8::1"} <= got, detail=str(got))


def test_extract_urls():
    print("\n--- extract_urls ---")
    out = extractors.extract_urls("see https://Example.com:443/api/v1?x=1#f and http://test.example.com/")
    urls = values(out, TYPE_URL)
    domains = values(out, TYPE_DOMAIN)
    endpoints = values(out, TYPE_ENDPOINT)
    check("url canonicalized", "https://example.com/api/v1?x=1" in urls, detail=str(urls))
    check("host Domain derived", {"example.com", "test.example.com"} <= domains, detail=str(domains))
    check("endpoint (host+path) emitted", "example.com/api/v1" in endpoints, detail=str(endpoints))
    check("bare-host '/' endpoint skipped", "test.example.com/" not in endpoints, detail=str(endpoints))


def test_extract_cert_sans():
    print("\n--- extract_cert_sans ---")
    out = extractors.extract_cert_sans(["*.example.com", "API.example.com.", "example.com"])
    check("wildcard -> Wildcard type", "example.com" in values(out, TYPE_WILDCARD), detail=str(values(out, TYPE_WILDCARD)))
    check("plain SANs -> Domain", {"api.example.com", "example.com"} <= values(out, TYPE_DOMAIN),
          detail=str(values(out, TYPE_DOMAIN)))
    check("high SAN confidence", all(c.confidence >= 0.9 for c in out), detail=str([c.confidence for c in out]))


def test_extract_secrets():
    print("\n--- extract_secrets ---")
    text = (
        'aws_key=AKIAIOSFODNN7EXAMPLE '
        'jwt=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9 '
        'google=AIzaSyA1234567890abcdefghijklmnopqrstuv '
        'api_key="ABCD1234abcd5678wxyz"'
    )
    out = extractors.extract_secrets(text)
    kinds = {c.meta.get("kind") for c in out}
    check("aws + jwt + google + generic detected",
          {"aws_access_key", "jwt", "google_api_key", "generic_api_key"} <= kinds, detail=str(kinds))
    check("secrets are low confidence", all(c.confidence <= 0.3 for c in out))
    check("secrets flagged high_value", all(c.meta.get("high_value") for c in out))
    aws = next(c for c in out if c.meta.get("kind") == "aws_access_key")
    check("identity is hashed, not the raw secret", "AKIAIOSFODNN7EXAMPLE" not in aws.canonical_value,
          detail=aws.canonical_value)
    check("preview is redacted", aws.meta.get("preview") == "AKIA...MPLE", detail=str(aws.meta.get("preview")))


def test_extract_cloud():
    print("\n--- extract_cloud_resources ---")
    text = (
        "https://my-bucket.s3.amazonaws.com/k "
        "https://s3.us-west-2.amazonaws.com/other-bucket/k "
        "s3://cli-bucket "
        "https://storage.googleapis.com/gcs-bucket/o "
        "https://myaccount.blob.core.windows.net/c"
    )
    out = extractors.extract_cloud_resources(text)
    vals = values(out, TYPE_CLOUD_RESOURCE)
    check("s3 virtual-host bucket", "aws_s3:my-bucket" in vals, detail=str(vals))
    check("s3 path-style bucket", "aws_s3:other-bucket" in vals, detail=str(vals))
    check("s3 scheme bucket", "aws_s3:cli-bucket" in vals, detail=str(vals))
    check("gcs bucket", "gcs:gcs-bucket" in vals, detail=str(vals))
    check("azure account", "azure_blob:myaccount" in vals, detail=str(vals))


def test_candidate_contract():
    print("\n--- Candidate graph contract ---")
    c = Candidate(TYPE_DOMAIN, "api.example.com", 0.5)
    check("labels are base-Asset-first", c.labels == ["Asset", "Domain"], detail=str(c.labels))
    check("identity props for merge_node",
          c.identity == {"asset_type": "domain", "canonical_value": "api.example.com"}, detail=str(c.identity))
    check("unknown type falls back to :Other",
          Candidate("mystery", "x.y").labels == ["Asset", "Other"])
    deduped = candidate.dedupe([
        Candidate(TYPE_DOMAIN, "a.example.com", 0.5),
        Candidate(TYPE_DOMAIN, "a.example.com", 0.9),  # higher confidence wins
        Candidate(TYPE_IP, "1.2.3.4", 0.6),
    ])
    check("dedupe collapses by identity", len(deduped) == 2, detail=str(len(deduped)))
    dom = next(c for c in deduped if c.asset_type == TYPE_DOMAIN)
    check("dedupe keeps highest confidence", dom.confidence == 0.9, detail=str(dom.confidence))


def test_extract_all():
    print("\n--- extract_all (mixed artifact) ---")
    text = "https://api.example.com/login connects to 10.0.0.1 and leaks AKIAIOSFODNN7EXAMPLE via https://my-bucket.s3.amazonaws.com/k"
    grouped = extractors.group_by_type(extractors.extract_all(text))
    check("finds url", TYPE_URL in grouped)
    check("finds domain", "api.example.com" in {c.canonical_value for c in grouped.get(TYPE_DOMAIN, [])})
    check("finds ip", "10.0.0.1" in {c.canonical_value for c in grouped.get(TYPE_IP, [])})
    check("finds secret", TYPE_SECRET in grouped)
    check("finds cloud resource", TYPE_CLOUD_RESOURCE in grouped)


def run():
    test_normalize_hostname()
    test_normalize_ip()
    test_normalize_url()
    test_registrable_and_hash()
    test_extract_hostnames()
    test_extract_ips()
    test_extract_urls()
    test_extract_cert_sans()
    test_extract_secrets()
    test_extract_cloud()
    test_candidate_contract()
    test_extract_all()

    print(f"\n=== RESULTS: {len(PASS)} passed, {len(FAIL)} failed ===")
    if FAIL:
        print("Failed checks:")
        for f in FAIL:
            print(f"  - {f}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    run()
