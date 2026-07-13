import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QLabel

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
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_creation_service import (
        legal_requirement_creation_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.ui.legal_requirement_dialog import LegalRequirementDialog


class LegalRequirementDialogFromSectionTestCase(unittest.TestCase):
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

    def _create_document(
        self,
        *,
        title: str = "Zákoník práce",
        number: str = "262/2006 Sb.",
        year: int = 2006,
        short_title: str = "ZP",
    ):
        return legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title=title,
            number=number,
            year=year,
            short_title=short_title,
        )

    def _create_subsection_101_odst_2(self, document=None):
        document = document or self._create_document()
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="Předmět",
            sort_order=1,
        )
        subsection = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph.id,
            section_number="2",
            text="Text odstavce 2",
            sort_order=2,
        )
        return document, subsection

    def _form_labels(self, dialog: LegalRequirementDialog) -> list[str]:
        labels = []
        for widget in dialog.findChildren(QLabel):
            text = widget.text().strip()
            if text.endswith(":"):
                labels.append(text)
        return labels

    def test_dialog_prefills_fields_when_created_from_section(self) -> None:
        _document, subsection = self._create_subsection_101_odst_2()
        draft = legal_requirement_creation_service.create_from_section(subsection.id)

        dialog = LegalRequirementDialog(draft=draft)

        self.assertEqual(dialog.regulation_name.currentText(), "Zákoník práce")
        self.assertEqual(dialog.regulation_number.text(), "262/2006 Sb.")
        self.assertEqual(dialog.provision.text(), "§ 101 odst. 2")
        self.assertEqual(dialog.legal_section.currentText(), "§ 101 odst. 2")
        self.assertEqual(dialog.sources_widget.get_section_ids(), [subsection.id])
        self.assertNotIn("Právní předpis:", self._form_labels(dialog))
        self.assertNotIn("Oblast:", self._form_labels(dialog))
        self.assertEqual(dialog.get_data()["legal_document_id"], _document.id)

    def test_selecting_name_fills_regulation_number(self) -> None:
        self._create_document()
        dialog = LegalRequirementDialog()
        dialog.regulation_number.clear()

        dialog.regulation_name.apply_search_text("Zákoník práce")

        self.assertEqual(dialog.regulation_name.currentText(), "Zákoník práce")
        self.assertEqual(dialog.regulation_number.text(), "262/2006 Sb.")

    def test_selecting_number_fills_regulation_name(self) -> None:
        self._create_document()
        dialog = LegalRequirementDialog()
        dialog.regulation_name.setCurrentText("")
        dialog.regulation_number.setText("262/2006 Sb.")

        self.assertEqual(dialog.regulation_name.currentText(), "Zákoník práce")
        self.assertEqual(dialog.regulation_number.text(), "262/2006 Sb.")

    def test_selecting_short_title_fills_name_and_number(self) -> None:
        self._create_document()
        dialog = LegalRequirementDialog()
        dialog.regulation_name.setCurrentText("")
        dialog.regulation_number.clear()

        dialog.regulation_name.apply_search_text("ZP")

        self.assertEqual(dialog.regulation_name.currentText(), "Zákoník práce")
        self.assertEqual(dialog.regulation_number.text(), "262/2006 Sb.")

    def test_changing_document_clears_selected_section_but_keeps_sources(self) -> None:
        first_document, subsection = self._create_subsection_101_odst_2()
        second_document = self._create_document(
            title="Nařízení vlády",
            number="390/2021",
            year=2021,
            short_title="NV",
        )
        second_version = legal_document_version_service.create(
            legal_document_id=second_document.id,
            version_name="Verze 2021",
        )
        second_section = legal_section_service.create(
            legal_document_id=second_document.id,
            legal_document_version_id=second_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="5",
            title="Test",
            sort_order=1,
        )

        draft = legal_requirement_creation_service.create_from_section(subsection.id)
        dialog = LegalRequirementDialog(draft=draft)
        self.assertEqual(dialog.legal_section.currentData(), subsection.id)
        self.assertEqual(dialog.sources_widget.get_section_ids(), [subsection.id])

        dialog.regulation_name.apply_search_text("Nařízení vlády")

        self.assertIsNone(dialog.legal_section.currentData())
        self.assertEqual(dialog.sources_widget.get_section_ids(), [subsection.id])
        self.assertEqual(dialog.get_data()["legal_document_id"], second_document.id)
        section_ids = [
            dialog.legal_section.itemData(index)
            for index in range(dialog.legal_section.count())
        ]
        self.assertIn(second_section.id, section_ids)
        self.assertNotIn(subsection.id, section_ids)
        self.assertNotIn(first_document.id, [dialog.get_data()["legal_document_id"]])

    def test_dialog_shows_pravni_podklady_label(self) -> None:
        from PySide6.QtWidgets import QGroupBox

        dialog = LegalRequirementDialog()
        groups = [widget.title() for widget in dialog.findChildren(QGroupBox)]
        self.assertIn("Právní podklady", groups)
        self.assertNotIn("Vychází z:", self._form_labels(dialog))

    def test_dialog_shows_zpusob_plneni_label(self) -> None:
        dialog = LegalRequirementDialog()
        labels = [label.text() for label in dialog.findChildren(QLabel)]

        self.assertIn("Způsob plnění:", labels)
        self.assertNotIn("Stručný požadavek:", labels)
        self.assertEqual(dialog.requirement_summary.toolTip(), "")

    def test_dialog_uses_process_terminology_labels(self) -> None:
        from PySide6.QtWidgets import QGroupBox

        dialog = LegalRequirementDialog()
        labels = self._form_labels(dialog)
        groups = [widget.title() for widget in dialog.findChildren(QGroupBox)]

        self.assertIn("Řídicí proces:", labels)
        self.assertIn("Identifikace procesu", groups)
        self.assertIn("Právní podklady", groups)
        self.assertIn("Popis procesu", groups)
        self.assertIn("Správa procesu", groups)
        self.assertIn("Vstupy procesu", groups)
        self.assertIn("Výstupy procesu", groups)
        self.assertIn("Vlastník procesu:", labels)
        self.assertIn("Kód procesu:", labels)
        self.assertNotIn("Odpovědnost:", labels)
        self.assertNotIn("Funkce / role:", labels)
        self.assertNotIn("Hlavní právní předpis:", labels)
        self.assertNotIn("Hlavní právní podklad:", labels)
        self.assertNotIn("Ustanovení předpisu:", labels)
        self.assertNotIn("Název předpisu:", labels)
        self.assertNotIn("Číslo předpisu:", labels)
        self.assertNotIn("Ustanovení:", labels)
        self.assertEqual(dialog.tabs.tabText(0), "Řídicí proces")
        self.assertEqual(dialog.tabs.tabText(2), "Vazby a použití")

    def test_dialog_without_sources_prompts_to_select_source(self) -> None:
        from moduly.pravni_pozadavky.ui.legal_requirement_sources_widget import _NO_SOURCE_SELECTED_TEXT

        dialog = LegalRequirementDialog()
        dialog.sources_widget.tree.clearSelection()
        dialog._display_section_text(None)

        self.assertEqual(dialog.provision_text_view.toPlainText(), _NO_SOURCE_SELECTED_TEXT)
        self.assertEqual(dialog.provision_text_header.text(), "")

    def test_edit_dialog_shows_process_title(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service

        _document, subsection = self._create_subsection_101_odst_2()
        draft = legal_requirement_creation_service.create_from_section(subsection.id)
        requirement = legal_requirement_service.create_requirement(
            title="Řízení systému BOZP",
            regulation_name=draft.regulation_name,
            regulation_number=draft.regulation_number,
            provision=draft.provision,
            legal_document_id=draft.legal_document_id,
            legal_section_id=draft.legal_section_id,
            source_section_id=draft.source_section_id,
            source_section_ids=[draft.source_section_id],
        )

        dialog = LegalRequirementDialog(requirement=requirement)

        self.assertEqual(dialog.windowTitle(), "Upravit řídicí proces")
        self.assertEqual(dialog.process_title.text(), "Řízení systému BOZP")
        self.assertFalse(dialog.process_title.isReadOnly())

    def test_edit_root_process_title_updates_record(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service

        requirement = legal_requirement_service.create_requirement(
            title="Řízení systému BOZP",
        )
        dialog = LegalRequirementDialog(requirement=requirement)
        dialog.process_title.setText("Řízení BOZP a PO")

        legal_requirement_service.update_requirement(requirement.id, **dialog.get_data())

        reloaded = legal_requirement_service.get_by_id(requirement.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.title, "Řízení BOZP a PO")

    def test_empty_process_title_cannot_be_accepted(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service

        requirement = legal_requirement_service.create_requirement(
            title="Řízení systému BOZP",
        )
        dialog = LegalRequirementDialog(requirement=requirement)
        dialog.process_title.clear()

        with patch(
            "moduly.pravni_pozadavky.ui.legal_requirement_dialog.QMessageBox.warning"
        ) as warning:
            dialog.accept()

        warning.assert_called_once()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)

    def test_new_dialog_uses_ridici_proces_window_title(self) -> None:
        dialog = LegalRequirementDialog()
        self.assertEqual(dialog.windowTitle(), "Řídicí proces")

    def test_dialog_calculates_next_verification_from_periodicity(self) -> None:
        from datetime import date

        from moduly.pravni_pozadavky.constants import PERIODICITY_NA_POZADANI, PERIODICITY_ROCNE

        dialog = LegalRequirementDialog()
        dialog.periodicity.setCurrentIndex(dialog.periodicity.findData(PERIODICITY_ROCNE))
        dialog.last_verification.set_date_value(date(2026, 7, 9))

        self.assertEqual(dialog.next_verification.get_date(), date(2027, 7, 9))

        dialog.next_verification.set_date_value(date(2028, 1, 1))
        dialog.last_verification.set_date_value(date(2026, 1, 1))
        self.assertEqual(dialog.next_verification.get_date(), date(2027, 1, 1))

        dialog.periodicity.setCurrentIndex(dialog.periodicity.findData(PERIODICITY_NA_POZADANI))
        dialog.last_verification.set_date_value(date(2026, 7, 9))
        self.assertEqual(dialog.next_verification.get_date(), date(2027, 1, 1))

    def test_dialog_loads_and_saves_process_inputs_outputs(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service

        requirement = legal_requirement_service.create_requirement(
            title="Školení BOZP",
            requirement_summary="Test",
            process_inputs="Seznam zaměstnanců",
            process_outputs="Potvrzení o školení",
        )

        dialog = LegalRequirementDialog(requirement=requirement)

        self.assertFalse(dialog.process_inputs_view.isReadOnly())
        self.assertFalse(dialog.process_outputs_view.isReadOnly())
        self.assertEqual(dialog.process_inputs_view.toPlainText(), "Seznam zaměstnanců")
        self.assertEqual(dialog.process_outputs_view.toPlainText(), "Potvrzení o školení")
        self.assertEqual(dialog.get_data()["process_inputs"], "Seznam zaměstnanců")
        self.assertEqual(dialog.get_data()["process_outputs"], "Potvrzení o školení")

    def test_dialog_shows_provision_text_for_selected_source(self) -> None:
        from moduly.pravni_pozadavky.ui.legal_requirement_sources_widget import _MISSING_SECTION_TEXT

        _document, subsection = self._create_subsection_101_odst_2()
        legal_section_service.update(
            subsection.id,
            legal_document_id=subsection.legal_document_id,
            legal_document_version_id=subsection.legal_document_version_id,
            section_type=subsection.section_type,
            parent_section_id=subsection.parent_section_id,
            section_number=subsection.section_number,
            text="Text odstavce 2 pro zobrazení.",
        )
        draft = legal_requirement_creation_service.create_from_section(subsection.id)
        dialog = LegalRequirementDialog(draft=draft)

        self.assertTrue(dialog.provision_text_view.isReadOnly())
        self.assertEqual(
            dialog.provision_text_header.text(),
            "262/2006 Sb.\n§ 101 odst. 2",
        )
        self.assertEqual(
            dialog.provision_text_view.toPlainText(),
            "Text odstavce 2 pro zobrazení.",
        )

        version = legal_document_version_service.create(
            legal_document_id=_document.id,
            version_name="Verze B",
        )
        second_section = legal_section_service.create(
            legal_document_id=_document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="200",
            text="Druhý právní podklad.",
            sort_order=1,
        )
        dialog.sources_widget._append_section(second_section.id)
        dialog.sources_widget.select_section_at_index(1)

        self.assertEqual(dialog.provision_text_header.text(), "262/2006 Sb.\n§ 200")
        self.assertEqual(
            dialog.provision_text_view.toPlainText(),
            "Druhý právní podklad.",
        )

        empty_section = legal_section_service.create(
            legal_document_id=_document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="201",
            text="   ",
            sort_order=2,
        )
        dialog.sources_widget._append_section(empty_section.id)
        dialog.sources_widget.select_section_at_index(2)

        self.assertEqual(dialog.provision_text_header.text(), "262/2006 Sb.\n§ 201")
        self.assertEqual(dialog.provision_text_view.toPlainText(), _MISSING_SECTION_TEXT)

    def test_dialog_composes_paragraph_text_from_subsections(self) -> None:
        from moduly.pravni_pozadavky.constants import (
            DOCUMENT_TYPE_VYHLASKA,
            SECTION_ATTACHMENT,
            SECTION_PARAGRAPH,
            SECTION_SUBSECTION,
        )
        from moduly.pravni_pozadavky.ui.legal_requirement_sources_widget import _MISSING_SECTION_TEXT

        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Vyhláška č. 432/2003 Sb.",
            number="432",
            year=2003,
            short_title="V432",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
        )
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="2",
            title="(K § 37 zákona)",
            sort_order=1,
        )
        for index, text in enumerate(
            [
                "Zařazení práce do kategorie vyjadřuje souhrnné hodnocení.",
                "Při zařazování prací do kategorií se stanoví kategorie.",
            ],
            start=1,
        ):
            legal_section_service.create(
                legal_document_id=document.id,
                legal_document_version_id=version.id,
                section_type=SECTION_SUBSECTION,
                parent_section_id=paragraph.id,
                section_number=str(index),
                text=text,
                sort_order=index,
            )
        attachment = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_ATTACHMENT,
            section_number="1",
            title="Příloha č. 1 k vyhlášce č. 432/2003 Sb.",
            text="Kritéria kategorizace prací",
            sort_order=10,
        )
        empty_paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="99",
            sort_order=11,
        )

        dialog = LegalRequirementDialog()
        dialog.sources_widget.load_section_ids([paragraph.id, attachment.id, empty_paragraph.id])

        self.assertEqual(dialog.provision_text_header.text(), "432/2003 Sb.\n§ 2")
        self.assertIn(
            "(1) Zařazení práce do kategorie vyjadřuje souhrnné hodnocení.",
            dialog.provision_text_view.toPlainText(),
        )
        self.assertFalse(dialog.provision_text_view.toPlainText().startswith("§ 2"))
        self.assertIn(
            "(2) Při zařazování prací do kategorií se stanoví kategorie.",
            dialog.provision_text_view.toPlainText(),
        )

        dialog.sources_widget.select_section_at_index(1)
        self.assertEqual(dialog.provision_text_view.toPlainText(), "Kritéria kategorizace prací")

        dialog.sources_widget.select_section_at_index(2)
        self.assertEqual(dialog.provision_text_view.toPlainText(), _MISSING_SECTION_TEXT)


class LegalRequirementDialogChildrenTabTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement

        with get_session() as session:
            session.execute(delete(LegalRequirement))
            session.commit()

    def _tab_names(self, dialog: LegalRequirementDialog) -> list[str]:
        return [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]

    def test_root_process_dialog_shows_children_tab(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )

        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )

        dialog = LegalRequirementDialog(requirement=root)

        self.assertIn("Podřízené procesy", self._tab_names(dialog))
        self.assertIsNotNone(dialog.children_tab)
        self.assertEqual(dialog.parent_process_label.text(), "")

    def test_edit_child_process_title_updates_record(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )

        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        child = legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=root.id,
        )
        dialog = LegalRequirementDialog(requirement=child)

        self.assertFalse(dialog.process_title.isReadOnly())
        dialog.process_title.setText("Elektrická zařízení – revize")

        legal_requirement_service.update_requirement(child.id, **dialog.get_data())

        reloaded = legal_requirement_service.get_by_id(child.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.title, "Elektrická zařízení – revize")

    def test_child_process_dialog_shows_parent_process_label(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )

        root = legal_requirement_service.create_requirement(
            title="Řízení vyhrazených technických zařízení",
            process_code="P-015",
        )
        child = legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=root.id,
        )

        dialog = LegalRequirementDialog(requirement=child)

        self.assertEqual(
            dialog.parent_process_label.text(),
            "P-015 – Řízení vyhrazených technických zařízení",
        )

    def test_child_process_dialog_hides_children_tab(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )

        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        child = legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=root.id,
        )

        dialog = LegalRequirementDialog(requirement=child)

        self.assertNotIn("Podřízené procesy", self._tab_names(dialog))

    def test_children_tab_lists_child_processes(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )
        from moduly.pravni_pozadavky.ui.legal_requirement_children_table import (
            COL_ACTIVE,
            COL_CODE,
            COL_TITLE,
        )

        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        child = legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=root.id,
        )

        dialog = LegalRequirementDialog(requirement=root)
        dialog.children_tab.refresh()

        self.assertEqual(dialog.children_tab.table.rowCount(), 1)
        self.assertEqual(dialog.children_tab.table.item(0, COL_CODE).text(), child.process_code)
        self.assertEqual(dialog.children_tab.table.item(0, COL_TITLE).text(), "Elektrická zařízení")
        self.assertEqual(dialog.children_tab.table.item(0, COL_ACTIVE).text(), "Ano")

    def test_new_child_process_dialog_title_editable(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )

        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )

        dialog = LegalRequirementDialog(parent_requirement_id=root.id)

        self.assertFalse(dialog.process_title.isReadOnly())
        self.assertEqual(dialog.windowTitle(), "Nový podřízený proces")
        self.assertEqual(
            dialog.parent_process_label.text(),
            "P-015 – Řízení VTZ",
        )

    def test_new_child_process_requires_title(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )

        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        dialog = LegalRequirementDialog(parent_requirement_id=root.id)

        with patch(
            "moduly.pravni_pozadavky.ui.legal_requirement_dialog.QMessageBox.warning"
        ) as warning:
            dialog.accept()

        warning.assert_called_once()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)

    def test_cancel_new_child_process_does_not_create_record(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )

        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        dialog = LegalRequirementDialog(requirement=root)

        with patch(
            "moduly.pravni_pozadavky.ui.legal_requirement_children_tab.exec_maximized",
            return_value=False,
        ):
            dialog.children_tab.create_child_process()

        children = legal_requirement_service.list_children(root.id)
        self.assertEqual(len(children), 0)

    def test_save_new_child_process_creates_child_with_parent_and_code(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )

        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        dialog = LegalRequirementDialog(requirement=root)

        def accept_child_editor(child_dialog) -> int:
            child_dialog.process_title.setText("Elektrická zařízení")
            child_dialog.accept()
            return QDialog.DialogCode.Accepted

        with patch(
            "moduly.pravni_pozadavky.ui.legal_requirement_children_tab.exec_maximized",
            side_effect=accept_child_editor,
        ):
            dialog.children_tab.create_child_process()

        children = legal_requirement_service.list_children(root.id)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].process_code, "P-015.1")
        self.assertEqual(children[0].parent_requirement_id, root.id)
        self.assertEqual(children[0].title, "Elektrická zařízení")

    def test_open_child_process_opens_editor_for_selected_child(self) -> None:
        from unittest.mock import patch

        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )

        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        child = legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=root.id,
        )
        dialog = LegalRequirementDialog(requirement=root)
        dialog.children_tab.table.selectRow(0)

        with patch(
            "moduly.pravni_pozadavky.ui.legal_requirement_children_tab.exec_maximized",
            return_value=False,
        ) as open_dialog:
            dialog.children_tab.open_selected_child()

        self.assertTrue(open_dialog.called)
        opened_dialog = open_dialog.call_args.args[0]
        self.assertEqual(opened_dialog.requirement.id, child.id)


if __name__ == "__main__":
    unittest.main()
