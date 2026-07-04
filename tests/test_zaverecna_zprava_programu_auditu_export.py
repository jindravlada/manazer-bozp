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

    from moduly.audity.sluzby.audit_process_maturity_history_service import (
        audit_process_maturity_history_service,
    )
    from moduly.audity.sluzby.audit_program_final_export_context_service import (
        audit_program_final_export_context_service,
    )
    from moduly.audity.sluzby.audit_program_final_report_service import (
        audit_program_final_report_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.zaverecna_zprava_programu_auditu_service import (
        zaverecna_zprava_programu_auditu_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _ensure_final_report_template() -> Path:
    return zaverecna_zprava_programu_auditu_service.template_path()


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _odt_styles(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("styles.xml").decode("utf-8")


class ZaverecnaZpravaProgramuAudituExportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from core.database.database_initializer import (
            _ensure_audit_program_final_report_table,
        )

        _ensure_audit_program_final_report_table()

        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

        from core.database.session import get_session
        from moduly.audity.modely.audit_program import (
            AuditProgram,
            AuditProgramVisit,
            AuditProgramVisitProcess,
            AuditProgramWorkplace,
        )
        from moduly.audity.modely.audit_program_final_report import AuditProgramFinalReport
        from moduly.audity.modely.audit_process_maturity_snapshot import (
            AuditProcessMaturitySnapshot,
        )

        with get_session() as session:
            for report in session.query(AuditProgramFinalReport).all():
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
        _ensure_final_report_template()

    def _create_program(
        self,
        *,
        name: str,
        date_from: date,
        date_to: date,
        previous_program_id: int | None = None,
    ):
        from moduly.audity.constants import DEFAULT_AUDIT_PROGRAM_STANDARDS

        workplace = settings_service.save_workplace(name=f"Pracoviště {name}")
        program = audit_program_service.create_program(
            name=name,
            date_from=date_from,
            date_to=date_to,
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
            previous_program_id=previous_program_id,
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            audit_interval_months=6,
        )
        for year in range(date_from.year, date_to.year + 1):
            audit_program_service.add_visit(
                program.id,
                workplace_id=workplace.id,
                planned_year=year,
                planned_month=3,
            )
        return audit_program_service.get_program(program.id)

    def _create_audit(self, *, program_id: int, year: int):
        from moduly.audity.sluzby.audit_commission_service import audit_commission_service
        from moduly.nastaveni.sluzby.person_service import person_service

        workplace = settings_service.save_workplace(name=f"Hala {year}")
        leader_id = settings_service.save_worker(first_name="Jan", last_name="Novák").id
        workplace_rep_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        union_id = person_service.create_person(first_name="Lucie", last_name="Horáková").id
        audit = audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=year,
            audit_date=date(year, 3, 10),
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
        return audit_service.update_audit(audit.id, program_id=program_id)

    def test_program_without_previous_program_reference_text(self) -> None:
        program = self._create_program(
            name="Program 2026–2028",
            date_from=date(2026, 4, 1),
            date_to=date(2028, 3, 31),
        )
        context = audit_program_final_export_context_service.build(program.id)
        self.assertIn("referenční bázi", context.continuity_text)
        self.assertIn("referenční bázi", context.previous_program_comparison_text)

    def test_program_with_previous_program_comparison(self) -> None:
        previous = self._create_program(
            name="Program 2023–2025",
            date_from=date(2023, 4, 1),
            date_to=date(2025, 3, 31),
        )
        current = self._create_program(
            name="Program 2026–2028",
            date_from=date(2026, 4, 1),
            date_to=date(2028, 3, 31),
            previous_program_id=previous.id,
        )
        self._create_audit(program_id=previous.id, year=2024)
        self._create_audit(program_id=current.id, year=2027)

        context = audit_program_final_export_context_service.build(current.id)
        self.assertIn("Předchozí program:", context.previous_program_comparison_text)
        self.assertIn("Aktuální program:", context.previous_program_comparison_text)
        self.assertIn(previous.name, context.continuity_text)

    def test_process_evolution_by_years(self) -> None:
        program = self._create_program(
            name="Program vývoj procesů",
            date_from=date(2026, 4, 1),
            date_to=date(2028, 3, 31),
        )
        for year, level, emoji, label in (
            (2026, "rizikovy", "🟠", "Rizikový"),
            (2027, "stabilni", "🟡", "Stabilní"),
            (2028, "vyspely", "🟢", "Vyspělý"),
        ):
            audit_process_maturity_history_service.record_snapshot(
                year=year,
                audit_program_id=program.id,
                process_id="rizeni_napravnych_opatreni",
                process_name="Řízení nápravných opatření",
                maturity_level=level,
                maturity_emoji=emoji,
                maturity_label=label,
                weighted_score=2,
                audits_count=1,
                control_points_count=5,
                nevyhovuje_count=1,
                doporuceni_count=0,
                open_measures_count=0,
                overdue_measures_count=0,
            )

        context = audit_program_final_export_context_service.build(program.id)
        self.assertIn("Řízení nápravných opatření", context.process_evolution_text)
        self.assertIn("2026", context.process_evolution_text)
        self.assertIn("2028", context.process_evolution_text)
        self.assertIn("zlepšuje se", context.process_evolution_text)
        self.assertIn("Trend:", context.system_maturity_evolution_text)

    def test_recommendation_for_new_program_placeholder(self) -> None:
        program = self._create_program(
            name="Program doporučení",
            date_from=date(2026, 4, 1),
            date_to=date(2028, 3, 31),
        )
        audit_program_final_report_service.save_for_program(
            program.id,
            doporuceni_novy_program="Zaměřit se na řízení změn a školení vedoucích.",
            silne_stranky="Dobrá dokumentace",
            hlavni_slabiny="Nedostatečné sledování opatření",
        )
        context = audit_program_final_export_context_service.build(program.id)
        values = context.placeholder_values()
        self.assertIn("řízení změn", values["doporuceni_novy_program_text"])
        self.assertIn("Dobrá dokumentace", values["silne_stranky_text"])
        self.assertIn("sledování opatření", values["hlavni_slabiny_text"])

    def test_generate_creates_odt_file(self) -> None:
        program = self._create_program(
            name="Export ODT",
            date_from=date(2026, 4, 1),
            date_to=date(2028, 3, 31),
        )
        self._create_audit(program_id=program.id, year=2026)
        path = zaverecna_zprava_programu_auditu_service.generate_for_program(program.id)
        self.assertTrue(path.exists())
        self.assertEqual(path.suffix.lower(), ".odt")

    def test_export_replaces_placeholders(self) -> None:
        program = self._create_program(
            name="Export placeholdery",
            date_from=date(2026, 4, 1),
            date_to=date(2028, 3, 31),
        )
        audit_program_final_report_service.save_for_program(
            program.id,
            doporuceni_novy_program="Nový program má rozšířit pokrytí BOZP.",
            zpracoval="Petr Auditor",
        )
        path = zaverecna_zprava_programu_auditu_service.generate_for_program(program.id)
        content = _odt_content(path)
        self.assertIn("ZÁVĚREČNÁ ZPRÁVA PROGRAMU INTERNÍCH AUDITŮ", content)
        self.assertIn(program.name, content)
        self.assertIn("Nový program má rozšířit pokrytí BOZP.", content)
        self.assertNotIn("${program_nazev}", content)

    def test_template_footer_contains_program_name_placeholder(self) -> None:
        template = zaverecna_zprava_programu_auditu_service.template_path()
        styles = _odt_styles(template)
        self.assertIn("${program_nazev}", styles)
        self.assertIn("Závěrečná zpráva programu interních auditů", styles)

    @patch(
        "moduly.audity.ui.zaverecna_zprava_programu_auditu_dialog."
        "zaverecna_zprava_programu_auditu_service.open_for_program"
    )
    def test_dialog_creates_report_from_ui(self, open_mock) -> None:
        from moduly.audity.ui.zaverecna_zprava_programu_auditu_dialog import (
            ZaverecnaZpravaProgramuAudituDialog,
        )

        program = self._create_program(
            name="UI dialog",
            date_from=date(2026, 4, 1),
            date_to=date(2028, 3, 31),
        )
        dialog = ZaverecnaZpravaProgramuAudituDialog(program_id=program.id)
        dialog.doporuceni_edit.setPlainText("Doporučení z dialogu.")
        dialog._create_report()
        open_mock.assert_called_once_with(program.id)
        saved = audit_program_final_report_service.get_for_program(program.id)
        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertIn("Doporučení z dialogu", saved.doporuceni_novy_program)


if __name__ == "__main__":
    unittest.main()
