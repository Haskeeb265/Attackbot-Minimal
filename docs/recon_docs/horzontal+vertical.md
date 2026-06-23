# HackerOne Target Coverage Goals
## Maximum Horizontal & Vertical Depth Reference

---

## How to Read This Document

**Horizontal depth** — How wide can you go? Finding every asset, subdomain, endpoint, or
service that belongs to the target. Breadth of discovery.

**Vertical depth** — How deep can you go on each discovered thing? Extracting maximum
detail, fingerprinting, classifying, and understanding what each asset exposes.

**Recursive outputs** — Every target type produces new asset objects during analysis.
Those objects re-enter the pipeline as new targets. This is what makes coverage
compounding rather than linear.

```
Input Asset
    │
    ├── Horizontal Goals ──► find every X that exists
    │
    ├── Vertical Goals ────► extract maximum detail from each X
    │
    └── Recursive Outputs ─► new asset objects ──► back to pipeline top
```

**A note on ordering**: Always exhaust horizontal goals before vertical.
You cannot achieve maximum vertical depth on an incomplete asset inventory.

---

## Asset Type Index

| Type | Definition | Primary Job |
|---|---|---|
| WILDCARD | `*.target.com` | Find every subdomain |
| URL | `https://app.target.com` | Find every endpoint and parameter |
| DOMAIN | `target.com` | WILDCARD + DNS infrastructure |
| IP_ADDRESS | `1.2.3.4` | Find every service on this machine |
| CIDR | `1.2.3.0/24` | Find every live host in this range |
| ANDROID_APP | `com.target.app` | Extract all backend surface from APK |
| IOS_APP | `com.target.app` | Extract all backend surface from IPA |
| SOURCE_CODE | `github.com/target/repo` | Extract secrets and infrastructure from code |
| HARDWARE | Physical device | Identify interfaces and firmware surface |

---

## Asset Type 1 — WILDCARD (`*.target.com`)

**What it is**: Any subdomain of `target.com` is in scope. The entire job of
this asset type is finding every subdomain that exists, then feeding each live one
into URL processing.

---

### Horizontal Goals — Find every subdomain that exists

**G1.1 — Passive aggregation from all sources**
Query every third-party database that has cached subdomain records: passive DNS
archives, threat intelligence feeds, certificate transparency logs, search engine
indexed results, virus scanning reports, and DNS history services. No requests
go to the target — pure passive.

**G1.2 — Certificate Transparency log mining**
Every TLS certificate issued for any subdomain is logged publicly within seconds
of issuance. Query CT logs for `%.target.com` to recover every subdomain that
has ever received a certificate, including historical ones no longer in DNS.

**G1.3 — Real-time CT log monitoring**
Subscribe to live CT log streams and alert the moment a new certificate is issued
for any subdomain of the target. New subdomains discovered this way are often
not yet hardened.

**G1.4 — DNS brute-force with quality wordlist**
Systematically test millions of potential subdomain names against the target's
DNS resolvers. Wordlist must cover technology naming patterns (`api`, `dev`,
`staging`, `admin`, `internal`), environment patterns (`prod`, `test`, `uat`,
`qa`), and regional patterns (`us`, `eu`, `ap`).

**G1.5 — Permutation and alteration breeding**
Take every already-discovered subdomain and generate variations:
- `api.target.com` → `api-v2`, `api-dev`, `api01`, `api-staging`
- `app.target.com` → `app2`, `app-beta`, `app-internal`
Run all permutations through DNS resolution.

**G1.6 — Reverse DNS sweep on target IP ranges**
Once any IP is associated with the target, sweep surrounding IPs with reverse
DNS lookups. Many subdomains are discoverable only this way because they never
appear in any public database.

**G1.7 — Extract subdomains from discovered web content**
JavaScript files, HTML responses, API error messages, and redirects frequently
reference internal subdomains. Every subdomain referenced in web content is a
new discovery candidate.

**G1.8 — Wildcard DNS detection and filtering**
Some targets configure catch-all DNS that resolves any random subdomain name.
Detect this pattern before brute-forcing — it generates unlimited false positives.
Only subdomains that resolve to IPs not part of the wildcard pattern are real.

---

### Vertical Goals — Extract maximum detail from each subdomain

**G1.V1 — Live vs dead classification**
Determine whether each resolved subdomain has an active HTTP/HTTPS service,
whether it responds only at the DNS level, or whether it is a dead record.
Dead records are subdomain takeover candidates.

**G1.V2 — HTTP response metadata extraction**
For every live subdomain: status code, page title, server header, content-type,
content-length, redirect chain, response time. This fingerprints the application
type without any active probing.

**G1.V3 — Technology stack fingerprinting**
Identify the web server software, application framework, CDN provider, and WAF
vendor from response headers, cookie names, error page content, and resource
path patterns.

