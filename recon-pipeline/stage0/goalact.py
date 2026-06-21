#!/usr/bin/env python3
"""
GoalAct Demo — Autonomous Security Tool Scout
==============================================
Showcases GoalAct's adaptive replanning: the agent breaks a complex research
task into steps, searches GitHub live, hits noise (lists/collections masquerading
as tools), refines its approach, synthesizes findings, and produces a ranked report.

Demonstrates:
  1. Global plan that rewrites itself each iteration based on observations
  2. Skill hierarchy: Searching (live data) → Coding (synthesis) → Finish (report)
  3. Natural trial-and-error when initial searches return noise
  4. Scratchpad (S_t) giving the model full memory across all steps

Usage:
    export GROQ_API_KEY=gsk_...
    export GITHUB_TOKEN=ghp_...   (optional — raises API rate limit from 10 to 30 req/min)
    python goalact_demo.py
"""

import os
import re
import json
import time
import builtins
import requests
from datetime import datetime

# ─────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
GROQ_MODEL     = "llama-3.3-70b-versatile"
GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"
MAX_ITERS      = 14

# ─────────────────────────────────────────────────────────
# TASK  (hardcoded for this showcase)
# ─────────────────────────────────────────────────────────
TASK = """
You are a security tool scout. Identify the top 5 open-source tools every
bug bounty hunter should know. Search GitHub across these four categories:

  1. Recon / subdomain enumeration
  2. Web vulnerability scanning / fuzzing
  3. Network / port scanning
  4. OSINT / passive intelligence

For each tool produce: tool name, category, GitHub stars, language, last
updated date, and one sentence on why it beats alternatives.

IMPORTANT: Skip 'awesome-list' collections and CTF write-up repos — only
real, reusable, runnable tools count. If a search returns a list repo
(repo name starts with 'Awesome' or description says 'collection of'),
refine your query and search again.
"""

# ─────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are an autonomous security ecosystem analyst operating
via the Thinking → Acting → Observing loop.

YOUR TASK:
{TASK}

SKILLS:
1. Searching  — HTTP GET to the GitHub Search API. Returns JSON with repository data.
                Details: {{"url": "...", "label": "short descriptive name"}}
                GitHub search URL format:
                  https://api.github.com/search/repositories?q={{QUERY}}&sort=stars&per_page=5
                Example queries: topic:recon+security, subdomain+enumeration+tool,
                  web+fuzzer+bugbounty, port+scanner+golang, osint+passive+recon
                Key fields in response: items[].full_name, .stargazers_count,
                  .language, .description, .updated_at

2. Coding     — Python to parse and synthesize data already collected.
                Details: {{"code": "raw Python — NO import statements, NO network calls", "label": "short name"}}
                Pre-loaded: results (dict keyed by label from Searching steps), json, re, output (list).
                Append your structured findings to `output`.
                To access prior observations: data = json.loads(results["your_label"])

3. Finish     — Write the final ranked report and terminate.
                Details: {{"summary": "complete ranked report"}}

STRATEGY:
- Run 3–4 Searching steps across different categories before synthesising.
- If a search returns lists/collections (not actual tools), note it in Thinking and refine the query.
- Use one Coding step to deduplicate and rank everything collected.
- Finish with a clean top-5 ranked report including all required fields.
- Do NOT re-search a category you already have good results for.

