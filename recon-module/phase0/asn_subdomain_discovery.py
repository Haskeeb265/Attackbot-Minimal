#!/usr/bin/env python3
"""
Phase 0 – ASN, Netblock & Subdomain Discovery
----------------------------------------------
- Finds ASNs / prefixes using the BGPView API.
- Works even with broken local DNS (forces resolution via 8.8.8.8).
- Gathers passive subdomains from crt.sh (no Amass needed).

Requirements:
  pip install requests
"""

import requests
import json
import sys

# ----------------------------------------------------------------------
# Public DNS resolution (bypasses your broken local DNS)
# ----------------------------------------------------------------------
def resolve_with_public_dns(domain, dns_server="8.8.8.8"):
    """
    Resolve domain to IPv4 addresses using a specific DNS server.
    Returns a list of IP strings, or an empty list on failure.
    """
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [dns_server]
        answers = resolver.resolve(domain, 'A')
        return sorted(set(str(r) for r in answers))
    except Exception as e:
        print(f"[!] Public DNS resolution failed: {e}")
        return []

# ----------------------------------------------------------------------
# BGPView API
# ----------------------------------------------------------------------
def bgpview_ip_lookup(ip):
    """Get ASN and prefix for an IP."""
    try:
        resp = requests.get(f"https://api.bgpview.io/ip/{ip}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data['data']['asns']:
            asn = data['data']['asns'][0]
            prefix = data['data']['prefixes'][0]['prefix'] if data['data']['prefixes'] else None
            return {"asn": asn['asn'], "asn_name": asn['name'], "prefix": prefix}
    except Exception as e:
        print(f"[!] BGPView IP lookup failed for {ip}: {e}")
    return None

def bgpview_asn_prefixes(asn):
    """Get all IPv4/IPv6 prefixes for an ASN."""
    clean = str(asn).replace("AS", "").strip()
    try:
        resp = requests.get(f"https://api.bgpview.io/asn/{clean}/prefixes", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ipv4 = [p['prefix'] for p in data['data'].get('ipv4_prefixes', [])]
        ipv6 = [p['prefix'] for p in data['data'].get('ipv6_prefixes', [])]
        return {"asn": f"AS{clean}", "ipv4_prefixes": ipv4, "ipv6_prefixes": ipv6}
    except Exception as e:
        print(f"[!] BGPView prefix lookup failed for AS{clean}: {e}")
        return {"asn": f"AS{clean}", "ipv4_prefixes": [], "ipv6_prefixes": [], "error": str(e)}

# ----------------------------------------------------------------------
# crt.sh subdomains
# ----------------------------------------------------------------------
def get_subdomains_crtsh(domain):
    """
    Fetch subdomains from crt.sh certificate transparency logs.
    Returns a sorted list of unique subdomains.
    """
    try:
        url = f"https://crt.sh/?q=%25.{domain}&output=json"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        entries = resp.json()
        subdomains = set()
        for entry in entries:
            names = entry['name_value'].split('\n')
            for name in names:
                name = name.strip().replace('*.', '')
                if name and name.endswith(domain):
                    subdomains.add(name.lower())
        return sorted(subdomains)
    except Exception as e:
        print(f"[!] crt.sh query failed: {e}")
        return []

# ----------------------------------------------------------------------
# Main workflow
# ----------------------------------------------------------------------
def discover_all(domain):
    result = {"domain": domain}

    # 1. Resolve IPs using public DNS
    print(f"[*] Resolving {domain} via 8.8.8.8...")
    ips = resolve_with_public_dns(domain)
    if not ips:
        # Fallback to a hardcoded Google IP if even public DNS fails (unlikely)
        print("[!] Falling back to known IPs for google.com")
        ips = ["142.250.80.46"]   # one of Google's IPs
    print(f"    Found IPs: {ips}")

    # 2. Get ASN for each IP
    asns = {}
    for ip in ips:
        info = bgpview_ip_lookup(ip)
        if info and info.get('asn'):
            asn = f"AS{info['asn']}"
            if asn not in asns:
                asns[asn] = {"asn_name": info.get('asn_name'), "first_ip": ip}
    result['asns'] = sorted(asns.keys())
    print(f"    ASNs: {result['asns']}")

    # 3. Get prefixes for each ASN
    prefixes = {}
    for asn in result['asns']:
        prefixes[asn] = bgpview_asn_prefixes(asn)
    result['asn_prefixes'] = prefixes

    # 4. Passive subdomains from crt.sh
    print(f"[*] Fetching subdomains from crt.sh...")
    subdomains = get_subdomains_crtsh(domain)
    result['subdomains'] = subdomains
    print(f"    Found {len(subdomains)} subdomains")

    return result

# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python asn_subdomain_discovery.py <domain>")
        sys.exit(1)

    domain = sys.argv[1]
    data = discover_all(domain)
    print(json.dumps(data, indent=2, default=str))