**G1.V4 — WAF and CDN presence detection**
Determine whether the subdomain sits behind a CDN or WAF, and which vendor.
This determines whether origin IP discovery is needed before any further testing.

**G1.V5 — Origin IP discovery behind CDN**
For CDN-protected subdomains, find the real server IP via:
- Historical DNS records from before CDN was added
- Mail server IPs (MX/SPF records often share the same origin netblock)
- Cross-referencing Shodan and Censys for IPs serving the same TLS certificate
- Subdomains that don't route through the CDN (ftp., smtp., vpn., mail.)

**G1.V6 — Subdomain takeover detection**
For every CNAME record, verify the target resource exists. A CNAME pointing to
an unclaimed S3 bucket, Heroku app, GitHub Pages site, or Azure resource is a
takeover opportunity. Dead NS delegations are zone-level takeovers.

**G1.V7 — TLS certificate detail extraction**
For every HTTPS subdomain: extract Subject Alternative Names (may reveal
additional undiscovered subdomains), issuer, validity period, supported TLS
versions, and cipher suites.

**G1.V8 — Functional classification**
Label each live subdomain by its apparent function: API, authentication, admin
panel, staging, developer tools, marketing, CDN origin, mail, VPN. This drives
prioritization — admin and API subdomains get deeper analysis first.

**G1.V9 — DNS record full extraction**
For every discovered subdomain, extract all DNS record types: A, AAAA, CNAME,
MX, NS, TXT, SRV. TXT records frequently expose internal hostnames, verification
tokens, and service configurations.

---

### Recursive Outputs

| What is produced | Feeds into |
|---|---|
| Each live subdomain | URL asset processing |
| Discovered origin IPs | IP_ADDRESS asset processing |
| New subdomains from JS/crawl | Back to WILDCARD horizontal goals |
| IP ranges from SPF/MX records | CIDR asset processing |

---

## Asset Type 2 — URL (`https://app.target.com`)

**What it is**: A specific web application. Horizontal = every reachable path and
parameter. Vertical = understand what each path does and what attack surface it presents.

---

### Horizontal Goals — Find every path, endpoint, and parameter

**G2.1 — Crawl the full visible link graph**
Use a JavaScript-aware headless browser to simulate real user navigation: click
links, submit forms, follow redirects, execute JavaScript. Map every URL the
application itself reveals to a legitimate user.

**G2.2 — Mine historical URLs**
Query Wayback Machine, Common Crawl, and URL aggregation services for every
URL ever indexed for this domain. Historical URLs reveal endpoints that were
removed from the UI but may still function on the backend.

**G2.3 — Directory and file fuzzing**
Systematically test dictionary-based path names against the application. Use
technology-appropriate extensions based on the identified stack (`.php`, `.aspx`,
`.jsp`, `.json`, `.bak`, `.env`, `.git`). Recursive fuzzing uncovers nested paths
missed in a single pass.

**G2.4 — Virtual host discovery**
Test whether the same IP serves different applications under different Host header
values. Internal applications, admin panels, and staging environments are frequently
accessible this way even when not listed in DNS.

**G2.5 — API specification document hunting**
Search for exposed developer documentation that maps the entire API surface:
`swagger.json`, `openapi.yaml`, `/api-docs`, `/graphql` (GraphQL introspection),
`/wsdl`, `/.well-known/`. These give a complete route map without any fuzzing.

**G2.6 — JavaScript source analysis for endpoints**
Download every JavaScript file linked from the application. Extract all API
paths, base URLs, and endpoint references via static analysis. Fetch and
decompress any source maps to recover original unminified code.

**G2.7 — Parameter discovery**
For every discovered endpoint, find all accepted query and body parameters —
including undocumented ones. Hidden parameters frequently control debug behavior,
admin access, or feature flags (`debug=true`, `admin=1`, `internal=true`).

**G2.8 — HTTP method matrix testing**
Test every discovered path with all HTTP methods: GET, POST, PUT, PATCH, DELETE,
OPTIONS, HEAD, TRACE. Method-based access control bypasses are common — a path
that returns 403 on GET may accept POST from unauthenticated users.

**G2.9 — robots.txt and sitemap analysis**
Both documents explicitly list paths the target either wants crawled or explicitly
wants hidden. Disallowed paths in robots.txt are often the most interesting ones.

**G2.10 — Error page path disclosure**
Trigger 404 and 500 errors with crafted requests. Error pages frequently disclose
internal file paths, framework versions, and stack traces that reveal additional
endpoint patterns.

---

### Vertical Goals — Extract depth from each discovered endpoint

**G2.V1 — Authentication requirement mapping**
Classify every endpoint: publicly accessible, requires authentication, requires
specific role/permission, or requires specific session state. Mismatches between
expected and actual access control are authorization bugs.

