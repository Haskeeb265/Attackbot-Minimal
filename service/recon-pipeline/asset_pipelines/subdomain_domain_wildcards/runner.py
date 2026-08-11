"""
Shared docker runner for the subdomain / domain / wildcard asset pipeline.

Every recon tool in this folder (amass, subfinder, chaos, gau, tlsx, bbot,
waymore, waybackurls, github-subdomains, github-endpoints) is installed inside
a single Docker image — `attackbot/subdomain-wildcards-tools:latest`, built
from the `Dockerfile` in this folder. Each tool script takes the target as a
CLI argument and runs its query inside a fresh container of that image, e.g.:

    docker run --rm attackbot/subdomain-wildcards-tools:latest \
        subfinder -d example.com -silent

Build the image once:

    docker build -t attackbot/subdomain-wildcards-tools:latest \
        service/recon-pipeline/asset_pipelines/subdomain_domain_wildcards/
"""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

# Make the repo root importable when these scripts are run directly (the
# `recon-pipeline` folder name contains a hyphen, so it is not a package).
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.colorlog import log  # noqa: E402

# Docker image that bundles all the subdomain tools. Override via env.
DOCKER_IMAGE = os.getenv(
    "SUBDOMAIN_TOOLS_IMAGE",
    "attackbot/subdomain-wildcards-tools:latest",
)


def run_in_docker(
    command: list[str],
    env: list[str] | None = None,
    image: str = DOCKER_IMAGE,
    timeout: int | None = None,
    output=None,
    input_data: str | None = None,
) -> int:
    """
    Run ``command`` (tool name + args) inside a fresh container of ``image``,
    streaming the container's stdout/stderr line by line.

    The caller substitutes the dynamic target into ``command``.

    Args:
        command: tool name + arguments (target already substituted in).
        env: names of host environment variables to forward into the
            container (e.g. ``["GITHUB_TOKEN", "PDCP_API_KEY"]``); only
            variables that are set get forwarded.
        image: docker image tag to run the tool in.
        timeout: kill the container after this many seconds (``None`` = no
            limit).
        output: optional writable file object that also receives each line.
        input_data: optional string piped to the container's stdin
            (e.g. ``echo <target> | waybackurls``).

    Returns:
        The container's exit code (``-1`` on setup failure / timeout).
    """
    # A fixed name lets us `docker kill` the container if the tool times out
    # (killing the docker CLI client alone would orphan the container).
    container_name = f"subdomain-tool-{uuid4().hex[:8]}"

    docker_cmd = ["docker", "run", "--rm", "--name", container_name, "-i"]
    for name in env or []:
        value = os.environ.get(name)
        if value:
            docker_cmd += ["-e", f"{name}={value}"]
    docker_cmd += [image] + list(command)

    log.process(f"docker run {' '.join(docker_cmd[2:])}")

    stdin_pipe = subprocess.PIPE if input_data is not None else None

    try:
        process = subprocess.Popen(
            docker_cmd,
            stdin=stdin_pipe,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        log.failed("docker executable not found — is Docker installed and on PATH?")
        return -1

    if input_data is not None:
        process.stdin.write(input_data)
        process.stdin.close()

    for line in process.stdout:
        print(line, end="")
        if output is not None:
            output.write(line)

    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        # Best-effort container cleanup (no-op if it already exited).
        subprocess.run(
            ["docker", "kill", container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.failed(f"tool timed out after {timeout}s — container killed")
        return -1
