"""
Neo4j graph schema for the Attackbot_v2 recon pipeline (Stage 1).

The graph is the *system of record* for all recon findings (recon.md §6).
This module is the Python home of the schema proposed in the design review and
stands in for the plan's suggested `graph/schema.cypher` file
(IMPLEMENTATION_PLAN.md Stage 1 — "Schema definition mechanism"). The
constraints/indexes below are idempotent Cypher (`CREATE ... IF NOT EXISTS`)
and can be applied at the start of any run or by a test fixture via
:func:`apply_schema`.

Design decisions (each traced to evidence):

* **Multi-label nodes.** Every asset carries the base `:Asset` label *plus* a
  typed label (`:Domain`, `:IP`, `:URL`, ...). The base label keeps cross-type
  queries uniform ("all assets related to org X"); the typed labels give
  type-specific indexes.  (IMPLEMENTATION_PLAN.md Stage 1; recon.md §6)
* **Canonical identity.** Every write is an idempotent `MERGE` keyed on
  `(asset_type, canonical_value)` where `canonical_value` is the S3-normalized
  value (lowercase, punycode, trailing-dot strip, IP canonicalization).
  (IMPLEMENTATION_PLAN.md §4.4 + Stage 1 + Stage 3)
* **Organization anchor.** `(:Organization {handle})` is the anchor all seeds
  `BELONGS_TO`; cross-program correlation (`RELATED_TO`) is a later refinement.
  (IMPLEMENTATION_PLAN.md Stage 4)
* **Provenance on edges, not nodes.** Every edge carries
  `(source, tool, observed_at, confidence)` plus an optional `signal` for
  evidence-bearing edges (maps to the recon.md §7 scoring signal table).
  (recon.md §6; IMPLEMENTATION_PLAN.md Stage 1)
* **Scoring state as indexed properties.** `score`, `state`, `state_changed_at`
  live on the node for fast tier queries (recon.md §7 thresholds);
  `score_audit` is a serialized snapshot of the S2 ScoreAudit, kept for run-end
  explainability (why a node scored as it did) and optional later replay.
  (IMPLEMENTATION_PLAN.md Stages 2, 7)
* **No redundant indexes.** `:Asset(asset_type)` alone would duplicate the
  leftmost prefix of the composite identity constraint, and `:Organization(handle)`
  is backed by its unique constraint — both omitted per the scope.md §4.7
  leftmost-prefix lesson applied to Neo4j.
* **Mode: one-shot (v1).** The pipeline runs to completion per invocation —
  recursion, scoring, and graph writes all happen *during* the run, and scores
  freeze at observation time. The plan's continuous machinery (S8 Redis cache,
  S9 workers, S11 background decay/pruning, S14 differential monitoring) is
  deferred. The schema is deliberately mode-agnostic: MERGE identity makes
  re-runs safe, and the deferred stages can be layered back on with no schema
  migration.

> **NOTE (resolved):** the CRUD in ``repository.py``
> (``merge_node``/``get_node``/``merge_relation``/``get_relation``) accepts a
> **list** of labels (``labels: Sequence[str]``) and emits multi-label nodes
> like ``(:Asset:Domain)``. Write real assets with ``labels=["Asset", "Domain"]``
> (base label first) so the ``:Asset`` identity constraint below is exercised by
> every write; ``tests/recon/test_repository.py`` asserts the constraint rejects
> duplicate ``(asset_type, canonical_value)`` pairs.

v1 core graph:

    (:Organization {handle})
            ▲
            │ BELONGS_TO
            │
    (:Asset:Domain) ──RESOLVES_TO──► (:Asset:IP)
            │
            │ HAS_CERTIFICATE
            ▼
    (:Asset:Certificate)

    (:Asset:URL) ──DERIVED_FROM──► (:Asset:Domain)   (host pivot of URL scope)
            │
            │ POINTS_TO
            ▼
    (:Asset:Endpoint)

    (:Asset:Secret) ──EXTRACTED_FROM──► (:Repository | :Binary | :MobileApp)

Sources: docs/recon_docs/recon.md · docs/recon_docs/IMPLEMENTATION_PLAN.md ·
docs/codebase/CONVENTIONS.md · scope.md §4.7/§6.3
"""