**G2.V2 — Exact technology version fingerprinting**
Extract precise software versions from response headers (`Server`, `X-Powered-By`,
`X-AspNet-Version`), cookie name patterns, error messages, and resource path
patterns. Exact versions map directly to CVEs.

**G2.V3 — WAF behavior analysis**
Test how the WAF responds to probe payloads. Identify the vendor, understand
which signature patterns trigger blocks, and identify encoding or structural
variations that pass through undetected.

**G2.V4 — Cache behavior analysis**
Determine whether responses are cached, what the cache key includes, and what
inputs are reflected in responses without being part of the cache key. Unkeyed
inputs that appear in responses are cache poisoning candidates.

**G2.V5 — Cookie and session analysis**
Extract all cookies set by the application. Classify each: session token,
authentication credential, CSRF token, tracking identifier, feature flag.
Assess entropy, expiry, security flags (HttpOnly, Secure, SameSite).

**G2.V6 — CORS policy assessment**
Test cross-origin read permissions on every endpoint by sending requests with
attacker-controlled `Origin` headers. An endpoint that reflects arbitrary origins
with `Access-Control-Allow-Credentials: true` allows full cross-origin data theft.

**G2.V7 — Input reflection surface mapping**
Identify every point where user-supplied input appears in responses: URL path,
query parameters, headers, JSON body fields. Each reflection point is a candidate
for XSS, SSTI, header injection, or open redirect testing.

**G2.V8 — File upload surface assessment**
For every upload endpoint: identify accepted MIME types, maximum file size, storage
location (local vs cloud), whether filenames are preserved, and whether uploaded
files are served back via a predictable URL.

**G2.V9 — Rate limiting behavior**
Test each authentication endpoint, password reset, OTP verification, and
resource-intensive endpoint for rate limiting presence, threshold, and bypass
(IP rotation, header manipulation, response-based detection).

**G2.V10 — Redirect chain analysis**
Follow and document every redirect. Open redirects, unvalidated redirect parameters,
and redirect chains that pass through multiple domains are both standalone bugs
and components of authentication bypass chains.

**G2.V11 — Serialized object detection**
Identify responses and parameters containing serialized data: Java serialization
(magic bytes `AC ED`), PHP serialized strings (`O:4:`), Python pickle, JSON with
type hints. Deserialization of attacker-controlled data is frequently RCE.

---

### Recursive Outputs

| What is produced | Feeds into |
|---|---|
| Subdomains in JS files | WILDCARD asset processing |
| API base URLs discovered | URL assets (each API as new target) |
| Cloud storage URLs | Potential CIDR/IP assets |
| Redirect destinations on other domains | New URL assets |
| Internal service URLs in error messages | New URL/IP assets |

---

## Asset Type 3 — DOMAIN (`target.com`)

**What it is**: A root domain without wildcard qualifier. Treat as WILDCARD plus a
dedicated infrastructure and email security layer. All WILDCARD goals apply in full.

---

### Horizontal Goals — Find every asset connected to this domain

**G3.1 — All WILDCARD horizontal goals (G1.1 through G1.8)**
Apply the complete WILDCARD goal set to `*.target.com` as derived scope.

**G3.2 — Zone transfer attempt**
Request the authoritative nameserver to send its complete zone file. This single
request returns every DNS record in the zone if the nameserver is misconfigured.
Test each NS record individually.

**G3.3 — Full DNS record type enumeration**
Query for every record type on the root domain and all discovered subdomains:
`A`, `AAAA`, `MX`, `NS`, `TXT`, `SOA`, `CAA`, `SRV`, `CNAME`, `NAPTR`, `HINFO`.

**G3.4 — SPF record full expansion**
The SPF TXT record lists every IP authorized to send email. It frequently includes
`include:` directives pointing to third-party services. Fully expand all includes
to produce a complete list of IP ranges the organization uses for email — these
are often the same netblocks as production infrastructure.

**G3.5 — DKIM selector enumeration**
DKIM public keys live at `selector._domainkey.target.com`. Common selectors include
`default`, `google`, `mail`, `k1`, `s1`, `s2`, `selector1`, `selector2`. Enumerating
active selectors reveals which email services the target uses.

**G3.6 — Reverse WHOIS for related domains**
Query reverse WHOIS databases with the registrant email, organization name, and
registrant name from the target's WHOIS record. Discover other domains registered
by the same entity — often older assets with weaker security posture.

**G3.7 — Historical WHOIS and DNS change tracking**
Review historical WHOIS records and DNS change history to find infrastructure
that existed previously and may still be running even if removed from current DNS.

---

### Vertical Goals — Extract infrastructure and email security detail

