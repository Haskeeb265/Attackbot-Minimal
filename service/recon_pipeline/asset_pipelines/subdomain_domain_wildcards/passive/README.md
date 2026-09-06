# Passive Subdomain Enumeration

Passive stage of the `subdomain_domain_wildcards` pipeline: enumerates subdomains of the
configured target using OSINT / certificate-transparency sources only (no DNS queries are
sent to the target's nameservers beyond normal lookups, no direct contact with target
infrastructure). Results feed the `active/` and `permutation/` stages.

All tools run via **Docker** — nothing but Python + Docker is needed on the host.

## Layout

```
passive/
├── README.md            <- this file
├── __init__.py
├── subfinder.py         -> output/subfinder.txt    (workhorse, 30+ sources)
├── assetfinder.py       -> output/assetfinder.txt  (7 CT/web sources)
├── findomain.py         -> output/findomain.txt    (54 CT/API sources)
├── chaos-client.py      -> output/chaos.txt        (ProjectDiscovery Chaos dataset)
├── amass.py             -> output/amass.txt        (graph relations, see below)
│                           output/amass.log        (amass stderr)
├── config/              (gitignored — contains API keys)
│   ├── config.yaml      amass entry config; references datasources.yaml by ABSOLUTE path
│   └── datasources.yaml amass API keys (Shodan, Censys, VirusTotal, SecurityTrails, Chaos, GitHub)
└── output/              per-tool result files + logs (each run overwrites)
```

## Requirements

- **Docker running.** Images are pulled on first use:
  - `projectdiscovery/subfinder:v2.14.0`
  - `lotuseatersec/assetfinder:latest`
  - `edu4rdshl/findomain:latest`
  - `projectdiscovery/chaos-client:latest`
  - `caffix/amass` (v4.2.0 — pinned, see `../Dockerfile` header for why)
- Python 3 with `python-dotenv` (used by `../config.py`).
- Project root `.env` with `TARGET=<domain>` and the recon tool keys
  (`CHAOS_KEY`, `GITHUB_KEY`, ...). See *Amass configuration* below.

## Target configuration

The target comes from `service/recon_pipeline/asset_pipelines/config.py`:

- `.env` `TARGET=...` takes precedence,
- fallback default is `qbsco.net`.

Every tool's `run(domain: str = TARGET)` also accepts an explicit domain argument,
e.g. `subfinder.run("example.com")`.

> **Watch out:** a stale `TARGET` in `.env` makes every tool silently enumerate the
> wrong domain (this bit us once — outputs contained google.com data while the code
> said qbsco.net). Check `grep '^TARGET' .env` before trusting any results.

## Running

Run each tool as a module **from the project root** (imports are absolute):

```bash
python -m service.recon_pipeline.asset_pipelines.subdomain_domain_wildcards.passive.subfinder
python -m service.recon_pipeline.asset_pipelines.subdomain_domain_wildcards.passive.assetfinder
python -m service.recon_pipeline.asset_pipelines.subdomain_domain_wildcards.passive.findomain
python -m service.recon_pipeline.asset_pipelines.subdomain_domain_wildcards.passive.chaos-client
python -m service.recon_pipeline.asset_pipelines.subdomain_domain_wildcards.passive.amass
```

Verified runtimes and yields against `qbsco.net` (2026-09-06):

| Tool | Typical runtime | Yield on qbsco.net | Notes |
|---|---|---|---|
| subfinder | ~10 s | 10 subs | most reliable plain-list source |
| assetfinder | ~10 s | 4 subs + apex | includes the apex domain |
| findomain | ~75 s | 1 sub + apex | includes the apex domain |
| chaos | ~5 s | 12 subs | empty output = domain not in dataset (not an error) |
| amass | 1–5+ min | graph relations | relations stream to stdout at the end; see below |

Output files always land in `passive/output/` regardless of cwd, and are overwritten
on each run.

## Amass notes

`amass.py` mounts `config/` read-only at `/home/user/.config/amass` inside the container
and passes `-config /home/user/.config/amass/config.yaml`.

**Critical:** `config/config.yaml` must reference the datasources file by **absolute
container path**:

```yaml
options:
  datasources: "/home/user/.config/amass/datasources.yaml"
```

amass resolves the path relative to its **own working directory** (`/` in the
`caffix/amass` image), not relative to the config file. A bare `datasources.yaml`
fails *silently* — the run exits 0 and outputs only keyless-source data (3 sources
instead of ~50, missing MX/A-record relations). Symptom: verbose output lists only
keyless sources (Sublist3rAPI, RapidDNS, PKey...).

