from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, START, END
import subprocess
import json
import os
import requests
import socket
import tempfile

HTTPX_BIN = os.path.join(os.environ["USERPROFILE"], "go", "bin", "httpx.exe")
NAABU_BIN = os.path.join(os.environ["USERPROFILE"], "go", "bin", "naabu.exe")

# ── Scope gate (unchanged) ────────────────────────────────────────────
IN_SCOPE = ["qbsco.net"]

def is_in_scope(domain: str) -> bool:
    domain = domain.strip().lower().rstrip(".")
    for allowed in IN_SCOPE:
        if domain == allowed or domain.endswith("." + allowed):
            return True
    return False


# ── State: extended with IP/port layer fields ─────────────────────────
class ReconState(TypedDict):
    target: str
    scope_decision: str
    recon_output: List[str]          # all discovered hosts (passive)
    in_scope_hosts: List[str]        # hosts that passed the re-gate
    live_hosts: List[str]            # httpx-confirmed live web servers
    ip_map: Dict[str, List[str]]     # host → [ip1, ip2, ...]
    resolved_ips: List[str]          # unique IPs for scanning
    open_ports: List[Dict]           # [{"ip":..., "port":..., "protocol":...}]
    service_targets: List[str]       # "host:port" strings for discovered services


# ── Existing nodes ────────────────────────────────────────────────────
def propose_target(state: ReconState) -> dict:
    target = "qbsco.net"
    print(f"[propose_target] proposing: {target}")
    return {"target": target}

def scope_gate(state: ReconState) -> dict:
    target = state["target"]
    decision = "ALLOWED" if is_in_scope(target) else "DENIED"
    print(f"[scope_gate] {target} → {decision}")
    return {"scope_decision": decision}

def run_recon(state: ReconState) -> dict:
    target = state["target"]
    print(f"[run_recon] running subfinder on {target}")
    try:
        result = subprocess.run(
            ["subfinder", "-d", target, "-silent", "-oJ"],
            capture_output=True, text=True, timeout=120, check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"[run_recon] subfinder timed out"); return {"recon_output": []}
    except FileNotFoundError:
        print("[run_recon] subfinder not on PATH"); return {"recon_output": []}
    if result.returncode != 0:
        print(f"[run_recon] subfinder exited {result.returncode}"); return {"recon_output": []}

    hosts = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            host = json.loads(line).get("host")
            if host:
                hosts.append(host)
        except json.JSONDecodeError:
            continue
    print(f"[run_recon] found {len(hosts)} subdomains")
    return {"recon_output": hosts}


# ── FIXED: crt.sh passive subdomain enrichment ─────────────────────────
def run_crtsh(state: ReconState) -> dict:
    target = state["target"]
    # FIX: Use %. instead of %25. — crt.sh expects raw % as wildcard
    url = f"https://crt.sh/?q=%.{target}&output=json"
    discovered = set()

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        entries = resp.json()
        for entry in entries:
            for key in ("common_name", "name_value"):
                val = entry.get(key, "")
                # one entry can have multiple domains separated by newline
                for name in val.split("\n"):
                    name = name.strip().lower().rstrip(".")
                    if name and name.endswith(target):   # also catches the apex
                        discovered.add(name)
    except Exception as e:
        print(f"[run_crtsh] error (non-fatal): {e}")

    # Merge with existing subfinder results
    existing = set(h.lower().rstrip(".") for h in state.get("recon_output", []))
    combined = list(existing | discovered)
    print(f"[run_crtsh] added {len(discovered)} hosts, total {len(combined)}")
    return {"recon_output": combined}


# ── NEW: filter / re-gate the combined discoveries ───────────────────
def filter_scope(state: ReconState) -> dict:
    discovered = state["recon_output"]
    kept, dropped = [], []
    for host in discovered:
        (kept if is_in_scope(host) else dropped).append(host)

    # deduplicate (just in case)
    kept = list(set(kept))
    print(f"[filter_scope] kept {len(kept)} in-scope, dropped {len(dropped)}")
    if dropped:
        print(f"[filter_scope] dropped (out-of-scope): {dropped}")
    return {"in_scope_hosts": kept}


# ── NEW: resolve in-scope hosts to IPs ───────────────────────────────
def resolve_ips(state: ReconState) -> dict:
    in_scope = state["in_scope_hosts"]
    ip_map = {}
    for host in in_scope:
        try:
            addrs = socket.getaddrinfo(host, None)
            ips = list({addr[4][0] for addr in addrs})
            ip_map[host] = ips
        except Exception as e:
            print(f"[resolve_ips] could not resolve {host}: {e}")
            ip_map[host] = []

    unique_ips = sorted({ip for ips in ip_map.values() for ip in ips})
    print(f"[resolve_ips] resolved {len(in_scope)} hosts → {len(unique_ips)} unique IPs")
    return {
        "ip_map": ip_map,
        "resolved_ips": unique_ips
    }