**G3.V1 — Email spoofing feasibility assessment**
Determine whether an attacker can send email that appears to come from
`@target.com` and be delivered. Requires assessing: SPF policy strictness
(`~all` softfail vs `-all` hardfail), DMARC policy (`p=none` delivers spoofed
mail), DKIM presence, and DMARC alignment mode.

**G3.V2 — Subdomain DMARC coverage gap**
The root domain DMARC record does not automatically protect subdomains unless
`sp=` (subdomain policy) is set. A missing subdomain policy means any subdomain
can be spoofed even if the root domain has `p=reject`.

**G3.V3 — Mail infrastructure identification**
Identify all components of the email stack from MX records: mail server software,
email security gateways (Mimecast, Proofpoint, Barracuda), cloud email platform
(Google Workspace, Microsoft 365). Each component has its own attack surface.

**G3.V4 — CAA record assessment**
CAA records restrict which Certificate Authorities may issue certs for the domain.
Missing or overly permissive CAA records mean an attacker who can social-engineer
any CA can obtain a certificate for the domain. Missing CAA = no restriction.

**G3.V5 — DNSSEC validation**
Determine whether DNSSEC is deployed. Without DNSSEC, DNS responses can be
forged in certain network positions (cache poisoning). With DNSSEC but broken
chain of trust, validation fails and some resolvers may fall back to unsigned.

**G3.V6 — Nameserver provider assessment**
Identify the DNS hosting provider. Some providers (older Route53 configs, legacy
providers) have subdomain takeover risks at the nameserver delegation level.

---

### Recursive Outputs

| What is produced | Feeds into |
|---|---|
| All discovered subdomains | WILDCARD outputs |
| SPF-expanded IP ranges | CIDR/IP_ADDRESS assets |
| MX server hostnames | URL/IP_ADDRESS assets |
| Related domains from reverse WHOIS | New DOMAIN assets (if in scope) |

---

## Asset Type 4 — IP_ADDRESS (`1.2.3.4`)

**What it is**: A single IP address. Horizontal = every service on every port. Vertical =
maximum detail on each service. No assumption about what runs here — scan everything.

---

### Horizontal Goals — Find every service running on this machine

**G4.1 — Full TCP port scan (all 65,535 ports)**
Test every possible TCP port for open/closed/filtered status. Non-standard ports
are common for internal admin interfaces, development servers, and legacy services.
Never scan only the top 1,000 ports on an IP target.

**G4.2 — UDP scan on high-value ports**
UDP services are invisible to TCP scanning. Test ports for SNMP (161), DNS (53),
DHCP (67/68), TFTP (69), NTP (123), SNMP traps (162), IPMI (623), and other
high-value UDP services.

**G4.3 — Pre-cached data query**
Query Shodan and Censys for cached scan data on this IP before any active scanning.
May reveal services on ports that are now firewalled, historical banners, and past
TLS certificates. Zero detection risk.

**G4.4 — Reverse DNS and hostname recovery**
Look up the hostname assigned to this IP. Hostnames encode function and environment
information (`db-prod-01`, `admin-internal`, `vpn-gateway`) and may reveal
additional assets in the same naming convention.

**G4.5 — Virtual host enumeration on HTTP ports**
A single IP may serve multiple web applications under different Host header values.
After finding HTTP ports, brute-force Host headers to discover all applications
sharing this IP.

---

### Vertical Goals — Per service on each open port

**G4.V1 — Exact version fingerprinting**
Extract the precise software name and version from service banners, probe responses,
and protocol-specific handshakes. Version string maps directly to CVE lookup.

**G4.V2 — Default and weak credential testing**
Test every service that requires authentication against default credentials for
the identified software. Default credentials remain unchanged in a significant
portion of production deployments.

**G4.V3 — HTTP/HTTPS services**
For every port serving HTTP or HTTPS: treat as a URL asset and apply the full
URL vertical goal set (G2.V1 through G2.V11).

**G4.V4 — SSH assessment**
Extract: software version and build, supported authentication methods, host key
algorithm and size, supported KEX algorithms. Old OpenSSH versions map to CVEs.
Weak KEX algorithms (diffie-hellman-group1-sha1) are cryptographic downgrade risks.

**G4.V5 — SNMP full assessment**
Test community strings against a quality wordlist. If a valid string is found:
walk the full MIB tree to extract device configuration, all interface IPs, ARP
table (reveals connected hosts), routing table, and any credentials stored in
configuration OIDs.

**G4.V6 — SMB/NetBIOS assessment**
Test for null session authentication. If accessible: enumerate shares, enumerate
users via RID cycling, extract domain information and policy. Map accessible
shares for sensitive data.

**G4.V7 — LDAP assessment**
Test anonymous bind. If accessible: enumerate the base DN object tree, extract
user accounts, group memberships, computer objects, and policy objects. LDAP
data provides the full Active Directory structure.

