import requests

def bgpview_ip_lookup(ip_address):
    """
    Looks up the ASN and network info for a given IP.
    """
    url = f"https://api.bgpview.io/ip/{ip_address}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def bgpview_asn_lookup(asn):
    """
    Looks up the prefixes (network ranges) for a given ASN.
    """
    url = f"https://api.bgpview.io/asn/{asn}/prefixes"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

# Example usage
ip_info = bgpview_ip_lookup("8.8.8.8")
print(f"ASN for 8.8.8.8: AS{ip_info['data']['asns'][0]['asn']}")

asn_info = bgpview_asn_lookup(32934)
print(f"Prefixes for AS32934: {[p['prefix'] for p in asn_info['data']['ipv4_prefixes']]}")