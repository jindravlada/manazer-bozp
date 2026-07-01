import importlib
import tempfile
import unittest
from datetime import date
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

    from moduly.proverky.constants import (
        INSPECTION_STATUS_DOKONCENO,
        INSPECTION_STATUS_PLANOVANO,
        INSPECTION_STATUS_PROBIHA,
    )
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class ProverkyLifecycleTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

    def _create_leader(self) -> int:
        worker = settings_service.save_worker(first_name="Jan", last_name="Novák")
        return worker.id

    def _create_inspection_with_commission(self, **fields):
        leader_id = self._create_leader()
        workplace_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        union_id = person_service.create_person(first_name="Lucie", last_name="Horáková").id
        inspection = bozp_inspection_service.create_inspection(**fields)
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
                    "thp_worker_id": workplace_id,
                    "display_name": "Eva Králová",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": "zastupce_odboru",
                    "person_id": union_id,
                    "display_name": "Lucie Horáková",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        return bozp_inspection_service.get_by_id(inspection.id)

    def _create_inspection_with_leader(self, **fields):
        return self._create_inspection_with_commission(**fields)

    def test_derive_status_rules(self) -> None:
        self.assertEqual(
            bozp_inspection_service.derive_status(None, None),
            INSPECTION_STATUS_PLANOVANO,
        )
        self.assertEqual(
            bozp_inspection_service.derive_status(date(2026, 3, 1), None),
            INSPECTION_STATUS_PROBIHA,
        )
        self.assertEqual(
            bozp_inspection_service.derive_status(None, date(2026, 3, 15)),
            INSPECTION_STATUS_DOKONCENO,
        )
        self.assertEqual(
            bozp_inspection_service.derive_status(date(2026, 3, 1), date(2026, 3, 15)),
            INSPECTION_STATUS_DOKONCENO,
        )

    def test_new_inspection_planned_with_month_and_workplace(self) -> None:
        workplace = settings_service.save_workplace(name="Hala A")
        inspection = bozp_inspection_service.create_inspection(
            planned_month=6,
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )

        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        self.assertEqual(loaded.status, INSPECTION_STATUS_PLANOVANO)
        self.assertIsNone(loaded.started_at)
        self.assertIsNone(loaded.finished_at)

    def test_inspection_date_does_not_change_status(self) -> None:
        workplace = settings_service.save_workplace(name="Hala B")
        inspection = bozp_inspection_service.create_inspection(
            planned_month=6,
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )
        updated = bozp_inspection_service.update_inspection(
            inspection.id,
            inspection_date=date(2026, 6, 20),
        )

        assert updated is not None
        self.assertEqual(updated.status, INSPECTION_STATUS_PLANOVANO)

    def test_started_at_sets_in_progress(self) -> None:
        inspection = bozp_inspection_service.create_inspection(planned_month=4)
        bozp_inspection_service.update_inspection(
            inspection.id,
            started_at=date(2026, 4, 10),
        )

        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        self.assertEqual(loaded.status, INSPECTION_STATUS_PROBIHA)

    def test_finished_at_sets_completed(self) -> None:
        inspection = bozp_inspection_service.create_inspection(planned_month=4)
        bozp_inspection_service.update_inspection(
            inspection.id,
            started_at=date(2026, 4, 10),
        )
        bozp_inspection_service.update_inspection(
            inspection.id,
            finished_at=date(2026, 4, 20),
        )

        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        self.assertEqual(loaded.status, INSPECTION_STATUS_DOKONCENO)

    def test_clear_finished_at_returns_to_in_progress(self) -> None:
        inspection = bozp_inspection_service.create_inspection(planned_month=4)
        bozp_inspection_service.update_inspection(
            inspection.id,
            started_at=date(2026, 4, 10),
            finished_at=date(2026, 4, 20),
        )
        updated = bozp_inspection_service.update_inspection(
            inspection.id,
            finished_at=None,
        )

        assert updated is not None
        self.assertEqual(updated.status, INSPECTION_STATUS_PROBIHA)
        self.assertIsNone(updated.finished_at)

    def test_clear_started_and_finished_returns_to_planned(self) -> None:
        inspection = bozp_inspection_service.create_inspection(planned_month=4)
        bozp_inspection_service.update_inspection(
            inspection.id,
            started_at=date(2026, 4, 10),
            finished_at=date(2026, 4, 20),
        )
        updated = bozp_inspection_service.update_inspection(
            inspection.id,
            started_at=None,
            finished_at=None,
        )

        assert updated is not None
        self.assertEqual(updated.status, INSPECTION_STATUS_PLANOVANO)

    def test_manual_status_is_ignored_on_save(self) -> None:
        inspection = bozp_inspection_service.create_inspection(planned_month=4)
        updated = bozp_inspection_service.update_inspection(
            inspection.id,
            status=INSPECTION_STATUS_PROBIHA,
        )

        assert updated is not None
        self.assertEqual(updated.status, INSPECTION_STATUS_PLANOVANO)

    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.QMessageBox.question")
    def test_complete_button_sets_finished_at_and_status(self, mock_question) -> None:
        from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog

        inspection = self._create_inspection_with_commission()
        bozp_inspection_service.update_inspection(
            inspection.id,
            started_at=date(2026, 5, 1),
        )

        dialog = BozpInspectionDialog(inspection=inspection)
        dialog.conclusion_widget._complete_inspection()

        mock_question.assert_not_called()
        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        self.assertEqual(loaded.finished_at, date.today())
        self.assertEqual(loaded.status, INSPECTION_STATUS_DOKONCENO)


if __name__ == "__main__":
    unittest.main()
