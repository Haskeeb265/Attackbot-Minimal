# Attackbot_v2 — Project Context & Architecture Reference

This document exists to give a coding assistant (or a new contributor) full context
on Attackbot_v2 without needing to reconstruct it from scattered conversation
history. It covers what the project is, what's been decided and why, what's built,
what's next, and the coding conventions this project follows. Treat every
"decision" section below as settled unless explicitly told otherwise — several of
these were arrived at after rejecting simpler-looking alternatives, and the
rejection reasons matter as much as the decisions.

---

## 1. What Attackbot_v2 Is

Attackbot_v2 is an autonomous vulnerability discovery engine targeting public
HackerOne bug bounty programs. It is built from four top-level operations:

1. **Scraping** — pulls program metadata, scope, weaknesses, and exclusions from
   HackerOne's Hacker API.
2. **Recon** — a five-stage internal pipeline (see §5) that takes ingested program
   data and produces a validated, fingerprinted attack surface.
3. **Pentesting** — not yet started.
4. **Reporting** — not yet started.

**Important distinction:** the "five-stage pipeline" (Stage 0–4) referenced
elsewhere in this project is internal to the *recon* operation only. It is not the
architecture of the whole project. Scraping, pentesting, and reporting are
separate top-level operations with their own internal structure (or none yet).

**HackerOne handle used for testing/reference:** `p0zzam`.

---

## 2. Current State (as of this doc)

- **Scraping operation:** functionally split into two scrapers —
  `program_scraper` (fetches and filters program handles, e.g. by
  `bounty_eligible: true`) and `program_detail_scraper` (takes filtered handles
  one at a time and fetches full program detail — scopes, weaknesses,
  exclusions). Output shape is documented in §6.
- **Database layer:** fully built and smoke-tested. Schema, query modules, and
  connection management are done (see §4).
- **Active work:** building the ingestion pipeline that connects scraper output
  to the DB layer, orchestrated from `main.py`. This is a **one-shot job on
  startup** — not a polling/interval loop — that runs in a background thread so
  it doesn't block whatever else `main.py` does. See §7 for the target design
  and §8 for known-bad patterns to avoid.
- **Recon operation:** not started. Begins after the scraping/DB/ingestion work
  is complete and stable.

---

## 3. Tech Stack & Environment

- **Language/runtime:** Python 3.14
- **OS:** Windows, developed via PowerShell
- **Database:** PostgreSQL 16 Alpine, run via Docker Compose
- **DB driver:** psycopg3 + psycopg_pool for all runtime queries
- **Schema tooling:** SQLAlchemy models used *only* for Alembic schema diffing —
  never imported at runtime. Alembic used for migration versioning.
- **LLM providers:** Cerebras (primary), Groq (fallback) — both running
  llama-3.3-70b. Rate limits are shared across all services and centrally managed
  via a single root `config.py`, since all services draw from one quota.
- **Architecture pattern for recon:** GoalAct — an LLM-driven goal-action loop.

---

## 4. Database Layer (Built & Locked In)

### 4.1 Stack decisions

- PostgreSQL 16 Alpine via Docker Compose.
- psycopg3 + psycopg_pool for all runtime queries — no ORM at runtime.
- SQLAlchemy models exist solely to let Alembic autogenerate schema diffs; they
  are never imported or instantiated outside of migration generation.
- Alembic for migration versioning, but see the migration strategy note below —
  the initial schema was **not** created via `alembic upgrade head`.

### 4.2 Schema — four tables

- **`bounty_master`** — one row per program. Unique constraint on `handle`.
- **`bounty_detail`** — scoped assets for a program. FK to `bounty_master`.
  `UNIQUE(master_id, scope_type, scope_identifier)`.
- **`program_weaknesses`** — persisted weakness rulesets per program. FK to
  `bounty_master`. Uses delete-then-insert replace pattern on update.
- **`bounty_exclusion`** — persisted exclusion rulesets per program. FK to
  `bounty_master`. Uses delete-then-insert replace pattern on update.