# ── FIXED: run naabu (port scan) on resolved IPs ───────────────────────
def run_naabu(state: ReconState, timeout: int = 300) -> dict:
    ips = state.get("resolved_ips", [])
    if not ips:
        print("[run_naabu] no IPs to scan")
        return {"open_ports": []}

    # Write IPs to a temp file (naabu -list reads from file)
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("\n".join(ips))
        ip_list_path = f.name

    try:
        args = [
            NAABU_BIN,
            "-list", ip_list_path,
            "-json",              # output JSON lines
            "-silent",
            "-top-ports", "1000", # scan top 1000 ports
            "-rate", "3000",      # adjust for your bandwidth
            "-scan-type", "c",    # full connect scan – no admin required on Windows
        ]
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)

        if result.returncode != 0:
            print(f"[run_naabu] naabu exited with code {result.returncode}: {result.stderr}")
            return {"open_ports": []}

        open_ports = []
        for line in result.stdout.strip().splitlines():
            try:
                entry = json.loads(line)
                # FIX: naabu uses "ip" not "host" — use .get() with fallback for safety
                ip = entry.get("ip") or entry.get("host", "UNKNOWN")
                open_ports.append({
                    "ip": ip,
                    "port": entry["port"],
                    "protocol": entry.get("protocol", "tcp")
                })
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[run_naabu] skipping malformed line: {line[:80]}... ({e})")
                continue

        print(f"[run_naabu] found {len(open_ports)} open ports across {len(ips)} IPs")
        return {"open_ports": open_ports}
    except subprocess.TimeoutExpired:
        print("[run_naabu] timeout expired")
        return {"open_ports": []}
    except FileNotFoundError:
        print(f"[run_naabu] binary not found at {NAABU_BIN}")
        return {"open_ports": []}
    finally:
        os.unlink(ip_list_path)


# ── NEW: map open ports back to hostnames ─────────────────────────────
def map_ports_to_hosts(state: ReconState) -> dict:
    ip_map = state.get("ip_map", {})
    open_ports = state.get("open_ports", [])

    # Build reverse IP → hostnames list
    ip_to_hosts: Dict[str, List[str]] = {}
    for host, ips in ip_map.items():
        for ip in ips:
            ip_to_hosts.setdefault(ip, []).append(host)

    service_targets = []
    for entry in open_ports:
        ip = entry["ip"]
        port = entry["port"]
        for host in ip_to_hosts.get(ip, []):
            service_targets.append(f"{host}:{port}")

    service_targets = sorted(set(service_targets))
    print(f"[map_ports] {len(service_targets)} unique service targets")
    return {"service_targets": service_targets}


# ── Existing: httpx (now after port mapping, but still probes all in‑scope hosts) ──
def run_httpx(state: ReconState) -> dict:
    hosts = state["in_scope_hosts"]
    if not hosts:
        print("[run_httpx] no in-scope hosts to probe")
        return {"live_hosts": []}

    print(f"[run_httpx] probing {len(hosts)} hosts")
    try:
        result = subprocess.run(
            [HTTPX_BIN, "-silent", "-json", "-sc", "-title"],
            input="\n".join(hosts),
            capture_output=True, text=True, timeout=180, check=False,
        )
    except subprocess.TimeoutExpired:
        print("[run_httpx] httpx timed out"); return {"live_hosts": []}
    except FileNotFoundError:
        print("[run_httpx] httpx not on PATH"); return {"live_hosts": []}
    if result.returncode != 0:
        print(f"[run_httpx] httpx exited {result.returncode}")
        print(f"[run_httpx] STDERR: {result.stderr.strip()}")
        print(f"[run_httpx] STDOUT: {result.stdout.strip()}")
        return {"live_hosts": []}

    live = []
    for line in result.stdout.splitlines():
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
    print(f"[run_httpx] {len(live)} live web servers")
    return {"live_hosts": live}


# ── Routing ───────────────────────────────────────────────────────────
def route_after_gate(state: ReconState) -> str:
    return "run_recon" if state["scope_decision"] == "ALLOWED" else END


# ── Wiring ────────────────────────────────────────────────────────────
builder = StateGraph(ReconState)

builder.add_node("propose_target", propose_target)
builder.add_node("scope_gate", scope_gate)
builder.add_node("run_recon", run_recon)
builder.add_node("run_crtsh", run_crtsh)
builder.add_node("filter_scope", filter_scope)
builder.add_node("resolve_ips", resolve_ips)
builder.add_node("run_naabu", run_naabu)
builder.add_node("map_ports_to_hosts", map_ports_to_hosts)
builder.add_node("run_httpx", run_httpx)

builder.add_edge(START, "propose_target")
builder.add_edge("propose_target", "scope_gate")
builder.add_conditional_edges("scope_gate", route_after_gate)
builder.add_edge("run_recon", "run_crtsh")
builder.add_edge("run_crtsh", "filter_scope")
builder.add_edge("filter_scope", "resolve_ips")
builder.add_edge("resolve_ips", "run_naabu")
builder.add_edge("run_naabu", "map_ports_to_hosts")
builder.add_edge("map_ports_to_hosts", "run_httpx")
builder.add_edge("run_httpx", END)

graph = builder.compile()


if __name__ == "__main__":
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
    })
    print("\n[final state]")
    print(json.dumps(final, indent=2))