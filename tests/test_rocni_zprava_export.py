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
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.proverky.sluzby.bozp_annual_export_context_service import (
        bozp_annual_export_context_service,
    )
    from moduly.proverky.sluzby.bozp_annual_report_service import bozp_annual_report_service
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.rocni_zprava_service import rocni_zprava_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _ensure_annual_report_template() -> Path:
    import shutil

    path = rocni_zprava_service.template_path()
    bundled = (
        Path(__file__).resolve().parents[1]
        / "moduly"
        / "proverky"
        / "templates"
        / "exporty"
        / "RocniZpravaBOZP.odt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if bundled.exists():
        shutil.copy2(bundled, path)
    return path


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


class RocniZpravaExportTestCase(unittest.TestCase):
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
        settings_service.save_worker(
            first_name="Petr",
            last_name="Specialista",
            performs_controls=True,
        )
        self.preparer_worker = next(
            worker
            for worker in settings_service.get_workers()
            if worker.last_name == "Specialista"
        )
        _ensure_annual_report_template()

    def _create_inspection_with_commission(self, **fields):
        leader_id = settings_service.save_worker(first_name="Jan", last_name="Novák").id
        workplace_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        union_id = person_service.create_person(first_name="Lucie", last_name="Horáková").id
        workplace = settings_service.save_workplace(name=fields.pop("workplace_name", "Hala A"))
        inspection = bozp_inspection_service.create_inspection(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            **fields,
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
                    "thp_worker_id": workplace_id,
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
        return bozp_inspection_service.get_by_id(inspection.id)

    def test_generate_creates_odt_file(self) -> None:
        self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 3, 10))
        path = rocni_zprava_service.generate_for_year(2026)
        self.assertTrue(path.exists())
        self.assertEqual(path.suffix.lower(), ".odt")

    def test_context_placeholder_keys(self) -> None:
        self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 3, 10))
        bozp_annual_report_service.save_for_year(
            2026,
            silne_stranky="Dobrá dokumentace",
            top_priority="Snížit počet neshod",
            doporuceni_specialisty="Pokračovat v preventivních kontrolách",
        )
        context = bozp_annual_export_context_service.build(2026)
        values = context.placeholder_values()

        expected_keys = {
            "rok",
            "organizace",
            "obdobi",
            "datum_vytvoreni",
            "datum_vygenerovani",
            "zpracoval",
            "celkove_hodnoceni_text",
            "prehled_vysledku_text",
            "silne_stranky_text",
            "oblasti_pozornosti_text",
            "vyvoj_text",
            "top_priority_text",
            "doporuceni_specialisty",
            "priloha_proverky_text",
            "priloha_zjisteni_text",
            "priloha_opatreni_text",
            "priloha_otevrena_opatreni_text",
            "statistika_text",
            "souhrn_text",
            "zamestnavatel_nazev",
            "pocet_proverek",
            "pocet_pracovist",
            "pocet_oblasti",
            "pocet_kontrolnich_bodu",
            "trendy_text",
            "grafy_text",
            "top10_zavad_text",
            "problemova_pracoviste_text",
            "priciny_zavad_text",
        }
        self.assertEqual(set(values.keys()), expected_keys)

    def test_management_report_structure_in_output(self) -> None:
        inspection = self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 3, 10))
        assert inspection is not None
        bozp_annual_report_service.save_for_year(
            2026,
            zpracoval_worker_id=self.preparer_worker.id,
        )

        path = rocni_zprava_service.generate_for_year(2026)
        content = _odt_content(path)

        for heading in (
            "ROČNÍ ZPRÁVA O STAVU BOZP",
            "Základní informace",
            "CELKOVÉ HODNOCENÍ",
            "Přehled výsledků",
            "Silné stránky systému",
            "Oblasti vyžadující pozornost",
            "Vývoj oproti minulému roku",
            "TOP priority na příští rok",
            "Doporučení specialisty BOZP",
            "Příloha – Seznam prověrek",
            "Příloha – Významná zjištění",
            "Příloha – Uložená opatření",
            "Příloha – Otevřená opatření",
        ):
            self.assertIn(heading, content)

        self.assertIn("Test Zaměstnavatel s.r.o.", content)
        self.assertIn("Petr Specialista", content)

    def test_export_without_preparer_does_not_auto_fill_name(self) -> None:
        self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 3, 10))

        context = bozp_annual_export_context_service.build(2026)
        self.assertEqual(context.manual.zpracoval, "")
        self.assertEqual(context.placeholder_values()["zpracoval"], "—")

        path = rocni_zprava_service.generate_for_year(2026)
        content = _odt_content(path)
        self.assertNotIn("Petr Specialista", content)

    def test_aggregated_statistics_and_attention_areas(self) -> None:
        inspection = self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 4, 1))
        assert inspection is not None

        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ControlPointContext(
                area_id="bozp",
                area_label="BOZP",
                section_id="s1",
                section_label="Sekce",
                control_point_id="cp1",
                control_point_label="Chybí označení únikových východů.",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
        )
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ControlPointContext(
                area_id="bozp",
                area_label="BOZP",
                section_id="s1",
                section_label="Sekce",
                control_point_id="cp2",
                control_point_label="Evidence preventivních opatření není vždy úplná.",
            ),
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        bozp_annual_report_service.save_for_year(
            2026,
            silne_stranky="Funkční organizace práce.",
            top_priority="Snížit počet neshod",
            doporuceni_specialisty="Dokončit otevřená opatření",
        )

        path = rocni_zprava_service.generate_for_year(2026)
        content = _odt_content(path)

        self.assertIn("Počet prověrek: 1", content)
        self.assertIn("Nevyhovuje: 1", content)
        self.assertIn("✔ Funkční organizace práce.", content)
        self.assertIn("🔴 Chybí označení únikových východů.", content)
        self.assertIn("🟡 Evidence preventivních opatření není vždy úplná.", content)
        self.assertIn("Jedná se o první hodnocené období.", content)

    def test_year_comparison_when_previous_year_exists(self) -> None:
        self._create_inspection_with_commission(year=2025, inspection_date=date(2025, 2, 1))
        inspection = self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 2, 1))
        assert inspection is not None
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ControlPointContext(
                area_id="bozp",
                area_label="BOZP",
                section_id="s1",
                section_label="Sekce",
                control_point_id="cp1",
                control_point_label="Neshoda",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
        )

        context = bozp_annual_export_context_service.build(2026)
        self.assertIn("Prověrky:", context.comparison.text)
        self.assertNotIn("první hodnocené období", context.comparison.text)

    def test_appendix_findings_and_tasks(self) -> None:
        inspection = self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 6, 1))
        assert inspection is not None
        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Chybí ochranné prvky",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_task_service.create_task_from_finding(finding.id)

        path = rocni_zprava_service.generate_for_year(2026)
        content = _odt_content(path)

        self.assertIn("Chybí ochranné prvky", content)
        self.assertIn("Počet uložených opatření: 1", content)

    @patch("moduly.proverky.ui.rocni_zprava_dialog.rocni_zprava_service.open_for_year")
    def test_dialog_create_calls_service(self, mock_open) -> None:
        from moduly.proverky.ui.rocni_zprava_dialog import RocniZpravaDialog

        self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 3, 10))
        dialog = RocniZpravaDialog(year=2026)
        dialog.silne_stranky_edit.setPlainText("Silná stránka")
        dialog.top_priority_edit.setPlainText("Priorita")
        dialog.doporuceni_edit.setPlainText("Doporučení")
        dialog.zpracoval_selector.set_person_id(self.preparer_worker.id)
        dialog._create_report()

        mock_open.assert_called_once_with(2026)
        saved = bozp_annual_report_service.get_for_year(2026)
        assert saved is not None
        self.assertEqual(saved.silne_stranky, "Silná stránka")
        self.assertEqual(saved.zpracoval_worker_id, self.preparer_worker.id)
        self.assertEqual(saved.zpracoval, "Petr Specialista")

    def test_dialog_restores_saved_preparer_for_year(self) -> None:
        from moduly.proverky.ui.rocni_zprava_dialog import RocniZpravaDialog

        self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 3, 10))
        bozp_annual_report_service.save_for_year(
            2026,
            zpracoval_worker_id=self.preparer_worker.id,
        )

        dialog = RocniZpravaDialog(year=2026)
        self.assertEqual(dialog.zpracoval_selector.current_person_id(), self.preparer_worker.id)

    def test_dialog_prefills_last_preparer_for_new_year(self) -> None:
        from moduly.proverky.ui.rocni_zprava_dialog import RocniZpravaDialog

        self._create_inspection_with_commission(year=2025, inspection_date=date(2025, 3, 10))
        self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 3, 10))
        bozp_annual_report_service.save_for_year(
            2025,
            zpracoval_worker_id=self.preparer_worker.id,
        )

        dialog = RocniZpravaDialog(year=2026)
        self.assertEqual(dialog.zpracoval_selector.current_person_id(), self.preparer_worker.id)


if __name__ == "__main__":
    unittest.main()
