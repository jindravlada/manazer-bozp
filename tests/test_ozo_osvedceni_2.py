"""OZO-OSVEDCENI-2: evidence ostatních osvědčení a upozornění."""

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

    from core.dashboard.attention_item import (
        ITEM_TYPE_OZO_PERSON_CERTIFICATE,
        ITEM_TYPE_QUALIFICATION_CERTIFICATE,
    )
    from core.dashboard.attention_service import get_attention_items
    from core.dashboard.widget_today import (
        TodayWidget,
        overdue_certificate_items,
    )
    from core.services.attachment_service import attachment_service
    from core.windows.main_window import MainWindow
    from moduly.smlouvy_ozo.constants import (
        ACTION_OTHER_CERTIFICATES,
        ENTITY_QUALIFICATION_CERTIFICATE_PERIOD,
        UNIT_MONTHS,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service
    from moduly.smlouvy_ozo.sluzby.qualification_certificate_service import (
        QualificationCertificateValidationError,
        qualification_certificate_service,
    )
    from moduly.smlouvy_ozo.ui.smlouvy_ozo_page import SmlouvyOzoPage


class OzoOsvedceni2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from core.models.attachment import Attachment
        from moduly.smlouvy_ozo.modely.ozo_person import OzoPerson
        from moduly.smlouvy_ozo.modely.ozo_person_period import OzoPersonPeriod
        from moduly.smlouvy_ozo.modely.qualification_certificate import (
            QualificationCertificate,
        )
        from moduly.smlouvy_ozo.modely.qualification_certificate_period import (
            QualificationCertificatePeriod,
        )

        with get_session() as session:
            session.execute(delete(Attachment))
            session.execute(delete(QualificationCertificatePeriod))
            session.execute(delete(QualificationCertificate))
            session.execute(delete(OzoPersonPeriod))
            session.execute(delete(OzoPerson))
            session.commit()

    def _cert_items(self, today: date, item_type: str):
        return [
            item
            for item in get_attention_items(today=today)
            if item.item_type == item_type
        ]

    def test_page_has_other_certificates_button(self) -> None:
        page = SmlouvyOzoPage()
        self.assertEqual(page.other_certificates_btn.text(), ACTION_OTHER_CERTIFICATES)
        page.close()

    def test_create_other_certificate(self) -> None:
        cert = qualification_certificate_service.save(
            name="OZO v požární ochraně",
            certificate_number="PO-1",
            exam_date=date(2024, 1, 10),
            indefinite=False,
            certificate_valid_to=date(2030, 1, 10),
            notify_before_value=1,
            notify_before_unit=UNIT_MONTHS,
        )
        period = qualification_certificate_service.get_open_period(cert)
        self.assertIsNotNone(period)
        self.assertEqual(period.certificate_number, "PO-1")
        self.assertEqual(period.notify_before_value, 1)

    def test_new_exam_history_and_split_attachments(self) -> None:
        cert = qualification_certificate_service.save(
            name="Báňské oprávnění",
            certificate_number="B-1",
            exam_date=date(2020, 5, 1),
            certificate_valid_to=date(2025, 5, 1),
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )
        first = qualification_certificate_service.get_open_period(cert)
        tmp = Path(tempfile.mkdtemp()) / "old.pdf"
        tmp.write_bytes(b"%PDF-old")
        attachment_service.add_file(
            ENTITY_QUALIFICATION_CERTIFICATE_PERIOD, first.id, str(tmp)
        )

        qualification_certificate_service.renew(
            cert.id,
            name="Báňské oprávnění",
            certificate_number="B-2",
            exam_date=date(2026, 4, 15),
            certificate_valid_to=date(2031, 4, 15),
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )
        closed = qualification_certificate_service.get_period(first.id)
        open_period = qualification_certificate_service.get_open_period(cert)
        self.assertEqual(closed.valid_to_period, date(2026, 4, 14))
        self.assertEqual(closed.certificate_number, "B-1")
        self.assertEqual(open_period.certificate_number, "B-2")
        self.assertEqual(
            len(
                attachment_service.get_for_entity(
                    ENTITY_QUALIFICATION_CERTIFICATE_PERIOD, first.id
                )
            ),
            1,
        )
        self.assertEqual(
            attachment_service.get_for_entity(
                ENTITY_QUALIFICATION_CERTIFICATE_PERIOD, open_period.id
            ),
            [],
        )

    def test_indefinite_never_in_attention(self) -> None:
        cert = qualification_certificate_service.save(
            name="Neurčité",
            exam_date=date(2020, 1, 1),
            indefinite=True,
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )
        items = self._cert_items(date(2040, 1, 1), ITEM_TYPE_QUALIFICATION_CERTIFICATE)
        self.assertFalse(any(item.source_id == cert.id for item in items))

    def test_notify_one_six_eighteen_months(self) -> None:
        for months, notify_day, before_day in (
            (1, date(2030, 5, 30), date(2030, 5, 29)),
            (6, date(2029, 12, 30), date(2029, 12, 29)),
            (18, date(2028, 12, 30), date(2028, 12, 29)),
        ):
            with self.subTest(months=months):
                cert = qualification_certificate_service.save(
                    name=f"Předstih {months} m",
                    exam_date=date(2025, 1, 1),
                    certificate_valid_to=date(2030, 6, 30),
                    notify_before_value=months,
                    notify_before_unit=UNIT_MONTHS,
                )
                self.assertFalse(
                    any(
                        item.source_id == cert.id
                        for item in self._cert_items(
                            before_day, ITEM_TYPE_QUALIFICATION_CERTIFICATE
                        )
                    )
                )
                self.assertTrue(
                    any(
                        item.source_id == cert.id
                        for item in self._cert_items(
                            notify_day, ITEM_TYPE_QUALIFICATION_CERTIFICATE
                        )
                    )
                )

    def test_no_notify_value_no_upcoming_until_expired(self) -> None:
        cert = qualification_certificate_service.save(
            name="Bez předstihu",
            exam_date=date(2025, 1, 1),
            certificate_valid_to=date(2030, 6, 30),
            notify_before_value=0,
        )
        self.assertFalse(
            any(
                item.source_id == cert.id
                for item in self._cert_items(
                    date(2030, 6, 15), ITEM_TYPE_QUALIFICATION_CERTIFICATE
                )
            )
        )
        expired_day = date(2030, 7, 1)
        items = self._cert_items(expired_day, ITEM_TYPE_QUALIFICATION_CERTIFICATE)
        match = [item for item in items if item.source_id == cert.id]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0].status, "Po platnosti")
        overdue = overdue_certificate_items(expired_day)
        self.assertTrue(any(item.source_id == cert.id for item in overdue))

    def test_ozo_person_custom_notify(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2024, 1, 1),
            certificate_number="OZO-9",
            certificate_valid_to=date(2030, 6, 30),
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )
        self.assertFalse(
            any(
                self._cert_items(date(2029, 12, 29), ITEM_TYPE_OZO_PERSON_CERTIFICATE)
            )
        )
        items = self._cert_items(date(2029, 12, 30), ITEM_TYPE_OZO_PERSON_CERTIFICATE)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Jan Novák")
        self.assertIn("Odborně způsobilá osoba", items[0].subtitle)

    def test_ozo_person_expired_in_co_hori(self) -> None:
        ozo_person_service.save(
            first_name="Eva",
            last_name="Testová",
            exam_date=date(2020, 1, 1),
            certificate_number="OZO-E",
            certificate_valid_to=date(2030, 1, 15),
            notify_before_value=0,
        )
        today = date(2030, 1, 16)
        items = self._cert_items(today, ITEM_TYPE_OZO_PERSON_CERTIFICATE)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].status, "Po platnosti")
        widget = TodayWidget()
        widget.refresh(today=today)
        self.assertIn("Eva Testová", widget.content.text())
        self.assertIn("🔴", widget.content.text())
        widget.close()

    def test_open_qualification_from_attention(self) -> None:
        cert = qualification_certificate_service.save(
            name="Drážní",
            exam_date=date(2025, 1, 1),
            certificate_valid_to=date(2030, 6, 30),
            notify_before_value=1,
            notify_before_unit=UNIT_MONTHS,
        )
        opened: list[int] = []
        window = MainWindow()
        page = window._page_widgets.get("smlouvy_ozo")
        if page is None:
            window._show("smlouvy_ozo")
            page = window._page_widgets.get("smlouvy_ozo")
        with patch.object(page, "open_qualification_certificate", side_effect=opened.append):
            item = type(
                "Item",
                (),
                {
                    "item_type": ITEM_TYPE_QUALIFICATION_CERTIFICATE,
                    "source_id": cert.id,
                    "open_metadata": {},
                },
            )()
            window._open_attention_item(item)
        self.assertEqual(opened, [cert.id])
        window.close()

    def test_open_ozo_person_from_attention(self) -> None:
        ozo_person_service.save(
            first_name="Petr",
            last_name="OZO",
            exam_date=date(2025, 1, 1),
            certificate_number="X",
            certificate_valid_to=date(2030, 1, 1),
            notify_before_value=1,
            notify_before_unit=UNIT_MONTHS,
        )
        opened = []
        window = MainWindow()
        page = window._page_widgets.get("smlouvy_ozo")
        if page is None:
            window._show("smlouvy_ozo")
            page = window._page_widgets.get("smlouvy_ozo")
        with patch.object(page, "edit_ozo_person", side_effect=lambda: opened.append(True)):
            item = type(
                "Item",
                (),
                {
                    "item_type": ITEM_TYPE_OZO_PERSON_CERTIFICATE,
                    "source_id": 1,
                    "open_metadata": {},
                },
            )()
            window._open_attention_item(item)
        self.assertTrue(opened)
        window.close()

    def test_definite_requires_valid_to(self) -> None:
        with self.assertRaises(QualificationCertificateValidationError):
            qualification_certificate_service.save(
                name="Bez konce",
                indefinite=False,
                certificate_valid_to=None,
            )


if __name__ == "__main__":
    unittest.main()
