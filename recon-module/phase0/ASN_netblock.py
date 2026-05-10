#!/usr/bin/env python3
"""
Amass Wrapper for Phase 0 - ASN & Netblock Discovery
-----------------------------------------------------
Requires: amass (https://github.com/owasp-amass/amass)
Install:  sudo apt install amass   (Kali/Debian)
          or brew install amass    (macOS)

If amass is not found, the script gracefully degrades by using the BGPView API
for prefix lookups (but cannot discover ASNs from org/domain).
"""

import subprocess
import sys
import json
import socket
import requests

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
AMASS_PATH = "amass"          # Assumes 'amass' is in PATH
TIMEOUT = 120                  # seconds, some intel queries take time
BGPVIEW_API = "https://api.bgpview.io"

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def _run_amass(cmd_list, description="Amass command"):
    """Run an amass command and return stdout lines, or an error dict."""
    try:
        result = subprocess.run(
            [AMASS_PATH] + cmd_list,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=True
        )
        lines = [line.strip() for line in result.stdout.splitlines()
                 if line.strip() and not line.startswith('//')]
        return lines
    except FileNotFoundError:
        return {"error": "Amass is not installed or not in PATH"}
    except subprocess.TimeoutExpired:
        return {"error": f"{description} timed out after {TIMEOUT}s"}
    except subprocess.CalledProcessError as e:
        return {"error": f"{description} failed:\n{e.stderr}"}


def _bgpview_asn_prefixes(asn):
    """Fallback: get prefixes for an ASN using BGPView API."""
    url = f"{BGPVIEW_API}/asn/{asn}/prefixes"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ipv4 = [p['prefix'] for p in data['data'].get('ipv4_prefixes', [])]
        ipv6 = [p['prefix'] for p in data['data'].get('ipv6_prefixes', [])]
        return {"asn": asn, "ipv4_prefixes": ipv4, "ipv6_prefixes": ipv6}
    except Exception as e:
        return {"error": f"BGPView API error: {e}"}


def _bgpview_ip_lookup(ip):
    """Fallback: get ASN + prefix for a single IP."""
    url = f"{BGPVIEW_API}/ip/{ip}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data['data']['asns']:
            asn_info = data['data']['asns'][0]
            prefix = data['data']['prefixes'][0]['prefix'] if data['data']['prefixes'] else None
            return {
                "ip": ip,
                "asn": asn_info['asn'],
                "asn_name": asn_info['name'],
                "prefix": prefix
            }
        else:
            return {"ip": ip, "asn": None, "error": "No ASN found"}
    except Exception as e:
        return {"error": str(e)}

# ------------------------------------------------------------------------------
# Main Amass Functions
# ------------------------------------------------------------------------------
def amass_intel_org(org_name):
    """
    Discover ASNs associated with an organisation name.
    Returns a list of ASN strings.
    """
    raw = _run_amass(["intel", "-org", org_name], f"Intel org '{org_name}'")
    if isinstance(raw, dict) and "error" in raw:
        return raw
    # Filter only lines that look like AS numbers (e.g., "AS15169")
    asns = [line for line in raw if line.upper().startswith("AS")]
    return {"org": org_name, "asns": asns}


def amass_intel_domain(domain):
    """
    Discover ASNs, IP ranges, and related domains for a given root domain.
    Returns a dict with discovered ASNs and netblocks.
    """
    raw = _run_amass(["intel", "-d", domain], f"Intel domain '{domain}'")
    if isinstance(raw, dict) and "error" in raw:
        return raw

    asns = []
    prefixes = []
    for line in raw:
        if line.upper().startswith("AS"):
            asns.append(line)
        elif "/" in line and not line.startswith("//"):  # looks like a CIDR
            prefixes.append(line)
    return {"domain": domain, "asns": asns, "prefixes": prefixes}


