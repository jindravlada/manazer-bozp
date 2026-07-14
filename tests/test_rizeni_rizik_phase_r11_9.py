"""Fáze R11.9 – odstranění jména odpovědné osoby z AI exportu."""

from __future__ import annotations

import importlib
import json
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

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.ai_oponentni.constants import AI_PEER_REVIEW_ZIP_FILES
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewExportOptionsDialog
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
        hazard_identification_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )


class AiPeerReviewNoPersonalDataR119TestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R119",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Pracoviště R119",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        person = person_service.create_person(
            first_name="Karel",
            last_name="Tajny",
        )
        self.person_name = "Karel Tajny"
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
        )
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lis",
        )
        self.provider = hazard_identification_peer_review_provider
        self.export_dir = Path(tempfile.mkdtemp())

    def test_dialog_has_no_responsible_person_option(self) -> None:
        dialog = AiPeerReviewExportOptionsDialog()
        self.assertFalse(hasattr(dialog, "include_responsible_person"))
        options = dialog.get_options()
        self.assertFalse(hasattr(options, "include_responsible_person"))
        serialized = json.dumps(options.__dict__, ensure_ascii=False)
        self.assertNotIn("include_responsible_person", serialized)
        self.assertNotIn("responsible_person", serialized)

    def test_export_never_contains_responsible_person_name(self) -> None:
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        payload = "\n".join(
            [
                content.prompt_text,
                content.data_text,
                content.overview_text,
                json.dumps(content.batches[0].zadani_json, ensure_ascii=False),
            ]
        )
        self.assertNotIn(self.person_name, payload)
        self.assertNotIn("Karel", payload)
        self.assertNotIn("Tajny", payload)
        self.assertNotIn("Odpovědná osoba", payload)
        self.assertNotIn("responsible_person", payload)
        self.assertNotIn("include_responsible_person", payload)

        # Hierarchie dat zůstává
        self.assertIn("workplace_analysis", content.batches[0].zadani_json)
        self.assertEqual(
            content.batches[0].zadani_json["workplace_analysis"][0]["name"],
            "Lis",
        )

    def test_zip_export_has_no_personal_data(self) -> None:
        target = self.export_dir / "r119.zip"
        ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
            options=AiPeerReviewExportOptions(),
        )
        with zipfile.ZipFile(target, "r") as zf:
            self.assertEqual(set(zf.namelist()), set(AI_PEER_REVIEW_ZIP_FILES))
            for name in AI_PEER_REVIEW_ZIP_FILES:
                text = zf.read(name).decode("utf-8")
                self.assertNotIn(self.person_name, text)
                self.assertNotIn("Odpovědná osoba", text)
                self.assertNotIn("responsible_person", text)


if __name__ == "__main__":
    unittest.main()
