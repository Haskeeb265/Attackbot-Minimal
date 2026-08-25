
import subprocess
from pathlib import Path
import shared.colorlog as colorlog

AMASS_IMAGE = "caffix/amass"
OUTPUT_DIR = Path("output/amass").resolve()
CONFIG_DIR = Path("config/amass").resolve()  # holds config.yaml + datasources.yaml (API keys)

def run_amass_passive(domain: str) -> Path:

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"{domain}_passive.txt"
    log_file = OUTPUT_DIR / f"{domain}_passive.log"

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

    out_file.write_text(result.stdout, encoding="utf-8")
    log_file.write_text(result.stderr, encoding="utf-8")
    colorlog.log.info(f"amass passive results written to {out_file}")

    return out_file


if __name__ == "__main__":

    import sys

    if len(sys.argv) != 2:
        print("Usage: python amass.py qbsco.net")
        sys.exit(1)

    run_amass_passive(sys.argv[1])