**G4.V8 — Database port assessment**
For MySQL (3306), PostgreSQL (5432), MongoDB (27017), Redis (6379), Elasticsearch
(9200), Cassandra (9042): test for unauthenticated or default-credential access.
Unauthenticated database access is a critical finding.

**G4.V9 — IPMI assessment (UDP 623)**
If IPMI responds: test the Cipher Zero authentication bypass (any password
accepted with valid username), attempt HMAC hash capture for offline cracking.
IPMI access is hardware-level — it bypasses all OS-level authentication.

**G4.V10 — TLS service assessment**
For every TLS-wrapped service: test supported protocol versions (is TLS 1.0/1.1
still enabled?), cipher suite strength (RC4, 3DES, NULL, export-grade ciphers),
forward secrecy (ECDHE/DHE vs RSA key exchange), and known vulnerabilities
(POODLE, BEAST, ROBOT, DROWN).

**G4.V11 — CVE correlation**
For every identified software and version: query CVE databases and vendor advisories.
Prioritize by CVSS score but also by exploitability (public PoC available vs
theoretical). Version pinning in banners often lags behind actual patch state.

---

### Recursive Outputs

| What is produced | Feeds into |
|---|---|
| HTTP/HTTPS services on any port | URL assets |
| Hostnames from rDNS | WILDCARD/URL assets |
| Internal IPs from SNMP/LDAP | IP_ADDRESS assets (if in scope) |
| Internal hostnames from LDAP/SMB | WILDCARD/URL assets |

---

## Asset Type 5 — CIDR (`1.2.3.0/24`)

**What it is**: An IP address range. The sole job before anything else is finding which
hosts are alive. Once live hosts are found, each becomes an IP_ADDRESS asset.

---

### Horizontal Goals — Find every live host in the range

**G5.1 — CIDR expansion to flat IP list**
Convert the range notation to an explicit list of every individual IP address in
the range. A /24 contains 254 usable hosts. A /16 contains 65,534.

**G5.2 — High-speed live host discovery**
Test every IP for responsiveness via TCP SYN probes on common ports (80, 443, 22,
8080, 8443) and ICMP echo. Use fast asynchronous tools capable of testing the full
range in under a minute. Do not assume hosts are dead from a single probe type.

**G5.3 — Reverse DNS sweep of entire range**
Look up the hostname for every IP in the range simultaneously. Naming patterns
reveal function (`db-`, `admin-`, `vpn-`, `dev-`) and provide targets for
focused testing before any port scanning.

**G5.4 — Pre-cached intelligence query**
Query Shodan and Censys for every IP in the range before any active scanning.
Retrieve historical port data, banners, and TLS certificates for the entire range.

**G5.5 — ASN and ownership verification**
Confirm the entire range belongs to the target via BGP routing data and WHOIS.
Ranges may contain IPs allocated to third parties or cloud providers — these
are not in scope without explicit program confirmation.

---

### Vertical Goals

**G5.V1 — Per live host: full IP_ADDRESS goal set**
For every confirmed live host: apply all IP_ADDRESS horizontal and vertical goals
(G4.1 through G4.V11).

**G5.V2 — Cross-IP TLS certificate correlation**
Identify groups of IPs that serve the same TLS certificate. This reveals virtual
hosting configurations and CDN origin clusters.

**G5.V3 — Hostname pattern analysis**
Map the naming convention across discovered hostnames. Patterns (`prod-web-01`,
`prod-web-02`, `prod-db-01`) predict undiscovered hosts (`prod-web-03`, `prod-db-02`).

**G5.V4 — Network topology inference**
SNMP data, rDNS names, and router/switch banner grabs collectively reveal network
segmentation, routing topology, and the relationship between hosts in the range.

---

### Recursive Outputs

| What is produced | Feeds into |
|---|---|
| Every live host | IP_ADDRESS asset processing |
| Hostnames from rDNS | WILDCARD/URL asset processing |
| HTTP services discovered | URL asset processing |

---

## Asset Type 6 — ANDROID_APP (`com.target.app`)

**What it is**: An Android application package (APK). This is pure code and traffic
analysis. Zero networking background needed — you are reading source code and watching
what the app says to its backend.

---

### Horizontal Goals — Find every backend surface the app uses

**G6.1 — APK acquisition**
Download the APK from Google Play Store using automation tools that do not require
a paid purchase. Obtain every version if multiple are available — older versions
may have fewer security controls.

**G6.2 — Full decompilation to readable source**
Convert the APK binary to readable Java source code. The goal is human-readable
class files, not raw bytecode. Decompile all included libraries, not just the
main application classes.

**G6.3 — API endpoint extraction from source**
Search all decompiled source files for: hardcoded URLs, base URL configuration
strings, HTTP client instantiation with hostnames, API path constants, and
dynamic URL construction patterns. Build a complete list of every backend
hostname and path referenced in the code.

