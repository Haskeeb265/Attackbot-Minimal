import requests
import config
import json
from helpers.send_request import SendRequest


class ProgramScraper:

    # ============================================================
    # High Priority Handle Scraper
    # ============================================================
    def high_priority_handle_scraping(self):
        high_priority_handles = []
        data = SendRequest.send_request("hackers/programs")

        for program in data["data"]:
            attrs = program["attributes"]

            if (attrs["submission_state"] in {"open", "paused", "disabled"} and attrs["offers_bounties"] and attrs["open_scope"] and attrs["gold_standard_safe_harbor"]):
                high_priority_handles.append(attrs["handle"])
    
        return high_priority_handles


    # ============================================================
    # Low Priority Handle Scraper
    # ============================================================
    def low_priority_handle_scraping(self):
        low_priority_handles = []
        data = SendRequest.send_request("hackers/programs")

        for program in data["data"]:
            attrs = program["attributes"]

            if (attrs["offers_bounties"] and not(attrs["open_scope"] and attrs["gold_standard_safe_harbor"])):
                low_priority_handles.append(attrs["handle"])

        return low_priority_handles    



# ============================================================
# MAIN
# ============================================================
# handle_scraper = ProgramScraper()
# high_priority_handle_data = handle_scraper.high_priority_handle_scraping()
# low_priority_handle_data = handle_scraper.low_priority_handle_scraping()

# print("High", high_priority_handle_data)
# print("Low", low_priority_handle_data)