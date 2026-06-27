import json
import re
from cerebras.cloud.sdk import Cerebras
import skills  # noqa: F401 — registers SKILLS executors

from config import MODEL, MAX_ITERATIONS, MAX_TOKENS, SKILLS, DEFAULT_MISSION
from scratchpad import Scratchpad
from result_state import Result_State

# Planner prompt templates
_PLANNER_SYSTEM = """\
You are the Planner for an autonomous security reconnaissance agent (Attackbot).
Your job: given a mission and target scope, autonomously decompose the work into
a global plan and decide the very next action. You choose tools, ordering, and
commands — the mission does not prescribe step-by-step instructions.

## Skills available to you
{skills_block}

## Critical rules
1. Output ONLY valid JSON. No prose, no markdown fences, no explanation outside JSON.
2. The last step in global_plan MUST always have skill = "Finish".
3. next_step MUST be the first incomplete step (not yet showing CONFIRMED in history).
4. If the scratchpad shows EXECUTION_FAILED for a step, do NOT advance past it.
   Instead: retry with a corrected command, or use a different skill as fallback.
5. Never select Finish while any step shows EXECUTION_FAILED in the scratchpad.
6. next_step.skill MUST be one of: {skill_names}
7. next_step.action must be a concrete, directly executable instruction or command.

## Output schema (respond with ONLY this JSON object)
{{
  "thinking": "<1-3 sentences: what has been done, what remains, why next_step was chosen>",
  "global_plan": [
    {{"step": 1, "skill": "<skill>", "objective": "<what this step achieves>"}},
    {{"step": 2, "skill": "<skill>", "objective": "<what this step achieves>"}},
    ...
    {{"step": N, "skill": "Finish", "objective": "Summarise all findings"}}
  ],
  "next_step": {{
    "step": <integer matching a step in global_plan>,
    "skill": "<skill_name>",
    "objective": "<what this step achieves>",
    "action": "<exact command or Python code to execute>"
  }}
}}
"""

_PLANNER_USER = """\
## Mission
{mission}

## Target scope
{target}

## Execution history (scratchpad St)
{scratchpad}

Produce the updated global plan and next_step now.
"""

def _build_skills_block() -> str:
    lines = []
    for name, info in SKILLS.items():
        lines.append(f"- {name}: {info['description']}")
    return "\n".join(lines)

def call_planner(
    client: Cerebras, target: str, mission: str, scratchpad: Scratchpad
) -> dict:
    system = _PLANNER_SYSTEM.format(
        skills_block=_build_skills_block(),
        skill_names=", ".join(SKILLS.keys()),
    )
    user = _PLANNER_USER.format(
        mission=mission,
        target=target,
        scratchpad=scratchpad.to_text(),
    )

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    # Defensive extraction
    raw = ""
    msg = response.choices[0].message
    if hasattr(msg, "content") and msg.content:
        raw = msg.content.strip()
    elif hasattr(msg, "reasoning") and msg.reasoning:
        raw = msg.reasoning.strip()

    if not raw:
        raise ValueError("Planner returned empty response.")

    return _parse_planner_output(raw)

def _parse_planner_output(raw: str) -> dict:
    raw = re.sub(r"^```(?\:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object in planner output:\n{raw[:400]}")

    try:
        return json.loads(raw[start:end])
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse failed: {e}\nRaw snippet: {raw[start:start+400]}")

def run_goalact(
    target: str,
    client: Cerebras | None = None,
    mission: str | None = None,
) -> tuple[dict, Scratchpad]:
    if client is None:
        client = Cerebras()
    if mission is None:
        mission = DEFAULT_MISSION

    scratchpad = Scratchpad()
    results: dict = {"target": target}

    print(f"\n{'#' * 60}")
    print(f"[GoalAct] Target: {target}")
    print(f"[GoalAct] Mission: {mission}")
    print(f"{'#' * 60}\n")

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n{'=' * 55}")
        print(f" Iteration {iteration}/{MAX_ITERATIONS}")
        print(f"{'=' * 55}")

        # Planner: rewrite global plan, select next step
        try:
            plan_output = call_planner(client, target, mission, scratchpad)
        except Exception as e:
            print(f"[PLANNER ERROR] {e}")
            break

        thinking = plan_output.get("thinking", "")
        global_plan = plan_output.get("global_plan", [])
        next_step = plan_output.get("next_step", {})

        print(f"[Thinking]    {thinking}")
        print(f"[Plan length] {len(global_plan)} steps")

        skill_name = next_step.get("skill", "")
        action = next_step.get("action", "")
        objective = next_step.get("objective", "")
        step_num = next_step.get("step", "?")

        print(f"[Next]  Step {step_num} | Skill: {skill_name}")
        print(f"        Objective: {objective}")
        print(f"        Action:    {action[:120]}")

        # Terminal condition
        if skill_name == "Finish":
            print("\n[GoalAct] Finish skill reached.")
            skill_exec = SKILLS["Finish"]["executor"]
            state, obs = skill_exec(action, results)
            scratchpad.append(objective, skill_name, action, state, obs)
            break

        # Validate skill name
        if skill_name not in SKILLS:
            obs = (
                f"Unknown skill '{skill_name}'. "
                f"Valid skills: {list(SKILLS.keys())}. "
                "Planner must correct this."
            )
            print(f"[INVALID SKILL] {obs}")
            scratchpad.append(objective, skill_name, action, Result_State.EXECUTION_FAILED, obs)
            continue

        # Execute skill
        print(f"\n[Executing] {skill_name} ...")
        executor = SKILLS[skill_name]["executor"]
        state, obs = executor(action, results)

        print(f"[State]       {state}")
        print(f"[Observation] {obs[:250]}")

        # Append to scratchpad
        scratchpad.append(objective, skill_name, action, state, obs)

        # EXECUTION_FAILED is not a stopping condition
        if state == Result_State.EXECUTION_FAILED:
            print(
                "[WARNING] Step failed. "
                "Planner will see EXECUTION_FAILED and must retry or fallback."
            )

    else:
        print(f"\n[GoalAct] Max iterations ({MAX_ITERATIONS}) reached without Finish.")

    return results, scratchpad