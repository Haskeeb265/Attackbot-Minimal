import whois          # pip install python-whois
import json
from datetime import datetime

def serialize(obj):
    """Make non-JSON-serialisable types printable."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, list):
        return [serialize(i) for i in obj]
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    return str(obj)

def whois_lookup(domain):
    """Perform a WHOIS/RDAP lookup using python-whois."""
    try:
        w = whois.whois(domain)
        return {"status": "success", "data": dict(w)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Example usage
if __name__ == "__main__":
    domain = "google.com"
    result = whois_lookup(domain)
    print(json.dumps(result, indent=2, default=serialize))