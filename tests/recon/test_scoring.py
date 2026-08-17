"""
Hermetic unit tests for the scoring engine (recon.md 7 / IMPLEMENTATION_PLAN
Stage 2). Pure math — no Neo4j, no Redis, no network, no wall clock (``now`` is
injected). Follows the PASS/FAIL + exit-code style of test_repository.py.

Usage:
    python tests/recon/test_scoring.py
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCORING_DIR = _ROOT / "service" / "recon-pipeline" / "scoring"
sys.path.insert(0, str(_SCORING_DIR))

import weights  # noqa: E402
import engine  # noqa: E402
from engine import Signal, compute_score, decay  # noqa: E402

NOW = datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc)

PASS = []
FAIL = []


def check(label, condition, detail=""):
    if condition:
        PASS.append(label)
        print(f"  [PASS] {label}")
    else:
        FAIL.append(label)
        print(f"  [FAIL] {label}  {detail}")


def approx(a, b, eps=1e-6):
    return abs(a - b) <= eps


def sig(signal_type, age_days=0.0, confidence=1.0):
    return Signal(signal_type, NOW - timedelta(days=age_days), confidence)


def test_decay():
    print("\n--- decay math ---")
    check("d(0) = 1", approx(decay(0, 90), 1.0))
    check("d(h) = 0.5", approx(decay(90, 90), 0.5))
    check("d(2h) = 0.25", approx(decay(180, 90), 0.25))
    check("no decay when half_life is None", approx(decay(9999, None), 1.0))
    check("future observation clamps to d=1", approx(decay(-10, 90), 1.0))


def test_positive_contributions():
    print("\n--- positive signal contributions (w * d * c) ---")
    a = compute_score([sig(weights.SIG_EXACT_MATCH)], [], NOW)
    check("exact match -> 100", approx(a.final_score, 100.0), detail=str(a.final_score))
    check("exact match -> Active", a.state == weights.STATE_ACTIVE, detail=a.state)

    # SAN co-occurrence w=60, h=90; conf 0.5, age 0 -> 30
    b = compute_score([sig(weights.SIG_SAN_COOCCURRENCE, confidence=0.5)], [], NOW)
    check("confidence scales contribution (60*1*0.5=30)", approx(b.final_score, 30.0), detail=str(b.final_score))

    # SAN at age = one half-life -> 60*0.5 = 30
    c = compute_score([sig(weights.SIG_SAN_COOCCURRENCE, age_days=90)], [], NOW)
    check("decay applied in score (60*0.5=30)", approx(c.final_score, 30.0), detail=str(c.final_score))


def test_max_not_stack():
    print("\n--- max-not-stack rule ---")
    # two SAN observations: fresh (60) and decayed (30) -> only 60 counts
    a = compute_score(
        [sig(weights.SIG_SAN_COOCCURRENCE, age_days=0),
         sig(weights.SIG_SAN_COOCCURRENCE, age_days=90)],
        [], NOW,
    )
    check("same-type signals do not stack (max 60)", approx(a.positive_total, 60.0), detail=str(a.positive_total))
    counted = [s for s in a.signals if s.counted]
    check("exactly one observation counted", len(counted) == 1, detail=str(len(counted)))
    check("the larger observation is the counted one",
          approx(counted[0].contribution, 60.0), detail=str(counted[0].contribution))
    check("both observations still recorded in audit", len(a.signals) == 2, detail=str(len(a.signals)))

    # different types DO add
    b = compute_score([sig(weights.SIG_EXACT_MATCH), sig(weights.SIG_WEAK_NAMING)], [], NOW)
    check("different types add then clamp (100+15 -> 100)", approx(b.final_score, 100.0), detail=str(b.final_score))


def test_clamp():
    print("\n--- clamp to [0, 100] ---")
    hi = compute_score([sig(weights.SIG_EXACT_MATCH), sig(weights.SIG_ASN_CIDR_OWNERSHIP)], [], NOW)
    check("upper clamp (200 -> 100)", approx(hi.final_score, 100.0), detail=str(hi.final_score))
    check("raw preserved pre-clamp (200)", approx(hi.raw_score, 200.0), detail=str(hi.raw_score))
    lo = compute_score([], [weights.PEN_GENERIC_NAME], NOW)
    check("lower clamp (-25 -> 0)", approx(lo.final_score, 0.0), detail=str(lo.final_score))


def test_penalties():
    print("\n--- penalty table (recon.md 7) ---")
    expected = {
        weights.PEN_PARKING: -100.0,
        weights.PEN_SINKHOLE_IP: -100.0,
        weights.PEN_EXPIRED_DOMAIN: -90.0,
        weights.PEN_CDN_NO_SIGNAL: -80.0,
        weights.PEN_SHARED_HOSTING: -60.0,
        weights.PEN_NXDOMAIN: -50.0,
        weights.PEN_EXPIRED_CERT: -40.0,
        weights.PEN_TAKEOVER: -70.0,
        weights.PEN_GENERIC_NAME: -25.0,
    }
    for pen, w in expected.items():
        check(f"penalty {pen} = {w}", approx(weights.penalty_weight(pen), w), detail=str(weights.penalty_weight(pen)))

    # a penalty subtracts from positives
    a = compute_score([sig(weights.SIG_EXACT_MATCH)], [weights.PEN_GENERIC_NAME], NOW)
    check("100 - 25 = 75 (Active boundary)", approx(a.final_score, 75.0) and a.state == weights.STATE_ACTIVE,
          detail=f"{a.final_score}/{a.state}")

    # penalties dedupe (same condition applies once)
    b = compute_score([sig(weights.SIG_EXACT_MATCH)], [weights.PEN_GENERIC_NAME, weights.PEN_GENERIC_NAME], NOW)
    check("duplicate penalty applied once", approx(b.penalty_total, -25.0), detail=str(b.penalty_total))


def test_kill():
    print("\n--- immediate-kill penalties ---")
    for pen in (weights.PEN_PARKING, weights.PEN_SINKHOLE_IP):
        a = compute_score([sig(weights.SIG_EXACT_MATCH)], [pen], NOW)
        check(f"{pen} kills score to 0", approx(a.final_score, 0.0), detail=str(a.final_score))
        check(f"{pen} -> Cold + killed flag", a.state == weights.STATE_COLD and a.killed,
              detail=f"{a.state}/{a.killed}")


def test_thresholds():
    print("\n--- state thresholds (ties use >=) ---")
    check("75 -> Active", weights.classify(75.0) == weights.STATE_ACTIVE)
    check("74.99 -> Warm", weights.classify(74.99) == weights.STATE_WARM)
    check("40 -> Warm", weights.classify(40.0) == weights.STATE_WARM)
    check("39.99 -> Cold", weights.classify(39.99) == weights.STATE_COLD)
    check("0 -> Cold", weights.classify(0.0) == weights.STATE_COLD)


def test_audit_completeness():
    print("\n--- audit completeness + serialization ---")
    a = compute_score(
        [sig(weights.SIG_EXACT_MATCH), sig(weights.SIG_SAN_COOCCURRENCE, age_days=45, confidence=0.8)],
        [weights.PEN_GENERIC_NAME],
        NOW,
    )
    check("every signal appears in audit", len(a.signals) == 2, detail=str(len(a.signals)))
    check("every penalty appears in audit", len(a.penalties) == 1, detail=str(len(a.penalties)))
    fields_ok = all(
        s.signal_type and s.observed_at and s.decayed_weight is not None and s.age_days is not None
        for s in a.signals
    )
    check("signal audit rows carry (type, observed_at, decayed_weight, age)", fields_ok)
    check("computed_at echoes injected now", a.computed_at == NOW.isoformat(), detail=a.computed_at)
    try:
        json.dumps(a.to_dict())
        check("ScoreAudit.to_dict() is JSON-serializable", True)
    except (TypeError, ValueError) as exc:
        check("ScoreAudit.to_dict() is JSON-serializable", False, detail=str(exc))


def test_determinism():
    print("\n--- deterministic (injected now) ---")
    inp = [sig(weights.SIG_SAN_COOCCURRENCE, age_days=30, confidence=0.7)]
    a = compute_score(inp, [weights.PEN_NXDOMAIN], NOW)
    b = compute_score(inp, [weights.PEN_NXDOMAIN], NOW)
    check("same inputs + same now -> identical score", a.final_score == b.final_score,
          detail=f"{a.final_score} vs {b.final_score}")
    check("unknown signal type contributes nothing",
          compute_score([sig("nonexistent_signal")], [], NOW).final_score == 0.0)


def run():
    test_decay()
    test_positive_contributions()
    test_max_not_stack()
    test_clamp()
    test_penalties()
    test_kill()
    test_thresholds()
    test_audit_completeness()
    test_determinism()

    print(f"\n=== RESULTS: {len(PASS)} passed, {len(FAIL)} failed ===")
    if FAIL:
        print("Failed checks:")
        for f in FAIL:
            print(f"  - {f}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    run()
