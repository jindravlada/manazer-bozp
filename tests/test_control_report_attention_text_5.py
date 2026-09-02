"""CONTROL-REPORT-ATTENTION-TEXT-5: věcný popis oblastí vyžadujících pozornost."""

from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="control-report-attention-text-5-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_AUDITY,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.control_report_language import FINDINGS_OVERVIEW_EMPTY_SENTENCE
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.sluzby.audit_export_context_service import (
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
        bozp_inspection_export_context_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service
    from moduly.ukoly.sluzby.task_service import task_service


REPO_ROOT = Path(__file__).resolve().parents[1]
EMPTY_OVERVIEW = FINDINGS_OVERVIEW_EMPTY_SENTENCE
POSITIVE_HP = "Hasicí přístroj je správně označen."
PROBLEM_HP = "Hasicí přístroj v místnosti váhy není dostatečně viditelný."
POSITIVE_DOC = "Dokumentace je pravidelně aktualizována."
PROBLEM_DOC = "Provozní postup nebyl aktualizován po změně technologie."


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _attention_section(content: str) -> str:
    after = content.split("Oblasti vyžadující pozornost", 1)[1]
    for marker in ("Podrobný přehled zjištění", "Doporučení vedoucího"):
        if marker in after:
            return after.split(marker, 1)[0]
    return after


def _findings_section(content: str) -> str:
    after = content.split("Podrobný přehled zjištění", 1)[1]
    for marker in ("Doporučení vedoucího prověrky", "Doporučení vedoucího auditora"):
        if marker in after:
            return after.split(marker, 1)[0]
    return after


def _sync_templates() -> None:
    import moduly.audity.sluzby.protokol_audit_service as audit_protokol
    import moduly.proverky.sluzby.protokol_proverky_service as inspection_protokol

    importlib.reload(inspection_protokol)
    importlib.reload(audit_protokol)
    pairs = (
        (
            REPO_ROOT / "moduly" / "proverky" / "templates" / "exporty",
            inspection_protokol.protokol_proverky_service,
            ("ProtokolProverkyBOZP.odt", "PodrobnaZpravaProverky.odt"),
        ),
        (
            REPO_ROOT / "moduly" / "audity" / "templates" / "exporty",
            audit_protokol.protokol_audit_service,
            ("ProtokolAudit.odt", "PodrobnaZpravaAudit.odt"),
        ),
    )
    for bundled_root, service, names in pairs:
        for name in names:
            target = service.template_path(detailed="Podrobna" in name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_root / name, target)


class ControlReportAttentionText5TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        _sync_templates()

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _create_inspection(self):
        workplace = settings_service.save_workplace(name="Poříčí")
        return bozp_inspection_service.create_inspection(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=1,
            started_at=date(2026, 1, 10),
            finished_at=date(2026, 1, 12),
            notes_mode=None,
        )

    def _create_audit(self):
        workplace = settings_service.save_workplace(name="Provoz Audit")
        return audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=2,
            started_at=date(2026, 2, 1),
            finished_at=date(2026, 2, 3),
            notes_mode=None,
        )

    def _set_point(
        self,
        entity_type: str,
        entity_id: int,
        *,
        point_id: str,
        result: str,
        label: str,
        area: str = "Požární ochrana",
        section: str = "Hasicí přístroje",
        note: str = "",
    ) -> None:
        control_result_service.set_result(
            entity_type,
            entity_id,
            ControlPointContext(
                area_id="oblast",
                area_label=area,
                section_id="sekce",
                section_label=section,
                control_point_id=point_id,
                control_point_label=label,
            ),
            result=result,
            note=note,
        )

    def test_inspection_uses_finding_description(self) -> None:
        inspection = self._create_inspection()
        self._set_point(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="hp1",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            label=POSITIVE_HP,
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description=PROBLEM_HP,
            source_control_point_id="hp1",
            status=FINDING_STATUS_OTEVRENE,
        )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).attention_areas_text()
        self.assertEqual(f"🟡 {PROBLEM_HP}", text)
        self.assertNotIn(POSITIVE_HP, text)

    def test_audit_uses_finding_description(self) -> None:
        audit = self._create_audit()
        self._set_point(
            ENTITY_AUDITY,
            audit.id,
            point_id="doc1",
            result=CONTROL_RESULT_NEVYHOVUJE,
            label=POSITIVE_DOC,
            area="Řízení dokumentace",
            section="Aktualizace",
        )
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description=PROBLEM_DOC,
            source_control_point_id="doc1",
            status=FINDING_STATUS_OTEVRENE,
        )
        text = audit_export_context_service.build(audit).attention_areas_text()
        self.assertEqual(f"🔴 {PROBLEM_DOC}", text)
        self.assertNotIn(POSITIVE_DOC, text)

    def test_multiple_findings_and_duplicates(self) -> None:
        inspection = self._create_inspection()
        self._set_point(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="hp1",
            result=CONTROL_RESULT_NEVYHOVUJE,
            label=POSITIVE_HP,
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            description="První problém.",
            source_control_point_id="hp1",
            display_order=1,
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            description="Druhý problém.",
            source_control_point_id="hp1",
            display_order=2,
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            description="První problém.",
            source_control_point_id="hp1",
            display_order=3,
        )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).attention_areas_text()
        self.assertEqual("🔴 První problém.\n🔴 Druhý problém.", text)

    def test_recommended_action_and_note_and_task_fallbacks(self) -> None:
        inspection = self._create_inspection()
        self._set_point(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="hp_note",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            label=POSITIVE_HP,
            note="Přístroj je za skříní.",
        )
        self._set_point(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="hp_action",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            label=POSITIVE_HP,
            area="OOPP",
            section="Přilby",
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            description="",
            recommended_action="Doplnit označení HP.",
            source_control_point_id="hp_action",
        )
        self._set_point(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="hp_task",
            result=CONTROL_RESULT_NEVYHOVUJE,
            label=POSITIVE_HP,
            area="Únikové cesty",
            section="Značení",
        )
        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            description="",
            recommended_action="",
            source_control_point_id="hp_task",
        )
        task = finding_task_service.create_task_from_finding(finding.id)
        task_service.update_task(task.id, title="Zajistit viditelnost HP")

        text = bozp_inspection_export_context_service.build(
            inspection
        ).attention_areas_text()
        self.assertIn("🔴 Zajistit viditelnost HP", text)
        self.assertIn("🟡 Přístroj je za skříní.", text)
        self.assertIn("🟡 Doplnit označení HP.", text)
        self.assertNotIn(POSITIVE_HP, text)

    def test_neutral_fallback_and_icons(self) -> None:
        inspection = self._create_inspection()
        self._set_point(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="hp1",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            label=POSITIVE_HP,
        )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).attention_areas_text()
        self.assertEqual(
            "🟡 Požární ochrana — Hasicí přístroje (Vyhovuje s doporučením)",
            text,
        )
        self.assertNotIn(POSITIVE_HP, text)

    def test_no_n_plus_one_on_task_fallback(self) -> None:
        inspection = self._create_inspection()
        for index in range(5):
            point_id = f"hp{index}"
            self._set_point(
                ENTITY_PROVERKY,
                inspection.id,
                point_id=point_id,
                result=CONTROL_RESULT_NEVYHOVUJE,
                label=POSITIVE_HP,
            )
            finding = finding_service.create(
                ENTITY_PROVERKY,
                inspection.id,
                description="",
                recommended_action="",
                source_control_point_id=point_id,
            )
            finding_task_service.create_task_from_finding(finding.id)

        context = bozp_inspection_export_context_service.build(inspection)
        with patch.object(
            task_service,
            "get_task_by_id",
            side_effect=AssertionError("N+1 get_task_by_id"),
        ):
            text = context.attention_areas_text()
        self.assertEqual(5, text.count("🔴"))
        self.assertNotIn(POSITIVE_HP, text)

    def test_empty_findings_overview_sentence(self) -> None:
        inspection = self._create_inspection()
        audit = self._create_audit()
        inspection_text = bozp_inspection_export_context_service.build(
            inspection
        ).findings_overview_text()
        audit_text = audit_export_context_service.build(audit).evaluation_text()
        self.assertEqual(EMPTY_OVERVIEW, inspection_text)
        self.assertEqual(EMPTY_OVERVIEW, audit_text)

        outputs = (
            protokol_proverky_service.generate_for_inspection(inspection),
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            ),
            protokol_audit_service.generate_for_audit(audit),
            protokol_audit_service.generate_detailed_report_for_audit(audit),
        )
        for path in outputs:
            content = _odt_content(path)
            self.assertIn(EMPTY_OVERVIEW, _findings_section(content), msg=path.name)
            folded = content.casefold()
            self.assertNotIn("významná zjištění", folded, msg=path.name)
            self.assertNotIn("významných zjištění", folded, msg=path.name)

    def test_yearly_reports_keep_significant_findings_wording(self) -> None:
        for path in (
            REPO_ROOT / "moduly" / "proverky" / "templates" / "exporty" / "RocniZpravaBOZP.odt",
            REPO_ROOT / "moduly" / "audity" / "templates" / "exporty" / "RocniZpravaAuditu.odt",
        ):
            xml = _odt_content(path)
            self.assertIn("Příloha – Významná zjištění", xml, msg=path.name)
            self.assertNotIn(EMPTY_OVERVIEW, xml, msg=path.name)

    def test_odt_attention_uses_finding_not_question(self) -> None:
        inspection = self._create_inspection()
        self._set_point(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="hp1",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            label=POSITIVE_HP,
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            description=PROBLEM_HP,
            source_control_point_id="hp1",
        )
        audit = self._create_audit()
        self._set_point(
            ENTITY_AUDITY,
            audit.id,
            point_id="doc1",
            result=CONTROL_RESULT_NEVYHOVUJE,
            label=POSITIVE_DOC,
            area="Řízení dokumentace",
            section="Aktualizace",
        )
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            description=PROBLEM_DOC,
            source_control_point_id="doc1",
        )

        inspection_paths = (
            protokol_proverky_service.generate_for_inspection(inspection),
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            ),
        )
        audit_paths = (
            protokol_audit_service.generate_for_audit(audit),
            protokol_audit_service.generate_detailed_report_for_audit(audit),
        )
        for path in inspection_paths:
            section = _attention_section(_odt_content(path))
            self.assertIn(PROBLEM_HP, section, msg=path.name)
            self.assertNotIn(POSITIVE_HP, section, msg=path.name)
            self.assertIn("🟡", section)
        for path in audit_paths:
            section = _attention_section(_odt_content(path))
            self.assertIn(PROBLEM_DOC, section, msg=path.name)
            self.assertNotIn(POSITIVE_DOC, section, msg=path.name)
            self.assertIn("🔴", section)


if __name__ == "__main__":
    unittest.main()
