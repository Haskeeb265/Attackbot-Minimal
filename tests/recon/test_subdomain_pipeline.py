"""
Hermetic tests for the subdomain_domain_wildcards recon pipeline.

Covers the pure, deterministic parts — no external binaries and no Neo4j
required (parsing, normalization, scope filtering, tool discovery). The graph
write path is exercised separately against a real Neo4j by
``tests/recon/test_repository.py``.

Follows the PASS/FAIL + exit-code style of test_repository.py.

Usage:
    python tests/recon/test_subdomain_pipeline.py
"""

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE = _ROOT / "service" / "recon-pipeline" / "asset_pipelines" / "subdomain_domain_wildcards"


def _load(name: str, path: Path):
    """Load a module by file path (the pipeline folder has a hyphen and is not
    importable as a dotted package)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


main = _load("sdw_main", _PIPELINE / "main.py")
# The tool files and main.py all import the canonical module named "base"
# (via their own sys.path shim). Reference that same module object here so
# isinstance() checks compare against the identical SubdomainTool class.
base = sys.modules["base"]

PASS = []
FAIL = []


def check(label, condition, detail=""):
    if condition:
        PASS.append(label)
        print(f"  [PASS] {label}")
    else:
        FAIL.append(label)
        print(f"  [FAIL] {label}  {detail}")


def test_normalize():
    print("\n--- normalize_host ---")
    n = base.normalize_host
    check("plain host", n("Sub.Example.COM") == "sub.example.com")
    check("wildcard stripped", n("*.example.com") == "example.com")
    check("scheme + port + path stripped", n("https://api.example.com:443/v1") == "api.example.com")
    check("trailing dot stripped", n("host.example.com.") == "host.example.com")
    check("userinfo stripped", n("user@host.example.com") == "host.example.com")
    check("no-dot rejected", n("localhost") is None)
    check("empty rejected", n("") is None)
    check("junk rejected", n("--> a_record") is None)


def test_scope():
    print("\n--- in_scope ---")
    s = base.in_scope
    check("apex in scope", s("example.com", "example.com"))
    check("subdomain in scope", s("a.b.example.com", "example.com"))
    check("sibling domain out of scope", not s("example.com.evil.com", "example.com"))
    check("unrelated out of scope", not s("other.org", "example.com"))


def _tool(category, name):
    tools = main.discover_tools()
    for t in tools[category]:
        if t.name == name:
            return t
    return None


def test_discovery():
    print("\n--- discover_tools ---")
    tools = main.discover_tools()
    names = {c: sorted(t.name for t in ts) for c, ts in tools.items()}
    check("5 passive tools", len(tools["passive"]) == 5, detail=str(names["passive"]))
    check("passive set", set(names["passive"]) == {"amass", "assetfinder", "chaos", "findomain", "subfinder"},
          detail=str(names["passive"]))
    check("5 active tools", len(tools["active"]) == 5, detail=str(names["active"]))
    check("active set", set(names["active"]) == {"amass-active", "dnsx", "massdns", "puredns", "shuffledns"},
          detail=str(names["active"]))
    check("2 permutation tools", len(tools["permutation"]) == 2, detail=str(names["permutation"]))
    check("permutation set", set(names["permutation"]) == {"dnsgen", "gotator"}, detail=str(names["permutation"]))
    check("every tool is a SubdomainTool with a binary",
          all(isinstance(t, base.SubdomainTool) and t.binary
              for ts in tools.values() for t in ts))


def test_parsers():
    print("\n--- tool parsers ---")

    sub = _tool("passive", "subfinder")
    out = sub.parse("a.example.com\nb.example.com\nnot-in-scope.org\n\n", "example.com")
    check("subfinder parse + scope filter", out == {"a.example.com", "b.example.com"}, detail=str(out))

    am = _tool("passive", "amass")
    relations = (
        "sub.example.com (FQDN) --> a_record --> 1.2.3.4 (IPAddress)\n"
        "api.example.com (FQDN) --> cname_record --> cdn.other.com (FQDN)\n"
        "example.com (FQDN) --> ns_record --> ns1.example.com (FQDN)\n"
    )
    out = am.parse(relations, "example.com")
    check("amass parses in-scope FQDNs from relations",
          {"sub.example.com", "api.example.com", "example.com", "ns1.example.com"} <= out, detail=str(out))
    check("amass excludes out-of-scope host", "cdn.other.com" not in out, detail=str(out))

    dnsx = _tool("active", "dnsx")
    dnsx.resolutions = {}
    jsonl = (
        '{"host":"a.example.com","a":["1.2.3.4","5.6.7.8"]}\n'
        '{"host":"b.example.com","a":["9.9.9.9"]}\n'
        'not json\n'
        '{"host":"evil.org","a":["6.6.6.6"]}\n'
    )
    out = dnsx.parse(jsonl, "example.com")
    check("dnsx keeps in-scope resolving hosts", out == {"a.example.com", "b.example.com"}, detail=str(out))
    check("dnsx captures A records", dnsx.resolutions.get("a.example.com") == ["1.2.3.4", "5.6.7.8"],
          detail=str(dnsx.resolutions))
    check("dnsx drops out-of-scope host", "evil.org" not in out, detail=str(out))

    massdns = _tool("active", "massdns")
    massdns.resolutions = {}
    simple = "a.example.com. A 1.2.3.4\nb.example.com. A 9.9.9.9\ngarbage line\n"
    out = massdns.parse(simple, "example.com")
    check("massdns parses simple output", out == {"a.example.com", "b.example.com"}, detail=str(out))
    check("massdns captures A record", massdns.resolutions.get("a.example.com") == ["1.2.3.4"],
          detail=str(massdns.resolutions))


def test_commands():
    print("\n--- command construction ---")
    sub = _tool("passive", "subfinder")
    check("subfinder command", sub.command(target="example.com") == ["subfinder", "-d", "example.com", "-silent"],
          detail=str(sub.command(target="example.com")))
    chaos = _tool("passive", "chaos")
    check("chaos gated on PDCP_API_KEY", chaos.api_key_env == "PDCP_API_KEY")
    got = _tool("permutation", "gotator")
    cmd = got.command(infile="/tmp/hosts.txt")
    check("gotator reuses infile for -sub and -perm",
          cmd[:5] == ["gotator", "-sub", "/tmp/hosts.txt", "-perm", "/tmp/hosts.txt"], detail=str(cmd))
    dnsgen = _tool("permutation", "dnsgen")
    check("dnsgen reads stdin", dnsgen.input_mode == "stdin" and dnsgen.command() == ["dnsgen", "-"])


def main_run():
    test_normalize()
    test_scope()
    test_discovery()
    test_parsers()
    test_commands()

    print(f"\n=== RESULTS: {len(PASS)} passed, {len(FAIL)} failed ===")
    if FAIL:
        print("Failed checks:")
        for f in FAIL:
            print(f"  - {f}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main_run()
