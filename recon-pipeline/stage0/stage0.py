#!/usr/bin/env python3
"""
Stage 0: Live Web Service Discovery
- DNS resolution (A records)
- Lightweight TCP port scanning
- HTTP/HTTPS verification
Output: list of unique live web origins (protocol://host:port)
"""

import asyncio
import ipaddress
import logging
import socket
import ssl
from typing import Optional

import aiodns
import aiohttp

import sys

logger = logging.getLogger("stage0")
logger.setLevel(logging.DEBUG)

# Create a stream handler that prints to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# ---------------------------------------------------------------------------
# 1. DNS resolution
# ---------------------------------------------------------------------------
async def resolve_target(target: str) -> list[str]:
    """
    Resolve a domain (or IP) to a list of IPv4 addresses.
    Tries aiodns first, falls back to asyncio's built-in getaddrinfo.
    """
    # Quick check: already an IP?
    try:
        ipaddress.ip_address(target)
        return [target]
    except ValueError:
        pass

    # --- Attempt 1: aiodns (fast, non-blocking) ---
    try:
        resolver = aiodns.DNSResolver()
        answers = await resolver.query(target, 'A')
        ip_list = sorted({answer.host for answer in answers})
        logger.info(f"Resolved {target} via aiodns -> {ip_list}")
        return ip_list
    except Exception as e:
        logger.debug(f"aiodns failed for {target}: {e}")

    # --- Fallback: asyncio built-in resolver (works on all platforms) ---
    try:
        loop = asyncio.get_running_loop()
        addrinfo = await loop.getaddrinfo(target, None, family=socket.AF_INET)
        ip_list = sorted({addr[4][0] for addr in addrinfo})
        logger.info(f"Resolved {target} via getaddrinfo -> {ip_list}")
        return ip_list
    except Exception as e:
        logger.warning(f"All DNS methods failed for {target}: {e}")
        return []
# ---------------------------------------------------------------------------
# 2. TCP port scanning
# ---------------------------------------------------------------------------
# Default set of common web / API ports
COMMON_WEB_PORTS = [80, 443, 8080, 8443, 3000, 4443, 5000, 8000, 8008, 8081, 8888]

async def tcp_connect(ip: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if a TCP connection to ip:port succeeds within timeout."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False

async def scan_ports(
    ip: str,
    ports: Optional[list[int]] = None,
    concurrency: int = 20
) -> list[int]:
    """Return sorted list of open web ports on the given IP."""
    if ports is None:
        ports = COMMON_WEB_PORTS

    sem = asyncio.Semaphore(concurrency)

    async def probe(p: int) -> Optional[int]:
        async with sem:
            if await tcp_connect(ip, p):
                logger.debug(f"Open port: {ip}:{p}")
                return p
        return None

    tasks = [probe(p) for p in ports]
    results = await asyncio.gather(*tasks)
    open_ports = sorted([p for p in results if p is not None])
    logger.info(f"Open ports on {ip}: {open_ports}")
    return open_ports

# ---------------------------------------------------------------------------
# 3. HTTP/HTTPS verification
# ---------------------------------------------------------------------------
async def verify_web_service(
    ip: str,
    port: int,
    timeout: float = 5.0,
    max_redirects: int = 5
) -> Optional[dict]:
    """
    Plain IP‑only HTTP/HTTPS check – no SNI, no hostname.
    Returns canonical origin after redirects (or raw IP if no redirect).
    """
    # Port‑based protocol selection
    if port == 443:
        protocols = ["https"]
    elif port == 80:
        protocols = ["http"]
    else:
        protocols = ["https", "http"]

    for scheme in protocols:
        url = f"{scheme}://{ip}:{port}"
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(
                ssl=ssl_context,
                force_close=True,
            )
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as session:
                async with session.get(
                    url,
                    allow_redirects=True,
                    max_redirects=max_redirects,
                ) as resp:
                    final_url = str(resp.url)
                    origin = f"{resp.url.scheme}://{resp.url.host}"
                    if resp.url.port and resp.url.port not in (80, 443):
                        origin += f":{resp.url.port}"
                    return {
                        "origin": origin,
                        "final_url": final_url,
                        "status": resp.status,
                        "protocol": resp.url.scheme,
                        "ip": ip,
                        "port": port,
                    }
        except Exception:
            continue
    return None
# ---------------------------------------------------------------------------
# 4. Stage 0 orchestrator
# ---------------------------------------------------------------------------
async def discover_live_origins(
    targets: list[str],
    ports: Optional[list[int]] = None,
    concurrency: int = 50
) -> list[dict]:
    """
    Stage 0 pipeline:
      DNS resolution -> port scan -> HTTP/HTTPS verification -> live origins.
    Returns deduplicated list of origins.
    """
    # 1. Resolve all targets
    ip_map = {}
    for target in targets:
        ips = await resolve_target(target)
        if ips:
            ip_map[target] = ips
        else:
            logger.warning(f"Skipping unresolved target: {target}")

    if not ip_map:
        return []

    # Flatten unique (ip, original_target) pairs
    ip_pairs = set()
    for target, ips in ip_map.items():
        for ip in ips:
            ip_pairs.add((ip, target))

    # 2. Scan ports on each unique IP
    sem = asyncio.Semaphore(concurrency)

    async def scan_single(ip: str, orig_target: str) -> list[tuple[str, int, str]]:
        async with sem:
            open_ports = await scan_ports(ip, ports)
            return [(ip, port, orig_target) for port in open_ports]

    scan_tasks = [scan_single(ip, tgt) for ip, tgt in ip_pairs]
    nested = await asyncio.gather(*scan_tasks)
    open_services = [item for sublist in nested for item in sublist]

    # 3. Verify HTTP/HTTPS on each open (ip, port)
    async def verify_one(ip: str, port: int, orig_target: str) -> Optional[dict]:
        async with sem:
            return await verify_web_service(ip, port)

    verify_tasks = [verify_one(ip, port, tgt) for ip, port, tgt in open_services]
    results = await asyncio.gather(*verify_tasks)

    # Deduplicate by origin
    seen = set()
    live = []
    for r in results:
        if r and r["origin"] not in seen:
            seen.add(r["origin"])
            live.append(r)

    logger.info(f"Total live origins: {len(live)}")
    return live