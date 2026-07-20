"""UX-COORD-11 – důležité kontakty."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-11-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import (
        CONTACT_TYPES_DEPRECATED_FOR_NEW,
        CONTACT_TYPES_SELECTABLE,
        CONTACT_TYPE_EMERGENCY,
        CONTACT_TYPE_FIRE,
        CONTACT_TYPE_LABELS,
        CONTACT_TYPE_ORGANIZATIONAL,
        CONTACT_TYPE_OTHER,
        CONTACT_TYPE_SHIFT_SUPERVISOR,
        CONTACT_TYPE_TECHNICAL,
        CONTACT_TYPE_WORK_START_END,
        TAB_CONTACTS,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_contact_service import (
        coordination_contact_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        coordination_protocol_builder,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
        PROTOCOL_ODT_CHAPTER_TITLES,
        coordination_protocol_odt_renderer,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import (
        BozpCoordinationDialog,
    )
    from moduly.koordinace_bozp.ui.coordination_contact_dialog import (
        CoordinationContactDialog,
    )
    from moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog import (
        CoordinationProtocolPreviewDialog,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


class UxCoord11ImportantContactsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationContact))
            session.execute(delete(CoordinationEmployerActivity))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()
        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
        )

    def test_tab_uses_new_name(self) -> None:
        self.assertEqual(TAB_CONTACTS, "Důležité kontakty")
        self.assertNotEqual(TAB_CONTACTS, "Kontakty a mimořádné události")
        dialog = BozpCoordinationDialog(None)
        labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertIn("Důležité kontakty", labels)
        self.assertNotIn("Kontakty a mimořádné události", labels)
        dialog.close()

    def test_new_dialog_offers_only_selectable_types(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-11 types",
            meeting_date=date.today(),
        )
        dialog = CoordinationContactDialog(None, coordination_id=coordination.id)
        offered = [
            dialog.contact_type.itemData(i)
            for i in range(dialog.contact_type.count())
        ]
        self.assertEqual(tuple(offered), CONTACT_TYPES_SELECTABLE)
        for type_id in CONTACT_TYPES_DEPRECATED_FOR_NEW:
            self.assertNotIn(type_id, offered)
        for type_id in (
            CONTACT_TYPE_TECHNICAL,
            CONTACT_TYPE_ORGANIZATIONAL,
            CONTACT_TYPE_WORK_START_END,
            CONTACT_TYPE_SHIFT_SUPERVISOR,
            CONTACT_TYPE_OTHER,
        ):
            self.assertIn(CONTACT_TYPE_LABELS[type_id], [
                dialog.contact_type.itemText(i)
                for i in range(dialog.contact_type.count())
            ])
        dialog.close()

    def test_legacy_contact_loads_and_saves(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-11 legacy",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        contact = coordination_contact_service.add(
            coordination.id,
            contact_type=CONTACT_TYPE_EMERGENCY,
            employer_id=main.id,
            custom_name="Pohotovost",
            phone="+420111222333",
        )
        dialog = CoordinationContactDialog(
            None,
            coordination_id=coordination.id,
            contact=contact,
        )
        self.assertEqual(dialog.contact_type.currentData(), CONTACT_TYPE_EMERGENCY)
        self.assertEqual(
            dialog.contact_type.currentText(),
            CONTACT_TYPE_LABELS[CONTACT_TYPE_EMERGENCY],
        )
        # Lze uložit se stejným legacy typem.
        data = dialog.get_data()
        data["custom_name"] = "Pohotovost upravená"
        updated = coordination_contact_service.update(contact.id, **data)
        assert updated is not None
        self.assertEqual(updated.contact_type, CONTACT_TYPE_EMERGENCY)
        self.assertEqual(updated.custom_name, "Pohotovost upravená")
        # Fire zůstává dostupný při editaci.
        fire = coordination_contact_service.add(
            coordination.id,
            contact_type=CONTACT_TYPE_FIRE,
            employer_id=main.id,
            custom_name="Hasiči",
            phone="+420150",
        )
        edit_fire = CoordinationContactDialog(
            None,
            coordination_id=coordination.id,
            contact=fire,
        )
        self.assertEqual(edit_fire.contact_type.currentData(), CONTACT_TYPE_FIRE)
        edit_fire.close()
        dialog.close()

    def test_output_title_and_empty_groups_omitted(self) -> None:
        self.assertIn("Důležité kontakty", PROTOCOL_ODT_CHAPTER_TITLES)
        self.assertNotIn("Kontakty", PROTOCOL_ODT_CHAPTER_TITLES)

        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-11 output",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        coordination_contact_service.add(
            coordination.id,
            contact_type=CONTACT_TYPE_TECHNICAL,
            employer_id=main.id,
            custom_name="Technik energií",
            phone="+420100",
        )
        coordination_contact_service.add(
            coordination.id,
            contact_type=CONTACT_TYPE_SHIFT_SUPERVISOR,
            employer_id=main.id,
            custom_name="Vedoucí směny",
            phone="+420200",
        )

        result = coordination_protocol_builder.build(coordination.id)
        groups = result.protocol_data["contacts_by_type"]
        labels = [group["contact_type_label"] for group in groups]
        self.assertEqual(
            labels,
            [
                CONTACT_TYPE_LABELS[CONTACT_TYPE_TECHNICAL],
                CONTACT_TYPE_LABELS[CONTACT_TYPE_SHIFT_SUPERVISOR],
            ],
        )
        self.assertNotIn(CONTACT_TYPE_LABELS[CONTACT_TYPE_ORGANIZATIONAL], labels)
        self.assertNotIn(CONTACT_TYPE_LABELS[CONTACT_TYPE_OTHER], labels)

        target = _TMP / "contacts.odt"
        coordination_protocol_odt_renderer.render_from_result(target, result)
        content = _odt_content(target)
        self.assertIn("Důležité kontakty", content)
        self.assertIn(CONTACT_TYPE_LABELS[CONTACT_TYPE_TECHNICAL], content)
        self.assertIn("Technik energií", content)
        self.assertIn(CONTACT_TYPE_LABELS[CONTACT_TYPE_SHIFT_SUPERVISOR], content)
        self.assertNotIn(CONTACT_TYPE_LABELS[CONTACT_TYPE_ORGANIZATIONAL], content)
        self.assertNotIn("Kontakty a mimořádné události", content)

        with patch(
            "moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog."
            "coordination_protocol_builder.build",
            return_value=result,
        ):
            preview = CoordinationProtocolPreviewDialog(
                None,
                coordination_id=coordination.id,
            )
        titles = [
            group.title()
            for group in preview.findChildren(
                __import__("PySide6.QtWidgets", fromlist=["QGroupBox"]).QGroupBox
            )
        ]
        self.assertIn("Důležité kontakty", titles)
        self.assertNotIn("Kontakty a mimořádné události", titles)
        preview.close()


if __name__ == "__main__":
    unittest.main()
