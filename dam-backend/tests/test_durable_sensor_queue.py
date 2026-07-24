import tempfile
import unittest
from pathlib import Path

from app.services.durable_sensor_queue import DurableSensorQueue


class DurableSensorQueueTest(unittest.TestCase):
    def test_records_survive_close_and_reopen_until_acknowledged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pending.sqlite3"
            queue = DurableSensorQueue(path)
            queue.enqueue("temp_001", 1000, {"temperature": 21.5})
            queue.close()

            reopened = DurableSensorQueue(path)
            pending = reopened.fetch_pending()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["timestamp_ms"], 1000)
            self.assertEqual(pending[0]["data"]["temperature"], 21.5)

            reopened.acknowledge([pending[0]["_queue_id"]])
            self.assertEqual(reopened.status()["pending_count"], 0)
            reopened.close()

    def test_enqueue_is_idempotent_for_device_and_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = DurableSensorQueue(Path(tmpdir) / "pending.sqlite3")
            self.assertTrue(queue.enqueue("wind_001", 1000, {"wind_speed_ms": 1}))
            self.assertFalse(queue.enqueue("wind_001", 1000, {"wind_speed_ms": 1}))
            self.assertEqual(queue.status()["pending_count"], 1)
            queue.close()

    def test_failed_records_are_retained_and_deprioritized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = DurableSensorQueue(Path(tmpdir) / "pending.sqlite3")
            queue.enqueue("rain_001", 1000, {"total_rain": 1})
            queue.enqueue("rain_001", 2000, {"total_rain": 2})
            first, second = queue.fetch_pending()

            queue.mark_failed([first["_queue_id"]], "temporary failure")
            reordered = queue.fetch_pending()

            self.assertEqual(reordered[0]["_queue_id"], second["_queue_id"])
            self.assertEqual(reordered[1]["attempts"], 1)
            queue.close()


if __name__ == "__main__":
    unittest.main()
