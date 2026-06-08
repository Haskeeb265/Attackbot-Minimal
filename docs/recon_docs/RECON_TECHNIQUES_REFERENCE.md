# Reconnaissance Techniques Reference
> Exhaustive reference of attack surface categories and their associated recon techniques, organized by target domain. Covers passive, active, and exotic/research-grade methods.

---

## Table of Contents

1. [Web / HTTP](#1-web--http)
2. [DNS / Domain](#2-dns--domain)
3. [TLS / Certificates](#3-tls--certificates)
4. [Auth / IAM](#4-auth--iam)
5. [Email / Messaging](#5-email--messaging)
6. [Network / IP](#6-network--ip)
7. [Cloud / Infrastructure](#7-cloud--infrastructure)
8. [WAF / CDN](#8-waf--cdn)
9. [Mobile / IoT](#9-mobile--iot)
10. [Protocols / SCADA](#10-protocols--scada)
11. [OSINT / HUMINT](#11-osint--humint)
12. [Crypto / Hardware Security](#12-crypto--hardware-security)
13. [Exotic / Research](#13-exotic--research)

---

## 1. Web / HTTP

**Role in cybersecurity:** HTTP is the universal application transport layer. Every web app, API, and microservice communicates over it. It carries authentication tokens, session state, user data, and business logic — making it the richest single attack surface in any engagement. Misconfigurations here affect every user simultaneously. A successful exploitation chain often originates here and pivots outward: SSRF reaches cloud metadata, request smuggling bypasses WAF rules, and cache poisoning injects malicious responses for all users.

**Primary attacker gains:** Session hijacking, account takeover, remote code execution, SSRF to internal network, source code and secret disclosure, supply chain poisoning via cache injection, business logic abuse.

---

### Fingerprinting & Discovery

- **Web server stack fingerprinting via error pages** — Identifies server technology, version, and loaded modules from error page templates, response headers, and header ordering. Enables precise CVE targeting without guessing.

- **HTTP/2 SETTINGS frame fingerprint** — Analyzes HTTP/2 SETTINGS frames and stream prioritization order to fingerprint server implementations (nginx vs. Apache vs. Caddy). Useful when standard headers are stripped.

- **HTTP/3 QUIC transport parameter analysis** — Inspects QUIC version negotiation and transport parameters to fingerprint H3-enabled servers and identify their implementation lineage.

- **Favicon hash technology fingerprinting** — Hashes the server favicon (MurmurHash) and queries Shodan/Censys for matching hosts to identify technology stack and discover related infrastructure at scale.

- **Browser devtools debug port exposure** — Detects exposed Chrome/Firefox remote debug ports (default 9222/9229) that allow full browser control, DOM inspection, and credential extraction from active sessions.

- **Host Header / TLS SNI virtual host brute-force** — Brute-forces Host header values and SNI fields to enumerate hidden virtual hosts sharing the same IP — discovers internal or staging apps not listed in DNS.

- **HTTP Host header:port internal fingerprint** — Appends non-standard ports to the Host header to probe and fingerprint back-end internal services that respond differently to unusual port values.

- **Absolute URI injection for proxy mapping** — Sends absolute-URI requests to identify reverse proxy topology and reveal internal routing logic. A request to `http://internal-host/path` forwarded by an unwitting proxy exposes backend addressing.

- **Magic tunnel endpoint enumeration** — Enumerates Cloudflare TryCloudflare, ngrok, and localtunnel endpoints associated with the target to find temporarily exposed internal services or development environments.

- **Internal URL shortener and redirect inference** — Maps internal URL shortener rules and redirect chains to discover internal paths and services accessible only via abbreviated links.

---

### Method & Protocol Probing

- **HTTP method enumeration and override probing** — Tests all HTTP methods (GET, PUT, DELETE, TRACE, PATCH, CONNECT) and override headers (X-HTTP-Method-Override, X-Method-Override) to find hidden functionality and bypass method-based access controls.

- **WebDAV OPTIONS and PROPFIND probing** — Issues WebDAV verbs to discover internal directory structures, server-side file paths, and potential file write access on misconfigured servers.

- **HTTP request smuggling detection (CL/TE, TE.CL, H2.CL)** — Tests for request desynchronization vulnerabilities between front-end proxies and back-end servers. Successful smuggling poisons the request queue, enables firewall bypass, and allows cache injection or credential theft.

- **HTTP desync via hop-by-hop header abuse** — Exploits differences in how proxies and origins handle hop-by-hop headers (Connection, Transfer-Encoding) to cause desynchronization and request smuggling variants.

- **Cross-origin resource sharing (CORS) misconfiguration crawl** — Crawls all endpoints for overly permissive CORS policies — wildcard origins or origin reflection — that allow cross-origin data theft from authenticated sessions.

- **Cross-origin opener/embedder policy (COOP/COEP) bypass assessment** — Tests COOP and COEP headers for isolation bypass conditions that re-enable cross-origin attacks (SharedArrayBuffer timing, Spectre) in browsers that enforced isolation.

- **postMessage origin wildcard enumeration** — Enumerates JavaScript event listeners using postMessage with wildcard origin checks (`*`) — enables cross-site scripting escalation via message injection.

- **WebSocket handshake origin bypass and hijacking** — Tests WebSocket handshake origin validation and probes for CSRF-style hijacking via unvalidated origin in the Upgrade request. Allows reading/writing to WS data streams.

- **WebRTC internal IP disclosure** — Uses WebRTC ICE candidate negotiation to leak internal/private IP addresses of users or servers, bypassing NAT and revealing network topology.

- **Server-Sent Events (SSE) and WebTransport endpoint discovery** — Discovers SSE and WebTransport endpoints that may expose internal push data streams or real-time operational data without authentication.

---

### Content & Application Analysis

- **JavaScript static analysis for secrets and endpoints** — Statically analyzes bundled, minified, and obfuscated JavaScript for hardcoded API keys, internal endpoint URLs, access tokens, and developer comments revealing architecture.

- **Source map extraction (.js.map)** — Retrieves JavaScript source maps (`.js.map`) to reconstruct original pre-minification source code, recovering internal logic, comments, and secrets stripped during production build.

- **DOM-based routing and client-side template reverse engineering** — Reverse-engineers client-side routing tables and template compilation to discover hidden UI states, admin routes, and feature-flagged functionality not linked from the visible interface.

- **PWA service worker scope and cache enumeration** — Enumerates service worker registration scope and cached responses to find offline-stored sensitive data, authentication tokens, or responses from authenticated endpoints.

- **robots.txt, security.txt, and humans.txt analysis** — Mines Disallow entries, security contact disclosures, and employee mentions for hidden paths, internal tools, and technology stack hints left by developers.

- **Parameter discovery via fuzzing, dictionary, and static assets** — Discovers hidden query/body parameters through dictionary fuzzing, behavioral analysis, and static extraction from HTML, JS, and API documentation — reveals undocumented functionality.

- **Backup and default file exposure** — Enumerates tilde (`~`), `.bak`, `.swp`, `.orig`, `.old`, `Copy of`, and similar backup file suffixes across discovered paths to recover source code and configuration.

- **Log file and crash dump exposure** — Discovers publicly accessible `debug.log`, `error_log`, `application.log`, and core dump files containing stack traces, internal paths, credentials, and user data.

- **.git / .svn / .hg / .bzr directory exposure** — Detects exposed version control directories and extracts repository DAGs (via git clone or manual reconstruction) to recover full source history including secrets committed and later deleted.

- **Web server directory listing and mod_status/mod_info exposure** — Finds open directory indexes and Apache mod_status/mod_info diagnostic pages leaking server internals, loaded modules, and current request state.

- **Telemetry, crash-report, and error-tracking endpoint harvesting** — Identifies Sentry DSN URLs, Datadog RUM keys, and error-tracking endpoints from JS assets. Grants read access to real-time application errors containing user data and stack traces.

---

### Injection & Logic Surfaces

- **Server-side request forgery (SSRF) blind probe via DNS/HTTP bin** — Tests for blind SSRF by injecting out-of-band callbacks (DNS lookups, HTTP requests to a controlled server) into URL parameters, headers, and XML/JSON payloads.

- **Out-of-band resource load probe (XXE, DTD, SVG)** — Probes XML external entity, DTD expansion, and SVG `<image href>` injection points for out-of-band resource loading that confirms SSRF, file read, or internal service access.

- **Cache-poisoning vector identification via unkeyed headers** — Identifies HTTP headers and query parameters excluded from the cache key that an attacker can use to inject a malicious variant into the shared cache — affects all subsequent users.

- **Web cache deception into authenticated page caching** — Tricks CDN/proxy caches into storing authenticated page fragments by appending a static file extension to an authenticated URL — fragment then accessible to unauthenticated users.

- **Content Security Policy (CSP) nonce, hash, and reporting endpoint mapping** — Extracts nonces, hashes, and report-uri/report-to endpoints from CSP headers to identify weaknesses enabling XSS and data exfiltration via policy violation reporting.

- **Cross-domain policy file crawl (crossdomain.xml / clientaccesspolicy.xml)** — Retrieves legacy Flash/Silverlight cross-domain policy files that may grant overly broad cross-origin read access to unauthenticated data.

- **CSS injection and attribute selector exfiltration** — Uses CSS attribute selectors injected into pages to exfiltrate sensitive attribute values (CSRF tokens, hidden input values) character by character via timing or network requests.

- **Trusted-type policy and DOM clobbering surface** — Analyzes Trusted Types CSP policies and tests DOM clobbering gadgets — HTML elements whose IDs shadow global JS objects — to find XSS bypass paths in apps enforcing strict CSP.

- **MIME sniffing and X-Content-Type-Options bypass** — Probes for content-type sniffing behavior where browsers interpret responses as a different MIME type than declared, allowing content-type confusion attacks (script execution from text files).

- **CSP report-uri / report-to endpoint and violation data leakage** — Subscribes to or spoofs CSP reporting endpoints to capture policy violation data that leaks internal paths, injected script sources, and application structure.

- **Feature-Policy / Permissions-Policy mis-scoping** — Tests Permissions-Policy headers for overly broad camera, microphone, geolocation, and USB grants that expose browser sensor access to embedded frames or third-party scripts.

- **Registration and account creation flow verb-injection surface** — Tests account registration and profile creation flows for HTTP verb injection vulnerabilities — where parameter names or values are interpreted as method overrides or template directives.

- **Backup, staging, development, and UAT environment discovery** — Discovers publicly accessible staging (staging.), dev (dev.), test (uat.), and preview environments that typically run with reduced security controls and contain recent production data.

- **Request queue-based timing attack for internal endpoint discovery** — Uses response time variations induced by request queue depth to infer the existence of internal endpoints — longer queue times for valid routes vs. immediate 404s.

- **OOB file inclusion probe via SMB/WebDAV/HTTP** — Tests for out-of-band file inclusion by injecting UNC paths (`\\attacker\share\file`) into file path parameters — confirms SSRF, RFI, or XXE and maps internal share access.

- **Browser-in-the-browser (BITB) precursor detection** — Identifies site characteristics (iframe-able SSO popups, trusted domain appearance) that make the target useful as a basis for BITB phishing attacks.

- **Browser GPU/CSS side-channel for cross-origin size/presence inference** — Exploits browser GPU/CPU timing or CSS selector timing behavior to infer whether a specific resource (image, document) exists at a cross-origin URL — bypasses SameSite and CORP headers in some configurations.

---

## 2. DNS / Domain

**Role in cybersecurity:** DNS underpins every other protocol. It translates names to IPs, stores SPF/DKIM authentication policy, defines mail routing, enables service discovery, and is queried before any connection is made. Weaknesses here let attackers redirect traffic, impersonate services, and enumerate the entire attack surface of a target before sending a single packet to their servers. DNS recon is typically the first and most information-dense phase of any engagement.

**Primary attacker gains:** Full subdomain enumeration, origin IP discovery bypassing CDN/WAF, subdomain takeover for phishing/malware hosting, traffic interception via cache poisoning, internal hostname and IP range disclosure, DNSSEC downgrade paths.

---

### Enumeration & Discovery

- **Passive DNS data aggregation and analysis** — Collects historical DNS resolutions (A, AAAA, MX, NS, TXT, CNAME) from third-party passive DNS datasets (SecurityTrails, CIRCL, VirusTotal) without touching the target — reveals historical infrastructure and rotated IPs.

- **DNS zone walking (NSEC/NSEC3)** — Iterates through DNSSEC-signed zones using NSEC chain traversal to enumerate all hostnames — reveals every record in the zone without brute-force. NSEC3 is resistant but vulnerable to offline hash cracking for common names.

- **Subdomain brute-force using Markov-chained permutation engines** — Generates candidate subdomains using statistical language models (Markov chains, neural networks) trained on leaked zone files and previous DNS data — significantly higher hit rate than static wordlists.

- **Wildcard DNS detection and TTL entropy analysis** — Detects wildcard DNS responses (NXDOMAIN masking) and analyzes TTL variation entropy to distinguish genuine records from catch-all responses — prevents false-positive enumeration results.

- **TXT record harvesting** — Extracts TXT records for internal hostnames, API keys, ownership verification tokens, internal path hints, and configuration data left by developers or services.

- **Recursive DNS cache snooping and timing analysis** — Queries a target's DNS resolver for records to determine whether they are cached — infers which hosts have been recently resolved by internal users, revealing active internal service usage.

- **Authoritative nameserver software/version inference** — Fingerprints nameserver software and version via response behavior, EDNS option handling, and timing — identifies BIND, PowerDNS, Knot, and Windows DNS versions for known vulnerability matching.

- **DNS query type/payload fuzzing for resolver behavior profiling** — Sends crafted query types (ANY, AXFR, IXFR, private types) and malformed payloads to map resolver feature support, quirks, and security posture.

- **Domain generation algorithm (DGA) seed inference from passive data** — Analyzes observed DNS query patterns and registered domains from passive data to reverse-engineer DGA seeds and predict future C2 domain registrations.

- **Whois history and reverse Whois** — Retrieves past domain registration records to track ownership changes, hosting moves, and rebranding. Reverse Whois finds all domains registered with the same registrant email, name, or organization — maps the full domain portfolio.

---

### Origin IP Discovery

- **Origin IP via historic DNS A/AAAA records** — Mines passive DNS databases for historical A/AAAA records to find the server's real IP address before a CDN or reverse proxy was placed in front — direct IP bypasses WAF entirely.

- **Origin IP via Certificate Transparency log cross-referencing** — Compares CT log certificate SANs against current DNS records to find IPs that were directly associated with the domain before CDN deployment.

- **Origin IP via ZSK/KSK reuse across zones** — Identifies DNSSEC signing key reuse across zones controlled by the same operator — correlates key fingerprints to find hidden origin zones sharing infrastructure.

- **Origin IP via SPF macro expansion and DMARC report ingestion** — Expands SPF macros (which perform DNS lookups) and ingests DMARC aggregate/forensic reports to extract mail server IPs and related infrastructure.

- **Origin IP via cloud provider global accelerator health check leaks** — Discovers origin IPs leaked through health-check requests from AWS Global Accelerator, Azure Front Door, or Cloudflare health monitors — these bypass CDN and contact origin directly.

- **Origin IP via HTTP/3 Alt-Svc headers on sibling hosts** — Inspects Alt-Svc headers on sibling and related hosts to find QUIC/H3 endpoints that reveal the true origin IP before CDN termination.

---

### Subdomain Takeover & Abuse

- **Subdomain takeover via dangling CNAME, NS, and cloud alias records** — Finds CNAME or NS records pointing to unclaimed resources (deleted S3 buckets, Heroku apps, GitHub Pages) and claims them — hosts malicious content under the target's trusted domain.

- **Subdomain hijack via dangling cloud resource records (A, NS)** — Discovers dangling A records for deleted cloud instances and NS delegations for unconfigured zones — allows serving attacker content from trusted DNS names.

- **DNS rebinding surface pre-test via staged payloads** — Tests whether the target application validates the Host header or origin — if not, staged DNS rebinding payloads can be used to pivot from a victim's browser into their internal network.

---

### Infrastructure & Policy Analysis

- **CAA record interpretation for internal CA trust boundaries** — Reads Certification Authority Authorization records to determine which CAs are permitted to issue certificates — infers internal PKI and CA infrastructure, identifies rogue issuance paths.

- **DNSSEC chain validation and trust anchor mapping** — Maps the full DNSSEC delegation chain from root to zone to identify misconfigured trust anchors, unsigned delegations, and chain breaks enabling downgrade.

- **DNSSEC chain break for downgrade attack path** — Identifies breaks in the DNSSEC chain of trust where a signed parent delegates to an unsigned child — enables DNS spoofing attacks in that zone.

- **DoH/DoT server and resolution path discovery** — Identifies DNS-over-HTTPS and DNS-over-TLS resolvers used by the target — maps how they resolve target domains and whether DoH bypasses internal DNS policy.

- **Oblivious DNS/HTTP (ODoH) gateway proxy address discovery** — Discovers ODoH gateway proxies used by the target organization to understand resolution infrastructure and potential blind spots.

- **DNS-based command and control staging point detection** — Identifies DNS patterns (high-entropy subdomain labels, low TTL, beaconing cadence) indicative of DNS C2 infrastructure — relevant for threat intelligence and red team infrastructure detection.

- **RIR object and route object mapping** — Queries ARIN, RIPE, APNIC, LACNIC, and AFRINIC for IP block ownership, ASN assignments, contact information, and route objects — builds the authoritative map of what IPs belong to the organization.

- **Reverse IP/domain lookup across all major CDN edges** — Finds all domains co-hosted on the same IP across CDN edge nodes — discovers sibling hosts, sister companies, and infrastructure shared with other targets.

---

## 3. TLS / Certificates

**Role in cybersecurity:** TLS is what makes HTTPS meaningful. Certificates establish identity; cipher suites determine confidentiality strength; session management determines forward secrecy. Weaknesses in TLS allow decryption of traffic previously assumed safe, impersonation of services, and interception of credentials in transit. Certificate Transparency logs also serve as a real-time subdomain discovery mechanism — every cert issued is publicly logged.

**Primary attacker gains:** Certificate-based impersonation, traffic decryption, credential and token harvest, real-time new asset discovery via CT logs, session replay, downgrade to exploitable cipher suites.

---

### Certificate Analysis

- **SSL/TLS certificate chain and intermediary trust store mapping** — Enumerates the full certificate chain including intermediate CAs to identify weak chains, cross-signed certificates, and trust store gaps enabling MITM.

- **Certificate Transparency log subscription and real-time alerting** — Subscribes to CT log streams (crt.sh, Google Argon, Cloudflare Nimbus) for real-time discovery of certificates issued for target domains — surfaces new subdomains the moment they're provisioned.

- **Wildcard HTTPS certificate search and subdomain inference** — Mines wildcard TLS certificates from CT logs to infer the naming convention used for subdomains — discovers assets not listed in DNS by pattern-matching against the wildcard.

- **CAA record interpretation** — Reads CAA DNS records to determine which certificate authorities are authorized — infers internal PKI, identifies unauthorized issuance paths, and finds CAs potentially susceptible to compromise.

- **HPKP / Expect-CT / Certificate Transparency enforcement gap** — Checks for missing or misconfigured HTTP Public Key Pinning and Expect-CT headers — gaps allow certificate substitution without browser warnings.

---

### Cipher Suite & Protocol Analysis

- **TLS cipher suite ordering and fallback behavior fingerprint** — Analyzes the order and selection of offered cipher suites and protocol versions to fingerprint server implementation and identify supported but deprecated cipher suites.

- **TLS compression (CRIME/BREACH) surface mapping** — Tests for TLS-level compression (CRIME) and HTTP-level compression (BREACH) that enable chosen-plaintext attacks to recover session tokens byte by byte.

- **TLS session ticket lifetime and rotation analysis** — Measures session ticket key rotation intervals to assess forward secrecy posture — long-lived session ticket keys mean past traffic is decryptable if the key is later compromised.

- **TLS 1.3 0-RTT early data replay surface assessment** — Probes whether 0-RTT (early data) is accepted by the server — creates a replay attack surface where previously observed 0-RTT data can be replayed to induce side effects.

- **Key exchange group preference enumeration** — Lists supported ECDH and DHE groups to find deprecated groups (EXPORT, 512-bit DH, FREAK curves) that enable downgrade to weak key exchanges.

- **Renegotiation and post-handshake client authentication testing** — Tests for insecure TLS renegotiation (CVE-2009-3555 variants) and post-handshake client certificate authentication surfaces that allow session injection.

- **Cross-protocol attack surface via ALPN** — Tests ALPN negotiation to find cross-protocol confusion vectors where a server that speaks HTTP also accepts SMTP, FTP, or Redis commands — enables protocol injection if a client can be directed to connect.

---

### Vulnerability Probing

- **Heartbleed / Bleichenbacher-style oracle probe** — Tests legacy endpoints for Heartbleed (CVE-2014-0160) and Bleichenbacher-style RSA PKCS#1 v1.5 decryption oracles — allows memory disclosure or private key recovery on unpatched systems.

- **Origin IP via Certificate Transparency cross-reference** — Cross-references historical CT log entries with current DNS to find IP addresses that were directly associated with the domain before CDN deployment.

---

## 4. Auth / IAM

**Role in cybersecurity:** Authentication and Identity & Access Management is the system that decides who can do what. Compromising it doesn't trigger most security controls because the attacker appears to be a legitimate user. A single IAM weakness typically cascades across every connected application — SSO means one token grants access to dozens of services. This is the highest-leverage attack surface in the kill chain.

**Primary attacker gains:** Account takeover, privilege escalation to admin roles, lateral movement across SSO-connected apps, AD/cloud domain compromise, MFA bypass, credential spray at scale.

---

### Identity & Protocol Discovery

- **OAuth 2.0 / OpenID Connect discovery document extraction** — Fetches `.well-known/openid-configuration` to enumerate authorization endpoints, supported grant types, scopes, JWKS URIs, and token endpoints — full attack surface for OAuth abuse.

- **SAML metadata, ACS URL, and entity ID mapping** — Retrieves SAML metadata documents to map Assertion Consumer Service URLs, entity IDs, and signing certificates — prerequisite for signature wrapping and forgery attacks.

- **SSO redirect flow and session state leakage** — Tests SSO redirect flows for open redirect, state parameter misuse, and session state exposure during authentication — allows nonce capture and session hijacking.

- **Cloud identity tenant ID and domain validation (Azure AD, Okta, Auth0)** — Resolves cloud IAM tenant IDs and validates domain associations — enables account enumeration, tenant confusion attacks, and identifies federated identity configurations.

- **Multi-stage redirect and SSO chain enumeration** — Maps full redirect chains through SSO and OAuth flows to identify intermediate state leakage, open redirects, and token exposure in referrer headers.

---

### Token & Session Attacks

- **JWT algorithm confusion and key-id injection** — Tests JWT implementations for algorithm confusion (RS256→HS256 using public key as HMAC secret) and key-id header injection to forge tokens claiming arbitrary roles.

- **SAML XML signature wrapping (XSW)** — Tests SAML assertions for XML Signature Wrapping attacks that move the signed element while leaving the assertion body unverified — allows authentication as any user including admin.

- **OIDC ID token claim and kid header fuzzing** — Fuzzes OIDC token claim fields (sub, email, roles) and key-id headers to find validation weaknesses where the server accepts attacker-controlled key material.

- **Credential-stuffed session hijack via OAuth implicit flow remnants** — Tests for OAuth implicit flow tokens exposed in browser history, referrer headers, or fragment identifiers — allows session hijacking without credentials.

- **OIDC back-channel logout endpoint enumeration** — Discovers OIDC back-channel logout endpoints to understand session termination architecture and test for incomplete logout that leaves sessions active after sign-out.

---

### Credential Attacks

- **Breach credential stuffing candidate list** — Retrieves breach combo lists and generates targeted credential stuffing candidates for the target's accounts — combined with username enumeration, achieves bulk account compromise.

- **Username format and email address pattern generation** — Generates likely username and email formats from employee names (first.last@, flast@, f.last@) to support credential spray attacks across discovered services.

- **Password policy, complexity, and lockout threshold inference** — Infers password complexity rules, minimum length, and account lockout thresholds from login portal behavior — calibrates spray attack timing to avoid lockouts.

- **Multifactor authentication method detection and MFA push fatigue analysis** — Identifies MFA methods in use (TOTP, push, SMS, hardware token) and evaluates susceptibility to push fatigue (bombing) and SIM-swap vulnerabilities.

- **Password reset flow and security question harvesting** — Maps password reset flows, security question sets, backup email patterns, and rate limiting — identifies account takeover paths that bypass primary authentication.

---

### Active Directory & Enterprise IAM

- **Kerberos SPN scanning and weak cipher (RC4) enumeration** — Enumerates Service Principal Names and identifies accounts with RC4 encryption enabled — directly enables Kerberoasting to recover service account passwords offline.

- **Active Directory domain and forest trust enumeration without auth** — Maps Active Directory domain and forest trusts without credentials — identifies one-way and transitive trusts enabling lateral movement paths to other domains.

- **AD CS certificate template enumeration and ESC attack surface** — Enumerates Active Directory Certificate Services templates to identify ESC1-ESC8 attack paths — allows privilege escalation to domain admin via misconfigured certificate templates.

- **Azure / Entra ID Connect sync account metadata leak** — Extracts sync account metadata and configuration leaks from Azure AD Connect deployments — identifies accounts with privileged replication rights enabling DCSync.

- **LDAP signing and channel binding policy inference** — Determines whether LDAP signing and channel binding are enforced — identifies environments susceptible to LDAP relay attacks from coerced NTLM authentication.

- **LDAP anonymous bind, rootDSE, and schema extraction** — Performs anonymous LDAP binds to read rootDSE attributes, directory schema, and any objects accessible without authentication — maps AD structure without credentials.

---

### SaaS & Cloud IAM

- **SaaS-to-SaaS OAuth grant graph and excessive permission mapping** — Maps OAuth permission grants between connected SaaS applications to find over-privileged integrations — a compromised low-value SaaS with admin grants to high-value SaaS enables lateral movement.

- **API secret, token, and credential leak monitoring** — Monitors Pastebin, dark web forums, public repositories, and breach databases for leaked API keys and access tokens belonging to the target organization.

---

## 5. Email / Messaging

**Role in cybersecurity:** Email is how organizations communicate, reset passwords, deliver invoices, and authenticate users. Weak email authentication policy allows impersonation of any sender. The SMTP layer exposes user enumeration and relay abuse. Email is also the primary delivery vector for phishing — making its infrastructure recon foundational to social engineering operations.

**Primary attacker gains:** Domain spoofing for phishing, validated user enumeration for spray attacks, password reset hijacking, internal hostname and IP leakage, OWA/Exchange exploitation.

---

### Server Discovery & Fingerprinting

- **Email server (MX) enumeration and SMTP banner fingerprint** — Discovers mail exchangers via MX DNS records and fingerprints SMTP server software, version, and capabilities from EHLO/banner responses — identifies Exchange, Postfix, sendmail, and cloud gateways.

- **Email gateway appliance vendor and model fingerprinting** — Identifies email security gateway vendor and model from received headers, SMTP banner artifacts, and bounce message formatting — Proofpoint, Mimecast, Barracuda, and Cisco IronPort each have distinct fingerprints.

- **Exchange Autodiscover, ActiveSync, OWA, ECP endpoint discovery** — Discovers Exchange web endpoints — Autodiscover XML, OWA login, Exchange Control Panel, and ActiveSync — which have historically been vulnerability-dense and provide authentication attack surface.

---

### Authentication & Policy Analysis

- **SPF, DKIM, DMARC, MTA-STS, BIMI, DANE/DNSSEC policy evaluation** — Evaluates the complete email authentication policy stack for weaknesses enabling spoofing — missing DMARC, permissive SPF (+all), weak DKIM key size, and absent MTA-STS are all exploitable.

- **DKIM selector enumeration via brute-force and DMARC reports** — Brute-forces DKIM selectors (google._domainkey, s1._domainkey, etc.) and mines DMARC aggregate reports to discover active selectors and their key material — weak keys enable mail signing.

- **Origin IP via SPF macro expansion and DMARC report ingestion** — Expands SPF macros that perform DNS lookups on message metadata and ingests DMARC reports to extract sending mail server IPs revealing otherwise-hidden infrastructure.

---

### User Enumeration & Relay Testing

- **SMTP VRFY, EXPN, RCPT TO user enumeration** — Uses SMTP commands to enumerate valid email addresses and mailing list memberships — VRFY confirms accounts, EXPN expands lists, RCPT TO acceptance/rejection reveals valid recipients.

- **Open relay and authenticated relay testing** — Tests whether the SMTP server relays mail for unauthorized external senders — open relays enable spam and phishing from trusted IPs; authenticated relay tests check for credential-based relay abuse.

---

## 6. Network / IP

**Role in cybersecurity:** Network-layer recon establishes the fundamental topology: what hosts exist, what ports are open, what OS and services are running, and what firewall rules govern access. Every other attack category depends on this foundation. It also covers legacy protocols (SNMP, NetBIOS, LDAP) that are frequently misconfigured and grant unauthenticated access to sensitive network configuration and user data.

**Primary attacker gains:** Complete host and service inventory, unauthenticated protocol access to configuration data, precise OS/service fingerprinting for exploit targeting, firewall rule inference, topology mapping for lateral movement planning, hardware-level access via IPMI.

---

### Host & Port Discovery

- **TCP/IP stack OS fingerprinting** — Uses Nmap, p0f, and ZMap TCP/IP probe responses (window size, TTL, DF bit, options order) to identify host operating systems and kernel versions — enables precise exploit selection.

- **ICMP probing for firewall ruleset inference** — Sends varied ICMP types and codes (echo, timestamp, address mask, unreachable) to infer firewall ACL rules and identify permitted traffic flows between network segments.

- **IP ID sequence, TCP ISN, and TCP timestamp fingerprinting** — Analyzes IP ID counter sequences and TCP initial sequence numbers to fingerprint OS, detect idle hosts useful for idle scanning, and identify shared-IP infrastructure.

- **TTL-based topology mapping and tunnel detection** — Uses TTL hop counts and IP fragment reassembly timeout behavior to map routing topology and detect encapsulated tunnels (GRE, IPsec, IP-in-IP) in the path.

- **IP option processing and MTU path discovery** — Probes IP options (Record Route, Timestamp) and Path MTU Discovery to detect intermediate tunnels, identify encapsulation overhead, and infer network device types.

- **Shodan / Censys / ZoomEye / FOFA / BinaryEdge query** — Queries internet-wide scan platforms for current and historical snapshots of target IP ranges, ports, banners, and certificates — passive reconnaissance with no interaction with target.

- **Historical scan data diffing** — Compares historical Shodan/Censys snapshots over time to discover ephemeral services, configuration changes, and services that appeared and disappeared — reveals development and testing infrastructure.

- **IPv6 SLAAC, DHCPv6, and Neighbor Discovery passive monitoring** — Passively observes IPv6 Stateless Address Autoconfiguration and Neighbor Discovery Protocol traffic to enumerate IPv6 hosts — frequently overlooked by defenses focused on IPv4.

- **6to4, Teredo, and ISATAP tunnel endpoint detection** — Detects IPv6 transition tunnel endpoints that may bypass IPv4-only security controls and firewalls — reveals IPv6-accessible services hidden from IPv4 scanning.

---

### Protocol-Level Reconnaissance

- **SNMPv1/2c community string brute-force and MIB walking** — Brute-forces default and common SNMP community strings (public, private, community) to gain read/write MIB access — full device configuration, routing tables, interface details, and often credentials.

- **SNMPv3 engine ID and user enumeration** — Enumerates SNMPv3 engine IDs and usernames via response timing differences — prerequisite for authenticated SNMP access without knowing valid credentials.

- **NetBIOS name service, SMB null session, and named pipe enumeration** — Uses null SMB sessions and named pipes (IPC$) to enumerate shares, users, groups, domain information, and policies without authentication on older Windows configurations.

- **MSRPC endpoint mapper and interface UUID discovery** — Queries the DCE/RPC endpoint mapper to list all registered RPC interfaces and their UUIDs — maps Windows service attack surface including WMI, Task Scheduler, and Print Spooler.

- **NTP monlist, version, and peer discovery** — Queries NTP servers for monlist (list of recent clients), version, and peer information — reveals internal host IP addresses from the NTP client list and maps time synchronization topology.

- **IPMI / BMC / iLO / DRAC interface discovery and cipher profiling** — Discovers out-of-band management interfaces on servers and tests for IPMI 2.0 cipher zero authentication bypass — grants hardware-level access to servers entirely bypassing OS-level security controls.

- **UPnP, SSDP, mDNS, LLMNR, and NBT-NS passive listening** — Passively captures multicast discovery traffic to enumerate internal devices, hostnames, and services without sending any probes — Responder-style passive intelligence collection.

- **NFS export list and anonymous mount path discovery** — Discovers NFS export listings and tests for anonymous mount access to network file shares — commonly exposes home directories, backup data, and configuration files.

- **iSCSI target discovery and CHAP authentication bypass** — Enumerates iSCSI target names and tests for CHAP authentication bypass or default credential access — grants block-level storage access.

---

### Firewall & Network Topology Analysis

- **Firewall rule inference via differential IP TTL/port exhaustion** — Derives firewall ACL rules by correlating differential TTL responses, port exhaustion behavior, and timing across protocol and port combinations — maps permissive paths without triggering alerts.

- **IDS/IPS evasion via payload slicing and protocol ambiguity** — Tests IDS/IPS signature coverage by fragmenting, encoding, and segmenting payloads to identify blind spots — establishes which payloads will bypass detection.

- **IPv6 extension header processing and hop-by-hop option probing** — Sends IPv6 packets with unusual extension headers (Routing, Fragment, Hop-by-Hop) to discover firewall processing gaps and OS-level parsing bugs.

- **BGP stream real-time monitoring** — Monitors live BGP route streams for hijacks, leaks, and mis-originations of target IP prefixes — detects infrastructure changes and potential BGP-based attacks in near real-time.

- **PeeringDB, IXP looking glass, and traceroute archive correlation** — Correlates PeeringDB peering records with traceroute archives and IXP route servers to map upstream path diversity and identify network provider relationships.

---

### Remote Management & Legacy Services

- **Remote management interface (SSH, RDP, VNC, Telnet) version and key** — Identifies SSH/RDP/VNC/Telnet service versions, host keys, and supported authentication methods — detects weak key exchange, deprecated ciphers, and password authentication enabled.

- **SSL-VPN, ZTNA, SDP gateway, and SD-WAN edge fingerprint** — Identifies SSL-VPN, ZTNA, SDP, and SD-WAN gateway devices by certificate, response headers, and portal page signatures — maps network access control perimeter.

- **NAC and 802.1X policy profiling via supplicant analysis** — Infers NAC enforcement strictness and 802.1X policy from EAP type responses and supplicant behavior — identifies segments with lax enforcement as lateral movement targets.

- **VoIP/SIP trunk enumeration** — Probes SIP servers with INVITE, OPTIONS, and REGISTER to enumerate extensions, authentication requirements, and supported codecs — maps telephony attack surface.

- **Remote support tool detection** — Detects TeamViewer, AnyDesk, Splashtop, and ScreenConnect agents on enumerated hosts — identifies persistent remote access channels that may be abused for unauthorized access.

- **AS relationship and peering inference** — Infers upstream/downstream ISP and peering relationships from BGP data — maps the network provider ecosystem and identifies potential BGP-based pivot paths.

- **IP block and netblock ownership transitive mapping** — Traces IP ownership chains through SWIP/RIR transfer records to find all netblocks the target controls, including those registered to subsidiaries or acquired companies.

- **BGP route leak and hijack monitoring for target prefix** — Watches BGP feeds in real time for unauthorized announcements of target IP prefixes — detects infrastructure exposure and potential man-in-the-middle positioning.

- **IRR route object auditing** — Checks Internet Routing Registry entries for mis-registered or stale route objects — identifies mismatches between declared and observed routing that could indicate exposure or misconfiguration.

---

## 7. Cloud / Infrastructure

**Role in cybersecurity:** Cloud infrastructure has replaced the data center but introduced endemic misconfiguration vulnerabilities. Public storage buckets, exposed Kubernetes APIs, unauthenticated databases, and misconfigured IAM roles routinely contain millions of records. A single cloud misconfiguration typically has a blast radius of entire databases or full infrastructure control — not just a single host. CI/CD pipelines and container registries add supply chain pivot paths that compromise every downstream system.

**Primary attacker gains:** Mass data exposure from misconfigured storage, cloud credential theft via metadata service, full Kubernetes cluster compromise, Docker socket RCE, CI/CD supply chain injection, NoSQL unauthenticated data access.

---

### Cloud Provider & Metadata

- **Cloud metadata service (169.254.169.254) reachability from multi-tenant** — Tests whether the IMDS endpoint is reachable from multi-tenant environments — reachability via SSRF yields temporary IAM credentials with the instance's permission set.

- **Cloud instance identity document and IAM role name extraction** — Extracts instance identity documents and IAM role names from cloud metadata responses — role name enables targeted privilege escalation via role assumption or policy enumeration.

- **Cloud storage bucket enumeration via DNS, brute-force, and account ID** — Discovers S3, GCS, and Azure Blob storage containers via DNS-based discovery, naming convention brute-force, and account ID permutation — finds public buckets containing data intended as private.

- **Cloud CDN, load balancer, and API gateway origin mapping** — Maps the real origin infrastructure behind cloud CDN (CloudFront, Cloud CDN, Azure CDN) and API gateway layers — enables direct origin attack bypassing all front-end security.

- **Azure / Entra ID Connect sync account metadata leak** — Extracts sync account metadata and configuration from Azure AD Connect — identifies accounts with privileged directory replication rights enabling DCSync-equivalent attacks.

- **Firebase / Realtime Database unauthenticated read** — Tests Firebase and Realtime Database instances for misconfigured security rules allowing public read access — commonly exposes complete user databases with PII and authentication tokens.

---

### Container & Orchestration

- **Kubernetes API server, etcd, kubelet, and dashboard exposure** — Tests K8s API server for unauthenticated access, etcd for direct data access (contains all cluster secrets), kubelet for node-level exec, and dashboard for credential-free cluster management.

- **Docker daemon (2375/2376) and Podman API unauthenticated access** — Connects to Docker TCP sockets exposed without TLS or authentication — allows container creation with host filesystem mounts, enabling trivial host escape.

- **Container registry catalog enumeration** — Enumerates Docker Hub, ECR, GCR, and ACR registry catalogs for publicly accessible images and tags — images often contain hardcoded secrets, internal certificates, and environment configurations in layer history.

- **Container escape surface enumeration via exposed APIs** — Tests /proc, /sys, and kernel capability exposure through network-accessible container management APIs — identifies containers running with elevated privileges or dangerous capability sets.

---

### CI/CD & Source Control

- **CI/CD pipeline service exposure (Jenkins, TeamCity, Drone, GitLab CI)** — Discovers exposed CI/CD services and tests for unauthenticated access, script console exposure (Jenkins), or guest access — enables build pipeline injection delivering malicious code to production.

- **GitHub Actions workflow, environment, and OIDC trust mapping** — Analyzes GitHub Actions workflow files and OIDC trust configurations for supply chain attack surfaces — overly permissive OIDC trust allows cloud credential theft from forked PR builds.

- **Source code repository public indexing** — Searches GitHub, GitLab, Bitbucket, and SourceForge for public repositories belonging to or referencing the target organization — discovers accidentally public internal repos.

- **Commit, issue, wiki, and pull request history deep search** — Mines repository history, issue trackers, wikis, and PR comments for accidentally committed secrets, internal URLs, IP addresses, and architecture details — git history persists even after file deletion.

---

### Database & Storage Services

- **Database server version, TLS, and anonymous login (MySQL, PostgreSQL, MSSQL, Oracle)** — Fingerprints relational database servers, tests for unauthenticated or default-credential access, and evaluates TLS configuration — direct database access exposes all stored data.

- **NoSQL unauthenticated access (MongoDB, Redis, Elasticsearch, CouchDB, InfluxDB)** — Probes NoSQL services for unauthenticated read/write access — MongoDB and Redis have historically defaulted to no authentication, exposing entire databases.

- **Graph database open bolt/REST interface (Neo4j, OrientDB)** — Tests graph database HTTP and bolt interfaces for unauthenticated access and data exposure — graph databases often store relationship data with significant organizational intelligence value.

- **Big data stack exposure (HDFS NameNode, YARN, Spark UI)** — Discovers exposed Hadoop, YARN, and Spark web UIs — HDFS NameNode without authentication allows reading or deleting all stored data; YARN allows code execution via job submission.

---

### Serverless & Function Computing

- **Serverless function endpoint discovery (Lambda, Cloud Functions, Fn)** — Discovers AWS Lambda, GCP Cloud Functions, and Apache OpenWhisk endpoints from CloudFormation templates, source code, naming patterns, and log analysis — maps serverless attack surface.

- **Cloud function cold-start and execution environment reuse** — Exploits the sandboxed execution environment reuse between function invocations to read residual data (global variables, /tmp, database connections) from previous invocations.

---

## 8. WAF / CDN

**Role in cybersecurity:** WAFs and CDNs sit in front of web applications as the primary security control layer. They are not targets themselves — they are the obstacle between an attacker and the real target. Understanding WAF vendor, rule sets, and CDN topology is prerequisite to any web exploitation. Bypassing them typically doubles the number of reachable vulnerabilities and removes rate limiting.

**Primary attacker gains:** WAF rule nullification enabling delivery of otherwise-blocked payloads, origin IP exposure for direct attack, cache poisoning affecting all users, authenticated data theft via cache deception, internal port scanning via HTTP CONNECT.

---

### Fingerprinting & Bypass

- **WAF vendor and rule set fingerprinting** — Identifies WAF vendor (Cloudflare, AWS WAF, Akamai, Imperva, F5) and active rule sets from response patterns, error pages, headers, and response timing — enables vendor-specific bypass technique selection.

- **WAF bypass via parameter pollution, encoding, and parser differentials** — Attempts WAF bypass using HTTP parameter pollution, encoding variations (double URL-encode, Unicode normalization, HTML entity encoding), and parser differentials between WAF and origin.

- **Load balancer cookie decryption and injection surface** — Maps load balancer persistence cookie formats (Netscaler NSVPX, HAProxy, F5 BigIP) to identify encryption weaknesses or injection attack surfaces in the cookie value.

- **Cloudflare Workers / Fastly VCL logic inference from response delta** — Derives edge logic behavior by comparing response variations across requests with different headers, geographic origins, and timing — reverse-engineers VCL/Worker-based routing and caching rules.

---

### Cache Attacks

- **CDN edge-node caching rule inference and cache deception probe** — Infers CDN caching rules by analyzing Vary headers, Cache-Control directives, and response consistency — tests cache deception to trick the CDN into caching authenticated responses.

- **Web cache deception into authenticated page fragment caching** — Appends a static file extension or path segment to an authenticated URL to trick the CDN into caching the response — the cached authenticated content is then accessible to unauthenticated users.

- **Cache-poisoning vector identification via unkeyed headers/query** — Identifies HTTP request headers and query parameters excluded from the CDN cache key — injects malicious values into these unkeyed components to poison cached responses for all users.

- **Edge-side includes (ESI) injection surface mapping** — Tests for ESI injection at the CDN layer — successful injection allows SSRF from CDN infrastructure and exfiltration of cache-accessible data.

---

### Internal Access

- **CDN edge internal service port scanning via HTTP CONNECT** — Uses the HTTP CONNECT tunneling method through CDN edge nodes to scan internal ports behind the CDN — bypasses perimeter firewall for the CDN's internal network.

- **HTTP CONNECT via CDN edge as proxy to internal hosts** — Chains HTTP CONNECT through misconfigured CDN or proxy nodes to reach internal services not directly accessible from the internet.

---

## 9. Mobile / IoT

**Role in cybersecurity:** Mobile apps and IoT devices are systematically under-reviewed compared to web apps, yet contain hardcoded API keys, endpoint maps, and authentication logic in easily-reversible binaries. IoT devices sit on internal networks with direct access to segments that external attackers cannot reach. Both represent persistent footholds with privileged internal network positioning.

**Primary attacker gains:** Hardcoded credential extraction, complete backend API surface map, IP camera access for persistent surveillance and internal network pivot, MDM profile extraction revealing internal CA certificates and WiFi PSKs, Firebase unauthenticated database access.

---

### Mobile Application Analysis

- **SDK key extraction from mobile app static/dynamic binary analysis** — Extracts hardcoded API keys, private keys, SDK credentials, and backend URLs from mobile app binaries via static analysis (jadx, apktool, class-dump) — reveals secrets not visible from external recon.

- **Mobile app API endpoint, deep link, and push notification mapping** — Maps all backend API endpoints, deep link URI schemes, and push notification configurations from decompiled mobile app code — often more complete than any external API discovery technique.

- **Mobile Device Management (MDM) enrolment URL and profile extraction** — Discovers MDM enrolment endpoints (typically mobileconfig URLs) and retrieves configuration profiles — profiles contain internal CA trust anchors, WiFi PSKs, VPN configurations, and proxy settings.

- **UEM/MAM configuration leak from enrolment pages** — Extracts Unified Endpoint Management and Mobile Application Management configuration details from publicly accessible enrolment or registration pages — reveals MDM server addresses and policy enforcement scope.

---

### IoT & Physical Devices

- **IP camera default credential and RTSP/ONVIF stream discovery** — Discovers IP cameras using default or known credentials and enumerates RTSP video streams and ONVIF management interfaces — provides persistent video surveillance access and an internal network foothold.

- **Smart TV, digital signage, and conference room controller LAN presence** — Identifies smart TVs, digital signage players, and conference room AV controllers via mDNS, SSDP, and default ports — devices often run outdated Android or Linux with minimal patching.

- **NFC/RFID card UID, SAK, ATQA, and ATS fingerprinting via network-connected reader** — Reads NFC/RFID card parameters via network-connected reader infrastructure — fingerprints access card technology to assess physical access control vulnerability.

---

### Cloud & Backend Services

- **Firebase / Realtime Database unauthenticated read** — Tests Firebase Database, Firestore, and Realtime Database instances for public read access rules — misconfigured instances expose complete user databases accessible with no credentials.

- **Cloud storage bucket enumeration** — Discovers misconfigured cloud storage associated with mobile app backends (S3, GCS, Azure Blob) from mobile app strings and network traffic analysis — finds publicly accessible data stores.

---

### Wireless & Proximity Protocols

- **BLE advertisement and GATT enumeration (via remote BLE proxy)** — Reads BLE device advertisements and enumerates GATT service and characteristic UUIDs via network-connected BLE proxy — maps wireless device attack surface without physical proximity.

- **LoRa/LoRaWAN join procedure and DevEUI harvesting** — Captures LoRaWAN Over-The-Air-Activation join procedures from a network-connected LoRa gateway to harvest device EUIs and application identifiers.

---

## 10. Protocols / SCADA

**Role in cybersecurity:** Industrial protocols (Modbus, DNP3, BACnet, OPC UA, IEC 61850, MQTT) were designed when networks were air-gapped and security was physical. They have no authentication, no encryption, and no access control. When exposed to IP networks — even internal ones — they allow unauthenticated read and write of physical process parameters. SCADA recon is prerequisite to operational technology attacks with real-world physical consequences.

**Primary attacker gains:** Unauthenticated device enumeration and inventory, real-time physical process state read, operational telemetry theft, physical process manipulation (setpoint changes, valve commands, safety interlock disable), HMI/historian access for process visualization and historical data.

---

### Discovery Protocols

- **Industrial protocol broadcast discovery (Modbus, DNP3, EtherNet/IP, PROFINET)** — Broadcasts Modbus FC01/03, DNP3 Data Link Layer, EtherNet/IP List Identity, and PROFINET DCP Identify to enumerate OT devices — returns device model, firmware version, and I/O configuration without credentials.

- **BACnet Who-Is / I-Am enumeration** — Sends BACnet Who-Is broadcasts to enumerate building automation controllers (VAV, AHU, chillers, boilers) and retrieves their object lists — maps building automation network and control points.

- **WS-Discovery, WSD, and device function discovery** — Probes WS-Discovery protocol to discover printers, cameras, and WSD-enabled industrial devices — returns device description URLs with detailed capability information.

- **OPC UA discovery server and endpoint list enumeration** — Queries OPC UA discovery servers for registered server endpoints without establishing a full session — lists all OPC UA server endpoints and their security policies, identifying no-security endpoints.

- **EtherNet/IP List Identity and PROFINET DCP discovery** — Sends EtherNet/IP List Identity requests and PROFINET DCP Identify frames to enumerate PLCs, VFDs, and industrial networking equipment — no authentication required.

- **DICOM C-ECHO and HL7 FHIR endpoint enumeration** — Probes medical device networks for DICOM services (imaging systems, PACS) and HL7 FHIR API endpoints — medical devices frequently run outdated software with minimal access controls.

---

### Messaging & Telemetry

- **MQTT broker open topic discovery and retained message dump** — Connects to MQTT brokers without authentication and subscribes to wildcard topics (`#`) to read all retained messages — exposes operational telemetry, device credentials, and configuration data.

- **CoAP /.well-known/core resource directory enumeration** — Queries CoAP resource directories to enumerate IoT devices and their available resource endpoints — lightweight protocol used in constrained industrial and building IoT devices.

- **AMQP, STOMP, and NATS message broker anonymous access** — Tests AMQP, STOMP, and NATS message brokers for unauthenticated connection and queue/topic enumeration — exposes operational message flows and system-to-system communication.

---

### SCADA & Control System Access

- **SCADA HMI, historian, and engineering workstation web interface** — Identifies SCADA HMI and engineering workstation web interfaces accessible from the network (Wonderware, Ignition, iFIX, FactoryTalk) — frequently run with default or no authentication.

- **RTU/PLC ladder logic download and tag name extraction** — Downloads ladder logic programs and tag name databases from RTUs and PLCs via engineering protocol commands — reveals process variable names, setpoints, interlocks, and safety thresholds.

- **DNP3 secure authentication bypass check** — Tests DNP3 Secure Authentication v5 implementations for bypass vulnerabilities — DNP3 SA is the only security layer in many utility SCADA networks.

- **MMS IEC 61850 logical device and node enumeration** — Enumerates IEC 61850 MMS logical devices, logical nodes, and data objects on substation automation networks — maps protection relay and circuit breaker control surfaces.

- **ICCP / TASE.2 bilateral table and dataset probing** — Probes ICCP/TASE.2 energy management bilateral tables and dataset definitions — reveals inter-utility SCADA communication topology and accessible data sets.

- **OPC Classic (DCOM) interface and item enumeration** — Enumerates OPC Classic server interfaces via DCOM — legacy industrial data access protocol with minimal authentication, exposes process variable trees.

- **Modbus function code 0x11 / 0x2B device identification** — Uses Modbus Diagnostic (FC11) and MEI Device ID (FC43) to retrieve device vendor, model, and firmware — no authentication required by protocol design.

- **DNP3 Data Link Layer broadcast enumeration** — Sends DNP3 Data Link Layer request broadcast frames to discover all devices on the segment and retrieve device addressing without session establishment.

---

### Building Systems

- **Building management system (BMS) and energy management portal** — Discovers BMS and energy management web portals accessible over IP — controls HVAC, lighting, access control, and power monitoring with significant physical impact potential.

- **EV charging station (OCPP) and fleet management platform API** — Enumerates OCPP-based EV charging management APIs — unauthenticated access allows charging session manipulation, billing fraud, and fleet data exposure.

- **Fire alarm panel loop mapping and cause-and-effect logic** — Maps fire alarm panel zones and cause-and-effect logic via network-accessible Simplex, Notifier, or Edwards interfaces — understanding this logic has physical safety implications.

- **Elevator controller RS-485/Modbus and destination dispatch system** — Discovers elevator controller Modbus interfaces and destination dispatch system APIs accessible on building IP networks — potential for physical access disruption.

---

### Safety & Specialized Systems

- **Safety instrumented system (SIS) logic solver network probing** — Probes Safety Instrumented System logic solvers (Triconex, HIMatrix, Pilz) for network-accessible interfaces — safety systems were historically completely isolated; any network presence is anomalous.

- **GOOSE / SMV passive capture on switched Ethernet** — Passively captures IEC 61850 GOOSE (Generic Object Oriented Substation Event) and Sampled Values frames on switched Ethernet — reveals protection relay state and inter-relay communication without active probing.

- **3D printer network and G-code interception** — Discovers 3D printer management interfaces (OctoPrint, Repetier-Server) and intercepts G-code print streams — enables intellectual property theft and physical process interference.

- **Robotic arm controller teach pendant and safety PLC bus** — Discovers robotic arm controller and safety PLC interfaces accessible over IP — relevant in manufacturing environments where robots operate near humans.

---

## 11. OSINT / HUMINT

**Role in cybersecurity:** Open-source intelligence aggregates publicly available information — without any interaction with the target's systems — to build a comprehensive picture of the organization's technology, employees, partners, and operational patterns. HUMINT (human intelligence) techniques harvest information that people inadvertently disclose through professional profiles, public code, conference talks, and job postings. This phase costs nothing and produces intelligence directly actionable for phishing, spear-phishing, and technical attack planning.

**Primary attacker gains:** Technology stack enumeration, employee targeting list with roles and tools, job posting-derived internal architecture insights, source code and secret discovery, supply chain partner identification for pivot attacks, credential leak monitoring.

---

### Digital Footprint & Code

- **Source code repository public indexing** — Searches GitHub, GitLab, Bitbucket, and SourceForge for public repositories belonging to or referencing the target — discovers accidentally public internal code, infrastructure-as-code, and internal tooling.

- **Commit, issue, wiki, and pull request history deep search for secrets** — Mines repository history, issues, wikis, and PR comments for accidentally committed secrets, internal hostnames, IP ranges, and architecture details — git history is permanent even after file deletion.

- **GitHub Actions workflow, environment, and OIDC trust mapping** — Analyzes Actions workflows and OIDC federation configurations for supply chain attack surfaces — identifies misconfigurations enabling cloud credential theft via malicious PR builds.

- **Dependency manifest vulnerability mapping** — Parses package.json, Gemfile, requirements.txt, go.mod, and Cargo.toml to identify vulnerable third-party dependencies — establishes a vulnerability inventory without touching the production system.

- **Public/private package registry and artifact repository search** — Searches npm, PyPI, Maven, and internal registries (Artifactory, Nexus) for packages owned or used by the target — finds accidental private package publication, typosquatting opportunities.

- **API secret, token, and credential leak monitoring** — Monitors Pastebin, GitHub, dark web forums, and breach aggregators for leaked API keys, access tokens, and credentials belonging to the target organization.

- **PDF/DOCX metadata and hidden content extraction** — Extracts author, company, software version, revision history, and hidden tracked changes from publicly available documents — reveals employee names, internal paths, and software versions.

- **EXIF, XMP, and IPTC metadata from published images** — Extracts GPS coordinates, camera make/model, software version, and creation timestamps from published images — GPS data reveals physical locations of sensitive facilities.

---

### Personnel & Organization

- **Employee professional profiles for IT roles and tools** — Mines LinkedIn, Xing, and similar platforms for IT staff roles, technology certifications, tools mentioned, and tenure — directly identifies the target's technology stack and potential weak points.

- **Job posting technology and certification requirement analysis** — Mines job listings for technology requirements — "experience with Palo Alto Panorama required" directly reveals the firewall platform; "AWS Security Hub" reveals cloud monitoring tooling.

- **Conference talk, slide deck, and webcast OSINT** — Extracts internal architecture details disclosed in conference presentations (AWS re:Invent, DEF CON, internal tech blogs) — engineers routinely over-disclose in conference talks.

- **Technical blog, forum, Stack Overflow, and Q&A site disclosure** — Searches developer Q&A sites for employee posts containing internal hostnames, configuration snippets, error messages, and internal library names.

- **Organization chart, reporting structure, and PGP key cross-signing graph** — Builds org charts from public data and maps PGP web-of-trust to understand team structure, reporting relationships, and identify key decision-makers for targeting.

- **Public calendar, event, and CalDAV leakage** — Identifies publicly accessible calendars and CalDAV servers exposing meeting subjects, attendee lists, and room bookings — reveals project timelines, partner meetings, and M&A activity.

---

### Supply Chain & Third Parties

- **Supply chain partner, contractor, and vendor OSINT** — Maps third-party suppliers, contractors, and vendors connected to the target — supply chain partners often have privileged access and weaker security posture, serving as pivot paths.

- **Third-party SBOM inference from public documentation** — Infers the software bill of materials from public changelogs, job postings, conference talks, and API documentation — identifies third-party components and their known vulnerabilities.

- **Third-party SaaS and vendor technology stack inference** — Derives technology stack from response headers, JavaScript vendor libraries, cookie names, and third-party script domains in page source — identifies CRM, HR, ERP, and collaboration platforms.

---

### Signals & Physical

- **ADS-B / ACARS / VDL2 decoding from internet-connected receivers** — Decodes aircraft ADS-B position and ACARS datalink messages from online aggregators — tracks private jets associated with executives and corporate facilities.

- **AIS, LRIT, and marine VHF data from online aggregators** — Retrieves vessel position, identity, and route data from AIS aggregators — relevant for maritime-sector targets and supply chain logistics intelligence.

- **Public webcam, traffic camera, and CCTV feed discovery** — Finds publicly accessible IP camera streams via default credential databases and search engines — provides physical intelligence about facility access, personnel presence, and security posture.

- **QR code, barcode, and visual tag decoding from published images** — Decodes QR codes and barcodes visible in published photographs (marketing materials, social media) to recover internal URLs, asset tracking IDs, and system identifiers.

- **Breach credential stuffing candidate list from combo lists** — Retrieves breach credential lists and generates targeted stuffing candidates for the target's user accounts — combined with username enumeration and password spray produces large-scale account compromise.

---

### Blockchain & Dark Web

- **Cryptocurrency address and wallet transaction graph analysis** — Traces blockchain transactions to map wallet relationships, identify exchange accounts, and correlate financial flows — relevant for financial sector targets and ransom payment tracking.

- **Tor hidden service, I2P eepsite, and Freenet key retrieval** — Discovers target-affiliated .onion and .i2p addresses from public indexes and dark web paste sites — finds infrastructure or data intentionally or accidentally hosted on anonymization networks.

- **Generative AI for plausible internal document and email reconstruction** — Uses LLMs and public OSINT corpus to synthesize realistic internal documentation and email patterns — produces phishing pretexts and social engineering artifacts with authentic internal language.

---

## 12. Crypto / Hardware Security

**Role in cybersecurity:** Cryptographic vulnerabilities are low probability but maximum consequence. A padding oracle in a single endpoint decrypts all ciphertext the attacker has already collected. An HSM API weakness exposes key material protecting an entire PKI. These attacks bypass memory corruption mitigations entirely — they exploit mathematical properties of correctly-functioning but misused cryptography. Hardware security module attacks, white-box crypto differential fault analysis, and TEE attacks target the highest-value secrets in any organization.

**Primary attacker gains:** Ciphertext decryption via oracle, RSA/EC private key recovery, PKI compromise enabling universal certificate forgery, session token decryption enabling authentication bypass, long-term storage-now-decrypt-later target identification.

---

### Oracle & Side-Channel Attacks

- **Cryptographic oracle identification (padding, timing, length)** — Identifies CBC padding oracles, RSA PKCS#1 v1.5 decryption oracles, and timing oracles in public-facing endpoints — allows decryption of arbitrary ciphertext via adaptive chosen-ciphertext queries.

- **Heartbleed / Bleichenbacher-style oracle probe** — Tests for Heartbleed memory disclosure and Bleichenbacher-style RSA oracles on HTTPS endpoints — Bleichenbacher allows private key recovery from millions of carefully crafted TLS handshakes.

- **Hardware security module (HSM) network API usage analysis and key export tests** — Tests HSM network APIs (PKCS#11 over TLS, Thales RFS, SafeNet) for key export weaknesses or unintended cryptographic operation exposure — HSM compromise is total PKI defeat.

- **Differential fault analysis on white-box crypto implementations** — Triggers white-box cryptographic implementations over the network by inducing computational faults (via timing or load manipulation) to perform differential fault analysis and recover embedded keys.

- **Physically Unclonable Function (PUF) response data gathering** — Gathers PUF challenge-response pairs via network APIs to build a machine learning model capable of predicting responses — enables device impersonation without physical access to the PUF hardware.

---

### PKI & Certificate Infrastructure

- **Quantum-safe crypto inventory mapping** — Catalogs post-quantum cryptography deployment status from public TLS certificates and API documentation — identifies targets still using RSA/ECC against a store-now-decrypt-later threat model.

- **CAA record interpretation for internal CA trust boundaries** — Reads CAA DNS records to infer internal PKI structure, identify authorized CAs, and find potential unauthorized issuance paths.

---

### Hardware & Trusted Execution

- **Hardware trusted execution environment (TEE) fault injection profiling** — Probes remote attestation interfaces to profile TEE fault injection surfaces — identifies whether the implementation is susceptible to fault-induced instruction skipping or register corruption.

- **Secure boot PCR bank and TPM quote signature analysis** — Analyzes TPM PCR bank values and quote signatures from network-based attestation endpoints — identifies whether secure boot is properly configured or can be subverted.

- **Virtualised TPM (vTPM) and vSGX enclave boundary scan** — Probes virtualised TPM and SGX enclave interfaces over network-accessible management APIs — maps trust boundary assumptions and identifies attestation weaknesses enabling malicious enclave deployment.

- **eSIM / iSIM profile downloading and OTA platform key derivation** — Probes eSIM Over-The-Air platforms to test for platform key derivation weaknesses that would allow unauthorized profile installation or subscriber identity manipulation.

- **Contactless payment terminal kernel and reader configuration mapping** — Maps contactless payment terminal kernel versions, reader configurations, and transaction flow via network-accessible management interfaces.

---

## 13. Exotic / Research

**Role in cybersecurity:** Exotic research techniques represent the absolute frontier of offensive security — attacks that operate at the physics layer, bypass all software controls, target protocols from the pre-security era, or leverage AI to scale previously manual intelligence work. These techniques are used by nation-state actors and advanced APT groups, and are relevant for threat modeling, red team scenario planning against air-gapped or highly secure targets, and understanding the long-term risk landscape. Several categories (AI-assisted recon, SDR signal intelligence) are crossing into mainstream deployment.

**Primary attacker gains (by subcategory):** Hardware side-channels → cross-tenant cryptographic key recovery, ASLR bypass, hypervisor memory read; Cellular/SS7 → real-time geolocation of any mobile number, SMS 2FA interception; RF/Satellite → executive travel intelligence, satellite telemetry; Air-gap covert channels → exfiltration from physically isolated networks; AI-assisted → scaled OSINT correlation, high-fidelity phishing, OT digital twin construction.

---

### Hardware Side-Channel Attacks

- **Rowhammer / RAMBleed VM co-tenant** — Exploits DRAM bit-flip physics across adjacent memory rows to flip bits in a neighboring VM's memory — enables ASLR bypass and cross-tenant cryptographic key extraction (RSA-2048 demonstrated) with no vulnerability in victim software.

- **Cache side-channel (Prime+Probe, Flush+Reload)** — Monitors CPU cache state via timed memory access patterns to infer a victim process's memory access sequences — recovers AES keys from 256 cache measurements; underpins Spectre and Meltdown.

- **Memory deduplication covert channel for ASLR break** — Exploits KSM (Kernel Samepage Merging) timing to detect whether a specific memory page exists in a co-tenant VM — breaks ASLR by confirming virtual address layout in under 2 seconds.

- **Transient execution attacks (Spectre v1/v2, Meltdown, SpectreRSB)** — Tricks CPU speculative execution into transiently reading out-of-bounds memory, then exfiltrates via cache timing — Meltdown reads all kernel memory from userspace; Spectre crosses process and VM boundaries.

- **L1TF / MDS / Foreshadow (Intel Hyper-Threading co-tenant)** — Exploits Intel microarchitectural data sampling vulnerabilities to extract data from CPU-internal buffers across Hyper-Threading boundaries — Foreshadow-VMM reads hypervisor memory from a guest VM and breaks Intel SGX.

- **TEMPEST / EM emanation interception** — Captures electromagnetic emissions from video cables, keyboards, and CPUs to reconstruct screen content and keystrokes from an adjacent room — classified NSA technique; academic variants demonstrated at 20+ meters.

- **Power analysis and electromagnetic side-channel (SCA) on crypto implementations** — Analyzes power consumption and EM emissions from smart cards and embedded crypto implementations to recover AES and RSA keys via Simple/Differential Power Analysis — requires proximity or compromised power measurement.

---

### Cellular & Telephony

- **SS7 MAP Any Time Interrogation (ATI)** — Sends unauthenticated SS7 MAP ATI messages to the victim's home network to retrieve real-time cell tower location and IMEI — demonstrated against US Congressmen in 2017; SS7 access commercially available.

- **SS7 SMS interception (SRI-SM / MT-Forward-SM redirect)** — Redirects SMS delivery to attacker-controlled node via SS7 Send Routing Info — intercepts one-time passwords and bypasses SMS-based 2FA for banking and corporate accounts.

- **SS7 home routing bypass for SMS mis-delivery** — Exploits SS7 home routing weaknesses to intercept or redirect SMS messages intended for legitimate subscribers — enables account takeover for services dependent on SMS verification.

- **Diameter / GTP-C information element leakage** — Exploits trust relationships in 4G LTE Diameter and GTP-C signaling to extract subscriber location (more precise than SS7 ATI) and characterize data session parameters.

- **5G SUCI/SUPI de-concealment and network function profiling** — Attacks the 5G Subscriber Concealed Identifier encryption to de-anonymize subscribers, and enumerates 5G Service Based Architecture NF endpoints.

- **Lawful intercept interface and CALEA architecture reconnaissance** — Identifies lawful intercept interfaces and CALEA architecture components accessible on carrier networks — understanding this architecture is relevant for both red team and threat intelligence.

- **SIM Toolkit proactive command and card application discovery** — Discovers SIM Toolkit applet capabilities via OTA commands — maps subscriber identity module application attack surface.

- **UICC/USIM file system brute-force traversal (via OTA)** — Brute-forces UICC/USIM file system paths via OTA commands to enumerate subscriber identity and service configuration data.

- **Cellular IMSI/TMSI passive capture from compromised network element** — Captures IMSI/TMSI subscriber identifiers from a compromised network element or IMSI catcher — enables device tracking and targeted interception.

---

### RF / Satellite / Signals Intelligence

- **ADS-B / ACARS / VDL2 decoding** — Decodes unencrypted aircraft position, identity, and datalink messages from online aggregators or local SDR — tracks executive private jets, maps corporate aviation relationships, and identifies government aircraft operations.

- **AIS, LRIT, and marine VHF data from online aggregators** — Retrieves vessel AIS position tracks and LRIT reports — tracks shipping associated with target supply chain, identifies offshore platform support vessels, documents sanctions evasion.

- **SDR proprietary signal reverse engineering (streamed capture)** — Reverse-engineers unencrypted or weakly-encrypted ISM-band signals from industrial sensors, building systems, and access control using GNU Radio or Universal Radio Hacker.

- **Satellite downlink telemetry capture** — Captures unencrypted satellite telemetry and data downlinks from LEO/GEO satellites using ground-based SDR — demonstrated on multiple operational commercial and government satellites at DEF CON.

- **Wi-Fi probe request monitoring (via remote sensor)** — Captures Wi-Fi probe requests from remote RF sensors to infer device histories, preferred network names, and device MAC addresses — passive and undetectable.

- **LoRa/LoRaWAN join procedure and DevEUI harvesting** — Captures Over-The-Air-Activation join procedures from a network-connected LoRa gateway to harvest device identifiers and application keys.

---

### Air-Gap Covert Channels

- **Acoustic covert channel (AirHopper / MOSQUITO)** — Modulates data onto high-frequency audio emitted by PC speakers, received by a nearby smartphone microphone — AirHopper achieves 13-60 bps over 1-7 meters; MOSQUITO uses speaker-to-speaker coupling without a microphone.

- **Optical / LED covert channel (LED-it-GO / aIR-Jumper)** — Modulates data onto hard drive LED blink patterns or display brightness changes, captured by a line-of-sight camera — LED-it-GO achieves 4000 bps; aIR-Jumper uses IP camera IR LEDs for two-way communication.

- **Power line covert channel (PowerHammer)** — Encodes data in CPU workload-driven power consumption fluctuations transmitted over building power lines — receiver is a current clamp anywhere on the same electrical phase; 1000 bps demonstrated.

- **Thermal covert channel (BitWhisper)** — Uses controlled CPU heating to modulate temperature readings between physically adjacent isolated computers — 8 bps without any shared hardware or network connection.

- **Magnetic field covert channel (MAGNETO / ODINI)** — Modulates data onto CPU-generated magnetic field fluctuations — MAGNETO uses smartphone magnetometer as receiver; ODINI targets Faraday-cage-shielded systems.

- **Air-gap bridging via GSM/EM emissions (GSMem)** — Uses CPU memory bus operations to generate specific electromagnetic emissions detectable by a nearby mobile phone's GSM receiver — demonstrated on air-gapped systems in a shielded room.

---

### AI-Assisted Reconnaissance

- **Generative AI for internal document and email structure reconstruction** — Uses LLMs fed with public OSINT corpus to synthesize realistic internal documentation, phishing emails, and IT policy documents — produces authentic-sounding pretexts indistinguishable from genuine internal communications.

- **AI-driven pattern-of-life synthesis from CCTV and social media** — Aggregates public CCTV feeds, social media check-ins, ADS-B data, and LinkedIn activity through ML models to build behavioral profiles — predicts physical location windows and identifies vulnerability periods in security coverage.

- **ML-based secret detection at scale** — Applies NLP and pattern recognition models to GitHub, Pastebin, dark web, and job postings to detect API keys and credentials with >95% precision — 10x reduction in false positives vs. regex scanning.

- **Digital twin construction of OT network from packet captures** — Uses ML to infer full OT network topology, device roles, and process state from minimal passive packet capture — maps an ICS network and models the physical process without active scanning.

- **Browser GPU/CPU timing side-channel for cross-origin inference** — Exploits GPU/CPU rendering timing variations from browser execution to infer whether specific cross-origin resources exist — bypasses SameSite cookies and CORP in some browser configurations.

---

### Virtualization & Trusted Execution

- **Cloud hypervisor type and nested virtualization detection** — Detects hypervisor type (VMware, KVM, Hyper-V, Xen) and nested virtualization via CPUID leaf responses and network-based timing — informs hypervisor-specific VM escape CVE selection.

- **Cloud function cold-start execution environment reuse** — Exploits serverless function warm container reuse to access residual data (global variables, /tmp, database connection pools) from previous invocations — confirmed in AWS Lambda, GCP Cloud Functions.

- **vTPM / vSGX enclave boundary scan** — Probes virtualised TPM and Intel SGX enclave interfaces over network-accessible APIs — maps trust boundary assumptions and identifies attestation weaknesses.

- **Enclave side-channel (L1TF, MDS, Foreshadow) applicability mapping** — Assesses applicability of Intel L1TF, MDS, and Foreshadow attacks based on co-location inference — Foreshadow-VMM defeats SGX isolation entirely.

- **Container escape surface via exposed /proc, /sys, and capabilities** — Tests network-accessible container management APIs for /proc, /sys exposure and elevated capability sets — identifies containers running as privileged or with dangerous capabilities (SYS_ADMIN, NET_ADMIN).

- **Linux eBPF program map and helper introspection** — Enumerates loaded eBPF programs and BPF maps via remotely accessible interfaces — eBPF with JIT and unrestricted helper access represents a kernel-level attack surface from userspace.

- **Kernel module symbol and version cross-reference** — Cross-references leaked kernel symbols (from /proc/kallsyms, dmesg, or crash dumps) with version strings to identify precise kernel versions and select known-good exploit offsets.

- **Hardware TEE fault injection profiling via remote attestation** — Probes remote attestation interfaces to profile TEE fault injection attack surface — identifies whether implementations are susceptible to fault-induced instruction skipping.

---

### Legacy, Mainframe & Storage

- **Mainframe (z/OS) TN3270, FTP, and CICS region discovery** — Fingerprints z/OS mainframe services via TN3270 terminal emulation, FTP banners, and CICS transaction names — mainframes often run critical financial applications with decades-old security configurations.

- **AS/400 (IBM i) DDM/DRDA service enumeration** — Discovers IBM i DDM and DRDA services and tests for unauthenticated or default-credential database access — AS/400 hosts mission-critical ERP data in many manufacturing and financial organizations.

- **NFS export list and anonymous mount path discovery** — Discovers NFS export listings and tests for anonymous mount access — historically common in Unix/Linux environments with legacy configurations.

- **iSCSI target discovery and CHAP authentication bypass** — Enumerates iSCSI targets and tests for CHAP bypass or default credentials — grants block-level storage access equivalent to direct disk access.

- **FCoE and NVMe-over-Fabrics discovery controller enumeration** — Discovers Fibre Channel over Ethernet and NVMe-oF controllers — relevant in high-performance storage network environments.

- **RDMA (RoCE, InfiniBand) subnet manager query** — Queries RDMA subnet managers to enumerate nodes and topology of high-performance computing and storage networks — RDMA bypasses the CPU and OS network stack entirely.

---

### Specialized Domain

- **Aircraft SATCOM (SwiftBroadband, Classic Aero) and IFE interface discovery** — Discovers aircraft satellite communications and in-flight entertainment IP interfaces — demonstrated to have network separation weaknesses between passenger and avionics networks.

- **In-vehicle IFE Wi-Fi and ADAS sensor network mapping** — Maps in-vehicle infotainment Wi-Fi and ADAS sensor communication networks accessible over IP — relevant for automotive security research.

- **Maritime ECDIS and VDR network integration** — Discovers Electronic Chart Display and Voyage Data Recorder network interfaces — maritime navigation systems have well-documented isolation failures.

- **Drone Remote ID broadcast and FLARM data capture** — Captures drone Remote ID (ASTM F3411) broadcasts and FLARM collision avoidance data via network-connected receivers — maps UAV activity for counter-drone intelligence.

- **Telematics FMS-standard CAN PGN mapping** — Maps FMS-standard CAN parameter group numbers to fleet vehicle telemetry via IP gateways — relevant for fleet management platform security assessment.

- **Quantum random number generator entropy quality test** — Tests quantum RNG entropy source quality via publicly accessible network APIs — weak entropy sources affect all downstream cryptographic operations.

- **Photonic chip interconnect and co-packaged optics side-channel** — Exploits photonic chip management interfaces to detect information leakage via optical power measurements — emerging research area as co-packaged optics become mainstream in data center networking.

---

*End of Reference — v1.0*

> **Coverage summary:** 13 categories · 250+ techniques · Passive, active, and exotic methods · Includes real-world exploitation context and pipeline integration notes.
