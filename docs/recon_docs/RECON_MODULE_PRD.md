# PRD: Recon Module — Asset-Specific Reconnaissance Methodology

## 0. Executive summary

### 0.1 Problem statement

Attackbot's scraping module ingests HackerOne program data (scopes, weaknesses, exclusions) into PostgreSQL, but the recon module that transforms this raw scope data into a validated, fingerprinted attack surface does not yet exist. Without it, the pentesting module has no structured input — the pipeline stops after ingestion.

### 0.2 Proposed solution

Build a recursive, asset-type-aware reconnaissance pipeline that:
1. Classifies each scoped asset by type (URL, WILDCARD, DOMAIN, IP_ADDRESS, CIDR, ANDROID_APP, IOS_APP, SOURCE_CODE, HARDWARE)
2. Executes the appropriate reconnaissance workflow for each type — discovering subdomains, endpoints, ports, services, secrets, and hidden infrastructure
3. Feeds recursive outputs (newly discovered assets) back into the pipeline until no new assets are produced
4. Produces a structured, deduplicated, prioritized asset inventory for the pentesting module

### 0.3 Success criteria

| Criterion | Target | Baseline (Current State) |
|---|---|---|
| Asset discovery coverage | >= 90% of reachable assets per program (MVP); >= 95% (v1.0) | Manual recon ~60% in 2 hours |
| Hidden asset discovery rate | >= 20% of final count from recursive outputs | Manual: ~5% |
| False positive rate | <= 5% unreachable/out-of-scope assets | Manual: ~15% |
| Time per program | <= 15 minutes (<= 100 scopes) | Manual: ~2 hours |
| Programs per hour | >= 20 with parallel execution | Manual: ~3 |
| LLM quota consumption | <= 50% per program (deterministic stages use 0%) | N/A |

---

## 1. Product overview

### 1.1 Document title and version

- PRD: Recon Module — Asset-Specific Reconnaissance Methodology
- Version: 1.0
- Status: Draft
- Author: Buffy (AI assistant) + Haseeb
- Date: July 14, 2026

### 1.2 Product summary

Attackbot's recon module is the second top-level operation in the autonomous vulnerability discovery engine. It takes ingested HackerOne program data (scopes, weaknesses, exclusions) and produces a validated, fingerprinted attack surface ready for pentesting.

This document defines the complete reconnaissance methodology for each asset type encountered in HackerOne bug bounty programs. The methodology is designed to maximize attack surface discovery — specifically, to uncover hidden assets that can be inferred or derived from publicly known assets. Every asset type produces recursive outputs that feed back into the pipeline, creating a compounding discovery loop rather than a linear sweep.

The recon module operates within the GoalAct architecture — an LLM-driven goal-action loop where every action must answer: "What new information will this provide?" The pipeline is structured as a decision tree, not a linear workflow, with evidence driving hypothesis formation and hypothesis driving the next reconnaissance action.

### 1.3 Prerequisites

- Ingestion pipeline must be complete and stable (scope.md §2)
- `bounty_master`, `bounty_detail`, `program_weaknesses`, `bounty_exclusion` tables populated
- PostgreSQL 16 + psycopg3 connection pool operational
- External recon tools installed (see Appendix C for tool stack tiers)

---

## 2. Goals

### 2.1 Business goals

- Maximize vulnerability discovery yield per program by achieving complete asset coverage
- Minimize redundant reconnaissance work across programs with overlapping asset types
- Produce structured intelligence that directly feeds the pentesting module without manual transformation
- Scale across thousands of HackerOne programs with predictable resource consumption

### 2.2 User goals

- Discover every internet-facing asset belonging to a target organization
- Identify hidden assets (staging environments, internal tools, forgotten subdomains) not explicitly listed in scope
- Classify each asset by technology stack, WAF/CDN presence, and authentication requirements
- Map trust relationships and lateral movement paths between discovered assets
- Generate actionable evidence for vulnerability testing prioritization

### 2.3 Non-goals

- Vulnerability exploitation — recon produces intelligence, not exploits
- Social engineering or phishing campaigns
- Physical security testing
- Denial-of-service testing
- Testing assets explicitly out of scope per program rules
- Real-time continuous monitoring (this is a one-shot pipeline per program)

