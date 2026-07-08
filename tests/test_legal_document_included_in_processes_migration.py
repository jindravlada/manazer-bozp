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


class LegalDocumentIncludedInProcessesMigrationTestCase(unittest.TestCase):
    def test_migration_adds_included_in_processes_column(self) -> None:
        from core.database.database_initializer import _table_columns

        columns = _table_columns("legal_documents")
        self.assertIn("included_in_processes", columns)


if __name__ == "__main__":
    unittest.main()
