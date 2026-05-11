#!/usr/bin/env python3
"""
Amass/BGPView Wrapper - Phase 0 - ASN, Netblock, Subdomain Discovery
---------------------------------------------------------------------
Works on Windows, Linux, macOS.

Requirements:
  - Python packages: pip install requests
  - (Optional) Amass CLI: https://github.com/owasp-amass/amass/releases
    Only needed for passive subdomain enumeration.
    This script will work even without Amass installed (uses BGPView API).
"""

import subprocess
import sys
import json
import requests

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
AMASS_BINARY = "amass"            # 'amass.exe' on Windows
TIMEOUT = 120                     # seconds for amass enum
BGPVIEW_API = "https://api.bgpview.io"

# ------------------------------------------------------------------------------
# BGPView API functions (core for ASN/netblock now)
# ------------------------------------------------------------------------------
def bgpview_asn_prefixes(asn: str) -> dict:
    """
    Get all IPv4/IPv6 prefixes announced by an ASN.
    Accepts 'AS15169' or just '15169'.
    """
    clean_asn = asn.replace("AS", "").replace("as", "").strip()
    url = f"{BGPVIEW_API}/asn/{clean_asn}/prefixes"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ipv4 = [p['prefix'] for p in data['data'].get('ipv4_prefixes', [])]
        ipv6 = [p['prefix'] for p in data['data'].get('ipv6_prefixes', [])]
        return {"asn": f"AS{clean_asn}", "ipv4_prefixes": ipv4, "ipv6_prefixes": ipv6}
    except Exception as e:
        return {"error": f"BGPView API error: {e}"}


def bgpview_ip_lookup(ip_or_domain: str) -> dict:
    """
    Resolve a domain/IP to its ASN and covering prefix.
    """
    import socket
    # Resolve domain if needed
    try:
        socket.inet_aton(ip_or_domain)
        ip = ip_or_domain
    except (socket.error, OSError):
        try:
            ip = socket.gethostbyname(ip_or_domain)
        except socket.gaierror as e:
            return {"error": f"DNS resolution failed: {e}"}

    url = f"{BGPVIEW_API}/ip/{ip}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data['data']['asns']:
            asn_info = data['data']['asns'][0]
            prefix = data['data']['prefixes'][0]['prefix'] if data['data']['prefixes'] else None
            return {"ip": ip, "asn": asn_info['asn'], "asn_name": asn_info['name'], "prefix": prefix}
        else:
            return {"ip": ip, "asn": None, "error": "No ASN found"}
    except Exception as e:
        return {"error": str(e)}


def discover_asn_from_domain(domain: str) -> list:
    """
    Find all unique ASNs associated with a domain by looking up
    its resolved IP addresses and their ASNs.
    """
    import socket
    try:
        # Get all IPv4 addresses for the domain
        ips = list(set(socket.gethostbyname_ex(domain)[2]))
    except socket.gaierror:
        return []

    asns = set()
    for ip in ips:
        result = bgpview_ip_lookup(ip)
        if "asn" in result and result["asn"]:
            asns.add(f"AS{result['asn']}")
    return sorted(asns)


# ------------------------------------------------------------------------------
# Amass enum wrapper (optional, for subdomain discovery)
# ------------------------------------------------------------------------------
def amass_enum_passive(domain: str, output_file: str = None) -> dict:
    """
    Perform passive subdomain enumeration using amass enum.
    Returns a dict with list of subdomains.

    If Amass is not installed, returns an error clearly.
    """
    cmd = ["enum", "-passive", "-d", domain]
    if output_file:
        cmd += ["-o", output_file]

    try:
        result = subprocess.run(
            [AMASS_BINARY] + cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=True
        )
        # Amass writes results to file if -o is given; otherwise to stdout?
        # Passive results are printed to stdout as "subdomain.example.com" lines
        lines = [line.strip() for line in result.stdout.splitlines()
                 if line.strip() and not line.startswith('//')]
        if output_file:
            # If we used -o, the subdomains are in the file, not stdout.
            # So we read them from the file instead.
            try:
                with open(output_file, 'r') as f:
                    lines = [line.strip() for line in f if line.strip()]
            except FileNotFoundError:
                lines = []
        return {"domain": domain, "subdomains": lines, "output_file": output_file if output_file else None}
    except FileNotFoundError:
        return {"error": "Amass is not installed or not in PATH"}
    except subprocess.TimeoutExpired:
        return {"error": f"Amass enum timed out after {TIMEOUT}s"}
    except subprocess.CalledProcessError as e:
        return {"error": f"Amass enum failed:\n{e.stderr}"}


# ------------------------------------------------------------------------------
# Full workflow
# ------------------------------------------------------------------------------
def full_discovery(domain: str) -> dict:
    """
    Run the complete Phase 0 ASN/netblock/subdomain discovery
    for a given domain.
    """
    result = {"domain": domain}

    # 1. Discover ASNs from the domain's IP addresses
    print(f"[*] Discovering ASNs for {domain}...")
    asns = discover_asn_from_domain(domain)
    result["asns"] = asns

    # 2. Get prefixes for each ASN
    print(f"[*] Fetching netblocks for {len(asns)} ASNs...")
    prefixes = {}
    for asn in asns:
        prefixes[asn] = bgpview_asn_prefixes(asn)
    result["asn_prefixes"] = prefixes

    # 3. Optional passive subdomain enumeration (if Amass is available)
    print(f"[*] Attempting passive subdomain enumeration (Amass)...")
    subs = amass_enum_passive(domain)
    if "error" in subs and "not installed" in subs["error"].lower():
        result["subdomains"] = {"warning": "Amass not installed; skipping subdomain enumeration"}
    else:
        result["subdomains"] = subs

    return result


# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python amass_wrapper.py <domain>")
        sys.exit(1)

    domain = sys.argv[1]
    data = full_discovery(domain)
    print(json.dumps(data, indent=2, default=str))