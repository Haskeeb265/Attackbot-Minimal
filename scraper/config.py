from dotenv import load_dotenv
import os

load_dotenv()

HACKERONE_USERNAME = os.getenv("HACKERONE_USERNAME")
HACKERONE_TOKEN = os.getenv("HACKERONE_TOKEN")
BASE = "https://api.hackerone.com/v1"
AUTH = (HACKERONE_USERNAME, HACKERONE_TOKEN)