**G6.4 — AndroidManifest.xml full analysis**
Extract: every declared Activity, Service, ContentProvider, and BroadcastReceiver;
their exported status; their intent filters; required permissions; deep link URL
schemes; and backup configuration. Exported components with no permission check
are accessible from any other app on the device.

**G6.5 — Third-party SDK and service identification**
Identify every integrated SDK, analytics service, crash reporting tool, payment
processor, and cloud service referenced in the code or resources. Each integration
is a potential credential source and attack surface.

**G6.6 — Network traffic capture during runtime**
Route the app's traffic through a proxy during normal use. This captures endpoints
that are only called at runtime and not visible in static analysis — particularly
endpoints called only after authentication.

**G6.7 — String and resource file scanning**
Search all string resources, raw assets, and configuration files for: API keys,
access tokens, private keys, passwords, internal hostnames, and configuration
values. These are frequently embedded in non-code resources that static analysis
misses.

---

### Vertical Goals — Extract depth from each discovered surface

**G6.V1 — API endpoint testing**
For every extracted backend endpoint: apply the full URL vertical goal set
(G2.V1 through G2.V11). Mobile apps frequently call APIs without the same
authentication checks enforced on web clients.

**G6.V2 — Exported component exploitation testing**
For every exported component without a permission requirement: test whether it
can be invoked from another app to trigger unintended behavior — data leakage,
privilege escalation, or unintended state changes.

**G6.V3 — API key and credential validation**
For every extracted key or token: test it against the target service. Hardcoded
keys are a direct bug — they expose the service associated with that key.

**G6.V4 — Deep link and URI scheme testing**
Test every registered URI scheme (`target://action?param=value`) for injection,
open redirect, and authentication bypass. Deep links that authenticate users or
perform privileged actions without validation are login bypass vulnerabilities.

**G6.V5 — Firebase backend assessment**
Extract the Firebase project ID from the app's `google-services.json`. Test
`https://project-id.firebaseio.com/.json` for unauthenticated read access.
Test common collection paths (`/users`, `/messages`, `/accounts`).

**G6.V6 — Certificate pinning bypass**
Determine whether the app implements certificate pinning. If yes: test whether
common bypass techniques work (Frida hooks, patching the manifest). Pinning
bypass is necessary to proxy traffic for dynamic analysis.

**G6.V7 — Local storage security assessment**
Inspect what the app stores on device: SharedPreferences for plaintext credentials,
SQLite databases for sensitive data, external storage for data that should be
private. Local storage vulnerabilities are relevant when device access is in scope.

**G6.V8 — WebView security assessment**
Identify all WebView usages in the app. Assess: whether JavaScript is enabled,
whether the JavaScript bridge exposes dangerous native methods, whether the
WebView loads external URLs that could be controlled by an attacker.

---

### Recursive Outputs

| What is produced | Feeds into |
|---|---|
| Discovered API hostnames | WILDCARD/URL assets |
| Firebase project IDs | URL assets (Firebase backend) |
| Third-party service hostnames | URL assets |
| Backend URLs from traffic capture | URL assets |

---

## Asset Type 7 — IOS_APP (`com.target.app`)

**What it is**: An iOS application package (IPA). Parallel structure to Android but
a different binary format and different toolchain. Same goal: extract the full
backend surface from the app's code and traffic.

---

### Horizontal Goals — Find every backend surface the app uses

**G7.1 — IPA acquisition**
Obtain the IPA from the App Store via appropriate tooling, from TestFlight if
available, or from an enterprise distribution URL if discoverable via OSINT.

**G7.2 — Binary string extraction**
Run strings extraction across the compiled application binary. Unlike Android,
iOS binaries are compiled native code — full source recovery is not always
possible. Strings extraction captures hardcoded URLs, hostnames, and keys
embedded in the binary.

**G7.3 — Plist and resource file analysis**
Extract all property list files (`.plist`) bundled with the app. These contain
API base URLs, feature flag configurations, environment settings, and third-party
service configurations.

**G7.4 — Framework and library identification**
List all bundled frameworks and linked libraries. Identify third-party components,
their versions, and associated CVEs. Backend service SDKs reveal backend hostnames.

**G7.5 — Info.plist full analysis**
Extract: all registered URL schemes, app transport security (ATS) exceptions,
required device capabilities, background modes, and entitlements. ATS exceptions
(allowing HTTP, disabling cert validation) are security misconfigurations.

**G7.6 — Runtime network traffic capture**
Configure a trusted proxy on the device and route all app traffic through it.
Capture all API calls made during normal app use, authentication, and every
user-accessible feature.

**G7.7 — Objective-C/Swift class and method enumeration**
Dump the Objective-C runtime headers to list all classes and methods. Method
names are descriptive in Objective-C and frequently reveal internal API structure
and authentication logic.