Sanity check that sources load (expect ~50 "Querying ..." lines):

```bash
# from the project root — verified on Git Bash / Windows
MSYS_NO_PATHCONV=1 docker run --rm --dns 8.8.8.8 --dns 1.1.1.1 \
  -v "$(pwd -W)/service/recon_pipeline/asset_pipelines/subdomain_domain_wildcards/passive/config:/home/user/.config/amass:ro" \
  --entrypoint /bin/sh caffix/amass -c "ls /home/user/.config/amass/"
```

For a fast verbose enumeration (3-minute cap) to inspect which sources are queried:

```bash
MSYS_NO_PATHCONV=1 docker run --rm --dns 8.8.8.8 --dns 1.1.1.1 \
  -v "$(pwd -W)/service/recon_pipeline/asset_pipelines/subdomain_domain_wildcards/passive/config:/home/user/.config/amass:ro" \
  caffix/amass enum -config /home/user/.config/amass/config.yaml \
  -passive -nocolor -v -d qbsco.net -timeout 3
```

On macOS/Linux, `$(pwd -W)` is just `$(pwd)`; without Git Bash, `MSYS_NO_PATHCONV=1` is unnecessary.

`amass.txt` holds one graph relation per line, e.g.:

```
qbsco.net (FQDN) --> mx_record --> qbsco-net.mail.protection.outlook.com (FQDN)
autodiscover.qbsco.net (FQDN) --> cname_record --> autodiscover.outlook.com (FQDN)
```

amass v4 is intentionally thin on subdomains for small targets; the other four tools
cover subdomain discovery. The value here is DNS/MX/ASN relations.

The `caffix/amass` image's entrypoint is `/bin/amass` — any ad-hoc command needs
`--entrypoint /bin/sh` and `MSYS_NO_PATHCONV=1` on Git Bash (see Troubleshooting).

## Testing / verification

1. **Exit codes** — every script raises on failure (`check=True`); a clean run prints
   its `* results saved to:` line via `python -m` / `__main__`.
2. **Leakage check** — no output line should contain a foreign domain:

   ```bash
   cd service/recon_pipeline/asset_pipelines/subdomain_domain_wildcards/passive/output
   grep -vE '(^|[[:space:]])[a-z0-9._-]*qbsco\.net' subfinder.txt assetfinder.txt findomain.txt chaos.txt
   ```

3. **Ground-truth cross-check** against crt.sh (certificate transparency):

   ```bash
   curl -s --max-time 60 "https://crt.sh/?q=%25.qbsco.net&output=json" \
     | python -c "import json,sys; d=json.load(sys.stdin); names=set(); [names.update(n['name_value'].split('\n')) for n in d]; print(sorted(names))"
   ```

   The union of all five outputs should be a superset of (and for qbsco.net matched
   exactly) the crt.sh name list.

4. **Liveness check** — passive lists contain historical entries that no longer
   resolve; that is expected. Resolve candidates before acting on them:

   ```python
   import socket
   try:
       print(socket.gethostbyname("www.qbsco.net"))
   except OSError:
       ...
   ```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Tool call hangs / container outlives the caller | Kill the orphan: `docker rm -f $(docker ps -q --filter ancestor=<image>)`. Docker containers survive the process that launched them. |
| amass output too thin, only 2–3 relations | `config.yaml` datasources path — must be absolute (see *Amass notes*). |
| `exec: "C:/Program Files/Git/usr/bin/sh"` from Git Bash | Git Bash mangles absolute container paths. Prefix the command with `MSYS_NO_PATHCONV=1`. |
| chaos.txt empty | Domain not in the Chaos dataset (exit 0, not an error). Verify the key works against a known-populated domain, e.g. `hackerone.com`. |
| Results show the wrong domain | Stale `TARGET` in `.env` — see *Target configuration*. |
| `-v "$PWD:/workspace"` fails to mount on Windows | Use `-v "$(pwd -W):/workspace"` (Git Bash) or `MSYS_NO_PATHCONV=1`. |

## Related

- `../commands.txt` — raw per-tool docker commands for the all-in-one
  `subdomain_domain_wildcards_image` (built from `../Dockerfile`), active &
  permutation stages, and one-liner chains.
- `../active/`, `../permutation/` — downstream stages consuming these outputs.