---

## 3. User personas

### 3.1 Key user types

- **Attackbot Autonomous Engine**: The primary consumer — an LLM-driven goal-action loop that reads recon output and makes decisions about next actions
- **Bug Bounty Researcher**: Human operator who reviews Attackbot's findings and validates high-value targets
- **Program Administrator**: Defines scope, weaknesses, and exclusions via HackerOne

### 3.2 Basic persona details

- **Attackbot Engine**: Reads structured JSON output from each recon stage. Makes decisions based on evidence. Requires deterministic, deduplicated, normalized data. Never interacts with raw tool output.
- **Bug Bounty Researcher**: Reviews asset inventory, prioritization scores, and technology fingerprints. Needs clear rationale for why each asset was flagged as high-priority.

### 3.3 Role-based access

- **Recon Pipeline**: Read access to `bounty_master`, `bounty_detail`, `program_weaknesses`, `bounty_exclusion` tables. Write access to recon-specific tables (asset inventory, fingerprint cache, evidence store).
- **GoalAct Planner**: Reads asset inventory and evidence. Writes action plans and scratchpad state.

---

## 4. Functional requirements

### 4.1 Asset classification layer (Priority: P0)

- Classify each `bounty_detail.scope_type` into the correct recon workflow
- Supported asset types: `URL`, `WILDCARD`, `DOMAIN`, `IP_ADDRESS`, `CIDR`, `ANDROID_APP`, `IOS_APP`, `SOURCE_CODE`, `HARDWARE`
- Classification must be deterministic — same scope type always routes to the same workflow
- Unknown asset types must be logged and flagged, not silently dropped

### 4.2 WILDCARD recon workflow (Priority: P0)

- **Horizontal goals**: Discover every subdomain via passive aggregation (CT logs, passive DNS, search engines), active brute-force (puredns + shuffledns), permutation breeding (DNSGen), reverse DNS sweep, and web content extraction
- **Vertical goals**: Classify each subdomain as live/dead, extract HTTP metadata, fingerprint technology stack, detect WAF/CDN, discover origin IPs behind CDN, detect subdomain takeover candidates, extract TLS certificate details, classify functional purpose
- **Recursive outputs**: Each live subdomain produces a `URL` asset; discovered origin IPs produce `IP_ADDRESS` assets; new subdomains from JS crawl re-enter WILDCARD processing

### 4.3 URL recon workflow (Priority: P0)

- **Horizontal goals**: Crawl full visible link graph (katana + Playwright), mine historical URLs (gau + waybackurls), directory/file fuzzing (feroxbuster), virtual host discovery (ffuf Host header brute-force), API specification hunting (swagger/openapi/graphql introspection), JavaScript source analysis for endpoints (LinkFinder), parameter discovery (Arjun), HTTP method matrix testing, robots.txt/sitemap analysis, error page path disclosure
- **Vertical goals**: Authentication requirement mapping, exact technology version fingerprinting, WAF behavior analysis, cache behavior analysis, cookie/session analysis, CORS policy assessment, input reflection surface mapping, file upload surface assessment, rate limiting behavior, redirect chain analysis, serialized object detection
- **Recursive outputs**: Subdomains in JS files produce `WILDCARD` assets; API base URLs produce new `URL` assets; cloud storage URLs produce `IP_ADDRESS`/`CIDR` assets; redirect destinations produce new `URL` assets

### 4.4 DOMAIN recon workflow (Priority: P1)

- All WILDCARD horizontal and vertical goals apply in full
- Additional: zone transfer attempt (AXFR), full DNS record type enumeration, SPF record full expansion, DKIM selector enumeration, reverse WHOIS for related domains, historical WHOIS and DNS change tracking
- Email spoofing feasibility assessment (SPF/DMARC/DKIM evaluation)
- Subdomain DMARC coverage gap analysis
- CAA record assessment for internal CA trust boundaries
- DNSSEC validation
- **Recursive outputs**: SPF-expanded IP ranges produce `CIDR`/`IP_ADDRESS` assets; MX server hostnames produce `URL`/`IP_ADDRESS` assets; related domains from reverse WHOIS produce new `DOMAIN` assets

