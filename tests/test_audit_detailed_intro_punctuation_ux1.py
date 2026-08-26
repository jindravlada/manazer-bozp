"""AUDIT-DETAILED-INTRO-PUNCTUATION-UX1: dvojtečky u mezititulků Podrobné zprávy."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-intro-punct-ux1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from moduly.audity.constants import (
        AUDIT_INTRO_CHANGES_LABEL,
        AUDIT_INTRO_EXPORT_CHANGES_HEADING,
        AUDIT_INTRO_EXPORT_FINDINGS_HEADING,
        AUDIT_INTRO_EXPORT_PREVIOUS_AUDITS_HEADING,
        AUDIT_INTRO_EXPORT_TASKS_HEADING,
        AUDIT_INTRO_FINDINGS_GROUP,
        AUDIT_INTRO_PREVIOUS_AUDITS_GROUP,
        AUDIT_INTRO_TASKS_GROUP,
    )
    from moduly.audity.sluzby.audit_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG,
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_history_service import audit_history_service
    from moduly.audity.sluzby.audit_intro_export_service import (
        audit_intro_export_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service


def _odt_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


_HEADING_BREAK = "<text:line-break/>"


class AuditDetailedIntroPunctuationUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        self.workplace = settings_service.save_workplace(name="Provoz PUNCT-UX1")
        self.worker = settings_service.save_worker(
            first_name="Auditor",
            last_name="Punct",
        )

    def _create(self, **fields):
        payload = {
            "workplace_id": self.workplace.id,
            "workplace_name": self.workplace.name,
            "year": 2026,
        }
        payload.update(fields)
        return audit_service.create_audit(**payload)

    def _audit_with_history(self):
        earlier = self._create(
            year=2025,
            started_at=date(2025, 3, 1),
            finished_at=date(2025, 3, 2),
            title="Historický audit",
        )
        finding = finding_service.create(
            ENTITY_AUDITY,
            earlier.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Historické zjištění punct",
            status=FINDING_STATUS_OTEVRENE,
        )
        task = task_service.create_task(
            title="Historický úkol punct",
            responsible_person_id=self.worker.id,
            due_date=date(2025, 6, 1),
        )
        finding_service.update(finding.id, task_id=task.id)
        current = self._create(
            year=2026,
            started_at=date(2026, 8, 12),
            finished_at=date(2026, 8, 14),
            changes_since_last="Nová linka montáže.",
        )
        return earlier, current

    def test_detailed_content_xml_has_colon_headings(self) -> None:
        _earlier, current = self._audit_with_history()
        content = _odt_text(
            protokol_audit_service.generate_detailed_report_for_audit(current)
        )
        for heading in (
            AUDIT_INTRO_EXPORT_CHANGES_HEADING,
            AUDIT_INTRO_EXPORT_PREVIOUS_AUDITS_HEADING,
            AUDIT_INTRO_EXPORT_FINDINGS_HEADING,
            AUDIT_INTRO_EXPORT_TASKS_HEADING,
        ):
            self.assertIn(heading, content)
            self.assertIn(f"{heading}{_HEADING_BREAK}", content)

    def test_headings_without_colon_are_not_standalone(self) -> None:
        _earlier, current = self._audit_with_history()
        content = _odt_text(
            protokol_audit_service.generate_detailed_report_for_audit(current)
        )
        for label in (
            AUDIT_INTRO_CHANGES_LABEL,
            AUDIT_INTRO_PREVIOUS_AUDITS_GROUP,
            AUDIT_INTRO_FINDINGS_GROUP,
            AUDIT_INTRO_TASKS_GROUP,
        ):
            self.assertNotIn(f"{label}{_HEADING_BREAK}", content)
            self.assertIn(f"{label}:{_HEADING_BREAK}", content)

    def test_planned_2028_not_in_2026_detailed_intro(self) -> None:
        current = self._create(
            year=2026,
            started_at=date(2026, 8, 12),
            finished_at=date(2026, 8, 14),
        )
        planned = self._create(year=2028, planned_month=1, title="Plán 1/2028")
        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        self.assertNotIn(planned.id, [item.audit_id for item in history.previous_audits])
        intro = audit_intro_export_service.build_detailed_intro_text(current)
        self.assertNotIn(str(planned.number or planned.id), intro)
        content = _odt_text(
            protokol_audit_service.generate_detailed_report_for_audit(current)
        )
        self.assertNotIn(str(planned.number), content)

    def test_historical_content_unchanged(self) -> None:
        earlier, current = self._audit_with_history()
        intro = audit_intro_export_service.build_detailed_intro_text(current)
        self.assertIn(str(earlier.number or earlier.id), intro)
        self.assertIn("Historické zjištění punct", intro)
        self.assertIn("Historický úkol punct", intro)
        self.assertIn("Nová linka montáže.", intro)
        self.assertIn("Datum:", intro)
        self.assertIn("Stav:", intro)

    def test_no_extra_blank_paragraph_after_headings(self) -> None:
        _earlier, current = self._audit_with_history()
        intro = audit_intro_export_service.build_detailed_intro_text(current)
        for heading in (
            AUDIT_INTRO_EXPORT_CHANGES_HEADING,
            AUDIT_INTRO_EXPORT_PREVIOUS_AUDITS_HEADING,
            AUDIT_INTRO_EXPORT_FINDINGS_HEADING,
            AUDIT_INTRO_EXPORT_TASKS_HEADING,
        ):
            self.assertIn(f"{heading}\n\n", intro)
            self.assertNotIn(f"{heading}\n\n\n", intro)
        content = _odt_text(
            protokol_audit_service.generate_detailed_report_for_audit(current)
        )
        triple = f"{_HEADING_BREAK}{_HEADING_BREAK}{_HEADING_BREAK}"
        for heading in (
            AUDIT_INTRO_EXPORT_CHANGES_HEADING,
            AUDIT_INTRO_EXPORT_PREVIOUS_AUDITS_HEADING,
            AUDIT_INTRO_EXPORT_FINDINGS_HEADING,
            AUDIT_INTRO_EXPORT_TASKS_HEADING,
        ):
            self.assertNotIn(f"{heading}{triple}", content)

    def test_protocol_and_intro_tab_labels_unchanged(self) -> None:
        _earlier, current = self._audit_with_history()
        protocol_values = audit_export_context_service.build(
            current, config=PROTOCOL_DOCUMENT_CONFIG
        ).placeholder_values()
        self.assertNotIn("uvod_text", protocol_values)
        from PySide6.QtWidgets import QGroupBox

        from moduly.audity.ui.audit_workplace_history_widget import (
            AuditWorkplaceHistoryWidget,
        )

        widget = AuditWorkplaceHistoryWidget()
        widget.load_audit(current)
        widget.ensure_loaded()
        titles = [box.title() for box in widget.findChildren(QGroupBox)]
        self.assertIn(AUDIT_INTRO_CHANGES_LABEL, titles)
        self.assertIn(AUDIT_INTRO_PREVIOUS_AUDITS_GROUP, titles)
        self.assertNotIn(AUDIT_INTRO_EXPORT_CHANGES_HEADING, titles)
        self.assertNotIn(AUDIT_INTRO_EXPORT_PREVIOUS_AUDITS_HEADING, titles)
