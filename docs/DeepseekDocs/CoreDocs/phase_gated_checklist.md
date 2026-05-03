# Phase‑Gated Implementation Checklist

Each phase produces a **visible, testable output**. Do not move to the next phase until the current output matches expectation.

| Phase | Deliverable | Testable Output |
|-------|-------------|-----------------|
| **0. Foundation** | PostgreSQL + Neo4j + NATS running locally (Docker Compose). Basic agent shell that can log to console. | `docker compose up` and see "Agent running..." log. |
| **1. Input Pipeline** | Scraper JSON parser + validator. Classifies assets, extracts policies, expands wildcards (using subfinder or DNS brute). Flags SOURCE_CODE if GitHub URL. | Run on your 1password CTF JSON; see console output of parsed assets with classifications. |
| **2. Recon Agent** | A single agent that takes one asset (URL) and runs: tech fingerprint (Wappalyzer-like), port scan (naabu), endpoint discovery (gospider), and outputs a JSON summary. Respects scope. | Run on `https://bugbounty-ctf.1password.com/` (or a test site); get tech list, open ports, discovered URLs. |
| **3. GoalAct + Graph Advisor (Skeleton)** | GoalAct generates an attack plan (text) from the recon summary using Mistral API. Graph Advisor scores nodes. No execution yet. | Console shows: "Plan: [SQLi test → command injection → ...] with scores." |
| **4. Theory‑Code2 Skill Library** | Store 3–5 hardcoded “skills” (e.g., SQL injection check, open S3 bucket check). Agent can retrieve and execute them without LLM call. | Run skill on a known vulnerable test app (DVWA) and see expected result. |
| **5. Execution Loop** | Connect agents: GoalAct → tools (Nuclei, sqlmap, Metasploit‑via‑RPC). VulnBot placeholder. Full loop: recon → plan → exploit (safe only). HITL gate before any destructive action. | Run on a controlled vulnerable VM (like Metasploitable); see it find and (safely) exploit at least one vulnerability. |
| **6. STRUCTUREDAGENT & Branching** | Extend GoalAct to maintain multiple parallel branches (max 3). Use asyncio or threading. | Run on target with multiple potential vulns; see logs showing branches being explored concurrently. |
| **7. SymAgent & Past Findings DB** | Create PostgreSQL table for past findings, embed with sentence‑transformers (free, runs on CPU). SymAgent retrieves analogous findings for a given recon summary. | Feed it a recon summary of a target similar to a past bug; see relevant past findings printed. |
| **8. Scope & Policy Enforcer** | Implement Chain of Responsibility: scope checker → policy checker → rate limiter → HITL → tool executor. Rate limiter uses token bucket. | Deliberately try to exploit an out‑of‑scope asset; see it blocked with log message. |
| **9. Verification & Partial Findings** | After exploit success, retest. If partial, log and continue deeper (not stopping). | On a test target with a partial SQLi, see log “Partial finding: … exploring deeper”. |
| **10. Report Generator** | Collect all findings, format as Markdown with HackerOne fields. | Run on completed scan; open the report file and verify it’s submission‑ready. |
| **11. 24/7 Self‑Healing** | Add health checks, restart on crash, token budget monitor (fallback to heuristics if free API exhausted). | Leave it running overnight on a target; check logs in morning — no crashes, progress made. |

**Checkpoint verification:** After each phase, you (the human) inspect the output manually. Do not proceed if output is wrong or missing.