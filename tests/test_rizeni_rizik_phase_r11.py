"""Fáze R11 – export podkladů pro konzultaci s AI."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        AI_CONSULTATION_EXPORT_TYPE,
        AI_CONSULTATION_SCHEMA_VERSION,
        AI_CONSULTATION_ZIP_FILES,
        AI_EXPORT_COL_FILENAME,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
        TAB_AI_CONSULTATION,
    )
    from moduly.rizeni_rizik.modely.hazard_ai_export import HazardAiExport
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.modely.identified_hazard import IdentifiedHazard
    from moduly.rizeni_rizik.sluzby.hazard_ai_export_service import (
        HazardAiExportError,
        hazard_ai_export_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
        hazard_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
        hazard_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.identified_hazard_service import (
        identified_hazard_service,
    )
    from moduly.rizeni_rizik.ui.hazard_ai_consultation_widget import (
        HazardAiConsultationWidget,
        HazardAiExportOptionsDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import HazardIdentificationDialog


SAMPLE_CONSEQUENCE = "Zranění končetiny"


class HazardAiExportPhaseR11TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardAiExport))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(IdentifiedHazard))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Kolejiště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        person = person_service.create_person(
            first_name="Jan",
            last_name="Novák",
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
        )
        self.identification = hazard_identification_service.update_identification(
            self.identification.id,
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
            note="Testovací poznámka",
        )
        assert self.identification is not None

        self.item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lokomotiva",
            description="Posunová lokomotiva",
        )
        inactive_item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Neaktivní zařízení",
        )
        hazard_inventory_item_service.deactivate_item(inactive_item.id)

        self.hazard = identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item.id,
            name="Pohyb kolejového vozidla",
        )
        inactive_hazard = identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item.id,
            name="Neaktivní nebezpečí",
        )
        identified_hazard_service.deactivate_hazard(inactive_hazard.id)

        self.event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            identified_hazard_id=self.hazard.id,
            name="Sražení s osobou",
        )
        self.assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment.id,
            description="Výstražný signál",
        )
        hazard_required_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment.id,
            description="Instalace zábran",
        )

        self.export_dir = Path(tempfile.mkdtemp())

    def test_hazard_ai_exports_table_exists(self) -> None:
        columns = _table_columns("hazard_ai_exports")
        self.assertIn("hazard_identification_id", columns)
        self.assertIn("schema_version", columns)
        self.assertIn("file_path", columns)
        self.assertIn("item_count", columns)

    def test_export_saved_identification(self) -> None:
        target = self.export_dir / "export.zip"
        result = hazard_ai_export_service.export_consultation_package(
            self.identification.id,
            target,
        )
        self.assertTrue(target.exists())
        self.assertEqual(result.item_count, 1)
        self.assertEqual(result.hazard_count, 1)
        self.assertEqual(result.event_count, 1)
        self.assertEqual(result.assessment_count, 1)

    def test_reject_unsaved_identification(self) -> None:
        with self.assertRaises(HazardAiExportError):
            hazard_ai_export_service.export_consultation_package(
                None,
                self.export_dir / "fail.zip",
            )

    def test_export_only_active_records(self) -> None:
        payload = hazard_ai_export_service.build_payload_for_tests(self.identification.id)
        self.assertEqual(len(payload["workplace_analysis"]), 1)
        self.assertEqual(payload["workplace_analysis"][0]["name"], "Lokomotiva")
        self.assertEqual(len(payload["hazards"]), 1)
        self.assertEqual(payload["hazards"][0]["name"], "Pohyb kolejového vozidla")

    def test_export_ids_preserve_links(self) -> None:
        payload = hazard_ai_export_service.build_payload_for_tests(self.identification.id)
        self.assertEqual(payload["workplace_analysis"][0]["export_id"], "ITEM-001")
        self.assertEqual(payload["hazards"][0]["export_id"], "HAZARD-001")
        self.assertEqual(payload["hazards"][0]["source_item_export_id"], "ITEM-001")
        self.assertEqual(payload["events"][0]["export_id"], "EVENT-001")
        self.assertEqual(payload["events"][0]["hazard_export_id"], "HAZARD-001")
        self.assertEqual(payload["risk_assessments"][0]["export_id"], "ASSESSMENT-001")
        self.assertEqual(payload["risk_assessments"][0]["event_export_id"], "EVENT-001")

    def test_zip_contains_four_files(self) -> None:
        target = self.export_dir / "balicek.zip"
        hazard_ai_export_service.export_consultation_package(self.identification.id, target)
        with zipfile.ZipFile(target, "r") as zf:
            self.assertEqual(set(zf.namelist()), set(AI_CONSULTATION_ZIP_FILES))

    def test_schema_version_and_export_type(self) -> None:
        target = self.export_dir / "schema.zip"
        hazard_ai_export_service.export_consultation_package(self.identification.id, target)
        with zipfile.ZipFile(target, "r") as zf:
            payload = json.loads(zf.read("zadani.json").decode("utf-8"))
            response_schema = json.loads(zf.read("schema_odpovedi.json").decode("utf-8"))
        self.assertEqual(payload["schema_version"], AI_CONSULTATION_SCHEMA_VERSION)
        self.assertEqual(payload["export_type"], AI_CONSULTATION_EXPORT_TYPE)
        self.assertEqual(response_schema["schema_version"], "1.0")
        self.assertIn("proposals", response_schema["properties"])

    def test_no_internal_database_ids(self) -> None:
        payload = hazard_ai_export_service.build_payload_for_tests(self.identification.id)
        dumped = json.dumps(payload)

        forbidden_keys = {
            "id",
            "hazard_identification_id",
            "inventory_item_id",
            "identified_hazard_id",
            "hazard_event_id",
            "hazard_risk_assessment_id",
            "responsible_person_id",
            "operation_id",
            "workplace_id",
            "created_at",
            "updated_at",
        }

        def walk(node) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    self.assertNotIn(key, forbidden_keys)
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)
        self.assertNotIn(f'"{self.item.id}"', dumped)
        self.assertNotIn(f'"{self.hazard.id}"', dumped)
        self.assertNotIn(f'"{self.event.id}"', dumped)
        self.assertNotIn(f'"{self.assessment.id}"', dumped)

    def test_responsible_person_excluded_by_default(self) -> None:
        payload = hazard_ai_export_service.build_payload_for_tests(self.identification.id)
        self.assertNotIn("responsible_person", payload["identification"])

    def test_responsible_person_optional_include(self) -> None:
        payload = hazard_ai_export_service.build_payload_for_tests(
            self.identification.id,
            include_responsible_person=True,
        )
        self.assertIn("Novák", payload["identification"]["responsible_person"])

    def test_no_photos_or_attachments_in_zip(self) -> None:
        target = self.export_dir / "bez_priloh.zip"
        hazard_ai_export_service.export_consultation_package(self.identification.id, target)
        with zipfile.ZipFile(target, "r") as zf:
            names = zf.namelist()
        self.assertEqual(len(names), 4)
        for name in names:
            self.assertFalse(name.lower().endswith((".jpg", ".png", ".pdf", ".docx")))

    def test_creates_hazard_ai_export_record(self) -> None:
        target = self.export_dir / "evidence.zip"
        result = hazard_ai_export_service.export_consultation_package(
            self.identification.id,
            target,
        )
        records = hazard_ai_export_service.get_for_identification(self.identification.id)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].id, result.export.id)
        self.assertEqual(records[0].schema_version, AI_CONSULTATION_SCHEMA_VERSION)
        self.assertEqual(Path(records[0].file_path).name, "evidence.zip")

    def test_no_db_record_on_failed_export(self) -> None:
        target = self.export_dir / "selhani.zip"
        with patch(
            "moduly.rizeni_rizik.sluzby.hazard_ai_export_service.zipfile.ZipFile",
            side_effect=OSError("disk full"),
        ):
            with self.assertRaises(HazardAiExportError):
                hazard_ai_export_service.export_consultation_package(
                    self.identification.id,
                    target,
                )
        self.assertEqual(
            hazard_ai_export_service.get_for_identification(self.identification.id),
            [],
        )
        self.assertFalse(target.exists())

    def test_dialog_has_ai_consultation_tab(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        labels = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertIn(TAB_AI_CONSULTATION, labels)
        self.assertTrue(dialog.tabs.isTabEnabled(5))
        self.assertTrue(dialog.ai_consultation_widget.export_btn.isEnabled())

    def test_widget_lists_exports(self) -> None:
        target = self.export_dir / "seznam.zip"
        hazard_ai_export_service.export_consultation_package(self.identification.id, target)
        widget = HazardAiConsultationWidget()
        widget.set_identification(self.identification.id)
        self.assertEqual(widget.table.rowCount(), 1)
        self.assertEqual(widget.table.item(0, AI_EXPORT_COL_FILENAME).text(), "seznam.zip")

    def test_options_dialog_default_unchecked(self) -> None:
        dialog = HazardAiExportOptionsDialog()
        self.assertFalse(dialog.include_responsible_person.isChecked())


if __name__ == "__main__":
    unittest.main()
