"""Fáze 97f – Stav procesu: základ a výsledky auditů."""

from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.editable_catalog_service import editable_catalog_service
    from core.shared.constants import (
        CONTROL_RESULT_NEKONTROLOVANO,
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_AUDITY,
    )
    from core.shared.control_result_display import control_result_label
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_process_status_service import (
        PROCESS_STATUS_NO_ASSERTIONS,
        PROCESS_STATUS_NOT_AUDITED,
        legal_requirement_process_status_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.ui.legal_requirement_dialog import LegalRequirementDialog
    from moduly.pravni_pozadavky.ui.legal_requirement_process_status_widget import (
        LegalRequirementProcessStatusWidget,
    )

_RIZENI_RIZIK_PROCESS_ID = "rizeni_rizik"
_LINKED_SECTION_ID = "identifikace_nebezpeci"
_ASSERTION_ID = "id_proces_identifikace"
_ASSERTION_ID_2 = "id_zapojeni_zamestnancu"


class LegalRequirementProcessStatusPhase97fTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from core.shared.modely.control_result import ControlResult
        from moduly.audity.modely.audit import Audit
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource

        audit_knowledge_editor_service.ensure_user_catalogs()
        self._knowledge_path = audit_knowledge_service.audity_dir / "rizeni_rizik.json"
        bundled = editable_catalog_service.bundled_path("audity/rizeni_rizik.json")
        shutil.copy2(bundled, self._knowledge_path)
        with self._knowledge_path.open(encoding="utf-8") as handle:
            self._original_knowledge = json.load(handle)

        with get_session() as session:
            session.execute(delete(ControlResult))
            session.execute(delete(Audit))
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

        self._requirement = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
        )
        self._process_name = "Řízení rizik"
        self._section_name = "Identifikace nebezpečí a rizik"

    def tearDown(self) -> None:
        self._knowledge_path.write_text(
            json.dumps(self._original_knowledge, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _link_section(self, requirement_id: int | None = None) -> None:
        requirement_id = requirement_id if requirement_id is not None else self._requirement.id
        with self._knowledge_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        section = next(
            item for item in payload.get("sekce") or [] if item.get("id") == _LINKED_SECTION_ID
        )
        errors = audit_knowledge_editor_service.save_section_metadata(
            _RIZENI_RIZIK_PROCESS_ID,
            _LINKED_SECTION_ID,
            {
                "nazev": section.get("nazev"),
                "popis": section.get("popis"),
                "cil_overeni": section.get("cil_overeni"),
                "poradi": section.get("poradi"),
                "aktivni": section.get("aktivni", True),
                "legal_requirement_id": requirement_id,
            },
        )
        self.assertEqual(errors, [])

    def _create_audit(
        self,
        *,
        finished_at: date | None,
        audit_date: date | None = None,
        title: str = "Audit procesu",
    ):
        return audit_service.create_audit(
            title=title,
            audit_date=audit_date or finished_at or date(2026, 1, 1),
            started_at=date(2026, 1, 1),
            finished_at=finished_at,
            workplace_name="Provoz A",
        )

    def _set_result(
        self,
        audit_id: int,
        *,
        assertion_id: str,
        result: str,
        label: str = "Tvrzení",
    ) -> None:
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit_id,
            ControlPointContext(
                area_id=_RIZENI_RIZIK_PROCESS_ID,
                area_label=self._process_name,
                section_id=_LINKED_SECTION_ID,
                section_label=self._section_name,
                control_point_id=assertion_id,
                control_point_label=label,
            ),
            result=result,
        )

    def test_dialog_has_process_status_tab_after_links(self) -> None:
        dialog = LegalRequirementDialog(requirement=self._requirement)
        labels = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertIn("Stav procesu", labels)
        self.assertIn("Vazby a použití", labels)
        self.assertEqual(
            labels.index("Stav procesu"),
            labels.index("Vazby a použití") + 1,
        )
        self.assertIsNotNone(dialog.process_status_widget)

    def test_no_linked_assertions_shows_empty_message(self) -> None:
        status = legal_requirement_process_status_service.get_audit_status(self._requirement.id)
        self.assertEqual(status.assertion_count, 0)
        self.assertEqual(status.empty_message, PROCESS_STATUS_NO_ASSERTIONS)

        widget = LegalRequirementProcessStatusWidget(self._requirement.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn(PROCESS_STATUS_NO_ASSERTIONS, labels)

    def test_linked_but_never_audited_shows_empty_message(self) -> None:
        self._link_section()
        status = legal_requirement_process_status_service.get_audit_status(self._requirement.id)
        self.assertGreater(status.assertion_count, 0)
        self.assertEqual(status.empty_message, PROCESS_STATUS_NOT_AUDITED)

        widget = LegalRequirementProcessStatusWidget(self._requirement.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn(PROCESS_STATUS_NOT_AUDITED, labels)

    def test_last_completed_audit_results_are_summarized(self) -> None:
        self._link_section()
        audit = self._create_audit(finished_at=date(2026, 3, 15), title="Jarní audit")
        self._set_result(audit.id, assertion_id=_ASSERTION_ID, result=CONTROL_RESULT_VYHOVUJE)
        self._set_result(
            audit.id,
            assertion_id=_ASSERTION_ID_2,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )

        status = legal_requirement_process_status_service.get_audit_status(self._requirement.id)

        self.assertIsNone(status.empty_message)
        self.assertEqual(status.last_audit_id, audit.id)
        self.assertEqual(status.last_audit_date, date(2026, 3, 15))
        self.assertEqual(status.last_audit_number, audit.number)
        self.assertEqual(status.evaluated_count, 2)

        by_code = {item.result_code: item.count for item in status.result_counts}
        self.assertEqual(by_code[CONTROL_RESULT_VYHOVUJE], 1)
        self.assertEqual(by_code[CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM], 1)
        self.assertEqual(by_code[CONTROL_RESULT_NEVYHOVUJE], 0)

        widget = LegalRequirementProcessStatusWidget(self._requirement.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Poslední dokončený audit: 15.03.2026", labels)
        self.assertTrue(any(audit.number in text for text in labels))
        self.assertIn(f"• {control_result_label(CONTROL_RESULT_VYHOVUJE)}: 1", labels)

    def test_uses_latest_completed_audit_only(self) -> None:
        self._link_section()
        older = self._create_audit(finished_at=date(2026, 1, 10), title="Starý audit")
        newer = self._create_audit(finished_at=date(2026, 4, 20), title="Nový audit")
        self._set_result(older.id, assertion_id=_ASSERTION_ID, result=CONTROL_RESULT_NEVYHOVUJE)
        self._set_result(newer.id, assertion_id=_ASSERTION_ID, result=CONTROL_RESULT_VYHOVUJE)

        status = legal_requirement_process_status_service.get_audit_status(self._requirement.id)

        self.assertEqual(status.last_audit_id, newer.id)
        self.assertEqual(status.last_audit_date, date(2026, 4, 20))
        by_code = {item.result_code: item.count for item in status.result_counts}
        self.assertEqual(by_code[CONTROL_RESULT_VYHOVUJE], 1)
        self.assertEqual(by_code[CONTROL_RESULT_NEVYHOVUJE], 0)

    def test_in_progress_audit_is_ignored(self) -> None:
        self._link_section()
        open_audit = self._create_audit(finished_at=None, audit_date=date(2026, 5, 1))
        self._set_result(open_audit.id, assertion_id=_ASSERTION_ID, result=CONTROL_RESULT_VYHOVUJE)

        status = legal_requirement_process_status_service.get_audit_status(self._requirement.id)
        self.assertEqual(status.empty_message, PROCESS_STATUS_NOT_AUDITED)

    def test_nekontrolovano_alone_does_not_count_as_verified(self) -> None:
        self._link_section()
        audit = self._create_audit(finished_at=date(2026, 2, 1))
        self._set_result(
            audit.id,
            assertion_id=_ASSERTION_ID,
            result=CONTROL_RESULT_NEKONTROLOVANO,
        )

        status = legal_requirement_process_status_service.get_audit_status(self._requirement.id)
        self.assertEqual(status.empty_message, PROCESS_STATUS_NOT_AUDITED)

    def test_unrelated_process_results_are_ignored(self) -> None:
        self._link_section()
        audit = self._create_audit(finished_at=date(2026, 3, 1))
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="jiny_proces",
                area_label="Jiný proces",
                section_id="jina_sekce",
                section_label="Jiná sekce",
                control_point_id="cizi_tvrzeni",
                control_point_label="Cizí",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
        )

        status = legal_requirement_process_status_service.get_audit_status(self._requirement.id)
        self.assertEqual(status.empty_message, PROCESS_STATUS_NOT_AUDITED)


if __name__ == "__main__":
    unittest.main()
