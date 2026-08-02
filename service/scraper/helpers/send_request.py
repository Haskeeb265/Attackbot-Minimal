import requests
from config import HACKERONE_BASE_URL, HACKERONE_AUTH


class SendRequest:

    @staticmethod
    def send_request(url):
        r = requests.get(
            f"{HACKERONE_BASE_URL}{url}",
            auth=HACKERONE_AUTH
        )
        r.raise_for_status()  # For status_code errors. If not included, program might keep running even on unauthorized request (no results)
        return r.json()