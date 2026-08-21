from pathlib import Path
from dotenv import load_dotenv
import os

# 5 parents up to reach project root from this config.py
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent.parent / ".env", override=True)

TARGET = os.getenv("TARGET", "qbsco.net")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIRPC"))
OUTPUT_FILESUB = OUTPUT_DIR / "subfinder.txt"
OUTPUT_FILEAMASS = OUTPUT_DIR / "amass.txt"