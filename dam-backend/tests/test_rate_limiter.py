import unittest
import sys
import types


class FakeLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


sys.modules.setdefault("loguru", types.SimpleNamespace(logger=FakeLogger()))

from app.core.rate_limiter import RedisRateLimiter


class FakePipeline:
    def __init__(self, count):
        self.count = count
        self.executed = False

    def zremrangebyscore(self, *_args):
        return self

    def zcard(self, *_args):
        return self

    def zadd(self, *_args):
        return self

    def expire(self, *_args):
        return self

    async def execute(self):
        self.executed = True
        return [0, self.count, 1, True]


class FakeRedis:
    def __init__(self, count=0):
        self.pipeline_instance = FakePipeline(count)
        self.removed = []

    def pipeline(self):
        return self.pipeline_instance

    async def zrem(self, *args):
        self.removed.append(args)


class RateLimiterTest(unittest.IsolatedAsyncioTestCase):
    async def test_redis_rate_limiter_awaits_pipeline(self):
        redis = FakeRedis(count=0)
        limiter = RedisRateLimiter(max_attempts=5, window_seconds=60)
        limiter._redis_client = redis

        allowed, remaining = await limiter.is_allowed("127.0.0.1")

        self.assertTrue(redis.pipeline_instance.executed)
        self.assertTrue(allowed)
        self.assertEqual(remaining, 4)

    async def test_redis_rate_limiter_rejects_over_limit(self):
        redis = FakeRedis(count=5)
        limiter = RedisRateLimiter(max_attempts=5, window_seconds=60)
        limiter._redis_client = redis

        allowed, remaining = await limiter.is_allowed("127.0.0.1")

        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)
        self.assertEqual(len(redis.removed), 1)


if __name__ == "__main__":
    unittest.main()