OUTPUT FORMAT: Valid JSON only — parseable by json.loads(). No markdown fences. No prose before or after.
Schema: [{{"Thinking": "...", "Skill": "Searching|Coding|Finish", "Action": "...", "Details": {{...}}}}]
Output exactly ONE step."""

# ─────────────────────────────────────────────────────────
# PLANNER — calls Groq to decide next step
# ─────────────────────────────────────────────────────────
def call_groq(scratchpad: str) -> dict:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set. Run: export GROQ_API_KEY=gsk_...")

    user_msg = (
        f"TRAJECTORY SO FAR:\n{scratchpad or '(none — this is the first step)'}\n\n"
        "Based on the trajectory, output the single best next step as a JSON array with one element."
    )

    resp = requests.post(
        GROQ_API_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": GROQ_MODEL,
            "temperature": 0,
            "max_tokens": 1200,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if the model ignores the instruction
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:])
    raw = raw.rstrip("`").strip()

    parsed = json.loads(raw)
    return parsed[0] if isinstance(parsed, list) else parsed

# ─────────────────────────────────────────────────────────
# SKILL: Searching — HTTP GET to GitHub API
# ─────────────────────────────────────────────────────────
def run_searching(details: dict) -> str:
    url   = details.get("url", "")
    print(f"    → GET {url}")

    headers = {"User-Agent": "GoalActDemo/1.0"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    try:
        r = requests.get(url, timeout=30, headers=headers)
        r.raise_for_status()

        data = r.json()

        # Rate limit signal
        if isinstance(data, dict) and "message" in data and "rate limit" in data["message"].lower():
            return f"RATE_LIMIT: {data['message']} — wait 60s or set GITHUB_TOKEN env var"

        # Trim items list to avoid huge payloads bloating the scratchpad
        if isinstance(data, dict) and "items" in data:
            trimmed = []
            for item in data["items"][:5]:
                trimmed.append({
                    "name":        item.get("name"),
                    "full_name":   item.get("full_name"),
                    "description": item.get("description", ""),
                    "stars":       item.get("stargazers_count"),
                    "language":    item.get("language"),
                    "updated_at":  item.get("updated_at", "")[:10],
                    "topics":      item.get("topics", []),
                    "url":         item.get("html_url"),
                })
            data = {"total_count": data.get("total_count", 0), "items": trimmed}

        return json.dumps(data, indent=2)

    except Exception as e:
        return f"SEARCHING ERROR: {e}"

# ─────────────────────────────────────────────────────────
# SKILL: Coding — sandboxed Python exec
# ─────────────────────────────────────────────────────────
def run_coding(details: dict, results: dict) -> str:
    code  = details.get("code", "")
    label = details.get("label", "code")
    print(f"    → exec: {label}")

    # Strip markdown fences — models frequently add them despite instructions
    code = code.strip()
    if code.startswith("```"):
        code = "\n".join(code.split("\n")[1:])
    code = code.rstrip("`").strip()

    _ALLOWED = (
        "len", "range", "enumerate", "sorted", "set", "list", "dict", "str",
        "int", "float", "bool", "isinstance", "type", "zip", "map", "filter",
        "min", "max", "sum", "any", "all", "print", "repr", "round",
    )
    sandbox = {
        "__builtins__": {k: getattr(builtins, k) for k in _ALLOWED},
        "json":    json,
        "re":      re,
        "results": results,
        "output":  [],
    }

    try:
        exec(compile(code, "<goalact_coding>", "exec"), sandbox)
        return json.dumps(sandbox["output"], indent=2)
    except Exception as e:
        return f"CODING ERROR: {type(e).__name__}: {e}"

# ─────────────────────────────────────────────────────────
# SKILL DISPATCHER
# ─────────────────────────────────────────────────────────
def dispatch(step: dict, results: dict) -> str:
    skill   = step.get("Skill", "")
    details = step.get("Details", {})

    if skill == "Searching":
        obs = run_searching(details)
        results[details.get("label", f"search_{len(results)}")] = obs
        return obs

    elif skill == "Coding":
        obs = run_coding(details, results)
        results[details.get("label", f"code_{len(results)}")] = obs
        return obs

    elif skill == "Finish":
        return details.get("summary", "Done.")

    return f"UNKNOWN SKILL: {skill}"

# ─────────────────────────────────────────────────────────
# SCRATCHPAD — S_t from Equation 2 of the GoalAct paper
# Every (Thinking, Skill, Action, Observation) triple is injected
# into the next Planner call. This is what prevents looping.
# ─────────────────────────────────────────────────────────
def build_scratchpad(history: list) -> str:
    lines = []
    for i, h in enumerate(history, 1):
        lines.append(f"Step {i} | Skill: {h['Skill']}")
        lines.append(f"  Thinking:    {h['Thinking']}")
        lines.append(f"  Action:      {h['Action']}")
        # Truncate long observations so the context doesn't explode
        obs = h["observation"][:800].replace("\n", " ")
        lines.append(f"  Observation: {obs}...")
        lines.append("")
    return "\n".join(lines)

# ─────────────────────────────────────────────────────────
# MAIN GOALACT LOOP
# G_t = π(Task | Tools | S_t)   ← Eq. 2 from the paper
# ─────────────────────────────────────────────────────────
def run():
    history = []
    results = {}

    print(f"\n{'='*64}")
    print(f"  GoalAct  |  Security Tool Scout  |  {GROQ_MODEL}")
    print(f"{'='*64}")
    print(f"  Task: {TASK.strip()[:120]}...")
    print(f"{'='*64}")

    for iteration in range(1, MAX_ITERS + 1):
        print(f"\n[STEP {iteration}] {'─'*50}")

        # ── PLAN (Eq. 2) ──────────────────────────────────────
        scratchpad = build_scratchpad(history)
        step = call_groq(scratchpad)

        print(f"  Thinking : {step.get('Thinking', '')}")
        print(f"  Skill    : {step.get('Skill', '?')}")
        print(f"  Action   : {step.get('Action', '')}")
        print()

        # ── EXECUTE ───────────────────────────────────────────
        observation = dispatch(step, results)

        # ── OBSERVE (append P_i, A_i, O_i to S_t) ────────────
        step["observation"] = observation
        history.append(step)

        print(f"  Observation ({len(observation)} chars):")
        for ln in observation.split("\n")[:8]:
            print(f"    {ln}")
        if observation.count("\n") > 8:
            print("    ...")

        # ── TERMINATE ─────────────────────────────────────────
        if step.get("Skill") == "Finish":
            print(f"\n{'='*64}")
            print(f"  COMPLETE — {iteration} steps | {len(results)} data buckets")
            print(f"\n{'─'*64}")
            print(observation)
            print(f"{'='*64}\n")
            break

    else:
        print(f"\n[!] Hit MAX_ITERS={MAX_ITERS} without Finish.")

    # ── SAVE ──────────────────────────────────────────────────
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"goalact_run_{ts}.json"
    with open(path, "w") as f:
        json.dump({"task": TASK, "history": history, "results": results}, f, indent=2)
    print(f"Trajectory saved → {path}")

if __name__ == "__main__":
    run()