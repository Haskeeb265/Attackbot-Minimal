import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

URI = NEO4J_URI
AUTH = (NEO4J_USERNAME, NEO4J_PASSWORD)


def run_example():
    
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        driver.verify_connectivity()
        print("Connected Successfully")
        

if __name__ == "__main__":
    run_example()