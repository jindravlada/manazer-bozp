"""OZO-HIST-2: doplnění historických osvědčení do časové osy."""

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

    from core.dashboard.attention_item import ITEM_TYPE_OZO_PERSON_CERTIFICATE
    from core.dashboard.attention_service import get_attention_items
    from core.services.attachment_service import attachment_service
    from moduly.smlouvy_ozo.constants import (
        ACTION_ADD_HISTORICAL_CERTIFICATE,
        ENTITY_OZO_PERSON_PERIOD,
        HISTORY_CERTIFICATE_VALID_TO_LABEL,
        HISTORY_USAGE_FROM_LABEL,
        HISTORY_USAGE_TO_LABEL,
        UNIT_MONTHS,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_contract_list_service import (
        ozo_contract_list_service,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_person_service import (
        OzoPersonValidationError,
        ozo_person_service,
    )
    from moduly.smlouvy_ozo.ui.ozo_period_detail_dialog import OzoPeriodDetailDialog
    from moduly.smlouvy_ozo.ui.ozo_person_dialog import OzoPersonDialog


class OzoHist2TestCase(unittest.TestCase):
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

    def _ozo_attention(self, today: date):
        return [
            item
            for item in get_attention_items(today=today)
            if item.item_type == ITEM_TYPE_OZO_PERSON_CERTIFICATE
        ]

    def test_insert_before_first_period(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2013, 6, 15),
            certificate_number="NEW",
            certificate_valid_to=date(2018, 6, 15),
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )
        open_before = ozo_person_service.get_open_period()
        open_id = open_before.id
        open_cert_to = open_before.certificate_valid_to

        inserted = ozo_person_service.insert_historical_period(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2008, 8, 10),
            certificate_number="OLD",
            certificate_valid_to=date(2013, 8, 10),
        )
        self.assertEqual(inserted.valid_from, date(2008, 8, 10))
        self.assertEqual(inserted.valid_to, date(2013, 6, 14))
        self.assertEqual(inserted.certificate_valid_to, date(2013, 8, 10))

        open_period = ozo_person_service.get_open_period()
        self.assertEqual(open_period.id, open_id)
        self.assertEqual(open_period.certificate_number, "NEW")
        self.assertEqual(open_period.certificate_valid_to, open_cert_to)
        self.assertIsNone(open_period.valid_to)

        closed = ozo_person_service.list_closed_periods()
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].id, inserted.id)

    def test_insert_between_two_periods(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2008, 8, 10),
            certificate_number="A",
            certificate_valid_to=date(2013, 8, 10),
        )
        first_id = ozo_person_service.get_open_period().id
        tmp = Path(tempfile.mkdtemp()) / "a.pdf"
        tmp.write_bytes(b"%PDF-a")
        attachment_service.add_file(ENTITY_OZO_PERSON_PERIOD, first_id, str(tmp))

        ozo_person_service.renew(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2018, 1, 1),
            certificate_number="C",
            certificate_valid_to=date(2023, 1, 1),
        )
        open_id = ozo_person_service.get_open_period().id
        first = ozo_person_service.get_period(first_id)
        first_cert_to = first.certificate_valid_to

        middle = ozo_person_service.insert_historical_period(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2013, 6, 15),
            certificate_number="B",
            certificate_valid_to=date(2018, 6, 15),
        )
        first = ozo_person_service.get_period(first_id)
        open_period = ozo_person_service.get_open_period()

        self.assertEqual(first.valid_to, date(2013, 6, 14))
        self.assertEqual(first.certificate_valid_to, first_cert_to)
        self.assertEqual(middle.valid_from, date(2013, 6, 15))
        self.assertEqual(middle.valid_to, date(2017, 12, 31))
        self.assertEqual(middle.certificate_valid_to, date(2018, 6, 15))
        self.assertEqual(open_period.id, open_id)
        self.assertIsNone(open_period.valid_to)
        self.assertEqual(
            len(attachment_service.get_for_entity(ENTITY_OZO_PERSON_PERIOD, first_id)),
            1,
        )
        self.assertEqual(
            attachment_service.get_for_entity(
                ENTITY_OZO_PERSON_PERIOD, middle.id
            ),
            [],
        )

    def test_insert_does_not_change_current_ozo_or_attention(self) -> None:
        ozo_person_service.save(
            first_name="Eva",
            last_name="Testová",
            exam_date=date(2021, 1, 1),
            certificate_number="CUR",
            certificate_valid_to=date(2030, 1, 15),
            notify_before_value=0,
        )
        person_before = ozo_person_service.get()
        attention_before = self._ozo_attention(date(2030, 1, 16))
        self.assertEqual(len(attention_before), 1)

        ozo_person_service.insert_historical_period(
            first_name="Eva",
            last_name="Testová",
            exam_date=date(2016, 1, 1),
            certificate_number="OLD",
            certificate_valid_to=date(2021, 1, 1),
        )
        person_after = ozo_person_service.get()
        self.assertEqual(person_after.certificate_number, person_before.certificate_number)
        self.assertEqual(person_after.exam_date, person_before.exam_date)
        self.assertEqual(person_after.certificate_valid_to, person_before.certificate_valid_to)
        attention_after = self._ozo_attention(date(2030, 1, 16))
        self.assertEqual(len(attention_after), 1)
        self.assertEqual(attention_after[0].title, attention_before[0].title)

    def test_chronological_list_uses_inserted_period(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="2021",
        )
        ozo_person_service.insert_historical_period(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2016, 3, 1),
            certificate_number="2016",
            certificate_valid_to=date(2021, 3, 1),
        )
        html = ozo_contract_list_service.build_html(2018)
        self.assertIn("2016", html)
        self.assertNotIn("2021", html)

    def test_duplicate_exam_date_rejected(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="X",
        )
        with self.assertRaises(OzoPersonValidationError):
            ozo_person_service.insert_historical_period(
                first_name="Jan",
                last_name="Novák",
                exam_date=date(2021, 5, 10),
                certificate_number="Y",
            )

    def test_newer_than_current_requires_renew(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="X",
        )
        with self.assertRaises(OzoPersonValidationError):
            ozo_person_service.insert_historical_period(
                first_name="Jan",
                last_name="Novák",
                exam_date=date(2026, 1, 1),
                certificate_number="Y",
            )

    def test_history_labels_and_action(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="X",
        )
        dialog = OzoPersonDialog()
        self.assertEqual(dialog.historical_btn.text(), ACTION_ADD_HISTORICAL_CERTIFICATE)
        headers = [
            dialog.history_table.horizontalHeaderItem(i).text()
            for i in range(dialog.history_table.columnCount())
        ]
        self.assertEqual(headers[0], HISTORY_USAGE_FROM_LABEL)
        self.assertEqual(headers[1], HISTORY_USAGE_TO_LABEL)
        self.assertEqual(headers[5], HISTORY_CERTIFICATE_VALID_TO_LABEL)
        dialog.close()

        ozo_person_service.insert_historical_period(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2016, 1, 1),
            certificate_number="OLD",
            certificate_valid_to=date(2021, 1, 1),
        )
        closed = ozo_person_service.list_closed_periods()[0]
        detail = OzoPeriodDetailDialog(period=closed)
        from PySide6.QtWidgets import QLabel

        texts = [w.text() for w in detail.findChildren(QLabel)]
        self.assertTrue(any(HISTORY_USAGE_FROM_LABEL in text for text in texts))
        self.assertTrue(any(HISTORY_USAGE_TO_LABEL in text for text in texts))
        self.assertTrue(
            any(HISTORY_CERTIFICATE_VALID_TO_LABEL in text for text in texts)
        )
        detail.close()


if __name__ == "__main__":
    unittest.main()
