# Attackbot_v2 — Project Scope & Pitch

> **An autonomous vulnerability discovery engine for HackerOne bug bounty programs.**

---

# What This Is

**Attackbot_v2** is an autonomous vulnerability discovery engine designed to operate against public HackerOne bug bounty programs.

The system ingests structured program data directly from the HackerOne API, reasons over program scope, plans and executes a multi-stage reconnaissance and testing pipeline, and produces human-readable Markdown vulnerability reports—with **no human in the loop**, except for unavoidable hard stops such as CAPTCHA or MFA.

Unlike traditional automation frameworks, Attackbot_v2 is **not** a scanner wrapper.

It is an **LLM-driven agent** that:

* Selects its own tools
* Adapts its strategy based on observations
* Accumulates knowledge throughout execution
* Reasons through an entire exploitation workflow

From subdomain enumeration to vulnerability confirmation, the agent continuously updates its understanding of the target before deciding what to do next.

---

# The Problem It Solves

Bug bounty hunting at scale is fundamentally a **context-management problem**.

Experienced researchers build an internal mental model of a target:

* What assets exist?
* Which assets deserve attention?
* Which techniques apply?
* Which paths are dead ends?

That model must typically be rebuilt from scratch for every engagement.

Traditional automation (Recon frameworks, Nuclei templates, scanners, etc.) excels at **execution**, but not **reasoning**.

They produce enormous quantities of output while leaving humans responsible for:

* Correlating findings
* Prioritizing targets
* Choosing the next technique
* Deciding when enough evidence exists

Attackbot_v2 closes this gap.

Instead of using the LLM as a report generator, it makes the LLM the **orchestrator**.

The model continuously:

1. Reads observations
2. Updates its understanding
3. Revises its plan
4. Chooses the next technique
5. Determines when to stop
6. Produces a vulnerability report

---

# Architecture

```text
┌─────────────────────────────────────────────────────┐
│                  HackerOne API                      │
│         ProgramScraper / DetailScraper              │
└────────────────────┬────────────────────────────────┘
                     │
             Stage 0 (Deterministic)
      Program Ingestion & Normalization
               ScopeManifest JSON
      [Assets • Scope • Bounty • Policy]
                     │
             Stage 1 (LLM Entry Point)
      Classification & Plan Generation
      [asset_type → skill routing]
                     │
        ┌────────────┼────────────┐
        │            │            │
     WILDCARD     URL/DOMAIN    MOBILE
        │            │            │
    Enumeration   Fingerprint   App Recon
        │            │            │
    Validation    Validation   Validation
        │            │            │
    Vulnerability Vulnerability Vulnerability
       Testing       Testing       Testing
        │            │            │
        └────────────┴────────────┘
                     │
               GoalAct Loop
 Thinking → Skill → Action → Observation
                     │
        ┌────────────┴────────────┐
        │                         │
CONFIRMED_FINDING         CONFIRMED_EMPTY
 Markdown Report            Next Target
        │
 Discord Webhook
```

---

# GoalAct Loop

The GoalAct loop is the core execution engine.

Every iteration performs the following cycle:

1. Read the complete scratchpad
2. Rewrite the current plan
3. Select the appropriate skill file
4. Generate the next action
5. Execute the action
6. Observe the result
7. Repeat

The planner always receives the complete execution history:

```
Thinking
↓
Skill
↓
Action
↓
Observation
```

This history serves as the agent's working memory during execution.

A failed technique (**EXECUTION_FAILED**) **never terminates** the loop.

It simply indicates that a particular method failed—not that the target has been exhausted.

---

# Persistent Memory

Persistent memory exists **outside** the GoalAct loop.

Before execution it provides:

* Previously discovered assets
* Historical findings
* Technique success history
* Program-specific knowledge

After execution it stores:

* Confirmed findings
* Newly discovered assets
* Successful exploitation paths
* Technique effectiveness

The GoalAct loop itself remains unchanged.

---

# Scope Enforcement

Attackbot_v2 operates **exclusively** within public HackerOne bug bounty programs.

Scope enforcement is deterministic.

Validation occurs:

* During Stage 0 ingestion
* Before every stage transition
* Before every actionable test

Scope verification combines information from:

* `/structured_scopes`
* `/scope_exclusions`

No asset is tested unless it passes validation.

Additionally:

* Rate limits are respected
* Program rules are enforced
* Out-of-scope assets are never touched

Programs are filtered before the LLM is invoked.

Minimum requirements include:

* Active submission state
* Bounty enabled
* Valid normalized in-scope asset list

---

# Operational Design

## LLM Layer

Primary provider:

* Cerebras

Secondary provider:

* Groq

Current model:

```
Llama 3.3 70B
```

Both operate using free-tier APIs, making **context efficiency** a first-class architectural constraint.

---

## Skill Files

Knowledge is encoded as modular Markdown skill files located under:

```text
skills/recon/
```

Skill routing is determined dynamically through:

```text
(asset_type, stage)
        ↓
  Selected Skill Files
```

Only the required knowledge is loaded for each decision.

Skill files contain:

* Recon methodologies
* Exploitation chains
* Decision heuristics
* Observation → implication mappings
* False-positive avoidance
* Few-shot reasoning traces

These files describe **how to think**, not merely **which tool to execute**.

---

## Program Classes

Program classification determines high-level reasoning.

Examples include:

| Program Type   | Preferred Reasoning                      |
| -------------- | ---------------------------------------- |
| FinTech        | IDOR, business logic                     |
| SaaS           | OAuth, tenant isolation, API enumeration |
| Infrastructure | Network exposure, fingerprinting         |

---

## New Program Detection

New HackerOne programs are detected using a dual mechanism:

* Rolling watermark
* 24-hour full synchronization diff

This provides both efficiency and correctness.

---

# Current State

## Completed

* ✅ Stage 0 implementation
* ✅ ProgramScraper
* ✅ ProgramDetailScraper
* ✅ Scope normalization
* ✅ ScopeManifest generation
* ✅ GoalAct core loop
* ✅ Planner
* ✅ Scratchpad
* ✅ Result state management
* ✅ Fixed major failure modes

  * Prose-before-JSON outputs
  * Cerebras reasoning extraction
  * Observation bloat
  * EXECUTION_FAILED collapse

---

## In Progress

* Skill file architecture
* Asset-type routing layer
* Recon reasoning chains

---

## Next Milestones

* Integrate `scope_exclusions` into `scope_check()`
* Parse HackerOne policy fields into structured `program_constraints`
* Build complete WILDCARD skill chains
* Build complete URL/DOMAIN skill chains

---

# Success Criteria

A successful Attackbot_v2 deployment should be capable of:

1. Detecting a newly published HackerOne program.
2. Normalizing its scope.
3. Planning an autonomous reconnaissance strategy.
4. Executing recon through validation.
5. Confirming vulnerabilities.
6. Producing a reproducible Markdown report.
7. Sending real-time Discord notifications.
8. Persisting knowledge for future executions.

Repeated runs against the same program should benefit from:

* Historical enumeration
* Previous findings
* Technique history
* Accumulated program knowledge

---

# Long-Term Vision

The benchmark for Attackbot_v2 is **not**:

> "Find more bugs than a human in a day."

Instead, success is defined by building an autonomous system that:

* Runs continuously
* Respects program scope
* Produces actionable reports
* Learns across executions
* Scales across hundreds of programs
* Requires no per-target human setup

In short, Attackbot_v2 aims to function as a continuously operating AI bug bounty researcher rather than a collection of automated scanners.
