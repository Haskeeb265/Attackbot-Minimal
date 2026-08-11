from shared.colorlog import log
from shared.connectors.base import BaseConnector
from shared.connectors.hackerone_client import HackerOneConnector


class ProgramScraper:
    MAX_PAGES = 100
    PAGE_SIZE = 100

    def __init__(self, connector: BaseConnector | None = None):
        self.connector = connector or HackerOneConnector()

    def _fetch_all_programs(self):
        log.process("Fetching programs...")
        all_programs = self.connector.fetch_programs(
            page_size=self.PAGE_SIZE,
            max_pages=self.MAX_PAGES,
        )
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