import subprocess
from pathlib import Path
from service.recon_pipeline.asset_pipelines.subdomain_domain_wildcards.config import TARGET, OUTPUT_DIR, OUTPUT_FILESUB

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

command = [
    "docker",
    "run",
    "--rm",
    "projectdiscovery/subfinder:v2.14.0",
    "-d",
    TARGET,
    "-silent",
]

with OUTPUT_FILESUB.open("w", encoding="utf-8") as file:
    subprocess.run(
        command,
        stdout=file,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

print(f"Subfinder results saved to: {OUTPUT_FILESUB}")