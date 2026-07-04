import importlib
import tempfile
import unittest
import zipfile
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
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.proverky.constants import (
        CONTROL_POINT_SEVERITY_KRITICKA,
        CONTROL_POINT_SEVERITY_NIZKA,
        CONTROL_POINT_SEVERITY_VYSOKA,
    )
    from moduly.proverky.sluzby.bozp_annual_export_context_service import (
        AnnualReportMetrics,
        AnnualReportSeverityMetrics,
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
    from moduly.ukoly.sluzby.task_service import task_service


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

        from core.database.session import get_session
        from moduly.proverky.modely.bozp_annual_report import BozpAnnualReport

        with get_session() as session:
            for report in session.query(BozpAnnualReport).all():
                session.delete(report)
            session.commit()

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
            "klicove_poznatky_text",
            "top_priority_text",
            "doporuceni_specialisty",
            "priloha_proverky_text",
            "priloha_zjisteni_text",
            "priloha_opatreni_text",
            "priloha_otevrena_opatreni_text",
            "priloha_metodika_text",
            "metodika_zduvodneni_text",
            "spolehlivost_hodnoceni",
            "spolehlivost_hodnoceni_text",
            "spolehlivost_hodnoceni_vysvetleni",
            "statistika_text",
            "souhrn_text",
            "zamestnavatel_nazev",
            "pocet_proverek",
            "pocet_pracovist",
            "pocet_oblasti",
            "pocet_kontrolnich_bodu",
            "neshody_na_proverku",
            "doporuceni_na_proverku",
            "zjisteni_na_proverku",
            "opatreni_na_proverku",
            "vahove_skore_zjisteni",
            "vahove_skore_na_proverku",
            "vahove_skore_na_100_bodu",
            "otevrena_opatreni_po_terminu",
            "podil_nevyhovuje_procent",
            "ukazatele_vykonnosti_text",
            "trendy_text",
            "grafy_text",
            "top10_zavad_text",
            "problemova_pracoviste_text",
            "priciny_zavad_text",
            "historie_roky_text",
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
            "KLÍČOVÉ POZNATKY ROKU",
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
            "Příloha – Metodika hodnocení výkonnosti systému BOZP",
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
        self.assertIn("Neshody: 1.00 / prověrku", content)
        self.assertIn("✔ Funkční organizace práce.", content)
        self.assertIn("🔴 Chybí označení únikových východů.", content)
        self.assertIn("🟡 Evidence preventivních opatření není vždy úplná.", content)
        self.assertIn("Jedná se o první hodnocené období.", content)
        self.assertIn("• Nejčastější problém:", content)

    def test_attention_areas_skip_positive_audit_assertions(self) -> None:
        inspection = self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 5, 1))
        assert inspection is not None
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ControlPointContext(
                area_id="bozp",
                area_label="BOZP",
                section_id="s1",
                section_label="Sekce",
                control_point_id="cp_pos",
                control_point_label="Kontroly probíhají pravidelně",
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
                control_point_id="cp_rec",
                control_point_label="Doplnit systém evidence školení.",
            ),
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )

        context = bozp_annual_export_context_service.build(2026)
        text = context.attention_areas_text
        self.assertIn("Neprobíhají pravidelné kontroly pracovišť.", text)
        self.assertNotIn("Kontroly probíhají pravidelně", text)
        self.assertIn("Doplnit systém evidence školení.", text)

    def test_normalized_metrics_in_year_comparison(self) -> None:
        for index in range(2):
            inspection = self._create_inspection_with_commission(
                year=2025,
                inspection_date=date(2025, 3, 10 + index),
                workplace_name=f"Hala 2025-{index}",
            )
            assert inspection is not None
            for neshoda_index in range(2 if index == 0 else 1):
                control_result_service.set_result(
                    ENTITY_PROVERKY,
                    inspection.id,
                    ControlPointContext(
                        area_id="bozp",
                        area_label="BOZP",
                        section_id="s1",
                        section_label="Sekce",
                        control_point_id=f"cp-2025-{index}-{neshoda_index}",
                        control_point_label=f"Neshoda 2025-{index}-{neshoda_index}",
                    ),
                    result=CONTROL_RESULT_NEVYHOVUJE,
                )

        for index in range(9):
            inspection = self._create_inspection_with_commission(
                year=2026,
                inspection_date=date(2026, 3, 10 + (index % 20)),
                workplace_name=f"Hala 2026-{index}",
            )
            assert inspection is not None
            control_result_service.set_result(
                ENTITY_PROVERKY,
                inspection.id,
                ControlPointContext(
                    area_id="bozp",
                    area_label="BOZP",
                    section_id="s1",
                    section_label="Sekce",
                    control_point_id=f"cp-2026-{index}",
                    control_point_label=f"Neshoda 2026-{index}",
                ),
                result=CONTROL_RESULT_NEVYHOVUJE,
            )

        context = bozp_annual_export_context_service.build(2026)
        self.assertIn("Prověrky: 2 → 9", context.comparison.text)
        self.assertIn("Neshody: 3 → 9", context.comparison.text)
        self.assertIn("Neshody: 1.50 / prověrku → 1.00 / prověrku", context.comparison.text)
        self.assertIn("samotný nárůst absolutního počtu tedy neznamená zhoršení úrovně BOZP", context.comparison.text)

    def test_historical_series_loads_all_previous_years(self) -> None:
        self._create_inspection_with_commission(year=2023, inspection_date=date(2023, 1, 1))
        self._create_inspection_with_commission(year=2025, inspection_date=date(2025, 1, 1))
        self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 1, 1))

        context = bozp_annual_export_context_service.build(2026)
        self.assertEqual(context.history.available_years, (2023, 2025, 2026))
        self.assertEqual(context.history.previous_years(), (2023, 2025))
        self.assertEqual(context.placeholder_values()["historie_roky_text"], "2023, 2025, 2026")

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

    def _severity_side_effect(self, **_kwargs):
        control_point_id = str(_kwargs.get("control_point_id", ""))
        if control_point_id.startswith("cp-low"):
            return CONTROL_POINT_SEVERITY_NIZKA
        if control_point_id.startswith("cp-high"):
            return CONTROL_POINT_SEVERITY_VYSOKA
        if control_point_id.startswith("cp-crit"):
            return CONTROL_POINT_SEVERITY_KRITICKA
        return "stredni"

    def test_many_low_severity_issues_do_not_force_red_rating(self) -> None:
        inspection = self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 3, 10))
        assert inspection is not None
        with patch.object(
            bozp_annual_export_context_service,
            "_resolve_control_point_severity",
            side_effect=self._severity_side_effect,
        ):
            for index in range(4):
                control_result_service.set_result(
                    ENTITY_PROVERKY,
                    inspection.id,
                    ControlPointContext(
                        area_id="bozp",
                        area_label="BOZP",
                        section_id="s1",
                        section_label="Sekce",
                        control_point_id=f"cp-low-{index}",
                        control_point_label=f"Formální nedostatek {index}",
                    ),
                    result=CONTROL_RESULT_NEVYHOVUJE,
                )
            for index in range(4996):
                control_result_service.set_result(
                    ENTITY_PROVERKY,
                    inspection.id,
                    ControlPointContext(
                        area_id="bozp",
                        area_label="BOZP",
                        section_id="s1",
                        section_label="Sekce",
                        control_point_id=f"cp-ok-{index}",
                        control_point_label=f"Vyhovující bod {index}",
                    ),
                    result=CONTROL_RESULT_VYHOVUJE,
                )

            context = bozp_annual_export_context_service.build(2026)
            self.assertEqual(context.overall_rating.level, "green")
            self.assertLess(context.severity.nevyhovuje_percent, 5)
            self.assertEqual(context.severity.count_for(CONTROL_POINT_SEVERITY_NIZKA), 4)
            self.assertIn("Celkové hodnocení je zelené", context.overall_assessment_text)

    def test_critical_open_overdue_finding_worsens_rating(self) -> None:
        inspection = self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 3, 10))
        assert inspection is not None
        with patch.object(
            bozp_annual_export_context_service,
            "_resolve_control_point_severity",
            side_effect=self._severity_side_effect,
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

            context = bozp_annual_export_context_service.build(2026)
            self.assertEqual(context.overall_rating.level, "red")
            self.assertGreaterEqual(context.severity.open_critical_overdue, 1)
            self.assertIn("kritická závada po termínu", context.overall_assessment_text)
            self.assertIn("Spolehlivost hodnocení:", context.overall_assessment_text)
            self.assertIn("Kritéria hodnocení", context.methodology.appendix_text)

    def test_high_severity_has_greater_weight_than_low(self) -> None:
        metrics = AnnualReportMetrics(
            year=2026,
            inspections_count=1,
            workplaces_count=1,
            areas_count=1,
            control_points_count=2,
            ratings_vyhovuje=0,
            ratings_vyhovuje_s_doporucenim=0,
            ratings_nevyhovuje=2,
            findings_count=2,
            measures_total=0,
            measures_open=0,
            measures_closed=0,
        )
        low = AnnualReportSeverityMetrics(
            counts_by_severity={
                CONTROL_POINT_SEVERITY_NIZKA: 2,
                "stredni": 0,
                CONTROL_POINT_SEVERITY_VYSOKA: 0,
                CONTROL_POINT_SEVERITY_KRITICKA: 0,
            },
            weighted_score=2,
            score_per_inspection=2.0,
            score_per_100_control_points=100.0,
            nevyhovuje_percent=100.0,
            overdue_open_measures=0,
            open_critical_count=0,
            open_critical_overdue=0,
            open_high_overdue=0,
            repeated_problems_count=0,
        )
        high = AnnualReportSeverityMetrics(
            counts_by_severity={
                CONTROL_POINT_SEVERITY_NIZKA: 0,
                "stredni": 0,
                CONTROL_POINT_SEVERITY_VYSOKA: 2,
                CONTROL_POINT_SEVERITY_KRITICKA: 0,
            },
            weighted_score=14,
            score_per_inspection=14.0,
            score_per_100_control_points=700.0,
            nevyhovuje_percent=100.0,
            overdue_open_measures=0,
            open_critical_count=0,
            open_critical_overdue=0,
            open_high_overdue=0,
            repeated_problems_count=0,
        )
        self.assertGreater(high.weighted_score, low.weighted_score)
        self.assertEqual(low.weighted_score, 2)
        self.assertEqual(high.weighted_score, 14)

    def test_overall_assessment_explains_rating_color(self) -> None:
        inspection = self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 4, 1))
        assert inspection is not None
        with patch.object(
            bozp_annual_export_context_service,
            "_resolve_control_point_severity",
            side_effect=self._severity_side_effect,
        ):
            for index in range(20):
                control_result_service.set_result(
                    ENTITY_PROVERKY,
                    inspection.id,
                    ControlPointContext(
                        area_id="bozp",
                        area_label="BOZP",
                        section_id="s1",
                        section_label="Sekce",
                        control_point_id=f"cp-ok-{index}",
                        control_point_label=f"Vyhovující bod {index}",
                    ),
                    result=CONTROL_RESULT_VYHOVUJE,
                )
            control_result_service.set_result(
                ENTITY_PROVERKY,
                inspection.id,
                ControlPointContext(
                    area_id="bozp",
                    area_label="BOZP",
                    section_id="s1",
                    section_label="Sekce",
                    control_point_id="cp-high",
                    control_point_label="Závada s vysokou závažností",
                ),
                result=CONTROL_RESULT_NEVYHOVUJE,
            )

            context = bozp_annual_export_context_service.build(2026)
            self.assertEqual(context.overall_rating.level, "yellow")
            self.assertIn("Celkové hodnocení je žluté", context.overall_assessment_text)
            self.assertIn("vysokou závažností", context.overall_assessment_text)
            self.assertIn("Ukazatele výkonnosti systému BOZP", context.placeholder_values()["prehled_vysledku_text"])
            self.assertIn("Váhové skóre zjištění: 7", context.placeholder_values()["prehled_vysledku_text"])
            self.assertIn("Spolehlivost hodnocení:", context.placeholder_values()["ukazatele_vykonnosti_text"])

    def test_methodology_appendix_in_export(self) -> None:
        self._create_inspection_with_commission(year=2026, inspection_date=date(2026, 3, 10))
        path = rocni_zprava_service.generate_for_year(2026)
        content = _odt_content(path)

        self.assertIn("Kritéria hodnocení", content)
        self.assertIn("Podíl nevyhovujících bodů", content)
        self.assertIn("Rozhodovací pravidla", content)
        self.assertIn("Spolehlivost hodnocení", content)


if __name__ == "__main__":
    unittest.main()
