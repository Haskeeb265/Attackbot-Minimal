#!/usr/bin/env python3
"""
Stage 0 entry point – runs live web service discovery on command‑line targets.
Usage:
    python main.py example.com
    python main.py example.com sub.example.com 192.168.1.1
"""

import asyncio
import sys
from stage0 import discover_live_origins

async def main(targets: list[str]):
    print(f"[*] Stage 0 starting for {len(targets)} target(s): {', '.join(targets)}")
    origins = await discover_live_origins(targets)

    if not origins:
        print("[!] No live web origins found.")
        return

    print(f"\n[+] Found {len(origins)} live origin(s):")
    for entry in origins:
        print(f"    {entry['origin']}  (status={entry['status']}, ip={entry['ip']}:{entry['port']})")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <domain_or_ip> [domain_or_ip ...]")
        sys.exit(1)

    targets = sys.argv[1:]
    asyncio.run(main(targets))