Both `program_weaknesses` and `bounty_exclusion` are **persisted DB tables, not
runtime API calls**. This is a deliberate architecture decision: Stage 1 of recon
(LLM classification) reads weaknesses and exclusions from the DB rather than
hitting the HackerOne API live. This decouples recon from HackerOne API
availability/rate limits during classification.

### 4.3 Migration strategy

`db/init/001_schema.sql` auto-runs on first container boot and creates the
schema directly. Alembic was backfilled *after the fact* with a hand-written
`0001_baseline_schema.py`, stamped as applied via `alembic stamp 0001` — it was
never run via `upgrade head`, since the schema already existed from the init
script. **Principle:** when an init SQL script pre-creates the schema outside
Alembic, the correct move is a hand-written baseline migration stamped as
applied, not an autogenerated one that gets actually run (which would either
conflict or be a no-op against reality).

### 4.4 `shared/db.py` — connection & query primitives

Plain module of top-level functions, not a class, not a repository object:

```python
get_conn()          # context manager, yields a pooled connection
atomic(conn)         # context manager, wraps conn.transaction()
fetch_one(conn, query, params=())
fetch_all(conn, query, params=())
execute(conn, query, params=())
now()                 # UTC-aware datetime.now()
close()               # closes the pool; call once at process shutdown
```

Backed by a single `psycopg_pool.ConnectionPool`, created eagerly at import time
with `min_size=2, max_size=10`, `row_factory=dict_row`.

**Unit-of-work rule (important, applies everywhere):** only top-level
orchestrating code calls `get_conn()` / `atomic()`. Query functions in
`db/queries/*.py` always receive `conn` as a parameter — they never open their
own connection. This is what makes multi-table ingestion atomic: the caller
controls the transaction boundary, not the individual query functions.

**Exception to watch:** `update_weaknesses()` and `update_exclusions()` in the
query modules *do* call `db.atomic(conn)` internally (to make their own
delete-then-insert pairs atomic when called standalone). This is safe to nest
inside an outer `atomic()` block because psycopg3's `conn.transaction()` uses
savepoints when nested — it does not open a conflicting new transaction. Don't
"fix" this by stripping the inner `atomic()` calls; it's intentional.

### 4.5 Query modules (`db/queries/`)

Four modules, one per table: `bounty_master.py`, `bounty_detail.py`,
`bounty_weaknesses.py`, `bounty_exclusions.py`. All follow:

```python
import shared.db as db

def some_query(conn, ...):
    ...
```

Never `from shared.db import fetch_one` etc. — always the module-qualified
`db.fetch_one(...)` form, for consistency and to make call sites obviously
DB-touching at a glance.

Each module has (roughly): an `add_*` insert, an `upsert_*` (where relevant),
`get_*_by_id`, `get_*_by_master_id` / equivalent, `list_active_*`, and either
`update_*` + `delete_*` (mutable rows) or a `delete_then_insert`-style
`update_weaknesses` / `update_exclusions` replace function (immutable-content
rows).

### 4.6 Write pattern per table — why they differ

| Table | Write pattern | Why |
|---|---|---|
| `bounty_master` | `INSERT ... ON CONFLICT (handle) DO UPDATE` (upsert) | Dedup falls out naturally from the unique constraint on `handle`. |
| `bounty_detail` | `INSERT ... ON CONFLICT (master_id, scope_type, scope_identifier) DO UPDATE` (upsert) | **Not** delete-then-insert, deliberately. Downstream recon stages may hold references to specific `bounty_detail.id` values across runs. Delete-then-insert would silently invalidate those FK references on every re-scrape. Upsert preserves row identity. |
| `program_weaknesses` | Delete-then-insert (full replace) | No historical continuity needed — only the current ruleset matters. Simpler than diffing. |
| `bounty_exclusion` | Delete-then-insert (full replace) | Same reasoning as weaknesses. |

### 4.7 Index note

`UNIQUE(master_id, scope_type, scope_identifier)` on `bounty_detail` already
provides leftmost-prefix B-tree index coverage for `WHERE master_id = ?` queries.
A separate index on `master_id` alone would be redundant. Only
`idx_bounty_exclusion_master_id` is a genuinely needed standalone index (that
table has no compound unique constraint covering `master_id` as a prefix).
**Principle:** before adding an index, check whether an existing unique
constraint already covers the query pattern as a leftmost prefix.

