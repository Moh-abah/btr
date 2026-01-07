import redis.asyncio as redis
from app.config import settings
import json

class RedisClient:
    def __init__(self):
        self.redis = None
    
    async def connect(self):
        self.redis = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
            
        )
    
    async def disconnect(self):
        if self.redis:
            await self.redis.close()
    
    async def get_cached(self, key: str):
        if not self.redis:
            await self.connect()
        data = await self.redis.get(key)
        return json.loads(data) if data else None
    
    async def set_cached(self, key: str, value, expire: int = 300):
        if not self.redis:
            await self.connect()
        await self.redis.setex(
            key,
            expire,
            json.dumps(value)
        )

redis_client = RedisClient()