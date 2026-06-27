# skills/passive_skill.py
import subprocess
from result_state import Result_State

def skill_passive(action: str, results: dict) -> tuple[str, str]:
    """
    Passive recon — zero packets to target.
    action: shell command (e.g. 'subfinder -d example.com -silent')
    Use for: subfinder, amass passive, crt.sh curl, shodan CLI, waybackurls, gau
    """
    try:
        proc = subprocess.run(
            action, shell=True, capture_output=True, text=True, timeout=90
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if proc.returncode != 0 and not stdout:
            return Result_State.EXECUTION_FAILED, f"rc={proc.returncode} stderr={stderr[:300]}"

        if not stdout:
            return Result_State.CONFIRMED_EMPTY, "Command completed with no output."

        # Store findings under 'passive' key
        results.setdefault("passive", []).extend(
            line for line in stdout.splitlines() if line.strip()
        )
        return Result_State.CONFIRMED_FINDING, stdout

    except subprocess.TimeoutExpired:
        return Result_State.EXECUTION_FAILED, "Timeout after 90s. Target may be rate-limiting."
    except Exception as e:
        return Result_State.EXECUTION_FAILED, f"Executor exception: {e}"