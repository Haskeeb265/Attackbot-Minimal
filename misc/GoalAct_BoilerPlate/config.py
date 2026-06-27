MODEL = "zai-glm-4.7"
MAX_ITERATIONS = 20
MAX_OBS_CHARS = 800  # hard cap on observation length injected into scratchpad
MAX_TOKENS = 2500    # planner output budget — keep headroom above plan size

# Generic mission — target is injected separately at runtime
DEFAULT_MISSION = (
    "Perform external attack-surface reconnaissance on the target scope. "
    "Discover assets (subdomains, hosts, services), determine what is reachable, "
    "and produce a structured summary of findings. "
    "Autonomously decompose this into steps using available skills; "
    "prefer passive enumeration before any active probing."
)

# Skill registry
SKILLS = {}