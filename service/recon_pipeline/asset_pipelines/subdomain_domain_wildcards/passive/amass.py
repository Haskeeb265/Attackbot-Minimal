import subprocess
from pathlib import Path

from service.recon_pipeline.asset_pipelines.config import TARGET
import shared.colorlog as colorlog

AMASS_IMAGE = "caffix/amass"

# Output/config always resolve relative to this file, regardless of cwd
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
CONFIG_DIR = Path(__file__).resolve().parent / "config"  # holds config.yaml + datasources.yaml (API keys)
OUTPUT_FILE = OUTPUT_DIR / "amass.txt"
LOG_FILE = OUTPUT_DIR / "amass.log"


def run(domain: str = TARGET) -> Path:
    """Run amass passive enum via Docker; write results to passive/output/amass.txt."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{CONFIG_DIR}:/root/.config/amass:ro",
        AMASS_IMAGE,
        "enum", "-passive", "-nocolor",
        "-d", domain,
    ]

    colorlog.log.info(f"Running amass passive enum (Docker) for {domain}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        colorlog.log.failed(f"amass Docker run failed for {domain}: {e.stderr}")
        raise

    OUTPUT_FILE.write_text(result.stdout, encoding="utf-8")
    LOG_FILE.write_text(result.stderr, encoding="utf-8")
    colorlog.log.info(f"amass passive results written to {OUTPUT_FILE}")

    return OUTPUT_FILE


if __name__ == "__main__":
    run()
    print(f"Amass results saved to: {OUTPUT_FILE}")