### 4.5 IP_ADDRESS recon workflow (Priority: P1)

- **Horizontal goals**: Full TCP port scan (all 65,535 ports via masscan), UDP scan on high-value ports (SNMP, DNS, NTP, IPMI), pre-cached data query (Shodan/Censys), reverse DNS recovery, virtual host enumeration on HTTP ports
- **Vertical goals**: Exact version fingerprinting (nmap -sV), default/weak credential testing per service, SSH assessment (ssh-audit), SNMP full assessment (onesixtyone + snmpwalk), SMB/NetBIOS assessment (smbclient + enum4linux), LDAP assessment (ldapsearch), database port assessment (MySQL, PostgreSQL, MongoDB, Redis, Elasticsearch), IPMI assessment (cipher zero bypass), TLS service assessment (testssl.sh), CVE correlation
- **Recursive outputs**: HTTP/HTTPS services produce `URL` assets; hostnames from rDNS produce `WILDCARD`/`URL` assets; internal IPs from SNMP/LDAP produce `IP_ADDRESS` assets

### 4.6 CIDR recon workflow (Priority: P1)

- **Horizontal goals**: CIDR expansion to flat IP list, high-speed live host discovery (masscan SYN on common ports + ICMP), reverse DNS sweep of entire range, pre-cached intelligence query (Shodan/Censys bulk), ASN and ownership verification
- **Vertical goals**: Full `IP_ADDRESS` goal set applied to every confirmed live host; cross-IP TLS certificate correlation; hostname pattern analysis for naming convention prediction; network topology inference from SNMP/rDNS data
- **Recursive outputs**: Every live host produces `IP_ADDRESS` processing; hostnames produce `WILDCARD`/`URL` processing; HTTP services produce `URL` processing

### 4.7 ANDROID_APP recon workflow (Priority: P2)

- **Horizontal goals**: APK acquisition (apkeep), full decompilation to readable source (jadx), API endpoint extraction from source, AndroidManifest.xml full analysis (exported components, permissions, deep links), third-party SDK and service identification, network traffic capture during runtime (mitmproxy), string and resource file scanning for secrets
- **Vertical goals**: API endpoint testing (full URL goal set), exported component exploitation testing, API key and credential validation, deep link and URI scheme testing, Firebase backend assessment, certificate pinning bypass (Frida), local storage security assessment, WebView security assessment
- **Recursive outputs**: Discovered API hostnames produce `WILDCARD`/`URL` assets; Firebase project IDs produce `URL` assets; third-party service hostnames produce `URL` assets

### 4.8 IOS_APP recon workflow (Priority: P2)

- **Horizontal goals**: IPA acquisition (ipatool), binary string extraction, plist and resource file analysis, framework and library identification, Info.plist full analysis (URL schemes, ATS exceptions), runtime network traffic capture, Objective-C/Swift class and method enumeration
- **Vertical goals**: API endpoint testing, URL scheme handler testing, ATS exception assessment, keychain and local storage assessment, certificate pinning bypass, runtime method hooking (Frida), WKWebView JavaScript bridge assessment
- **Recursive outputs**: API hostnames from binary/plist produce `WILDCARD`/`URL` assets; third-party service endpoints produce `URL` assets

### 4.9 SOURCE_CODE recon workflow (Priority: P2)

- **Horizontal goals**: All branches scanned (not just default), full git commit history including deleted files, all repositories in the organization, employee public forks, associated GitHub gists, dependency and package registry analysis, environment variable name enumeration
- **Vertical goals**: Credential validation against target services, internal hostname and endpoint mapping, infrastructure topology from IaC (Terraform, CloudFormation), dependency vulnerability mapping, CI/CD pipeline security assessment, secrets management maturity assessment, Docker image layer history analysis
- **Recursive outputs**: Internal hostnames produce `WILDCARD`/`URL` assets; cloud resource names produce passive enumeration targets; CI/CD endpoint URLs produce `URL` assets

