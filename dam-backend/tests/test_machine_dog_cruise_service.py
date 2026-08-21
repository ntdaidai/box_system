import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.services.machine_dog_cruise_service import MachineDogCruiseService
from app.services.minio_service import minio_service


class MachineDogCruiseServiceTests(unittest.TestCase):
    def test_catalog_contains_one_route_and_four_photo_plan(self):
        catalog = MachineDogCruiseService().route_catalog()
        self.assertEqual([item["route_key"] for item in catalog], ["all"])
        self.assertEqual(catalog[0]["photo_count"], 4)

    def test_cruise_returns_four_photos_from_dogtake(self):
        uploaded = []

        def upload(data, *, object_name, content_type):
            uploaded.append((data, object_name, content_type))
            return f"http://minio.test/dam/{object_name}"

        with tempfile.TemporaryDirectory() as temp_dir:
            picture_dir = Path(temp_dir) / "dogtake"
            picture_dir.mkdir()
            for index in range(1, 5):
                (picture_dir / f"dog-{index}.png").write_bytes(f"image-{index}".encode())

            with patch.object(settings, "MACHINE_DOG_CRUISE_PICTURE_ROOT", temp_dir), \
                 patch.object(minio_service, "upload_bytes", side_effect=upload):
                result = asyncio.run(MachineDogCruiseService().cruise())

        self.assertEqual(result["photo_count"], 4)
        self.assertEqual([item["point"] for item in result["photos"]], [
            "巡检点 1", "巡检点 2", "巡检点 3", "巡检点 4"
        ])
        self.assertEqual(result["image_urls"], [item["minio_url"] for item in result["photos"]])
        self.assertEqual(len(uploaded), 4)
        self.assertTrue(all(name.startswith("machine-dog-cruises/all/") for _, name, _ in uploaded))


if __name__ == "__main__":
    unittest.main()
