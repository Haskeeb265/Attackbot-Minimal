# Module Contract Specification

| Module | Responsibility | Inputs | Outputs | Events Published | Events Subscribed |
|--------|----------------|--------|--------|------------------|-------------------|
| **InputParser** | Validate scraper JSON, extract assets, classify types, parse policy, expand wildcards | Scraper JSON file | `ValidatedProgram` object (assets, policy rules, credentials) | `ProgramLoaded`, `AssetAdded`, `AssetClassified` | (none) |
| **AssetClassifier** | Determine if `OTHER` is a source code repo (GitHub, GitLab, etc.) | `Asset` (type `OTHER`) | `Asset.type` updated (e.g., `SOURCE_CODE`) | `AssetClassified` | `AssetAdded` |
| **RepoCloner** | Clone source code from GitHub URL, extract into local sandbox | `Asset` of type `SOURCE_CODE` | Local directory path with code | `RepoCloned` | `AssetClassified` |
| **ReconAgent** | Fingerprint technology, scan ports, discover endpoints, analyze JS, fetch API docs | `Asset` of type `URL` or `WILDCARD` | `ReconReport` (tech stack, open ports, discovered URLs, JS endpoints, API schemas) | `ReconCompleted` | `AssetAdded` |
| **GoalActPlanner** | Dynamically creates and updates global attack plan using LLM (Mistral) | `ReconReport`, `AttackGraph`, past findings | `Plan` (ranked list of actions/branches) | `PlanUpdated` | `ReconCompleted`, `BranchCompleted`, `NewFinding` |
| **GraphAdvisor** | Scores attack graph nodes (probability, impact, FP risk), prioritizes surfaces, generates explanations | `AttackGraph`, `ReconReport` | `ScoredGraph` (annotated nodes) | `GraphScored` | `PlanUpdated`, `ReconCompleted` |
| **STRUCTUREDAGENT** | Maintains multiple parallel attack branches, coordinates execution | `Plan` | `BranchState` updates | `BranchStarted`, `BranchCompleted`, `BranchAborted` | `PlanUpdated` |
| **TheoryCode2** | Stores reusable attack workflows; when triggered, executes them without new LLM planning | `Action` request, context | `ActionResult` | `SkillExecuted` | `ActionRequest` (if skill matches) |
| **SymAgent** | Traverses past findings DB, suggests analogous exploit paths | `ReconReport`, `AttackGraph` | `SuggestionList` | `SuggestionGenerated` | `ReconCompleted` |
| **CrystalBall** | Generates attack graph from assets, vulnerabilities, MITRE ATT&CK, CySec KG | `ValidatedProgram` | `InitialAttackGraph` | `GraphGenerated` | `ProgramLoaded` |
| **VulnBot** | Executes active exploitation (wraps Metasploit, custom scripts) | `ExploitPlan`, `Target` | `ExploitResult` (success/fail, evidence) | `ExploitCompleted`, `ExploitFailed` | `ActionRequest` (exploit type) |
| **RateLimiter** | Token‑bucket throttling per domain; respects program policy (requests/sec) | `ActionRequest` | approve/delay | (none) | `ActionRequest` |
| **ScopeEnforcer** | Checks target against in‑scope list, enforces policy rules (no phishing, etc.) | `ActionRequest` | allow/deny | `OutOfScopeBlocked` if denied | `ActionRequest` |
| **HITLGate** | Pauses execution, notifies human, waits for input (CAPTCHA, MFA, destructive action approval) | `HITLRequest` (type, prompt) | `HITLResponse` (approved/input) | `HITLPaused`, `HITLResumed` | `ActionRequest` (if action requires HITL) |
| **VerificationAgent** | After exploit, retest to confirm vulnerability; check scope again; handle partial findings | `ExploitResult`, `Target` | `VerifiedFinding` or `PartialFinding` | `BugConfirmed`, `PartialFindingFound` | `ExploitCompleted` |
| **ReportGenerator** | Collects all findings, formats as HackerOne‑style report (Markdown) | `VerifiedFinding[]`, `ProgramDetails` | `Report.md` (title, severity, steps, impact) | `ReportGenerated` | `BugConfirmed`, `PartialFindingFound` |
| **LoggerObserver** | Logs all events, saves detailed JSON/MD logs, also writes summary to console | all events | local log files | (none) | all events |
| **TokenBudgetMonitor** | Tracks Mistral/Groq API usage; if near limit, switches to cheaper heuristics or pauses | API request count, remaining tokens | mode switch signal | `BudgetWarning`, `BudgetExhausted` | (internal timer) |

**Events (NATS topics):**
- `asset.added`, `asset.classified`, `repo.cloned`
- `program.loaded`, `policy.parsed`
- `recon.completed`
- `plan.updated`, `branch.*`
- `action.request`, `action.approved`, `action.denied`, `action.completed`
- `exploit.completed`, `exploit.failed`
- `bug.confirmed`, `partial.finding`
- `report.generated`

**Human‑in‑the‑Loop contract:**
- HITLGate will fire events `hitl.paused` and wait for a response on `hitl.resume` with the human’s input.
- The system will not proceed with the blocked action until resumed.
- For CAPTCHA/MFA, the gate presents the challenge; human solves it; system continues.

**Token Budget Strategy:**
- GoalAct and SymAgent use Mistral (large model) only for complex tasks.
- Groq (fast, free) used for tool output summarization, classification, simple yes/no.
- If token budget reaches 80%, the system stops spawning new branches and finishes current ones.
- Theory‑Code2 execution entirely bypasses LLM (no tokens).