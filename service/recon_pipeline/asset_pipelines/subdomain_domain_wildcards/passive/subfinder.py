import subprocess
from pathlib import Path

from service.recon_pipeline.asset_pipelines.config import TARGET

IMAGE = "projectdiscovery/subfinder:v2.14.0"

# Output always lands in passive/output, regardless of cwd
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "subfinder.txt"


def run(domain: str = TARGET) -> Path:
    """Run subfinder passively via Docker; write results to passive/output/subfinder.txt."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "docker", "run", "--rm",
        IMAGE,
        "-d", domain,
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
    print(f"Subfinder results saved to: {OUTPUT_FILE}")