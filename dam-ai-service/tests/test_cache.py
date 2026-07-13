import unittest
import sys
import types


class FakeLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


sys.modules.setdefault("loguru", types.SimpleNamespace(logger=FakeLogger()))
fake_redis_asyncio = types.SimpleNamespace(
    Redis=object,
    ConnectionPool=types.SimpleNamespace(from_url=lambda *args, **kwargs: object()),
)
sys.modules.setdefault("redis", types.SimpleNamespace(asyncio=fake_redis_asyncio))
sys.modules.setdefault("redis.asyncio", fake_redis_asyncio)

from app.core.cache import _resolve_ttl, _build_cache_key
from app.schemas.common import PageQuery


class CacheKeyTest(unittest.TestCase):
    def test_cache_key_includes_pydantic_model_fields(self):
        first = _build_cache_key("device:list", query=PageQuery(page_num=1, page_size=10))
        second = _build_cache_key("device:list", query=PageQuery(page_num=2, page_size=10))

        self.assertIn("query.page_num=1", first)
        self.assertIn("query.page_size=10", first)
        self.assertIn("query.page_num=2", second)
        self.assertNotEqual(first, second)

    def test_cache_key_includes_nested_dict_fields(self):
        key = _build_cache_key("alarm:list", params={"page_size": 5, "page_num": 1})
        self.assertIn("params.page_num=1", key)
        self.assertIn("params.page_size=5", key)

    def test_resolve_ttl_accepts_callable(self):
        ttl = _resolve_ttl(lambda *args, **kwargs: 120 if kwargs["range"] == "1h" else 300, range="1h")
        self.assertEqual(ttl, 120)


if __name__ == "__main__":
    unittest.main()
