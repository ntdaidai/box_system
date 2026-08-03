# dai
"""Validation tests for stream access tickets."""

import unittest
from unittest.mock import patch

from app.services.stream_ticket import StreamTicketStore


class StreamTicketTests(unittest.TestCase):
    def test_ticket_is_bound_to_camera_mode_and_expiry(self):
        store = StreamTicketStore(ttl_seconds=5)
        with patch("app.services.stream_ticket.time.time", return_value=100.0):
            token, expires_at = store.issue("camera_a", detected=False)
        self.assertEqual(expires_at, 105.0)

        with patch("app.services.stream_ticket.time.time", return_value=101.0):
            self.assertTrue(store.validate(token, "camera_a", detected=False))
            self.assertFalse(store.validate(token, "camera_b", detected=False))
            self.assertFalse(store.validate(token, "camera_a", detected=True))

        with patch("app.services.stream_ticket.time.time", return_value=106.0):
            self.assertFalse(store.validate(token, "camera_a", detected=False))

    def test_revoked_or_unknown_ticket_is_rejected(self):
        store = StreamTicketStore()
        token, _ = store.issue("camera_a", detected=True)
        store.revoke(token)
        self.assertFalse(store.validate(token, "camera_a", detected=True))
        self.assertFalse(store.validate("unknown", "camera_a", detected=True))


if __name__ == "__main__":
    unittest.main()
