from cerebras.cloud.sdk import Cerebras
from main_loop import run_goalact

if __name__ == "__main__":
    client = Cerebras(api_key="csk-m6p6m8hxmex2vttfdht5jv8hmwcp3j5dhex4t5k4yw35wje4")
    TARGET_QUERY = (
        "Perform passive subdomain enumeration on qbsco.net. "
        "Then resolve discovered subdomains with dnsx to find live hosts. "
        "Then probe live hosts with httpx to identify active web services. "
        "Report all discovered subdomains and live HTTP services."
    )
    results, scratchpad = run_goalact(TARGET_QUERY, client)

    print("\n\n" + "#" * 60)
    print("FINAL RESULTS")
    print("#" * 60)
    for key, val in results.items():
        if isinstance(val, list):
            print(f"  {key}: {len(val)} items")
            for item in val[:10]:  # show first 10
                print(f"    - {item}")
            if len(val) > 10:
                print(f"    ... and {len(val) - 10} more")
        else:
            print(f"  {key}: {val}")