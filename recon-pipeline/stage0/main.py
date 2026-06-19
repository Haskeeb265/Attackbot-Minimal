from typing import TypedDict, List, Dict, Set, Optional, Annotated
from langgraph.graph import StateGraph, START, END
import operator
import subprocess
import json
import os
import requests
import socket
import tempfile
import re
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime
import urllib3

# Disable SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Pinned binaries (absolute paths, never trust PATH) ──────────────
SUBFINDER_BIN = os.path.join(os.environ.get("USERPROFILE", ""), "go", "bin", "subfinder.exe")
HTTPX_BIN     = os.path.join(os.environ.get("USERPROFILE", ""), "go", "bin", "httpx.exe")
NAABU_BIN     = os.path.join(os.environ.get("USERPROFILE", ""), "go", "bin", "naabu.exe")
KATANA_BIN    = os.path.join(os.environ.get("USERPROFILE", ""), "go", "bin", "katana.exe")
FFUF_BIN      = os.path.join(os.environ.get("USERPROFILE", ""), "go", "bin", "ffuf.exe")
DNSX_BIN      = os.path.join(os.environ.get("USERPROFILE", ""), "go", "bin", "dnsx.exe")
TLSX_BIN      = os.path.join(os.environ.get("USERPROFILE", ""), "go", "bin", "tlsx.exe")
NUCLEI_BIN    = os.path.join(os.environ.get("USERPROFILE", ""), "go", "bin", "nuclei.exe")

# ── Scope gate (sacred, deterministic, deny-by-default) ───────────────
IN_SCOPE = ["bahria.edu.pk"]

def is_in_scope(domain: str) -> bool:
    domain = domain.strip().lower().rstrip(".")
    for allowed in IN_SCOPE:
        if domain == allowed or domain.endswith("." + allowed):
            return True
    return False


def _canonicalize_domain(domain: str) -> Optional[str]:
    """CAF: strip wildcards, lowercase, validate."""
    domain = domain.strip().lower().rstrip(".")
    if domain.startswith("*."):
        domain = domain[2:]
    if not domain or "." not in domain:
        return None
    # Reject anything with invalid characters
    if re.search(r'[^a-z0-9.\-_]', domain):
        return None
    return domain


def _merge_dicts(left: Dict[str, Dict], right: Dict[str, Dict]) -> Dict[str, Dict]:
    return {**left, **right}


# ── Enhanced State ─────────────────────────────────────────────────────
class ReconState(TypedDict):
    target: str
    scope_decision: str

    # Discovery
    recon_output: List[str]
    in_scope_hosts: List[str]

    # Resolution
    ip_map: Dict[str, List[str]]
    resolved_ips: List[str]

    # Enumeration
    open_ports: List[Dict]
    service_targets: List[str]
    live_hosts: List[str]

    # Inspection
    host_details: List[Dict]

    # Endpoint extraction (existing)
    endpoints: List[Dict]

    # NEW: Crawl layer
    crawled_endpoints: List[Dict]      # From katana/gospider
    forms: List[Dict]                 # Discovered forms
    js_files: List[Dict]               # JavaScript files for analysis

    # NEW: Fuzz layer
    fuzz_results: List[Dict]          # Directory/file brute force
    discovered_panels: List[Dict]     # Admin panels, login pages

    # NEW: Secrets layer
    secrets_found: List[Dict]         # API keys, tokens, credentials
    git_exposed: List[str]             # Exposed .git directories
    env_files: List[str]               # Exposed .env files

    # NEW: DNS deep layer
    dns_records: Dict[str, List[Dict]] # MX, NS, TXT, SPF, DMARC, DKIM
    ptr_records: Dict[str, str]        # Reverse DNS
    tls_history: List[Dict]            # Historical certificates
    ct_logs: List[Dict]              # Certificate transparency logs

    # Meta
    tool_plan: Dict[str, List[str]]
    audit_log: Annotated[List[Dict], operator.add]
    layer_results: Annotated[Dict[str, Dict], _merge_dicts]


