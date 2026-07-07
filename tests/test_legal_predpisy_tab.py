import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.pravni_pozadavky.constants import (
        DEFAULT_DOCUMENT_ACTIVE_FILTER,
        DOCUMENT_TYPE_ZAKON,
        FILTER_ACTIVE_ONLY,
        FILTER_ALL_RECORDS,
        FILTER_INACTIVE_ONLY,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.ui.pravni_predpisy_tab import PravniPredpisyTab


class PravniPredpisyTabFilterTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

    def _create_document(self, *, title: str, active: bool = True):
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title=title,
            number="262/2006 Sb." if title == "Zákoník práce" else "390/2021 Sb.",
            year=2006 if title == "Zákoník práce" else 2021,
            short_title="ZP" if title == "Zákoník práce" else "Test",
        )
        if not active:
            legal_document_service.deactivate(document.id)
            document = legal_document_service.get_by_id(document.id)
        return document

    def _titles_in_table(self, tab: PravniPredpisyTab) -> list[str]:
        titles = []
        for row in range(tab.table.rowCount()):
            if tab.table.isRowHidden(row):
                continue
            item = tab.table.item(row, 4)
            if item is not None:
                titles.append(item.text())
        return titles

    def test_default_filter_shows_only_active_documents(self) -> None:
        self._create_document(title="Zákoník práce", active=True)
        self._create_document(title="Zákoník práce", active=False)

        tab = PravniPredpisyTab()

        self.assertEqual(tab.active_filter.currentText(), DEFAULT_DOCUMENT_ACTIVE_FILTER)
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(self._titles_in_table(tab), ["Zákoník práce"])

    def test_inactive_filter_shows_deactivated_documents(self) -> None:
        active = self._create_document(title="Aktivní předpis", active=True)
        inactive = self._create_document(title="Neaktivní předpis", active=False)

        tab = PravniPredpisyTab()
        tab.active_filter.setCurrentText(FILTER_INACTIVE_ONLY)
        tab.refresh()

        titles = self._titles_in_table(tab)
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(titles, ["Neaktivní předpis"])
        self.assertNotIn(active.title, titles)

    def test_all_filter_shows_active_and_inactive_documents(self) -> None:
        self._create_document(title="Aktivní předpis", active=True)
        self._create_document(title="Neaktivní předpis", active=False)

        tab = PravniPredpisyTab()
        tab.active_filter.setCurrentText(FILTER_ALL_RECORDS)
        tab.refresh()

        self.assertEqual(tab.table.rowCount(), 2)
        self.assertEqual(
            sorted(self._titles_in_table(tab)),
            ["Aktivní předpis", "Neaktivní předpis"],
        )

    def test_search_works_together_with_active_filter(self) -> None:
        self._create_document(title="Zákoník práce", active=True)
        self._create_document(title="Nařízení vlády", active=True)
        self._create_document(title="Zákoník práce", active=False)

        tab = PravniPredpisyTab()
        tab.text_filter.search_edit.setText("zákoník")

        titles = self._titles_in_table(tab)
        self.assertEqual(titles, ["Zákoník práce"])
        self.assertIn("Zobrazeno: 1 / 2", tab.text_filter.count_label.text())


if __name__ == "__main__":
    unittest.main()
