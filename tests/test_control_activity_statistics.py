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

    from core.shared.constants import (
        CONTROL_RESULT_NELZE_POSOUDIT,
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        ENTITY_AUDITY,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.control_activity_statistics_service import (
        ControlActivityStatistics,
        control_activity_statistics_service,
    )
    from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service


class ControlActivityStatisticsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _control_context(self, *, area: str, section: str, point_id: str) -> ControlPointContext:
        return ControlPointContext(
            area_id=area.lower().replace(" ", "_"),
            area_label=area,
            section_id=section.lower().replace(" ", "_"),
            section_label=section,
            control_point_id=point_id,
            control_point_label=f"Bod {point_id}",
        )

    def test_compute_for_proverky(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        ctx_a1 = self._control_context(area="BOZP", section="Sekce A", point_id="a1")
        ctx_a2 = self._control_context(area="BOZP", section="Sekce B", point_id="b1")
        ctx_b1 = self._control_context(area="Požár", section="Sekce C", point_id="c1")

        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ctx_a1,
            result=CONTROL_RESULT_VYHOVUJE,
        )
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ctx_a2,
            result=CONTROL_RESULT_NEVYHOVUJE,
        )
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ctx_b1,
            result=CONTROL_RESULT_NELZE_POSOUDIT,
        )
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            self._control_context(area="BOZP", section="Sekce A", point_id="a2"),
            result=CONTROL_RESULT_VYHOVUJE,
        )

        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Závada",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_task_service.create_task_from_finding(finding.id)

        stats = control_activity_statistics_service.compute(ENTITY_PROVERKY, inspection.id)

        self.assertEqual(stats.areas_checked, 2)
        self.assertEqual(stats.sections_checked, 3)
        self.assertEqual(stats.control_points_checked, 4)
        self.assertEqual(stats.ratings_vyhovuje, 2)
        self.assertEqual(stats.ratings_nevyhovuje, 1)
        self.assertEqual(stats.ratings_netyka_se, 1)
        self.assertEqual(stats.findings_total, 1)
        self.assertEqual(stats.tasks_total, 1)

    def test_compute_for_audit(self) -> None:
        audit = audit_service.create_audit()
        ctx = self._control_context(area="Proces", section="Kritérium", point_id="q1")
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ctx,
            result=CONTROL_RESULT_VYHOVUJE,
        )
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Neshoda",
            status=FINDING_STATUS_OTEVRENE,
        )

        stats = control_activity_statistics_service.compute(ENTITY_AUDITY, audit.id)

        self.assertEqual(stats.areas_checked, 1)
        self.assertEqual(stats.control_points_checked, 1)
        self.assertEqual(stats.findings_total, 1)

    def test_format_text_contains_required_labels(self) -> None:
        stats = ControlActivityStatistics(
            areas_checked=2,
            sections_checked=3,
            control_points_checked=5,
            ratings_vyhovuje=2,
            ratings_nevyhovuje=1,
            ratings_netyka_se=1,
            ratings_nehodnoceno=0,
            findings_total=1,
            tasks_total=1,
        )
        text = stats.format_text()

        self.assertIn("Počet kontrolovaných oblastí: 2", text)
        self.assertIn("Počet hodnocení Netýká se: 1", text)
        self.assertIn("Počet úkolů / opatření: 1", text)


if __name__ == "__main__":
    unittest.main()