import logging
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node labels
# ---------------------------------------------------------------------------
LABEL_ORGANIZATION = "Organization"
LABEL_ASSET = "Asset"

# v1 asset type labels (IMPLEMENTATION_PLAN.md Stage 1 + Stage 4)
LABEL_DOMAIN = "Domain"
LABEL_WILDCARD = "Wildcard"
LABEL_URL = "URL"
LABEL_IP = "IP"
LABEL_CIDR = "CIDR"
LABEL_ENDPOINT = "Endpoint"
LABEL_CERTIFICATE = "Certificate"
LABEL_SECRET = "Secret"
LABEL_ASN = "ASN"

# Post-v1 asset labels (recon.md §3 taxonomy; added as pipelines arrive per
# Stage 1 "add the rest as pipelines arrive").
LABEL_REPOSITORY = "Repository"
LABEL_BINARY = "Binary"
LABEL_MOBILE_APP = "MobileApp"
LABEL_SMART_CONTRACT = "SmartContract"
LABEL_TECHNOLOGY = "Technology"
LABEL_CLOUD_RESOURCE = "CloudResource"
# Optional refinement: discovered subdomains could carry :Subdomain in addition
# to :Domain once the Domain pipeline is mature. v1 stores them as :Domain.
LABEL_SUBDOMAIN = "Subdomain"


# ---------------------------------------------------------------------------
# Relationship types
# ---------------------------------------------------------------------------
# v1 set — the handful the first pipelines need (Stage 1).
REL_BELONGS_TO = "BELONGS_TO"             # (Asset)->(Organization)  seed ownership
REL_DERIVED_FROM = "DERIVED_FROM"         # (URL)->(Domain)          host pivot
REL_RESOLVES_TO = "RESOLVES_TO"           # (Domain)->(IP)           DNS resolution
REL_HAS_CERTIFICATE = "HAS_CERTIFICATE"   # (Domain)->(Certificate)  TLS cert observed
REL_EXTRACTED_FROM = "EXTRACTED_FROM"     # (Asset)->(Repository|Binary|MobileApp)
REL_FOUND_IN = "FOUND_IN"                 # (Asset)->(Asset)         correlated occurrence
REL_POINTS_TO = "POINTS_TO"               # (URL|Endpoint)->(Domain) target host

# Later additions (recon.md §6; added as their pipelines arrive).
REL_ISSUED_FOR = "ISSUED_FOR"
REL_SHARES_CERTIFICATE_WITH = "SHARES_CERTIFICATE_WITH"
REL_BELONGS_TO_ASN = "BELONGS_TO_ASN"
REL_OWNED_BY = "OWNED_BY"
REL_RELATED_TO = "RELATED_TO"
REL_USES_TECHNOLOGY = "USES_TECHNOLOGY"
REL_HOSTS = "HOSTS"


# ---------------------------------------------------------------------------
# Asset node properties
# ---------------------------------------------------------------------------
# Identity — the canonical unique key (Stage 1 / Stage 3).
PROP_ASSET_TYPE = "asset_type"
PROP_CANONICAL_VALUE = "canonical_value"

# Lifecycle / scoring (recon.md §7; Stage 7).
PROP_STATE = "state"
PROP_SCORE = "score"
PROP_STATE_CHANGED_AT = "state_changed_at"
PROP_FIRST_SEEN_AT = "first_seen_at"
PROP_LAST_SEEN_AT = "last_seen_at"

# Evidence / idempotency (recon.md §5.3 content hash; Stage 7 audit).
PROP_CONTENT_HASH = "content_hash"
PROP_SCORE_AUDIT = "score_audit"          # serialized S2 ScoreAudit snapshot (run-end explainability)

# HackerOne seed extras (Stage 4; scope.md §6.3: keep ineligible scopes).
PROP_ELIGIBLE_FOR_BOUNTY = "eligible_for_bounty"
PROP_SEVERITY = "severity"                # from scope max_severity

