import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.app_runtime_service import mark_application_started

    mark_application_started()

    from moduly.pravni_pozadavky.constants import (
        CHANGE_EVALUATE_ACTION_LABEL,
        CHANGE_NOVELIZATION,
        CHANGE_UPDATED,
        DEFAULT_EVALUATION_FILTER,
        DOCUMENT_TYPE_ZAKON,
        FILTER_EVALUATION_ALL,
        FILTER_EVALUATION_EVALUATED,
        FILTER_EVALUATION_UNEVALUATED,
        SECTION_PARAGRAPH,
        WORDING_STATUS_ADOPTED,
        WORDING_STATUS_PENDING,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.sluzby.legal_version_adoption_service import (
        legal_version_adoption_service,
    )
    from moduly.pravni_pozadavky.ui.legal_change_detail_dialog import LegalChangeDetailDialog
    from moduly.pravni_pozadavky.ui.zmeny_legislativy_tab import ZmenyLegislativyTab


class LegalChangeEvaluationFilterTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalChangeSection))
            session.execute(delete(LegalChange))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

    def _create_change(self, *, title: str, evaluated: bool = False):
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title=f"Předpis {title}",
            number="262",
            year=2006,
        )
        return legal_change_service.create(
            legal_document_id=document.id,
            change_type=CHANGE_UPDATED,
            title=title,
            evaluated=evaluated,
        )

    def _titles(self, tab: ZmenyLegislativyTab) -> list[str]:
        return [tab.table.item(row, 4).text() for row in range(tab.table.rowCount())]

    def _create_pending_change(self, *, title: str):
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title=f"Předpis {title}",
            number="262",
            year=2006,
        )
        old_version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
        )
        new_version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Nově zjištěné znění – e-Sbírka 1",
            pending_adoption=True,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=old_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            title="§ 1",
            text="Původní text",
            sort_order=1,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=new_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            title="§ 1",
            text="Nový text",
            sort_order=1,
        )
        change = legal_change_service.create(
            legal_document_id=document.id,
            legal_document_version_id=old_version.id,
            new_legal_document_version_id=new_version.id,
            change_type=CHANGE_NOVELIZATION,
            title=title,
        )
        return change, old_version, new_version

    def test_default_filter_is_unevaluated(self) -> None:
        self._create_change(title="Nová", evaluated=False)
        self._create_change(title="Stará", evaluated=True)
        tab = ZmenyLegislativyTab()
        self.assertEqual(tab.evaluation_filter.currentText(), DEFAULT_EVALUATION_FILTER)
        self.assertEqual(tab.evaluation_filter.currentText(), FILTER_EVALUATION_UNEVALUATED)
        self.assertEqual(self._titles(tab), ["Nová"])

    def test_evaluated_filter_shows_only_evaluated(self) -> None:
        self._create_change(title="Nová", evaluated=False)
        self._create_change(title="Stará", evaluated=True)
        tab = ZmenyLegislativyTab()
        tab.evaluation_filter.setCurrentText(FILTER_EVALUATION_EVALUATED)
        self.assertEqual(self._titles(tab), ["Stará"])

    def test_all_filter_shows_both(self) -> None:
        self._create_change(title="Nová", evaluated=False)
        self._create_change(title="Stará", evaluated=True)
        tab = ZmenyLegislativyTab()
        tab.evaluation_filter.setCurrentText(FILTER_EVALUATION_ALL)
        self.assertEqual(set(self._titles(tab)), {"Nová", "Stará"})

    def test_existing_evaluated_records_are_filtered(self) -> None:
        older = self._create_change(title="Starší vyhodnocená", evaluated=True)
        self.assertTrue(older.evaluated)
        tab = ZmenyLegislativyTab()
        self.assertNotIn("Starší vyhodnocená", self._titles(tab))
        tab.evaluation_filter.setCurrentText(FILTER_EVALUATION_EVALUATED)
        self.assertEqual(self._titles(tab), ["Starší vyhodnocená"])

    def test_evaluate_action_saves_note_and_hides_from_default_filter(self) -> None:
        change = self._create_change(title="K posouzení", evaluated=False)
        tab = ZmenyLegislativyTab()
        self.assertEqual(tab.evaluate_btn.text(), CHANGE_EVALUATE_ACTION_LABEL)
        dialog = LegalChangeDetailDialog(tab, change=change)
        self.assertEqual(dialog.evaluate_btn.text(), CHANGE_EVALUATE_ACTION_LABEL)
        self.assertEqual(dialog.evaluation_status_label.text(), "Ne")
        dialog.evaluation_note_edit.setPlainText("Dopad omezený na školení.")
        dialog._save_evaluation()

        updated = legal_change_service.get_by_id(change.id)
        assert updated is not None
        self.assertTrue(updated.evaluated)
        self.assertEqual(updated.evaluation_note, "Dopad omezený na školení.")
        self.assertEqual(dialog.evaluation_status_label.text(), "Ano")
        self.assertEqual(self._titles(tab), [])

        tab.evaluation_filter.setCurrentText(FILTER_EVALUATION_EVALUATED)
        self.assertEqual(self._titles(tab), ["K posouzení"])
        found = legal_change_service.get_by_id(change.id)
        assert found is not None
        self.assertEqual(found.title, "K posouzení")
        dialog.close()

    def test_list_evaluate_button_hides_record_from_unevaluated(self) -> None:
        change = self._create_change(title="Ze seznamu", evaluated=False)
        tab = ZmenyLegislativyTab()
        tab.table.selectRow(0)
        tab._refresh_action_buttons()
        self.assertTrue(tab.evaluate_btn.isEnabled())
        tab.mark_selected_evaluated()
        updated = legal_change_service.get_by_id(change.id)
        assert updated is not None
        self.assertTrue(updated.evaluated)
        self.assertEqual(self._titles(tab), [])
        tab.evaluation_filter.setCurrentText(FILTER_EVALUATION_EVALUATED)
        self.assertEqual(self._titles(tab), ["Ze seznamu"])

    def test_adoption_does_not_change_evaluated_or_default_list(self) -> None:
        change, _old, new_version = self._create_pending_change(title="Čeká na převzetí")
        tab = ZmenyLegislativyTab()
        self.assertEqual(self._titles(tab), ["Čeká na převzetí"])
        legal_version_adoption_service.adopt_detected_version(change.id)
        tab.refresh()
        updated = legal_change_service.get_by_id(change.id)
        assert updated is not None
        self.assertFalse(updated.evaluated)
        adopted = legal_document_version_service.get_by_id(new_version.id)
        assert adopted is not None
        self.assertFalse(adopted.pending_adoption)
        self.assertEqual(self._titles(tab), ["Čeká na převzetí"])
        dialog = LegalChangeDetailDialog(change=updated)
        self.assertEqual(dialog.evaluation_status_label.text(), "Ne")
        self.assertEqual(dialog.wording_status_label.text(), WORDING_STATUS_ADOPTED)
        dialog.close()

    def test_evaluate_does_not_adopt_pending_version(self) -> None:
        change, _old, new_version = self._create_pending_change(title="Posoudit bez převzetí")
        dialog = LegalChangeDetailDialog(change=change)
        self.assertEqual(dialog.wording_status_label.text(), WORDING_STATUS_PENDING)
        dialog.evaluation_note_edit.setPlainText("Posouzeno, znění zatím nepřebírat.")
        dialog._save_evaluation()
        updated = legal_change_service.get_by_id(change.id)
        assert updated is not None
        self.assertTrue(updated.evaluated)
        pending = legal_document_version_service.get_by_id(new_version.id)
        assert pending is not None
        self.assertTrue(pending.pending_adoption)
        self.assertEqual(dialog.evaluation_status_label.text(), "Ano")
        self.assertEqual(dialog.wording_status_label.text(), WORDING_STATUS_PENDING)
        dialog.close()

    def test_detail_keeps_history_fields_after_evaluation(self) -> None:
        change, _old, _new = self._create_pending_change(title="Historie")
        legal_change_service.mark_evaluated(
            change.id,
            evaluation_note="Poznámka historie",
        )
        tab = ZmenyLegislativyTab()
        tab.evaluation_filter.setCurrentText(FILTER_EVALUATION_EVALUATED)
        self.assertEqual(self._titles(tab), ["Historie"])
        stored = legal_change_service.get_by_id(change.id)
        dialog = LegalChangeDetailDialog(change=stored)
        self.assertEqual(dialog.evaluation_status_label.text(), "Ano")
        self.assertEqual(dialog.evaluation_note_edit.toPlainText(), "Poznámka historie")
        self.assertEqual(dialog.wording_status_label.text(), WORDING_STATUS_PENDING)
        self.assertTrue(hasattr(dialog, "old_text_edit"))
        self.assertTrue(hasattr(dialog, "new_text_edit"))
        dialog.close()


if __name__ == "__main__":
    unittest.main()