# ── Safe subprocess helper ──────────────────────────────────────────
def _run_cmd(args: List[str], input_data: str = None, timeout: int = 120) -> dict:
    result = {"stdout": "", "stderr": "", "rc": -1, "error": None}
    try:
        proc = subprocess.run(
            args,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["rc"] = proc.returncode
    except FileNotFoundError as e:
        result["error"] = f"binary_not_found: {e.filename}"
    except subprocess.TimeoutExpired:
        result["error"] = "timeout"
    except Exception as e:
        result["error"] = f"exception: {e}"
    return result


# ═══════════════════════════════════════════════════════════════════════
# EXISTING TOOLS (kept for compatibility)
# ═══════════════════════════════════════════════════════════════════════

def _run_subfinder(target: str) -> List[str]:
    print(f"[_run_subfinder] running on {target}")
    result = _run_cmd([SUBFINDER_BIN, "-d", target, "-silent", "-oJ"], timeout=120)
    if result["error"] or result["rc"] != 0:
        print(f"[_run_subfinder] failed: {result.get('error', 'non-zero exit')}")
        return []
    hosts = []
    for line in result["stdout"].splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            host = json.loads(line).get("host")
            if host:
                hosts.append(host)
        except json.JSONDecodeError:
            continue
    print(f"[_run_subfinder] found {len(hosts)} hosts")
    return hosts

def _run_crtsh(target: str) -> List[str]:
    url = f"https://crt.sh/?q=%.{target}&output=json"
    print(f"[_run_crtsh] querying crt.sh")
    try:
        resp = requests.get(url, timeout=30, verify=False)
        resp.raise_for_status()
        entries = resp.json()
        discovered = set()
        for entry in entries:
            for key in ("common_name", "name_value"):
                val = entry.get(key, "")
                for name in val.split("\n"):
                    name = name.strip().lower().rstrip(".")
                    if name and name.endswith(target):
                        discovered.add(name)
        print(f"[_run_crtsh] found {len(discovered)} hosts")
        return list(discovered)
    except Exception as e:
        print(f"[_run_crtsh] error (non-fatal): {e}")
        return []

def _run_naabu(ips: List[str]) -> List[Dict]:
    if not ips:
        return []
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("\n".join(ips))
        ip_list_path = f.name
    try:
        result = _run_cmd([
            NAABU_BIN, "-list", ip_list_path, "-json", "-silent",
            "-top-ports", "1000", "-rate", "3000", "-scan-type", "c",
        ], timeout=300)
        if result["error"]:
            print(f"[_run_naabu] failed: {result['error']}")
            return []
        ports = []
        seen = set()
        for line in result["stdout"].strip().splitlines():
            try:
                entry = json.loads(line)
                key = (entry.get("ip") or entry.get("host", "UNKNOWN"), entry["port"])
                if key not in seen:
                    seen.add(key)
                    ports.append({
                        "ip": key[0], "port": entry["port"],
                        "protocol": entry.get("protocol", "tcp")
                    })
            except (json.JSONDecodeError, KeyError):
                continue
        print(f"[_run_naabu] found {len(ports)} unique open ports")
        return ports
    finally:
        os.unlink(ip_list_path)

def _run_httpx(hosts: List[str]) -> List[str]:
    if not hosts:
        return []
    print(f"[_run_httpx] probing {len(hosts)} hosts")
    result = _run_cmd(
        [HTTPX_BIN, "-silent", "-json", "-sc", "-title"],
        input_data="\n".join(hosts), timeout=180
    )
    if result["error"]:
        print(f"[_run_httpx] failed: {result['error']}")
        return []
    live = []
    for line in result["stdout"].splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            url = obj.get("url")
            status = obj.get("status_code")
            if url:
                live.append(f"{url} [{status}]")
        except json.JSONDecodeError:
            continue
    print(f"[_run_httpx] {len(live)} live web servers")
    return live

def _run_httpx_deep(urls: List[str]) -> List[Dict]:
    if not urls:
        return []
    print(f"[_run_httpx_deep] deep probing {len(urls)} urls")
    result = _run_cmd(
        [HTTPX_BIN, "-silent", "-json", "-tech-detect", "-tls-grab",
         "-hash", "body", "-jarm", "-follow-redirects"],
        input_data="\n".join(urls), timeout=180
    )
    if result["error"]:
        print(f"[_run_httpx_deep] failed: {result['error']}")
        return []
    details = []
    for line in result["stdout"].splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            details.append({
                "url": obj.get("url"),
                "status_code": obj.get("status_code"),
                "title": obj.get("title"),
                "tech": obj.get("tech", []),
                "tls": obj.get("tls", {}),
                "body_hash": obj.get("hash", {}).get("body"),
                "jarm": obj.get("jarm"),
                "headers": obj.get("header", {}),
            })
        except json.JSONDecodeError:
            continue
    print(f"[_run_httpx_deep] enriched {len(details)} hosts")
    return details


def _extract_from_body(base_url: str, body: str) -> List[Dict]:
    found = []
    patterns = [
        (r'href=["\'](.*?)["\']', "link"),
        (r'src=["\'](.*?)["\']', "script"),
        (r'action=["\'](.*?)["\']', "form"),
        (r'url\(["\']?(.*?)["\']?\)', "css_url"),
        (r'data-[a-z-]+=["\'](.*?)["\']', "data_attr"),
    ]
    for pattern, ep_type in patterns:
        for match in re.findall(pattern, body, re.IGNORECASE):
            match = match.strip()
            if not match or match.startswith("#") or match.startswith("mailto:"):
                continue
            if match.startswith("http"):
                found.append({"raw": match, "type": ep_type})
            else:
                found.append({"raw": urljoin(base_url, match), "type": ep_type})

    leak_pattern = re.compile(
        r'(https?://[^\s"\'<>]+|localhost:\d+|127\.0\.0\.1:\d+|'
        r'10\.\d+\.\d+\.\d+:\d+|192\.168\.\d+\.\d+:\d+|'
        r'172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+:\d+)',
        re.IGNORECASE
    )
    for match in leak_pattern.findall(body):
        found.append({"raw": match, "type": "leak"})

    api_patterns = [
        r'["\'](/api/[a-zA-Z0-9/_-]+)["\']',
        r'["\'](/v\d+/[a-zA-Z0-9/_-]+)["\']',
        r'["\'](/graphql|/graphiql|/swagger|/openapi\.json|/health|/status)["\']',
    ]
    for pattern in api_patterns:
        for match in re.findall(pattern, body):
            found.append({"raw": urljoin(base_url, match), "type": "api_pattern"})

    seen = set()
    unique = []
    for item in found:
        if item["raw"] not in seen:
            seen.add(item["raw"])
            unique.append(item)
    return unique


# ═══════════════════════════════════════════════════════════════════════
# NEW LAYERS
# ═══════════════════════════════════════════════════════════════════════

# ── LAYER: CRAWL ─────────────────────────────────────────────────────

def _run_katana(urls: List[str]) -> List[Dict]:
    """Headless crawler for JS-rendered content, forms, and deep links."""
    if not urls:
        return []
    print(f"[_run_katana] crawling {len(urls)} urls")

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("\n".join(urls))
        url_list_path = f.name

    try:
        result = _run_cmd([
            KATANA_BIN, "-list", url_list_path,
            "-jc",           # JS crawl
            "-kf", "all",    # Keep all file types
            "-fx",           # Form extraction
            "-xhr",          # XHR extraction
            "-silent",
            "-json",
            "-timeout", "15",
            "-retry", "2",
        ], timeout=300)

        if result["error"]:
            print(f"[_run_katana] failed: {result['error']}")
            return []

        endpoints = []
        forms = []
        js_files = []

        for line in result["stdout"].splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                url = obj.get("url", "")

                # Categorize by extension/pattern
                if url.endswith(".js") or ".js?" in url:
                    js_files.append({
                        "url": url,
                        "source": obj.get("source", ""),
                        "method": obj.get("method", "GET"),
                    })
                elif obj.get("type") == "form":
                    forms.append({
                        "url": url,
                        "source": obj.get("source", ""),
                        "method": obj.get("method", "GET"),
                        "params": obj.get("params", []),
                    })
                else:
                    endpoints.append({
                        "url": url,
                        "source": obj.get("source", ""),
                        "type": obj.get("type", "unknown"),
                        "method": obj.get("method", "GET"),
                    })
            except json.JSONDecodeError:
                continue

        print(f"[_run_katana] {len(endpoints)} endpoints, {len(forms)} forms, {len(js_files)} JS files")
        return {
            "endpoints": endpoints,
            "forms": forms,
            "js_files": js_files
        }
    finally:
        os.unlink(url_list_path)


def crawl_layer(state: ReconState) -> dict:
    """Intent: Go through the doors and see what's inside.
    Uses headless crawling to find JS-rendered content, forms,
    API calls, and deep links that regex missed."""

    live = state.get("live_hosts", [])
    if not live:
        print("[crawl_layer] no live hosts; skipping")
        return {
            "crawled_endpoints": [],
            "forms": [],
            "js_files": [],
            "audit_log": [{
                "layer": "crawl", "status": "skipped", "reason": "no_live_hosts"
            }]
        }

    urls = []
    for line in live:
        url = line.split(" [")[0] if " [" in line else line
        urls.append(url)

    plan = state.get("tool_plan", {}).get("crawl", ["katana"])
    audit = []
    all_endpoints = []
    all_forms = []
    all_js = []

    for tool_name in plan:
        if tool_name == "katana":
            result = _run_katana(urls)
            if result:
                all_endpoints.extend(result["endpoints"])
                all_forms.extend(result["forms"])
                all_js.extend(result["js_files"])
                audit.append({
                    "tool": "katana",
                    "status": "success",
                    "endpoints": len(result["endpoints"]),
                    "forms": len(result["forms"]),
                    "js_files": len(result["js_files"])
                })
            else:
                audit.append({"tool": "katana", "status": "failed_or_empty"})
        elif tool_name == "gospider":
            audit.append({"tool": "gospider", "status": "not_implemented"})
        else:
            audit.append({"tool": tool_name, "status": "unknown_tool"})

    # Deduplicate
    seen = set()
    deduped_eps = []
    for ep in all_endpoints:
        if ep["url"] not in seen:
            seen.add(ep["url"])
            ep["in_scope"] = is_in_scope(urlparse(ep["url"]).netloc or "")
            deduped_eps.append(ep)

    print(f"[crawl_layer] total: {len(deduped_eps)} endpoints, {len(all_forms)} forms, {len(all_js)} JS files")

    return {
        "crawled_endpoints": deduped_eps,
        "forms": all_forms,
        "js_files": all_js,
        "audit_log": audit,
        "layer_results": {
            "crawl": {
                "endpoints": len(deduped_eps),
                "forms": len(all_forms),
                "js_files": len(all_js),
            }
        },
    }


# ── LAYER: FUZZ ──────────────────────────────────────────────────────

def _resolve_wordlists(preferred: Optional[str] = None) -> List[str]:
    """Resolve wordlists with cross-platform fallbacks and a nuclear temp-file option."""
    if preferred and os.path.exists(preferred):
        return [preferred]

    candidates = [
        os.environ.get("FFUF_WORDLIST"),
        os.path.join(os.environ.get("USERPROFILE", ""), "wordlists", "common.txt"),
        os.path.join(os.environ.get("USERPROFILE", ""), "wordlists", "raft-medium-directories.txt"),
        os.path.join(os.environ.get("USERPROFILE", ""), "wordlists", "api-endpoints.txt"),
        "/usr/share/wordlists/dirb/common.txt",
        "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt",
        "/usr/share/seclists/Discovery/Web-Content/common.txt",
        "/usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt",
        "wordlists/common.txt",
        "common.txt",
    ]

    found = [p for p in candidates if p and os.path.exists(p)]
    if found:
        return found

    # Nuclear fallback: generate a minimal temp wordlist so ffuf never runs empty
    minimal = [
        "admin", "login", "api", "test", "dev", "staging", "backup",
        "config", "env", ".env", "wp-admin", "phpmyadmin", "robots.txt",
        "sitemap.xml", ".git", "api/v1", "graphql", "swagger", "debug",
        "panel", "manage", "setup", "install", "webmail", "phpinfo"
    ]
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt")
    tmp.write("\n".join(minimal))
    tmp.close()
    print(f"[_resolve_wordlists] WARNING: No wordlists found. Generated minimal fallback: {tmp.name}")
    return [tmp.name]


def _run_ffuf(urls: List[str], wordlist: Optional[str] = None) -> List[Dict]:
    if not urls:
        return []

    wordlists = _resolve_wordlists(wordlist)
    all_results = []
    temp_files_to_clean: List[str] = []

    for base_url in urls:
        for wl in wordlists:
            result = _run_cmd([
                FFUF_BIN,
                "-u", f"{base_url}/FUZZ",
                "-w", wl,
                "-json",
                "-mc", "200,201,204,301,302,307,308,401,403,405,500",
                "-t", "50",
                "-timeout", "10",
                "-s",
            ], timeout=120)

            if result["error"]:
                print(f"[_run_ffuf] failed on {base_url}: {result['error']}")
                continue

            for line in result["stdout"].splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    all_results.append({
                        "url": obj.get("url", ""),
                        "status": obj.get("status", 0),
                        "length": obj.get("length", 0),
                        "words": obj.get("words", 0),
                        "lines": obj.get("lines", 0),
                        "content_type": obj.get("content-type", ""),
                        "redirect": obj.get("redirectlocation", ""),
                        "base_url": base_url,
                        "wordlist": os.path.basename(wl),
                    })
                except json.JSONDecodeError:
                    continue

    # Clean up any generated temp wordlists
    for tf in temp_files_to_clean:
        try:
            os.unlink(tf)
        except OSError:
            pass

    print(f"[_run_ffuf] found {len(all_results)} potential paths")
    return all_results


def fuzz_layer(state: ReconState) -> dict:
    """Intent: Try every key on the keyring.
    Brute forces common directories, files, API endpoints, and
    backup files on all live hosts."""

    live = state.get("live_hosts", [])
    if not live:
        print("[fuzz_layer] no live hosts; skipping")
        return {
            "fuzz_results": [],
            "discovered_panels": [],
            "audit_log": [{
                "layer": "fuzz", "status": "skipped", "reason": "no_live_hosts"
            }]
        }

    urls = []
    for line in live:
        url = line.split(" [")[0] if " [" in line else line
        urls.append(url)

    plan = state.get("tool_plan", {}).get("fuzz", ["ffuf"])
    audit = []
    all_results = []
    panels = []

    for tool_name in plan:
        if tool_name == "ffuf":
            results = _run_ffuf(urls)
            if results:
                all_results.extend(results)
                # Identify admin panels, login pages, interesting endpoints
                panel_keywords = [
                    "admin", "login", "signin", "wp-admin", "dashboard",
                    "panel", "manage", "config", "setup", "install",
                    "api", "swagger", "graphql", "debug", "test",
                    "backup", ".env", ".git", "phpmyadmin", "webmail"
                ]
                for r in results:
                    path = urlparse(r["url"]).path.lower()
                    if any(kw in path for kw in panel_keywords):
                        panels.append(r)
                audit.append({
                    "tool": "ffuf",
                    "status": "success",
                    "results": len(results),
                    "panels": len(panels)
                })
            else:
                audit.append({"tool": "ffuf", "status": "failed_or_empty"})
        elif tool_name == "feroxbuster":
            audit.append({"tool": "feroxbuster", "status": "not_implemented"})
        else:
            audit.append({"tool": tool_name, "status": "unknown_tool"})

    print(f"[fuzz_layer] {len(all_results)} paths, {len(panels)} panels/login pages")

    return {
        "fuzz_results": all_results,
        "discovered_panels": panels,
        "audit_log": audit,
        "layer_results": {
            "fuzz": {
                "total_results": len(all_results),
                "panels_found": len(panels),
            }
        },
    }


# ── LAYER: SECRETS ─────────────────────────────────────────────────────

def _analyze_js_for_secrets(js_files: List[Dict]) -> List[Dict]:
    """Download and analyze JS files for API keys, tokens, endpoints."""
    secrets = []

    # Patterns for common secrets
    patterns = {
        "aws_access_key": r'AKIA[0-9A-Z]{16}',
        "aws_secret_key": r"[\"'][0-9a-zA-Z/+]{40}[\"']",
        "google_api_key": r'AIza[0-9A-Za-z_-]{35}',
        "slack_token": r'xox[baprs]-[0-9a-zA-Z]{10,48}',
        "github_token": r'ghp_[0-9a-zA-Z]{36}',
        "jwt_token": r'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*',
        "private_key": r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
        "api_key_generic": r"[\"']?[aA][pP][iI][-_]?[kK][eE][yY][\"']?\s*[:=]\s*[\"'][a-zA-Z0-9_-]{16,64}[\"']",
        "secret_generic": r"[\"']?[sS][eE][cC][rR][eE][tT][\"']?\s*[:=]\s*[\"'][a-zA-Z0-9_-]{8,64}[\"']",
        "password_in_js": r"[\"']?[pP][aA][sS][sS][wW][oO][rR][dD][\"']?\s*[:=]\s*[\"'][^\"']{4,}[\"']",
        "internal_ip": r'(?:10|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\.\d+\.\d+',
        "graphql_endpoint": r"[\"'](/graphql|/graphiql|/api/graphql)[\"']",
        "websocket_url": r"wss?://[^\s\"'<>]+",
        "firebase_url": r'https://[a-zA-Z0-9_-]+\.firebaseio\.com',
    }

    for js_file in js_files[:20]:  # Limit to first 20 to avoid timeout
        url = js_file.get("url", "")
        try:
            resp = requests.get(url, timeout=15, verify=False, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            content = resp.text

            for secret_type, pattern in patterns.items():
                matches = re.findall(pattern, content)
                for match in matches:
                    secrets.append({
                        "type": secret_type,
                        "match": match[:100] if len(match) > 100 else match,  # Truncate
                        "source": url,
                        "line": content[:500].count("\n") + 1,  # Approximate
                    })

            # Also look for fetch/XHR endpoints
            endpoint_pattern = r"(?:fetch|axios|\$\.ajax|XMLHttpRequest)\s*\(\s*[\"']([^\"']+)[\"']"
            for match in re.findall(endpoint_pattern, content):
                secrets.append({
                    "type": "api_endpoint_in_js",
                    "match": match,
                    "source": url,
                    "line": 0,
                })

        except Exception as e:
            print(f"[_analyze_js] failed on {url}: {e}")

    print(f"[_analyze_js] found {len(secrets)} potential secrets/leaks")
    return secrets


def _check_git_exposure(urls: List[str]) -> List[str]:
    """Check for exposed .git directories."""
    exposed = []
    git_paths = ["/.git/HEAD", "/.git/config", "/.git/index"]

    for base in urls[:10]:  # Limit to first 10
        for path in git_paths:
            try:
                url = base.rstrip("/") + path
                resp = requests.get(url, timeout=10, allow_redirects=False, verify=False)
                if resp.status_code == 200 and ("ref:" in resp.text or "[core]" in resp.text):
                    exposed.append(url)
                    break  # Found one, no need to check others
            except:
                continue

    print(f"[_check_git] found {len(exposed)} exposed .git directories")
    return exposed


def _check_env_files(urls: List[str]) -> List[str]:
    """Check for exposed .env files and config backups."""
    exposed = []
    env_paths = [
        "/.env", "/.env.local", "/.env.production", "/.env.development",
        "/config.php.bak", "/config.php~", "/.htaccess.bak",
        "/wp-config.php.bak", "/database.yml", "/settings.py",
    ]

    for base in urls[:10]:
        for path in env_paths:
            try:
                url = base.rstrip("/") + path
                resp = requests.get(url, timeout=10, allow_redirects=False, verify=False)
                if resp.status_code == 200:
                    # Check if it looks like an env file
                    content = resp.text.lower()
                    if any(kw in content for kw in ["=", "database", "password", "secret", "api_key"]):
                        exposed.append({
                            "url": url,
                            "size": len(resp.text),
                            "preview": resp.text[:200]
                        })
            except:
                continue

    print(f"[_check_env] found {len(exposed)} exposed config files")
    return exposed


def secrets_layer(state: ReconState) -> dict:
    """Intent: Look under the doormats and behind the paintings.
    Searches for exposed credentials, API keys, .git directories,
    .env files, and secrets embedded in JavaScript."""

    js_files = state.get("js_files", [])
    live = state.get("live_hosts", [])

    urls = []
    for line in live:
        url = line.split(" [")[0] if " [" in line else line
        urls.append(url)

    plan = state.get("tool_plan", {}).get("secrets", ["js_analysis", "git_check", "env_check"])
    audit = []
    secrets = []
    git_exposed = []
    env_files = []

    for tool_name in plan:
        if tool_name == "js_analysis":
            if js_files:
                found = _analyze_js_for_secrets(js_files)
                secrets.extend(found)
                audit.append({
                    "tool": "js_analysis",
                    "status": "success",
                    "secrets_found": len(found)
                })
            else:
                audit.append({"tool": "js_analysis", "status": "skipped", "reason": "no_js_files"})

        elif tool_name == "git_check":
            found = _check_git_exposure(urls)
            git_exposed.extend(found)
            audit.append({
                "tool": "git_check",
                "status": "success",
                "exposed": len(found)
            })

        elif tool_name == "env_check":
            found = _check_env_files(urls)
            env_files.extend(found)
            audit.append({
                "tool": "env_check",
                "status": "success",
                "exposed": len(found)
            })

        elif tool_name == "trufflehog":
            audit.append({"tool": "trufflehog", "status": "not_implemented"})
        else:
            audit.append({"tool": tool_name, "status": "unknown_tool"})

    print(f"[secrets_layer] {len(secrets)} secrets, {len(git_exposed)} git dirs, {len(env_files)} env files")

    return {
        "secrets_found": secrets,
        "git_exposed": git_exposed,
        "env_files": env_files,
        "audit_log": audit,
        "layer_results": {
            "secrets": {
                "secrets_found": len(secrets),
                "git_exposed": len(git_exposed),
                "env_files": len(env_files),
            }
        },
    }


# ── LAYER: DNS DEEP ────────────────────────────────────────────────────

def _run_dnsx(targets: List[str], query_type: str) -> List[Dict]:
    """Run dnsx for specific DNS record types."""
    if not targets:
        return []

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("\n".join(targets))
        target_path = f.name

    # Build flag based on query type
    type_flag = {
        "A": "-a", "AAAA": "-aaaa", "MX": "-mx", "NS": "-ns",
        "TXT": "-txt", "CNAME": "-cname", "PTR": "-ptr", "SOA": "-soa"
    }.get(query_type, "-a")

    try:
        result = _run_cmd([
            DNSX_BIN, "-l", target_path,
            "-resp", "-json", "-silent",
            "-retry", "3", "-timeout", "10",
            type_flag,
        ], timeout=180)

        if result["error"]:
            print(f"[_run_dnsx] failed: {result['error']}")
            return []

        records = []
        for line in result["stdout"].splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records
    finally:
        os.unlink(target_path)


def _check_spf_dkim_dmarc(domain: str) -> Dict:
    """Check email security records."""
    results = {}

    for record_type, prefix in [("TXT", "_dmarc."), ("TXT", "_domainkey.")]:
        try:
            import dns.resolver
            answers = dns.resolver.resolve(prefix + domain, 'TXT')
            results[prefix + domain] = [str(r) for r in answers]
        except:
            results[prefix + domain] = []

    # SPF check
    try:
        answers = dns.resolver.resolve(domain, 'TXT')
        spf_records = [str(r) for r in answers if 'v=spf1' in str(r)]
        results["spf"] = spf_records
    except:
        results["spf"] = []

    return results


def _run_tlsx(hosts: List[str]) -> List[Dict]:
    """Deep TLS analysis including historical certs."""
    if not hosts:
        return []

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("\n".join(hosts))
        host_path = f.name

    try:
        result = _run_cmd([
            TLSX_BIN,
            "-l", host_path,
            "-json",
            "-silent",
            "-san",
            "-cn",
            "-cipher",
            "-tls-version",
            "-expired",
            "-self-signed",
            "-hash", "sha256",
        ], timeout=180)

        if result["error"]:
            print(f"[_run_tlsx] failed: {result['error']}")
            return []

        certs = []
        for line in result["stdout"].splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                certs.append(obj)
            except json.JSONDecodeError:
                continue
        return certs
    finally:
        os.unlink(host_path)


def dns_deep_layer(state: ReconState) -> dict:
    """Intent: Check the building's foundation and utility connections.
    Deep DNS analysis: MX, NS, TXT, SPF, DMARC, DKIM, PTR records,
    certificate transparency, and TLS certificate history."""

    in_scope = state.get("in_scope_hosts", [])
    resolved_ips = state.get("resolved_ips", [])
    target = state.get("target", "")

    if not in_scope:
        print("[dns_deep_layer] no hosts; skipping")
        return {
            "dns_records": {},
            "ptr_records": {},
            "tls_history": [],
            "ct_logs": [],
            "audit_log": [{
                "layer": "dns_deep", "status": "skipped", "reason": "no_hosts"
            }]
        }

    plan = state.get("tool_plan", {}).get("dns_deep", ["dnsx", "tlsx", "email_security"])
    audit = []
    dns_records = {}
    ptr_records = {}
    tls_history = []
    ct_logs = []

    for tool_name in plan:
        if tool_name == "dnsx":
            for qtype in ["MX", "NS", "TXT", "CNAME", "SOA"]:
                records = _run_dnsx(in_scope[:20], qtype)  # Limit to first 20
                if records:
                    dns_records[qtype] = records

            # PTR records for IPs
            if resolved_ips:
                ptr = _run_dnsx(resolved_ips[:20], "PTR")
                for r in ptr:
                    ip = r.get("host", "")
                    ptr_name = r.get("response", "")
                    if ip and ptr_name:
                        ptr_records[ip] = ptr_name

            audit.append({
                "tool": "dnsx",
                "status": "success",
                "record_types": list(dns_records.keys()),
                "ptr_records": len(ptr_records)
            })

        elif tool_name == "tlsx":
            # Get unique hosts with TLS
            live = state.get("live_hosts", [])
            tls_hosts = []
            for line in live:
                url = line.split(" [")[0] if " [" in line else line
                parsed = urlparse(url)
                if parsed.scheme == "https":
                    tls_hosts.append(parsed.netloc)

            if tls_hosts:
                certs = _run_tlsx(list(set(tls_hosts))[:20])
                tls_history.extend(certs)
                audit.append({
                    "tool": "tlsx",
                    "status": "success",
                    "certs_analyzed": len(certs)
                })
            else:
                audit.append({"tool": "tlsx", "status": "skipped", "reason": "no_tls_hosts"})

        elif tool_name == "email_security":
            email_sec = _check_spf_dkim_dmarc(target)
            dns_records["email_security"] = email_sec
            audit.append({
                "tool": "email_security",
                "status": "success",
                "records_found": len(email_sec)
            })

        elif tool_name == "crtsh_deep":
            # Already done in discovery, but could do deeper CT log analysis
            audit.append({"tool": "crtsh_deep", "status": "not_implemented"})
        else:
            audit.append({"tool": tool_name, "status": "unknown_tool"})

    print(f"[dns_deep_layer] DNS: {len(dns_records)} types, PTR: {len(ptr_records)}, TLS: {len(tls_history)}")

    return {
        "dns_records": dns_records,
        "ptr_records": ptr_records,
        "tls_history": tls_history,
        "ct_logs": ct_logs,
        "audit_log": audit,
        "layer_results": {
            "dns_deep": {
                "dns_record_types": list(dns_records.keys()),
                "ptr_records": len(ptr_records),
                "tls_certs": len(tls_history),
                "email_records": len(dns_records.get("email_security", {})),
            }
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# EXISTING LAYER DISPATCHERS (unchanged logic, kept for completeness)
# ═══════════════════════════════════════════════════════════════════════

def extract_endpoints(state: ReconState) -> dict:
    live = state.get("live_hosts", [])
    if not live:
        print("[extract_endpoints] no live hosts; skipping")
        return {
            "endpoints": [],
            "audit_log": [{
                "layer": "extract_endpoints", "status": "skipped", "reason": "no_live_hosts"
            }]
        }

    all_endpoints = []
    audit = []

    for line in live:
        url = line.split(" [")[0] if " [" in line else line
        print(f"[extract_endpoints] fetching body from {url}")
        try:
            resp = requests.get(
                url, timeout=20, allow_redirects=True, verify=False,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            body = resp.text
            extracted = _extract_from_body(url, body)
            for ep in extracted:
                all_endpoints.append({
                    "url": ep["raw"],
                    "source": url,
                    "type": ep["type"],
                    "in_scope": is_in_scope(urlparse(ep["raw"]).netloc or "")
                })
            audit.append({
                "url": url,
                "status": "success",
                "endpoints_found": len(extracted),
                "response_size": len(body)
            })
        except Exception as e:
            print(f"[extract_endpoints] failed on {url}: {e}")
            audit.append({"url": url, "status": "failed", "error": str(e)})

    seen = set()
    deduped = []
    for ep in all_endpoints:
        if ep["url"] not in seen:
            seen.add(ep["url"])
            deduped.append(ep)

    print(f"[extract_endpoints] total unique endpoints: {len(deduped)}")

    return {
        "endpoints": deduped,
        "audit_log": audit,
        "layer_results": {
            "extract_endpoints": {
                "hosts_scanned": len(live),
                "unique_endpoints": len(deduped),
            }
        },
    }


def discovery_layer(state: ReconState) -> dict:
    target = state["target"]
    plan = state.get("tool_plan", {}).get("discovery", ["subfinder"])
    audit = []
    all_hosts = set()

    for tool_name in plan:
        found = []
        if tool_name == "subfinder":
            found = _run_subfinder(target)
        elif tool_name == "crtsh":
            found = _run_crtsh(target)
        else:
            audit.append({"tool": tool_name, "status": "unknown_tool"})
            continue

        if found:
            all_hosts.update(found)
            audit.append({"tool": tool_name, "found": len(found), "status": "success"})
        else:
            audit.append({"tool": tool_name, "found": 0, "status": "failed_or_empty"})

    if not all_hosts:
        all_hosts.add(target)
        audit.append({"fallback": "apex_domain", "value": target})

    return {
        "recon_output": sorted(all_hosts),
        "audit_log": audit,
        "layer_results": {
            "discovery": {
                "tools_attempted": len(plan),
                "unique_hosts_found": len(all_hosts),
            }
        },
    }


def filter_scope(state: ReconState) -> dict:
    discovered = state.get("recon_output", [])
    kept, dropped = [], []
    seen: Set[str] = set()

    for host in discovered:
        canonical = _canonicalize_domain(host)
        if not canonical:
            dropped.append(host)
            continue
        if canonical in seen:
            continue
        seen.add(canonical)

        if is_in_scope(canonical):
            kept.append(canonical)
        else:
            dropped.append(canonical)

    kept = sorted(kept)
    print(f"[filter_scope] CAF normalized: kept {len(kept)} in-scope, dropped {len(dropped)}")
    return {"in_scope_hosts": kept}


def resolution_layer(state: ReconState) -> dict:
    in_scope = state.get("in_scope_hosts", [])
    if not in_scope:
        return {
            "ip_map": {},
            "resolved_ips": [],
            "audit_log": [{"layer": "resolution", "status": "skipped"}]
        }

    # Primary: delegate to dnsx for fast, bulk A-record resolution
    print(f"[resolution_layer] delegating {len(in_scope)} hosts to dnsx")
    dnsx_records = _run_dnsx(in_scope, "A")

    ip_map: Dict[str, List[str]] = {host: [] for host in in_scope}
    for entry in dnsx_records:
        host = entry.get("host", "")
        # dnsx JSON schema varies by version: 'a' field or 'response' string
        raw_ips = entry.get("a") or entry.get("response", "")
        ips: List[str] = []
        if isinstance(raw_ips, list):
            ips = [str(i).strip() for i in raw_ips if i]
        elif isinstance(raw_ips, str):
            ips = [i.strip() for i in raw_ips.split(",") if i.strip()]
        if host in ip_map and ips:
            ip_map[host] = ips

    # Fallback: native socket only for hosts dnsx missed
    unresolved = [h for h, ips in ip_map.items() if not ips]
    for host in unresolved:
        try:
            addrs = socket.getaddrinfo(host, None)
            ips = list({addr[4][0] for addr in addrs})
            ip_map[host] = ips
        except Exception as e:
            print(f"[resolution_layer] socket fallback failed for {host}: {e}")
            ip_map[host] = []

    unique_ips = sorted({ip for ips in ip_map.values() for ip in ips})

    return {
        "ip_map": ip_map,
        "resolved_ips": unique_ips,
        "layer_results": {
            "resolution": {
                "hosts": len(in_scope),
                "unique_ips": len(unique_ips),
                "dnsx_resolved": len(in_scope) - len(unresolved),
                "socket_fallback": len(unresolved),
            },
        },
    }


def enumeration_layer(state: ReconState) -> dict:
    in_scope = state.get("in_scope_hosts", [])
    ips = state.get("resolved_ips", [])
    ip_map = state.get("ip_map", {})
    plan = state.get("tool_plan", {}).get("enumeration", ["httpx"])
    audit = []

    open_ports = []
    service_targets = []

    if "naabu" in plan and ips:
        naabu_ports = _run_naabu(ips)
        if naabu_ports:
            open_ports = naabu_ports
            ip_to_hosts = {}
            for host, host_ips in ip_map.items():
                for ip in host_ips:
                    ip_to_hosts.setdefault(ip, []).append(host)
            targets = []
            for entry in open_ports:
                ip = entry.get("ip", "")
                port = entry.get("port", "")
                for host in ip_to_hosts.get(ip, []):
                    targets.append(f"{host}:{port}")
            service_targets = sorted(set(targets))
            audit.append({"tool": "naabu", "status": "success", "ports": len(open_ports)})
        else:
            audit.append({"tool": "naabu", "status": "failed_or_empty"})

    live_hosts = []
    if "httpx" in plan and in_scope:
        live_hosts = _run_httpx(in_scope)
        audit.append({"tool": "httpx", "status": "success", "live": len(live_hosts)})

    return {
        "open_ports": open_ports,
        "service_targets": service_targets,
        "live_hosts": live_hosts,
        "audit_log": audit,
        "layer_results": {
            "enumeration": {"ports": len(open_ports), "live_hosts": len(live_hosts)},
        },
    }


def inspection_layer(state: ReconState) -> dict:
    live = state.get("live_hosts", [])
    if not live:
        return {
            "host_details": [],
            "audit_log": [{
                "layer": "inspection", "status": "skipped"
            }]
        }

    plan = state.get("tool_plan", {}).get("inspection", [])
    audit = []
    details = []
    urls = [line.split(" [")[0] if " [" in line else line for line in live]

    for tool_name in plan:
        if tool_name == "httpx_deep":
            found = _run_httpx_deep(urls)
            if found:
                details.extend(found)
                audit.append({"tool": "httpx_deep", "found": len(found), "status": "success"})
            else:
                audit.append({"tool": "httpx_deep", "status": "failed_or_empty"})
        else:
            audit.append({"tool": tool_name, "status": "unknown_tool"})

    return {
        "host_details": details,
        "audit_log": audit,
        "layer_results": {
            "inspection": {"hosts_enriched": len(details)},
        },
    }


def propose_target(state: ReconState) -> dict:
    target = "bahria.edu.pk"
    print(f"[propose_target] proposing: {target}")
    return {"target": target}


def scope_gate(state: ReconState) -> dict:
    target = state["target"]
    decision = "ALLOWED" if is_in_scope(target) else "DENIED"
    print(f"[scope_gate] {target} -> {decision}")
    return {"scope_decision": decision}


def route_after_gate(state: ReconState) -> str:
    return "discovery_layer" if state["scope_decision"] == "ALLOWED" else END


# ═══════════════════════════════════════════════════════════════════════
# GRAPH WIRING
# ═══════════════════════════════════════════════════════════════════════

builder = StateGraph(ReconState)

# Existing nodes
builder.add_node("propose_target", propose_target)
builder.add_node("scope_gate", scope_gate)
builder.add_node("discovery_layer", discovery_layer)
builder.add_node("filter_scope", filter_scope)
builder.add_node("resolution_layer", resolution_layer)
builder.add_node("enumeration_layer", enumeration_layer)
builder.add_node("inspection_layer", inspection_layer)
builder.add_node("extract_endpoints", extract_endpoints)

# NEW nodes
builder.add_node("crawl_layer", crawl_layer)
builder.add_node("fuzz_layer", fuzz_layer)
builder.add_node("secrets_layer", secrets_layer)
builder.add_node("dns_deep_layer", dns_deep_layer)

# Edges
builder.add_edge(START, "propose_target")
builder.add_edge("propose_target", "scope_gate")
builder.add_conditional_edges("scope_gate", route_after_gate)
builder.add_edge("discovery_layer", "filter_scope")
builder.add_edge("filter_scope", "resolution_layer")
builder.add_edge("resolution_layer", "enumeration_layer")
builder.add_edge("enumeration_layer", "inspection_layer")
builder.add_edge("inspection_layer", "extract_endpoints")

# NEW: Parallel deep exploration after endpoint extraction
builder.add_edge("extract_endpoints", "crawl_layer")
builder.add_edge("extract_endpoints", "fuzz_layer")
builder.add_edge("extract_endpoints", "secrets_layer")
builder.add_edge("extract_endpoints", "dns_deep_layer")

# All new layers converge to END
builder.add_edge("crawl_layer", END)
builder.add_edge("fuzz_layer", END)
builder.add_edge("secrets_layer", END)
builder.add_edge("dns_deep_layer", END)

graph = builder.compile()


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    TOOL_PLAN = {
        "discovery": ["subfinder", "crtsh"],
        "enumeration": ["naabu", "httpx"],
        "inspection": ["httpx_deep"],
        "crawl": ["katana"],
        "fuzz": ["ffuf"],
        "secrets": ["js_analysis", "git_check", "env_check"],
        "dns_deep": ["dnsx", "tlsx", "email_security"]
    }

    final = graph.invoke({
        "target": "",
        "scope_decision": "",
        "recon_output": [],
        "in_scope_hosts": [],
        "live_hosts": [],
        "ip_map": {},
        "resolved_ips": [],
        "open_ports": [],
        "service_targets": [],
        "host_details": [],
        "endpoints": [],
        "crawled_endpoints": [],
        "forms": [],
        "js_files": [],
        "fuzz_results": [],
        "discovered_panels": [],
        "secrets_found": [],
        "git_exposed": [],
        "env_files": [],
        "dns_records": {},
        "ptr_records": {},
        "tls_history": [],
        "ct_logs": [],
        "tool_plan": TOOL_PLAN,
        "audit_log": [],
        "layer_results": {}
    })

    print("\n" + "=" * 60)
    print("[FINAL STATE - DEEP RECON COMPLETE]")
    print("=" * 60)
    print(json.dumps(final, indent=2))