# Organization anchor properties.
PROP_HANDLE = "handle"
PROP_NAME = "name"

# Edge provenance (recon.md §6; Stage 1) — present on EVERY relationship.
PROP_SOURCE = "source"
PROP_TOOL = "tool"
PROP_OBSERVED_AT = "observed_at"
PROP_CONFIDENCE = "confidence"
# Optional evidence marker on scoring-relevant edges — the signal_type used by
# the S2 signal table (recon.md §7: weight / half-life / confidence).
PROP_SIGNAL = "signal"


# ---------------------------------------------------------------------------
# Node lifecycle states (recon.md §7 thresholds)
# ---------------------------------------------------------------------------
STATE_ACTIVE = "ACTIVE"   # score >= 75  -> eligible for full recursive probing
STATE_WARM = "WARM"       # 40 <= score < 75 -> stored, low-priority (no background refresh)
STATE_COLD = "COLD"       # score < 40   -> quarantined, correlation only


# ---------------------------------------------------------------------------
# Idempotent schema DDL (Stage 1: no Alembic for Neo4j; applied at the start
# of each run and by a test fixture via apply_schema).
# ---------------------------------------------------------------------------
SCHEMA_STATEMENTS: List[str] = [
    # Canonical identity — the idempotency backbone (plan §4.4 + Stage 1).
    # MERGE relies on this uniqueness for effectively-once writes.
    (
        "CREATE CONSTRAINT asset_identity_unique IF NOT EXISTS "
        "FOR (a:Asset) REQUIRE (a.asset_type, a.canonical_value) IS UNIQUE"
    ),

    # Organization anchor (Stage 4). The unique constraint also backs
    # handle lookups, so a standalone :Organization(handle) index would be
    # redundant (scope.md §4.7).
    (
        "CREATE CONSTRAINT org_handle_unique IF NOT EXISTS "
        "FOR (o:Organization) REQUIRE o.handle IS UNIQUE"
    ),

    # Hot lookup by canonical_value ALONE — not covered by the composite
    # identity constraint (asset_type is its leftmost prefix, so a standalone
    # :Asset(asset_type) index IS redundant; this one is not).
    (
        "CREATE INDEX asset_canonical_idx IF NOT EXISTS "
        "FOR (a:Asset) ON (a.canonical_value)"
    ),

    # State / score tier queries (recon.md §7) — run-end reporting of hot assets;
    # no background pruning sweep in one-shot mode.
    (
        "CREATE INDEX asset_state_idx IF NOT EXISTS "
        "FOR (a:Asset) ON (a.state)"
    ),
    (
        "CREATE INDEX asset_score_idx IF NOT EXISTS "
        "FOR (a:Asset) ON (a.score)"
    ),

    # Provenance / re-run safety lookups; decay sweeps are N/A in one-shot mode.
    (
        "CREATE INDEX asset_last_seen_idx IF NOT EXISTS "
        "FOR (a:Asset) ON (a.last_seen_at)"
    ),

    # In-run evidence dedup + safe re-runs (recon.md §5.3 content hash).
    (
        "CREATE INDEX asset_content_hash_idx IF NOT EXISTS "
        "FOR (a:Asset) ON (a.content_hash)"
    ),
]


class SchemaRunner(Protocol):
    """Minimal structural type for anything that can execute Cypher."""

    def run_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher statement and return records as dicts."""
        ...


def apply_schema(repo: SchemaRunner) -> None:
    """Apply all schema statements idempotently (Stage 1).

    Call at the start of each run (before CRUD) or from a test fixture. Every
    statement uses ``IF NOT EXISTS`` so repeated application — including
    re-runs against an already-initialized graph — is a no-op. Neo4j schema DDL
    runs in its own auto-commit transaction, so no explicit transaction is
    needed.
    """
    for statement in SCHEMA_STATEMENTS:
        repo.run_query(statement)
    logger.info("Applied %d Neo4j schema statements", len(SCHEMA_STATEMENTS))