### 4.10 HARDWARE recon workflow (Priority: P3)

- **Horizontal goals**: Firmware acquisition (vendor site, UART/JTAG, update mechanism), firmware filesystem extraction (binwalk), network interface enumeration, RF interface enumeration
- **Vertical goals**: Hardcoded credential extraction, web interface assessment (full URL goal set), binary vulnerability analysis (OS/kernel/library version mapping), update mechanism security assessment
- **Recursive outputs**: Cloud backend URLs produce `URL` assets; management interfaces produce `URL`/`IP_ADDRESS` assets

### 4.11 Cross-cutting goals (Priority: P0)

- Cloud storage bucket enumeration (S3/GCS/Azure) via naming permutation
- Source code secret scanning across all organization repositories
- Breach credential correlation for valid credential discovery
- Technology stack CVE monitoring for identified software versions
- Scope boundary enforcement — every active action gates on scope validation

### 4.12 Recursive pipeline engine (Priority: P0)

- Implement asset discovery as a queue-based pipeline
- Each asset type produces outputs that get enqueued as new assets
- Deduplication by canonical form (normalized domain, IP:port, URL path)
- Pipeline terminates only when no new asset objects are produced or depth limit reached
- Pivot engine integrates into orchestrator from the start

---

## 5. User experience

### 5.1 Entry points and first-time user flow

1. Ingestion pipeline completes — `bounty_detail` table populated with scoped assets
2. Recon orchestrator reads all `bounty_detail` rows for a given program
3. Asset classification layer routes each scope to the correct workflow
4. Each workflow executes its horizontal goals first, then vertical goals
5. Recursive outputs feed back into the classification layer
6. Pipeline terminates when queue is empty

### 5.2 Core experience

- **Asset classification**: Deterministic routing of each scope type to its workflow. Classification is instant — no LLM cost.
- **Horizontal discovery**: Maximum breadth before depth. Every subdomain, endpoint, port, and service discovered before any detailed analysis begins.
- **Vertical fingerprinting**: Maximum detail extraction from each discovered asset. Technology stack, version, WAF, auth requirements, cache behavior.
- **Recursive loop**: New assets discovered at any stage immediately re-enter the pipeline. The pipeline compounds rather than linearizes.

### 5.3 Advanced features and edge cases

- Wildcard DNS detection and filtering (catch-all responses produce false positives)
- CDN-protected assets trigger origin IP discovery sub-pipeline
- Subdomain takeover detection for dangling CNAME/NS records
- Rate limit awareness — tools must respect target's rate limits
- Scope exclusion enforcement — assets matching `bounty_exclusion` rules are flagged, not tested

### 5.4 UI/UX highlights

- Structured JSON output at every stage for downstream consumption
- Asset inventory with deduplication and canonical normalization
- Evidence store with concrete file paths and tool output references
- Prioritization scoring based on asset type, severity, and bounty eligibility

---

## 6. Narrative

A bug bounty program lists 62 scoped assets across 8 asset types. The recon module classifies each asset, executes the appropriate workflow, and discovers 340 subdomains, 1,200 endpoints, 15 hidden staging environments, 3 subdomain takeover candidates, and 2 exposed databases — all from the initial 62 assets. The recursive loop ensures that every discovered asset feeds back into the pipeline, producing a compounding discovery effect. The final asset inventory is structured, deduplicated, and prioritized for the pentesting module, with every finding traceable to concrete evidence.

---

## 7. Success metrics

### 7.1 User-centric metrics

- Asset discovery coverage: >= 95% of reachable assets discovered per program
- Hidden asset discovery rate: >= 20% of final asset count discovered via recursive outputs (not in initial scope)
- False positive rate: <= 5% of discovered assets are unreachable or out-of-scope
- Time to complete recon per program: <= 15 minutes for standard programs (<= 100 scopes)

### 7.2 Business metrics

- Programs processed per hour: >= 20 (with parallel execution)
- Bounty yield improvement: >= 30% more valid findings per program vs. manual recon
- Scope compliance: 0 out-of-scope interactions per program run

### 7.3 Technical metrics

