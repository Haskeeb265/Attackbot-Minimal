from .passive_skill import skill_passive
from .active_skill import skill_active
from config import SKILLS

_PASSIVE_DESCRIPTION = """\
Run passive reconnaissance — ZERO direct probes to the target. Safe at any time.
Substitute <target> with the Target scope from the mission context.
Prefer -silent / line-based stdout so output parses cleanly. One command per action (pipes OK).

Tools and command templates:

1. subfinder — passive subdomain enumeration
   subfinder -d <target> -silent

2. amass (passive mode) — OSINT subdomain enumeration
   amass enum -passive -d <target> -silent

3. crt.sh — certificate transparency subdomain discovery
   curl -s "https://crt.sh/?q=%25.<target>&output=json" | jq -r ".[].name_value" | sed "s/\\*\\.//g" | sort -u

4. SecurityTrails — subdomain lookup (requires SECURITYTRAILS_API_KEY in env)
   curl -s -H "APIKEY: $SECURITYTRAILS_API_KEY" "https://api.securitytrails.com/v1/domain/<target>/subdomains" | jq -r ".subdomains[]" | sed "s/$/.<target>/" | sort -u

5. Shodan CLI — domain info and subdomains (requires shodan init / SHODAN_API_KEY)
   shodan domain <target>
   shodan search ssl.cert.subject.cn:<target> --fields ip_str,port,hostnames --separator ,

6. waybackurls — historical URLs from Wayback Machine (indirect; no direct target probe)
   echo <target> | waybackurls

7. gau (GetAllUrls) — known URLs/subdomains from archives and datasets
   gau --subs <target>
   gau <target> --threads 5

General guidance:
- Run multiple passive sources and merge/dedupe later (Code skill).
- If a tool is not installed, pick another source or retry with a fallback.
- Do not use Active skill tools here.
"""

_ACTIVE_DESCRIPTION = """\
Run active reconnaissance — sends probes DIRECTLY to the target.
Use ONLY after Passive enumeration is complete.
Substitute <target> with the Target scope. Use <subs_file> for a line-delimited subdomain list
(e.g. /tmp/subs.txt) — write it first via the Code skill from results["passive"] if needed.
Prefer -silent flags. One command per action (pipes OK).

Tools and command templates:

1. dnsx — DNS resolution and record enumeration
   dnsx -l <subs_file> -a -aaaa -cname -mx -resp -silent
   echo <target> | dnsx -a -aaaa -cname -resp -silent
   subfinder -d <target> -silent | dnsx -a -resp -silent

2. httpx — HTTP/HTTPS probing of live web services
   httpx -l <subs_file> -silent -status-code -title -tech-detect -follow-redirects
   cat <subs_file> | httpx -silent -status-code -title -ip
   echo https://<target> | httpx -silent -status-code -title

3. naabu — fast port scanning
   naabu -host <target> -silent
   naabu -list <subs_file> -top-ports 1000 -silent
   subfinder -d <target> -silent | naabu -silent -top-ports 100

4. nmap — detailed port and service enumeration (slower; use on high-value hosts)
   nmap -sV -sC -T4 --open -oN /tmp/nmap_<target>.txt <target>
   nmap -sV -p 80,443,8080,8443 --open <target>

5. shuffledns — DNS brute-force subdomain discovery (requires wordlist, e.g. /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt)
   shuffledns -d <target> -w /path/to/wordlist.txt -r 8.8.8.8,1.1.1.1 -silent

6. nuclei — vulnerability and misconfiguration scanning
   httpx -l <subs_file> -silent | nuclei -silent -severity low,medium,high,critical
   nuclei -u https://<target> -silent -tags exposure,misconfig

7. subzy — subdomain takeover detection
   subfinder -d <target> -silent | subzy run --targets /dev/stdin --concurrency 50 --hide_fails
   subzy run --targets <subs_file> --concurrency 50 --hide_fails

General guidance:
- Typical flow: resolve with dnsx → probe with httpx → scan with nuclei on live URLs.
- Write <subs_file> from accumulated passive results before bulk active scans.
- If a tool is not installed, pick an alternative or narrower command.
- Do not run shuffledns/nmap until passive enumeration has been attempted.
"""

# Register skills
SKILLS.update({
    "Passive": {
        "description": _PASSIVE_DESCRIPTION,
        "executor": skill_passive,
    },
    "Active": {
        "description": _ACTIVE_DESCRIPTION,
        "executor": skill_active,
    },
    "Code": {
        "description": (
            "Execute Python code for data processing: deduplication, filtering, "
            "sorting, merging lists, pattern extraction, writing files. "
            "The 'results' dict contains all data collected so far. "
            "Set variable 'output' to expose a summary to the scratchpad."
        ),
        "executor": lambda action, results: (None, None),  # Placeholder, implement in code_skill.py if needed
    },
    "Finish": {
        "description": (
            "Task is complete. All goals are in CONFIRMED state (no EXECUTION_FAILED). "
            "Write a final summary of all findings. This stops the agent."
        ),
        "executor": lambda action, results: (None, None),  # Placeholder, implement in finish_skill.py if needed
    },
})