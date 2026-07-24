"""速率限制器 — 支持 Redis 分布式和内存级两种模式

优先使用 Redis 实现分布式速率限制，Redis 不可用时自动降级为内存级限制。
"""

import time
import threading
from collections import defaultdict
from typing import Tuple, Optional
from loguru import logger


class MemoryRateLimiter:
    """基于滑动窗口的内存级速率限制器

    线程安全，无需外部依赖。适合单进程场景或 Redis 不可用时的降级方案。
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self._max_attempts = max_attempts
        self._window = window_seconds
        self._attempts: defaultdict = defaultdict(list)  # key → [timestamp, ...]
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> Tuple[bool, int]:
        """检查 key 是否允许访问。

        Returns:
            (allowed: bool, remaining: int) — 剩余尝试次数
        """
        now = time.time()
        with self._lock:
            # 清理窗口外的旧记录
            cutoff = now - self._window
            self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]

            count = len(self._attempts[key])
            if count >= self._max_attempts:
                return False, 0

            self._attempts[key].append(now)
            return True, self._max_attempts - count - 1


class RedisRateLimiter:
    """基于 Redis 的分布式速率限制器

    使用滑动窗口算法，支持分布式部署。
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self._max_attempts = max_attempts
        self._window = window_seconds
        self._redis_client = None

    def _get_redis(self):
        """延迟获取 Redis 客户端"""
        if self._redis_client is None:
            try:
                from app.core.redis import redis_manager
                if redis_manager.is_connected:
                    self._redis_client = redis_manager.client
            except Exception:
                pass
        return self._redis_client

    async def is_allowed(self, key: str) -> Tuple[bool, int]:
        """检查 key 是否允许访问。

        Returns:
            (allowed: bool, remaining: int) — 剩余尝试次数
        """
        redis_client = self._get_redis()
        if redis_client is None:
            # Redis 不可用，降级到内存限制器
            return _memory_fallback.is_allowed(key)

        try:
            # 使用 Redis 事务实现滑动窗口
            now = time.time()
            window_start = now - self._window
            redis_key = f"rate_limit:{key}"

            # 使用 pipeline 减少网络往返
            pipe = redis_client.pipeline()

            # 移除窗口外的记录
            pipe.zremrangebyscore(redis_key, 0, window_start)

            # 统计当前窗口内的记录数
            pipe.zcard(redis_key)

            # 添加当前请求
            pipe.zadd(redis_key, {str(now): now})

            # 设置过期时间
            pipe.expire(redis_key, self._window)

            results = await pipe.execute()
            current_count = results[1]

            if current_count >= self._max_attempts:
                # 超过限制，移除刚添加的记录
                await redis_client.zrem(redis_key, str(now))
                return False, 0

            return True, self._max_attempts - current_count - 1

        except Exception as e:
            logger.warning(f"Redis 速率限制失败，降级到内存模式: {e}")
            self._redis_client = None
            return _memory_fallback.is_allowed(key)


class HybridRateLimiter:
    """混合速率限制器

    自动选择可用的实现：优先 Redis，降级到内存。
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self._max_attempts = max_attempts
        self._window = window_seconds
        self._redis_limiter = RedisRateLimiter(max_attempts, window_seconds)
        self._memory_limiter = MemoryRateLimiter(max_attempts, window_seconds)

    async def is_allowed(self, key: str) -> Tuple[bool, int]:
        """检查 key 是否允许访问。"""
        # 尝试使用 Redis
        redis_client = self._redis_limiter._get_redis()
        if redis_client is not None:
            return await self._redis_limiter.is_allowed(key)

        # 降级到内存
        return self._memory_limiter.is_allowed(key)


# 内存级降级方案
_memory_fallback = MemoryRateLimiter(max_attempts=5, window_seconds=60)

# 登录接口限速: 每 60 秒最多 5 次尝试（同一 IP）
login_limiter = HybridRateLimiter(max_attempts=5, window_seconds=60)
