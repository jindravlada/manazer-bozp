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
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_export_context_service import audit_export_context_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.ukoly.sluzby.task_service import task_service


def _ensure_audit_protocol_template() -> Path:
    import moduly.audity.sluzby.protokol_audit_service as protokol_module
    import shutil

    importlib.reload(protokol_module)
    path = protokol_module.protokol_audit_service.template_path()
    bundled = (
        Path(__file__).resolve().parents[1]
        / "moduly"
        / "audity"
        / "templates"
        / "exporty"
        / "ProtokolAudit.odt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if bundled.exists():
        shutil.copy2(bundled, path)
    return path


with patch.object(Path, "home", return_value=_TMP):
    from moduly.audity.sluzby.protokol_audit_service import (
        PROTOCOL_INCOMPLETE_WARNING,
        protokol_audit_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


class AudityProtokolExportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        import moduly.audity.sluzby.protokol_audit_service as protokol_module

        importlib.reload(protokol_module)
        global protokol_audit_service
        protokol_audit_service = protokol_module.protokol_audit_service

        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

        settings_service.save_employer(
            ico="12345678",
            name="Test Zaměstnavatel s.r.o.",
            address="Praha 1",
            nace="62.01",
        )
        _ensure_audit_protocol_template()

    def _create_audit(self, **fields):
        workplace = settings_service.save_workplace(name="Provoz A")
        leader_id = settings_service.save_worker(first_name="Jan", last_name="Novák").id
        workplace_rep_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        from moduly.nastaveni.sluzby.person_service import person_service

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

    def test_conclusion_widget_has_protocol_button(self) -> None:
        from moduly.audity.ui.audit_conclusion_widget import AuditConclusionWidget

        audit = self._create_audit()
        assert audit is not None

        widget = AuditConclusionWidget()
        widget.load_audit(audit)

        self.assertEqual(widget.protocol_btn.text(), "Protokol z auditu")
        self.assertTrue(widget.protocol_btn.isEnabled())

    def test_generate_creates_odt_file(self) -> None:
        audit = self._create_audit()
        assert audit is not None

        path = protokol_audit_service.generate_for_audit(audit)

        self.assertTrue(path.exists())
        self.assertEqual(path.suffix.lower(), ".odt")

    def test_statistics_in_output(self) -> None:
        audit = self._create_audit()
        assert audit is not None
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="rizeni_rizik",
                area_label="Řízení rizik",
                section_id="sekce",
                section_label="Sekce",
                control_point_id="q1",
                control_point_label="Tvrzení 1",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )

        path = protokol_audit_service.generate_for_audit(audit)
        content = _odt_content(path)

        self.assertIn(audit.number, content)
        self.assertIn("Auditních tvrzení: 1", content)
        self.assertIn("Vyhovuje: 1", content)
        self.assertIn("Executive Summary", content)

    def test_evaluation_in_output_includes_only_recommendations_and_noncompliance(self) -> None:
        audit = self._create_audit()
        assert audit is not None

        contexts = [
            (
                "q_ok",
                "Vyhovuje tvrzení",
                CONTROL_RESULT_VYHOVUJE,
            ),
            (
                "q_rec",
                "Doporučení tvrzení",
                CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            ),
            (
                "q_bad",
                "Neshoda tvrzení",
                CONTROL_RESULT_NEVYHOVUJE,
            ),
        ]
        for question_id, label, result in contexts:
            control_result_service.set_result(
                ENTITY_AUDITY,
                audit.id,
                ControlPointContext(
                    area_id="rizeni_rizik",
                    area_label="Řízení rizik",
                    section_id="sekce",
                    section_label="Sekce",
                    control_point_id=question_id,
                    control_point_label=label,
                ),
                result=result,
            )

        context = audit_export_context_service.build(audit)
        evaluation_text = context.evaluation_text()

        self.assertIn("🟡 Vyhovuje s doporučením", evaluation_text)
        self.assertIn("Doporučení tvrzení", evaluation_text)
        self.assertIn("🔴 Nevyhovuje", evaluation_text)
        self.assertIn("Neshoda tvrzení", evaluation_text)
        self.assertNotIn("Vyhovuje tvrzení", evaluation_text)
        self.assertNotIn("Zobrazit pouze výsledky", evaluation_text)
        self.assertIn("   Proces:", evaluation_text)

        path = protokol_audit_service.generate_for_audit(audit)
        content = _odt_content(path)
        self.assertIn("🟡 Vyhovuje s doporučením", content)
        self.assertIn("🔴 Nevyhovuje", content)
        self.assertNotIn("Vyhovuje tvrzení", content)
        self.assertNotIn("Vyhovuje;", content)
        self.assertNotIn("Zobrazit pouze výsledky", content)

    def test_statistics_and_summary_are_not_duplicated(self) -> None:
        audit = self._create_audit()
        assert audit is not None
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="rizeni_rizik",
                area_label="Řízení rizik",
                section_id="sekce",
                section_label="Sekce",
                control_point_id="q1",
                control_point_label="Tvrzení 1",
            ),
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )

        context = audit_export_context_service.build(audit)
        statistics_text = context.statistics_text()
        summary_text = context.summary_text()

        self.assertIn("Auditních tvrzení:", statistics_text)
        self.assertIn("Vyhovuje:", statistics_text)
        self.assertIn("Celkové hodnocení:", summary_text)
        self.assertIn("Stručné doporučení auditora:", summary_text)
        self.assertNotEqual(statistics_text, summary_text)
        self.assertNotIn("Vyhovuje:", summary_text.split("Stručné doporučení auditora:")[0].split("\n")[-3:])

    def test_findings_and_tasks_use_multiline_format(self) -> None:
        audit = self._create_audit()
        assert audit is not None
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Chybí dokumentace",
            recommended_action="Doplnit dokumentaci",
            status=FINDING_STATUS_OTEVRENE,
            source_area_label="Řízení rizik",
            source_section_label="Dokumentace",
        )
        task = finding_task_service.create_task_from_finding(finding.id)
        task_service.update_task(
            task.id,
            title="Doplnit BOZP dokumentaci",
            responsible_person_id=None,
            due_date=date(2026, 8, 15),
        )
        task = task_service.get_task_by_id(task.id)
        assert task is not None

        context = audit_export_context_service.build(audit)
        findings_text = context.findings_text()
        tasks_text = context.tasks_text()

        self.assertIn("1. Neshoda", findings_text)
        self.assertIn("   Proces: Řízení rizik", findings_text)
        self.assertIn("   Kritérium: Dokumentace", findings_text)
        self.assertIn("   Popis: Chybí dokumentace", findings_text)
        self.assertIn("   Doporučení: Doplnit dokumentaci", findings_text)

        self.assertIn("1. Doplnit BOZP dokumentaci", tasks_text)
        self.assertIn("   Termín: 15.08.2026", tasks_text)
        self.assertIn("   Stav:", tasks_text)

        path = protokol_audit_service.generate_for_audit(audit)
        content = _odt_content(path)
        self.assertIn("   Popis: Chybí dokumentace", content)
        self.assertIn("   Termín: 15.08.2026", content)

    def test_conclusion_text_is_short_without_process_list(self) -> None:
        audit = self._create_audit()
        assert audit is not None
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="rizeni_rizik",
                area_label="Řízení rizik",
                section_id="sekce",
                section_label="Sekce",
                control_point_id="q1",
                control_point_label="Tvrzení 1",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
        )

        context = audit_export_context_service.build(audit)
        conclusion_text = context.conclusion_text()

        self.assertNotIn("z oblastí:", conclusion_text)
        self.assertIn("interního auditu", conclusion_text)
        self.assertLess(len(conclusion_text), 300)

    def test_findings_in_output(self) -> None:
        audit = self._create_audit()
        assert audit is not None
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Chybí dokumentace",
            status=FINDING_STATUS_OTEVRENE,
        )

        path = protokol_audit_service.generate_for_audit(audit)
        content = _odt_content(path)

        self.assertIn("Chybí dokumentace", content)

    def test_context_placeholder_keys(self) -> None:
        audit = self._create_audit()
        assert audit is not None

        context = audit_export_context_service.build(audit)
        values = context.placeholder_values()

        expected_keys = {
            "cislo_auditu",
            "zamestnavatel_nazev",
            "pracoviste",
            "provoz",
            "program_nazev",
            "rok",
            "planovany_mesic",
            "typ_auditu",
            "datum_auditu",
            "datum_zahajeni",
            "datum_ukonceni",
            "stav",
            "komise_text",
            "auditni_tym_text",
            "procesy_text",
            "celkove_hodnoceni",
            "auditovany_provoz",
            "auditovany_system",
            "doporuceni_auditora",
            "executive_summary_text",
            "prehled_vysledku_text",
            "vyznamna_zjisteni_text",
            "prijata_opatreni_text",
            "detail_zjisteni_text",
            "podpisy_text",
            "hodnoceni_text",
            "zjisteni_text",
            "ukoly_text",
            "zaver_text",
            "statistika_text",
            "souhrn_text",
            "datum_vygenerovani",
        }
        self.assertEqual(set(values.keys()), expected_keys)

    def test_management_reporting_structure_in_output(self) -> None:
        audit = self._create_audit()
        assert audit is not None

        path = protokol_audit_service.generate_for_audit(audit)
        content = _odt_content(path)

        for heading in (
            "PROTOKOL Z AUDITU",
            "Executive Summary",
            "Přehled výsledků",
            "Významná zjištění",
            "Přijatá opatření / úkoly",
            "Detail zjištění",
            "Závěr",
            "Podpisy",
        ):
            self.assertIn(heading, content)

        self.assertIn("Podpis vedoucího auditu:", content)
        self.assertNotIn("Zobrazit pouze výsledky", content)

    def test_incomplete_warning(self) -> None:
        audit = self._create_audit()
        assert audit is not None

        warning = protokol_audit_service.incomplete_warning(audit)

        self.assertEqual(warning, PROTOCOL_INCOMPLETE_WARNING)

    @patch("moduly.audity.ui.audit_conclusion_widget.QMessageBox.warning")
    @patch("moduly.audity.ui.audit_conclusion_widget.protokol_audit_service.open_for_audit")
    def test_ui_export_calls_service(self, mock_open, mock_warning) -> None:
        from moduly.audity.ui.audit_conclusion_widget import AuditConclusionWidget

        audit = self._create_audit()
        assert audit is not None

        widget = AuditConclusionWidget()
        widget.load_audit(audit)
        widget._export_protocol()

        mock_warning.assert_called_once()
        mock_open.assert_called_once_with(audit)


if __name__ == "__main__":
    unittest.main()
