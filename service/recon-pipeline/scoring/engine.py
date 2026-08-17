"""
Scoring engine (recon.md 7; IMPLEMENTATION_PLAN.md Stage 2).

Pure functions implementing the spec's confidence model exactly:

    FinalScore(N) = clamp( sum_s( w_s * d_s(t) * c_s ) + sum_p( p ), 0, 100 )
    d_s(t) = 2 ** (-t / h_s)          # exponential decay; h_s == None -> no decay

Rules baked in (recon.md 7):
* Multiple observations of the SAME signal type take the MAX contribution
  (they do not stack).
* Penalties apply once per condition; parking / sinkhole are immediate kills.
* State: score >= 75 Active, 40-74 Warm, < 40 Cold (ties use >=).

No infra, no wall clock: ``now`` is an injected parameter, so every result is
deterministic and unit-testable (the stage the plan calls "the project's most
standalone-testable stage").
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

# Sibling modules are imported by bare name (this folder lives under the
# hyphenated service/recon-pipeline/ path, so add it to sys.path — same shim
# graph/repository.py uses).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit import PenaltyContribution, ScoreAudit, SignalContribution  # noqa: E402
import weights  # noqa: E402


@dataclass
class Signal:
    """One positive-signal observation fed to the engine.

    ``signal_type`` must be one of the ``weights.SIG_*`` identifiers; unknown
    types are ignored (they carry no weight). ``observed_at`` drives decay;
    ``confidence`` is the observation confidence c_s in [0, 1].
    """

    signal_type: str
    observed_at: datetime
    confidence: float = 1.0


def decay(age_days: float, half_life: Optional[float]) -> float:
    """d(t) = 2 ** (-t / h). No decay (1.0) when half_life is None/inf.

    d(0)=1, d(h)=0.5, d(2h)=0.25. Negative ages (future observations) clamp to 0.
    """
    if half_life is None:
        return 1.0
    t = max(0.0, age_days)
    return 2.0 ** (-t / half_life)


def _age_days(observed_at: datetime, now: datetime) -> float:
    return max(0.0, (now - observed_at).total_seconds() / 86400.0)


def compute_score(
    signals: Iterable[Signal],
    penalties: Sequence[str],
    now: datetime,
) -> ScoreAudit:
    """Compute the final score + full audit for a node.

    Parameters
    ----------
    signals:
        Positive-signal observations (any number, any mix of types).
    penalties:
        Penalty-condition identifiers (``weights.PEN_*``); deduplicated.
    now:
        The scoring instant (injected — never the wall clock), used for decay.
    """
    contribs: List[SignalContribution] = []

    # 1. Decay + confidence for every observation.
    for sig in signals:
        params = weights.signal_params(sig.signal_type)
        if params is None:
            continue  # unknown signal type carries no weight
        base_w, half_life = params
        age = _age_days(sig.observed_at, now)
        d = decay(age, half_life)
        decayed = base_w * d
        confidence = max(0.0, min(1.0, sig.confidence))
        contribs.append(SignalContribution(
            signal_type=sig.signal_type,
            weight=base_w,
            half_life=half_life,
            confidence=confidence,
            observed_at=sig.observed_at.isoformat(),
            age_days=round(age, weights.AUDIT_ROUND),
            decayed_weight=round(decayed, weights.AUDIT_ROUND),
            contribution=round(decayed * confidence, weights.AUDIT_ROUND),
            counted=False,  # decided by the max-not-stack pass below
        ))

    # 2. Max-not-stack: per signal type, only the largest contribution counts.
    best_by_type: dict = {}
    for c in contribs:
        best = best_by_type.get(c.signal_type)
        if best is None or c.contribution > best.contribution:
            best_by_type[c.signal_type] = c
    positive_total = 0.0
    for c in best_by_type.values():
        c.counted = True
        positive_total += c.contribution

    # 3. Penalties (dedup by type; unknown types ignored).
    pen_contribs: List[PenaltyContribution] = []
    penalty_total = 0.0
    killed = False
    for pen_type in dict.fromkeys(penalties):  # ordered dedup
        w = weights.penalty_weight(pen_type)
        if w is None:
            continue
        is_kill = pen_type in weights.KILL_PENALTIES
        killed = killed or is_kill
        penalty_total += w
        pen_contribs.append(PenaltyContribution(penalty_type=pen_type, weight=w, kill=is_kill))

    # 4. Combine, clamp, classify.
    raw = positive_total + penalty_total
    if killed:
        final = weights.SCORE_MIN
    else:
        final = max(weights.SCORE_MIN, min(weights.SCORE_MAX, raw))
    final = round(final, weights.SCORE_ROUND)
    state = weights.classify(final)

    return ScoreAudit(
        signals=contribs,
        penalties=pen_contribs,
        positive_total=round(positive_total, weights.AUDIT_ROUND),
        penalty_total=round(penalty_total, weights.AUDIT_ROUND),
        raw_score=round(raw, weights.AUDIT_ROUND),
        final_score=final,
        state=state,
        killed=killed,
        computed_at=now.isoformat(),
    )
