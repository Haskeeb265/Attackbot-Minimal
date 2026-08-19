"""
Candidate node produced by extraction (IMPLEMENTATION_PLAN.md Stage 3).

A :class:`Candidate` is the normalized, canonical unit that flows from
extraction (S3) into scoring (S2) and the graph write (S1). It carries exactly
what a ``merge_node`` call needs — the multi-label set (base ``Asset`` first, per
graph_crud_contract.md), the ``(asset_type, canonical_value)`` identity, a
confidence, and free-form ``meta`` for type-specific properties.

Pure data — no infra imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# asset_type identity strings (match schema.py typed labels, lowercased).
TYPE_DOMAIN = "domain"
TYPE_WILDCARD = "wildcard"
TYPE_URL = "url"
TYPE_ENDPOINT = "endpoint"
TYPE_IP = "ip"
TYPE_SECRET = "secret"
TYPE_CLOUD_RESOURCE = "cloud_resource"
TYPE_CERTIFICATE = "certificate"

# asset_type -> graph label set (base :Asset first — graph_crud_contract.md).
_LABELS: Dict[str, List[str]] = {
    TYPE_DOMAIN:         ["Asset", "Domain"],
    TYPE_WILDCARD:       ["Asset", "Wildcard"],
    TYPE_URL:            ["Asset", "URL"],
    TYPE_ENDPOINT:       ["Asset", "Endpoint"],
    TYPE_IP:             ["Asset", "IP"],
    TYPE_SECRET:         ["Asset", "Secret"],
    TYPE_CLOUD_RESOURCE: ["Asset", "CloudResource"],
    TYPE_CERTIFICATE:    ["Asset", "Certificate"],
}


@dataclass(frozen=True)
class Candidate:
    """A canonical candidate node ready for scoring + graph write."""

    asset_type: str
    canonical_value: str
    confidence: float = 1.0
    meta: Dict[str, object] = field(default_factory=dict)

    @property
    def labels(self) -> List[str]:
        """Multi-label set for merge_node (base :Asset first)."""
        return list(_LABELS.get(self.asset_type, ["Asset", "Other"]))

    @property
    def identity(self) -> Dict[str, str]:
        """The ``(asset_type, canonical_value)`` identity props for merge_node."""
        return {"asset_type": self.asset_type, "canonical_value": self.canonical_value}

    def key(self) -> tuple:
        return (self.asset_type, self.canonical_value)


def dedupe(candidates: List[Candidate]) -> List[Candidate]:
    """Collapse candidates sharing an identity, keeping the highest confidence.

    Preserves first-seen order. meta from the highest-confidence occurrence
    wins; ties keep the earlier one.
    """
    best: Dict[tuple, Candidate] = {}
    order: List[tuple] = []
    for c in candidates:
        k = c.key()
        if k not in best:
            best[k] = c
            order.append(k)
        elif c.confidence > best[k].confidence:
            best[k] = c
    return [best[k] for k in order]
