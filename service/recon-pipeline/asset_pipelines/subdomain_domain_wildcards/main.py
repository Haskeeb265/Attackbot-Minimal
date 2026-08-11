"""
Subdomain / domain / wildcard asset pipeline runner.

Runs every bundled recon tool against a single target. Each tool receives
the target dynamically and executes inside its own Docker container (the
`subdomain-wildcards-tools` image — see `runner.py`), mirroring the manual
test documented in `test.md`: all tools run **in parallel** and each tool's
output is written to its own file as it finishes.

Usage:
    python main.py example.com
    python main.py example.com --out output/example-com
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import runner  # noqa: F401 — bootstraps sys.path so `shared.*` imports work
from shared.colorlog import log

import tool_amass
import tool_bbot
import tool_chaos
import tool_gau
import tool_github_endpoints
import tool_github_subdomains
import tool_subfinder
import tool_tlsx
import tool_waybackurls
import tool_waymore

# name -> run(target, timeout, output) callable
TOOLS = {
    "amass": tool_amass.run,
    "subfinder": tool_subfinder.run,
    "chaos": tool_chaos.run,
    "gau": tool_gau.run,
    "tlsx": tool_tlsx.run,
    "bbot": tool_bbot.run,
    "waymore": tool_waymore.run,
    "waybackurls": tool_waybackurls.run,
    "github-subdomains": tool_github_subdomains.run,
    "github-endpoints": tool_github_endpoints.run,
}


def run_all(target: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    log.process(f"Running {len(TOOLS)} tools against {target} -> {out_dir}")

    def _run_one(name: str, run_fn) -> None:
        out_path = out_dir / f"{name}.txt"
        log.process(f"[{name}] starting...")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                exit_code = run_fn(target, output=f)
            log.success(f"[{name}] finished (exit {exit_code}) — {out_path}")
        except Exception as e:
            log.failed(f"[{name}] failed: {e}")

    with ThreadPoolExecutor(max_workers=len(TOOLS)) as pool:
        futures = [pool.submit(_run_one, name, fn) for name, fn in TOOLS.items()]
        for future in futures:
            future.result()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run all subdomain recon tools against a target"
    )
    parser.add_argument("target", help="Target domain, e.g. example.com")
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory (default: output/<target>)",
    )
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else Path("output") / args.target
    run_all(args.target, out_dir)


if __name__ == "__main__":
    main()