def amass_intel_asn(asn, use_bgpview_fallback=True):
    """
    Get all netblocks (IPv4/IPv6) for a given ASN.
    If Amass fails and fallback is enabled, uses BGPView API.
    """
    # Remove 'AS' prefix if present, amass expects just the number
    clean_asn = asn.replace("AS", "").strip()
    raw = _run_amass(["intel", "-asn", clean_asn], f"Intel ASN {asn}")
    if isinstance(raw, dict) and "error" in raw:
        if use_bgpview_fallback:
            print(f"[!] Amass failed for ASN {asn}, trying BGPView API...")
            return _bgpview_asn_prefixes(clean_asn)
        return raw

    prefixes = [line for line in raw if "/" in line]
    ipv4 = [p for p in prefixes if ":" not in p]   # no colons → IPv4
    ipv6 = [p for p in prefixes if ":" in p]
    return {"asn": asn, "ipv4_prefixes": ipv4, "ipv6_prefixes": ipv6}


def amass_enum_passive(domain, output_file=None):
    """
    Perform passive subdomain enumeration for a domain.
    Optionally save results to a file.
    Returns a list of subdomains (if output not saved, reads from stdout).
    """
    cmd = ["enum", "-passive", "-d", domain]
    if output_file:
        cmd += ["-o", output_file]

    raw = _run_amass(cmd, f"Enum passive '{domain}'")
    if isinstance(raw, dict) and "error" in raw:
        return raw

    if output_file:
        return {"status": "success", "output_file": output_file, "subdomains": raw}
    else:
        return {"domain": domain, "subdomains": raw}


def amass_enum_active(domain, output_file=None):
    """
    Perform active subdomain enumeration for a domain.
    (This can be noisy and more intrusive – use with permission.)
    """
    cmd = ["enum", "-active", "-d", domain]
    if output_file:
        cmd += ["-o", output_file]

    raw = _run_amass(cmd, f"Enum active '{domain}'")
    if isinstance(raw, dict) and "error" in raw:
        return raw

    if output_file:
        return {"status": "success", "output_file": output_file, "subdomains": raw}
    else:
        return {"domain": domain, "subdomains": raw}


# ------------------------------------------------------------------------------
# Integrated Reconnaissance Workflow
# ------------------------------------------------------------------------------
def full_asn_discovery(domain=None, org_name=None):
    """
    Given a domain or organisation name, discover ASNs and their netblocks.
    If domain is provided, also attempts passive passive subdomain enumeration.
    """
    result = {}
    if org_name:
        print(f"[*] Discovering ASNs for org: {org_name}")
        asn_data = amass_intel_org(org_name)
        result['org_asns'] = asn_data

    if domain:
        print(f"[*] Discovering ASNs and prefixes for domain: {domain}")
        domain_data = amass_intel_domain(domain)
        result['domain_intel'] = domain_data

    # For every discovered ASN, get its prefixes
    all_asns = set()
    if 'org_asns' in result and isinstance(result['org_asns'], dict) and 'asns' in result['org_asns']:
        all_asns.update(result['org_asns']['asns'])
    if 'domain_intel' in result and isinstance(result['domain_intel'], dict) and 'asns' in result['domain_intel']:
        all_asns.update(result['domain_intel']['asns'])

    asn_prefixes = {}
    for asn in all_asns:
        print(f"[*] Getting prefixes for {asn}")
        prefixes = amass_intel_asn(asn)
        asn_prefixes[asn] = prefixes
    result['asn_prefixes'] = asn_prefixes

    # Optional: passive enumeration of the domain
    if domain:
        print(f"[*] Passive subdomain enumeration for {domain}")
        subs = amass_enum_passive(domain)
        result['passive_subs'] = subs

    return result


# ------------------------------------------------------------------------------
# Command-line test
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 amass_wrapper.py <domain> [org_name]")
        sys.exit(1)

    target_domain = sys.argv[1]
    target_org = sys.argv[2] if len(sys.argv) > 2 else None

    # Example: Combine with the earlier WHOIS result to feed org name automatically
    # (Assume we already have whois data, this is just a demo)
    results = full_asn_discovery(domain=target_domain, org_name=target_org)
    print(json.dumps(results, indent=2, default=str))