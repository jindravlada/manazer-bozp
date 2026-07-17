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
        CONTROL_RESULT_NELZE_POSOUDIT,
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
    from moduly.audity.modely.audit_commission_member import AuditCommissionMember
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.ukoly.sluzby.task_service import task_service


def _ensure_audit_protocol_template() -> Path:
    import moduly.audity.sluzby.protokol_audit_service as protokol_module

    importlib.reload(protokol_module)
    # Preferuje uživatelskou kopii v .local a případně ji obnoví z balíčku.
    return protokol_module.protokol_audit_service.template_path()


with patch.object(Path, "home", return_value=_TMP):
    from moduly.audity.sluzby.protokol_audit_service import (
        PROTOCOL_INCOMPLETE_WARNING,
        protokol_audit_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from core.services.storage_service import storage_service


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

    def test_protocol_template_uses_local_copy_and_preserves_customization(self) -> None:
        import shutil

        user = storage_service.template_file("exporty", "ProtokolAudit.odt")
        bundled = storage_service.bundled_template_file("exporty", "ProtokolAudit.odt")
        self.assertIsNotNone(bundled)
        assert bundled is not None

        resolved = protokol_audit_service.template_path()
        self.assertEqual(resolved.resolve(), user.resolve())
        self.assertTrue(str(resolved).startswith(str(_TMP)))

        shutil.copy2(bundled, user)
        storage_service._write_template_bundle_hash(
            user,
            storage_service._file_sha256(bundled),
        )
        customized = b"custom-logo-template"
        user.write_bytes(customized)
        self.assertEqual(
            storage_service.resolve_editable_template("exporty", "ProtokolAudit.odt").read_bytes(),
            customized,
        )

        # Neupravená (marker odpovídá obsahu) se při změně balíčku obnoví.
        old_default = b"old-default-from-previous-appimage"
        user.write_bytes(old_default)
        storage_service._write_template_bundle_hash(
            user,
            storage_service._file_sha256(user),
        )
        refreshed = storage_service.resolve_editable_template("exporty", "ProtokolAudit.odt")
        self.assertEqual(refreshed.read_bytes(), bundled.read_bytes())

    def _create_audit(self, **fields):
        workplace = settings_service.save_workplace(name="Provoz A")
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
        self.assertIn("ZPRÁVA Z INTERNÍHO AUDITU", content)

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
        before_appendix_b = content.split("Příloha B", 1)[0]
        self.assertNotIn("Vyhovuje tvrzení", before_appendix_b)
        self.assertIn("🟢 Vyhovuje tvrzení", content)
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
            "datum_zahajeni_auditu",
            "datum_ukonceni_auditu",
            "stav",
            "komise_text",
            "auditni_tym_text",
            "clenove_komise_text",
            "procesy_text",
            "priloha_procesy_text",
            "priloha_auditni_tvrzeni_text",
            "priloha_auditni_tvrzeni_souhrn",
            "celkove_hodnoceni",
            "celkove_hodnoceni_text",
            "auditovany_provoz",
            "auditovany_system",
            "vedouci_auditor",
            "zastupce_provozu",
            "zastupce_odborove_organizace",
            "podpis_odboru_blok",
            "doporuceni_auditora",
            "silne_stranky_text",
            "oblasti_pozornosti_text",
            "rozsah_auditu_text",
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
        self.assertEqual(values["datum_ukonceni_auditu"], "Dosud neukončen")
        self.assertEqual(values["datum_ukonceni"], "Dosud neukončen")

    def test_management_reporting_structure_in_output(self) -> None:
        audit = self._create_audit()
        assert audit is not None

        path = protokol_audit_service.generate_for_audit(audit)
        content = _odt_content(path)

        headings = (
            "ZPRÁVA Z INTERNÍHO AUDITU",
            "Základní informace",
            "CELKOVÉ HODNOCENÍ",
            "Přehled výsledků",
            "Silné stránky systému",
            "Oblasti vyžadující pozornost",
            "Významná zjištění",
            "Doporučení vedoucího auditora",
            "Rozsah auditu",
            "Detail zjištění",
            "Přijatá opatření / úkoly",
            "Podpisy",
            "Příloha A – Auditované procesy",
            "Příloha B – Auditní tvrzení",
        )
        positions = []
        for heading in headings:
            self.assertIn(heading, content)
            positions.append(content.find(heading))
        self.assertEqual(positions, sorted(positions))

        self.assertIn("Jan Novák", content)
        self.assertIn("Eva Králová", content)
        self.assertIn("Lucie Horáková", content)
        self.assertIn("Datum zahájení auditu", content)
        self.assertIn("Datum ukončení auditu", content)
        self.assertIn("Členové auditorské komise", content)
        self.assertIn("Zástupce odborové organizace", content)
        self.assertIn("Dosud neukončen", content)
        self.assertNotIn("Příloha – Auditované procesy", content)
        self.assertNotIn("Datum auditu", content)
        self.assertNotIn("Zobrazit pouze výsledky", content)
        self.assertNotIn("Executive Summary", content)

        self.assertIn('fo:break-before="page"', content)
        self.assertLess(
            content.find("Podpisy"),
            content.find("Příloha A – Auditované procesy"),
        )
        self.assertLess(
            content.find("Přijatá opatření / úkoly"),
            content.find("Podpisy"),
        )
        self.assertLess(
            content.find("Významná zjištění"),
            content.find("Podpisy"),
        )

    def test_strengths_and_attention_areas_in_output(self) -> None:
        audit = self._create_audit()
        assert audit is not None
        audit = audit_service.update_audit(
            audit.id,
            silne_stranky="Funkční systém řízení.\nDobře vedená dokumentace.",
        )
        assert audit is not None

        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="rizeni_rizik",
                area_label="Řízení rizik",
                section_id="sekce",
                section_label="Sekce",
                control_point_id="q_rec",
                control_point_label="Evidence preventivních opatření není vždy úplná.",
            ),
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="rizeni_rizik",
                area_label="Řízení rizik",
                section_id="sekce",
                section_label="Sekce",
                control_point_id="q_bad",
                control_point_label="Analýza příčin neshod není prováděna jednotným způsobem.",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
        )

        path = protokol_audit_service.generate_for_audit(audit)
        content = _odt_content(path)

        self.assertIn("✔ Funkční systém řízení.", content)
        self.assertIn("✔ Dobře vedená dokumentace.", content)
        self.assertIn("🔴 Analýza příčin neshod není prováděna jednotným způsobem.", content)
        self.assertIn("🟡 Evidence preventivních opatření není vždy úplná.", content)
        self.assertIn("Auditované procesy jsou uvedeny v příloze této zprávy.", content)
        self.assertIn("Otevřené úkoly:", content)

    def test_a12_protocol_export_includes_commission_dates_and_assertions_appendix(
        self,
    ) -> None:
        audit = self._create_audit(
            started_at=date(2026, 3, 10),
            finished_at=date(2026, 3, 12),
        )
        assert audit is not None

        leader_id = settings_service.save_worker(first_name="Jan", last_name="Novák").id
        workplace_rep_id = settings_service.save_worker(
            first_name="Eva",
            last_name="Králová",
        ).id
        union_id = person_service.create_person(
            first_name="Lucie",
            last_name="Horáková",
        ).id
        member_id = settings_service.save_worker(
            first_name="Petr",
            last_name="Svoboda",
        ).id
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
                {
                    "record_type": "clen_komise",
                    "thp_worker_id": member_id,
                    "display_name": "Petr Svoboda",
                    "display_order": 40,
                    "active": True,
                },
            ],
        )

        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="rizeni_rizik",
                area_label="Řízení rizik",
                section_id="dokumentace",
                section_label="Dokumentace rizik",
                control_point_id="q_ok",
                control_point_label="Rizika jsou identifikována.",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="rizeni_rizik",
                area_label="Řízení rizik",
                section_id="dokumentace",
                section_label="Dokumentace rizik",
                control_point_id="q_partial",
                control_point_label="Evidence opatření je neúplná.",
            ),
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="havarijni",
                area_label="Havarijní připravenost",
                section_id="cviceni",
                section_label="Cvičení",
                control_point_id="q_na",
                control_point_label="Cvičení se neprovádí.",
            ),
            result=CONTROL_RESULT_NELZE_POSOUDIT,
        )

        context = audit_export_context_service.build(audit)
        members_text = context.commission_members_without_leader_text()
        self.assertEqual(members_text, "Petr Svoboda")
        self.assertNotIn("Eva Králová", members_text)
        self.assertNotIn("Lucie Horáková", members_text)
        self.assertNotIn("Jan Novák", members_text)

        assertions_text = context.appendix_assertions_text()
        self.assertIn("Dokumentace rizik", assertions_text)
        self.assertIn("🟢 Rizika jsou identifikována.", assertions_text)
        self.assertIn("🟡 Evidence opatření je neúplná.", assertions_text)
        self.assertIn("Cvičení", assertions_text)
        self.assertIn("⚪ Cvičení se neprovádí.", assertions_text)
        self.assertNotIn("Havarijní připravenost\n", assertions_text)

        summary = context.appendix_assertions_summary_text()
        self.assertIn("Celkem auditních tvrzení: 3", summary)
        self.assertIn("🟢 Splněno: 1", summary)
        self.assertIn("🟡 Částečně splněno: 1", summary)
        self.assertIn("🔴 Nesplněno: 0", summary)
        self.assertIn("⚪ Není relevantní: 1", summary)

        values = context.placeholder_values()
        self.assertEqual(values["datum_zahajeni_auditu"], "10.03.2026")
        self.assertEqual(values["datum_ukonceni_auditu"], "12.03.2026")

        path = protokol_audit_service.generate_for_audit(audit)
        content = _odt_content(path)

        self.assertIn("Eva Králová", content)
        self.assertIn("Lucie Horáková", content)
        self.assertIn("Petr Svoboda", content)
        self.assertIn("10.03.2026", content)
        self.assertIn("12.03.2026", content)
        self.assertIn("Datum zahájení auditu", content)
        self.assertIn("Datum ukončení auditu", content)
        self.assertNotIn("${datum_zahajeni_auditu}", content)
        self.assertNotIn("${datum_ukonceni_auditu}", content)
        self.assertIn("Příloha A – Auditované procesy", content)
        self.assertIn("Příloha B – Auditní tvrzení", content)
        self.assertIn("🟢 Rizika jsou identifikována.", content)
        self.assertIn("Celkem auditních tvrzení: 3", content)
        self.assertIn("🟢 Splněno: 1", content)

    def test_a12_1_dates_and_commission_membership_rules(self) -> None:
        unfinished = self._create_audit(started_at=date(2026, 4, 1))
        assert unfinished is not None
        unfinished_values = audit_export_context_service.build(unfinished).placeholder_values()
        self.assertEqual(unfinished_values["datum_zahajeni_auditu"], "01.04.2026")
        self.assertEqual(unfinished_values["datum_ukonceni_auditu"], "Dosud neukončen")

        finished = self._create_audit(
            started_at=date(2026, 4, 1),
            finished_at=date(2026, 4, 5),
        )
        assert finished is not None
        leader_id = settings_service.save_worker(
            first_name="Dana",
            last_name="Testovací",
        ).id
        workplace_rep_id = settings_service.save_worker(
            first_name="Cyril",
            last_name="Testovací",
        ).id
        member_ids = [
            settings_service.save_worker(first_name="Adam", last_name="Testovací").id,
            settings_service.save_worker(first_name="Vladimír", last_name="Jindra").id,
            settings_service.save_worker(first_name="Boris", last_name="Testovací").id,
        ]
        audit_commission_service.save_members(
            finished.id,
            [
                {
                    "record_type": "vedouci_komise",
                    "thp_worker_id": leader_id,
                    "display_name": "Dana Testovací",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": "zastupce_pracoviste",
                    "thp_worker_id": workplace_rep_id,
                    "display_name": "Cyril Testovací",
                    "display_order": 20,
                    "active": True,
                },
                {
                    "record_type": "zastupce_odboru",
                    "person_id": person_service.create_person(
                        first_name="Lucie",
                        last_name="Horáková",
                    ).id,
                    "display_name": "Lucie Horáková",
                    "display_order": 30,
                    "active": True,
                },
                {
                    "record_type": "clen_komise",
                    "thp_worker_id": member_ids[0],
                    "display_name": "Ing. Adam Testovací",
                    "display_order": 40,
                    "active": True,
                },
                {
                    "record_type": "clen_komise",
                    "thp_worker_id": member_ids[1],
                    "display_name": "Ing. Vladimír Jindra",
                    "display_order": 50,
                    "active": True,
                },
                {
                    "record_type": "clen_komise",
                    "thp_worker_id": member_ids[2],
                    "display_name": "Boris Testovací",
                    "display_order": 60,
                    "active": True,
                },
                {
                    "record_type": "clen_komise",
                    "thp_worker_id": settings_service.save_worker(
                        first_name="Dana",
                        last_name="Testovací",
                    ).id,
                    "display_name": "Dana Testovací",
                    "display_order": 80,
                    "active": True,
                },
                {
                    "record_type": "prizvana_osoba",
                    "person_id": person_service.create_person(
                        first_name="Host",
                        last_name="Testovací",
                    ).id,
                    "display_name": "Host Testovací",
                    "display_order": 90,
                    "active": True,
                },
            ],
        )
        # Stejné THP ID nelze uložit validací služby — ověříme ID filtr přímo v datech.
        audit_commission_service.repository.add(
            AuditCommissionMember(
                audit_id=finished.id,
                record_type="clen_komise",
                thp_worker_id=workplace_rep_id,
                person_id=None,
                display_name="Cyril Testovací",
                role_text=None,
                note_text=None,
                display_order=70,
                active=True,
            )
        )

        context = audit_export_context_service.build(finished)
        members_text = context.commission_members_without_leader_text()
        self.assertEqual(
            members_text,
            "Adam Testovací\nVladimír Jindra\nBoris Testovací",
        )
        self.assertNotIn("Dana Testovací", members_text)
        self.assertNotIn("Cyril Testovací", members_text)
        self.assertNotIn("Lucie Horáková", members_text)
        self.assertNotIn("Host Testovací", members_text)

        values = context.placeholder_values()
        self.assertEqual(values["datum_zahajeni_auditu"], "01.04.2026")
        self.assertEqual(values["datum_ukonceni_auditu"], "05.04.2026")
        self.assertEqual(values["vedouci_auditor"], "Dana Testovací")
        self.assertEqual(values["zastupce_provozu"], "Cyril Testovací")
        self.assertEqual(values["zastupce_odborove_organizace"], "Lucie Horáková")
        self.assertEqual(values["clenove_komise_text"], members_text)
        self.assertIn("Lucie Horáková", values["podpis_odboru_blok"])

        path = protokol_audit_service.generate_for_audit(finished)
        content = _odt_content(path)
        self.assertIn("01.04.2026", content)
        self.assertIn("05.04.2026", content)
        self.assertIn("Adam Testovací", content)
        self.assertIn("Vladimír Jindra", content)
        self.assertIn("Boris Testovací", content)
        commission_block = content.split("Členové auditorské komise", 1)[1].split(
            "CELKOVÉ HODNOCENÍ",
            1,
        )[0]
        self.assertIn("Adam Testovací", commission_block)
        self.assertNotIn("Cyril Testovací", commission_block)
        self.assertNotIn("Dana Testovací", commission_block)
        self.assertNotIn("Lucie Horáková", commission_block)

    def test_a12_2_participants_signatures_and_appendix_page_breaks(self) -> None:
        audit = self._create_audit(
            started_at=date(2026, 5, 1),
            finished_at=date(2026, 5, 3),
        )
        assert audit is not None
        member_id = settings_service.save_worker(
            first_name="Petr",
            last_name="Svoboda",
        ).id
        leader_id = settings_service.save_worker(first_name="Jan", last_name="Novák").id
        workplace_rep_id = settings_service.save_worker(
            first_name="Eva",
            last_name="Králová",
        ).id
        union_id = person_service.create_person(
            first_name="Lucie",
            last_name="Horáková",
        ).id
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
                {
                    "record_type": "clen_komise",
                    "thp_worker_id": member_id,
                    "display_name": "Petr Svoboda",
                    "display_order": 40,
                    "active": True,
                },
            ],
        )

        context = audit_export_context_service.build(audit)
        values = context.placeholder_values()
        self.assertEqual(values["zastupce_odborove_organizace"], "Lucie Horáková")
        self.assertIn("Zástupce odborové organizace", values["podpis_odboru_blok"])
        self.assertIn("Lucie Horáková", values["podpis_odboru_blok"])
        self.assertEqual(values["clenove_komise_text"], "Petr Svoboda")

        path = protokol_audit_service.generate_for_audit(audit)
        content = _odt_content(path)

        basic = content.split("Základní informace", 1)[1].split("CELKOVÉ HODNOCENÍ", 1)[0]
        order_labels = [
            "Vedoucí auditor",
            "Zástupce auditovaného provozu",
            "Zástupce odborové organizace",
            "Členové auditorské komise",
        ]
        positions = [basic.find(label) for label in order_labels]
        self.assertTrue(all(pos >= 0 for pos in positions))
        self.assertEqual(positions, sorted(positions))

        members_cell = basic.split("Členové auditorské komise", 1)[1]
        self.assertIn("Petr Svoboda", members_cell)
        self.assertNotIn("Eva Králová", members_cell.split("Petr Svoboda", 1)[0])
        self.assertNotIn("Jan Novák", members_cell)
        # zástupce provozu je v základních informacích dříve, ne v buňce členů
        self.assertNotIn("Eva Králová", members_cell)

        main = content.split("CELKOVÉ HODNOCENÍ", 1)[1]
        self.assertLess(main.find("Podpisy"), main.find("Příloha A – Auditované procesy"))
        self.assertLess(main.find("Přijatá opatření / úkoly"), main.find("Podpisy"))
        self.assertLess(main.find("Významná zjištění"), main.find("Podpisy"))
        self.assertLess(main.find("Detail zjištění"), main.find("Podpisy"))
        after_signatures = main.split("Podpisy", 1)[1]
        for forbidden in (
            "CELKOVÉ HODNOCENÍ",
            "Přehled výsledků",
            "Silné stránky systému",
            "Oblasti vyžadující pozornost",
            "Významná zjištění",
            "Doporučení vedoucího auditora",
            "Rozsah auditu",
            "Detail zjištění",
            "Přijatá opatření / úkoly",
        ):
            self.assertNotIn(f">{forbidden}</text:p>", after_signatures)

        self.assertIn("Příloha A – Auditované procesy", content)
        self.assertIn("Příloha B – Auditní tvrzení", content)
        self.assertNotIn("Příloha – Auditované procesy", content)
        self.assertIn('fo:break-before="page"', content)
        self.assertIn('text:style-name="HPageBreak"', content)
        self.assertEqual(content.count('text:style-name="HPageBreak"'), 2)

        signatures = content.split("Podpisy", 1)[1].split("Příloha A", 1)[0]
        self.assertIn("Jan Novák", signatures)
        self.assertIn("Eva Králová", signatures)
        self.assertIn("Lucie Horáková", signatures)
        self.assertIn("Zástupce odborové organizace", signatures)

        from core.database.session import SessionLocal
        from sqlalchemy import select

        with SessionLocal() as session:
            rows = session.scalars(
                select(AuditCommissionMember).where(
                    AuditCommissionMember.audit_id == audit.id,
                    AuditCommissionMember.record_type == "zastupce_odboru",
                )
            ).all()
            for row in rows:
                session.delete(row)
            session.commit()

        audit_reloaded = audit_service.get_by_id(audit.id)
        assert audit_reloaded is not None
        values_without_union = audit_export_context_service.build(
            audit_reloaded
        ).placeholder_values()
        self.assertEqual(values_without_union["zastupce_odborove_organizace"], "Neuveden")
        self.assertEqual(values_without_union["podpis_odboru_blok"], "")

        path2 = protokol_audit_service.generate_for_audit(audit_reloaded)
        content2 = _odt_content(path2)
        basic2 = content2.split("Základní informace", 1)[1].split("CELKOVÉ HODNOCENÍ", 1)[0]
        self.assertIn("Neuveden", basic2)
        signatures2 = content2.split("Podpisy", 1)[1].split("Příloha A", 1)[0]
        self.assertNotIn("Zástupce odborové organizace", signatures2)

    def test_appendix_assertions_skips_empty_area_heading(self) -> None:
        audit = self._create_audit()
        assert audit is not None
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="rizeni_rizik",
                area_label="Řízení rizik",
                section_id="sekce",
                section_label="Sekce A",
                control_point_id="q1",
                control_point_label="Tvrzení A",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )

        text = audit_export_context_service.build(audit).appendix_assertions_text()
        self.assertIn("Sekce A", text)
        self.assertIn("🟢 Tvrzení A", text)
        self.assertNotIn("Sekce B", text)

    def test_a12_3_appendix_excludes_orphaned_methodology_assertions(self) -> None:
        """Export tiskne jen tvrzení ze spisu, která patří do aktuální metodiky auditu."""
        from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service

        audit = self._create_audit()
        assert audit is not None

        process = audit_knowledge_service.get_process_by_id("bezpecnostni_kultura")
        self.assertIsNotNone(process)
        knowledge = audit_knowledge_service.load_process_knowledge(process)
        self.assertIsNotNone(knowledge)

        section = None
        for candidate in audit_export_context_service.build(audit)._iter_knowledge_sections(
            knowledge.get("sekce") or [],
        ):
            if str(candidate.get("id") or "") == "postoj_vedeni":
                section = candidate
                break
        self.assertIsNotNone(section)
        questions = audit_knowledge_service.get_audit_questions(section)
        self.assertTrue(questions)
        current = questions[0]
        current_id = str(current.get("id") or "").strip()
        current_text = str(current.get("text") or current.get("nazev") or "").strip()
        self.assertTrue(current_id)
        self.assertTrue(current_text)

        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="bezpecnostni_kultura",
                area_label="Bezpečnostní kultura",
                section_id="postoj_vedeni",
                section_label="Postoj vedení k BOZP",
                control_point_id="legacy_bozp_postoj_vedeni_old",
                control_point_label="Staré BOZP tvrzení ze starší metodiky.",
            ),
            result=CONTROL_RESULT_NELZE_POSOUDIT,
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="bezpecnostni_kultura",
                area_label="Bezpečnostní kultura",
                section_id="postoj_vedeni",
                section_label="Postoj vedení k BOZP",
                control_point_id=current_id,
                control_point_label=current_text,
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )

        context = audit_export_context_service.build(audit)
        text = context.appendix_assertions_text()
        self.assertIn("Postoj vedení k BOZP", text)
        self.assertIn(f"🟢 {current_text}", text)
        self.assertNotIn("Staré BOZP tvrzení ze starší metodiky.", text)
        self.assertNotIn("legacy_bozp_postoj_vedeni_old", text)

        summary = context.appendix_assertions_summary_text()
        self.assertIn("Celkem auditních tvrzení: 1", summary)
        self.assertIn("🟢 Splněno: 1", summary)
        self.assertIn("⚪ Není relevantní: 0", summary)

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
