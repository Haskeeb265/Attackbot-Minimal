

MODEL = "zai-glm-4.7"
MAX_ITERATIONS = 20
MAX_OBS_CHARS = 800  # hard cap on observation length injected into scratchpad
MAX_TOKENS = 2500    # planner output budget — keep headroom above plan size

# Skill registry
SKILLS = {}