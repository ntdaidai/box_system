"""缓存工具层

提供缓存装饰器和便捷的缓存操作方法。
"""

import functools
import random
from collections.abc import Mapping
from typing import Callable, Optional, Any
from loguru import logger

from app.core.redis import redis_manager


def _flatten_key_parts(name: str, value: Any) -> list[str]:
    if name.startswith("_"):
        return []

    if value is None:
        return [f"{name}=null"]

    if isinstance(value, (str, int, float, bool)):
        return [f"{name}={value}"]

    if hasattr(value, "model_dump"):
        return _flatten_key_parts(name, value.model_dump())

    if hasattr(value, "dict"):
        return _flatten_key_parts(name, value.dict())

    if isinstance(value, Mapping):
        parts = []
        for key in sorted(value.keys(), key=str):
            parts.extend(_flatten_key_parts(f"{name}.{key}", value[key]))
        return parts

    if isinstance(value, (list, tuple)):
        parts = []
        for index, item in enumerate(value):
            parts.extend(_flatten_key_parts(f"{name}.{index}", item))
        return parts

    return []


def _build_cache_key(prefix: str, *args, **kwargs) -> str:
    """构建缓存键

    Args:
        prefix: 缓存键前缀
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        缓存键字符串
    """
    # 提取有意义的参数（过滤掉 db、_user 等依赖注入对象）
    key_parts = []
    for index, arg in enumerate(args):
        key_parts.extend(_flatten_key_parts(f"arg{index}", arg))
    for k, v in sorted(kwargs.items()):
        key_parts.extend(_flatten_key_parts(k, v))

    if key_parts:
        key_suffix = ":".join(key_parts)
        return f"{prefix}:{key_suffix}"
    return prefix


def _add_jitter(ttl: int, jitter_ratio: float = 0.1) -> int:
    """为 TTL 添加随机偏移，防止缓存雪崩

    Args:
        ttl: 基础 TTL（秒）
        jitter_ratio: 偏移比例（默认10%）

    Returns:
        添加偏移后的 TTL
    """
    jitter = int(ttl * jitter_ratio)
    return ttl + random.randint(-jitter, jitter)


def _resolve_ttl(ttl: int | Callable, *args, **kwargs) -> int:
    if callable(ttl):
        return int(ttl(*args, **kwargs))
    return int(ttl)


def cached(ttl: int = 300, prefix: str = "", jitter: bool = True):
    """缓存装饰器

    Args:
        ttl: 缓存过期时间（秒）
        prefix: 缓存键前缀（默认使用函数名）
        jitter: 是否添加 TTL 随机偏移

    Usage:
        @cached(ttl=60, prefix="device")
        async def get_device_list(page: int = 1, size: int = 10):
            ...
    """
    def decorator(func: Callable):
        # 确定缓存前缀
        cache_prefix = prefix or func.__name__

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 如果 Redis 未连接，直接执行函数
            if not redis_manager.is_connected:
                return await func(*args, **kwargs)

            # 构建缓存键
            cache_key = _build_cache_key(cache_prefix, *args, **kwargs)

            # 尝试从缓存获取
            try:
                cached_data = await redis_manager.get_json(cache_key)
                if cached_data is not None:
                    logger.debug(f"缓存命中: {cache_key}")
                    return cached_data
            except Exception as e:
                logger.warning(f"缓存读取失败: {cache_key}, {e}")

            # 缓存未命中，执行函数
            result = await func(*args, **kwargs)

            # 写入缓存
            try:
                base_ttl = _resolve_ttl(ttl, *args, **kwargs)
                actual_ttl = _add_jitter(base_ttl) if jitter else base_ttl
                await redis_manager.set_json(cache_key, result, actual_ttl)
                logger.debug(f"缓存写入: {cache_key}, TTL={actual_ttl}s")
            except Exception as e:
                logger.warning(f"缓存写入失败: {cache_key}, {e}")

            return result

        # 添加缓存失效方法
        async def invalidate(*args, **kwargs):
            """手动失效此函数的缓存"""
            cache_key = _build_cache_key(cache_prefix, *args, **kwargs)
            await redis_manager.delete(cache_key)

        async def invalidate_pattern(pattern: str = None):
            """按模式批量失效缓存"""
            p = pattern or f"{cache_prefix}:*"
            return await redis_manager.delete_pattern(p)

        wrapper.invalidate = invalidate
        wrapper.invalidate_pattern = invalidate_pattern
        wrapper.cache_prefix = cache_prefix

        return wrapper
    return decorator


async def invalidate_cache(pattern: str) -> int:
    """按模式批量失效缓存

    Args:
        pattern: 匹配模式，如 "device:*"

    Returns:
        删除的键数量
    """
    return await redis_manager.delete_pattern(pattern)


async def cache_get(key: str) -> Optional[Any]:
    """直接获取缓存"""
    return await redis_manager.get_json(key)


async def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """直接设置缓存"""
    return await redis_manager.set_json(key, value, ttl)


async def cache_delete(key: str) -> bool:
    """直接删除缓存"""
    return await redis_manager.delete(key)
