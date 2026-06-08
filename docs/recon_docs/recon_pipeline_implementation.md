# Recon Pipeline – Hierarchical Stage Design

This document defines the **implementation hierarchy** for a large‑scale web reconnaissance and attack‑surface mapping pipeline.  
It follows a strict top‑down dependency model: each stage only uses data produced by earlier stages, eliminating circular dependencies and enabling incremental development.

---

## Overview of Stages

| Stage | Name | Description |
|-------|------|-------------|
| **0** | Live Web Service Discovery | DNS resolution, port scanning, HTTP/HTTPS verification – outputs **live origins** (protocol://host:port). |
| **1** | Host & Infrastructure Fingerprinting | Server identity, virtual‑host brute‑forcing, tunnel/service enumeration using only the base live origin. |
| **2** | Header & Protocol Baseline Checks | Method/verb probing, request smuggling, CORS, COOP, CSP, and other header‑level checks without needing any crawled paths. |
| **3** | Crawling & First‑Pass Endpoint Collection | Deep spider / static crawl to collect all HTML, JavaScript, API endpoints, and forms. |
| **4** | Content, Script & Endpoint‑Driven Analysis | JavaScript static analysis, source maps, backup files, postMessage, service workers, telemetry harvesting – everything that requires **crawled endpoints**. |
| **5** | Injection & Exploitation Probing | SSRF, cache poisoning, XXE, timing attacks, etc. – techniques that inject into parameters or headers identified in earlier stages. |

Each stage is **self‑contained** and produces data consumable by the next.  
No module is built until its dependencies (earlier stages) are fully implemented.

---

## Stage 0 – Live Web Service Discovery

**Goal:** Convert domain names / IPs into a clean list of **live HTTP/HTTPS origins** (canonical base URLs).  

### Modules

| # | Technique | Dependencies | Why |
|---|-----------|--------------|-----|
| — | DNS resolution (A records) | None | Starting point – all subsequent work requires an IP. |
| — | TCP port scanning (common web ports) | DNS resolution | Need an IP before you can test ports. |
| — | HTTP/HTTPS verification (raw IP) | Open ports | Confirms a web server actually speaks HTTP(S) on that port; produces canonical origin after redirects. |

**Output:**  
A deduplicated list of origins, e.g. `http://1.2.3.4:8080`, `https://example.com`.  
Stage 1 begins its work using exactly these origins.

---

## Stage 1 – Host & Infrastructure Fingerprinting

**Goal:** Gather server technology, hidden virtual hosts, and infrastructure details using only the base origin (no crawled paths).  

All modules below depend on **Stage 0 (live origin)** – they must have a confirmed web endpoint to probe.

| # | Technique | Depends on | Why |
|---|-----------|------------|-----|
| 1 | Web server stack fingerprinting via error pages | Stage 0 | Sends crafted requests that trigger 4xx/5xx pages; needs a live server. |
| 2 | HTTP/2 SETTINGS frame fingerprint | Stage 0 | Must open an HTTP/2 connection to the origin. |
| 3 | HTTP/3 QUIC transport parameter analysis | Stage 0 | Requires a QUIC handshake with the origin. |
| 4 | Favicon hash technology fingerprinting | Stage 0 | Fetches `/favicon.ico` from the origin. |
| 5 | Browser devtools debug port exposure | Stage 0 | Probes the host’s IP on ports 9222/9229 – no HTTP path needed, but needs an IP. |
| 6 | Host Header / TLS SNI virtual host brute‑force | Stage 0 | Re‑uses the origin IP to test alternate Host names (SNI / HTTP Host). |
| 7 | HTTP Host header `:port` internal fingerprint | Stage 0 | Mutates the Host header on the same origin; only needs a live socket. |
| 8 | Absolute URI injection for proxy mapping | Stage 0 | Sends `GET http://internal-host/` to the origin to detect proxy behaviour. |
| 9 | Magic tunnel endpoint enumeration | Stage 0 (domain name) | Constructs subdomains of known tunnel services; needs the target’s base domain. |
| 44 | Backup, staging, dev, UAT environment discovery | Stage 0 (domain name) | Brute‑forces subdomains like `staging.`, `dev.`; only needs DNS. |
| 25 | robots.txt / security.txt / humans.txt analysis | Stage 0 | Fetches well‑known files from the root of the origin (`/robots.txt`). |

**Why Stage 1 first?**  
None of these techniques depend on crawled pages or extracted endpoints. They can run as soon as you have the live base URL.

---

## Stage 2 – Header & Protocol Baseline Checks

**Goal:** Extract every piece of information the server exposes on the root or a dummy request, and probe protocol‑level behaviour.

These modules still only need the **base origin from Stage 0** – no path discovery required.

| # | Technique | Depends on | Why |
|---|-----------|------------|-----|
| 11 | HTTP method enumeration & override probing | Stage 0 | Sends OPTIONS / PUT / DELETE to root; root is enough. |
| 12 | WebDAV OPTIONS & PROPFIND probing | Stage 0 | Probes root or a single well‑known path. |
| 13 | HTTP request smuggling detection (CL/TE, H2.CL) | Stage 0 | Exploits proxy‑server interaction on any live endpoint. |
| 14 | HTTP desync via hop‑by‑hop header abuse | Stage 0 | Same as smuggling; works on any live endpoint. |
| 16 | COOP/COEP bypass assessment | Stage 0 | Parses response headers from the root page. |
| 34 | Cache‑poisoning vector identification (unkeyed headers) | Stage 0 | Probes caching behaviour on any resource; root is fine. |
| 36 | CSP nonce/hash/report‑uri mapping | Stage 0 | Reads `Content-Security-Policy` header from the root. |
| 37 | Cross‑domain policy file crawl | Stage 0 | Fetches `/crossdomain.xml` and `/clientaccesspolicy.xml` from root. |
| 40 | MIME sniffing & X‑Content‑Type‑Options bypass | Stage 0 | Checks response headers and content‑type behaviour on root. |
| 42 | Feature‑Policy / Permissions‑Policy mis‑scoping | Stage 0 | Parses `Permissions-Policy` header from root. |
| 41 | CSP report‑uri / report‑to endpoint data leakage | Stage 0 | Extracts reporting endpoints from CSP header; can test further later. |

**Why Stage 2 before crawling?**  
These are lightweight request‑response inspections that do not rely on knowing any internal paths. Doing them early provides critical context (e.g., CSP rules) for later stages and avoids wasting time on paths that are already blocked.

---

## Stage 3 – Crawling & First‑Pass Endpoint Collection

**Goal:** Perform a deep crawl (headless or fast static) to collect all internal links, JavaScript files, form actions, WebSocket URLs, redirect chains, etc.  

### Modules

| # | Technique | Depends on | Why |
|---|-----------|------------|-----|
| — | Spider / page enumeration | Stage 0 (origins) | Navigates pages, extracts anchors, scripts, forms. Foundation for all stages below. |

**Output:**  
A list of discovered **URLs, JS sources, API endpoints, and forms** – fed directly into Stage 4.

---

## Stage 4 – Content, Script & Endpoint‑Driven Analysis

**Goal:** Deep dive into client‑side code, hidden endpoints, backup files, and configuration leaks – everything that depends on the crawled data.

| # | Technique | Depends on | Why |
|---|-----------|------------|-----|
| 10 | Internal URL shortener & redirect inference | Stage 3 (crawled links, redirects) | Identifies short‑URL patterns and follows redirect chains found during crawling. |
| 15 | CORS misconfiguration crawl | Stage 3 (list of endpoints) | Sends cross‑origin requests to every discovered endpoint to test CORS headers. |
| 17 | postMessage origin wildcard enumeration | Stage 3 (loaded pages) | Requires headless loading of pages to capture `onmessage` listeners. |
| 18 | WebSocket handshake origin bypass & hijacking | Stage 3 (WebSocket URLs) | Needs WebSocket endpoints extracted from JavaScript or crawl. |
| 19 | WebRTC internal IP disclosure | Stage 3 (any page) | Loads a page to execute WebRTC ICE gathering; just needs one page. |
| 20 | SSE & WebTransport endpoint discovery | Stage 3 (JavaScript files) | Searches for `EventSource` and `WebTransport` in JS collected from crawling. |
| 21 | JavaScript static analysis for secrets/endpoints | Stage 3 (JS files) | Directly processes all downloaded `.js` files. |
| 22 | Source map extraction (`.js.map`) | Stage 3 (JS file URLs) | Fetches `.map` for each JavaScript file discovered. |
| 23 | DOM‑based routing & client‑side template reverse engineering | Stage 3 (loaded pages) | Headless analysis of single‑page app routers; needs a page to render. |
| 24 | PWA service worker scope & cache enumeration | Stage 3 (page context) | Executes JS on a loaded page to inspect `navigator.serviceWorker`. |
| 26 | Parameter discovery (initial collection) | Stage 3 (crawled URLs, forms) | Extracts query and body parameters from URLs and form elements; later used for fuzzing. |
| 27 | Backup & default file exposure | Stage 3 (discovered directories/paths) | Appends `~`, `.bak`, `.swp` to every found path. |
| 28 | Log file & crash dump exposure | Stage 3 (paths) | Probes common log file names under discovered directories. |
| 29 | `.git` / `.svn` / `.hg` / `.bzr` exposure | Stage 3 (paths) | Tests `/.git/config`, `/.svn/entries` on all base directories. |
| 30 | Directory listing & mod_status/mod_info exposure | Stage 3 (paths) | Checks `Directory listing` on discovered folders; also probes standard diagnostic paths. |
| 31 | Telemetry, crash‑report & error‑tracking endpoint harvesting | Stage 3 (JS files) | Regex‑parses JavaScript for Sentry DSNs, Datadog RUM keys. |
| 38 | CSS injection & attribute selector exfiltration (surface detection) | Stage 3 (reflected parameters from forms/links) | Needs an injection point to start testing; identifies candidate reflected inputs. |
| 39 | Trusted‑type policy & DOM clobbering surface | Stage 3 (page DOM & CSP from Stage 2) | Walks the DOM looking for `id` attributes that shadow globals; needs CSP already parsed. |
| 47 | BITB precursor detection | Stage 3 (loaded pages) | Analyzes OAuth/SSO popups, iframe behaviour on discovered pages. |
| 43 | Registration & account creation flow verb‑injection surface | Stage 3 (registration forms/endpoints) | Re‑plays registration request with different HTTP methods; needs the endpoint URL. |

**Why after crawling?**  
All these modules require either specific URLs discovered during crawling or the JavaScript source that the crawl fetches.

---

## Stage 5 – Injection & Exploitation Probing

**Goal:** Actively inject payloads to trigger out‑of‑band callbacks, cache manipulation, and timing attacks using parameters and endpoints gathered in Stages 3‑4.

| # | Technique | Depends on | Why |
|---|-----------|------------|-----|
| 32 | SSRF blind probe (OOB callbacks) | Stage 4 (parameters to inject) | Needs a set of URL/domain‑valued parameters from discovery or crawling. |
| 33 | OOB resource load probe (XXE, DTD, SVG) | Stage 4 (XML/JSON endpoints) | Requires endpoints that parse XML/JSON where an external entity can be injected. |
| 35 | Web cache deception | Stage 4 (authenticated‑seeming endpoints) | Needs authenticated‑looking URLs (e.g., `/profile`) to try static extension trick. |
| 45 | Request queue‑based timing attack | Stage 3 (endpoint list) | Probes for the existence of internal endpoints by measuring queue timing; uses a list of candidate paths. |
| 46 | OOB file inclusion via SMB/WebDAV/HTTP | Stage 4 (file‑path parameters) | Replaces file paths with UNC paths to test remote file inclusion; needs file‑path parameters. |
| 48 | Browser GPU/CSS side‑channel (cross‑origin inference) | Stage 3 (interesting cross‑origin URLs) | Requires a target URL whose existence you want to infer; uses timing from a page. |

**Why Stage 5 last?**  
These techniques are active and riskier; they depend on a thorough mapping of injectable parameters, endpoints, and behaviours collected in previous stages.

---

## Dependency Graph (Simplified)

Stage 0 – Live Origin
│
├──→ Stage 1 – Fingerprint (vhosts, favicon, tunnels…)
│
└──→ Stage 2 – Header Baseline (methods, smuggling, CSP…)
│
▼
Stage 3 – Crawl (endpoints, JS, forms)
│
└──→ Stage 4 – Script/Content Analysis (secrets, backups, postMessage…)
│
└──→ Stage 5 – Injection Exploitation (SSRF, cache poison, timing…)
text


**No module may reference any output from a later stage.** This guarantees that the pipeline can be implemented, tested, and executed incrementally.

---

## Implementation Order

1. **Stage 0** – entirely self‑contained.  
2. **Stage 1** – uses only Stage‑0 output.  
3. **Stage 2** – uses only Stage‑0 output (can run in parallel with Stage 1).  
4. **Stage 3** – needs Stage‑0 live origins; runs after 1+2 complete (or concurrently if careful).  
5. **Stage 4** – consumes Stage‑3 data (and optionally Stage‑2 headers).  
6. **Stage 5** – consumes Stage‑4 parameters and Stage‑3 endpoint lists.

Stages 1 and 2 are independent of each other and can be developed in parallel once Stage 0 is ready.

---

## Notes for Implementation

- **External tools** (ffuf, subfinder, smuggler, etc.) can be wrapped as sub‑processes; the pipeline always normalises their output into a common JSON/line format.
- **Headless browser** (Playwright) is required for Stage 3+ modules dealing with client‑side JavaScript.
- **Out‑of‑band callback server** (e.g., interactsh) is needed for Stage 5 probes.
- **Rate limiting and concurrency** controls must be applied at every stage to avoid overwhelming targets.

This document can now serve as your development roadmap. You can implement each stage in sequence and be confident that no module will be blocked by missing dependencies.