from databases import Database
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://reversi_user:reversi_password@localhost:5432/reversi_db")

database = Database(DATABASE_URL)
