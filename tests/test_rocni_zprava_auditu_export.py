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
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.sluzby.audit_annual_export_context_service import (
        AuditAnnualMetrics,
        AuditAnnualSeverityMetrics,
        audit_annual_export_context_service,
    )
    from moduly.audity.sluzby.audit_annual_report_service import audit_annual_report_service
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.rocni_zprava_auditu_service import rocni_zprava_auditu_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service


def _ensure_annual_report_template() -> Path:
    import shutil

    path = rocni_zprava_auditu_service.template_path()
    bundled = (
        Path(__file__).resolve().parents[1]
        / "moduly"
        / "audity"
        / "templates"
        / "exporty"
        / "RocniZpravaAuditu.odt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if bundled.exists():
        shutil.copy2(bundled, path)
    return path


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


class RocniZpravaAudituExportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

        from core.database.session import get_session
        from moduly.audity.modely.audit_annual_report import AuditAnnualReport

        with get_session() as session:
            for report in session.query(AuditAnnualReport).all():
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
            last_name="Auditor",
            performs_controls=True,
        )
        self.preparer_worker = next(
            worker
            for worker in settings_service.get_workers()
            if worker.last_name == "Auditor"
        )
        _ensure_annual_report_template()

    def _create_audit(self, **fields):
        workplace = settings_service.save_workplace(name=fields.pop("workplace_name", "Hala A"))
        leader_id = settings_service.save_worker(first_name="Jan", last_name="Novák").id
        workplace_rep_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        union_id = person_service.create_person(first_name="Lucie", last_name="Horáková").id
        audit = audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            **fields,
        )
        audit_commission_service.save_members(
            audit.id,
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
        return audit_service.get_by_id(audit.id)

    def test_generate_creates_odt_file(self) -> None:
        self._create_audit(year=2026, audit_date=date(2026, 3, 10))
        path = rocni_zprava_auditu_service.generate_for_year(2026)
        self.assertTrue(path.exists())
        self.assertEqual(path.suffix.lower(), ".odt")

    def test_context_placeholder_keys(self) -> None:
        self._create_audit(year=2026, audit_date=date(2026, 3, 10))
        audit_annual_report_service.save_for_year(
            2026,
            silne_stranky="Stabilní systém řízení",
            top_priority="Snížit počet neshod",
            doporuceni_specialisty="Posílit sledování opatření",
        )
        context = audit_annual_export_context_service.build(2026)
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
            "doporuceni_auditora",
            "doporuceni_specialisty",
            "priloha_auditu_text",
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
            "pocet_auditu",
            "pocet_pracovist",
            "pocet_procesu",
            "pocet_kontrolnich_bodu",
            "neshody_na_audit",
            "doporuceni_na_audit",
            "zjisteni_na_audit",
            "opatreni_na_audit",
            "vahove_skore_zjisteni",
            "vahove_skore_na_audit",
            "otevrena_opatreni_po_terminu",
            "podil_nevyhovuje_procent",
            "ukazatele_vykonnosti_text",
            "vyspelost_systemu_text",
            "vykonnost_systemu_text",
            "ucinnost_procesu_text",
            "systemicke_problemy_text",
            "ucinnost_opatreni_text",
            "plneni_programu_text",
            "silne_procesy_text",
            "slabe_procesy_text",
            "trendy_text",
            "grafy_text",
            "historie_roky_text",
            "program_zprava_rezerva_text",
        }
        self.assertEqual(set(values.keys()), expected_keys)

    def test_management_report_structure_in_output(self) -> None:
        audit = self._create_audit(year=2026, audit_date=date(2026, 3, 10))
        assert audit is not None
        audit_annual_report_service.save_for_year(
            2026,
            zpracoval_worker_id=self.preparer_worker.id,
        )

        path = rocni_zprava_auditu_service.generate_for_year(2026)
        content = _odt_content(path)

        for heading in (
            "ROČNÍ ZPRÁVA Z INTERNÍCH AUDITŮ",
            "Základní informace",
            "CELKOVÉ HODNOCENÍ",
            "KLÍČOVÉ POZNATKY ROKU",
            "Přehled výsledků",
            "Vyspělost systému řízení",
            "Výkonnost systému řízení",
            "Účinnost řídicích procesů",
            "Opakované systémové problémy",
            "Účinnost nápravných opatření",
            "Plnění auditního programu",
            "Silné stránky systému",
            "Oblasti vyžadující pozornost",
            "Vývoj oproti minulému roku",
            "TOP priority na příští rok",
            "Doporučení auditora",
            "Příloha – Seznam auditů",
            "Příloha – Významná zjištění",
            "Příloha – Uložená opatření",
            "Příloha – Otevřená opatření",
            "Příloha – Metodika hodnocení výkonnosti systému řízení",
        ):
            self.assertIn(heading, content)

        self.assertIn("Test Zaměstnavatel s.r.o.", content)
        self.assertIn("Petr Auditor", content)
        self.assertNotIn("prověrka", content.lower())
        self.assertNotIn("kontrolovaná oblast", content.lower())

    def test_aggregated_statistics_and_attention_areas(self) -> None:
        audit = self._create_audit(year=2026, audit_date=date(2026, 4, 1))
        assert audit is not None

        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="proces-a",
                area_label="Řídicí proces A",
                section_id="s1",
                section_label="Kritérium",
                control_point_id="cp1",
                control_point_label="Chybí dokumentace řídicího procesu.",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="proces-a",
                area_label="Řídicí proces A",
                section_id="s1",
                section_label="Kritérium",
                control_point_id="cp2",
                control_point_label="Evidence nápravných opatření není vždy úplná.",
            ),
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        audit_annual_report_service.save_for_year(
            2026,
            silne_stranky="Funkční systém řízení.",
            top_priority="Snížit počet neshod",
            doporuceni_specialisty="Dokončit otevřená opatření",
        )

        path = rocni_zprava_auditu_service.generate_for_year(2026)
        content = _odt_content(path)

        self.assertIn("Počet auditů: 1", content)
        self.assertIn("Nevyhovuje: 1", content)
        self.assertIn("Neshody: 1.00 / audit", content)
        self.assertIn("✔ Funkční systém řízení.", content)
        self.assertIn("🔴 Chybí dokumentace řídicího procesu.", content)
        self.assertIn("🟡 Evidence nápravných opatření není vždy úplná.", content)
        self.assertIn("Jedná se o první hodnocené období", content)
        self.assertIn("• Nejčastější systémový problém:", content)

    def test_process_maturity_block(self) -> None:
        audit = self._create_audit(year=2026, audit_date=date(2026, 5, 1))
        assert audit is not None
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="proces-b",
                area_label="Řídicí proces B",
                section_id="s1",
                section_label="Kritérium",
                control_point_id="cp-risk",
                control_point_label="Nedostatečné sledování opatření.",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
        )

        context = audit_annual_export_context_service.build(2026)
        self.assertIn("🟠", context.process_maturity.text)
        self.assertTrue(context.process_maturity.items)
        self.assertIn("Řídicí proces B", context.process_maturity.text)

    def test_systemic_problems_axis(self) -> None:
        audit1 = self._create_audit(year=2026, audit_date=date(2026, 2, 1), workplace_name="Hala 1")
        audit2 = self._create_audit(year=2026, audit_date=date(2026, 3, 1), workplace_name="Hala 2")
        assert audit1 is not None and audit2 is not None
        for audit in (audit1, audit2):
            control_result_service.set_result(
                ENTITY_AUDITY,
                audit.id,
                ControlPointContext(
                    area_id="proces-c",
                    area_label="Řídicí proces C",
                    section_id="s1",
                    section_label="Kritérium",
                    control_point_id="cp-repeat",
                    control_point_label="Opakovaný systémový problém.",
                ),
                result=CONTROL_RESULT_NEVYHOVUJE,
            )

        context = audit_annual_export_context_service.build(2026)
        self.assertIn("Opakovaný systémový problém", context.systemic_problems_text)
        self.assertIn("2 audity", context.systemic_problems_text)

    def test_corrective_measures_axis_with_overdue_task(self) -> None:
        audit = self._create_audit(year=2026, audit_date=date(2026, 6, 1))
        assert audit is not None
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Zjištění s opatřením",
            status=FINDING_STATUS_OTEVRENE,
            source_control_point_id="cp-task",
        )
        task = finding_task_service.create_task_from_finding(finding.id)
        task_service.update_task(
            task.id,
            task.title,
            due_date=date.today() - timedelta(days=5),
        )

        context = audit_annual_export_context_service.build(2026)
        self.assertIn("nápravných opatření", context.corrective_measures_text)
        self.assertGreaterEqual(context.severity.overdue_open_measures, 1)

    def test_evaluation_explanation_builds(self) -> None:
        self._create_audit(year=2026, audit_date=date(2026, 3, 10))
        explanation = audit_annual_export_context_service.build_evaluation_explanation(2026)
        self.assertTrue(explanation.rating.headline)
        self.assertTrue(explanation.justification)

    def test_severity_weight_ordering(self) -> None:
        from moduly.audity.constants import (
            CONTROL_POINT_SEVERITY_NIZKA,
            CONTROL_POINT_SEVERITY_VYSOKA,
        )

        metrics = AuditAnnualMetrics(
            year=2026,
            audits_count=1,
            workplaces_count=1,
            processes_count=1,
            control_points_count=2,
            ratings_vyhovuje=0,
            ratings_vyhovuje_s_doporucenim=0,
            ratings_nevyhovuje=2,
            findings_count=2,
            measures_total=0,
            measures_open=0,
            measures_closed=0,
        )
        low = AuditAnnualSeverityMetrics(
            counts_by_severity={
                CONTROL_POINT_SEVERITY_NIZKA: 2,
                "stredni": 0,
                CONTROL_POINT_SEVERITY_VYSOKA: 0,
                "kriticka": 0,
            },
            weighted_score=2,
            score_per_audit=2.0,
            nevyhovuje_percent=100.0,
            overdue_open_measures=0,
            open_critical_count=0,
            open_critical_overdue=0,
            open_high_overdue=0,
            repeated_problems_count=0,
        )
        high = AuditAnnualSeverityMetrics(
            counts_by_severity={
                CONTROL_POINT_SEVERITY_NIZKA: 0,
                "stredni": 0,
                CONTROL_POINT_SEVERITY_VYSOKA: 2,
                "kriticka": 0,
            },
            weighted_score=14,
            score_per_audit=14.0,
            nevyhovuje_percent=100.0,
            overdue_open_measures=0,
            open_critical_count=0,
            open_critical_overdue=0,
            open_high_overdue=0,
            repeated_problems_count=0,
        )
        self.assertGreater(high.weighted_score, low.weighted_score)


if __name__ == "__main__":
    unittest.main()
