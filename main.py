import threading
from service.scraper.ingest import run_ingestion_job

def main():
    ingestion_thread = threading.Thread(target=run_ingestion_job)
    ingestion_thread.start()
    ingestion_thread.join()
    

if __name__ == "__main__":
    main()