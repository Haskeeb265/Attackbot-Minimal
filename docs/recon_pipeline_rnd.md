# 📚 Reconnaissance Tools & Techniques – Complete Reading Materials & Links

## 1. DNS Enumeration & Measurement

### Tool Documentation
- [OWASP Amass – User Guide & Internals](https://github.com/owasp-amass/amass/blob/master/doc/user_guide.md)
- [Subfinder – Sources & API Keys](https://blog.projectdiscovery.io/subfinder-sources-and-api-keys/)
- [PureDNS – Features & Wildcard Handling](https://github.com/d3mondev/puredns#features)
- [Massdns – High‑speed Resolver](https://github.com/blechschmidt/massdns)
- [Altdns – Permutation Generation](https://github.com/infosec-au/altdns)
- [DNSGen – Subdomain Permutation](https://github.com/ProjectAnte/dnsgen)
- [Gotator – Advanced Permutation](https://github.com/Josue87/gotator)
- [Regulator – ML‑Based Permutation](https://github.com/cramppet/regulator)

### Research Papers & Articles
- [Passive DNS Replication (Weimer 2005)](https://www.first.org/conference/2005/papers/florian-weimer-paper-1.pdf)  
- [Kafka and the DNS Camel (Hu et al., 2022)](https://dl.acm.org/doi/10.1145/3517745.3561447)  
- [Measuring the Practical Impact of DNSSEC (Chung et al., 2016)](https://www.usenix.org/conference/usenixsecurity16/technical-sessions/presentation/chung)  
- [Sonar FDNS Dataset – Rapid7](https://opendata.rapid7.com/sonar.fdns_v2/)

### Books
- *DNS and BIND* (5th Edition) – Liu & Albitz (O’Reilly, 2006)

---

## 2. Internet‑Scale Scanning & Port Probes

### Tool Documentation
- [Masscan – GitHub & Manual](https://github.com/robertdavidgraham/masscan)
- [Nmap – Official Book & Docs](https://nmap.org/book/)
- [Naabu – ProjectDiscovery](https://github.com/projectdiscovery/naabu)
- [RustScan – Speed Benchmarks & Docs](https://rustscan.github.io/RustScan/)
- [ZMap – Internet‑Wide Scanner](https://zmap.io/)

### Research Papers & Articles
- [ZMap: Fast Internet‑wide Scanning (Durumeric et al., 2013)](https://www.usenix.org/conference/usenixsecurity13/technical-sessions/paper/durumeric)  
- [Masscan: Scanning the Entire Internet (Graham 2013)](https://github.com/robertdavidgraham/masscan) – see README  
- [Censys: A Search Engine Backed by Internet‑Wide Scanning (2015)](https://dl.acm.org/doi/10.1145/2810103.2813703)  
- [An Internet‑wide View of IPv6 (Czyz et al., 2016)](https://dl.acm.org/doi/10.1145/2987443.2987447)

---

## 3. Web Application Reconnaissance & Crawling

### Tool Documentation
- [HTTPx – Toolkit & Tech Detection](https://github.com/projectdiscovery/httpx)
- [Katana – Next‑Gen Crawler](https://blog.projectdiscovery.io/introducing-katana/)
- [Feroxbuster – Recursive Content Discovery](https://epi052.github.io/feroxbuster-docs/)
- [GoSpider – Fast Web Spider](https://github.com/jaeles-project/gospider#about)
- [Hakrawler – Simple Crawler](https://github.com/hakluke/hakrawler)

### Research Papers & Articles
- [Crawling the Hidden Web (Raghavan & Garcia‑Molina, 2001)](https://dl.acm.org/doi/10.5555/645927.672025)  
- [JavaScript‑aware Web Crawling (Mesbah et al., 2012)](https://link.springer.com/chapter/10.1007/978-3-642-27997-3_31)

---

## 4. Content Discovery & Fuzzing

### Tool Documentation
- [FFUF – Advanced Fuzzing Guide](https://github.com/ffuf/ffuf#advanced-usage)
- [Best Practices for Web Directory Brute Force (PortSwigger)](https://portswigger.net/support/using-burp-suite-intruder-for-directory-brute-force)

### Research Papers
- [A Survey of Web Application Vulnerability Discovery (Antunes & Vieira, 2012)](https://dl.acm.org/doi/10.1145/2180882.2180884)  
- [Fuzzing: The State of the Art (Miller et al., 2007)](https://ieeexplore.ieee.org/document/4273262)

---

## 5. JavaScript Analysis & Client‑Side Security

### Tool Documentation
- [LinkFinder – Extract Endpoints](https://github.com/GerbenJavado/LinkFinder)
- [SecretFinder – Find Secrets in JS](https://github.com/m4ll0k/SecretFinder)
- [JSParser – Parse JavaScript](https://github.com/nahamsec/JSParser)

### Research & Talks
- [JavaScript Source Maps – Deep Dive (MDN)](https://developer.mozilla.org/en-US/docs/Tools/Debugger/How_to/Use_a_source_map)  
- [Mining the Dark Matter of JavaScript for Bugs (René Robert, Hack.lu 2021)](https://www.youtube.com/watch?v=pm32IpjQqZg)

---

## 6. Mobile Application Security Analysis

### Tool Documentation
- [MobSF – Mobile Security Framework](https://mobsf.github.io/docs/)
- [Frida – Dynamic Instrumentation Toolkit](https://frida.re/docs/)
- [APKTool – Reverse Engineering APK](https://github.com/iBotPeaches/Apktool)
- [Appium – Mobile Automation](http://appium.io/docs/en/latest/)

### Research Papers & Books
- [Android Permissions Demystified (Felt et al., 2011)](https://dl.acm.org/doi/10.1145/2046707.2046779)  
- *Android Security Internals* – Nikolay Elenkov (No Starch Press, 2014)  
- *iOS Application Security* – David Thiel (No Starch Press, 2016)

---

## 7. Cloud Resource Enumeration

### Tool Documentation
- [cloud_enum – Multi‑Cloud Enumeration](https://github.com/initstring/cloud_enum)
- [S3Scanner – AWS S3 Bucket Scanner](https://github.com/sa7mon/S3Scanner)
- [GCPBucketBrute – GCP Bucket Enumeration](https://github.com/RhinoSecurityLabs/GCPBucketBrute)

### Research Papers
- [CloudRanger: Detecting Cloud Resource Exposure (Fernandes et al., 2016)](https://ieeexplore.ieee.org/document/7546498)  
- [Understanding AWS Control Plane Security (Kalinin et al., 2019)](https://www.usenix.org/conference/usenixsecurity19/presentation/kalinin)

---

## 8. Vulnerability Scanning & Subdomain Takeovers

### Tool Documentation
- [Nuclei – Template Writing Guide](https://nuclei.projectdiscovery.io/templating-guide/)
- [Subjack – Subdomain Takeover](https://github.com/haccer/subjack)
- [Subzy – Subdomain Takeover Checker](https://github.com/LukaSikic/subzy)

### Research Papers
- [Can I Take Over Your DNS? (Liu et al., 2016)](https://www.ieee-security.org/TC/SP2016/papers/2034a767.pdf)  
- [Subdomain Takeover: Analysis and Detection (Shuaib et al., 2020)](https://ieeexplore.ieee.org/document/9072185)

---

## 9. Protocol Analysis (HTTP/2, QUIC, WebSockets, SSE, gRPC, GraphQL)

### Documentation & Papers
- [HTTP/2 Explained (Daniel Stenberg)](https://daniel.haxx.se/http2/)
- [QUIC: A UDP‑Based Multiplexed and Secure Transport (Langley et al., 2017)](https://dl.acm.org/doi/10.1145/3098822.3098842)
- [gRPC Design & Documentation](https://grpc.io/docs/)
- [GraphQL Specification & Security](https://graphql.org/learn/)

---

## 10. Continuous Monitoring & OSINT

### Tool Documentation
- [CertStream – Real‑Time CT Monitoring](https://github.com/CaliDog/certstream-python)
- [dnstwist – Domain Permutation Detection](https://github.com/elceef/dnstwist)
- [PasteHunter – Pastebin Monitoring](https://github.com/kevthehermit/PasteHunter)

### Research Papers & Articles
- [Pastebin as a Threat Intelligence Source (Khandelwal, SANS 2016)](https://www.sans.org/white-papers/36942/)

---

## 11. General Reconnaissance Methodology Books

- [The Web Application Hacker’s Handbook (2nd Edition)](https://www.wiley.com/en-us/The+Web+Application+Hacker%27s+Handbook%3A+Finding+and+Exploiting+Security+Flaws%2C+2nd+Edition-p-9781118026472)
- [The Hacker Playbook 3 – Peter Kim](https://www.amazon.com/Hacker-Playbook-Practical-Penetration-Testing/dp/1980901759)
- [RTFM: Red Team Field Manual – Ben Clark](https://www.amazon.com/RTFM-Red-Team-Field-Manual/dp/1494295504)
- [Bug Bounty Bootcamp – Vickie Li](https://nostarch.com/bug-bounty-bootcamp)
- [OSINT Techniques (10th Edition) – Michael Bazzell](https://inteltechniques.com/book1.html)

---

**Note**: Papers without a direct open-access link can usually be found on the authors’ websites or via Google Scholar. The above list covers all the documentation, GitHub repos, and key research referenced in the **Ultimate Reconnaissance Pipeline v5.0** knowledge base.