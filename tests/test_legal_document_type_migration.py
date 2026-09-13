import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

_TMP = Path(tempfile.mkdtemp())
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)

with _HOME_PATCHER:
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.pravni_pozadavky.constants import (
        DOCUMENT_TYPE_NARIZENI_VLADY,
        DOCUMENT_TYPE_VYHLASKA,
        DOCUMENT_TYPE_ZAKON,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service


class LegalDocumentTypeMigrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _HOME_PATCHER.start()

    @classmethod
    def tearDownClass(cls) -> None:
        _HOME_PATCHER.stop()

    def setUp(self) -> None:
        from core.database.session import get_session

        with get_session() as session:
            session.execute(text("DELETE FROM legal_sections"))
            session.execute(text("DELETE FROM legal_document_versions"))
            session.execute(text("DELETE FROM legal_documents"))
            session.commit()

        self._seed_document(
            number="262",
            year=2006,
            title="Zákoník práce",
            document_type=DOCUMENT_TYPE_ZAKON,
        )
        self._seed_document(
            number="390",
            year=2021,
            title="Nařízení vlády o bližších podmínkách poskytování osobních ochranných pracovních prostředků",
            document_type=DOCUMENT_TYPE_ZAKON,
        )
        self._seed_document(
            number="79",
            year=2013,
            title="Vyhláška o provedení některých ustanovení zákona č. 262/2006 Sb.",
            document_type=DOCUMENT_TYPE_ZAKON,
        )

        from core.database.database_initializer import _migrate_legal_document_types

        _migrate_legal_document_types()

    def _seed_document(
        self,
        *,
        number: str,
        year: int,
        title: str,
        document_type: str,
    ) -> None:
        legal_document_service.create(
            number=number,
            year=year,
            title=title,
            document_type=document_type,
            active=True,
        )

    def test_migration_fixes_document_types_from_titles(self) -> None:
        documents = {
            (document.number, document.year): document.document_type
            for document in legal_document_service.list_all(include_inactive=True)
        }

        self.assertEqual(documents[("262", 2006)], DOCUMENT_TYPE_ZAKON)
        self.assertEqual(documents[("390", 2021)], DOCUMENT_TYPE_NARIZENI_VLADY)
        self.assertEqual(documents[("79", 2013)], DOCUMENT_TYPE_VYHLASKA)


if __name__ == "__main__":
    unittest.main()