- Tool execution success rate: >= 98% (failures handled gracefully, logged, and retried where appropriate)
- Deduplication accuracy: 100% (no duplicate assets in final inventory)
- Recursive loop termination: <= 5 iterations before no new assets produced
- LLM rate limit consumption: <= 50% of allocated quota per program (deterministic stages consume zero LLM budget)

---

## 8. Technical considerations

### 8.1 Integration points

- **Database layer**: Read from `bounty_master`, `bounty_detail`, `program_weaknesses`, `bounty_exclusion`. Write to recon-specific tables (asset inventory, fingerprint cache, evidence store). Uses existing `shared/db.py` connection pool and `db.atomic()` transaction pattern.
- **GoalAct loop**: Recon module is invoked by the GoalAct planner. Receives action requests, returns structured results (`CONFIRMED_FINDING`, `CONFIRMED_EMPTY`, `EXECUTION_FAILED`).
- **External tools**: All third-party recon tools (subfinder, httpx, masscan, etc.) invoked as subprocesses. Output parsed and normalized before storage.
- **HackerOne API**: Not called during recon — all program data read from DB (per scope.md persistence decision).
- **Ingestion pipeline**: Recon depends on ingestion being complete and stable. Recon reads from DB tables populated by `ingest.py`. No direct dependency on scraper code.

### 8.2 Data storage and privacy

- All recon data stored in PostgreSQL — same infrastructure as scraping/ingestion
- Tool output cached to avoid redundant execution across programs
- No credentials or sensitive data stored in plaintext — all API keys via environment variables
- Scope exclusions enforced at pipeline level — assets matching exclusion rules are flagged and skipped

### 8.3 Scalability and performance

- Parallel execution across programs (independent transactions)
- Tool execution bounded by timeout (configurable per tool, default 300s)
- DNS resolution rate-limited to avoid triggering target's protective measures
- Port scanning rate-limited to avoid IDS/IPS alerts
- Recursive loop depth-limited (default: 5 iterations) to prevent infinite loops

### 8.4 Technical risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Rate limiting / IP blocking by target | High | High | Configurable per-tool rate limits; passive-first approach; randomized timing |
| Accidental out-of-scope interaction | Low | Critical (program ban) | Scope check gates every active action; assets matching bounty_exclusion flagged and skipped; pre-action validation |
| CDN/WAF blocks active scanning | High | Medium | Origin IP discovery sub-pipeline; WAF fingerprinting before probing |
| Mobile app not publicly available | Medium | Low | Flag and skip; focus on web surface |
| Recursive loop does not terminate | Low | High | Depth limit (5 iterations); queue deduplication; circuit breaker |
| External tool execution failure | Medium | Medium | Retry with backoff; graceful degradation; logged failures |
| LLM rate limit exhaustion | Medium | High | Deterministic stages consume 0% quota; budget allocation per program |
| False positive subdomain takeover | Medium | Medium | Validate against known-takeoverable services; evidence required |
| Firmware acquisition requires physical access | High | Low | Flag and skip; focus on network-accessible surface |
| PostgreSQL connection pool exhaustion under parallel load | Medium | High | Pool max_size=10; parallel programs limited; connection timeout configured |
| Tool version drift breaks output parsers | Medium | Medium | Pin tool versions in requirements; normalize output before parsing; log raw output for debugging |

### 8.5 AI system requirements

**Tool requirements:**
- LLM provider: Cerebras (primary), Groq (fallback) — llama-3.3-70b
- LLM usage: GoalAct planner only. Deterministic stages (classification, tool orchestration, deduplication) use zero LLM budget.
- LLM prompts: Skill files in `skills/recon/` provide context-specific instructions per asset type and stage.
- Skill file selection layer: Deterministic `(asset_type, stage) → [skill_files]` mapping keeps context costs predictable against shared rate limits. No LLM call needed to select which skill file to load.
- Context window: Bounded per iteration. Scratchpad is the planner's sole intra-run memory channel — no side channels for passing state between plan iterations (scope.md §5 GoalAct invariants).

