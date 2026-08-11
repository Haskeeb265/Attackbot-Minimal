"""
HackerOne Hacker API v1 connector.

Concrete ``BaseConnector`` implementation for HackerOne. The scraper
service talks to this connector (or any other ``BaseConnector``) instead
of issuing HackerOne-specific HTTP calls itself.
"""

from config import HACKERONE_AUTH, HACKERONE_BASE_URL

from shared.connectors.base import BaseConnector


class HackerOneConnector(BaseConnector):
    """HackerOne implementation of :class:`BaseConnector` (Hacker API v1)."""

    def __init__(self):
        super().__init__(base_url=HACKERONE_BASE_URL, auth=HACKERONE_AUTH)

    def fetch_programs(
        self,
        page_size: int = 100,
        max_pages: int = 100,
    ) -> list[dict]:
        return self._paginate("hackers/programs", page_size, max_pages)

    def fetch_program_scopes(
        self,
        handle: str,
        page_size: int = 100,
        max_pages: int = 100,
    ) -> list[dict]:
        return self._paginate(
            f"hackers/programs/{handle}/structured_scopes",
            page_size,
            max_pages,
        )

    def fetch_program_weaknesses(
        self,
        handle: str,
        page_size: int = 100,
        max_pages: int = 100,
    ) -> list[dict]:
        return self._paginate(
            f"hackers/programs/{handle}/weaknesses",
            page_size,
            max_pages,
        )

    def fetch_program_scope_exclusions(self, handle: str) -> list[dict]:
        data = self._get(f"hackers/programs/{handle}/scope_exclusions")
        if not data or "data" not in data:
            return []
        return data["data"]
