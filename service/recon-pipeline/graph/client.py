import sys
from pathlib import Path

# Make the project root importable so `config` always resolves to the single
# root config.py (one source of truth for all env vars). Needed because this
# directory is not a Python package (`recon-pipeline` contains a hyphen) and
# when run as a script only this directory is on sys.path.
# NOTE: `parents[3]` assumes graph -> recon-pipeline -> service -> root;
# update the index if this file is ever moved.
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

URI = NEO4J_URI
AUTH = (NEO4J_USERNAME, NEO4J_PASSWORD)

driver = GraphDatabase.driver(URI, auth=AUTH)