import config
import json
from program_scraper import ProgramScraper
from helpers.send_request import SendRequest


class ProgramDetailScraper:

    @staticmethod
    def _flatten_scope(scope):
        attrs = scope.get('attributes', {})
        return {
            'id': scope.get('id'),
            'asset_type': attrs.get('asset_type'),
            'asset_identifier': attrs.get('asset_identifier'),
            'eligible_for_bounty': attrs.get('eligible_for_bounty'),
            'eligible_for_submission': attrs.get('eligible_for_submission'),
            'max_severity': attrs.get('max_severity'),
            'instruction': attrs.get('instruction'),
            'confidentiality_requirement': attrs.get('confidentiality_requirement'),
            'integrity_requirement': attrs.get('integrity_requirement'),
            'availability_requirement': attrs.get('availability_requirement'),
            'created_at': attrs.get('created_at'),
            'updated_at': attrs.get('updated_at'),
        }

    @staticmethod
    def _fetch_handle_scopes(handle):
        all_scopes = []
        page = 1
        page_size = 100

        while True:
            url = f"hackers/programs/{handle}/structured_scopes?page[number]={page}&page[size]={page_size}"
            data = SendRequest.send_request(url)

            scopes = data.get('data', [])
            if not scopes:
                break

            all_scopes.extend(scopes)

            links = data.get('links', {})
            if links.get('next'):
                page += 1
            else:
                break

            if page > 100:
                break

        return {
            'handle': handle,
            'scope_count': len(all_scopes),
            'scopes': [ProgramDetailScraper._flatten_scope(scope) for scope in all_scopes]
        }

    @staticmethod
    def high_priority_handle_detail_scraping():
        scraper = ProgramScraper()
        handles = scraper.high_priority_handle_scraping()
        return [ProgramDetailScraper._fetch_handle_scopes(handle) for handle in handles]

    @staticmethod
    def low_priority_handle_detail_scraping():
        scraper = ProgramScraper()
        handles = scraper.low_priority_handle_scraping()
        return [ProgramDetailScraper._fetch_handle_scopes(handle) for handle in handles]


high_function = ProgramDetailScraper.high_priority_handle_detail_scraping()
low_function = ProgramDetailScraper.low_priority_handle_detail_scraping()

with open("high_priority_details.json", "w") as f:
    json.dump(high_function, f, indent=4)

with open("low_priority_details.json", "w") as f:
    json.dump(low_function, f, indent=4)