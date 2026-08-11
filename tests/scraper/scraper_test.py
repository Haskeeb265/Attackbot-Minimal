"""
Manual/integration test for ProgramDetailScraper.

Instead of going through ProgramScraper.high_priority_handle_scraping() /
low_priority_handle_scraping() (which requires paging through the entire
/hackers/programs list), this script lets you pass a specific list of
handles directly and runs the same per-handle pipeline that
high_priority_handle_detail_scraping() / low_priority_handle_detail_scraping()
would have run on them.

Usage:
    python -m your_package.tests.test_program_detail_scraper --handles shopify hackerone
    python -m your_package.tests.test_program_detail_scraper --handles-file handles.txt
    python -m your_package.tests.test_program_detail_scraper  # uses DEFAULT_HANDLES below
"""

import argparse
import json
import sys

from service.scraper.program_detail_scraper import ProgramDetailScraper
from shared.colorlog import log


# Edit this list for quick ad-hoc runs without CLI args
DEFAULT_HANDLES = [
    "cloudflare"
]


def scrape_handles(handles: list[str]) -> list[dict]:
    """
    Runs the exact same per-handle pipeline as
    high_priority_handle_detail_scraping()/low_priority_handle_detail_scraping(),
    but against a caller-supplied handle list instead of a scraped one.
    """
    detail_scraper = ProgramDetailScraper()
    results = []
    for handle in handles:
        log.process(f"=== Testing handle: {handle} ===")
        try:
            record = detail_scraper.fetch_program(handle)
            results.append(record)
            log.success(f"[{handle}] Done — "
                        f"{record['scope_count']} scopes, "
                        f"{len(record['scope_exclusions'])} exclusions, "
                        f"{len(record['weaknesses'])} weaknesses")
        except Exception as e:
            log.failed(f"[{handle}] Failed: {e}")
            results.append({"handle": handle, "error": str(e)})

    return results


def scrape_single_component(handle: str, component: str):
    """
    Hit just one piece of functionality for a single handle — useful when
    you only want to debug e.g. get_weaknesses() without re-fetching scopes.
    component: "scopes" | "exclusions" | "weaknesses"
    """
    detail_scraper = ProgramDetailScraper()
    if component == "scopes":
        return detail_scraper._fetch_handle_scopes(handle)
    elif component == "exclusions":
        return detail_scraper.get_scope_exclusions(handle)
    elif component == "weaknesses":
        return detail_scraper.get_weaknesses(handle)
    else:
        raise ValueError(f"Unknown component: {component}")


def parse_args():
    parser = argparse.ArgumentParser(description="Test ProgramDetailScraper against explicit handles")
    parser.add_argument("--handles", nargs="+", help="Space-separated list of handles to test")
    parser.add_argument("--handles-file", help="Path to a text file with one handle per line")
    parser.add_argument("--component", choices=["scopes", "exclusions", "weaknesses"],
                         help="Only test a single component instead of the full pipeline")
    parser.add_argument("--out", default="test_detail_output.json", help="Output JSON path")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.handles:
        handles = args.handles
    elif args.handles_file:
        with open(args.handles_file) as f:
            handles = [line.strip() for line in f if line.strip()]
    else:
        handles = DEFAULT_HANDLES

    if not handles:
        log.failed("No handles provided (use --handles, --handles-file, or set DEFAULT_HANDLES)")
        sys.exit(1)

    log.process(f"Running test against {len(handles)} explicit handle(s): {handles}")

    if args.component:
        results = {h: scrape_single_component(h, args.component) for h in handles}
    else:
        results = scrape_handles(handles)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=4)

    log.success(f"Results written to {args.out}")


if __name__ == "__main__":
    main()