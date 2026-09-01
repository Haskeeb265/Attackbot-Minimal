import subprocess
from pathlib import Path

from service.recon_pipeline.asset_pipelines.config import TARGET

IMAGE = "projectdiscovery/chaos-client:latest"
CHAOS_KEY = "b6701c79-73ca-4d60-b88e-267d67171c27"

# Output always lands in passive/output, regardless of cwd
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "chaos.txt"


def run(domain: str = TARGET) -> Path:
    """Run chaos passive enum via Docker; write results to passive/output/chaos.txt."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "docker", "run", "--rm",
        IMAGE,
        "-d", domain,
        "-key", CHAOS_KEY,
        "-silent",
    ]

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        subprocess.run(
            cmd,
            stdout=file,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

    return OUTPUT_FILE


if __name__ == "__main__":
    run()
    print(f"Chaos results saved to: {OUTPUT_FILE}")
