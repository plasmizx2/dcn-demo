import asyncio
from backend.database import get_pool
async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'users';")
        print([r['column_name'] for r in rows])
asyncio.run(main())
