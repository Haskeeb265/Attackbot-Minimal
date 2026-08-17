"""
Score audit structures (IMPLEMENTATION_PLAN.md Stage 2).

A :class:`ScoreAudit` is the first-class, serializable record of *why* a node
scored the way it did — every contributing signal (with its decayed weight) and
every penalty, plus the raw sum, the clamped final score and the resulting
state. The spec NFR "every score decision must be auditable" is satisfied from
day one; this is also what S14 (observability) queries and what lands in the
``score_audit`` node property (recon.md Appendix A).

Pure data only — no infra imports — so the engine stays unit-testable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class SignalContribution:
    """One positive-signal observation and its decayed contribution."""

    signal_type: str
    weight: float                 # base weight w_s
    half_life: Optional[float]    # h_s in days (None == no decay)
    confidence: float             # c_s in [0, 1]
    observed_at: str              # ISO-8601 timestamp of the observation
    age_days: float               # t at scoring time
    decayed_weight: float         # w_s * d_s(t)
    contribution: float           # w_s * d_s(t) * c_s
    counted: bool                 # False when out-competed by the max-not-stack rule


@dataclass
class PenaltyContribution:
    """One penalty condition and the weight it applied."""

    penalty_type: str
    weight: float                 # negative
    kill: bool                    # immediate-kill penalty (recon.md 7)


@dataclass
class ScoreAudit:
    """Complete, serializable explanation of a node's score."""

    signals: List[SignalContribution] = field(default_factory=list)
    penalties: List[PenaltyContribution] = field(default_factory=list)
    positive_total: float = 0.0   # sum of counted contributions
    penalty_total: float = 0.0    # sum of penalty weights (negative)
    raw_score: float = 0.0        # positive_total + penalty_total (pre-clamp)
    final_score: float = 0.0      # clamped to [0, 100]
    state: str = "COLD"
    killed: bool = False          # a kill penalty forced the score to 0
    computed_at: str = ""         # ISO-8601 of the scoring run (the injected `now`)

    def to_dict(self) -> dict:
        """JSON-serializable dict for the graph ``score_audit`` property."""
        return asdict(self)
