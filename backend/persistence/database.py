from databases import Database
import os

# Load .env file when running locally (fallback if python-dotenv not installed)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL")

database = Database(DATABASE_URL, statement_cache_size=0)
