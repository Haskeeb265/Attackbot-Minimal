import subprocess
from pathlib import Path

from service.recon_pipeline.asset_pipelines.config import TARGET
import shared.colorlog as colorlog

IMAGE = "edu4rdshl/findomain:latest"

# Output always lands in passive/output, regardless of cwd
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "findomain.txt"
LOG_FILE = OUTPUT_DIR / "findomain.log"


def run(domain: str = TARGET) -> Path:
    """Run findomain passive enum via Docker; write results to passive/output/findomain.txt.

    Passive by default (no -w/--wordlist flag). Queries 54 CT + API sources
    in parallel. Typical runtime ~20s for most domains.

    Flags:
        -t <domain>  Target domain
        -q           Quiet mode (results only, no banner)
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "docker", "run", "--rm",
        IMAGE,
        "-t", domain,
        "-q",
    ]

    colorlog.log.info(f"Running findomain passive enum (Docker) for {domain}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        colorlog.log.failed(f"findomain Docker run failed for {domain}: {e.stderr}")
        raise

    OUTPUT_FILE.write_text(result.stdout, encoding="utf-8")
    LOG_FILE.write_text(result.stderr, encoding="utf-8")
    colorlog.log.info(f"findomain passive results written to {OUTPUT_FILE}")

    return OUTPUT_FILE


if __name__ == "__main__":
    run()
    print(f"Findomain results saved to: {OUTPUT_FILE}")
