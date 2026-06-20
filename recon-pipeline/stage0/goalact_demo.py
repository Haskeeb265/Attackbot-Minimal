#!/usr/bin/env python3
"""
GoalAct Demo — Attackbot_v2
Implements: Global Planning + Hierarchical Execution (Searching / Coding / Finish)

Usage:
    export GROQ_API_KEY=gsk_...
    python goalact_demo.py --target example.com

What this demonstrates:
  1. Planner calls Groq on every iteration to generate/update the global plan
  2. Each step is dispatched to a skill executor (Searching or Coding)
  3. Observations are injected back into the next Planner call (the scratchpad)
  4. The plan rewrites itself based on what it finds
  5. Loop terminates when the Planner emits a Finish action
"""

import os
import re
import json
import socket
import argparse
import requests
import builtins
from datetime import datetime

# ─────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_ITERS    = 20

# ─────────────────────────────────────────────────────────
# PLANNER — calls Groq to decide the next step
# ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an offensive security recon planner for HackerOne bug bounty programs.
You solve tasks using the Thinking → Acting → Observing loop.

SKILLS:
1. Searching  — Single HTTP GET to a public passive source (no active probing).
                Details must include: {"url": "...", "label": "short name"}

2. Coding     — Python block that processes already-collected data. No network calls allowed here.
                Details must include: {"code": "python string", "label": "short name"}
                Pre-loaded globals: results (dict of prior obs keyed by label), json, re, socket, output (list).
                Append findings to `output`. Do NOT use import statements. Do NOT call requests or urllib.

3. Finish     — Summarise and terminate.
                Details must include: {"summary": "what was found"}

RULES:
- Passive ONLY. Only crt.sh and similar public read-only APIs for Searching.
- scope_check in Coding: only keep names ending with the target domain.
- Plan must end with a Finish step.

