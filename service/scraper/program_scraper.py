import json
from .helpers.send_request import SendRequest
from shared.colorlog import log


class ProgramScraper:
    MAX_PAGES = 100
    PAGE_SIZE = 100

    @staticmethod
    def _fetch_all_programs():
        all_programs = []
        page = 1
        while True:
            url = f"hackers/programs?page[number]={page}&page[size]={ProgramScraper.PAGE_SIZE}"
            log.process(f"Fetching programs page {page}...")
            data = SendRequest.send_request(url)
            if not data or "data" not in data:
                log.failed(f"Programs page {page} returned no usable data")
                break
            programs = data["data"]
            if not programs:
                break
            all_programs.extend(programs)
            links = data.get("links", {})
            if not links.get("next"):
                break
            page += 1
            if page > ProgramScraper.MAX_PAGES:
                log.failed(f"Hit MAX_PAGES limit ({ProgramScraper.MAX_PAGES}) fetching programs")
                break
        log.success(f"Total programs fetched: {len(all_programs)}")
        return all_programs

    def high_priority_handle_scraping(self):
        all_programs = self._fetch_all_programs()
        high_priority = []
        for program in all_programs:
            attrs = program.get("attributes", {})
            handle = attrs.get("handle", "")
            submission_state = attrs.get("submission_state", "").lower()
            offers_bounties = attrs.get("offers_bounties", False)

            # Treat null as True for these fields (many programs have null instead of True)
            open_scope = attrs.get("open_scope") is not False
            gold_standard = attrs.get("gold_standard_safe_harbor") is not False
            valid_states = {"open", "paused", "disabled", "api_only"}
            if submission_state in valid_states and offers_bounties and open_scope and gold_standard:
                high_priority.append(handle)
        log.success(f"High priority handles found: {len(high_priority)}")
        return high_priority

    def low_priority_handle_scraping(self):
        all_programs = self._fetch_all_programs()
        low_priority = []
        for program in all_programs:
            attrs = program.get("attributes", {})
            handle = attrs.get("handle", "")
            offers_bounties = attrs.get("offers_bounties", False)

            # Strict check: must be explicitly False to qualify as "low"
            open_scope = attrs.get("open_scope") is True
            gold_standard = attrs.get("gold_standard_safe_harbor") is True
            if offers_bounties and not (open_scope and gold_standard):
                low_priority.append(handle)
        log.success(f"Low priority handles found: {len(low_priority)}")
        return low_priority

    def all_handles_scraping(self):
        all_programs = self._fetch_all_programs()
        return [
            p["attributes"]["handle"]
            for p in all_programs
            if "attributes" in p and "handle" in p["attributes"]
        ]

    def find_specific_program(self, handle: str):
        all_programs = self._fetch_all_programs()
        handle_lower = handle.lower()
        for program in all_programs:
            attrs = program.get("attributes", {})
            if attrs.get("handle", "").lower() == handle_lower:
                return {
                    "found": True,
                    "raw_attributes": attrs
                }
        return {"found": False}