### 4.8 Smoke test

A full lifecycle test (insert → read → update → replace → delete, across all
four tables) passed 100% inside a single rolled-back transaction. Implementation
detail worth preserving: it uses a **named sentinel exception class**
(`_ForceRollback`) raised at the end of the test and caught specifically, rather
than a bare `finally: raise SystemExit(...)`. The bare-SystemExit approach
silently swallows real assertion failures/tracebacks before they can print — the
named sentinel lets genuine test failures surface normally while still
guaranteeing rollback via the exception path.

---

## 5. Recon Operation — Five-Stage Pipeline (Not Started Yet)

This is scoped for after scraping/DB/ingestion is stable. Documented here so the
DB schema and ingestion design aren't accidentally built in a way that blocks it.

- **Stage 0** — Deterministic program ingestion and normalization (no LLM).
  Produces a `ScopeManifest` JSON. This stage is deterministic specifically so
  it doesn't burn LLM rate limit budget on pure data transformation.
- **Stage 1** — LLM classification and plan generation. Reads weaknesses and
  exclusions **from the DB** (per §4.2's persistence decision), not live from
  HackerOne.
- **Stage 2** — Enumeration / horizontal.
- **Stage 3** — Validation and fingerprinting.
- **Stage 4** — Vulnerability testing / vertical.

**GoalAct loop** wraps the recon pipeline. Persistent memory is a wrapper around
the loop — it enriches the query before a run starts and writes findings back
after the run ends — without modifying the loop's internals.

**GoalAct invariants (do not violate when this gets built):**
- Full plan rewrite happens every iteration — no incremental plan patching.
- `EXECUTION_FAILED` never terminates the loop. It's one of three possible
  result states, not a stopping condition.
- The scratchpad is the planner's *sole* intra-run memory channel — no side
  channels for passing state between plan iterations.

**Three-state result system:** every action in the loop resolves to one of
`CONFIRMED_FINDING`, `CONFIRMED_EMPTY`, or `EXECUTION_FAILED`.
`EXECUTION_FAILED` is explicitly never a stopping condition — it's expected and
handled, not exceptional.

**Skill file taxonomy (planned):** `skills/recon/` with subdirectories for asset
types, program classes, and cross-cutting concerns. A deterministic
`(asset_type, stage) → [skill_files]` selection layer is planned specifically to
keep context costs predictable against the shared Cerebras/Groq rate limits.

**FastAPI layer:** planned for a future frontend. Deliberately deferred — not
being built now, don't scaffold it prematurely.

---

## 6. Scraper Output Contract

The scraper (`program_scraper` + `program_detail_scraper`) produces a JSON
structure like this, per program:

```json
{
  "handle": "cloudflare",
  "scope_count": 62,
  "scopes": [
    {
      "id": "92116",
      "asset_type": "URL",
      "asset_identifier": "dash.cloudflare.com",
      "eligible_for_bounty": true,
      "eligible_for_submission": true,
      "max_severity": "critical",
      "instruction": "The Cloudflare dashboard...",
      "confidentiality_requirement": "high",
      "integrity_requirement": "high",
      "availability_requirement": "high",
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "scope_exclusions": [
    {
      "id": "495",
      "type": "scope-exclusion",
      "attributes": {
        "category": "MITM or physical access to a user's device",
        "details": "Attacks requiring MITM or physical access...",
        "created_at": "...",
        "updated_at": "..."
      }
    }
  ],
  "weaknesses": [
    {
      "id": "12",
      "type": "weakness",
      "attributes": {
        "name": "Array Index Underflow",
        "description": "...",
        "external_id": "cwe-129",
        "created_at": "..."
      }
    }
  ]
}
```

### 6.1 Scraper internals (relevant to ingestion design)

- `program_scraper` fetches and filters handles. Filtering criteria include
  bounty eligibility (`bounty: yes/no` — currently only targeting `yes`).
- `program_detail_scraper` runs in a loop, taking filtered handles from
  `program_scraper` one at a time and fetching full detail per handle.
- The end result, as currently produced, is a JSON file matching the shape
  above (a list of these program objects).
- **API pagination:** HackerOne's `/hackers/programs` endpoint requires explicit
  `page[number]` / `links.next` handling.
- **Shared fetch requirement:** both priority-bucket filtering methods on
  `program_scraper` must share a single `_fetch_all_programs()` call — calling
  it once per bucket would double the API requests against the same endpoint.
- **`structured_scopes` rate limit:** this HackerOne endpoint has its own
  separate rate limit from the general read limit and needs a dedicated
  throttle — don't assume it shares budget with other endpoints.

### 6.2 Field mapping — scraper JSON → DB columns

This is the exact contract the ingestion layer has to bridge. Field name
mismatches and nesting differences here are the most common source of bugs —
verify against this table, not against assumption.

| Scraped JSON field | DB column | Notes |
|---|---|---|
| `handle` | `bounty_master.handle` | |
| `scope_count` | `bounty_master.scope_count` | |
| *(computed)* | `bounty_master.max_severity` | **Not present at top level.** Must be computed as the highest `max_severity` across all of that program's `scopes[]`. See §7.2 for the correct computation — a naive "if critical, set critical" special-case is wrong (see §8). |
| `scopes[].asset_type` | `bounty_detail.scope_type` | |
| `scopes[].asset_identifier` | `bounty_detail.scope_identifier` | |
| `scopes[].instruction` | `bounty_detail.scope_instructions` | |
| `weaknesses[].id` | `bounty_weaknesses.weakness_id` | **Top-level `id`, not `attributes.external_id`.** `external_id` is the CWE/CAPEC reference and is frequently `null` (e.g. every ASI-series and LLM-series weakness in real HackerOne data has `external_id: null`). Using `external_id` as `weakness_id` silently corrupts the column for a large fraction of rows. See §8. |
| `weaknesses[].attributes.name` | `bounty_weaknesses.weakness_name` | |
| `weaknesses[].attributes.description` | `bounty_weaknesses.weakness_description` | |
| `scope_exclusions[].attributes.category` | `bounty_exclusion.exclusion_category` | |
| `scope_exclusions[].attributes.details` | `bounty_exclusion.exclusion_details` | |

### 6.3 Open question — scope eligibility filtering

Real HackerOne data includes plenty of scopes with `eligible_for_bounty: false`
(e.g. Zendesk-hosted support subdomains, deprecated assets) sitting alongside
eligible ones in the same `scopes[]` array. Current decision: **ingest all
scopes regardless of `eligible_for_bounty`**, and do not add an eligibility
column to `bounty_detail` yet. Rationale: ineligible scopes still carry useful
signal for recon (they mark explicitly-off-limits assets, which matters for
respecting program rules). If Stage 1 classification later needs to filter on
this, `eligible_for_bounty` is not currently persisted and would need a schema
addition — flag this explicitly rather than silently dropping ineligible scopes
during ingestion.

---

## 7. Target Ingestion Pipeline Design

### 7.1 Ownership / transaction boundaries (the part that's easy to get wrong)

```
main.py
  └── run_ingestion_job()                 [owns: ONE get_conn() for the whole run]
        ├── get_filtered_handles()                  (program_scraper)
        └── for handle in handles:
              ├── scrape_program_detail(handle)      (program_detail_scraper)
              └── ingest_program(conn, program)       [owns: ONE atomic() per program]
                    ├── bounty_master.upsert_program
                    ├── bounty_detail.upsert_scope     (looped, one call per scope)
                    ├── bounty_weaknesses.update_weaknesses   (replace)
                    └── bounty_exclusions.update_exclusions   (replace)
```

**Why one connection for the whole run, one transaction per program:**
Opening a fresh connection per handle is wasteful and unnecessary — the pool
supports one long-lived connection just fine across a sequential loop. But
transactions must be scoped *per program*, not per run and not per query. If
program 7 of 60 fails partway through (bad data, constraint violation,
whatever), only program 7's writes should roll back. Programs 1–6, already
committed, must stay committed, and programs 8–60 must still get attempted. A
single `atomic()` wrapping the entire loop would roll back *everything* on one
bad program; no `atomic()` at all (bare calls) means a failure partway through
one program leaves that program half-ingested with no rollback at all. Per-
program `atomic()` is the only option that gives correct isolation at the right
granularity.

**Where the try/except goes:** in `run_ingestion_job`'s loop, wrapping the
`scrape_program_detail` + `ingest_program` calls for one handle — *not* inside
`ingest_program` itself. This way `ingest_program`'s `atomic()` block still
rolls back cleanly via normal exception propagation before the exception
reaches the outer `except`, and the loop continues to the next handle with the
connection still in a clean state.

### 7.2 `max_severity` computation

Correct approach — rank comparison, not a special-cased equality check:

```python
_SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

def _compute_max_severity(scopes: list[dict]) -> str | None:
    best, best_rank = None, -1
    for s in scopes:
        rank = _SEVERITY_RANK.get(s.get("max_severity"), -1)
        if rank > best_rank:
            best, best_rank = s.get("max_severity"), rank
    return best
```

See §8 for the specific bug this avoids.

### 7.3 Job trigger

**One-shot on startup**, not an interval/polling loop. Runs in a background
thread from `main.py` so it doesn't block other work `main.py` might do (none
yet, but don't design against that assumption). If a recurring re-scrape is
wanted later, that's a deliberate future decision, not something to add
speculatively now.

### 7.4 Logging

Use Python's standard `logging` module (or the project's existing
`shared/colorlog.py` if that module actually exists — confirm before importing
it; don't assume it's present). Log at minimum: job start, handle count found,
per-program success (handle + master_id + scope count), per-program failure
(handle + exception, via `logger.exception` for traceback), and a job-end
summary (ingested count / failed count).

