# skills/active_skill.py
import subprocess
from result_state import Result_State

def skill_active(action: str, results: dict) -> tuple[str, str]:
    """
    Active probing — sends packets to target. Use only after passive is complete.
    action: shell command (e.g. 'dnsx -l subs.txt -a -resp -silent')
    Use for: dnsx, httpx, nmap/naabu, shuffledns brute-force, nuclei
    """
    try:
        proc = subprocess.run(
            action, shell=True, capture_output=True, text=True, timeout=180
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if proc.returncode != 0 and not stdout:
            return Result_State.EXECUTION_FAILED, f"rc={proc.returncode} stderr={stderr[:300]}"

        if not stdout:
            return Result_State.CONFIRMED_EMPTY, "Command completed with no findings."

        results.setdefault("active", []).extend(
            line for line in stdout.splitlines() if line.strip()
        )
        return Result_State.CONFIRMED_FINDING, stdout

    except subprocess.TimeoutExpired:
        return Result_State.EXECUTION_FAILED, "Timeout after 180s."
    except Exception as e:
        return Result_State.EXECUTION_FAILED, f"Executor exception: {e}"