import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_ZAKON
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service


class LegalDocumentServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument

        with get_session() as session:
            session.execute(delete(LegalDocument))
            session.commit()

    def test_create_legal_document(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )

        self.assertIsNotNone(document.id)
        self.assertEqual(document.title, "Zákoník práce")
        self.assertTrue(document.active)

    def test_update_legal_document(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Původní název",
        )
        updated = legal_document_service.update(
            document.id,
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Upravený název",
            number="123/2020 Sb.",
            year=2020,
            short_title="Test",
            active=True,
        )

        assert updated is not None
        self.assertEqual(updated.title, "Upravený název")
        self.assertEqual(updated.short_title, "Test")

    def test_deactivate_and_restore_legal_document(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="K deaktivaci",
        )

        deactivated = legal_document_service.deactivate(document.id)
        assert deactivated is not None
        self.assertFalse(deactivated.active)

        active_only = legal_document_service.list_all()
        self.assertEqual(active_only, [])

        restored = legal_document_service.restore(document.id)
        assert restored is not None
        self.assertTrue(restored.active)


if __name__ == "__main__":
    unittest.main()
