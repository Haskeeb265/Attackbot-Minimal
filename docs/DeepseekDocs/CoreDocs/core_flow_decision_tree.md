# Core Flow & Decision Tree
┌───────────────────────────────────────────────────────────────────────┐
│ INPUT: Scraper JSON │
│ (program details, policy text, in_scope assets with eligibility, │
│ weaknesses catalog) │
└────────────────────────────────┬──────────────────────────────────────┘
│
▼
┌───────────────────────────────────────────────────────────────────────┐
│ 0. INPUT VALIDATION & ENRICHMENT │
│ • Verify all eligible_for_bounty=true assets present │
│ • Classify asset types: URL, WILDCARD (expand to subdomains), │
│ OTHER → inspect: if URL matches github.com → flag as SOURCE_CODE, │
│ else treat as generic web/API target. │
│ • Parse policy text: extract forbidden actions (e.g. "no phishing"), │
│ allowed hours, rate limits, contact emails. │
│ • Authenticate if credentials provided in program data; otherwise │
│ use system email to register account. │
│ • If MFA/CAPTCHA encountered: signal HITL → pause, wait for human │
│ input, then resume seamlessly. │
└────────────────────────────────┬──────────────────────────────────────┘
│
▼
┌───────────────────────────────────────────────────────────────────────┐
│ 1. GOALACT: CREATE DYNAMIC PLAN │
│ • Build initial attack graph from program data, MITRE ATT&CK, │
│ CySec Knowledge Graph, CrystalBall. │
│ • Graph Advisor scores nodes (probability × impact), reduces FPs. │
│ • STRUCTUREDAGENT maintains multiple parallel attack branches. │
│ • Theory-Code2 loads pre‑compiled skills if matching situation. │
│ • SymAgent suggests analogous attacks from past findings DB. │
│ • Output: prioritized task queue (branches). │
└────────────────────────────────┬──────────────────────────────────────┘
│
▼
┌───────────────────────────────────────────────────────────────────────┐
│ 2. EXECUTION LOOP (for each branch) │
│ ┌─ 2a. Recon: fingerprinter, port scan, tech detection, endpoint │
│ │ discovery, API schema extraction, JavaScript analysis. │
│ │ • Use passive/active probes respecting scope & policy. │
│ │ • If CAPTCHA/MFA appears: HITL pause. │
│ │ │
│ ├─ 2b. Exploit: select payloads based on recon results. │
│ │ • Chain vulnerabilities using graph traversal. │
│ │ • Theory-Code2 reuses known exploit sequences. │
│ │ • Before any destructive/intrusive action: HITL gate │
│ │ (show plan, confidence, risk; human approves/denies). │
│ │ • VulnBot/Metasploit attempts exploitation in sandbox. │
│ │ • If rate-limited: backoff and resume. │
│ │ │
│ └─ 2c. Verify: after exploit, retest to confirm vulnerability. │
│ │ • Check scope again (did we wander out‑of‑scope? → failsafe abort). │
│ │ • If success: record full reproduction steps. │
│ │ • If partial: log as partial finding, continue deeper. │
│ │ • If fail: update graph, deprioritize branch. │
└────────────────────────────────┬──────────────────────────────────────┘
│
▼
┌───────────────────────────────────────────────────────────────────────┐
│ 3. REPORT GENERATION │
│ • Gather all confirmed (and significant partial) findings. │
│ • Format per HackerOne guidelines: title, severity, steps to reproduce,│
│ impact, attachments. │
│ • Human review → manual submission. │
└───────────────────────────────────────────────────────────────────────┘



**Key decision points (embedded in flow):**
- Every time GoalAct replans, Graph Advisor reprioritizes.
- STRUCTUREDAGENT explores 2–3 highest-priority branches concurrently.
- If branch exhausts without success, its knowledge updates the graph for learning.
- HITL gates: before any destructive action, after CAPTCHA/MFA, before final report.
- Failsafe: if agent accidentally targets out‑of‑scope asset, it must log and abort that branch.