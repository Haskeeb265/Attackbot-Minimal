import subprocess
from pathlib import Path

from service.recon_pipeline.asset_pipelines.config import TARGET
import shared.colorlog as colorlog

IMAGE = "lotuseatersec/assetfinder:latest"

# Output always lands in passive/output, regardless of cwd
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "assetfinder.txt"
LOG_FILE = OUTPUT_DIR / "assetfinder.log"


def run(domain: str = TARGET) -> Path:
    """Run assetfinder passive enum via Docker; write results to passive/output/assetfinder.txt.

    Passive subdomain enumeration using 7 public data sources (crt.sh,
    certspotter, hackertarget, threatcrowd, wayback machine,
    dns.bufferover.run, facebook CT). Sources requiring API keys
    (virustotal, facebook) are skipped unless env vars are set.

    Flags:
        --subs-only  Only include subdomains (exclude apex domain)
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "docker", "run", "--rm",
        IMAGE,
        "--subs-only",
        domain,
    ]

    colorlog.log.info(f"Running assetfinder passive enum (Docker) for {domain}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        colorlog.log.failed(f"assetfinder Docker run failed for {domain}: {e.stderr}")
        raise

    OUTPUT_FILE.write_text(result.stdout, encoding="utf-8")
    LOG_FILE.write_text(result.stderr, encoding="utf-8")
    colorlog.log.info(f"assetfinder passive results written to {OUTPUT_FILE}")

    return OUTPUT_FILE


if __name__ == "__main__":
    run()
    print(f"Assetfinder results saved to: {OUTPUT_FILE}")
