"""CONTROL-REPORT-RESULTS-OVERVIEW-3: Přehled výsledků v kontextech a ODT."""

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

_TMP = Path(tempfile.mkdtemp(prefix="control-report-results-overview-3-"))
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
        CONTROL_RESULT_NEKONTROLOVANO,
        CONTROL_RESULT_NELZE_POSOUDIT,
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_AUDITY,
        ENTITY_PROVERKY,
    )
    from core.shared.sluzby.control_activity_statistics_service import (
        ControlActivityStatistics,
        control_activity_statistics_service,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from moduly.audity.sluzby.audit_export_context_service import (
        AuditExportContext,
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
        InspectionExportContext,
        bozp_inspection_export_context_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service


REPO_ROOT = Path(__file__).resolve().parents[1]

_STATS_485 = ControlActivityStatistics(
    areas_checked=8,
    sections_checked=20,
    control_points_checked=485,
    ratings_vyhovuje=383,
    ratings_nevyhovuje=0,
    ratings_netyka_se=97,
    ratings_nehodnoceno=12,
    findings_total=5,
    tasks_total=5,
    ratings_vyhovuje_s_doporucenim=5,
)


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _overview_section(content: str) -> str:
    after = content.split("Přehled výsledků", 1)[1]
    for marker in ("Silné stránky", "Oblasti vyžadující pozornost"):
        if marker in after:
            return after.split(marker, 1)[0]
    return after


def _assert_overview_order(test: unittest.TestCase, text: str) -> None:
    pos_nevyhovuje = text.find("Nevyhovuje:")
    pos_nelze = text.find("Nelze posoudit:")
    pos_zjisteni = text.find("Zjištění:")
    test.assertGreaterEqual(pos_nevyhovuje, 0)
    test.assertGreaterEqual(pos_nelze, 0)
    test.assertGreaterEqual(pos_zjisteni, 0)
    test.assertLess(pos_nevyhovuje, pos_nelze)
    test.assertLess(pos_nelze, pos_zjisteni)
    test.assertNotIn("Netýká se", text)
    test.assertNotIn("Není relevantní", text)


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


class ControlReportResultsOverview3TestCase(unittest.TestCase):
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

    def _add_result(
        self,
        entity_type: str,
        entity_id: int,
        *,
        point_id: str,
        result: str,
    ) -> None:
        control_result_service.set_result(
            entity_type,
            entity_id,
            ControlPointContext(
                area_id="oblast",
                area_label="Oblast",
                section_id="sekce",
                section_label="Sekce",
                control_point_id=point_id,
                control_point_label=f"Bod {point_id}",
            ),
            result=result,
        )

    def test_inspection_485_overview_from_statistics(self) -> None:
        inspection = self._create_inspection()
        with patch.object(
            InspectionExportContext,
            "_activity_statistics",
            return_value=_STATS_485,
        ):
            text = bozp_inspection_export_context_service.build(
                inspection
            ).results_overview_text()
        self.assertIn("Kontrolních bodů: 485", text)
        self.assertIn("Vyhovuje: 383", text)
        self.assertIn("Vyhovuje s doporučením: 5", text)
        self.assertIn("Nevyhovuje: 0", text)
        self.assertIn("Nelze posoudit: 97", text)
        self.assertEqual(
            485,
            383 + 5 + 0 + 97,
        )
        _assert_overview_order(self, text)

    def test_audit_485_overview_from_statistics(self) -> None:
        audit = self._create_audit()
        with patch.object(
            AuditExportContext,
            "_activity_statistics",
            return_value=_STATS_485,
        ):
            text = audit_export_context_service.build(audit).results_overview_text()
        self.assertIn("Auditních tvrzení: 485", text)
        self.assertIn("Vyhovuje: 383", text)
        self.assertIn("Vyhovuje s doporučením: 5", text)
        self.assertIn("Nevyhovuje: 0", text)
        self.assertIn("Nelze posoudit: 97", text)
        _assert_overview_order(self, text)

    def test_inspection_unevaluated_excluded_from_checked_sum(self) -> None:
        inspection = self._create_inspection()
        self._add_result(
            ENTITY_PROVERKY, inspection.id, point_id="ok1", result=CONTROL_RESULT_VYHOVUJE
        )
        self._add_result(
            ENTITY_PROVERKY, inspection.id, point_id="ok2", result=CONTROL_RESULT_VYHOVUJE
        )
        self._add_result(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="pkz",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        self._add_result(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="na1",
            result=CONTROL_RESULT_NELZE_POSOUDIT,
        )
        self._add_result(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="na2",
            result=CONTROL_RESULT_NELZE_POSOUDIT,
        )
        self._add_result(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="skip",
            result=CONTROL_RESULT_NEKONTROLOVANO,
        )
        stats = control_activity_statistics_service.compute(
            ENTITY_PROVERKY, inspection.id
        )
        self.assertEqual(5, stats.control_points_checked)
        self.assertEqual(2, stats.ratings_vyhovuje)
        self.assertEqual(1, stats.ratings_vyhovuje_s_doporucenim)
        self.assertEqual(0, stats.ratings_nevyhovuje)
        self.assertEqual(2, stats.ratings_netyka_se)
        self.assertEqual(1, stats.ratings_nehodnoceno)
        self.assertEqual(
            stats.control_points_checked,
            stats.ratings_vyhovuje
            + stats.ratings_vyhovuje_s_doporucenim
            + stats.ratings_nevyhovuje
            + stats.ratings_netyka_se,
        )

        text = bozp_inspection_export_context_service.build(
            inspection
        ).results_overview_text()
        self.assertIn("Kontrolních bodů: 5", text)
        self.assertIn("Nelze posoudit: 2", text)
        self.assertNotIn("Nekontrolováno", text)
        self.assertNotIn("Nehodnoceno", text)

    def test_inspection_nelze_posoudit_zero_still_in_text(self) -> None:
        inspection = self._create_inspection()
        self._add_result(
            ENTITY_PROVERKY, inspection.id, point_id="ok", result=CONTROL_RESULT_VYHOVUJE
        )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).results_overview_text()
        self.assertIn("Nelze posoudit: 0", text)
        self.assertIn("Nevyhovuje: 0", text)

    def test_mismatch_does_not_crash_or_rewrite_values(self) -> None:
        inspection = self._create_inspection()
        broken = ControlActivityStatistics(
            areas_checked=1,
            sections_checked=1,
            control_points_checked=400,
            ratings_vyhovuje=383,
            ratings_nevyhovuje=0,
            ratings_netyka_se=97,
            ratings_nehodnoceno=0,
            findings_total=5,
            tasks_total=5,
            ratings_vyhovuje_s_doporucenim=5,
        )
        with patch.object(
            InspectionExportContext,
            "_activity_statistics",
            return_value=broken,
        ):
            with self.assertLogs(
                "core.shared.sluzby.control_report_overview",
                level="WARNING",
            ):
                text = bozp_inspection_export_context_service.build(
                    inspection
                ).results_overview_text()
        self.assertIn("Kontrolních bodů: 400", text)
        self.assertIn("Vyhovuje: 383", text)
        self.assertIn("Nelze posoudit: 97", text)
        self.assertNotIn("Kontrolních bodů: 485", text)

    def test_odt_all_four_outputs_contain_nelze_posoudit(self) -> None:
        inspection = self._create_inspection()
        self._add_result(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="na",
            result=CONTROL_RESULT_NELZE_POSOUDIT,
        )
        audit = self._create_audit()
        self._add_result(
            ENTITY_AUDITY,
            audit.id,
            point_id="na",
            result=CONTROL_RESULT_NELZE_POSOUDIT,
        )

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
            overview = _overview_section(content)
            self.assertIn("Nelze posoudit:", overview, msg=path.name)
            _assert_overview_order(self, overview)


if __name__ == "__main__":
    unittest.main()
