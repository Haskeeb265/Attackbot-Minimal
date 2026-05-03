# Attackbot – Vulnerability Finder Module
## Architecture & Data Design Blueprint

**Document version:** 1.0  
**Phase:** Planning  
**Date:** 2026-05-03

---

## 1. Introduction

The Attackbot vulnerability finder is an autonomous bug‑bounty agent that continuously hunts for security
weaknesses across program assets. It integrates multiple research components – a dynamic planner
(GoalAct), a multi‑branching explorer (STRUCTUREDAGENT), a skill‑reuse engine (Theory‑Code2), a
graph‑based advisor (Graph Agent), a creative exploit suggester (SymAgent), and an active exploitation
core (VulnBot / Metasploit) – into a cohesive, safe, and extensible system.

This document defines the **architectural style, core design patterns, and data architecture** that allow
these heterogeneous components to collaborate reliably, evolve independently, and operate within
strict safety boundaries. All recommended technologies are free forever (self‑hosted, open‑source
licenses).

---

## 2. Overarching Architectural Style

**Event‑Driven, Agent‑Oriented System with a Central Blackboard Knowledge Hub**

The system is decomposed into a society of **loosely coupled agents** that communicate
asynchronously. Shared, persistent state lives in a **blackboard** – a combination of a graph database
(attack relationships) and a relational store (structured state). Agents react to domain events published
on a lightweight message bus, read from the blackboard, execute their logic, and write results back.

┌─────────────────────────────────────────────────┐
│ Message Bus (NATS) │
│ Events: AssetAdded, ReconCompleted, │
│ BranchCreated, ExploitAttempted … │
└─────┬──────────────┬──────────────┬─────────────┘
│ │ │
┌─────▼──────┐ ┌─────▼──────┐ ┌─────▼──────┐
│ GoalAct │ │Graph Advisor│ │ SymAgent │ …
└─────┬──────┘ └─────┬──────┘ └─────┬──────┘
│ │ │
└──────────────┼──────────────┘
▼
┌───────────────────────────────────┐
│ Blackboard │
│ • Attack Graph (Neo4j) │
│ • Structured State (PostgreSQL) │
│ • Event Log (PostgreSQL) │
└───────────────────────────────────┘


**Why this style fits:**

- **Heterogeneous agents** – GoalAct, Graph Agent, SymAgent, Theory‑Code2, and tool executors
  have vastly different responsibilities. An agent‑oriented design lets each be developed, tested, and
  replaced independently.
- **Dynamic replanning** – GoalAct continuously updates its global plan. An event‑driven model
  allows new information to trigger replanning without blocking other activities.
- **Parallel exploration** – STRUCTUREDAGENT’s multiple attack branches can be realised as
  independent, event‑driven sagas that share the blackboard but not each other’s internal state.
- **Extensibility** – Future components (e.g., an RL‑based attack‑path selector) are simply new
  agents subscribing to existing events.
- **Safety & auditability** – Every decision and action becomes an immutable event, forming a
  natural audit trail for reproduction‑ready reports and continuous learning.

---

## 3. Core Design Patterns

### 3.1 Blackboard Pattern
**Purpose:** Shared knowledge hub where agents collaborate.

All persistent, domain‑relevant information – assets, technology fingerprints, the attack graph,
hypotheses, and findings – resides in the blackboard. Agents read and annotate it without needing
direct knowledge of each other. For example, the Graph Advisor can add a false‑positive risk score to
a graph node, and GoalAct immediately sees the update the next time it queries the blackboard.

### 3.2 Observer (Pub/Sub) Pattern
**Purpose:** Loose coupling between agents via domain events.

When the tool execution layer confirms a vulnerability, it publishes a `BugConfirmed` event to the
message bus. The reporting module, SymAgent (to learn), and the Graph Advisor (to update attack‑
graph probabilities) all react independently, without any hard‑coded dependencies.

### 3.3 Orchestrator + Strategy Pattern
**Purpose:** Decouple high‑level decision‑making from the specific tactics used.

GoalAct acts as the primary orchestrator. It selects from a library of **attack strategies** (encapsulated
as interchangeable Strategy objects) based on the target’s technology stack and the Graph Advisor’s
suggestions. Example strategies: “Web‑API‑Enumeration”, “Cloud‑Service‑Misconfig”, “SQL‑Injection‑
Deep‑Dive”. This makes it straightforward to later introduce an RL agent that learns which strategy
to pick.

### 3.4 Command Pattern
**Purpose:** Encapsulate all tool executions (Nuclei scan, Metasploit module, custom script) as uniform,
self‑contained objects.

