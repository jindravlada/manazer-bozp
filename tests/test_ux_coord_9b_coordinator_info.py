"""UX-COORD-9b – další informace koordinátora ve výstupu dohody."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QFormLayout, QLabel
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-9b-"))
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
        PROTOCOL_CONCLUSION_4_COORDINATOR_INTRO,
        PROTOCOL_SECTION_CONCLUSIONS,
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
    from moduly.koordinace_bozp.sluzby.coordination_coordinator_service import (
        coordination_coordinator_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        coordination_protocol_builder,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_document import (
        render_blocks_to_plain_lines,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
        coordination_protocol_odt_renderer,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


class UxCoord9bCoordinatorInfoTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

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
            address="Praha 1",
            nace="",
            abbreviation="",
        )

    def test_ui_label_dalsi_informace(self) -> None:
        self.assertIn(
            "Stanovení koordinátora",
            PROTOCOL_CONCLUSION_4_COORDINATOR_INTRO,
        )
        dialog = BozpCoordinationDialog(None)
        form = dialog.coordinator_tab.form
        labels = []
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, QLabel):
                labels.append(widget.text())
        self.assertIn("Další informace:", labels)
        self.assertNotIn("Poznámka:", labels)
        dialog.mark_clean()
        dialog.close()

    def test_note_persists_as_additional_info(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9b persist",
            meeting_date=date.today(),
        )
        saved = coordination_coordinator_service.set_coordinator(
            coordination.id,
            full_name="Jan Koordinátor",
            employer_name="Hlavní firma s.r.o.",
            role="koordinátor BOZP",
            phone="+420111",
            email="jan@example.com",
            note="Starší uložená poznámka k dohodě.",
        )
        reloaded = coordination_coordinator_service.get_for_coordination(
            coordination.id
        )
        assert reloaded is not None
        self.assertEqual(reloaded.note, "Starší uložená poznámka k dohodě.")
        self.assertEqual(saved.note, reloaded.note)

        dialog = BozpCoordinationDialog(None, coordination=coordination)
        self.assertEqual(
            dialog.coordinator_tab.note.toPlainText(),
            "Starší uložená poznámka k dohodě.",
        )
        dialog.mark_clean()
        dialog.close()

    def test_output_shows_coordinator_and_additional_info(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9b output",
            meeting_date=date.today(),
        )
        coordination_coordinator_service.set_coordinator(
            coordination.id,
            full_name="Jan Koordinátor",
            employer_name="Hlavní firma s.r.o.",
            role="koordinátor BOZP",
            phone="+420111",
            email="jan@example.com",
            note="Kontaktovat před vstupem na stavbu.",
        )
        result = coordination_protocol_builder.build(coordination.id)
        lines = render_blocks_to_plain_lines(
            result.protocol_data["document"]["blocks"]
        )
        self.assertIn("Jméno: Jan Koordinátor", lines)
        self.assertIn("Organizace: Hlavní firma s.r.o.", lines)
        self.assertIn("Funkce: koordinátor BOZP", lines)
        self.assertIn("Telefon: +420111", lines)
        self.assertIn("E-mail: jan@example.com", lines)
        self.assertIn("Další informace:", lines)
        self.assertIn("Kontaktovat před vstupem na stavbu.", lines)
        info_index = lines.index("Další informace:")
        self.assertEqual(lines[info_index + 1], "Kontaktovat před vstupem na stavbu.")

        target = _TMP / "coord-info.odt"
        coordination_protocol_odt_renderer.render_from_result(target, result)
        content = _odt_content(target)
        self.assertIn(PROTOCOL_CONCLUSION_4_COORDINATOR_INTRO, content)
        self.assertIn("Další informace:", content)
        self.assertIn("Kontaktovat před vstupem na stavbu.", content)
        self.assertIn("Organizace:", content)
        self.assertIn("Hlavní firma s.r.o.", content)

    def test_empty_note_and_contacts_omitted(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9b empty",
            meeting_date=date.today(),
        )
        coordination_coordinator_service.set_coordinator(
            coordination.id,
            full_name="Petr Bez Kontaktu",
            employer_name="Firma s.r.o.",
            role="",
            phone="",
            email="",
            note="",
        )
        result = coordination_protocol_builder.build(coordination.id)
        lines = render_blocks_to_plain_lines(
            result.protocol_data["document"]["blocks"]
        )
        self.assertIn("Jméno: Petr Bez Kontaktu", lines)
        self.assertIn("Organizace: Firma s.r.o.", lines)
        self.assertIn("Funkce: —", lines)
        self.assertIn("Telefon: —", lines)
        self.assertIn("E-mail: —", lines)
        self.assertNotIn("Další informace", lines)

        target = _TMP / "coord-empty.odt"
        coordination_protocol_odt_renderer.render_from_result(target, result)
        content = _odt_content(target)
        self.assertIn("Petr Bez Kontaktu", content)
        self.assertNotIn("Další informace", content)


if __name__ == "__main__":
    unittest.main()
