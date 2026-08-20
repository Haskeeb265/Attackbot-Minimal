import subprocess
from pathlib import Path
from service.recon_pipeline.asset_pipelines.subdomain_domain_wildcards.config import TARGET, OUTPUT_DIR, OUTPUT_FILE

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

command = [
    "docker",
    "run",
    "--rm",
    "projectdiscovery/subfinder:latest",
    "-d",
    TARGET,
    "-silent",
]

with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    subprocess.run(
        command,
        stdout=file,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

print(f"Subfinder results saved to: {OUTPUT_FILE}")