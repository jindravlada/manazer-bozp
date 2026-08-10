"""OZO-HIST-3: oprava obnovy osvědčení OZO."""

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

_TMP = Path(tempfile.mkdtemp(prefix="ozo-hist-3-"))

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
    from moduly.smlouvy_ozo.constants import ENTITY_OZO_PERSON_PERIOD, UNIT_MONTHS
    from moduly.smlouvy_ozo.sluzby.ozo_contract_list_service import (
        ozo_contract_list_service,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_person_service import (
        OzoPersonValidationError,
        ozo_person_service,
    )


class OzoHist3TestCase(unittest.TestCase):
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

    def _seed_current(
        self,
        *,
        exam_date: date = date(2015, 10, 20),
        certificate_valid_to: date = date(2020, 10, 20),
        corrupt_valid_from: date | None = None,
    ):
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=exam_date,
            certificate_number="OZO-2015",
            certificate_valid_to=certificate_valid_to,
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )
        period = ozo_person_service.get_open_period()
        assert period is not None
        if corrupt_valid_from is not None:
            period.valid_from = corrupt_valid_from
            ozo_person_service.period_repository.update(period)
        return period

    def _ozo_attention(self, today: date):
        return [
            item
            for item in get_attention_items(today=today)
            if item.item_type == ITEM_TYPE_OZO_PERSON_CERTIFICATE
        ]

    def test_a_renew_before_old_certificate_valid_to(self) -> None:
        old = self._seed_current()
        old_cert_to = old.certificate_valid_to

        ozo_person_service.renew(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2020, 9, 15),
            certificate_number="OZO-2020",
            certificate_valid_to=date(2025, 9, 15),
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )

        closed = ozo_person_service.get_period(old.id)
        open_period = ozo_person_service.get_open_period()
        self.assertEqual(closed.certificate_valid_to, old_cert_to)
        self.assertEqual(closed.valid_to, date(2020, 9, 14))
        self.assertEqual(open_period.valid_from, date(2020, 9, 15))
        self.assertIsNone(open_period.valid_to)
        self.assertEqual(open_period.exam_date, date(2020, 9, 15))

    def test_b_renew_on_certificate_valid_to_day(self) -> None:
        old = self._seed_current()
        ozo_person_service.renew(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2020, 10, 20),
            certificate_number="OZO-2020B",
            certificate_valid_to=date(2025, 10, 20),
        )
        closed = ozo_person_service.get_period(old.id)
        open_period = ozo_person_service.get_open_period()
        self.assertEqual(closed.valid_to, date(2020, 10, 19))
        self.assertEqual(closed.certificate_valid_to, date(2020, 10, 20))
        self.assertEqual(open_period.valid_from, date(2020, 10, 20))
        self.assertIsNone(open_period.valid_to)

    def test_c_renew_after_certificate_valid_to(self) -> None:
        old = self._seed_current()
        ozo_person_service.renew(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 1, 10),
            certificate_number="OZO-2021",
            certificate_valid_to=date(2026, 1, 10),
        )
        closed = ozo_person_service.get_period(old.id)
        open_period = ozo_person_service.get_open_period()
        self.assertEqual(closed.valid_to, date(2021, 1, 9))
        self.assertEqual(closed.certificate_valid_to, date(2020, 10, 20))
        self.assertEqual(open_period.exam_date, date(2021, 1, 10))
        self.assertIsNone(open_period.valid_to)

    def test_d_renew_not_after_current_exam_rejected(self) -> None:
        self._seed_current(exam_date=date(2015, 10, 20))
        with self.assertRaises(OzoPersonValidationError):
            ozo_person_service.renew(
                first_name="Jan",
                last_name="Novák",
                exam_date=date(2015, 10, 20),
                certificate_number="SAME",
            )
        with self.assertRaises(OzoPersonValidationError):
            ozo_person_service.renew(
                first_name="Jan",
                last_name="Novák",
                exam_date=date(2015, 10, 19),
                certificate_number="OLDER",
            )

    def test_e_f_g_certificate_valid_to_and_single_open(self) -> None:
        old = self._seed_current()
        old_cert_to = old.certificate_valid_to
        ozo_person_service.renew(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2020, 9, 15),
            certificate_number="OZO-2020",
            certificate_valid_to=date(2025, 9, 15),
        )
        closed = ozo_person_service.get_period(old.id)
        periods = ozo_person_service.list_periods()
        open_periods = [p for p in periods if p.valid_to is None]
        self.assertEqual(closed.certificate_valid_to, old_cert_to)
        self.assertEqual(closed.valid_to, date(2020, 9, 14))
        self.assertEqual(len(open_periods), 1)
        self.assertEqual(open_periods[0].certificate_number, "OZO-2020")

    def test_h_attachments_stay_on_old_period(self) -> None:
        old = self._seed_current()
        tmp = Path(tempfile.mkdtemp()) / "ozo-old.pdf"
        tmp.write_bytes(b"%PDF-ozo-old")
        attachment_service.add_file(ENTITY_OZO_PERSON_PERIOD, old.id, str(tmp))

        ozo_person_service.renew(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2020, 9, 15),
            certificate_number="OZO-2020",
            certificate_valid_to=date(2025, 9, 15),
        )
        open_period = ozo_person_service.get_open_period()
        self.assertEqual(
            len(attachment_service.get_for_entity(ENTITY_OZO_PERSON_PERIOD, old.id)),
            1,
        )
        self.assertEqual(
            attachment_service.get_for_entity(
                ENTITY_OZO_PERSON_PERIOD, open_period.id
            ),
            [],
        )

    def test_i_attention_uses_new_open_period(self) -> None:
        self._seed_current(
            exam_date=date(2015, 10, 20),
            certificate_valid_to=date(2020, 10, 20),
        )
        before = self._ozo_attention(date(2020, 10, 21))
        self.assertEqual(len(before), 1)

        ozo_person_service.renew(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2020, 9, 15),
            certificate_number="OZO-2020",
            certificate_valid_to=date(2025, 9, 15),
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )
        after = self._ozo_attention(date(2020, 10, 21))
        self.assertEqual(after, [])
        open_period = ozo_person_service.get_open_period()
        self.assertEqual(open_period.certificate_valid_to, date(2025, 9, 15))

    def test_j_chronological_output_uses_usage_timeline(self) -> None:
        old = self._seed_current()
        ozo_person_service.renew(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2020, 9, 15),
            certificate_number="OZO-2020",
            certificate_valid_to=date(2025, 9, 15),
        )
        periods = ozo_person_service.periods_for_year(2020)
        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[0].id, old.id)
        self.assertEqual(periods[0].valid_from, date(2015, 10, 20))
        self.assertEqual(periods[0].valid_to, date(2020, 9, 14))
        self.assertEqual(periods[1].valid_from, date(2020, 9, 15))
        self.assertIsNone(periods[1].valid_to)

        html = ozo_contract_list_service.build_html(2020)
        self.assertIn("OZO-2015", html)
        self.assertIn("OZO-2020", html)
        self.assertIn("01.01.2020–14.09.2020", html)
        self.assertIn("15.09.2020–31.12.2020", html)

    def test_corrupt_valid_from_normalized_and_renew_works(self) -> None:
        """Po chybné migraci (valid_from = dnes) musí normalizace a renew projít."""
        old = self._seed_current(corrupt_valid_from=date(2026, 8, 10))
        self.assertEqual(old.exam_date, date(2015, 10, 20))

        # Načtení spustí normalizaci časové osy.
        fixed = ozo_person_service.get_open_period()
        self.assertEqual(fixed.valid_from, date(2015, 10, 20))
        self.assertEqual(fixed.exam_date, date(2015, 10, 20))
        self.assertEqual(fixed.certificate_valid_to, date(2020, 10, 20))

        ozo_person_service.renew(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2020, 9, 15),
            certificate_number="OZO-2020",
            certificate_valid_to=date(2025, 9, 15),
        )
        closed = ozo_person_service.get_period(old.id)
        self.assertEqual(closed.certificate_valid_to, date(2020, 10, 20))
        self.assertEqual(closed.valid_to, date(2020, 9, 14))


if __name__ == "__main__":
    unittest.main()
