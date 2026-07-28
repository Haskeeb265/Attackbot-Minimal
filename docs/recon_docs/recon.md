# Enterprise-Grade Attack Surface Management (ASM) Architecture

**Implementation Specification**  
**Objective:** Maximum attack surface discovery for bug bounty programs via recursive, graph-backed reconnaissance.

---

## 1. Strategic Context

In bug bounty reconnaissance, mapping corporate network infrastructure is the difference between finding a unique, unmonitored vulnerability and testing the same hardened main application as thousands of other hunters. Organizations frequently lose track of legacy systems, staging environments, shadow IT, and forgotten perimeter assets. These forgotten assets often represent the easiest path of entry.

This architecture is designed to systematically discover, correlate, score, and recursively expand every reachable asset from a given seed while remaining practical under real-world constraints (WAFs, CDNs, storage limits, and noise).

**Primary Success Criterion**  
If a hidden asset is discoverable from the available data through any combination of the defined techniques and correlation signals, the pipeline must surface it.

---

## 2. Core Reconnaissance Concepts

- **Subdomain Enumeration & Wildcard Evasion**  
  Passive sources (Certificate Transparency, VirusTotal, SecurityTrails, Rapid7 FDNS, etc.) combined with active wordlist + permutation resolution. Robust wildcard detection (consistent NXDOMAIN / response fingerprinting) is mandatory to avoid false-positive floods.

- **ASN and CIDR Mapping**  
  Resolve organizational ASNs via routing registries (RADB, Hurricane Electric, BGPView) to obtain all announced prefixes. These become high-value seeds for IP-space expansion.

- **Reverse DNS (PTR) Sweeps**  
  Systematic PTR queries across live IPs inside owned CIDRs frequently reveal internal hostnames, staging systems, and administrative interfaces that never appeared in forward DNS.

- **Historical Depth**  
  Wayback Machine CDX, Common Crawl, historical passive DNS, and full certificate history are first-class data sources. Organizations routinely clean the present while leaving the past intact.

- **Cross-Asset Recursion**  
  Every extracted artifact (hostname, IP, URL, certificate SAN, secret, cloud resource name, endpoint) is normalized and fed back as a potential new seed, gated by relevance scoring.

---

## 3. Target Asset Types & Base Strategies

The system supports the following asset taxonomy. Each type has dedicated extraction and probing logic. All findings flow into the shared graph and scoring engine.

| # | Asset Type | Core Strategy |
|---|------------|---------------|
| 1 | Domain | Tech fingerprinting, prioritized port/service scan, historical URL/JS harvest, certificate analysis |
| 2 | Wildcard | Exhaustive passive enumeration + wordlist/permutation DNS with wildcard filtering |
| 3 | URL | Scoped content discovery, recursive JS + source-map analysis, parameter & method mining |
| 4 | CIDR | Host discovery, PTR sweeps, TLS certificate extraction across the range |
| 5 | IP Address | Passive intelligence (Shodan/Censys/etc.) + prioritized → full port scan, banner & TLS inspection |
| 6 | Source Code | Full-history secret scanning, static analysis (routes, sinks, authz), dependency scanning |
| 7 | Android (Play Store) | APK acquisition, manifest analysis, string/URL/secret extraction |
| 8 | Android (.apk) | Full decompilation + deobfuscation, hardcoded endpoint & key recovery |
| 9 | iOS (App Store) | IPA acquisition, Info.plist / entitlements / URL scheme analysis, string extraction |
| 10 | iOS (TestFlight) | Binary & configuration delta analysis against public releases |
| 11 | iOS (.ipa) | Static Payload extraction, binary flags, embedded assets |
| 12 | Executable | Static string/import analysis + sandboxed dynamic network/IPC observation |
| 13 | Hardware / IoT | Firmware acquisition & unpacking, string/credential extraction (physical interfaces are high-touch) |
| 14 | Smart Contract | Source verification / decompilation, static + symbolic analysis, on-chain state & dependency mapping |
| 15 | AI Model | Prompt-injection & boundary testing, system-prompt / tool / RAG enumeration |
| 16 | Windows (Microsoft Store) | AppX/MSIX unpacking, manifest & resource analysis |
| 17 | Other (primarily ASNs) | BGP/ASN → prefix expansion into CIDR pipeline |
| 18 | Cross-Asset Correlation Layer | Universal graph + scoring engine that links all of the above |

---

## 4. Unconstrained Ideal vs. Practical Reality

A purely maximalist recursive design (every output immediately becomes a new unconstrained seed) maximizes theoretical coverage but fails in practice:

- **WAF / Anti-DDoS** — Aggressive probing triggers blackholing and CAPTCHAs, starving the recursive loop of data.
- **CDN / Shared-Hosting Tarpit** — Blind reverse-DNS or SAN expansion on shared infrastructure explodes the graph into the public internet.
- **Data Avalanche** — Retaining every raw binary, full git history, and HTTP body is unsustainable at scale.

