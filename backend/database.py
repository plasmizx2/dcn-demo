import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

pool = None


async def get_pool():
    """Get or create the database connection pool."""
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, statement_cache_size=0)
    return pool


async def close_pool():
    """Close the database connection pool."""
    global pool
    if pool:
        await pool.close()
        pool = None
