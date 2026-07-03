import importlib
import io
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
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_export_context_service import audit_export_context_service
    from moduly.audity.sluzby.audit_service import audit_service


def _ensure_audit_protocol_template() -> Path:
    import moduly.audity.sluzby.protokol_audit_service as protokol_module

    importlib.reload(protokol_module)
    path = protokol_module.protokol_audit_service.template_path()
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    content = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opentopic:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opentopic:xmlns:text:1.0">
<office:body><office:text>
<text:p>${cislo_auditu}</text:p>
<text:p>${statistika_text}</text:p>
<text:p>${zjisteni_text}</text:p>
<text:p>${ukoly_text}</text:p>
<text:p>${souhrn_text}</text:p>
</office:text></office:body></office:document-content>"""
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opentopic:xmlns:manifest:1.0">
 <manifest:file-entry manifest:media-type="application/vnd.oasis.opendocument.text" manifest:full-path="/"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="content.xml"/>
</manifest:manifest>"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zout:
        zout.writestr(
            "mimetype",
            "application/vnd.oasis.opendocument.text",
            compress_type=zipfile.ZIP_STORED,
        )
        zout.writestr("content.xml", content)
        zout.writestr("META-INF/manifest.xml", manifest)
    path.write_bytes(buffer.getvalue())
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
        self.assertIn("Počet kontrolovaných oblastí: 1", content)
        self.assertIn("Počet hodnocení Vyhovuje: 1", content)

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

        path = protokol_audit_service.generate_for_audit(audit)
        content = _odt_content(path)
        self.assertIn("🟡 Vyhovuje s doporučením", content)
        self.assertIn("🔴 Nevyhovuje", content)
        self.assertNotIn("Vyhovuje tvrzení", content)

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
            "hodnoceni_text",
            "zjisteni_text",
            "ukoly_text",
            "zaver_text",
            "statistika_text",
            "souhrn_text",
            "datum_vygenerovani",
        }
        self.assertEqual(set(values.keys()), expected_keys)

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