**Evaluation strategy:**
- Benchmark against 10 sample HackerOne programs with manually verified asset inventories
- Measure: asset count vs. manual baseline, hidden asset discovery rate, false positive rate
- Pass criteria (MVP): >= 90% coverage match with manual baseline on benchmark set
- Pass criteria (v1.0): >= 95% coverage match with manual baseline on benchmark set
- Continuous: log asset discovery rates per program; flag programs with < 50% coverage for manual review
- Validation: each benchmark run includes manual review of recursive output quality (are newly discovered assets actually reachable and in-scope?)

**Cost controls:**
- LLM calls capped at 50% of allocated quota per program
- Deterministic stages (classification, deduplication, tool output parsing) never invoke LLM
- Scratchpad context window bounded — full plan rewrite every iteration, no incremental patching
- Skill file size bounded — each file targets a specific (asset_type, stage) pair to minimize context token consumption

---

## 9. Milestones and sequencing

### 9.1 Project estimate

- Large: 6-8 weeks for full implementation

### 9.2 Team size and composition

- 1 developer (Haseeb) with AI assistant support

### 9.3 Suggested phases

**Phase 1: Core Infrastructure (Week 1-2)**
- Asset classification layer
- Recursive pipeline engine (queue-based)
- Deduplication and canonical normalization
- Database schema for recon-specific tables
- Key deliverables: Classification routing, pipeline engine, DB tables

**Phase 2: P0 Workflows (Week 2-4)**
- WILDCARD recon workflow (subdomain enumeration)
- URL recon workflow (crawling, fuzzing, API discovery)
- Cross-cutting goals (cloud storage, secret scanning)
- Key deliverables: WILDCARD and URL workflows operational

**Phase 3: P1 Workflows (Week 4-5)**
- DOMAIN recon workflow (DNS infrastructure, email security)
- IP_ADDRESS recon workflow (port scanning, service fingerprinting)
- CIDR recon workflow (range scanning, live host discovery)
- Key deliverables: DOMAIN, IP_ADDRESS, CIDR workflows operational

**Phase 4: P2/P3 Workflows (Week 5-7)**
- ANDROID_APP recon workflow (APK analysis)
- IOS_APP recon workflow (IPA analysis)
- SOURCE_CODE recon workflow (repo mining, secret scanning)
- HARDWARE recon workflow (firmware analysis)
- Key deliverables: All asset type workflows operational

**Phase 5: Integration and Optimization (Week 7-8)**
- GoalAct integration
- Performance optimization (parallel execution, caching)
- Error recovery and retry mechanisms
- End-to-end testing across sample programs
- Key deliverables: Production-ready recon module

---

## 10. User stories

### 10.1. Classify asset types from scope data

- **ID**: RECON-001
- **Description**: As the recon engine, I want to classify each `bounty_detail.scope_type` into the correct recon workflow so that each asset receives the appropriate reconnaissance treatment.
- **Acceptance criteria**:
  - All 9 asset types are recognized and routed correctly
  - Unknown asset types are logged and flagged (not silently dropped)
  - Classification is deterministic — same input always produces same output
  - Classification completes in < 100ms per asset

### 10.2. Enumerate subdomains from wildcard scope

- **ID**: RECON-002
- **Description**: As the recon engine, I want to discover every subdomain of a wildcard-scoped domain so that no internet-facing asset is missed.
- **Acceptance criteria**:
  - Passive discovery aggregates CT logs, passive DNS, and search engine results
  - Active brute-force uses puredns with quality wordlist
  - Permutation breeding generates variations of discovered subdomains
  - Wildcard DNS detection filters false positives from catch-all responses
  - Each discovered subdomain is deduplicated and normalized

### 10.3. Crawl web application endpoints

- **ID**: RECON-003
- **Description**: As the recon engine, I want to discover every reachable path, endpoint, and parameter on a web application so that the pentesting module has complete coverage.
- **Acceptance criteria**:
  - JS-aware crawling via katana captures JavaScript-rendered content
  - Historical URL recovery via gau and waybackurls finds removed endpoints
  - Directory fuzzing via feroxbuster discovers hidden paths
  - API specification hunting finds swagger/openapi/graphql endpoints
  - JavaScript source analysis extracts all API paths from JS files
  - Parameter discovery via Arjun finds hidden query/body parameters

