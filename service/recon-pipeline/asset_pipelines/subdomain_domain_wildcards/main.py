"""
Orchestrator for the subdomain / domain / wildcard recon pipeline.

Runs the chain documented in ``commands.txt`` end to end and persists the
findings into the Neo4j graph of record:

    passive enum  ->  merge/dedup  ->  (optional) permutation  ->  resolve  ->  graph

Every tool is a :class:`base.SubdomainTool` living in ``passive/``, ``active/``
or ``permutation/``. They are discovered by scanning those folders and loading
each file by path (the folder is not an importable package — see base.py).

Graph writes follow the Stage-1 CRUD contract (graph/repository.py + schema.py):
each subdomain is an idempotent ``MERGE`` of an ``(:Asset:Domain)`` node keyed on
``(asset_type, canonical_value)``, linked ``BELONGS_TO`` its ``(:Organization)``
and ``RESOLVES_TO`` each resolved ``(:Asset:IP)`` — every edge carrying
``(source, tool, observed_at, confidence)`` provenance.

Meant to run inside ``subdomain_domain_wildcards_image`` (all binaries on PATH).
Neo4j persistence is best-effort: with ``--no-graph``, or if Neo4j is
unreachable, the discovered subdomains are still printed / written to a file.

Usage:
    python main.py example.com
    python main.py example.com --org acme --permute --resolver dnsx
    python main.py example.com --no-graph --output live-subs.txt
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[3]                      # repo root
_GRAPH_DIR = _ROOT / "service" / "recon-pipeline" / "graph"
for _p in (str(_HERE), str(_ROOT), str(_GRAPH_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from base import SubdomainTool  # noqa: E402
from shared.colorlog import log  # noqa: E402

# Active tools that are resolvers (used in the resolve step) rather than
# enumerators. amass-active is an enumerator and only runs under --active.
RESOLVER_NAMES = {"dnsx", "puredns", "massdns", "shuffledns"}
PROVENANCE_SOURCE = "subdomain_domain_wildcards"


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------
def discover_tools() -> Dict[str, List[SubdomainTool]]:
    """Load every tool file under passive/ active/ permutation/ by path.

    Returns a ``{category: [tool, ...]}`` map. Files that don't expose a
    module-level ``TOOL`` are ignored.
    """
    tools: Dict[str, List[SubdomainTool]] = {"passive": [], "active": [], "permutation": []}
    for category in tools:
        folder = _HERE / category
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.py")):
            if path.name == "__init__.py":
                continue
            mod_name = f"sdw_tool_{category}_{path.stem.replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as exc:  # a broken tool file never aborts discovery
                log.warn(f"could not load {path.name}: {exc}")
                continue
            tool = getattr(module, "TOOL", None)
            if isinstance(tool, SubdomainTool):
                tools[category].append(tool)
    return tools


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------
def run_passive(
    tools: List[SubdomainTool],
    domain: str,
    provenance: Dict[str, Set[str]],
    tool_conf: Dict[str, float],
) -> Set[str]:
    subs: Set[str] = set()
    for tool in tools:
        tool_conf[tool.name] = tool.default_confidence
        for host in tool.run(domain=domain):
            subs.add(host)
            provenance.setdefault(host, set()).add(tool.name)
    return subs


def run_permutation(
    tools: List[SubdomainTool],
    hosts: Set[str],
    domain: str,
    provenance: Dict[str, Set[str]],
    tool_conf: Dict[str, float],
) -> Set[str]:
    candidates: Set[str] = set()
    host_list = sorted(hosts)
    for tool in tools:
        tool_conf[tool.name] = tool.default_confidence
        for host in tool.run(domain=domain, hosts=host_list):
            if host not in hosts:
                candidates.add(host)
                provenance.setdefault(host, set()).add(tool.name)
    return candidates


def resolve(
    resolver: Optional[SubdomainTool],
    hosts: Set[str],
    domain: str,
) -> Tuple[Set[str], Dict[str, List[str]]]:
    if resolver is None:
        log.warn("no resolver available - treating all discovered names as unresolved")
        return set(hosts), {}
    live = resolver.run(domain=domain, hosts=sorted(hosts))
    return live, dict(resolver.resolutions)


# ---------------------------------------------------------------------------
# Graph persistence (Stage-1 CRUD contract)
# ---------------------------------------------------------------------------
def persist_graph(
    org: str,
    live: Set[str],
    resolutions: Dict[str, List[str]],
    provenance: Dict[str, Set[str]],
    tool_conf: Dict[str, float],
    resolver_name: str,
) -> bool:
    """Write Organization / Domain / IP nodes + provenance edges. Best-effort:
    returns False (with a warning) if Neo4j is unavailable."""
    try:
        from client import Neo4jClient
        from repository import Neo4jRepository
        from schema import (
            LABEL_ASSET, LABEL_DOMAIN, LABEL_IP, LABEL_ORGANIZATION,
            REL_BELONGS_TO, REL_RESOLVES_TO,
            PROP_ASSET_TYPE, PROP_CANONICAL_VALUE, PROP_CONFIDENCE,
            PROP_FIRST_SEEN_AT, PROP_HANDLE, PROP_LAST_SEEN_AT, PROP_NAME,
            PROP_OBSERVED_AT, PROP_SIGNAL, PROP_SOURCE, PROP_TOOL,
            apply_schema,
        )
    except Exception as exc:
        log.warn(f"graph libraries unavailable ({exc}) - skipping persistence")
        return False

    client = Neo4jClient()
    try:
        client.verify()
    except Exception as exc:
        log.warn(f"Neo4j unreachable ({exc}) - skipping persistence (try: docker compose up -d neo4j)")
        client.close()
        return False

    now = datetime.now(timezone.utc).isoformat()
    repo = Neo4jRepository(client)
    try:
        apply_schema(repo)
        repo.merge_node([LABEL_ORGANIZATION], {PROP_HANDLE: org}, {PROP_NAME: org})

        for host in sorted(live):
            tools = sorted(provenance.get(host, set())) or ["unknown"]
            confidence = max((tool_conf.get(t, 0.5) for t in tools), default=0.5)

            repo.merge_node(
                [LABEL_ASSET, LABEL_DOMAIN],
                {PROP_ASSET_TYPE: "domain", PROP_CANONICAL_VALUE: host},
                {PROP_FIRST_SEEN_AT: now, PROP_LAST_SEEN_AT: now, "sources": tools},
            )
            repo.merge_relation(
                [LABEL_ASSET, LABEL_DOMAIN], {PROP_CANONICAL_VALUE: host},
                REL_BELONGS_TO,
                [LABEL_ORGANIZATION], {PROP_HANDLE: org},
                {
                    PROP_SOURCE: PROVENANCE_SOURCE,
                    PROP_TOOL: ",".join(tools),
                    PROP_OBSERVED_AT: now,
                    PROP_CONFIDENCE: confidence,
                },
            )

            for ip in resolutions.get(host, []):
                repo.merge_node(
                    [LABEL_ASSET, LABEL_IP],
                    {PROP_ASSET_TYPE: "ip", PROP_CANONICAL_VALUE: ip},
                    {PROP_FIRST_SEEN_AT: now, PROP_LAST_SEEN_AT: now},
                )
                repo.merge_relation(
                    [LABEL_ASSET, LABEL_DOMAIN], {PROP_CANONICAL_VALUE: host},
                    REL_RESOLVES_TO,
                    [LABEL_ASSET, LABEL_IP], {PROP_CANONICAL_VALUE: ip},
                    {
                        PROP_SOURCE: PROVENANCE_SOURCE,
                        PROP_TOOL: resolver_name,
                        PROP_OBSERVED_AT: now,
                        PROP_CONFIDENCE: 0.9,
                        PROP_SIGNAL: "dns_resolution",
                    },
                )
        log.success(f"graph: wrote {len(live)} domains under organization '{org}'")
        return True
    except Exception as exc:
        log.failed(f"graph write failed: {exc}")
        return False
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Subdomain/domain/wildcard recon pipeline")
    parser.add_argument("domain", help="root domain to enumerate (e.g. example.com)")
    parser.add_argument("--org", help="organization handle to anchor findings under (default: the domain)")
    parser.add_argument("--permute", action="store_true", help="expand results with dnsgen/gotator before resolving")
    parser.add_argument("--active", action="store_true", help="also run active enumerators (amass -active)")
    parser.add_argument("--resolver", choices=sorted(RESOLVER_NAMES), default="dnsx", help="resolver used to keep live names (default: dnsx)")
    parser.add_argument("--no-resolve", action="store_true", help="skip resolution; keep every discovered name")
    parser.add_argument("--no-graph", action="store_true", help="do not write to Neo4j")
    parser.add_argument("--output", help="write the final live subdomain list to this file")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    domain = args.domain.strip().lower().rstrip(".")
    org = args.org or domain

    tools = discover_tools()
    provenance: Dict[str, Set[str]] = {}
    tool_conf: Dict[str, float] = {}

    log.info(f"target: {domain}  |  org: {org}")
    log.process("stage: passive enumeration")
    subs = run_passive(tools["passive"], domain, provenance, tool_conf)

    if args.active:
        log.process("stage: active enumeration")
        enumerators = [t for t in tools["active"] if t.name not in RESOLVER_NAMES]
        for tool in enumerators:
            tool_conf[tool.name] = tool.default_confidence
            for host in tool.run(domain=domain):
                subs.add(host)
                provenance.setdefault(host, set()).add(tool.name)

    subs.add(domain)  # the root is always in scope
    log.success(f"discovered {len(subs)} unique names (passive + active)")

    if args.permute:
        log.process("stage: permutation")
        new = run_permutation(tools["permutation"], subs, domain, provenance, tool_conf)
        subs |= new
        log.success(f"permutation added {len(new)} candidates ({len(subs)} total)")

    if args.no_resolve:
        live, resolutions = set(subs), {}
        log.info("resolution skipped (--no-resolve)")
    else:
        log.process(f"stage: resolution ({args.resolver})")
        resolver = next((t for t in tools["active"] if t.name == args.resolver), None)
        live, resolutions = resolve(resolver, subs, domain)
        log.success(f"{len(live)} names resolve live")

    for host in sorted(live):
        print(host)

    if args.output:
        Path(args.output).write_text("\n".join(sorted(live)) + "\n", encoding="utf-8")
        log.success(f"wrote {len(live)} names to {args.output}")

    if not args.no_graph:
        log.process("stage: graph persistence")
        persist_graph(org, live, resolutions, provenance, tool_conf, args.resolver)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
