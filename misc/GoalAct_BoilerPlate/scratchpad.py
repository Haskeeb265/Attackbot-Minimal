from config import MAX_OBS_CHARS

class Scratchpad:
    def __init__(self):
        self._entries: list[dict] = []

    def append(self, plan_step: str, skill: str, action: str, state: str, observation: str):
        self._entries.append({
            "plan_step": plan_step,
            "skill": skill,
            "action": action,
            "state": state,
            "observation": observation[:MAX_OBS_CHARS],
        })

    def to_text(self) -> str:
        if not self._entries:
            return "(empty — first iteration)"
        parts = []
        for i, e in enumerate(self._entries, 1):
            parts.append(
                f"[Step {i}]\n"
                f"  Plan objective : {e['plan_step']}\n"
                f"  Skill          : {e['skill']}\n"
                f"  Action         : {e['action']}\n"
                f"  Result state   : {e['state']}\n"
                f"  Observation    : {e['observation']}\n"
            )
        return "\n".join(parts)

    def has_failed_steps(self) -> bool:
        return any(e["state"] == "EXECUTION_FAILED" for e in self._entries)

    def last_state(self) -> str | None:
        return self._entries[-1]["state"] if self._entries else None