OUTPUT: Respond ONLY with valid JSON (parseable by json.loads). No markdown fences. No prose.
Schema: [{"Thinking": "...", "Skill": "Searching|Coding|Finish", "Action": "...", "Details": {...}}]
Output exactly ONE step — the next action to take."""


def call_groq(target: str, scope: str, tools: str, scratchpad: str) -> dict:
    """Ask Groq what to do next. Returns a parsed plan step dict."""
    user_msg = (
        f"TARGET: {target}\n"
        f"SCOPE: {scope}\n"
        f"PASSIVE SOURCES:\n{tools}\n\n"
        f"TRAJECTORY SO FAR:\n{scratchpad or '(none — first step)'}\n\n"
        "Output exactly ONE next step as a JSON array with one element."
    )

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Run: export GROQ_API_KEY=gsk_...")

    resp = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "temperature": 0,
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if model ignores the instruction
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    raw = raw.rstrip("`").strip()

    parsed = json.loads(raw)
    return parsed[0] if isinstance(parsed, list) else parsed


# ─────────────────────────────────────────────────────────
# SKILL EXECUTORS
# ─────────────────────────────────────────────────────────

def run_searching(details: dict) -> str:
    """Searching skill: single HTTP GET to a public passive source."""
    url   = details.get("url", "")
    label = details.get("label", url)
    print(f"    → GET {url}")
    try:
        r = requests.get(
            url, timeout=15,
            headers={"User-Agent": "AttackbotV2-GoalActDemo/1.0"},
        )
        r.raise_for_status()
        try:
            return json.dumps(r.json(), indent=2)[:4000]
        except Exception:
            return r.text[:4000]
    except Exception as e:
        return f"SEARCHING ERROR: {e}"


def run_coding(details: dict, results: dict) -> str:
    """
    Coding skill: exec a Python block with pre-loaded modules and prior results.
    The agent appends to `output` to return data.
    No import statements allowed — json, re, socket are provided as globals.
    """
    code  = details.get("code", "")
    label = details.get("label", "code")
    print(f"    → exec: {label}")

    _ALLOWED = (
        "len", "range", "enumerate", "sorted", "set", "list", "dict", "str",
        "int", "float", "bool", "isinstance", "type", "zip", "map", "filter",
        "min", "max", "sum", "any", "all", "print", "repr", "round",
    )
    safe_builtins = {k: getattr(builtins, k) for k in _ALLOWED}

    sandbox = {
        "__builtins__": safe_builtins,
        "json":    json,
        "re":      re,
        "socket":  socket,
        "results": results,   # all prior observations keyed by their label
        "output":  [],        # agent appends findings here
    }

    try:
        exec(compile(code, "<goalact_coding>", "exec"), sandbox)
        return json.dumps(sandbox["output"], indent=2)
    except Exception as e:
        return f"CODING ERROR: {e}"


def dispatch_skill(step: dict, results: dict) -> str:
    """Route to the correct executor and store the observation in results."""
    skill   = step.get("Skill", "")
    details = step.get("Details", {})

    if skill == "Searching":
        obs = run_searching(details)
        results[details.get("label", f"search_{len(results)}")] = obs

    elif skill == "Coding":
        obs = run_coding(details, results)
        results[details.get("label", f"code_{len(results)}")] = obs

    elif skill == "Finish":
        obs = details.get("summary", "Done.")

    else:
        obs = f"UNKNOWN SKILL: {skill}"

    return obs


# ─────────────────────────────────────────────────────────
# SCRATCHPAD — S_t in the paper's notation
# Injects the full (Plan, Action, Observation) history into each Planner call.
# This is what gives the model global goal awareness across iterations.
# ─────────────────────────────────────────────────────────

def build_scratchpad(history: list) -> str:
    lines = []
    for i, h in enumerate(history, 1):
        lines.append(f"Step {i} | Skill: {h['Skill']}")
        lines.append(f"  Thinking:    {h['Thinking']}")
        lines.append(f"  Action:      {h['Action']}")
        obs_preview = h["observation"][:600].replace("\n", " ")
        lines.append(f"  Observation: {obs_preview}...")
        lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────
# GOALACT MAIN LOOP
# G_t = π(Query | Tools | S_t)  ← Eq. 2 from the paper
# ─────────────────────────────────────────────────────────

PASSIVE_SOURCES = (
    "- crt.sh subdomain query : https://crt.sh/?q=%.{domain}&output=json\n"
    "- crt.sh exact domain    : https://crt.sh/?q={domain}&output=json\n"
    "  (replace {{domain}} with actual domain; returns JSON array of cert records)"
)


def run_goalact(target: str):
    scope   = f"subdomains of {target} and {target} itself"
    tools   = PASSIVE_SOURCES.format(domain=target)
    history = []   # S_t — full trajectory
    results = {}   # accumulated observations keyed by label

    print(f"\n{'='*62}")
    print(f"  GoalAct Demo  |  target={target}  |  model={GROQ_MODEL}")
    print(f"{'='*62}")

    for iteration in range(1, MAX_ITERS + 1):
        print(f"\n[STEP {iteration}] {'─'*48}")

        # ── PLAN ──────────────────────────────────────────────
        # Eq. 2: G_t = π(Q | T | S_t)
        scratchpad = build_scratchpad(history)
        step = call_groq(target, scope, tools, scratchpad)

        print(f"  Thinking : {step.get('Thinking', '')}")
        print(f"  Skill    : {step.get('Skill', '?')}")
        print(f"  Action   : {step.get('Action', '')}")
        print()

        # ── EXECUTE ────────────────────────────────────────────
        observation = dispatch_skill(step, results)

        # ── OBSERVE ────────────────────────────────────────────
        # Append (P_i, A_i, O_i) triple to S_t
        step["observation"] = observation
        history.append(step)

        print(f"  Observation ({len(observation)} chars):")
        for ln in observation.split("\n")[:7]:
            print(f"    {ln}")
        if observation.count("\n") > 7:
            print("    ...")

        # ── TERMINATE ──────────────────────────────────────────
        if step.get("Skill") == "Finish":
            print(f"\n{'='*62}")
            print(f"  COMPLETE — {iteration} steps")
            print(f"  Observation buckets: {len(results)}")
            print(f"\n  SUMMARY:\n  {observation}")
            print(f"{'='*62}\n")
            break

    else:
        print(f"\n[!] Max iterations ({MAX_ITERS}) reached without Finish.")

    # ── SAVE FULL TRAJECTORY ───────────────────────────────────
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"goalact_{target}_{ts}.json"
    with open(path, "w") as f:
        json.dump({"target": target, "history": history, "results": results}, f, indent=2)
    print(f"Trajectory → {path}")

    return history, results


# ─────────────────────────────────────────────────────────
# ENTRY
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="GoalAct Demo — Passive Subdomain Recon")
    ap.add_argument("--target", required=True, help="Target domain, e.g. tesla.com")
    args = ap.parse_args()
    run_goalact(args.target)