Each Command carries the action, parameters, and an optional compensation/cleanup action.
Commands are queued, logged, and subject to a safety validation chain before execution.

### 3.5 Chain of Responsibility Pattern
**Purpose:** Pre‑execution safety and policy enforcement.

Before a Command is executed, it must pass through a configurable chain of handlers:
1. **Scope checker** – Is the target within the program’s defined scope?
2. **Policy verifier** – Does the program’s testing policy allow this action?
3. **Impact assessor** – Should this action be paused for human approval?
4. **Rate limiter** – Are we within allowed request limits?

Any handler can abort the action or elevate it to the human‑in‑the‑loop gate. The chain is assembled
dynamically per program using the scraper’s output.

### 3.6 Adapter Pattern (Tool Abstraction Layer)
**Purpose:** Uniform interface to external tools.

Each external tool (Nuclei, Metasploit, VulnBot, custom scripts) has its own CLI, API, and output
format. An Adapter translates between the internal `Command` representation and the tool‑specific
invocation. When VulnBot is later replaced or upgraded, only its Adapter changes.

### 3.7 State Pattern
**Purpose:** Manage per‑asset testing lifecycle.

An asset transitions through well‑defined states: `Unscanned → ReconInProgress →
AttackSurfaceIdentified → ExploitAttempted → Vulnerable / NotVulnerable`. The State pattern
ensures that only valid actions are available in each state (e.g., no exploit before recon completes)
and allows behaviour to vary per state.

### 3.8 Saga Pattern
**Purpose:** Manage long‑running, multi‑step attack chains.

An attack chain (e.g., SSRF → metadata endpoint → internal service → RCE) consists of multiple steps.
The Saga manages the overall workflow, tracks progress, and defines compensating actions when a
step fails (e.g., removing temporary files uploaded to a target, if permitted). This keeps the system
consistent and minimises unwanted artefacts on target systems.

### 3.9 Repository Pattern
**Purpose:** Clean, domain‑centric data access.

The blackboard is complex – a graph database plus relational tables. Repositories provide a
declarative API (e.g., `AssetRepository.findByTechnology("AWS")`,
`AttackGraphRepository.getPendingBranches()`) so agents never write raw queries. This isolates
storage evolution from agent logic.

### 3.10 Dependency Injection (Inversion of Control)
**Purpose:** Assemble the agent society and its dependencies in one place.

All agents, strategies, adapters, and safety handlers are wired together in a composition root.
Swapping a real Graph Advisor for a stub during integration tests becomes a one‑line change.
No agent instantiates its collaborators directly.

---

## 4. Data Architecture

The data layer is divided into distinct **domains**, each with its own access patterns, consistency
requirements, and underlying technology. The entire stack is free forever and self‑hosted.

| Domain | Description | Technology | License |
|--------|-------------|------------|---------|
| **Event Bus** | Real‑time, persistent pub/sub for inter‑agent communication | **NATS** (with JetStream) | Apache 2.0 |
| **Blackboard – Attack Graph** | Assets, vulnerabilities, techniques, relationships | **Neo4j Community Edition** | AGPL‑free Community license |
| **Blackboard – Structured State** | Asset lifecycle, test history, human approval queues | **PostgreSQL** | PostgreSQL license |
| **Event Log / Source of Truth** | Immutable record of all actions and decisions | **PostgreSQL** (append‑only `events` table) | PostgreSQL license |
| **RAG Vector Store** | Embeddings of past findings, CVE/CWE descriptions, manuals | **pgvector** (extension in PostgreSQL) | PostgreSQL + pgvector license |
| **Agent Short‑Term Memory** | Ephemeral plan trees, intermediate reasoning contexts | **Valkey** (or Redis OSS) | BSD (Valkey) |
| **Tool Sandbox / Files** | Temporary screenshots, logs, payloads | **Local filesystem** + TTL cleanup | – |

### 4.1 Why This Stack Was Chosen

- **PostgreSQL + pgvector** acts as the transactional backbone. It stores structured state, the
  immutable event log, and the vector index used for RAG – all within a single, battle‑tested
  database. pgvector eliminates the need for a separate vector service.
- **Neo4j Community** is purpose‑built for the highly connected attack graph. Cypher queries let the
  Graph Advisor, SymAgent, and GoalAct traverse attack paths, find analogies, and compute
  probabilities efficiently. The Community Edition is free, single‑node, and unlimited data – perfect
  for a self‑hosted bug bounty tool.
