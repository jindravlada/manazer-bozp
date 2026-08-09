"""OZO-SMLOUVY-7: historie OZO a historicky správný zákonný výstup."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.attachment_service import attachment_service
    from moduly.smlouvy_ozo.constants import (
        ENTITY_OZO_PERSON,
        ENTITY_OZO_PERSON_PERIOD,
        TAB_OZO_HISTORY,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_contract_list_service import (
        ozo_contract_list_service,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service
    from moduly.smlouvy_ozo.ui.ozo_person_dialog import OzoPersonDialog


class OzoSmlouvy7TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from core.models.attachment import Attachment
        from moduly.smlouvy_ozo.modely.ozo_person import OzoPerson
        from moduly.smlouvy_ozo.modely.ozo_person_period import OzoPersonPeriod

        with get_session() as session:
            session.execute(delete(Attachment))
            session.execute(delete(OzoPersonPeriod))
            session.execute(delete(OzoPerson))
            session.commit()

    def test_migrate_existing_ozo_and_attachments(self) -> None:
        # Simulace starého singletonu bez periods: přímý insert osoby + příloha.
        from core.database.session import get_session
        from moduly.smlouvy_ozo.modely.ozo_person import OzoPerson

        with get_session() as session:
            person = OzoPerson(
                first_name="Jan",
                last_name="Novák",
                title_before="Ing.",
                certificate_number="12345",
                exam_date=date(2021, 5, 10),
            )
            session.add(person)
            session.commit()
            session.refresh(person)
            person_id = person.id

        tmp = Path(tempfile.mkdtemp()) / "osvedceni-stare.pdf"
        tmp.write_bytes(b"%PDF-old")
        attachment_service.add_file(ENTITY_OZO_PERSON, person_id, str(tmp))
        self.assertEqual(
            len(attachment_service.get_for_entity(ENTITY_OZO_PERSON, person_id)),
            1,
        )

        period = ozo_person_service.ensure_migrated()
        self.assertIsNotNone(period)
        self.assertEqual(period.certificate_number, "12345")
        self.assertEqual(period.valid_from, date(2021, 5, 10))
        self.assertIsNone(period.valid_to)
        self.assertEqual(
            attachment_service.get_for_entity(ENTITY_OZO_PERSON, person_id),
            [],
        )
        moved = attachment_service.get_for_entity(
            ENTITY_OZO_PERSON_PERIOD, period.id
        )
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0].filename, "osvedceni-stare.pdf")

    def test_new_exam_creates_period_and_closes_previous(self) -> None:
        ozo_person_service.save(
            title_before="Ing.",
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="12345",
        )
        first = ozo_person_service.get_open_period()
        self.assertIsNotNone(first)
        first_id = first.id

        tmp = Path(tempfile.mkdtemp()) / "cert-2021.pdf"
        tmp.write_bytes(b"%PDF-2021")
        attachment_service.add_file(ENTITY_OZO_PERSON_PERIOD, first_id, str(tmp))

        ozo_person_service.save(
            title_before="Ing.",
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2026, 4, 15),
            certificate_number="67890",
        )
        open_period = ozo_person_service.get_open_period()
        self.assertIsNotNone(open_period)
        self.assertNotEqual(open_period.id, first_id)
        self.assertEqual(open_period.certificate_number, "67890")
        self.assertEqual(open_period.valid_from, date(2026, 4, 15))

        closed = ozo_person_service.get_period(first_id)
        self.assertIsNotNone(closed)
        self.assertEqual(closed.valid_to, date(2026, 4, 14))
        self.assertEqual(closed.certificate_number, "12345")

        # Staré přílohy zůstaly na uzavřené verzi.
        self.assertEqual(
            len(attachment_service.get_for_entity(ENTITY_OZO_PERSON_PERIOD, first_id)),
            1,
        )
        self.assertEqual(
            attachment_service.get_for_entity(
                ENTITY_OZO_PERSON_PERIOD, open_period.id
            ),
            [],
        )

    def test_history_not_overwritten(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="12345",
        )
        old_id = ozo_person_service.get_open_period().id
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2026, 4, 15),
            certificate_number="67890",
        )
        # Oprava překlepu v aktuální verzi nesmí měnit historii.
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2026, 4, 15),
            certificate_number="67890-X",
        )
        closed = ozo_person_service.get_period(old_id)
        self.assertEqual(closed.certificate_number, "12345")
        self.assertEqual(
            ozo_person_service.get_open_period().certificate_number,
            "67890-X",
        )

    def test_list_past_year_uses_old_certificate(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="12345",
        )
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2028, 3, 1),
            certificate_number="67890",
        )
        html = ozo_contract_list_service.build_html(2026)
        self.assertIn("12345", html)
        self.assertNotIn("67890", html)
        self.assertIn("Jan Novák", html)

    def test_year_with_midyear_change_lists_both_periods(self) -> None:
        ozo_person_service.save(
            title_before="Ing.",
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="12345",
        )
        ozo_person_service.save(
            title_before="Ing.",
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2026, 4, 15),
            certificate_number="67890",
        )
        html = ozo_contract_list_service.build_html(2026)
        self.assertIn("12345", html)
        self.assertIn("67890", html)
        self.assertIn("01.01.2026–14.04.2026", html)
        self.assertIn("15.04.2026–31.12.2026", html)

    def test_single_period_year_keeps_simple_header(self) -> None:
        ozo_person_service.save(
            first_name="Eva",
            last_name="Svobodová",
            exam_date=date(2024, 1, 1),
            certificate_number="CERT-ONE",
        )
        html = ozo_contract_list_service.build_html(2026)
        self.assertIn("Odborně způsobilá osoba:", html)
        self.assertIn("Číslo osvědčení:", html)
        self.assertIn("CERT-ONE", html)
        self.assertNotIn("období:", html)

    def test_validation_for_year_checks_used_periods(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="12345",
        )
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2026, 4, 15),
            certificate_number="",  # chybí u nové verze
        )
        missing = ozo_contract_list_service.missing_ozo_fields(2026)
        self.assertTrue(any("Číslo osvědčení" in item for item in missing))

    def test_dialog_history_tab_and_period_attachments(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="12345",
        )
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2026, 4, 15),
            certificate_number="67890",
        )
        dialog = OzoPersonDialog()
        self.assertEqual(dialog.tabs.tabText(1), TAB_OZO_HISTORY)
        self.assertEqual(dialog.attachments.entity_type, ENTITY_OZO_PERSON_PERIOD)
        self.assertIsNotNone(dialog.period)
        self.assertEqual(dialog.attachments.entity_id, dialog.period.id)
        self.assertGreaterEqual(dialog.history_table.rowCount(), 1)
        dialog.close()

    def test_pdf_matches_historical_html(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="12345",
        )
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2028, 1, 1),
            certificate_number="67890",
        )
        html = ozo_contract_list_service.build_html(2026)
        out = Path(tempfile.mkdtemp()) / "ozo-2026.pdf"
        ozo_contract_list_service.write_pdf(html, out)
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 0)
        self.assertIn("12345", html)
        self.assertNotIn("67890", html)


if __name__ == "__main__":
    unittest.main()
