# Attackbot – Vulnerability Finder Module
## Technical Implementation Playbook (v1.0)

This document provides the exact commands, parsing strategies, error‑handling policies, and integration details for every technical capability within the vulnerability finder. It is the **field manual** that translates the architecture, flow, and contracts into working code.

---

## 1. Environment and Prerequisites

### 1.1 Required Tools (must be pre‑installed or installable via script)
| Tool         | Purpose                              | Install method                |
|--------------|--------------------------------------|-------------------------------|
| `nmap`/`naabu` | Port scanning                       | `apt install nmap`; `go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest` |
| `subfinder`  | Subdomain enumeration                 | `go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest` |
| `gospider`   | Web crawling (URL discovery)          | `go install github.com/jaeles-project/gospider@latest` |
| `nuclei`     | Template‑based vulnerability scanning | `go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest` |
| `sqlmap`     | SQL injection exploitation            | `apt install sqlmap` or git clone |
| Metasploit   | Exploitation framework                | `apt install metasploit-framework` (or Docker) |
| `git`        | Cloning source code repositories      | `apt install git` |
| `python3` + pip | Core language, libraries (requests, aiohttp, pg8000, neo4j, nats‑py, etc.) | standard |

### 1.2 Python Libraries (install via `pip`)
- `requests`, `aiohttp` (async HTTP)
- `python‑nmap` (Nmap wrapper)
- `neo4j` (graph DB driver)
- `psycopg2` or `pg8000` (PostgreSQL)
- `nats‑py` (NATS client)
- `valkey` (Valkey client, or use `redis` with Valkey compatible)
- `sentence‑transformers` (embeddings for SymAgent, CPU only)
- `pydantic` (data validation)

### 1.3 Configuration (env vars or config file)
- `MISTRAL_API_KEY`
- `GROQ_API_KEY`
- `NATS_URL` (default `nats://localhost:4222`)
- `VALKEY_URL` (default `redis://localhost:6379`)
- `PG_DSN`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `TOOL_SANDBOX_DIR` (default `/tmp/attackbot_sandbox`)
- `HITL_NOTIFICATION` – `terminal` (default) or `telegram_bot_token` (future)

---

## 2. Concurrency Model

- **Main branch execution**: `asyncio` event loop for cooperative multitasking.
- **Parallel branches**: Each STRUCTUREDAGENT branch runs as an `asyncio.Task`. Max 3 active branches.
- **Blocking tools**: External CLI tools (nmap, sqlmap) are run in a `ProcessPoolExecutor` to avoid blocking the event loop. Results are communicated via asyncio queues.

---

## 3. Crash Recovery & Checkpointing

- After every major step (recon completed, exploit attempted), the agent’s state (which branch, what action, current plan) is saved to PostgreSQL `agent_state` table.
- On startup, the agent checks for incomplete branches from the last run and resumes by replaying events from the event log (NATS JetStream or PostgreSQL `events` table).
- Tools that leave temporary files are cleaned up on restart via a TTL‑based directory cleaner.

---

## 4. MFA / CAPTCHA Notification Mechanism

- **During development**: use a simple blocking `input()` in the terminal. Agent prints a clear message: `[HITL] MFA token required for program X. Enter token:` and waits.
- **Production upgrade path**: use a Telegram bot to send a message to your phone and wait for a reply. The HITLGate module will implement a pluggable `Notifier` interface (initially `TerminalNotifier`).

---

## 5. Agent‑Specific Tooling & Implementation Details

### 5.1 ReconAgent

| Action             | Tool       | Command / API call                                                                 | Output Parsing                                                                                          | Error Handling                                                                                  |
|--------------------|------------|------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| Port scan          | `naabu`    | `naabu -host {target} -p - -silent`                                                | Parse lines: `host:port` → list of open ports.                                                           | If naabu not found, fallback to `nmap -p- --open -T4 {target}`. If both fail, skip and log warning. |
| Technology detect  | `whatweb` or `Wappalyzer` API | `whatweb {url} --log-json=/tmp/whatweb.json` or Python Wappalyzer | Load JSON, extract `technologies` array.                                                                 | If whatweb fails, try a simple `curl -I` to read headers (Server, X‑Powered‑By). Log limited result. |
| Endpoint discovery | `gospider` | `gospider -s {url} -o /tmp/gospider_output`                                         | Read output directory, parse URLs.                                                                       | If gospider fails, fallback to a simple Python crawler using `requests` and `BeautifulSoup`.      |
| JS analysis        | custom Python | Fetch all `.js` files discovered, scan for hardcoded secrets (regex), API endpoints (`/api/...`). | Return list of potential secrets and endpoints. | If fetch fails (403/404), skip the file. |
| API detection      | custom Python | Look for Swagger/OpenAPI endpoints (`/swagger.json`, `/api‑docs`), WSDL, GraphQL introspection. | If found, fetch and store schema. | If not found, skip. |

