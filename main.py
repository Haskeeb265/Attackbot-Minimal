import time
import threading
import shared.db as db

from service.scraper.program_detail_scraper import ProgramDetailScraper
from service.scraper.program_scraper import ProgramScraper
from db.queries import bounty_master as master_q
from db.queries import bounty_detail as detail_q
from db.queries import bounty_weaknesses as weakness_q
from db.queries import bounty_exclusions as exclusion_q
from shared.colorlog import log

class DataIngestionPipeline:
    
    def __init__(self, interval_seconds: int = 3600):
        self.interval_seconds = interval_seconds
        self.is_running = False
        self.thread = None
        
    def _transform_scopes(self, scopes: list([dict])-> list[dict])