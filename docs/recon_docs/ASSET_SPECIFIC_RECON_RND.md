# Asset-Specific Recon R&D — Maximum Attack Surface Discovery

**Purpose:** Definitive reference document defining the tools, techniques, and decision trees for maximum attack surface discovery per asset type. Pure offensive reconnaissance methodology — no scope/permissions discussion.

**Date:** July 14, 2026

---

## Table of Contents

1. [WILDCARD (Subdomain Enumeration)](#1-wildcard-subdomain-enumeration)
2. [URL (Endpoint Discovery)](#2-url-endpoint-discovery)
3. [DOMAIN (DNS Infrastructure)](#3-domain-dns-infrastructure)
4. [IP_ADDRESS (Service Discovery)](#4-ip_address-service-discovery)
5. [CIDR (Range Scanning)](#5-cidr-range-scanning)
6. [ANDROID_APP (Mobile Recon)](#6-android_app-mobile-recon)
7. [IOS_APP (Mobile Recon)](#7-ios_app-mobile-recon)
8. [SOURCE_CODE (Repository Mining)](#8-source_code-repository-mining)
9. [HARDWARE (Firmware Recon)](#9-hardware-firmware-recon)
10. [Cross-Cutting Techniques](#10-cross-cutting-techniques)
11. [Tool Failure Fallbacks](#11-tool-failure-fallbacks)
12. [Evidence-Driven Decision Framework](#12-evidence-driven-decision-framework)

---

## 1. WILDCARD — Subdomain Enumeration

**Goal:** Discover every subdomain of `*.target.com` — hidden, abandoned, internal-facing.

### Tier 1 — Must Run (Passive, Zero-Touch)

| Technique | Tool | What It Finds | Info Gain |
|-----------|------|---------------|-----------|
| CT Log Mining | `crt.sh`, `certstream` | Every certificate ever issued | **Highest** — certificates are irrevocable, permanently logged |
| Passive DNS | `subfinder` (with 10+ API keys) | Historical DNS records | High — reveals zombie subdomains |
| Search Engine Dorking | `Shodan`, `Censys`, Google dorks | Indexed subdomains | High — finds assets crawlers found but UI doesn't link |
| GitHub/Code Mining | `github-subdomains` | Hardcoded hostnames in repos | High — developers commit internal hostnames |
| Historical URLs | `gau`, `waybackurls`, `waymore` | Old dev/staging environments | High — often left alive |

**Elite move:** Configure `subfinder` and `amass` with EVERY available API key — Shodan, Censys, SecurityTrails, VirusTotal, PassiveTotal, GitHub, BinaryEdge, etc. Most hunters use 2-3; elite use 10+.

### Tier 2 — Active Enumeration

| Technique | Tool | Config | What It Finds |
|-----------|------|--------|---------------|
| DNS Brute-force | `puredns` + `shuffledns` | SecLists `subdomains-top1million-5000.txt` minimum | Subdomains via name testing |
| Permutation Breeding | `gotator`, `mksub`, `DNSGen` | Feed initial findings through permutations | Variations of discovered subdomains |
| Reverse DNS Sweep | `masscan` → `dnsx` | Scan IP ranges, then PTR lookup every live host | Hostnames on target IP ranges |
| Web Content Extraction | `katana` (JS-aware) | Crawl live subdomains, extract all hostnames | Subdomains referenced in JS/HTML |
| Markov Chain Generation | Custom scripts | Analyze naming conventions, generate candidates | Statistically probable names |
| DNS Zone Walking | `nsec3map`, custom | Walk NSEC/NSEC3 chains | All records in DNSSEC zones |

**Elite — Permutation Breeding Workflow:**
1. Passive enumeration → initial list
2. Analyze naming patterns (`dev-api`, `staging-api`, `pre-prod`)
3. `gotator` with target-specific rules
4. `puredns` for resolution
5. Feed new subdomains back into step 2 (recursive)

**Elite — Recursive Discovery:** When `cloud.target.com` is found, treat it as a new root. Run full enumeration on `*.cloud.target.com`. Deeper tree traversal finds `*.prod.cloud.target.com`.

### Tier 3 — Validation & Fingerprinting

| Technique | Tool | Purpose |
|-----------|------|---------|
| HTTP Probing | `httpx` | Confirm live services, extract status/headers/title |
| Visual Fingerprinting | `gowitness`, `aquatone` | Screenshot every live subdomain |
| Wildcard Detection | Custom TTL analysis | Filter catch-all DNS false positives |
| Subdomain Takeover Check | `subjack`, `nuclei` templates | Detect dangling CNAME/NS |
| TLS Certificate Extraction | `httpx` | Infrastructure correlation via cert details |

### Decision Tree

```
Passive enumeration → 50+ subdomains?
  ├─ Yes → HTTP probe all → Any behind CDN? → Origin IP discovery sub-pipeline
  │                        → Any returning 403? → VHost fuzzing
  │                        → Any running GraphQL? → Introspection + Clairvoyance
  ├─ No → Permutation breeding → Re-enumerate
  └─ Feed new discoveries back into WILDCARD pipeline
```

### Recursive Outputs

| Output | Produces | Action |
|--------|----------|--------|
| Live subdomain | `URL` asset | → URL pipeline |
| Origin IP behind CDN | `IP_ADDRESS` asset | → IP pipeline |
| New subdomains from JS crawl | `WILDCARD` asset | → Back into WILDCARD |
| Dangling CNAME/NS | Takeover finding | Flag |

---

## 2. URL — Endpoint Discovery

**Goal:** Every reachable path, endpoint, parameter, hidden functionality on a web app.

### Tier 1 — Crawling & Historical Recovery

| Technique | Tool | What It Finds |
|-----------|------|---------------|
| JS-Aware Crawling | `katana`, `Playwright` | SPA-rendered content, API calls from bundles |
| Headless Browser | `Puppeteer`, `Playwright` | Full DOM after JS execution |
| Wayback/Archive | `waymore` (preferred), `gau` | Every URL ever archived |
| Common Crawl | `gau` | URLs from crawl snapshots |
| URLScan.io | API query | Recently scanned URLs |

**Elite:** Never rely on live site alone. Archive tools find `/api/v1/`, `/debug/`, `/test/` that still respond.

### Tier 2 — Fuzzing & Forced Browsing

| Technique | Tool | Config |
|-----------|------|--------|
| Directory Brute-force | `feroxbuster`, `ffuf` | Target-specific wordlists via `CeWL` |
| File Extension Fuzzing | `ffuf` | `.bak`, `.old`, `.env`, `.config`, `.sql`, `.zip` |
| Virtual Host Fuzzing | `ffuf -H "Host: FUZZ.target.com"` | Hidden apps on same IP |
| Parameter Discovery | `Arjun`, `x8` | Hidden GET/POST parameters |

**Elite — Contextual Wordlists:** `CeWL` crawl target site → combine with SecLists → `ffuf -fs <size>` to filter soft 404s → `ffuf -fc 404,403` for false positives → adjust `-t` for WAF rate limits.

**Elite — Mutation Fuzzing:** Test parameter pollution (`?id=1&id=2`), type switches (`?id=1` vs `?id[]=1`). Often bypass authorization and reveal IDORs.

### Tier 3 — API Discovery & Deep Analysis

| Technique | Tool | What It Finds |
|-----------|------|---------------|
| Spec Hunting | Manual + `ffuf` | `/swagger.json`, `/openapi.json`, `/graphql`, `/docs` |
| GraphQL Introspection | `graphql-cop` | Full schema including hidden mutations |
| GraphQL Reconstruction | `Clairvoyance` | Schema even when introspection disabled |
| gRPC Reflection | `grpcurl` | Service definitions and methods |
| Endpoint Extraction | `LinkFinder`, `JSFind` | API routes in JS bundles |
| Source Map Analysis | Manual | Original source from source maps |

**Elite — GraphQL Attack Surface:** Even with introspection disabled, servers return "Did you mean 'user'?" errors. `Clairvoyance` auto-reconstructs via suggestion attacks. Test query batching, aliases, field-level auth bypass.

### Evidence-Driven Branching

```
Found Content-Type: application/graphql?
  → Trigger GraphQL introspection + Clairvoyance

Found API base path?
  → Spawn new URL asset for that base

Found redirect destination?
  → Spawn new URL asset for target

Found subdomain in JS file?
  → Spawn WILDCARD asset

Found cloud storage URL?
  → Spawn IP_ADDRESS/CIDR asset
```

### Recursive Outputs

| Output | Produces | Action |
|--------|----------|--------|
| Subdomains in JS | `WILDCARD` asset | → WILDCARD pipeline |
| API base URLs | `URL` asset | → Back into URL pipeline |
| Cloud storage URLs | `IP_ADDRESS`/`CIDR` asset | → IP/CIDR pipeline |
| Redirect destinations | `URL` asset | → Back into URL pipeline |

---

## 3. DOMAIN — DNS Infrastructure

**Goal:** Full DNS infrastructure analysis — email security, zone integrity, historical changes.

### Tier 1 — Record Enumeration

| Record Type | Tool | What It Reveals |
|-------------|------|-----------------|
| A/AAAA | `dig`, `dnsx` | IP addresses |
| MX | `dig`, `spf-dig` | Mail servers (often bypass CDN) |
| NS | `dig`, `dnsx` | Nameservers (takeover potential) |
| TXT | `dig`, `dnsx` | SPF, DKIM, verification tokens |
| CAA | `dig` | Certificate authorities |
| SRV | `dig`, `dnsx` | Internal services (Kerberos, LDAP, SIP) — **rarely scanned, often critical** |
| SOA | `dig` | Zone authority, refresh intervals |
| TLSA | `dig` | DANE certificate infrastructure |

**Elite — SRV Record Mining:** SRV records reveal internal services never exposed via A records. These are rarely scanned but often point to critical, older, or internal-facing assets.

### Tier 2 — Email Infrastructure & Zone Integrity

| Technique | Tool | What It Finds |
|-----------|------|---------------|
| Zone Transfer (AXFR) | `dig axfr @ns1.target.com` | Full zone dump (rarely works but worth trying) |
| DNSSEC Zone Walking | `nsec3map` | All records in DNSSEC zones |
| NSEC Walking | Custom scripts | All subdomains in NSEC zones |
| NSEC3 Hash Cracking | Dictionary attacks | Subdomains in NSEC3 zones |
| SPF Record Expansion | Manual analysis | Third-party email providers |
| DKIM Selector Enumeration | `dig` | Specific mail gateways |
| DMARC Policy Analysis | `dig` | Email security maturity |

**Elite — MX-Based Origin Discovery:** Mail servers bypass CDNs entirely. Trigger password reset → analyze `Received`/`Return-Path`/`X-Originating-IP` headers. If mail server shares infrastructure with web server → origin IP found.

### Tier 3 — Historical Analysis

| Technique | Source | What It Reveals |
|-----------|--------|-----------------|
| Passive DNS | SecurityTrails, VirusTotal | Historical IP changes, abandoned infrastructure |
| WHOIS History | DomainTools | Ownership changes, registrant patterns |
| Certificate History | Censys, crt.sh | Infrastructure in TLS certificates |
| Reverse WHOIS | Manual correlation | Related domains under same ownership |

**Elite — Reverse Registration Correlation:** Track domains sharing nameserver architecture, SSL issuer organizations, or WHOIS patterns to find "rogue" or non-public domains.

### Recursive Outputs

| Output | Produces | Action |
|--------|----------|--------|
| SPF-expanded IP ranges | `CIDR`/`IP_ADDRESS` assets | → IP/CIDR pipeline |
| MX server hostnames | `URL`/`IP_ADDRESS` assets | → URL/IP pipeline |
| Related domains | `DOMAIN` assets | → Back into DOMAIN pipeline |

---

## 4. IP_ADDRESS — Service Discovery

**Goal:** Every service, version, and potential vulnerability on a given IP.

### Tier 1 — Passive Intelligence

| Source | What It Reveals |
|--------|-----------------|
| Shodan | Historical port scans, banners, vulnerabilities |
| Censys | Certificate data, service fingerprints |
| SecurityTrails | ASN ownership, historical DNS |
| VirusTotal | Passive DNS, community reports |

**Elite — Certificate Fingerprinting:** Search Shodan/Censys for certificates matching target domain. Certificates reveal infrastructure (CN/SAN) not linked in DNS — hidden servers.

### Tier 2 — Port Scanning & Service Detection

| Technique | Tool | Config |
|-----------|------|--------|
| Full TCP Scan | `masscan` | All 65,535 ports, rate-limited |
| High-Value UDP | `nmap -sU` | Ports 53, 123, 161, 500, 5060 |
| Service Detection | `nmap -sV -sC` | Version detection + default scripts |
| OS Fingerprinting | `nmap -O` | Operating system detection |

**Elite — Timing:** `-T3` or slower for production. Faster = IDS/IPS trigger + DoS.

### Tier 3 — Service Fingerprinting & Credential Testing

| Service | Tool | What It Tests |
|---------|------|---------------|
| SSH | `ssh-audit` | Key exchange, ciphers, compliance |
| SSL/TLS | `testssl.sh`, `sslyze` | Protocols, ciphers, vulnerabilities |
| SNMP | `onesixtyone`, `snmpwalk` | Community strings, MIB enumeration |
| SMB/NetBIOS | `smbclient`, `enum4linux` | Shares, users, policies |
| LDAP | `ldapsearch` | Directory enumeration |
| Databases | `nmap --script` | MySQL, PostgreSQL, MongoDB, Redis, Elasticsearch |
| Default Creds | `hydra`, `Medusa` | SSH, FTP, HTTP Basic Auth, SNMP |

**Elite — VHost Fuzzing:** Many web servers host multiple sites on one IP:
```bash
ffuf -u http://<IP> -H "Host: FUZZ.target.com" -w wordlist.txt
```
Reveals hidden admin portals reachable only with correct Host header.

### Recursive Outputs

| Output | Produces | Action |
|--------|----------|--------|
| HTTP/HTTPS services | `URL` assets | → URL pipeline |
| Hostnames from rDNS | `WILDCARD`/`URL` assets | → WILDCARD/URL pipeline |
| Internal IPs from SNMP/LDAP | `IP_ADDRESS` assets | → Back into IP pipeline |

---

## 5. CIDR — Range Scanning

**Goal:** Every live host and service in an IP range.

### Tier 1 — Range Analysis

| Technique | Tool | Purpose |
|-----------|------|---------|
| CIDR Expansion | Python `ipaddress` | Convert to flat IP list |
| ASN Verification | `whois`, SecurityTrails | Confirm range ownership |
| Cloud Provider Detection | `nmap --script ip-geolocation` | Identify AWS/GCP/Azure ranges |

### Tier 2 — Live Host Discovery

| Technique | Tool | Config |
|-----------|------|--------|
| SYN Scan | `masscan` | Common ports (80, 443, 22, 21, 25, 8080, 8443) |
| ICMP Sweep | `fping -a -g <CIDR>` | Live host detection |
| Reverse DNS | `dnsx` | PTR records for entire range |

### Tier 3 — Cross-IP Correlation

| Technique | What It Reveals |
|-----------|-----------------|
| TLS Certificate Correlation | IPs sharing same cert → same infrastructure |
| Hostname Pattern Analysis | Naming conventions for prediction |
| Network Topology Inference | SNMP/rDNS → internal network structure |

### Recursive Outputs

| Output | Produces | Action |
|--------|----------|--------|
| Every live host | `IP_ADDRESS` processing | Full IP pipeline |
| Hostnames from rDNS | `WILDCARD`/URL processing | → WILDCARD/URL pipeline |
| HTTP services | `URL` processing | → URL pipeline |

---

## 6. ANDROID_APP — Mobile Recon

**Goal:** Every API endpoint, hardcoded secret, configuration detail from APKs.

### Tier 1 — Acquisition & Static Analysis

| Technique | Tool | What It Finds |
|-----------|------|---------------|
| APK Acquisition | `apkeep`, APKPure, Aurora Store | The APK |
| Decompilation | `jadx` | Full Java/Kotlin source |
| Manifest Analysis | `jadx` | Exported components, permissions, deep links |
| String Extraction | `strings`, `jadx` | Hardcoded URLs, API keys, hostnames |
| Secret Scanning | `truffleHog`, regex | AWS keys, tokens, passwords |
| Firebase Detection | `jadx` | Firebase project IDs |
| SDK Identification | `jadx` | Third-party libraries |

**Elite — Exported Components:** AndroidManifest.xml reveals exported Activities/Services/Receivers (no permission required), deep links, URI schemes, custom permissions, backup configs.

### Tier 2 — Dynamic Analysis

| Technique | Tool | What It Finds |
|-----------|------|---------------|
| Traffic Interception | `mitmproxy` + Frida | All API calls during runtime |
| Certificate Pinning Bypass | `objection`, custom Frida scripts | Hidden API endpoints |
| Runtime Hooking | `Frida` | Method arguments, return values, memory |
| Local Storage Inspection | `adb` | SharedPreferences, SQLite databases |

### Recursive Outputs

| Output | Produces | Action |
|--------|----------|--------|
| API hostnames | `WILDCARD`/`URL` assets | → WILDCARD/URL pipeline |
| Firebase project IDs | `URL` assets | → URL pipeline |
| Third-party service hostnames | `URL` assets | → URL pipeline |

---

## 7. IOS_APP — Mobile Recon

**Goal:** Every API endpoint, hardcoded secret, configuration detail from IPAs.

### Tier 1 — Acquisition & Static Analysis

| Technique | Tool | What It Finds |
|-----------|------|---------------|
| IPA Acquisition | `ipatool`, iTunes | The IPA |
| String Extraction | `strings`, `Hopper` | Hardcoded URLs, API keys |
| Plist Analysis | `plutil`, manual | URL schemes, ATS exceptions |
| Framework Analysis | `otool`, `jtool` | Linked libraries |
| Info.plist Analysis | Manual | URL schemes, universal links, associated domains |
| ObjC/Swift Enumeration | `class-dump`, `Hopper` | Classes, methods, selectors |

**Elite — iOS-Specific Surfaces:** App Extensions (widgets, share extensions) have different entitlements. Universal Links reveal backend infrastructure. Keychain flags (`kSecAttrAccessibleAlways`) expose sensitive data. ATS exceptions reveal insecure endpoints.

### Tier 2 — Dynamic Analysis

| Technique | Tool | What It Finds |
|-----------|------|---------------|
| Traffic Interception | `mitmproxy` + Frida | All API calls |
| Pinning Bypass | `objection`, `SSL Kill Switch` | Hidden endpoints |
| Runtime Hooking | `Frida` | Method arguments, return values |
| Keychain Dump | `keychain-dump` | Stored credentials |

### Recursive Outputs

| Output | Produces | Action |
|--------|----------|--------|
| API hostnames from binary/plist | `WILDCARD`/`URL` assets | → WILDCARD/URL pipeline |
| Third-party service endpoints | `URL` assets | → URL pipeline |

---

## 8. SOURCE_CODE — Repository Mining

**Goal:** Secrets, internal hostnames, infrastructure details from repos.

### Tier 1 — Org Enumeration & Secret Scanning

| Technique | Tool | What It Finds |
|-----------|------|---------------|
| GitHub Org Enumeration | `gh CLI`, `theHarvester` | All repos in organization |
| Employee Fork Discovery | GitHub search | Personal forks of private repos |
| Gist Scanning | GitHub API | Code snippets with secrets |
| Current Code Secrets | `truffleHog`, `gitleaks` | Hardcoded secrets |
| Git History Secrets | `truffleHog`, `gitleaks` | Secrets deleted in previous commits |
| Branch Scanning | Custom scripts | Secrets only in feature branches |

**Elite — Full Git History:** Secrets deleted in a commit remain accessible unless purged via `git filter-repo`. ALWAYS scan entire commit history.

**Elite — Entropy Analysis:** High-entropy strings (Shannon > 4.5) that match no known pattern may be API keys, tokens, or passwords.

### Tier 2 — Infrastructure Extraction

| Technique | What It Reveals |
|-----------|-----------------|
| IaC File Analysis | Terraform, CloudFormation, Ansible → cloud infrastructure |
| Dockerfile Analysis | Base images, exposed ports, environment variables |
| CI/CD Config Analysis | Jenkinsfile, GitHub Actions → deployment targets |
| Config File Analysis | Internal hostnames, API endpoints, DB connection strings |

### Recursive Outputs

| Output | Produces | Action |
|--------|----------|--------|
| Internal hostnames | `WILDCARD`/`URL` assets | → WILDCARD/URL pipeline |
| Cloud resource names | Passive enumeration targets | → Cloud pipeline |
| CI/CD endpoint URLs | `URL` assets | → URL pipeline |

---

## 9. HARDWARE — Firmware Recon

**Goal:** Firmware, interfaces, attack surfaces on physical devices.

### Tier 1 — Firmware Acquisition & Analysis

| Technique | Tool | What It Finds |
|-----------|------|---------------|
| Firmware Download | Vendor websites, update APIs | The firmware image |
| Filesystem Extraction | `binwalk` | Internal filesystem structure |
| Hardcoded Credentials | `strings`, regex | Default passwords, API keys |
| Binary Analysis | `Ghidra`, `IDA Pro` | Vulnerable functions, logic flaws |
| Version Mapping | `cve-search` | Known CVEs for identified versions |

### Tier 2 — Network Interface Discovery

| Technique | What It Reveals |
|-----------|-----------------|
| Network Interface Enumeration | Available interfaces and configurations |
| Management Interface Discovery | Web UIs, SSH, Telnet endpoints |
| Default Credential Testing | Factory default passwords |

### Recursive Outputs

| Output | Produces | Action |
|--------|----------|--------|
| Cloud backend URLs | `URL` assets | → URL pipeline |
| Management interfaces | `URL`/`IP_ADDRESS` assets | → URL/IP pipeline |

---

## 10. Cross-Cutting Techniques

**Run these in parallel with ALL asset-specific pipelines.**

### 10.1 Cloud Storage Enumeration

| Technique | Tool | What It Finds |
|-----------|------|---------------|
| Bucket Name Permutation | `cloud_enum`, custom | S3/GCS/Azure buckets |
| CT Log Mining | `crt.sh` | Subdomains hinting at bucket names |
| Code Mining | `truffleHog`, manual | Hardcoded bucket names |

**Elite — Permutation Strategy:** Combine company name + keywords (`company-backups`, `company-dev-assets`) → use discovered subdomains as candidates → `cloud_enum` for public read/list → check CORS misconfig.

### 10.2 Cloud Infrastructure Discovery

| Technique | What It Reveals |
|-----------|-----------------|
| Metadata Endpoint Discovery | SSRF → cloud credentials (IMDSv1/v2) |
| Lambda/Serverless Discovery | Function URLs, API Gateway endpoints |
| Kubernetes Discovery | Exposed API servers, dashboards, registries |
| CI/CD Discovery | Jenkins, GitHub Actions workflows, deployment secrets |

### 10.3 Protocol-Level Techniques

| Technique | Tool | Why It Matters |
|-----------|------|----------------|
| WebSocket Enumeration | `wscat`, custom | Persistent connections bypass WAF signatures |
| HTTP/2 Server Push Analysis | Manual | Can reveal hidden endpoints |
| HTTP/3 (QUIC) Discovery | `nmap --script` | Emerging protocol, often misconfigured |
| DNS over HTTPS Enumeration | `dnsx` with DoH resolvers | Bypasses traditional DNS monitoring |
| Server-Sent Events | Manual | Hidden data streams |

### 10.4 Application-Layer Analysis

| Technique | Tool | Why It Matters |
|-----------|------|----------------|
| CORS Misconfiguration | `corsy`, custom | Reveals trusted origins and bypass potential |
| CSP Header Analysis | Manual | Reveals allowed sources, inline scripts, bypasses |
| Subresource Integrity Check | Manual | Missing SRI = supply chain attack surface |
| HTTP Request Smuggling | `smuggler` | HTTP/1.1 vs HTTP/2 parsing differences |
| Web Cache Deception | Manual | Cache poisoning via path manipulation |
| SSTI Detection | `nuclei` templates | Detect template engines from error messages |

### 10.5 Authentication/Authorization Recon

| Technique | Tool | Why It Matters |
|-----------|------|----------------|
| OAuth/SAML Endpoint Discovery | Manual + `ffuf` | Identity providers are high-value targets |
| JWT Endpoint Analysis | `jwt_tool` | Token endpoints, JWKS endpoints |
| Session Management Analysis | Manual | Cookie flags, token rotation |
| API Key Scope Analysis | Target-specific | What permissions does the key actually have? |

### 10.6 Infrastructure Recon

| Technique | Tool | Why It Matters |
|-----------|------|----------------|
| VPN Gateway Detection | `nmap` + custom | Cisco AnyConnect, OpenVPN, WireGuard — often unpatched |
| Load Balancer Fingerprinting | `nmap`, manual | Apache, Nginx, HAProxy, F5 detection |
| Reverse Proxy Detection | `X-Forwarded-For`, `X-Real-IP` analysis | Origin IP leakage |
| CDN Edge vs Origin Detection | Header analysis + timing | Beyond "is it behind CDN" |
| Container Escape Surface | Manual | Docker socket, Kubernetes API exposure |

---

## 11. Tool Failure Fallbacks

| Primary Tool | Failure Mode | Fallback |
|--------------|--------------|----------|
| `subfinder` | Timeout | `amass` (passive mode), `assetfinder` |
| `masscan` | Rate-limited | `nmap -T4 --top-ports 1000` (slower but reliable) |
| `httpx` | False positives (soft 404s) | `ffuf -fs <size>` to filter, manual verification |
| `puredns` | DNS resolver blocks | Rotate resolvers, use `dnsx` with DoH |
| `katana` | JS-heavy SPA | Playwright headless browser |
| `jadx` | APK obfuscation | `apktool` + manual string extraction |
| `nuclei` | Template misses | Custom nuclei templates, manual testing |

---

## 12. Evidence-Driven Decision Framework

Every action must answer: **"What new information will this provide?"**

| Finding | Triggers |
|---------|----------|
| Subdomain behind CDN | → Origin IP discovery sub-pipeline |
| HTTP 403 response | → VHost fuzzing + auth bypass testing |
| GraphQL endpoint | → Introspection + `Clairvoyance` schema reconstruction |
| API base path | → Parameter fuzzing + spec hunting |
| Cloud storage URL | → Bucket enumeration + CORS testing |
| VPN endpoint | → Credential testing + version mapping |
| WebSocket endpoint | → Real-time data interception |
| OAuth/SAML endpoint | → Token analysis + flow testing |
| High entropy string in code | → Credential validation against services |
| IaC config file | → Cloud resource enumeration |
| Exported Android component | → Deep link + URI scheme testing |

---

## Appendix: Tool Tiers Summary

### Tier 1 — Core Discovery (Must Have)
- `subfinder` — Passive subdomain enumeration
- `httpx` — HTTP probing and tech detection
- `katana` — JS-aware web crawling
- `masscan` / `naabu` — Fast port scanning
- `nuclei` — Template-based vulnerability detection
- `ffuf` / `feroxbuster` — Directory/parameter fuzzing
- `dnsx` — DNS resolution with full record extraction

### Tier 2 — High Value (Depth)
- `puredns` / `shuffledns` — Brute-force DNS resolution
- `gau` / `waymore` — Historical URL recovery
- `Arjun` / `x8` — Hidden parameter discovery
- `truffleHog` / `gitleaks` — Secret scanning
- `jadx` / `apktool` — Mobile app analysis
- `testssl.sh` / `sslyze` — TLS analysis

### Tier 3 — Advanced (Maximum Coverage)
- `certstream` — Real-time CT log monitoring
- `Shodan` / `Censys` API — Passive infrastructure intel
- `Frida` — Runtime instrumentation for mobile
- `gotator` / `mksub` — Permutation generation
- `Clairvoyance` — GraphQL schema reconstruction
- `cloud_enum` — Cloud storage enumeration
- Custom Markov chain generator — Intelligent brute-force

---

## Evidence

- Research compiled from: elite bug bounty methodologies, projectdiscovery, OWASP, PTES
- Tool documentation: projectdiscovery suite, SecLists, OWASP testing guide
- Critical analysis: `docs/recon_docs/RND_CRITICAL_ANALYSIS.md`
- Architecture principles: `ai-agent-workspace/AGENTS/network-security-architect.md`
