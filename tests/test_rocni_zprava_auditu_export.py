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
    from moduly.audity.sluzby.audit_annual_program_service import audit_annual_program_service
    from moduly.audity.sluzby.audit_annual_report_service import audit_annual_report_service
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.rocni_zprava_auditu_service import rocni_zprava_auditu_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service


def _ensure_annual_report_template() -> Path:
    return rocni_zprava_auditu_service.template_path()


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


class RocniZpravaAudituExportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from core.database.database_initializer import _ensure_audit_annual_report_table

        _ensure_audit_annual_report_table()

        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

        from core.database.session import get_session
        from moduly.audity.modely.audit_annual_report import AuditAnnualReport
        from moduly.audity.modely.audit_process_maturity_snapshot import AuditProcessMaturitySnapshot
        from moduly.audity.modely.audit_program import (
            AuditProgram,
            AuditProgramVisit,
            AuditProgramVisitProcess,
            AuditProgramWorkplace,
        )

        with get_session() as session:
            for report in session.query(AuditAnnualReport).all():
                session.delete(report)
            for snapshot in session.query(AuditProcessMaturitySnapshot).all():
                session.delete(snapshot)
            for row in session.query(AuditProgramVisitProcess).all():
                session.delete(row)
            for row in session.query(AuditProgramVisit).all():
                session.delete(row)
            for row in session.query(AuditProgramWorkplace).all():
                session.delete(row)
            for row in session.query(AuditProgram).all():
                session.delete(row)
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
        self.default_program = self._ensure_audit_program(2026, "Výchozí program")
        _ensure_annual_report_template()

    def _ensure_audit_program(self, year: int, name: str):
        from datetime import date

        from moduly.audity.constants import DEFAULT_AUDIT_PROGRAM_STANDARDS
        from moduly.audity.sluzby.audit_program_service import audit_program_service

        for program in audit_annual_program_service.list_programs_for_year(year):
            if program.name == name:
                return program

        workplace = settings_service.save_workplace(name=f"Pracoviště {name}")
        program = audit_program_service.create_program(
            name=name,
            date_from=date(year, 1, 1),
            date_to=date(year + 3, 12, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            audit_interval_months=6,
        )
        audit_program_service.add_visit(
            program.id,
            workplace_id=workplace.id,
            planned_year=year,
            planned_month=3,
        )
        return audit_program_service.get_program(program.id)

    def _create_audit(self, **fields):
        program_id = fields.pop("program_id", self.default_program.id)
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
        audit = audit_service.get_by_id(audit.id)
        if program_id is not None and audit is not None and audit.program_id != program_id:
            audit = audit_service.update_audit(audit.id, program_id=program_id)
        return audit

    def test_generate_creates_odt_file(self) -> None:
        self._create_audit(year=2026, audit_date=date(2026, 3, 10))
        path = rocni_zprava_auditu_service.generate_for_year(2026)
        self.assertTrue(path.exists())
        self.assertEqual(path.suffix.lower(), ".odt")

    def test_template_uses_bundled_heading_placeholder(self) -> None:
        from core.services.storage_service import storage_service

        template = rocni_zprava_auditu_service.template_path()
        bundled = storage_service.bundled_template_file("exporty", "RocniZpravaAuditu.odt")
        assert bundled is not None
        self.assertEqual(template.resolve(), bundled.resolve())
        self.assertIn("${celkove_hodnoceni_nadpis}", _odt_content(template))

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
            "celkove_hodnoceni_nadpis",
            "celkove_hodnoceni_emoji",
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
            "vyspelost_legenda_text",
            "prumerna_vyspelost_systemu_text",
            "auditni_program_nazev",
            "trendy_procesu_text",
            "historie_vyspelosti_text",
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
            "navaznost_predchozi_audity_text",
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
            "Průměrná vyspělost systému řízení",
            "KLÍČOVÉ POZNATKY ROKU",
            "Přehled výsledků",
            "Vyspělost systému řízení",
            "Výkonnost systému řízení",
            "Účinnost řídicích procesů",
            "Opakované systémové problémy",
            "Účinnost nápravných opatření",
            "Plnění auditního programu",
            "Návaznost na předchozí audity",
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
        self.assertRegex(content, r"CELKOVÉ HODNOCENÍ [🟢🟡🔴]")
        self.assertIn("Reprezentativnost dat", content)
        self.assertIn("Legenda úrovní vyspělosti řídicích procesů je uvedena v příloze.", content)
        self.assertIn("Legenda vyspělosti řídicích procesů:", content)
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

    def test_attention_areas_normalize_positive_assertions(self) -> None:
        audit = self._create_audit(year=2026, audit_date=date(2026, 5, 1))
        assert audit is not None
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="proces-a",
                area_label="Řízení dokumentace",
                section_id="s1",
                section_label="Kritérium",
                control_point_id="cp_pos",
                control_point_label="Je schválena politika BOZP?",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="proces-a",
                area_label="Řízení dokumentace",
                section_id="s1",
                section_label="Kritérium",
                control_point_id="cp_rec",
                control_point_label="Doplnit systém evidence školení.",
            ),
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )

        context = audit_annual_export_context_service.build(2026)
        text = context.attention_areas_text
        self.assertIn("Politika není schválena", text)
        self.assertNotIn("Je schválena politika BOZP?", text)
        self.assertIn("Doplnit systém evidence školení.", text)

    def test_maturity_history_snapshot_is_recorded(self) -> None:
        from moduly.audity.sluzby.audit_process_maturity_history_service import (
            audit_process_maturity_history_service,
        )

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
        snapshots = audit_process_maturity_history_service.get_year_snapshots(
            2026,
            audit_program_id=self.default_program.id,
        )
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].process_id, "proces-b")
        self.assertEqual(
            context.process_maturity.legend_text,
            "Legenda úrovní vyspělosti řídicích procesů je uvedena v příloze.",
        )
        self.assertNotIn("Legenda vyspělosti řídicích procesů:", context.process_maturity.text)
        self.assertIn("🟠", context.process_maturity.text)
        self.assertIn("Řídicí proces B", context.process_maturity.text)
        self.assertTrue(context.placeholder_values()["prumerna_vyspelost_systemu_text"])

    def test_maturity_snapshot_save_and_update_without_note(self) -> None:
        from moduly.audity.modely.audit_process_maturity_snapshot import AuditProcessMaturitySnapshot
        from moduly.audity.repository.audit_process_maturity_snapshot_repository import (
            AuditProcessMaturitySnapshotRepository,
        )
        from moduly.audity.sluzby.audit_process_maturity_history_service import (
            audit_process_maturity_history_service,
        )

        repository = AuditProcessMaturitySnapshotRepository()
        common_fields = {
            "year": 2026,
            "audit_program_id": self.default_program.id,
            "process_id": "proces-note",
            "process_name": "Proces bez poznámky",
            "maturity_level": "rizikovy",
            "maturity_emoji": "🟠",
            "maturity_label": "Rizikový",
            "weighted_score": 7,
            "audits_count": 1,
            "control_points_count": 1,
            "nevyhovuje_count": 1,
            "doporuceni_count": 0,
            "open_measures_count": 0,
            "overdue_measures_count": 0,
        }

        created = audit_process_maturity_history_service.record_snapshot(**common_fields)
        self.assertEqual(created.note, "")

        updated = repository.save(
            AuditProcessMaturitySnapshot(
                **common_fields,
                trend_direction="stable",
                trend_label="→ Stabilní",
            )
        )
        self.assertEqual(updated.id, created.id)
        self.assertEqual(updated.note, "")

        updated_again = audit_process_maturity_history_service.record_snapshot(
            year=2026,
            audit_program_id=self.default_program.id,
            process_id="proces-note",
            process_name="Proces bez poznámky",
            maturity_level="stabilni",
            maturity_emoji="🟡",
            maturity_label="Stabilní",
            weighted_score=3,
            audits_count=1,
            control_points_count=1,
            nevyhovuje_count=0,
            doporuceni_count=1,
            open_measures_count=0,
            overdue_measures_count=0,
        )
        self.assertEqual(updated_again.id, created.id)
        self.assertEqual(updated_again.note, "")

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

    def test_save_reports_per_program_year(self) -> None:
        from core.database.session import get_session
        from moduly.audity.modely.audit_annual_report import AuditAnnualReport

        program_a = self._ensure_audit_program(2026, "Program A")
        program_b = self._ensure_audit_program(2026, "Program B")

        saved_a = audit_annual_report_service.save_for_year(
            2026,
            audit_program_id=program_a.id,
            silne_stranky="Text A",
        )
        saved_b = audit_annual_report_service.save_for_year(
            2026,
            audit_program_id=program_b.id,
            silne_stranky="Text B",
        )
        self.assertNotEqual(saved_a.id, saved_b.id)

        updated_a = audit_annual_report_service.save_for_year(
            2026,
            audit_program_id=program_a.id,
            silne_stranky="Text A updated",
        )
        self.assertEqual(saved_a.id, updated_a.id)
        self.assertEqual(updated_a.silne_stranky, "Text A updated")

        with get_session() as session:
            reports = session.query(AuditAnnualReport).filter_by(year=2026).all()
            self.assertEqual(len(reports), 2)
            by_program = {report.audit_program_id: report for report in reports}
            self.assertEqual(by_program[program_a.id].silne_stranky, "Text A updated")
            self.assertEqual(by_program[program_b.id].silne_stranky, "Text B")

    def test_migration_allows_multiple_programs_per_year(self) -> None:
        from sqlalchemy import text

        from core.database.database_initializer import (
            _audit_annual_reports_has_year_only_unique,
            _ensure_audit_annual_report_table,
        )
        from core.database.session import engine, get_session
        from moduly.audity.modely.audit_annual_report import AuditAnnualReport

        program_a = self._ensure_audit_program(2026, "Migrace A")
        program_b = self._ensure_audit_program(2026, "Migrace B")

        with get_session() as session:
            for report in session.query(AuditAnnualReport).all():
                session.delete(report)
            session.commit()

        with engine.connect() as connection:
            connection.execute(text("DROP TABLE audit_annual_reports"))
            connection.execute(
                text(
                    """
                    CREATE TABLE audit_annual_reports (
                        id INTEGER NOT NULL PRIMARY KEY,
                        year INTEGER NOT NULL,
                        silne_stranky TEXT DEFAULT '' NOT NULL,
                        top_priority TEXT DEFAULT '' NOT NULL,
                        doporuceni_specialisty TEXT DEFAULT '' NOT NULL,
                        zpracoval VARCHAR(150) DEFAULT '' NOT NULL,
                        zpracoval_worker_id INTEGER,
                        created_at DATETIME,
                        updated_at DATETIME,
                        CONSTRAINT uq_audit_annual_reports_year UNIQUE (year)
                    )
                    """
                )
            )
            connection.commit()

        _ensure_audit_annual_report_table()
        self.assertFalse(_audit_annual_reports_has_year_only_unique())

        audit_annual_report_service.save_for_year(
            2026,
            audit_program_id=program_a.id,
            silne_stranky="A",
        )
        audit_annual_report_service.save_for_year(
            2026,
            audit_program_id=program_b.id,
            silne_stranky="B",
        )

        with get_session() as session:
            self.assertEqual(
                session.query(AuditAnnualReport).filter_by(year=2026).count(),
                2,
            )


if __name__ == "__main__":
    unittest.main()
