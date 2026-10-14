"""PRAVNI-REGRESE-1: úprava existujícího požadavku nepřepisuje needitovaná pole."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="pravni-regrese-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from sqlalchemy import select

    from core.database.session import get_session
    from moduly.pravni_pozadavky.constants import (
        COMPLIANCE_CASTECNE_SPLNENO,
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.ui.legal_document_workbench_tab import (
        LegalDocumentWorkbenchTab,
    )

_LAST_VERIFICATION = date(2024, 6, 1)
_NEXT_VERIFICATION = date(2025, 6, 1)
_PROCESS_INPUTS = "vstup: záznam o školení"
_PROCESS_OUTPUTS = "výstup: evidence plnění"
_ORIGINAL_NOTE = "původní poznámka"
_FIRST_NOTE = "první úprava poznámky"
_SECOND_NOTE = "druhá úprava poznámky"


def _read_database() -> tuple[list[dict], list[dict]]:
    """Načte požadavky a vazby na ustanovení z nové session."""
    with get_session() as session:
        requirements = list(
            session.scalars(select(LegalRequirement).order_by(LegalRequirement.id))
        )
        sources = list(
            session.scalars(
                select(LegalRequirementSource).order_by(LegalRequirementSource.id)
            )
        )
        requirement_rows = [
            {
                "id": row.id,
                "note": row.note,
                "legal_section_id": row.legal_section_id,
                "source_section_id": row.source_section_id,
                "process_inputs": row.process_inputs,
                "process_outputs": row.process_outputs,
                "last_verification_date": row.last_verification_date,
                "next_verification_date": row.next_verification_date,
                "compliance_status": row.compliance_status,
            }
            for row in requirements
        ]
        source_rows = [
            {
                "id": row.id,
                "requirement_id": row.requirement_id,
                "legal_section_id": row.legal_section_id,
            }
            for row in sources
        ]
    return requirement_rows, source_rows


class PravniRegrese1RequirementUpdateTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_form_save_updates_note_and_keeps_unedited_fields(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )
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
        section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph.id,
            section_number="1",
            text="Text ustanovení",
            sort_order=1,
        )
        created = legal_requirement_service.create_requirement(
            title="Povinnost BOZP",
            regulation_name="Zákoník práce",
            legal_document_id=document.id,
            legal_section_id=section.id,
            source_section_id=section.id,
            requirement_summary="Původní způsob plnění",
            process_inputs=_PROCESS_INPUTS,
            process_outputs=_PROCESS_OUTPUTS,
            last_verification_date=_LAST_VERIFICATION,
            next_verification_date=_NEXT_VERIFICATION,
            compliance_status=COMPLIANCE_CASTECNE_SPLNENO,
            note=_ORIGINAL_NOTE,
        )
        original_id = created.id
        before, before_sources = _read_database()
        self.assertEqual(len(before), 1)
        self.assertEqual(before[0]["id"], original_id)
        self.assertEqual(len(before_sources), 1)
        self.assertEqual(before_sources[0]["requirement_id"], original_id)
        self.assertEqual(before_sources[0]["legal_section_id"], section.id)

        tab = LegalDocumentWorkbenchTab(document_id=document.id, version_id=version.id)
        tab.show()
        self.app.processEvents()
        assert tab.tree is not None and tab.editor is not None
        tab.tree.select_section_id(section.id)
        tab.load_section(section.id)
        editor = tab.editor
        self.assertEqual(editor.note.toPlainText(), _ORIGINAL_NOTE)
        self.assertFalse(editor.has_changes())

        editor.note.setPlainText(_FIRST_NOTE)
        self._save_from_form(tab)
        self._assert_unchanged_fields(
            original_id=original_id,
            section_id=section.id,
            note=_FIRST_NOTE,
            source_link_id=before_sources[0]["id"],
        )
        self.assertEqual(editor.note.toPlainText(), _FIRST_NOTE)

        editor.note.setPlainText(_SECOND_NOTE)
        self._save_from_form(tab)
        self._assert_unchanged_fields(
            original_id=original_id,
            section_id=section.id,
            note=_SECOND_NOTE,
            source_link_id=before_sources[0]["id"],
        )
        self.assertEqual(editor.note.toPlainText(), _SECOND_NOTE)

    def _save_from_form(self, tab: LegalDocumentWorkbenchTab) -> None:
        warnings: list[tuple] = []

        def _exec(box: QMessageBox) -> int:
            self.assertEqual(box.windowTitle(), "Právní požadavky")
            return int(QMessageBox.StandardButton.Ok)

        with patch.object(QMessageBox, "warning", side_effect=lambda *args, **kwargs: warnings.append(args)):
            with patch(
                "moduly.pravni_pozadavky.ui.legal_document_workbench_tab._exec_message_box",
                side_effect=_exec,
            ):
                assert tab.editor is not None
                tab.editor.save_btn.click()
                self.app.processEvents()
        self.assertEqual(warnings, [])

    def _assert_unchanged_fields(
        self,
        *,
        original_id: int,
        section_id: int,
        note: str,
        source_link_id: int,
    ) -> None:
        rows, sources = _read_database()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], original_id)
        self.assertEqual(row["note"], note)
        self.assertEqual(row["legal_section_id"], section_id)
        self.assertEqual(row["source_section_id"], section_id)
        self.assertEqual(row["process_inputs"], _PROCESS_INPUTS)
        self.assertEqual(row["process_outputs"], _PROCESS_OUTPUTS)
        self.assertEqual(row["last_verification_date"], _LAST_VERIFICATION)
        self.assertEqual(row["next_verification_date"], _NEXT_VERIFICATION)
        self.assertEqual(row["compliance_status"], COMPLIANCE_CASTECNE_SPLNENO)
        self.assertEqual(
            sources,
            [
                {
                    "id": source_link_id,
                    "requirement_id": original_id,
                    "legal_section_id": section_id,
                }
            ],
        )
