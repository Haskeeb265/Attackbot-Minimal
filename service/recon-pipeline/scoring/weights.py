"""
Scoring weights, half-lives, penalties and thresholds (recon.md 7).

The spec's tables live here as plain dicts (IMPLEMENTATION_PLAN.md Stage 2:
"weights as code constants ... with an optional env override for tuning").
Everything is pure data — no infra, no I/O — so the engine that consumes it
(engine.py) stays unit-testable with zero dependencies.

Env overrides (optional, off by default so tests stay deterministic):
    RECON_SCORE_W_<signal>   overrides a positive-signal base weight
    RECON_SCORE_H_<signal>   overrides a positive-signal half-life (days)
    RECON_SCORE_P_<penalty>  overrides a penalty weight
e.g. RECON_SCORE_W_exact_match=90
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Positive signal identifiers (recon.md 7 "Positive Signals")
# ---------------------------------------------------------------------------
SIG_EXACT_MATCH = "exact_match"                       # exact subdomain / registrable domain match
SIG_ASN_CIDR_OWNERSHIP = "asn_cidr_ownership"         # current ASN / CIDR ownership
SIG_INSCOPE_EXTRACTION = "inscope_binary_or_source"   # extracted from in-scope binary / source
SIG_SAN_COOCCURRENCE = "san_cooccurrence"             # SAN of a cert that also covers the seed
SIG_REVERSE_WHOIS = "reverse_whois_match"             # reverse WHOIS exact org / email match
SIG_HISTORICAL_DNS = "historical_dns_dedicated_ip"    # historical DNS to dedicated (non-CDN) in-scope IP
SIG_BRAND_PROXIMITY = "brand_proximity"               # strong brand / string proximity in hostname
SIG_SHARES_NONCDN_IP = "shares_noncdn_ip"             # shares non-CDN IP with a high-confidence asset
SIG_WEAK_NAMING = "weak_naming_similarity"            # weak naming similarity only

# base weight, half-life in days (None == infinite / no decay)
_POSITIVE_SIGNALS_DEFAULT: Dict[str, Tuple[float, Optional[float]]] = {
    SIG_EXACT_MATCH:        (100.0, None),
    SIG_ASN_CIDR_OWNERSHIP: (100.0, None),
    SIG_INSCOPE_EXTRACTION: (70.0, 180.0),
    SIG_SAN_COOCCURRENCE:   (60.0, 90.0),
    SIG_REVERSE_WHOIS:      (50.0, 120.0),
    SIG_HISTORICAL_DNS:     (45.0, 60.0),
    SIG_BRAND_PROXIMITY:    (40.0, 90.0),
    SIG_SHARES_NONCDN_IP:   (30.0, 30.0),
    SIG_WEAK_NAMING:        (15.0, 45.0),
}

# ---------------------------------------------------------------------------
# Negative penalty identifiers (recon.md 7 "Negative Penalties")
# ---------------------------------------------------------------------------
PEN_PARKING = "parking_page"                  # known parking / for-sale page
PEN_SINKHOLE_IP = "sinkhole_ip"               # localhost / link-local / documentation / sinkhole IP
PEN_EXPIRED_DOMAIN = "expired_domain"         # domain expired or in redemption
PEN_CDN_NO_SIGNAL = "cdn_no_supporting_signals"   # pure CDN / generic cloud LB with no supporting signals
PEN_SHARED_HOSTING = "shared_hosting_ip"      # shared hosting IP with many unrelated domains
PEN_NXDOMAIN = "nxdomain_over_14d"            # NXDOMAIN for > 14 days
PEN_EXPIRED_CERT = "expired_cert_over_30d"    # certificate expired > 30 days with no renewal
PEN_TAKEOVER = "takeover_detected"            # takeover detected (DNS moved to unrelated party)
PEN_GENERIC_NAME = "generic_name_no_brand"    # extremely generic name with no brand signal

_PENALTIES_DEFAULT: Dict[str, float] = {
    PEN_PARKING:        -100.0,
    PEN_SINKHOLE_IP:    -100.0,
    PEN_EXPIRED_DOMAIN: -90.0,
    PEN_CDN_NO_SIGNAL:  -80.0,
    PEN_SHARED_HOSTING: -60.0,
    PEN_NXDOMAIN:       -50.0,
    PEN_EXPIRED_CERT:   -40.0,
    PEN_TAKEOVER:       -70.0,
    PEN_GENERIC_NAME:   -25.0,
}

# Penalties that force an immediate kill (recon.md 7: "-100 Immediate kill").
# The math alone (-100 vs a max +100 positive) already zeroes the score, but
# the engine also hard-sets state COLD so a kill can never be out-voted.
KILL_PENALTIES = frozenset({PEN_PARKING, PEN_SINKHOLE_IP})

# ---------------------------------------------------------------------------
# Node state thresholds (recon.md 7 "Node State Thresholds"; ties use >=)
# ---------------------------------------------------------------------------
STATE_ACTIVE = "ACTIVE"   # score >= 75
STATE_WARM = "WARM"       # 40 <= score < 75
STATE_COLD = "COLD"       # score < 40  (matches schema.py STATE_* values)

ACTIVE_THRESHOLD = 75.0
WARM_THRESHOLD = 40.0

# Score clamp bounds and rounding (IMPLEMENTATION_PLAN Stage 2).
SCORE_MIN = 0.0
SCORE_MAX = 100.0
SCORE_ROUND = 2       # final score decimals
AUDIT_ROUND = 4       # per-signal decayed-weight / contribution decimals


# ---------------------------------------------------------------------------
# Env override plumbing (applied once at import; no-op unless env vars set)
# ---------------------------------------------------------------------------
def _apply_env_overrides(
    positives: Dict[str, Tuple[float, Optional[float]]],
    penalties: Dict[str, float],
) -> Tuple[Dict[str, Tuple[float, Optional[float]]], Dict[str, float]]:
    positives = {k: v for k, v in positives.items()}
    penalties = dict(penalties)
    for sig, (w, h) in list(positives.items()):
        w_env = os.getenv(f"RECON_SCORE_W_{sig}")
        h_env = os.getenv(f"RECON_SCORE_H_{sig}")
        if w_env is not None:
            try:
                w = float(w_env)
            except ValueError:
                pass
        if h_env is not None:
            try:
                h = None if h_env.strip().lower() in ("", "none", "inf") else float(h_env)
            except ValueError:
                pass
        positives[sig] = (w, h)
    for pen in list(penalties):
        p_env = os.getenv(f"RECON_SCORE_P_{pen}")
        if p_env is not None:
            try:
                penalties[pen] = float(p_env)
            except ValueError:
                pass
    return positives, penalties


POSITIVE_SIGNALS, PENALTIES = _apply_env_overrides(_POSITIVE_SIGNALS_DEFAULT, _PENALTIES_DEFAULT)


def signal_params(signal_type: str) -> Optional[Tuple[float, Optional[float]]]:
    """(weight, half_life_days) for a positive signal, or None if unknown."""
    return POSITIVE_SIGNALS.get(signal_type)


def penalty_weight(penalty_type: str) -> Optional[float]:
    """Penalty weight (negative), or None if unknown."""
    return PENALTIES.get(penalty_type)


def classify(score: float) -> str:
    """Map a final score to a node state (recon.md 7 thresholds; ties use >=)."""
    if score >= ACTIVE_THRESHOLD:
        return STATE_ACTIVE
    if score >= WARM_THRESHOLD:
        return STATE_WARM
    return STATE_COLD
