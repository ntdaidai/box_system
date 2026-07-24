import unittest

from scripts.check_history_health import evaluate


class HistoryHealthTest(unittest.TestCase):
    def healthy_payload(self):
        return {
            "data": {
                "pending_queue": {"oldest_age_seconds": 2},
                "history_storage": {
                    "status": "healthy",
                    "fresh_device_count": 4,
                    "device_count": 4,
                    "rollup_lag": {"1m": {"lag_buckets": 1}},
                },
            }
        }

    def test_healthy_chain_passes(self):
        self.assertEqual(evaluate(self.healthy_payload(), 120, 10), [])

    def test_stale_queue_and_rollup_fail(self):
        payload = self.healthy_payload()
        payload["data"]["pending_queue"]["oldest_age_seconds"] = 121
        payload["data"]["history_storage"]["rollup_lag"]["1m"]["lag_buckets"] = 11

        failures = evaluate(payload, 120, 10)

        self.assertIn("queue_oldest_age=121.0s", failures)
        self.assertIn("rollup_1m_lag=11", failures)

    def test_stale_device_fails(self):
        payload = self.healthy_payload()
        payload["data"]["history_storage"]["fresh_device_count"] = 3

        self.assertIn("fresh_devices=3/4", evaluate(payload, 120, 10))


if __name__ == "__main__":
    unittest.main()
