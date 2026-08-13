import asyncpg


async def check_database_connection(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as connection:
        await connection.fetchval("select 1")