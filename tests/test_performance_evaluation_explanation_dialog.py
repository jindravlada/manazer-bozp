import importlib
import tempfile
import unittest
from datetime import date, timedelta
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
        CONTROL_RESULT_NEVYHOVUJE,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from core.shared.sluzby.performance_evaluation_methodology_service import RATING_RED
    from core.widgets.performance_evaluation_explanation_dialog import (
        PerformanceEvaluationExplanationDialog,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.constants import CONTROL_POINT_SEVERITY_KRITICKA
    from moduly.proverky.sluzby.bozp_annual_export_context_service import (
        bozp_annual_export_context_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.ui.rocni_zprava_dialog import RocniZpravaDialog
    from moduly.ukoly.sluzby.task_service import task_service


class PerformanceEvaluationExplanationDialogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_service.save_employer(
            ico="12345678",
            name="Test Zaměstnavatel s.r.o.",
            address="Praha 1",
            nace="62.01",
        )
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

        leader_id = settings_service.save_worker(first_name="Jan", last_name="Novák").id
        workplace_rep_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        union_id = person_service.create_person(first_name="Lucie", last_name="Horáková").id
        workplace = settings_service.save_workplace(name="Hala A")
        inspection = bozp_inspection_service.create_inspection(
            year=2026,
            inspection_date=date(2026, 3, 10),
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )
        bozp_inspection_commission_service.save_members(
            inspection.id,
            [
                {
                    "record_type": "vedouci_komise",
                    "thp_worker_id": leader_id,
                    "display_name": "Jan Novák",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": "zastupce_pracoviste",
                    "thp_worker_id": workplace_rep_id,
                    "display_name": "Eva Králová",
                    "display_order": 20,
                    "active": True,
                },
                {
                    "record_type": "zastupce_odboru",
                    "person_id": union_id,
                    "display_name": "Lucie Horáková",
                    "display_order": 30,
                    "active": True,
                },
            ],
        )

        with patch.object(
            bozp_annual_export_context_service,
            "_resolve_control_point_severity",
            return_value=CONTROL_POINT_SEVERITY_KRITICKA,
        ):
            control_result_service.set_result(
                ENTITY_PROVERKY,
                inspection.id,
                ControlPointContext(
                    area_id="bozp",
                    area_label="BOZP",
                    section_id="s1",
                    section_label="Sekce",
                    control_point_id="cp-crit",
                    control_point_label="Kritická závada",
                ),
                result=CONTROL_RESULT_NEVYHOVUJE,
            )
            finding = finding_service.create(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_ZJISTENI,
                description="Kritická závada po termínu",
                status=FINDING_STATUS_OTEVRENE,
                source_control_point_id="cp-crit",
            )
            task = finding_task_service.create_task_from_finding(finding.id)
            task_service.update_task(
                task.id,
                task.title,
                due_date=date.today() - timedelta(days=7),
            )

    def test_build_evaluation_explanation_for_year(self) -> None:
        explanation = bozp_annual_export_context_service.build_evaluation_explanation(2026)
        self.assertEqual(explanation.rating.level, RATING_RED)
        self.assertTrue(explanation.indicators)
        self.assertTrue(any(rule.applied for rule in explanation.rules))

    def test_dialog_recalculates_on_simulation_change(self) -> None:
        explanation = bozp_annual_export_context_service.build_evaluation_explanation(2026)
        dialog = PerformanceEvaluationExplanationDialog(explanation=explanation)
        dialog.sim_critical.setValue(0)
        dialog.sim_overdue.setValue(0)
        dialog._on_simulation_changed()
        self.assertNotEqual(dialog.rating_label.text(), "")

    def test_rocni_zprava_dialog_has_explanation_button(self) -> None:
        dialog = RocniZpravaDialog(year=2026)
        self.assertEqual(dialog.explanation_btn.text(), "🧠 Vysvětlení hodnocení")


if __name__ == "__main__":
    unittest.main()
