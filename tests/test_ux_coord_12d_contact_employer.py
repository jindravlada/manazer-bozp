"""UX-COORD-12d – zaměstnavatel důležitého kontaktu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-12d-"))
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
        CONTACT_TYPE_TECHNICAL,
        CTC_COL_EMPLOYER,
        CONTACT_TABLE_HEADERS,
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
        CONTACT_EMPLOYER_UNSPECIFIED,
        CoordinationContactError,
        coordination_contact_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
        coordination_participant_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        coordination_protocol_builder,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
        coordination_protocol_odt_renderer,
    )
    from moduly.koordinace_bozp.ui.coordination_contact_dialog import (
        CoordinationContactDialog,
    )
    from moduly.koordinace_bozp.ui.coordination_contacts_tab import (
        CoordinationContactsTab,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path) as zin:
        return zin.read("content.xml").decode("utf-8")


class UxCoord12dContactEmployerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
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

    def _setup(self):
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-12d",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="ZX - Zkušební firma, a.s.",
            abbreviation="ZX-ZF",
        )
        participant = coordination_participant_service.add_manual(
            contractor.id,
            full_name="Jan Novák",
            role="technik",
            phone="+420111",
            email="jan@example.com",
        )
        return coordination, main, contractor, participant

    def test_manual_requires_employer(self) -> None:
        coordination, _main, _contractor, _participant = self._setup()
        with self.assertRaises(CoordinationContactError) as ctx:
            coordination_contact_service.add(
                coordination.id,
                custom_name="Bez zaměstnavatele",
                phone="+420100",
            )
        self.assertIn("zaměstnavatel", str(ctx.exception).casefold())

    def test_participant_inherits_employer(self) -> None:
        coordination, _main, contractor, participant = self._setup()
        snapshot = coordination_contact_service.snapshot_from_participant(participant.id)
        self.assertEqual(snapshot["employer_id"], contractor.id)

        dialog = CoordinationContactDialog(
            None,
            coordination_id=coordination.id,
        )
        dialog.source_participant.setChecked(True)
        index = dialog.participant.findData(participant.id)
        self.assertGreaterEqual(index, 0)
        dialog.participant.setCurrentIndex(index)
        self.assertEqual(dialog.employer.currentData(), contractor.id)
        self.assertFalse(dialog.employer.isEnabled())
        data = dialog.get_data()
        self.assertEqual(data["employer_id"], contractor.id)
        contact = coordination_contact_service.add(coordination.id, **data)
        self.assertEqual(contact.employer_id, contractor.id)
        self.assertEqual(contact.employer_name, contractor.company_name)
        dialog.close()

    def test_table_shows_abbreviation_and_tooltip(self) -> None:
        coordination, _main, contractor, _participant = self._setup()
        coordination_contact_service.add(
            coordination.id,
            employer_id=contractor.id,
            contact_type=CONTACT_TYPE_TECHNICAL,
            custom_name="Jan Novák",
            role="technik",
            phone="+420111",
        )
        tab = CoordinationContactsTab(None, coordination_id=coordination.id)
        self.assertEqual(CONTACT_TABLE_HEADERS[CTC_COL_EMPLOYER], "Zaměstnavatel")
        self.assertEqual(tab.table.rowCount(), 1)
        cell = tab.table.item(0, CTC_COL_EMPLOYER)
        self.assertEqual(cell.text(), "ZX-ZF")
        self.assertNotIn(" – ", cell.text())
        self.assertNotIn("Zkušební firma", cell.text())
        self.assertEqual(cell.toolTip(), contractor.company_name)
        tab.close()

    def test_preview_and_odt_include_employer(self) -> None:
        coordination, _main, contractor, _participant = self._setup()
        coordination_contact_service.add(
            coordination.id,
            employer_id=contractor.id,
            contact_type=CONTACT_TYPE_TECHNICAL,
            custom_name="Jan Novák",
            role="technik",
            phone="+420111",
            email="jan@example.com",
        )
        result = coordination_protocol_builder.build(coordination.id)
        groups = result.protocol_data["contacts_by_type"]
        self.assertEqual(len(groups), 1)
        employer_groups = groups[0]["employer_groups"]
        self.assertEqual(employer_groups[0]["employer_label"], "ZX-ZF")
        contact = employer_groups[0]["contacts"][0]
        self.assertEqual(contact["employer_label"], "ZX-ZF")
        self.assertEqual(contact["employer_name"], contractor.company_name)

        target = _TMP / "contact-employer.odt"
        coordination_protocol_odt_renderer.render_from_result(target, result)
        content = _odt_content(target)
        self.assertIn("ZX-ZF", content)
        self.assertIn("Jan Novák, technik", content)
        self.assertIn("Telefon: +420111", content)
        self.assertIn("E-mail: jan@example.com", content)

    def test_legacy_contact_without_employer_preserved(self) -> None:
        coordination, _main, _contractor, _participant = self._setup()
        legacy = CoordinationContact(
            coordination_id=coordination.id,
            participant_id=None,
            employer_id=None,
            contact_type=CONTACT_TYPE_TECHNICAL,
            custom_name="Starý kontakt",
            employer_name="",
            role="",
            phone="+420999",
            email="",
            note="",
            active=True,
            sort_order=1,
        )
        saved = coordination_contact_service.repository.add(legacy)
        reloaded = coordination_contact_service.get_by_id(saved.id)
        assert reloaded is not None
        self.assertIsNone(reloaded.employer_id)
        self.assertEqual(reloaded.custom_name, "Starý kontakt")
        self.assertEqual(
            coordination_contact_service.employer_display_label(reloaded),
            CONTACT_EMPLOYER_UNSPECIFIED,
        )

        tab = CoordinationContactsTab(None, coordination_id=coordination.id)
        self.assertEqual(
            tab.table.item(0, CTC_COL_EMPLOYER).text(),
            CONTACT_EMPLOYER_UNSPECIFIED,
        )
        tab.close()


if __name__ == "__main__":
    unittest.main()