The architecture therefore imposes three mandatory gates while preserving maximum *relevant* discovery.

---

## 5. Refined Architecture Gates

### 5.1 Stealth & Resilience Layer
- Distributed residential + datacenter proxy pools with health scoring
- Protocol-aware traffic shaping (realistic TLS fingerprints, header order, HTTP/2)
- Per-target adaptive rate limiting with exponential backoff + jitter
- CAPTCHA / challenge detection with graceful fallback to passive-only mode
- Continuous feedback: quarantine techniques or sources that begin returning blocks

### 5.2 Scoped Recursion Gate
Before any newly discovered artifact may re-enter an active pipeline it must pass a relevance filter:

- **Hard signals** (immediate high confidence): exact registrable-domain match, current ASN/CIDR ownership, extraction from authenticated in-scope source.
- **Soft signals** (cumulative): certificate SAN co-occurrence, reverse-WHOIS linkage, historical DNS to dedicated infrastructure, strong brand proximity, extraction from in-scope binary or repository.
- Pure CDN edge nodes, generic shared hosting, and parking pages are rejected or heavily penalized unless additional strong ownership signals exist.

### 5.3 Stream-Extract-Discard Storage
- Ingest → stream process → extract structured artifacts (hosts, URLs, IPs, secrets, SANs, cloud resource names, endpoints).
- Persist: normalized artifacts + provenance + content hash.
- Retain raw objects only when a high-value extractor fires or for a short sliding window.
- Tiered storage: hot graph/metadata, cold object storage with lifecycle policies.

---

## 6. Data Correlation & Graph Database

**System of Record:** Property Graph Database (Neo4j, Amazon Neptune, Memgraph, or equivalent).

### Core Node Labels
`Organization`, `Asset`, `Domain`, `Subdomain`, `IP`, `CIDR`, `URL`, `Endpoint`, `Certificate`, `Secret`, `CloudResource`, `Repository`, `Binary`, `MobileApp`, `SmartContract`, `ASN`, `Technology`

### Core Relationship Types
`RESOLVES_TO`, `HAS_CERTIFICATE`, `ISSUED_FOR`, `EXTRACTED_FROM`, `FOUND_IN`, `POINTS_TO`, `BELONGS_TO_ASN`, `OWNED_BY`, `SHARES_CERTIFICATE_WITH`, `RELATED_TO`, `DERIVED_FROM`, `USES_TECHNOLOGY`, `HOSTS`

Every edge and signal observation carries provenance (pipeline, tool, timestamp, confidence).

**Illustrative Pivot**  
An S3 bucket name extracted from an in-scope APK receives `EXTRACTED_FROM` → Binary and `FOUND_IN` → MobileApp. A second bucket discovered in source code is correlated via naming similarity, shared cloud account indicators, or common linkage to the same Organization. When cumulative confidence exceeds threshold, both receive `RELATED_TO` / `BELONGS_TO` edges and become eligible for further enumeration.

---

## 7. Mathematical Scoring Model

Every candidate node receives a confidence score before it may trigger active recursion.

### Core Equation

\[
\text{FinalScore}(N) = \operatorname{clamp}\Bigg(
\sum_{s \in \text{Signals}} \big( w_s \cdot d_s(t) \cdot c_s \big)
+ \sum_{p \in \text{Penalties}} p
,\ 0,\ 100\Bigg)
\]

- \( w_s \) = base weight of signal \( s \)
- \( d_s(t) = 2^{-(t / h_s)} \) = exponential decay ( \( t \) = age in days, \( h_s \) = half-life in days)
- \( c_s \) = observation confidence (0.0–1.0)
- \( p \) = negative penalty values

### Node State Thresholds

| Score Range | State | Behavior |
|-------------|-------|----------|
| ≥ 75 | Active | Eligible for full recursive probing |
| 40–74 | Warm | Stored; background re-scoring only |
| < 40 | Cold | Quarantined; retained for future correlation only |

### Positive Signals

| Signal | Weight \( w_s \) | Half-life \( h_s \) |
|--------|------------------|---------------------|
| Exact subdomain / registrable domain match | 100 | ∞ (no decay) |
| Current ASN / CIDR ownership | 100 | ∞ (no decay) |
| Extracted from in-scope binary or source code | 70 | 180 days |
| Appears in SAN of certificate that also covers seed | 60 | 90 days |
| Reverse WHOIS exact org / email match | 50 | 120 days |
| Historical DNS to dedicated (non-CDN) in-scope IP | 45 | 60 days |
| Strong brand / string proximity in hostname | 40 | 90 days |
| Shares non-CDN IP with high-confidence asset | 30 | 30 days |
| Weak naming similarity only | 15 | 45 days |

