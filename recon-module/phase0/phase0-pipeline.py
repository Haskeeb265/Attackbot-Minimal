import whois
import json

domain = "example.com"
data = whois.whois(domain)
print(json.dumps(dict(data), default=str, indent=2))