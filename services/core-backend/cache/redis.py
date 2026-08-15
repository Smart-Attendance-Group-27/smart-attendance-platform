import logging

from redis import RedisError
from redis.asyncio import Redis

from core.config import Settings


logger = logging.getLogger(__name__)


async def create_redis_client(settings: Settings) -> Redis | None:
    if settings.redis_url is None:
        logger.info("Redis cache is disabled.")
        return None

    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )

    try:
        await redis_client.ping()
    except RedisError:
        logger.warning("Redis cache is unavailable; continuing without cache.")
        await close_redis_client(redis_client)
        return None

    logger.info("Redis cache is available.")
    return redis_client


async def close_redis_client(redis_client: Redis | None) -> None:
    if redis_client is not None:
        await redis_client.aclose()