- **NATS** provides ultra‑lightweight, high‑performance messaging. JetStream adds persistence and
  replay, enabling event‑sourcing and letting agents (especially the Graph Agent) learn from history.
- **Valkey** (the open‑source Redis fork) serves as a low‑latency key‑value store for agent sessions,
  temporary plan trees, and caches with automatic TTL.
- **Local filesystem** avoids additional infrastructure for ephemeral tool outputs; a simple cron job
  cleans directories older than a configurable window.

All components can be run on a single development machine or a single production server using
Docker Compose.

### 4.2 Data Flow Summary

1. Agents publish events to **NATS** (e.g., `asset.recon.completed`).
2. A lightweight **persister service** subscribes to all domain events and writes them into the
   PostgreSQL `events` table, then updates the structured state and triggers corresponding Neo4j
   graph mutations.
3. Agents needing real‑time state hold their ephemeral working memory in **Valkey**, refreshing from
   the blackboard when invalidated by events.
4. For RAG, a dedicated query service embeds the agent’s context, queries **pgvector**, and returns
   the most relevant past findings and technique descriptions to be injected into the agent’s prompt.
5. The tool execution sandbox writes artefacts to a designated filesystem path and records metadata
   in PostgreSQL.

### 4.3 Alignment with Research Components

| Research Component | How the Data Architecture Supports It |
|--------------------|----------------------------------------|
| **GoalAct** (dynamic planner) | Reads asset state from PostgreSQL, current attack graph from Neo4j, and retrieves RAG context from pgvector. Stores active plan tree in Valkey. Publishes new tasks as Commands on the bus. |
| **STRUCTUREDAGENT** (branching) | Each branch is a Valkey key with TTL, isolated yet observable. Branch events are tagged and can be replayed. |
| **Theory‑Code2** (skill reuse) | Skills are stored as parametrised Command sequences in PostgreSQL. When triggered, they are re‑executed through the tool adapters. |
| **Graph Agent** (advisor) | Directly queries and annotates the Neo4j attack graph. Can replay the event log from PostgreSQL to incrementally learn program‑specific patterns. |
| **SymAgent** (creative suggestions) | Traverses Neo4j to find analogous attack patterns and enriches its prompt with embeddings from pgvector. |
| **VulnBot / Metasploit** | Wrapped by a Command Adapter; every action is validated by the Chain of Responsibility and recorded in the event log. |
| **RL training (future)** | The event log in PostgreSQL and the attack graph in Neo4j can be used to build training environments and reward signals. |

---

## 5. Deployment View (Conceptual)
┌──────────────────────────────────────────────┐
│ Docker Host │
│ │
│ ┌───────────┐ ┌────────┐ ┌─────────────┐ │
│ │ NATS │ │ Valkey │ │ PostgreSQL │ │
│ │ (bus) │ │(cache) │ │ + pgvector │ │
│ └───────────┘ └────────┘ └─────────────┘ │
│ │
│ ┌───────────┐ ┌──────────────────────────┐ │
│ │ Neo4j CE │ │ Agent Containers │ │
│ │ (graph) │ │ (GoalAct, Graph Advisor, │ │
│ └───────────┘ │ SymAgent, Tool Exec …) │ │
│ └──────────────────────────┘ │
└──────────────────────────────────────────────┘


Agents are deployed as separate processes or containers, all connected to the same message bus and
databases. A minimal starting stack requires only PostgreSQL and Valkey; Neo4j and NATS can be
added incrementally.

---

## 6. Summary & Next Steps

This blueprint provides a **scalable, modular, and safety‑conscious foundation** for Attackbot’s
vulnerability finder. The combination of an event‑driven multi‑agent style, a blackboard knowledge
hub, and a suite of proven design patterns ensures that the system can incorporate your extensive
R&D without becoming a tangled monolith. The free‑forever technology stack keeps operational costs
at zero while still offering production‑grade reliability.

**Immediate action items (from planning to first prototype):**
1. Set up a minimal Docker Compose with **PostgreSQL (+ pgvector)** and **Valkey**.
2. Implement a basic event bus abstraction using Valkey Pub/Sub.
3. Build the Command and Chain of Responsibility framework with a single dummy tool adapter.
4. Wire a trivial orchestrator that reacts to `AssetAdded` events.
5. Design the PostgreSQL schema for assets, testing policies, and test history.
6. Gradually introduce GoalAct and Graph Agent, replacing the dummy orchestrator.

Once this spine is in place, the full weight of the research papers can be integrated without
architectural friction.