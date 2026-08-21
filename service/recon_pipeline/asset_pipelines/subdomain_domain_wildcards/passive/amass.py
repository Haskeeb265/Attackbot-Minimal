import subprocess
import uuid
from pathlib import Path
from service.recon_pipeline.asset_pipelines.subdomain_domain_wildcards.config import TARGET, OUTPUT_DIR

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
host_output_dir = OUTPUT_DIR.resolve()

AMASS_IMAGE = "jauderho/amass:v4.0.2"


def run_amass_passive():
    volume_name = f"amass_passive_{uuid.uuid4().hex[:8]}"
    subprocess.run(["docker", "volume", "create", volume_name], check=True, capture_output=True)

    command = [
        "docker", "run", "--rm",
        "--dns", "8.8.8.8",
        "--dns", "1.1.1.1",
        "-v", f"{volume_name}:/data",
        AMASS_IMAGE,
        "enum",
        "-passive",
        "-d", TARGET,
        "-o", "/data/passive.txt",
        "-log", "/data/passive.log",
        "-dir", "/data/amass_db",
    ]

    result = subprocess.run(command, capture_output=True, text=True)
    print(f"Amass return code: {result.returncode}")
    if result.returncode != 0:
        print("Amass stderr:", result.stderr)

    copy_result = subprocess.run([
        "docker", "run", "--rm",
        "-v", f"{volume_name}:/data",
        "-v", f"{host_output_dir}:/host",
        "alpine",
        "sh", "-c", "cp -a /data/. /host/",
    ], capture_output=True, text=True)
    if copy_result.returncode != 0:
        print("Copy failed:", copy_result.stderr)

    subprocess.run(["docker", "volume", "rm", volume_name], check=False, capture_output=True)
    return result


run_amass_passive()
print(f"amass passive results saved to: {host_output_dir / 'passive.txt'}")