Multiple observations of the same signal type take the maximum contribution (they do not stack unboundedly).

### Negative Penalties

| Condition | Weight | Effect |
|-----------|--------|--------|
| Known parking / for-sale page | –100 | Immediate kill |
| Localhost / link-local / documentation / sinkhole IP | –100 | Immediate kill |
| Domain expired or in redemption | –90 | Strong suppression |
| Pure CDN / generic cloud load-balancer hostname (no supporting signals) | –80 | Strong suppression |
| Shared hosting IP with many unrelated domains | –60 | |
| NXDOMAIN for > 14 days | –50 | |
| Certificate expired > 30 days with no renewal | –40 | |
| Takeover detected (DNS moved to unrelated party) | –70 | |
| Extremely generic name with no brand signal | –25 | |

### Pruning
- Soft prune: score < 40 → mark Cold, cancel pending active jobs.
- Optional hard prune: score remains < 20 for > 90 days with no new signals → archive.

Background re-scoring continuously refreshes decay and re-evaluates warm/cold nodes when new evidence arrives.

---

## 8. Event-Driven Queue & Worker Topology

Decouple high-throughput discovery from expensive correlation.

### Primary Queues
- `raw.artifacts` — raw responses, binaries, certificates
- `candidates.nodes` — normalized candidate nodes + provenance
- `scored.nodes` — final score + decision
- `active.recon.{asset_type}` — only nodes that passed the activation threshold
- `graph.writes` — all node/edge mutations
- Dead-letter / retry queues for poison messages

Partitioning is performed by stable hash of node identifier or by seed/organization where appropriate.

### Worker Roles
1. **Discovery / Active Probing Workers** — Lean. Local checks + bloom filters only. Never perform multi-hop graph queries.
2. **Extraction Workers** — Stateless stream processing of raw artifacts into candidate nodes.
3. **Correlation / Scoring Workers** — Own scoring. Prefer hot cache; issue only targeted, indexed graph queries when required.
4. **Graph Writer Service** — Single (or sharded) transactional authority for all mutations.
5. **Active Dispatcher** — Applies rate-limit tokens and priority before enqueueing probing work.

### Hot Cache (Redis) — Critical Path Support
- `sig:{node_id}` — node summary (last score, status, etc.)
- `sigobs:{node_id}:{signal_type}` — individual signal observations (weight, half-life, confidence, observed_at)
- `seed:hot:{seed_id}` — sorted set of related nodes by score
- `node:seeds:{node_id}` — set of linked seeds
- `penalty:{node_id}` — active penalties
- `bloom:seen:{seed_id}` — ultra-fast membership test

Scoring on the hot path uses pipelined reads + lightweight floating-point decay. A background refresher keeps long-lived `decayed_weight` values honest. New strong signals trigger immediate high-priority re-scoring. Sliding TTLs implement interest-based retention.

---

## 9. Implementation Guidance

### Recommended Build Order
1. Graph schema + basic CRUD and indexing
2. Scoring engine + Redis hot cache + unit tests for decay/penalties
3. One complete asset pipeline (Domain or Wildcard recommended) end-to-end
4. Extraction → candidate → scoring → graph write path
5. Active dispatcher + simple rate limiting
6. Additional asset pipelines in priority order (Source Code, CIDR/IP, Mobile, etc.)
7. Background re-scoring and decay refresher
8. Stealth layer (proxies, backoff, fingerprinting)
9. Observability, dead-letter handling, and operational dashboards
10. Continuous differential monitoring loops

### Key Non-Functional Requirements
- All active probing must be policy-gated (even if a separate module later filters scope).
- Every score decision must be auditable (contributing signals + provenance).
- The system must degrade gracefully to passive-only mode under defensive pressure.
- Idempotency and exactly-once (or effectively-once) semantics for graph mutations.

---

## 10. Validation Scenarios (Illustrative)

- **ASN → CIDR → PTR → Domain explosion**: Seed an organization ASN, expand prefixes, sweep PTRs, feed discovered hostnames into the Domain pipeline, and verify that previously unknown staging/admin hosts surface with high scores.
- **Mobile binary → Cloud resource → related infrastructure**: Extract bucket or API hostnames from an APK/IPA, confirm they receive high provenance weight, and observe automatic activation and further enumeration.
- **Certificate SAN co-occurrence**: A new certificate containing both a known seed domain and an unknown hostname should rapidly promote the unknown hostname via the +60 SAN signal.
- **Decay & penalty behavior**: Inject a historically linked domain that later becomes a parking page or NXDOMAIN and verify it is demoted and removed from active queues.

These scenarios serve both as acceptance tests and as educational walk-throughs of the recursive correlation engine.

---

**Document Status:** Implementation-ready master specification  
**Derived from:** Full multi-turn design discussion on recursive graph-backed ASM reconnaissance (July 2026)