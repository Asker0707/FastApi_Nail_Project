from redis import asyncio as aioredis

from core.config import settings

redis = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