### 7.5 Validating before wiring the live scraper

Before pointing this at the real scraper, validate `ingest_program()` against a
static sample JSON file matching §6's shape (e.g. a saved real
`program_detail_scraper` output) to catch field-mapping mistakes like the ones
in §8 without needing live API calls or dealing with scraper timing.

---

## 8. Known-Bad Patterns — Specific Bugs Already Caught in Review

These are documented because they were caught once already (in a coding
assistant's draft) and are exactly the kind of mistake likely to recur. Treat
each of these as a checklist item when reviewing new ingestion code.

### 8.1 `weakness_id` sourced from the wrong field

**Bad:**
```python
"weakness_id": attrs.get("external_id", attrs.get("name", "")),
```
This reads `attributes.external_id` (the CWE/CAPEC reference, often `null`) and
falls back to `attributes.name` when it's null — so `weakness_id` ends up
holding a CWE string for some rows and a weakness *name* for others,
inconsistently, and never the actual HackerOne weakness id.

**Correct:**
```python
"weakness_id": weakness["id"],   # top-level field, not under attributes
```

### 8.2 `max_severity` reduction using equality instead of rank comparison

**Bad:**
```python
max_severity = None
for scope in program_data.get("scopes", []):
    severity = scope.get("max_severity")
    if severity and severity != "none":
        if max_severity is None or severity == "critical":
            max_severity = severity
```
Walk through scopes `["low", "high", "medium"]` in that order: first iteration
sets `max_severity = "low"` (it was `None`). Second iteration sees `"high"` —
`max_severity is None` is now false, and `severity == "critical"` is false — so
it's skipped. `max_severity` incorrectly stays `"low"` despite a `"high"` scope
existing later in the list. This logic only correctly promotes to `"critical"`;
every other severity level is first-non-none-wins, not actually max. Use the
rank-comparison approach in §7.2 instead.

### 8.3 Dropping the per-program transaction boundary

**Bad pattern:** a method that calls `master_q.upsert_program(...)`, then loops
`detail_q.upsert_scope(...)` calls, then calls the weakness/exclusion replace
functions — with **no** `db.atomic(conn)` wrapping the whole body. The replace
functions have their own internal `atomic()` calls (safe, see §4.4), but the
master upsert and the scope-upsert loop are bare calls straight to the
connection with no surrounding transaction. If a scope upsert throws partway
through a 62-scope program, the master row and however many scopes succeeded
before the failure are already committed — a silently half-ingested program
with no rollback.

**Correct:** wrap the *entire* body of `ingest_program()` (master upsert, scope
loop, weakness replace, exclusion replace) in a single `with db.atomic(conn):`
block, per §7.1's design.

### 8.4 Scope creep into class-based / interval-based design without being asked

A draft introduced a `DataIngestionPipeline` class with `interval_seconds`,
`is_running`, and `thread` as instance attributes, plus an hourly re-scrape
loop — neither of which had been requested (the actual requirement was
one-shot on startup, per §7.3). Watch for coding assistants defaulting to more
general/reusable-looking structures than what was actually asked for.

### 8.5 Unverified imports

A draft imported `from shared.colorlog import log` without that module being
confirmed to exist in the project. Don't import project-internal modules
speculatively — confirm they exist first, or use stdlib `logging` as the safe
default.

---

## 9. Coding Conventions & Working Style (apply project-wide)

- **Architecture and design discussion happens before code.** Don't jump
  straight to a full implementation for a nontrivial piece without walking
  through the design tradeoffs first.
- **Haseeb implements code himself** unless the file is infrastructure-level
  (Docker Compose, DB schema, SQLAlchemy models, migrations). For those, a
  coding assistant producing the file directly is appropriate.
- **Pushes back on unnecessary complexity.** Already rejected in this project:
  ORM adoption at runtime, the repository pattern, generic/abstracted upsert
  helpers, history-tracking on replace-pattern tables, and
  `onupdate=func.now()` (confirmed unneeded once checked). Don't reintroduce
  these speculatively — if one seems genuinely needed, make the case for it
  explicitly rather than assuming it's wanted.
- **Function-first, not class-first**, for anything that doesn't need instance
  state. `shared/db.py` and the query modules are plain functions by design —
  match that style for new modules (e.g. the ingestion orchestrator) unless
  there's a concrete reason a class is needed.
- **Module-qualified imports for DB access:** `import shared.db as db`, then
  `db.fetch_one(...)` — not `from shared.db import fetch_one`.
- **Query functions always take `conn` as a parameter.** They never call
  `get_conn()` themselves. Only top-level orchestrating code opens connections
  or transactions.
- **Output format preference:** plain prose with ASCII diagrams and tabular
  module contracts (explicit inputs/outputs) where useful. Minimal bullet
  overuse, no excessive headers in conversational responses (this document is
  an exception, since it's a reference file, not a chat reply).
- **Close reading, willing to correct.** Verify claims against real data/code
  rather than taking them at face value — this project has already caught a
  wrong claim about a column (`triage_active`) and a redundant-index
  recommendation this way. Extend the same scrutiny to any draft code,
  including this document's own contents if something here turns out to be
  stale.

---

## 10. Tools & Resource Reference

- **Runtime:** Python 3.14, psycopg3, psycopg_pool, Docker Compose (Postgres 16
  Alpine)
- **Schema/migrations:** SQLAlchemy (diffing only, never at runtime), Alembic
- **LLM providers:** Cerebras (primary, `llama-3.3-70b`), Groq (fallback,
  `llama-3.3-70b-versatile`)
- **HackerOne Hacker API v1** — key endpoints in use: `/hackers/programs`,
  `/{handle}/structured_scopes`, `scope_exclusions`, `weaknesses`
- **Project structure:**
  ```
  shared/            # db.py, config access, cross-cutting utilities
  services/
    scraper/         # program_scraper.py, program_detail_scraper.py
    recon/           # not started
    attack/          # not started
  skills/            # recon skill files (planned)
  memory/            # GoalAct loop memory wrapper (planned)
  db/
    init/            # 001_schema.sql
    queries/         # bounty_master.py, bounty_detail.py,
                      #   bounty_weaknesses.py, bounty_exclusions.py
    ingest.py         # orchestrator (in progress)
  config.py           # root-level, shared rate-limit config
  main.py             # entry point
  ```
- **Recon codebase (planned, not yet built):** `main_loop.py`, `planner.py`,
  `scratchpad.py`, `skills/`, `result_state.py`
- **Alerting:** Discord webhook on findings (planned, not yet built)

---

*End of context document. If any section here conflicts with what's actually in
the codebase at the time you're reading this, the codebase wins — flag the
discrepancy back rather than silently trusting this file over reality.*