### 5.2 GoalActPlanner (LLM‑based)

- **Model**: Mistral (large) for plan generation and updates.
- **Prompt template**: `You are a security testing planner. Given the recon report below and the current attack graph, produce a prioritized list of attack actions. Include required tools and parameters. Respond in JSON.`
- **Output**: JSON with an array of actions, each having `action_type`, `target`, `tool`, `parameters`, `priority`, `branch_id`.
- **Fallback**: If Mistral API is unavailable or token budget exhausted, use Groq with a smaller model (e.g., `mixtral-8x7b-32768`? actually Groq supports Llama3 70B, etc.). For safety, we can fallback to a simple rule‑based planner that prioritizes based on Graph Advisor scores.

### 5.3 GraphAdvisor (LLM‑based scoring + graph queries)

- **Scoring**: Use Groq (cheaper) to score nodes (probability * impact – FP risk). Prompt: `Rate this attack path on a scale of 0-1 for likelihood, severity, and false positive risk. Output JSON.`
- **Graph queries**: Cypher queries to Neo4j to fetch paths, update scores.
- **Learning**: After each outcome, update node properties (e.g., `success_count`, `fp_count`) via Cypher.

### 5.4 STRUCTUREDAGENT

- Maintains up to 3 active `BranchState` objects in Valkey (key: `branch:{branch_id}`).
- Each branch is an asyncio task that runs the execution loop independently.
- When a branch completes or is aborted, its state is moved to a “finished” set with TTL for later analysis.

### 5.5 TheoryCode2 (Skill Library)

- **Storage**: Skills stored in PostgreSQL table `skill_library` as JSON (list of Command objects).
- **Trigger**: When GoalAct emits an `ActionRequest`, TheoryCode2 checks if the action matches a stored skill (via action_type + target fingerprint). If yes, it publishes `SkillExecuted` and returns the pre‑compiled result directly, bypassing LLM planning.
- **Creation**: After a successful new exploit sequence, the sequence is serialized and added to the library via manual review or automatic if confidence high.

### 5.6 SymAgent (Past Findings RAG)

- **Embeddings**: Use `sentence-transformers` model `all-MiniLM-L6-v2` (lightweight, CPU).
- **Retrieval**: Query `pgvector` in PostgreSQL with cosine similarity to find top‑3 analogous past findings for a given recon summary.
- **Suggestion**: Inject the analogous findings into GoalAct’s planning prompt as examples.

### 5.7 VulnBot / Metasploit Adapter

- **Wrapping**: All Metasploit interactions go through `msfrpc` (Metasploit RPC). The adapter translates `ExploitPlan` into Metasploit commands.
- **Sandbox**: Exploitation targets are strictly limited to in‑scope assets; additionally, for destructive tests, we run Metasploit inside a Docker container with network isolation (only able to reach the target). Not strictly required in MVP but recommended.
- **Rate limiting**: Before launching an exploit, the Chain of Responsibility (RateLimiter) checks the token bucket for the target domain.
- **Error handling**: If Metasploit fails, retry once. If still fails, record failure and deprioritize branch.

### 5.8 VerificationAgent

- After exploit success, re‑run the exploit with the same parameters (idempotency check).
- Perform a secondary check: if the vulnerability was SQLi, run a simple `SELECT 1` to confirm access.
- Check scope again via ScopeEnforcer.
- If only partial (e.g., error revealed but no data extraction), log as `PartialFinding` and continue execution (do not stop branch).
- Record all steps and evidence (screenshots, request/response logs) in sandbox directory.

### 5.9 ScopeEnforcer & RateLimiter (Chain of Responsibility)

