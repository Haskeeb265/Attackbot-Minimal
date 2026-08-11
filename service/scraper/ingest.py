import shared.db as db

from service.scraper.program_scraper import ProgramScraper
from service.scraper.program_detail_scraper import ProgramDetailScraper
from db.mapper.hackerone_mapper import HackerOneMapper
from db.persistence.persistence import persist_program
from shared.colorlog import log
from shared.connectors.base import BaseConnector
from shared.connectors.hackerone_client import HackerOneConnector


def ingest_program(conn, handle: str, detail_scraper: ProgramDetailScraper):
    """
    One program, one unit of work. Fetch -> map -> persist.
    Caller (run_ingestion_job) owns the connection; this function
    owns the atomic block for this program.
    """
    program = detail_scraper.fetch_program(handle)
    mapped = HackerOneMapper.map_program(program)

    with db.atomic(conn):
        return persist_program(conn, mapped)


def run_ingestion_job(connector: BaseConnector | None = None):
    """
    One-shot job: enumerate high priority handles, then low priority
    handles, ingesting each independently. A failure on one program
    is caught here — outside ingest_program's atomic block — so it
    rolls back cleanly without halting the run.

    The source of program data is a :class:`BaseConnector` (HackerOne by
    default) — swap in another connector to ingest from another platform.
    """
    connector = connector or HackerOneConnector()

    scraper = ProgramScraper(connector)
    detail_scraper = ProgramDetailScraper(connector)

    high_handles = scraper.high_priority_handle_scraping()
    low_handles = scraper.low_priority_handle_scraping()
    handles = high_handles + low_handles

    log.process(f"Starting ingestion job — {len(handles)} handles queued")

    succeeded = 0
    failed = 0

    with db.get_conn() as conn:
        for handle in handles:
            try:
                ingest_program(conn, handle, detail_scraper)
                log.success(f"[{handle}] ingested")
                succeeded += 1
            except Exception as e:
                log.failed(f"[{handle}] ingestion failed: {e}")
                failed += 1

    log.process(f"Ingestion job complete — {succeeded} succeeded, {failed} failed")