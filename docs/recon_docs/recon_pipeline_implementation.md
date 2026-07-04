Reconnaissance & Attack‑Surface Mapping Pipeline – Revised Hierarchical Design

```
Status: replaces previous linear draft
Key additions: passive OSINT, subdomain enumeration, full‑port scan, WAF fingerprinting, auth/IAM surface discovery, cloud asset enumeration, and feedback‑loop pivoting.
```

1. Stage Overview

Stage	Name	Purpose
Pre‑0	Passive OSINT & Domain Reconnaissance	Build the target’s asset inventory without sending a single packet to the target network.
0	Full‑Spectrum Service Discovery	Resolve, scan (all ports), and verify any reachable service — web, cloud, databases, CI/CD.
1	Infrastructure & Defence Fingerprinting	Identify server stacks, WAF/CDN, cloud providers, and map internal routing.
2	IAM & Authentication Surface Discovery	Locate OAuth, SAML, OIDC, Kerberos endpoints; harvest JWT issuers; detect AD CS.
3	Web Crawl & Endpoint Enumeration	Deep spider, JS extraction, API path discovery.
4	Content & Script Analysis	Secrets, source maps, backup files, postMessage, service workers.
5	WAF Bypass & Injection Surface Probing	WAF fingerprinting → bypass rules → then all injection/exploitation probes.
(loop)	Pivot Engine	Newly discovered hosts/domains re‑enter Pre‑0 or Stage 0.

Every stage only consumes data from earlier stages. The pipeline is still strictly layered, but it now supports feedback for new asset discovery.
2. Pre‑Stage 0 – Passive OSINT & Domain Reconnaissance

Goal: Maximise the known target asset list without touching the target network. All active stages rely on the host list produced here.

Depends on: nothing.
Module	Description
Subdomain enumeration	CT logs (crt.sh / Certstream), passive DNS (SecurityTrails, CIRCL), Markov‑based brute‑force (puredns + shuffledns).
DNS zone transfer attempt	Optional check via AXFR; strictly passive unless authorised.
Cloud asset discovery (passive)	Search for S3 buckets (grayhat warfare, bucket‑finder), Azure resources, GCP buckets via account ID permutations and leaked references.
Code repository scanning	GitHub/GitLab search for organisation repos, secrets, configuration files, and internal hostnames (gitleaks, truffleHog, Shhgit).
Job posting / LinkedIn analysis	Infer internal tools, firewalls, cloud stacks, and programming languages from employee profiles and job descriptions.
Breach credential collection	Harvest (legally/passively) password dumps for credential stuffing later.
Whois & ASN mapping	Map IP ranges and autonomous systems for the target organisation.
Reverse DNS & DNS adjacency	Build IP‑to‑host mappings for owned ranges.
Subdomain takeover detection	Compare A/CNAME records to known unclaimed endpoints (canonical takeover list).

Output:
A set of candidate domains, subdomains, IP ranges, cloud identifiers (bucket names, storage accounts).
All items are fed into Stage 0 for validation and deeper probing.
3. Stage 0 – Full‑Spectrum Service Discovery

Goal: From the candidate list, resolv and scan every target IP on all ports, then classify what is reachable.

Depends on: Pre‑0 asset list.
Module	Description
DNS resolution (A/AAAA)	Bulk resolve all domains/subdomains from Pre‑0.
IP range expansion & deduplication	Convert CIDRs to individual IPs, deduplicate with previous resolutions.
Full TCP port scan	Scan all 65535 ports (or top‑10k‑by‑service) using masscan/naabu.
UDP scan	Lightweight UDP probing for common services (DNS, NTP, SNMP).
Service identification	Banner grab, probe with Nmap NSE service fingerprints.
HTTP/HTTPS verification (raw IP)	Determine which IP:port pairs speak HTTP(S); handle redirects.
Non‑HTTP service tagging	Mark databases (3306, 5432, 27017), S3 (via virtual hosting), Kubernetes (6443), Docker (2375), CI/CD (8080, 9090) with their protocols.

Output:
A list of live services with protocol, banner, IP, port, and domain association.
Web services proceed to Stage 1; cloud/auth services are flagged for parallel Stage 2 and cloud enumeration.
4. Stage 1 – Infrastructure & Defence Fingerprinting

