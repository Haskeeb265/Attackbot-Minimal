import subprocess
from pathlib import Path

TARGET = "example.com"
OUTPUT_DIR = Path(r"C:\Users\Home\Desktop\Projects\Attackbot-Minima\service\recon-pipeline\asset_pipelines\subdomain_domain_wildcards\output")
OUTPUT_FILE = OUTPUT_DIR / "subfinder.txt"

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