### 10.4. Discover origin IPs behind CDN

- **ID**: RECON-004
- **Description**: As the recon engine, I want to discover the real server IP behind CDN/WAF protection so that direct origin testing can bypass edge security controls.
- **Acceptance criteria**:
  - Historical DNS records mined for pre-CDN IP addresses
  - Mail server IPs (MX/SPF) checked for shared origin netblock
  - Shodan/Censys cross-referenced for matching TLS certificates
  - Non-CDN subdomains (ftp, smtp, vpn) checked for origin IP
  - Origin IP confidence score assigned based on evidence strength

### 10.5. Detect subdomain takeover candidates

- **ID**: RECON-005
- **Description**: As the recon engine, I want to identify dangling CNAME and NS records pointing to unclaimed resources so that subdomain takeover vulnerabilities are flagged.
- **Acceptance criteria**:
  - CNAME records verified against known-takeoverable services (S3, Heroku, GitHub Pages, Azure)
  - NS delegations checked for unconfigured zones
  - Dangling A records checked for deleted cloud instances
  - Each candidate includes evidence (DNS record, target service, claimability status)

### 10.6. Scan full port range on IP targets

- **ID**: RECON-006
- **Description**: As the recon engine, I want to scan all 65,535 TCP ports on IP targets so that non-standard services are not missed.
- **Acceptance criteria**:
  - Full TCP port scan via masscan completes within timeout
  - UDP scan covers high-value ports (SNMP, DNS, NTP, IPMI)
  - Pre-cached Shodan/Censys data queried before active scanning
  - Each open port classified by service type and version

### 10.7. Extract secrets from source code repositories

- **ID**: RECON-007
- **Description**: As the recon engine, I want to scan all public repositories in the target organization for hardcoded secrets so that valid credentials can be tested against discovered services.
- **Acceptance criteria**:
  - All branches scanned (not just default)
  - Full git history including deleted files scanned
  - All repositories in the organization enumerated
  - Employee public forks scanned
  - Each discovered secret validated against the target service
  - False positives filtered via entropy analysis and known-pattern exclusion

### 10.8. Enumerate mobile app backend surface

- **ID**: RECON-008
- **Description**: As the recon engine, I want to extract every API endpoint, hardcoded key, and configuration detail from mobile app binaries so that the backend attack surface is fully mapped.
- **Acceptance criteria**:
  - APK decompiled via jadx; IPA strings extracted
  - All hardcoded URLs, API keys, and hostnames extracted
  - AndroidManifest.xml / Info.plist fully analyzed
  - Firebase project IDs identified and tested for unauthenticated access
  - Runtime traffic captured via mitmproxy (with pinning bypass if needed)

### 10.9. Enumerate cloud storage buckets

- **ID**: RECON-009
- **Description**: As the recon engine, I want to discover misconfigured cloud storage buckets (S3, GCS, Azure) associated with the target so that public data exposure is flagged.
- **Acceptance criteria**:
  - Bucket names generated from brand name, product names, and discovered subdomains
  - Candidates tested against AWS S3, GCP Cloud Storage, Azure Blob Storage
  - Unauthenticated public read access confirmed before flagging
  - Each discovered bucket includes evidence (URL, access status, sample content)

### 10.10. Enforce scope boundaries during recon

- **ID**: RECON-010
- **Description**: As the recon engine, I want to validate that every active action targets only in-scope assets so that program rules are never violated.
- **Acceptance criteria**:
  - Scope check gates every active reconnaissance action
  - Assets matching `bounty_exclusion` rules are flagged and skipped
  - Out-of-scope interactions logged and blocked
  - Scope validation completes in < 50ms per action

### 10.11. Terminate recursive pipeline when stable

- **ID**: RECON-011
- **Description**: As the recon engine, I want to stop the recursive discovery loop when no new assets are produced so that execution terminates in finite time.
- **Acceptance criteria**:
  - Pipeline terminates when asset queue is empty
  - Depth limit enforced (default: 5 iterations)
  - Each iteration logged with new asset count
  - Termination condition checked after every asset processing cycle