Goal: Understand the technology stack, WAF/CDN presence, and virtual hosting setup.

Depends on: Stage 0 live web origins (and non‑web service info for cloud).
Module	Description
WAF/CDN fingerprinting	Detect Cloudflare, Akamai, AWS WAF via response headers, cookie patterns, error pages, and behaviour. Map rule‑set heuristics.
Web server stack fingerprinting via error pages	Triggers 4xx/5xx pages and analyses response patterns.
HTTP/2 & HTTP/3 fingerprinting	SETTINGS frame analysis, QUIC transport parameters.
Favicon hash technology mapping	Compute favicon hash, query Shodan/Censys.
Virtual host brute‑force (SNI & Host header)	Use subdomain wordlists against each IP to uncover hidden hosts.
Absolute URI injection for proxy mapping	Detect internal proxy/routing logic.
HTTP Host header :port internal fingerprint	Probe back‑end services.
Magic tunnel endpoint enumeration	Find ngrok/Cloudflare Tunnel endpoints.
Cloud asset enumeration (active)	Bucket name permutation, Azure Blob store probing, K8s API server fingerprint, etcd port check, Docker daemon version.
robots.txt / security.txt / humans.txt	Fetch well‑known files.
Backup / staging / dev environment discovery	Subdomain brute‑force and pattern matching.

Why this order:
You need the live origins first, then you can identify what shields them and what runs behind them.
5. Stage 2 – IAM & Authentication Surface Discovery

Goal: Map every authentication entry point. A single SSO bypass can unlock dozens of services.

Depends on: Stage 0 live web origins (and some Stage 1 hostnames).
Module	Description
OpenID Connect discovery	Fetch /.well-known/openid-configuration from all origins.
SAML metadata harvesting	Look for /saml/metadata, entityID in response XML.
OAuth endpoint identification	Detect /oauth/authorize, /oauth/token from JS or well‑known.
JWT issuer discovery	Extract JWT issuers from HTTP responses and JS.
Kerberos SPN enumeration	Check for exposed AD CS web enrollment, LDAP, Kerberos endpoints.
Active Directory CS	Detect certserv pages (AD CS) and enrolment interfaces.
API gateway / management console fingerprinting	Identify Kong, Tyk, WSO2, etc.
Credential‑stuffing surface mapping	Determine login form action, CSRF protections.

Output:
A list of auth endpoints, protocols, and technologies — used later to test bypasses before Stage 5 injection.
6. Stage 3 – Web Crawl & Endpoint Collection

Goal: Collect all URLs, JavaScript files, forms, WebSocket URLs, and redirect chains from the web surface.

Depends on: Stage 0 (live web origins) + any new subdomain/vhosts from Stage 1.
Module	Description
Spider / page enumeration	Headless crawler (Playwright) and fast static link extractor.
JavaScript file collection	Fetch all .js files (including inline extraction).
Form & input field extraction	Record form action, method, input names.
API schema discovery	Swagger/OpenAPI JSON, GraphQL introspection.
Sitemap.xml / RSS feed parsing	Discover additional endpoints.
7. Stage 4 – Content & Script Analysis

Goal: Extract secrets, reverse engineer client‑side logic, and find hidden attack surface.

Depends on: Stage 3 collected data.
Module	Description
JavaScript static analysis for secrets/endpoints	Regex for keys, tokens, internal URLs.
Source map extraction (.js.map)	Recover unminified source.
DOM‑based routing reverse engineering	Single‑page app router discovery.
postMessage & WebSocket analysis	Listener origin checks, WS handshake verification.
WebRTC internal IP disclosure	Gather internal IPs via headless browser.
SSE / WebTransport endpoint discovery	Search for EventSource, WebTransport usage.
Backup & default file exposure	Test common backup extensions on all paths.
.git / .svn exposure	Probe version control directories.
Telemetry DSN harvesting	Sentry, Datadog RUM keys.
CSP / Feature‑Policy / Trusted Types analysis	Re‑analyse with fresh page context for DOM clobbering.
Parameter collection for injection	Compile all parameter names/values from forms, URLs, JSON bodies.
8. Stage 5 – WAF Bypass & Injection Surface Probing

