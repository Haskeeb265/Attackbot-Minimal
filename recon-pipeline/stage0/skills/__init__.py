from .passive_skill import skill_passive
from .active_skill import skill_active
from config import SKILLS

# Register skills
SKILLS.update({
    "Passive": {
        "description": (
            "Run passive reconnaissance tools that send ZERO requests to the target. "
            "Safe to use at any time. "
            "Use for: subfinder, amass passive mode, crt.sh API queries, "
            "SecurityTrails lookups, shodan CLI queries, waybackurls, gau, "
            "certificate transparency log queries."
        ),
        "executor": skill_passive,
    },
    "Active": {
        "description": (
            "Run active tools that send probes directly to the target. "
            "Use ONLY after Passive enumeration is complete. "
            "Use for: dnsx DNS resolution, httpx HTTP probing, nmap/naabu port scanning, "
            "shuffledns brute-force, nuclei template scanning, subzy takeover checks."
        ),
        "executor": skill_active,
    },
    "Code": {
        "description": (
            "Execute Python code for data processing: deduplication, filtering, "
            "sorting, merging lists, pattern extraction, writing files. "
            "The 'results' dict contains all data collected so far. "
            "Set variable 'output' to expose a summary to the scratchpad."
        ),
        "executor": lambda action, results: (None, None),  # Placeholder, implement in code_skill.py if needed
    },
    "Finish": {
        "description": (
            "Task is complete. All goals are in CONFIRMED state (no EXECUTION_FAILED). "
            "Write a final summary of all findings. This stops the agent."
        ),
        "executor": lambda action, results: (None, None),  # Placeholder, implement in finish_skill.py if needed
    },
})