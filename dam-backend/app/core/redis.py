"""Redis 连接管理

提供 Redis 连接池和便捷的缓存操作方法。
"""

import json
from typing import Any, Optional
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from loguru import logger

from app.core.config import settings


class RedisManager:
    """Redis 连接管理器"""

    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None

    async def connect(self):
        """建立 Redis 连接池"""
        try:
            self._pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=20,
                decode_responses=True,  # 自动解码为字符串
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            self._client = redis.Redis(connection_pool=self._pool)

            # 测试连接
            await self._client.ping()
            logger.info(f"Redis 连接成功: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            logger.error(f"Redis 连接失败: {e}")
            self._client = None
            raise

    async def disconnect(self):
        """关闭 Redis 连接"""
        if self._client:
            await self._client.close()
            logger.info("Redis 连接已关闭")
        if self._pool:
            await self._pool.disconnect()

    @property
    def client(self) -> redis.Redis:
        """获取 Redis 客户端实例"""
        if self._client is None:
            raise RuntimeError("Redis 未连接，请先调用 connect()")
        return self._client

    @property
    def is_connected(self) -> bool:
        """检查 Redis 是否已连接"""
        return self._client is not None

    @staticmethod
    def _json_default(obj):
        """JSON 序列化的兜底处理，支持 Pydantic 模型等对象"""
        # Pydantic v2 模型
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        # Pydantic v1 模型
        if hasattr(obj, 'dict'):
            return obj.dict()
        # datetime 等对象
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return str(obj)

    async def get(self, key: str) -> Optional[str]:
        """获取缓存值"""
        if not self.is_connected:
            return None
        try:
            return await self._client.get(key)
        except Exception as e:
            logger.warning(f"Redis GET 失败 [{key}]: {e}")
            return None

    async def set(self, key: str, value: str, ttl: int = 300) -> bool:
        """设置缓存值"""
        if not self.is_connected:
            return False
        try:
            await self._client.set(key, value, ex=ttl)
            return True
        except Exception as e:
            logger.warning(f"Redis SET 失败 [{key}]: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self.is_connected:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis DEL 失败 [{key}]: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """按模式批量删除缓存

        Args:
            pattern: 匹配模式，如 "device:*"

        Returns:
            删除的键数量
        """
        if not self.is_connected:
            return 0
        try:
            count = 0
            async for key in self._client.scan_iter(match=pattern, count=100):
                await self._client.delete(key)
                count += 1
            if count > 0:
                logger.debug(f"批量删除缓存: pattern={pattern}, count={count}")
            return count
        except Exception as e:
            logger.warning(f"Redis DEL Pattern 失败 [{pattern}]: {e}")
            return 0

    async def get_json(self, key: str) -> Optional[Any]:
        """获取 JSON 缓存值"""
        data = await self.get(key)
        if data is None:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            logger.warning(f"Redis JSON 解析失败 [{key}]")
            return None

    async def set_json(self, key: str, value: Any, ttl: int = 300) -> bool:
        """设置 JSON 缓存值"""
        try:
            data = json.dumps(value, ensure_ascii=False, default=self._json_default)
            return await self.set(key, data, ttl)
        except (TypeError, ValueError) as e:
            logger.warning(f"Redis JSON 序列化失败 [{key}]: {e}")
            return False

    async def incr(self, key: str, ttl: Optional[int] = None) -> int:
        """原子递增"""
        if not self.is_connected:
            return 0
        try:
            value = await self._client.incr(key)
            if ttl and value == 1:
                await self._client.expire(key, ttl)
            return value
        except Exception as e:
            logger.warning(f"Redis INCR 失败 [{key}]: {e}")
            return 0

    async def acquire_lock(self, key: str, ttl: int = 10) -> bool:
        """获取分布式锁"""
        if not self.is_connected:
            return False
        try:
            return await self._client.set(f"lock:{key}", "1", ex=ttl, nx=True)
        except Exception as e:
            logger.warning(f"Redis LOCK 失败 [{key}]: {e}")
            return False

    async def release_lock(self, key: str) -> bool:
        """释放分布式锁"""
        return await self.delete(f"lock:{key}")


# 全局单例
redis_manager = RedisManager()
