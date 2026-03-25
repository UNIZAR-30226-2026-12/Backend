from databases import Database
import os

# Load .env file when running locally (fallback if python-dotenv not installed)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://reversi_user:reversi_password@localhost:5432/reversi_db")

database = Database(DATABASE_URL, statement_cache_size=0)