### 10.12. Produce structured output for pentesting module

- **ID**: RECON-012
- **Description**: As the recon engine, I want to produce a structured, deduplicated, prioritized asset inventory so that the pentesting module can consume it directly without transformation.
- **Acceptance criteria**:
  - Output is valid JSON with defined schema
  - All assets deduplicated by canonical form
  - Each asset includes type, hostname/IP, technology stack, WAF status, auth requirements, and priority score
  - Evidence store includes concrete file paths and tool output references
  - Output size bounded (no unbounded growth from recursive loop)

---

## Appendix A: Asset Type Reference

| Asset Type | Definition | Primary Job | Key Tools |
|---|---|---|---|
| WILDCARD | `*.target.com` | Find every subdomain | subfinder, puredns, httpx, shuffledns |
| URL | `https://app.target.com` | Find every endpoint and parameter | katana, feroxbuster, ffuf, Arjun, gau |
| DOMAIN | `target.com` | WILDCARD + DNS infrastructure | dig, dnsx, spf-dig, whois |
| IP_ADDRESS | `1.2.3.4` | Find every service on this machine | masscan, nmap, ssh-audit, testssl.sh |
| CIDR | `1.2.3.0/24` | Find every live host in this range | masscan, fping, dnsx |
| ANDROID_APP | `com.target.app` | Extract all backend surface from APK | jadx, apktool, mitmproxy, Frida |
| IOS_APP | `com.target.app` | Extract all backend surface from IPA | ipatool, strings, mitmproxy, Frida |
| SOURCE_CODE | `github.com/target/repo` | Extract secrets and infrastructure from code | truffleHog, gitleaks, gh CLI |
| HARDWARE | Physical device | Identify interfaces and firmware surface | binwalk, firmware-analysis-toolkit |

## Appendix B: Recursive Discovery Map

```
WILDCARD ──────────────────────────────────────────────────────┐
    │                                                           │
    │ live subdomains                                           │
    ▼                                                           │
   URL ──► JS files ──► new subdomains ──────────────────────► │
    │                                                           │
    │ origin IPs                                                │
    ▼                                                           │
IP_ADDRESS ──► SNMP/LDAP internal IPs ──► new IP_ADDRESS       │
    │                                                           │
    │ HTTP services                                             │
    ▼                                                           │
   URL (again)                                                  │
                                                                │
DOMAIN ──► SPF ranges ──► CIDR ──► live hosts ──► IP_ADDRESS   │
         └──► MX hosts ──► IP_ADDRESS ──► URL                  │
                                                                │
ANDROID_APP ──► API hostnames ──► URL ──────────────────────── ┘
IOS_APP     ──► API hostnames ──► URL
SOURCE_CODE ──► internal hostnames ──► WILDCARD/URL
CIDR ──► all live hosts ──► IP_ADDRESS ──► URL
```

The pipeline terminates when no new asset objects are produced by any active processing cycle. Until that point, every discovered asset is a new input.

## Appendix C: Tool Stack Tiers

**Tier 1 — Must Have (Core Discovery):**
- `subfinder` / `assetfinder` — passive subdomain enumeration
- `httpx` — HTTP probing and tech detection
- `katana` — JS-aware web crawling
- `masscan` / `naabu` — fast port scanning
- `nuclei` — template-based vulnerability detection
- `ffuf` / `feroxbuster` — directory/parameter fuzzing

**Tier 2 — High Value (Depth):**
- `puredns` / `shuffledns` — brute-force DNS resolution
- `gau` / `waybackurls` — historical URL recovery
- `Arjun` / `x8` — hidden parameter discovery
- `truffleHog` / `gitleaks` — secret scanning
- `jadx` / `apktool` — mobile app analysis
- `testssl.sh` / `sslyze` — TLS analysis

**Tier 3 — Advanced (Maximum Coverage):**
- `certstream` — real-time CT log monitoring
- `Shodan` / `Censys` API — passive infrastructure intel
- `Frida` — runtime instrumentation for mobile
- `dnsx` — DNS resolution with full record extraction
- Custom Markov chain generator — intelligent brute-force
