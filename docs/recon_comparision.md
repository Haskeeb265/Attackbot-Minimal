# V1 vs V2 Recon Documentation — Comparison Analysis

**Date:** August 19, 2026
**Documents Compared:**
- V1: `recon.md`, `recon_flow.md`, `IMPLEMENTATION_PLAN.md`
- V2: `recon_v2.md`, `recon_flow_v2.md`, `IMPLEMENTATION_PLAN_V2.md`

---

## Verdict

**V2 is better**, but it's not a replacement — it's an **extension layer** on top of V1. The v2 docs explicitly state this and inherit all v1 mechanisms unchanged. Here's the breakdown.

---

## 1. `recon.md` vs `recon_v2.md`

**`recon_v2.md` adds critical missing architecture:**

| Area | V1 | V2 |
|---|---|---|
| **Scope Engine** | Not present — v1's recursion gate filters *relevance*, assumes candidate is already in-scope | New mandatory gate (`IN_SCOPE` / `AMBIGUOUS` / `OUT_OF_SCOPE`) upstream of scoring — **this is the single most important addition** |
| **Source classes** | Only crt.sh + Wayback CDX | 11 new source classes (ASN pivot, fingerprint clustering, code dorking, mobile teardown, cloud buckets, etc.) |
| **Takeover detection** | Not addressed | Dedicated subdomain/tenant takeover detector with per-program policy gating |
| **Secret handling** | Mentioned but not contractually specified | Full Secret Handling Contract — hash at extraction, raw values never leave the worker |
| **Failure modes at scale** | 3 named (WAF, CDN tarpit, data avalanche) | Adds 3 more: ownership ambiguity explosion, secret exposure amplification, policy drift on third-party findings |
| **Graph schema** | Complete v1 schema | Adds `FingerprintCluster`, `ThirdPartyService` nodes + 5 new relationship types + `scope_state` property |

**Why this matters:** V1 has a blind spot — ownership-pivot sources (ASN, fingerprint clustering, reverse WHOIS) produce ambiguous results by design. Without the Scope Engine, enabling those sources would flood the graph with cloud-provider IPs and shared-hosting artifacts. V2 solves this structurally, not by policy note.

---

## 2. `recon_flow.md` vs `recon_flow_v2.md`

**V2 flow is better:**

- V1 has 5 Mermaid diagrams — thorough, clean, covers S0-S14 well
- V2 updates the end-to-end flow diagram to show the Scope Engine (S15) as a mandatory chokepoint, with clear `PASSIVE` / `LIGHTACTIVE` subgraphs
- V2 adds a dedicated takeover detection flow diagram
- V2 provides an updated build order with rollout priority (highest surface-per-effort first)
- V2 has a clean "what did NOT change" section (§7) that explicitly preserves safety invariants

**Minor V2 improvement:** V2's Mermaid diagrams are more readable — the Scope Engine's position between sources and S3 is visually obvious, making the safety model self-evident in the diagram.

---

## 3. `IMPLEMENTATION_PLAN.md` vs `IMPLEMENTATION_PLAN_V2.md`

**V2 implementation plan is tighter:**

| Aspect | V1 Plan | V2 Plan |
|---|---|---|
| **Stage count** | 15 stages (S0-S14) | 12 new stages (S15-S26), continuing numbering |
| **Standalone testability** | Well-defined per stage | Same pattern + explicit "contract enforcement tests" (e.g., S21's secret never-in-logs test) |
| **Decisions format** | 6 locked-in decisions | 6 locked-in decisions with same rigor + 10 open questions clearly scoped |
| **Architecture diagram** | ASCII block diagram | Delta diagram showing exactly where v2 inserts into v1 |
| **Dependency graph** | Full DAG | Authoritative edge table with "mandatory" vs "soft" distinction — **more precise** |
| **Code layout** | Complete v1 layout | Clean additive layout under `scope/`, `sources/`, `lightactive/`, `extract/secrets.py` |
| **Convention extensions** | 9 conventions | Adds 3 more (#10 scope-state orthogonal to score-state, #11 Secret Handling Contract, #12 keyed-API graceful degradation) — **these prevent real bugs** |

**The v2 plan's Secret Handling Contract (convention #11) is particularly strong** — it makes "raw secret never touches a log/queue/graph" an auditable property enforced at a single module boundary, not something each extractor must remember to do.

---

## Summary Scorecard

| Dimension | Winner | Why |
|---|---|---|
| Core architecture | **V2** | Scope Engine solves the fundamental ambiguity problem V1 leaves open |
| Source coverage | **V2** | 11 new classes vs 2, covering the high-yield categories (ASN, fingerprints, code dorking, mobile, takeover) |
| Safety model | **V2** | Secret handling contract + Scope Engine + per-program takeover gating = defense in depth |
| Documentation quality | **V2** | Cleaner decision tables, better structured open questions, explicit "what changed / what didn't" |
| Completeness as standalone | **V1** | V1 is self-contained; V2 requires V1 as foundation (by design) |
| Implementation readiness | **Tie** | Both are well-specified with standalone tests, dependency tables, and trade-off analysis |

---

## Bottom Line

V2 is the better specification because it closes the ownership-ambiguity hole and adds the source classes that actually produce the highest-value bug bounty findings (ASN pivots, fingerprint clusters, code dorking, takeover detection). But V1 is essential — it's the foundation V2 extends. You need both, in that order.

**Recommended path:** implement S0-S14 from `IMPLEMENTATION_PLAN.md` first, then layer S15-S26 from `IMPLEMENTATION_PLAN_V2.md` once the core pipeline is proven.