Goal: Actively test injection vulnerabilities only after understanding the WAF and having a bypass strategy.

Depends on: Stage 1 (WAF fingerprint), Stage 4 (parameters), Stage 2 (auth endpoints), Stage 3 (endpoints list).

Sub‑stage 5a – WAF Bypass Engine
Module	Description
WAF‑specific bypass creation	Apply Cloudflare‑centric bypasses (Unicode normalization, HTTP/2 header splitting, request‑line obfuscation) or AWS WAF JSON parser differentials.
Rate‑limit evasion	PoC tests with slowloris or randomised delays.
Rule‑set probing	Determine which payload patterns are blocked, which are allowed.

Sub‑stage 5b – Injection & Exploitation
Module	Description
SSRF blind probe (OOB)	Inject interactsh URLs into parameters, headers, XML/JSON.
XXE / DTD / SVG out‑of‑band	Test for entity expansion and external resource loads.
Cache poisoning (unkeyed headers)	Manipulate cache keys.
Web cache deception	Append static extensions to authenticated URLs.
Request smuggling (CL/TE, H2.CL)	Test with bypass‑aware payloads.
Timing‑based endpoint discovery	Queue‑based timing for internal routes.
OOB file inclusion	UNC path injection.
Auth bypass & privilege escalation	Use discovered IAM endpoints to test token manipulation, JWT key confusion, SAML forgery.
BITB precursor detection	Analyse iframable SSO for phishing chains.
9. Feedback Loop – Pivot Engine

Goal: Any new hostname, IP, or service discovered anywhere in the pipeline re‑enters the workflow.

Implementation:

```
Stage 1 virtual host discovery → new domains → re‑enter Pre‑0 to enrich with passive data, then Stage 0 full scan.

Stage 4 JS‑extracted internal hostnames → add to subdomain list → run Stage 0 scan against them.

Stage 5 SSRF that confirms internal IP → that IP + port is now a known service → feed into Stage 0 for full port scanning and service identification.
```

The pipeline is no longer a single linear sweep but an iterative loop that expands until no new assets are found or a predefined depth is reached.
10. Dependency Graph
text

Pre‑0 (OSINT, subdomain enumeration)
      │
      ▼
Stage 0 (Full‑port scan, service discovery)
      │
      ├──→ Stage 1 (WAF/CDN/cloud fingerprint, vhost brute)
      │        │
      │        ▼
      │   Stage 2 (IAM/Auth surface) ──────────┐
      │        │                               │
      │        ▼                               │
      └──→ Stage 3 (Crawl)                     │
                │                               │
                ▼                               │
           Stage 4 (Script/content analysis)   │
                │                               │
                └───→ Stage 5a (WAF bypass)    │
                         │                     │
                         └→ Stage 5b (Injection/exploit) ←─┘
                                  │
                                  ▼
                           [Pivot Engine] ──→ Pre‑0 / Stage 0 (new assets)

1. Implementation Order
  Pre‑0 – fully passive; can be built immediately.
    Stage 0 – requires Pre‑0 output; now includes full‑port scanning.
    Stage 1 – uses live services; includes cloud and WAF identification.
    Stage 2 – parallel to Stage 1 once web origins are known.
    Stage 3 – uses live web origins from Stage 0.
    Stage 4 – needs Stage 3 data.
    Stage 5a – WAF bypass logic, needs WAF fingerprints from Stage 1.
    Stage 5b – injection tests, needs bypasses and parameters.
    Pivot engine – integrated into the orchestrator from the start; new findings from any stage are queued back.
2. Why This Redesign is Necessary
  No more blind spots: subdomain/cloud/IAM surfaces are now first‑class citizens.
    WAF‑aware: injection tests aren’t blindly launched into a wall.
    Passive‑first: reduces noise and improves targeting before any active packet is sent.
    Self‑healing scope: the pivot engine ensures you never stop at the initial asset list.

This blueprint addresses every gap raised and can be implemented incrementally — each stage can be built and tested in isolation, with a clear interface to the next.
This response is AI-generated, for reference only.