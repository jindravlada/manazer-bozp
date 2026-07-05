import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.services.attachment_service import AttachmentService


class AttachmentServiceImageTests(unittest.TestCase):
    def test_store_source_file_optimizes_image_to_jpeg(self) -> None:
        service = AttachmentService()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "photo.png"
            Image.new("RGB", (2400, 1800), color=(200, 50, 50)).save(source)

            target = temp_path / "accident" / "7" / "photo.png"
            stored, stored_name = service._store_source_file(source, target)

            self.assertTrue(stored.exists())
            self.assertEqual(stored.suffix.lower(), ".jpg")
            self.assertEqual(stored_name, stored.name)
            self.assertLessEqual(stored.stat().st_size, 500 * 1024)

    def test_store_source_file_keeps_non_image(self) -> None:
        service = AttachmentService()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "protokol.odt"
            source.write_text("test", encoding="utf-8")

            target = temp_path / "accident" / "7" / "protokol.odt"
            stored, stored_name = service._store_source_file(source, target)

            self.assertTrue(stored.exists())
            self.assertEqual(stored.suffix.lower(), ".odt")
            self.assertEqual(stored_name, "protokol.odt")


if __name__ == "__main__":
    unittest.main()
