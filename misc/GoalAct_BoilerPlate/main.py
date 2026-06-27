import argparse
import os

from cerebras.cloud.sdk import Cerebras
from main_loop import run_goalact

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GoalAct recon agent (stage 0)")
    parser.add_argument(
        "--target", "-t",
        required=True,
        help="Target domain or scope (e.g. example.com)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("CEREBRAS_API_KEY")
    client = Cerebras(api_key=api_key) if api_key else Cerebras()

    results, scratchpad = run_goalact(target=args.target, client=client)

    print("\n\n" + "#" * 60)
    print("FINAL RESULTS")
    print("#" * 60)
    for key, val in results.items():
        if isinstance(val, list):
            print(f"  {key}: {len(val)} items")
            for item in val[:10]:
                print(f"    - {item}")
            if len(val) > 10:
                print(f"    ... and {len(val) - 10} more")
        else:
            print(f"  {key}: {val}")