---

### Vertical Goals

**G7.V1 — API endpoint testing**
For every captured and extracted API endpoint: apply the full URL vertical goal
set (G2.V1 through G2.V11).

**G7.V2 — URL scheme handler testing**
Test every registered URL scheme for injection, authentication bypass, and
unintended privileged actions. URL scheme handlers are frequently overlooked
during development security review.

**G7.V3 — ATS exception assessment**
Document every App Transport Security exception. Exceptions that disable certificate
validation entirely (`NSAllowsArbitraryLoads: true`) mean traffic to those domains
can be intercepted without pinning bypass.

**G7.V4 — Keychain and local storage assessment**
Inspect what the app stores in the iOS Keychain, NSUserDefaults, and local files.
Assess accessibility attributes — data stored with `kSecAttrAccessibleAlways` is
accessible even when the device is locked.

**G7.V5 — Certificate pinning bypass**
Identify whether pinning is implemented (custom URLSessionDelegate, TrustKit,
Alamofire pinning). Test whether Frida-based hooks or SSL Kill Switch bypass
the pinning to enable traffic capture.

**G7.V6 — Runtime method hooking**
Use Frida to hook authentication methods, encryption/decryption functions, and
network request construction functions at runtime. Observe plaintext values before
encryption and after decryption — bypasses transport-layer analysis limitations.

**G7.V7 — WKWebView JavaScript bridge assessment**
Identify all WKWebView usages. Assess whether the `WKScriptMessageHandler`
interface exposes dangerous native capabilities to JavaScript loaded in the WebView.

---

### Recursive Outputs

| What is produced | Feeds into |
|---|---|
| API hostnames from binary/plist | WILDCARD/URL assets |
| Third-party service endpoints | URL assets |
| Backend URLs from traffic capture | URL assets |

---

## Asset Type 8 — SOURCE_CODE (`github.com/target/repo`)

**What it is**: A public source code repository. This is entirely passive — no
interaction with target systems at all. The attack surface is secrets embedded in
code and infrastructure details disclosed by configuration files.

---

### Horizontal Goals — Find every sensitive disclosure in the codebase

**G8.1 — All branches, not just default**
The default branch (main/master) is the most reviewed. Feature branches, release
branches, and hotfix branches are created and sometimes pushed publicly with less
scrutiny. Scan every branch.

**G8.2 — Full git commit history including deleted files**
Files deleted from a repository are not deleted from git history. A `.env` file
added in commit 50 and deleted in commit 51 is still fully recoverable from the
commit history. Scan the entire history, not just the current HEAD state.

**G8.3 — All repositories in the organization**
Bug bounty programs name one repository in scope but often other repositories
in the same GitHub org are also in scope and contain the same or related code.
Enumerate all public repositories under the target org.

**G8.4 — Employee public forks**
Developers fork the main repository to their personal accounts. These forks may
contain experimental branches, work-in-progress features, or debugging code with
hardcoded credentials that never made it back to the main org.

**G8.5 — Associated GitHub gists**
Developers use GitHub Gists for snippets and quick notes. Search gists associated
with org members' accounts for configuration examples, deployment scripts, and
debug output that discloses credentials or internal endpoints.

**G8.6 — Dependency and package registry analysis**
Extract all package names from `package.json`, `requirements.txt`, `Gemfile`,
`pom.xml`, and similar dependency files. Internal package names referencing
private registries (e.g., `@target/internal-sdk`) reveal internal registry URLs.

**G8.7 — Environment variable name enumeration**
Even when values are not hardcoded, environment variable names in code reveal
what secrets the application uses: `DATABASE_URL`, `AWS_ACCESS_KEY_ID`,
`STRIPE_SECRET_KEY`. This builds the secret schema for targeted search.

---

### Vertical Goals — Extract actionable intelligence from each finding

**G8.V1 — Credential validation**
For every discovered API key, access token, or password: test it against the
target service to determine if it is valid and what level of access it grants.
Treat expired or revoked credentials as informational, not critical.

**G8.V2 — Internal hostname and endpoint mapping**
Configuration files, infrastructure-as-code, and CI/CD pipeline files reference
internal hostnames, internal API base URLs, and private service endpoints. Extract
all of these — they represent attack surface not discoverable from the internet.

**G8.V3 — Infrastructure topology from IaC**
Terraform, CloudFormation, Pulumi, and Ansible files describe the exact cloud
and network infrastructure: VPCs, subnets, security groups, S3 buckets, RDS
instances, ECS services. This is a complete infrastructure map from passive read.

**G8.V4 — Dependency vulnerability mapping**
For each dependency and its pinned version: query CVE databases for known
vulnerabilities. A vulnerable dependency with a public exploit is a direct
finding if the vulnerable code path is reachable.

