"""Shared, repository-relative paths."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
RAW = DATA / 'raw'
REPORTS = ROOT / 'reports'
DB_PATH = ROOT / 'retail.db'
SOURCE_URL = 'https://archive.ics.uci.edu/static/public/502/online%2Bretail%2Bii.zip'
SOURCE_PAGE = 'https://archive.ics.uci.edu/dataset/502/online+retail+ii'
