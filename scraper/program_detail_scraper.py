import config
import requests
import json
from program_scraper import ProgramScraper
from helpers.send_request import SendRequest

class ProgramDetailScraper:

    def high_priority_handle_detail_scraping():
        Scraper = ProgramScraper()
        handles = Scraper.high_priority_handle_scraping()
        all_data = []

        for handle in handles:
            r = requests.get(
                f"{config.BASE}/hackers/programs/{handle}/structured_scopes",
                auth = config.AUTH
                )
            r.raise_for_status()
            all_data.append(r.json())

        return all_data


    
    
    def low_priority_handle_detail_scraping():
        Scraper = ProgramScraper()
        handles = Scraper.low_priority_handle_scraping()
        all_data = []

        for handle in handles:
            r = requests.get(
                f"{config.BASE}/hackers/programs/{handle}/structured_scopes",
                auth = config.AUTH
                )
            r.raise_for_status()
            all_data.append(r.json())

        return all_data




high_function = ProgramDetailScraper.high_priority_handle_detail_scraping()
low_function = ProgramDetailScraper.low_priority_handle_detail_scraping()

# ============================================================
# Save Results
# ============================================================

with open("high_priority_details.json", "w") as f:
    json.dump(high_function, f, indent=4)

with open("low_priority_details.json", "w") as f:
    json.dump(low_function, f, indent=4)

# print("High Detail:", high_function)
# print("Low Detail:", low_function)
