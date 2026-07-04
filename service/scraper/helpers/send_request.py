import requests
import config
import json

class SendRequest:
    
    @staticmethod
    def send_request(url):
        r = requests.get(
            f"{config.BASE}{url}",
            auth = config.AUTH
        )

        r.raise_for_status() # For status_code errors. If not included, program might keep running even on unauthorized request (no results)
        return r.json()