- **Scope check**: Compare target host/domain against `in_scope_assets` from the parsed program.
- **Policy check**: Parse policy text for forbidden actions (e.g., “no phishing”, “no malware”). Simple keyword matching with a library of forbidden patterns. If an action matches, block it.
- **Rate limiter**: Token bucket per domain. Default: 1 request per 2 seconds (adjustable by program policy). Use Valkey to store bucket state (key: `ratelimit:{domain}`).
- **HITL gate**: Called before any action with `impact_level >= 3` (destructive). The gate uses the configured notifier to alert human and wait for approval/denial.

### 5.10 ReportGenerator

- Collects all `BugConfirmed` and notable `PartialFinding` events.
- Formats as HackerOne report:

```markdown
# Title: [type] in [endpoint]
**Severity:** high/medium/low
**Asset:** [url]
**Description:** ...
**Steps to Reproduce:**
1. ...
2. ...
**Impact:** ...
**Supporting Evidence:** (screenshots, logs)
Saves to reports/{program_handle}_{timestamp}.md.

6. Token Budget Management (Mistral & Groq)

    Mistral free API: 200K tokens per session. Reserved for GoalAct planning, GraphAdvisor complex analysis, SymAgent suggestion generation. Large model only when needed.

    Groq free tier: used for all other LLM tasks (tool output summarisation, simple classifications, GraphAdvisor scoring).

    Monitor: TokenBudgetMonitor keeps track of estimated token usage per session. When usage reaches 80%, it sets a flag:

        New branches are not started.

        GoalAct switches to a simple rule‑based planner (pre‑defined strategies ranked by Graph Advisor scores).

        Groq calls continue until budget exhausted, then fallback to local heuristics.

    Recovery: After a cooldown period or when a new session begins, the budget resets (Mistral’s session‑based limit).

7. Output Directory Structure
text

/tmp/attackbot_sandbox/
  {program_handle}/
    {asset_id}/
      recon/
        ports.txt
        tech.json
        urls.txt
      exploits/
        {exploit_id}/
          evidence/
          logs/
          result.json

    A cleanup cron job deletes directories older than 24 hours.

8. Detailed Agent Implementation Notes
8.1 Command Pattern Implementation

Every tool action is a Command dataclass:
python

from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class Command:
    action_type: str           # e.g., "port_scan", "sql_injection_test"
    target: str               # host/URL
    parameters: dict          # tool‑specific parameters
    risk_level: int = 1       # 1=safe, 3=destructive
    timeout: int = 60
    retry_count: int = 0

The execution engine takes a command, passes it through the Chain of Responsibility, then invokes the appropriate Adapter.
8.2 Tool Adapter Interface
python

class ToolAdapter:
    async def execute(self, command: Command) -> dict:
        """Run the command and return a structured result dict."""
        ...
    def parse_output(self, raw: str) -> dict:
        ...

Each tool (Nmap, sqlmap, etc.) gets its own adapter.
8.3 Chain of Responsibility Setup
python

handlers = [
    ScopeEnforcer(program),
    PolicyChecker(program),
    RateLimiter(valkey_client),
    HITLGate(notifier),
]
for handler in handlers:
    if not handler.allow(command):
        raise CommandDenied(handler.reason)

9. Immediate Next Steps for the AI Assistant

When implementing Phase 0‑2, feed the AI this playbook together with the other anchor docs and say:

    “Based on the Technical Implementation Playbook, write the ReconAgent as an asyncio‑based class that subscribes to asset.added, runs naabu/whatweb/gospider using subprocess in an executor, parses outputs, and publishes recon.completed with the correct JSON schema. Include error handling as specified.”

10. Playbook Maintenance

This document will be updated as new tools are integrated or fallback strategies change. Any modification must be reviewed and approved by you before the AI changes the corresponding code.
text


This playbook fills the gap. It tells the AI **exactly** how to execute every technical step, what to do on failure, and how to notify you for MFA. Now your set of anchor documents is truly complete. Ready to start Phase 0?The Technical Implementation Playbook is now ready. It gives the AI the exact commands, parsing rules, error handling, and MFA notification mechanism for every technical action. Combined with your four anchor docs, you now have a complete set of instructions to hand over. Ready to start Phase 0.