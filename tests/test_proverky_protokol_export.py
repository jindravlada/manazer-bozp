import importlib
import tempfile
import unittest
import zipfile
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

    from core.shared.constants import (
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.proverky.constants import INSPECTION_STATUS_DOKONCENO
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
        bozp_inspection_export_context_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import (
        PROTOCOL_INCOMPLETE_WARNING,
        protokol_proverky_service,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


class ProverkyProtokolExportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

        settings_service.save_employer(
            ico="12345678",
            name="Test Zaměstnavatel s.r.o.",
            address="Praha 1",
            nace="62.01",
        )

    def _create_leader(self) -> int:
        worker = settings_service.save_worker(first_name="Jan", last_name="Novák")
        return worker.id

    def _create_inspection_with_leader(self, **fields):
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

    def test_generate_creates_odt_file(self) -> None:
        workplace = settings_service.save_workplace(name="Hala A")
        inspection = self._create_inspection_with_leader(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=3,
        )
        assert inspection is not None

        path = protokol_proverky_service.generate_for_inspection(inspection)

        self.assertTrue(path.exists())
        self.assertEqual(path.suffix.lower(), ".odt")

    def test_spis_values_in_output(self) -> None:
        workplace = settings_service.save_workplace(name="Sklad B")
        inspection = self._create_inspection_with_leader(
            year=2026,
            planned_month=5,
            inspection_date=date(2026, 5, 12),
            started_at=date(2026, 5, 10),
            inspection_type="Mimořádná",
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )
        assert inspection is not None

        path = protokol_proverky_service.generate_for_inspection(inspection)
        content = _odt_content(path)

        self.assertIn(inspection.number, content)
        self.assertIn("Test Zaměstnavatel s.r.o.", content)
        self.assertIn("Sklad B", content)
        self.assertIn("2026", content)
        self.assertIn("květen", content)
        self.assertIn("Mimořádná", content)
        self.assertIn("12.05.2026", content)
        self.assertIn("10.05.2026", content)
        self.assertIn("Probíhá", content)

    def test_commission_in_output(self) -> None:
        leader_id = self._create_leader()
        workplace_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        member_id = settings_service.save_worker(first_name="Petr", last_name="Svoboda").id
        union_id = person_service.create_person(first_name="Lucie", last_name="Horáková").id
        inspection = bozp_inspection_service.create_inspection()
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
                {
                    "record_type": "clen_komise",
                    "thp_worker_id": member_id,
                    "display_name": "Petr Svoboda",
                    "display_order": 30,
                    "active": True,
                },
            ],
        )
        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None

        path = protokol_proverky_service.generate_for_inspection(loaded)
        content = _odt_content(path)

        self.assertIn("Jan Novák", content)
        self.assertIn("Vedoucí komise", content)
        self.assertIn("Eva Králová", content)
        self.assertIn("Zástupce pracoviště", content)
        self.assertIn("Lucie Horáková", content)
        self.assertIn("Zástupce odborové organizace", content)
        self.assertIn("Petr Svoboda", content)
        self.assertIn("Člen komise", content)

    def test_findings_in_output(self) -> None:
        inspection = self._create_inspection_with_leader()
        assert inspection is not None
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Chybí ochranné prvky",
            source_area_label="BOZP obecně",
            status=FINDING_STATUS_OTEVRENE,
        )

        path = protokol_proverky_service.generate_for_inspection(inspection)
        content = _odt_content(path)

        self.assertIn("Chybí ochranné prvky", content)
        self.assertIn("BOZP obecně", content)
        self.assertIn("Otevřené", content)

    def test_tasks_in_output(self) -> None:
        inspection = self._create_inspection_with_leader()
        assert inspection is not None
        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Závada na výstupu",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_task_service.create_task_from_finding(finding.id)

        path = protokol_proverky_service.generate_for_inspection(inspection)
        content = _odt_content(path)

        self.assertNotIn("Nejsou evidována.", content.split("Úkoly")[-1][:200])
        self.assertIn("Aktivní", content)

    def test_empty_findings_and_tasks_no_error(self) -> None:
        inspection = self._create_inspection_with_leader()
        assert inspection is not None

        path = protokol_proverky_service.generate_for_inspection(inspection)
        content = _odt_content(path)

        self.assertTrue(path.exists())
        self.assertIn("Nejsou evidována.", content)

    def test_incomplete_warning(self) -> None:
        inspection = self._create_inspection_with_leader()
        assert inspection is not None

        warning = protokol_proverky_service.incomplete_warning(inspection)

        self.assertEqual(warning, PROTOCOL_INCOMPLETE_WARNING)

    def test_completed_no_warning(self) -> None:
        inspection = self._create_inspection_with_leader(
            started_at=date(2026, 4, 1),
            finished_at=date(2026, 4, 20),
        )
        assert inspection is not None
        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        self.assertEqual(loaded.status, INSPECTION_STATUS_DOKONCENO)

        warning = protokol_proverky_service.incomplete_warning(loaded)

        self.assertIsNone(warning)

    @patch("moduly.proverky.sluzby.protokol_proverky_service.subprocess.Popen")
    def test_open_for_inspection_calls_xdg_open(self, mock_popen) -> None:
        inspection = self._create_inspection_with_leader()
        assert inspection is not None

        path = protokol_proverky_service.open_for_inspection(inspection)

        mock_popen.assert_called_once()
        self.assertEqual(mock_popen.call_args.args[0][0], "xdg-open")
        self.assertEqual(mock_popen.call_args.args[0][1], str(path))

    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.QMessageBox.warning")
    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.protokol_proverky_service.open_for_inspection")
    def test_ui_incomplete_shows_warning(self, mock_open, mock_warning) -> None:
        from moduly.proverky.ui.bozp_inspection_conclusion_widget import BozpInspectionConclusionWidget

        inspection = self._create_inspection_with_leader()
        assert inspection is not None

        widget = BozpInspectionConclusionWidget()
        widget.load_inspection(inspection)
        widget._export_protocol()

        mock_warning.assert_called_once()
        mock_open.assert_called_once_with(inspection)

    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.QMessageBox.warning")
    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.protokol_proverky_service.open_for_inspection")
    def test_ui_completed_no_warning(self, mock_open, mock_warning) -> None:
        from moduly.proverky.ui.bozp_inspection_conclusion_widget import BozpInspectionConclusionWidget

        inspection = self._create_inspection_with_leader(
            started_at=date(2026, 4, 1),
            finished_at=date(2026, 4, 20),
        )
        assert inspection is not None
        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None

        widget = BozpInspectionConclusionWidget()
        widget.load_inspection(loaded)
        widget._export_protocol()

        mock_warning.assert_not_called()
        mock_open.assert_called_once_with(loaded)

    def test_unsaved_inspection_raises(self) -> None:
        from types import SimpleNamespace

        with self.assertRaises(ValueError):
            protokol_proverky_service.generate_for_inspection(SimpleNamespace(id=None))

    def test_context_placeholder_keys(self) -> None:
        inspection = self._create_inspection_with_leader()
        assert inspection is not None

        context = bozp_inspection_export_context_service.build(inspection)
        values = context.placeholder_values()

        expected_keys = {
            "cislo_proverky",
            "zamestnavatel_nazev",
            "pracoviste",
            "rok",
            "planovany_mesic",
            "typ_proverky",
            "datum_proverky",
            "datum_zahajeni",
            "datum_ukonceni",
            "stav",
            "komise_text",
            "zjisteni_text",
            "ukoly_text",
            "statistika_text",
            "souhrn_text",
            "datum_vygenerovani",
        }
        self.assertEqual(set(values.keys()), expected_keys)

    def test_statistics_in_output(self) -> None:
        from core.shared.constants import CONTROL_RESULT_VYHOVUJE

        workplace = settings_service.save_workplace(name="Statistika")
        inspection = self._create_inspection_with_leader(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )
        assert inspection is not None

        from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service

        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ControlPointContext(
                area_id="bozp",
                area_label="BOZP",
                section_id="sekce",
                section_label="Sekce",
                control_point_id="cp1",
                control_point_label="Bod 1",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )

        path = protokol_proverky_service.generate_for_inspection(inspection)
        content = _odt_content(path)

        self.assertIn("Počet kontrolovaných oblastí: 1", content)
        self.assertIn("Počet hodnocení Vyhovuje: 1", content)


if __name__ == "__main__":
    unittest.main()
