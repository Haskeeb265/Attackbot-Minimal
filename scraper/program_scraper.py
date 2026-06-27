import requests
import config
import json

class ProgramScraper:
    

    # ============================================================
    # High Priority Handle Scraper
    # ============================================================
    def high_priority_handle_scraping(self):
        high_priority_handles = []
        r = requests.get(
            f"{config.BASE}/hackers/programs",
            auth = config.AUTH
            )

        r.raise_for_status() # For status_code errors. If not included, program might keep running even on unauthorized request (no results)
        data = r.json()

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
        r = requests.get(
            f"{config.BASE}/hackers/programs",
            auth = config.AUTH
            )

        r.raise_for_status() # For status_code errors. If not included, program might keep running even on unauthorized request (no results)
        data = r.json()

        for program in data["data"]:
            attrs = program["attributes"]

            if (attrs["offers_bounties"] and not(attrs["open_scope"] and attrs["gold_standard_safe_harbor"])):
                low_priority_handles.append(attrs["handle"])

        return low_priority_handles    



# ============================================================
# MAIN
# ============================================================
# handle_scraper = Program_Scraper()
# high_priority_handle_data = handle_scraper.high_priority_handle_scraping()
# low_priority_handle_data = handle_scraper.low_priority_handle_scraping()

# print("High"+high_priority_handle_data)
# print(low_priority_handle_data)