**G8.V5 — CI/CD pipeline security assessment**
Review workflow files (`.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile`)
for: secrets passed as environment variables, OIDC trust misconfigurations that
allow fork pull requests to access secrets, external action dependencies from
untrusted sources.

**G8.V6 — Secrets management maturity assessment**
Determine how the application handles secrets: hardcoded values (critical),
environment variables (medium — check CI/CD exposure), external vault (assess
vault configuration), encrypted at rest (assess key management). This determines
where to look for credential theft paths.

**G8.V7 — Docker image layer history**
Dockerfile and CI/CD configurations reference Docker image names. Pull public
images and inspect layer history — credentials passed as build arguments or
`RUN` commands are embedded in layer history even if the final image does not
contain them.

---

### Recursive Outputs

| What is produced | Feeds into |
|---|---|
| Internal hostnames in config files | WILDCARD/URL assets |
| Cloud resource names (buckets, etc.) | Passive enumeration targets |
| CI/CD endpoint URLs | URL assets |
| Internal API base URLs | URL assets |
| Dependency package feeds | Potential supply chain surface |

---

## Asset Type 9 — HARDWARE (Physical Device)

**What it is**: A physical device — router, IoT device, embedded controller, network
appliance. In scope when the program explicitly includes a device model.

---

### Horizontal Goals

**G9.1 — Firmware acquisition**
Obtain the firmware binary from the vendor's download page, extract it from a
device via UART/JTAG, or extract it via the device's own update mechanism.
Firmware contains the entire software stack.

**G9.2 — Firmware filesystem extraction**
Unpack the firmware binary to recover its filesystem. Most embedded firmware
uses SquashFS, JFFS2, or CRAMFS. The filesystem contains all binaries, scripts,
configuration files, and certificates.

**G9.3 — Network interface enumeration**
Identify every network interface and service the device exposes: management web
UI, SSH/Telnet, API, cloud update service, UPnP, mDNS, proprietary protocols.

**G9.4 — RF interface enumeration**
Identify every wireless protocol the device uses: WiFi, Bluetooth, Zigbee, Z-Wave,
433/868 MHz proprietary, IR. Each is a separate attack surface.

---

### Vertical Goals

**G9.V1 — Hardcoded credential extraction**
Search firmware filesystem for hardcoded credentials: default passwords in config
files, SSH host keys bundled in firmware (same key across all devices), API keys
for cloud services.

**G9.V2 — Web interface assessment**
Apply full URL vertical goal set to the device's management web interface.
Embedded web servers are frequently outdated and unpatched.

**G9.V3 — Binary vulnerability analysis**
Identify the OS, kernel version, and key binary versions (BusyBox, OpenSSL,
dropbear). Map to CVEs. Test for common embedded vulnerabilities: command
injection in web parameters, stack overflows in network service parsing.

**G9.V4 — Update mechanism security**
Assess how firmware updates are delivered and validated: is the update signed,
is the signature verified before flashing, is the update channel HTTPS, can
updates be downgraded to vulnerable firmware.

---

### Recursive Outputs

| What is produced | Feeds into |
|---|---|
| Cloud backend URLs from firmware | URL assets |
| Internal API hostnames | WILDCARD/URL assets |
| Management interface on network | URL/IP_ADDRESS assets |

---

## Cross-Cutting Goals — Apply to Every Asset Type

These goals are not specific to one asset type. Apply them in parallel across
the entire program surface once initial asset discovery is underway.

**CG1 — Cloud storage bucket enumeration**
Generate naming candidates from the target's brand name, product names, and
discovered subdomains. Test candidates against all major cloud providers (AWS S3,
GCP Cloud Storage, Azure Blob Storage). Unauthenticated public read is a critical
finding regardless of which asset type led to discovery.

**CG2 — Source code secret scanning across the organization**
Scan every public repository in the target's GitHub/GitLab/Bitbucket organization.
This runs once at program start and again periodically — secrets are committed
continuously by developers.

**CG3 — Breach data correlation**
Query breach databases for the target's domain. Compromised employee credentials
from historical breaches may still be valid if not rotated. Valid credentials
enable authenticated testing of the full application surface.

**CG4 — Technology stack CVE monitoring**
Once the technology stack is fingerprinted (from URL analysis, banner grabbing,
and source code), monitor CVE feeds for newly disclosed vulnerabilities affecting
those exact versions. A new CVE against an identified version is an immediate
testing priority.

**CG5 — Scope boundary enforcement**
Before any active testing action: verify the target is in scope according to the
program's policy. Scope check must gate every stage. Out-of-scope interaction
is a program violation regardless of the vulnerability found.

---

## The Recursion Map — How Asset Types Feed Each Other

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

The pipeline terminates when no new asset objects are produced by any active
processing cycle. Until that point, every discovered asset is a new input.