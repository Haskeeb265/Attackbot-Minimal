import json
from .program_scraper import ProgramScraper
from .helpers.send_request import SendRequest
from shared.colorlog import log


class ProgramDetailScraper:

    MAX_PAGES = 100
    PAGE_SIZE = 100

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
        log.process(f"[{handle}] Fetching structured scopes...")
        all_scopes = []
        page = 1

        while True:
            url = f"hackers/programs/{handle}/structured_scopes?page[number]={page}&page[size]={ProgramDetailScraper.PAGE_SIZE}"
            data = SendRequest.send_request(url)

            if data is None:
                log.failed(f"[{handle}] Request failed on scopes page {page}")
                break

            scopes = data.get('data', [])
            if not scopes:
                break

            all_scopes.extend(scopes)
            log.process(f"[{handle}] Page {page} — {len(scopes)} scopes fetched")

            links = data.get('links', {})
            if links.get('next'):
                page += 1
            else:
                break

            if page > ProgramDetailScraper.MAX_PAGES:
                log.failed(f"[{handle}] Hit MAX_PAGES limit ({ProgramDetailScraper.MAX_PAGES}) on scopes")
                break

        log.success(f"[{handle}] {len(all_scopes)} total scopes fetched")

        return {
            'handle': handle,
            'scope_count': len(all_scopes),
            'scopes': [ProgramDetailScraper._flatten_scope(scope) for scope in all_scopes]
        }

    @staticmethod
    def get_scope_exclusions(handle: str) -> list[dict]:
        log.process(f"[{handle}] Fetching scope exclusions...")
        url = f"hackers/programs/{handle}/scope_exclusions"
        response = SendRequest.send_request(url)
        if response is None or "data" not in response:
            log.failed(f"[{handle}] Scope exclusions request failed or malformed")
            return []
        log.success(f"[{handle}] {len(response['data'])} scope exclusions fetched")
        return response["data"]

    @staticmethod
    def get_weaknesses(handle: str) -> list[dict]:
        log.process(f"[{handle}] Fetching weaknesses...")
        all_weaknesses = []
        page = 1

        while True:
            url = f"hackers/programs/{handle}/weaknesses?page[number]={page}&page[size]={ProgramDetailScraper.PAGE_SIZE}"
            response = SendRequest.send_request(url)
            if response is None or not response.get("data"):
                if response is None:
                    log.failed(f"[{handle}] Request failed on weaknesses page {page}")
                break
            all_weaknesses.extend(response["data"])
            if not response.get("links", {}).get("next"):
                break
            page += 1
            if page > ProgramDetailScraper.MAX_PAGES:
                log.failed(f"[{handle}] Hit MAX_PAGES limit ({ProgramDetailScraper.MAX_PAGES}) on weaknesses")
                break

        log.success(f"[{handle}] {len(all_weaknesses)} total weaknesses fetched")
        return all_weaknesses

    @staticmethod
    def high_priority_handle_detail_scraping():
        log.process("Starting HIGH priority handle detail scraping...")
        scraper = ProgramScraper()
        handles = scraper.high_priority_handle_scraping()
        results = [
            {
                **ProgramDetailScraper._fetch_handle_scopes(handle),
                "scope_exclusions": ProgramDetailScraper.get_scope_exclusions(handle),
                "weaknesses": ProgramDetailScraper.get_weaknesses(handle),
            }
            for handle in handles
        ]
        log.success(f"Finished HIGH priority scraping — {len(results)} programs")
        return results

    @staticmethod
    def low_priority_handle_detail_scraping():
        log.process("Starting LOW priority handle detail scraping...")
        scraper = ProgramScraper()
        handles = scraper.low_priority_handle_scraping()
        results = [
            {
                **ProgramDetailScraper._fetch_handle_scopes(handle),
                "scope_exclusions": ProgramDetailScraper.get_scope_exclusions(handle),
                "weaknesses": ProgramDetailScraper.get_weaknesses(handle),
            }
            for handle in handles
        ]
        log.success(f"Finished LOW priority scraping — {len(results)} programs")
        return results
    
    
    @staticmethod
    def fetch_program(handle: str) -> dict:
        return {
            **ProgramDetailScraper._fetch_handle_scopes(handle),
            "scope_exclusions": ProgramDetailScraper.get_scope_exclusions(handle),
            "weaknesses": ProgramDetailScraper.get_weaknesses(handle),
    }   


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    try:
        high_function = ProgramDetailScraper.high_priority_handle_detail_scraping()
        low_function = ProgramDetailScraper.low_priority_handle_detail_scraping()

        with open("high_priority_details.json", "w") as f:
            json.dump(high_function, f, indent=4)

        with open("low_priority_details.json", "w") as f:
            json.dump(low_function, f, indent=4)

        log.success(f"High priority details saved: {len(high_function)} programs")
        log.success(f"Low priority details saved: {len(low_function)} programs")

    except Exception as e:
        log.failed(f"Scraping run aborted: {e}")
        raise