"""AUDIT-REPORT-1 – podrobná zpráva z interního auditu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="audit-report-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.export.odt_engine import ODT_IMAGE_MARKER_RE
    from core.shared.constants import (
        CONTROL_RESULT_NELZE_POSOUDIT,
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_AUDITY,
        FINDING_TYPE_PRILEZITOST,
    )
    from core.shared.modely.control_result import ControlResult
    from core.shared.modely.finding import Finding
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.sluzby.finding_service import finding_service
    from moduly.audity.constants import (
        AUDIT_DETAILED_REPORT_BUTTON_LABEL,
        AUDIT_PROTOCOL_BUTTON_LABEL,
    )
    from moduly.audity.sluzby.audit_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG,
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.audity.ui.audit_conclusion_widget import AuditConclusionWidget
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _odt_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


class AudityDetailedReportExportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(Finding))
            session.execute(delete(ControlResult))
            session.commit()
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _create_finished_audit(self):
        workplace = settings_service.save_workplace(name="Provoz Report")
        return audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=7,
            started_at=date(2026, 7, 1),
            finished_at=date(2026, 7, 10),
        )

    def _set_result(self, audit_id: int, *, control_point_id: str, label: str, result: str, note: str = ""):
        return control_result_service.set_result(
            ENTITY_AUDITY,
            audit_id,
            ControlPointContext(
                area_id="rizeni_rizik",
                area_label="Řízení rizik",
                section_id="sekce",
                section_label="Sekce",
                control_point_id=control_point_id,
                control_point_label=label,
            ),
            result=result,
            note=note,
        )

    def test_conclusion_widget_has_both_export_buttons(self) -> None:
        widget = AuditConclusionWidget()
        self.assertEqual(widget.protocol_btn.text(), AUDIT_PROTOCOL_BUTTON_LABEL)
        self.assertEqual(
            widget.detailed_report_btn.text(),
            AUDIT_DETAILED_REPORT_BUTTON_LABEL,
        )

    def test_protocol_unchanged_summary_assertions_and_signatures(self) -> None:
        audit = self._create_finished_audit()
        self._set_result(
            audit.id,
            control_point_id="t1",
            label="Tvrzení jedna",
            result=CONTROL_RESULT_VYHOVUJE,
            note="Nemá být v protokolu u tvrzení",
        )
        context = audit_export_context_service.build(
            audit, config=PROTOCOL_DOCUMENT_CONFIG
        )
        appendix = context.appendix_assertions_text().plain_text()
        self.assertIn("🟢 Tvrzení jedna", appendix)
        self.assertNotIn("Vyhovuje", appendix.split("Tvrzení jedna", 1)[-1][:20])
        self.assertNotIn("Poznámka auditora", appendix)
        self.assertTrue(context.signatures_text().strip())
        self.assertIn("podpis", context.signatures_text())

        path = protokol_audit_service.generate_for_audit(audit)
        text = _odt_text(path)
        self.assertIn("Tvrzení jedna", text)
        self.assertNotIn("Poznámka auditora", text)

    def test_detailed_report_hides_signatures(self) -> None:
        audit = self._create_finished_audit()
        context = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        )
        values = context.placeholder_values()
        self.assertEqual(values["podpisy_text"], "")
        self.assertEqual(values["podpis_odboru_blok"], "")

        path = protokol_audit_service.generate_detailed_report_for_audit(audit)
        text = _odt_text(path)
        self.assertIn("PODROBNÁ ZPRÁVA", text)
        self.assertNotIn("Podpisy", text)
        self.assertNotIn(">podpis<", text)

    def test_detailed_assertions_same_ids_as_protocol_with_word_result(self) -> None:
        audit = self._create_finished_audit()
        self._set_result(
            audit.id,
            control_point_id="t_ok",
            label="Stejné tvrzení",
            result=CONTROL_RESULT_VYHOVUJE,
        )
        self._set_result(
            audit.id,
            control_point_id="t_na",
            label="Není relevantní tvrzení",
            result=CONTROL_RESULT_NELZE_POSOUDIT,
        )

        protocol = audit_export_context_service.build(
            audit, config=PROTOCOL_DOCUMENT_CONFIG
        ).summary_appendix_assertions_text()
        detailed = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).detailed_appendix_assertions_text()

        self.assertIn("Stejné tvrzení", protocol)
        self.assertIn("Stejné tvrzení", detailed)
        self.assertIn("🟢 Stejné tvrzení — Vyhovuje", detailed)
        self.assertIn("⚪ Není relevantní tvrzení — Není relevantní", detailed)

    def test_note_printed_only_when_present(self) -> None:
        audit = self._create_finished_audit()
        self._set_result(
            audit.id,
            control_point_id="with_note",
            label="S poznámkou",
            result=CONTROL_RESULT_VYHOVUJE,
            note="Kontrola na místě",
        )
        self._set_result(
            audit.id,
            control_point_id="no_note",
            label="Bez poznámky",
            result=CONTROL_RESULT_VYHOVUJE,
            note="",
        )
        detailed = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).detailed_appendix_assertions_text()

        self.assertIn("Poznámka auditora:", detailed)
        self.assertIn("Kontrola na místě", detailed)
        self.assertNotIn("    Poznámka auditora:", detailed)
        with_note = detailed[
            detailed.index("🟢 S poznámkou") : detailed.index("Kontrola na místě") + 20
        ]
        self.assertIn("Poznámka auditora:", with_note)
        without_note = detailed[
            detailed.index("🟢 Bez poznámky") : detailed.index("🟢 S poznámkou")
        ]
        self.assertNotIn("Poznámka auditora", without_note)

    def test_recommendation_only_for_partial_result(self) -> None:
        audit = self._create_finished_audit()
        self._set_result(
            audit.id,
            control_point_id="pkz_1",
            label="S doporučením",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            note="Doplnit školení",
        )
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_PRILEZITOST,
            description="PKZ",
            source_control_point_id="pkz_1",
            source_control_point_label="S doporučením",
            recommended_action="Proškolit směnu A",
        )
        self._set_result(
            audit.id,
            control_point_id="fail_1",
            label="Neshoda",
            result=CONTROL_RESULT_NEVYHOVUJE,
            note="Jen poznámka",
        )

        detailed = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).detailed_appendix_assertions_text()

        self.assertIn("🟡 S doporučením — Vyhovuje s doporučením", detailed)
        self.assertIn("Doporučení:", detailed)
        self.assertIn("Proškolit směnu A", detailed)
        fail_start = detailed.index("🔴 Neshoda")
        fail_end = detailed.index("🟡 S doporučením")
        fail_block = detailed[fail_start:fail_end]
        self.assertNotIn("Doporučení:", fail_block)
        self.assertIn("Poznámka auditora:", fail_block)

    def test_photo_under_correct_assertion_and_order(self) -> None:
        from core.services.control_result_photo_service import (
            control_result_photo_service,
        )

        audit = self._create_finished_audit()
        relative_photo = control_result_photo_service.relative_photo_path(
            ENTITY_AUDITY,
            audit.id,
            area_id="rizeni_rizik",
            section_id="sekce",
            control_point_id="photo_cp",
        )
        photo_path = control_result_photo_service.absolute_photo_path(relative_photo)
        photo_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (80, 60), color=(20, 120, 200)).save(
            photo_path, format="JPEG"
        )

        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="rizeni_rizik",
                area_label="Řízení rizik",
                section_id="sekce",
                section_label="Sekce",
                control_point_id="photo_cp",
                control_point_label="Tvrzení s fotkou",
            ),
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            note="Poznámka pod doporučením",
            photo_path=relative_photo,
        )

        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_PRILEZITOST,
            description="PKZ",
            source_control_point_id="photo_cp",
            source_control_point_label="Tvrzení s fotkou",
            recommended_action="Doporučení text",
        )

        self._set_result(
            audit.id,
            control_point_id="no_photo",
            label="Bez fotky",
            result=CONTROL_RESULT_VYHOVUJE,
        )

        detailed = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).detailed_appendix_assertions_text()

        self.assertIn("🟢 Bez fotky — Vyhovuje", detailed)
        self.assertIn("🟡 Tvrzení s fotkou — Vyhovuje s doporučením", detailed)
        self.assertRegex(detailed, ODT_IMAGE_MARKER_RE.pattern)

        assertion_idx = detailed.index("🟡 Tvrzení s fotkou")
        rec_idx = detailed.index("Doporučení:", assertion_idx)
        note_idx = detailed.index("Poznámka auditora:", assertion_idx)
        img_idx = detailed.index("[[[ODT_IMAGE|", assertion_idx)
        no_photo_idx = detailed.index("🟢 Bez fotky")

        # Pořadí: tvrzení → doporučení → poznámka → fotografie
        self.assertLess(assertion_idx, rec_idx)
        self.assertLess(rec_idx, note_idx)
        self.assertLess(note_idx, img_idx)
        # Fotografie patří k tvrzení s fotkou, ne k „Bez fotky“
        self.assertLess(no_photo_idx, assertion_idx)
        self.assertGreater(img_idx, assertion_idx)

        path = protokol_audit_service.generate_detailed_report_for_audit(audit)
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            self.assertTrue(any(name.startswith("Pictures/") for name in names))
            content = archive.read("content.xml").decode("utf-8")
        self.assertIn("draw:image", content)
        self.assertIn("Tvrzení s fotkou", content)


if __name__ == "__main__":
    unittest.main()
