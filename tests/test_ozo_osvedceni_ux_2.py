"""OZO-OSVEDCENI-UX-2: explicitní obnovení osvědčení."""

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
    from core.services.attachment_service import attachment_service
    from moduly.smlouvy_ozo.constants import (
        ACTION_EDIT,
        ACTION_RENEW_CERTIFICATE,
        DIALOG_TITLE_CERTIFICATE_NEW,
        ENTITY_OZO_PERSON_PERIOD,
        ENTITY_QUALIFICATION_CERTIFICATE_PERIOD,
        UNIT_MONTHS,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_person_service import (
        OzoPersonValidationError,
        ozo_person_service,
    )
    from moduly.smlouvy_ozo.sluzby.qualification_certificate_service import (
        QualificationCertificateValidationError,
        qualification_certificate_service,
    )
    from moduly.smlouvy_ozo.ui.ozo_person_dialog import OzoPersonDialog
    from moduly.smlouvy_ozo.ui.qualification_certificates_dialog import (
        QualificationCertificatesDialog,
    )


class OzoOsvedceniUx2TestCase(unittest.TestCase):
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

    def _open_periods(self, certificate_id: int) -> list:
        from core.database.session import get_session
        from moduly.smlouvy_ozo.modely.qualification_certificate_period import (
            QualificationCertificatePeriod,
        )

        with get_session() as session:
            return list(
                session.query(QualificationCertificatePeriod)
                .filter(
                    QualificationCertificatePeriod.certificate_id == certificate_id,
                    QualificationCertificatePeriod.valid_to_period.is_(None),
                )
                .all()
            )

    def test_list_toolbar_actions(self) -> None:
        dialog = QualificationCertificatesDialog()
        self.assertEqual(dialog.new_btn.text(), DIALOG_TITLE_CERTIFICATE_NEW)
        self.assertEqual(dialog.edit_btn.text(), ACTION_EDIT)
        self.assertEqual(dialog.renew_btn.text(), ACTION_RENEW_CERTIFICATE)
        self.assertFalse(dialog.edit_btn.isEnabled())
        self.assertFalse(dialog.renew_btn.isEnabled())
        dialog.close()

    def test_new_certificate_is_independent(self) -> None:
        first = qualification_certificate_service.save(
            name="Způsobilost A",
            certificate_number="A-1",
            exam_date=date(2024, 1, 1),
            certificate_valid_to=date(2029, 1, 1),
        )
        second = qualification_certificate_service.save(
            name="Způsobilost A",
            certificate_number="A-2",
            exam_date=date(2026, 1, 1),
            certificate_valid_to=date(2031, 1, 1),
        )
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(len(qualification_certificate_service.get_all()), 2)

    def test_edit_does_not_create_history(self) -> None:
        cert = qualification_certificate_service.save(
            name="Edit test",
            certificate_number="E-1",
            exam_date=date(2024, 1, 1),
            certificate_valid_to=date(2029, 1, 1),
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )
        first = qualification_certificate_service.get_open_period(cert)
        qualification_certificate_service.save(
            certificate_id=cert.id,
            name="Edit test",
            certificate_number="E-1-oprava",
            exam_date=date(2026, 6, 1),
            certificate_valid_to=date(2031, 6, 1),
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )
        open_period = qualification_certificate_service.get_open_period(cert)
        closed = qualification_certificate_service.list_closed_periods(cert)
        self.assertEqual(open_period.id, first.id)
        self.assertEqual(open_period.certificate_number, "E-1-oprava")
        self.assertEqual(open_period.exam_date, date(2026, 6, 1))
        self.assertEqual(closed, [])
        self.assertEqual(len(self._open_periods(cert.id)), 1)

    def test_renew_creates_version_and_closes_previous(self) -> None:
        cert = qualification_certificate_service.save(
            name="Obnova",
            certificate_number="R-1",
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
            name="Obnova",
            certificate_number="R-2",
            exam_date=date(2026, 4, 15),
            certificate_valid_to=date(2031, 4, 15),
            notify_before_value=3,
            notify_before_unit=UNIT_MONTHS,
            note="nová poznámka",
        )
        closed = qualification_certificate_service.get_period(first.id)
        open_period = qualification_certificate_service.get_open_period(cert)
        self.assertEqual(closed.valid_to_period, date(2026, 4, 14))
        self.assertEqual(closed.certificate_number, "R-1")
        self.assertEqual(open_period.certificate_number, "R-2")
        self.assertEqual(open_period.valid_from, date(2026, 4, 15))
        self.assertEqual(open_period.note, "nová poznámka")
        self.assertEqual(len(self._open_periods(cert.id)), 1)
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
        history = qualification_certificate_service.list_closed_periods(cert)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].id, first.id)

    def test_renew_rejects_exam_not_after_valid_from(self) -> None:
        cert = qualification_certificate_service.save(
            name="Validace",
            exam_date=date(2024, 1, 10),
            certificate_valid_to=date(2029, 1, 10),
        )
        with self.assertRaises(QualificationCertificateValidationError):
            qualification_certificate_service.renew(
                cert.id,
                name="Validace",
                exam_date=date(2024, 1, 10),
                certificate_valid_to=date(2029, 1, 10),
            )

    def test_attention_follows_new_open_period(self) -> None:
        cert = qualification_certificate_service.save(
            name="Attention",
            exam_date=date(2020, 1, 1),
            certificate_valid_to=date(2030, 6, 30),
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )
        before_renew = [
            item
            for item in get_attention_items(today=date(2030, 1, 1))
            if item.item_type == ITEM_TYPE_QUALIFICATION_CERTIFICATE
            and item.source_id == cert.id
        ]
        self.assertEqual(len(before_renew), 1)

        qualification_certificate_service.renew(
            cert.id,
            name="Attention",
            certificate_number="NEW",
            exam_date=date(2030, 7, 1),
            certificate_valid_to=date(2035, 7, 1),
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )
        after_same_day = [
            item
            for item in get_attention_items(today=date(2030, 1, 1))
            if item.item_type == ITEM_TYPE_QUALIFICATION_CERTIFICATE
            and item.source_id == cert.id
        ]
        self.assertEqual(after_same_day, [])
        later = [
            item
            for item in get_attention_items(today=date(2035, 1, 1))
            if item.item_type == ITEM_TYPE_QUALIFICATION_CERTIFICATE
            and item.source_id == cert.id
        ]
        self.assertEqual(len(later), 1)

    def test_ozo_edit_does_not_create_history(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="12345",
            certificate_valid_to=date(2026, 5, 10),
        )
        first_id = ozo_person_service.get_open_period().id
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2026, 4, 15),
            certificate_number="67890",
            certificate_valid_to=date(2031, 4, 15),
        )
        open_period = ozo_person_service.get_open_period()
        self.assertEqual(open_period.id, first_id)
        self.assertEqual(open_period.certificate_number, "67890")
        self.assertEqual(ozo_person_service.list_closed_periods(), [])

    def test_ozo_renew_creates_history_and_attention(self) -> None:
        ozo_person_service.save(
            first_name="Eva",
            last_name="Testová",
            exam_date=date(2020, 1, 1),
            certificate_number="OLD",
            certificate_valid_to=date(2030, 1, 15),
            notify_before_value=0,
        )
        first = ozo_person_service.get_open_period()
        tmp = Path(tempfile.mkdtemp()) / "ozo-old.pdf"
        tmp.write_bytes(b"%PDF-ozo")
        attachment_service.add_file(ENTITY_OZO_PERSON_PERIOD, first.id, str(tmp))

        expired = [
            item
            for item in get_attention_items(today=date(2030, 1, 16))
            if item.item_type == ITEM_TYPE_OZO_PERSON_CERTIFICATE
        ]
        self.assertEqual(len(expired), 1)

        ozo_person_service.renew(
            first_name="Eva",
            last_name="Testová",
            exam_date=date(2030, 2, 1),
            certificate_number="NEW",
            certificate_valid_to=date(2035, 2, 1),
            notify_before_value=6,
            notify_before_unit=UNIT_MONTHS,
        )
        closed = ozo_person_service.get_period(first.id)
        open_period = ozo_person_service.get_open_period()
        self.assertEqual(closed.valid_to, date(2030, 1, 31))
        self.assertEqual(open_period.certificate_number, "NEW")
        self.assertEqual(
            len(attachment_service.get_for_entity(ENTITY_OZO_PERSON_PERIOD, first.id)),
            1,
        )
        self.assertEqual(
            attachment_service.get_for_entity(
                ENTITY_OZO_PERSON_PERIOD, open_period.id
            ),
            [],
        )
        self.assertEqual(len(ozo_person_service.list_closed_periods()), 1)
        after = [
            item
            for item in get_attention_items(today=date(2030, 1, 16))
            if item.item_type == ITEM_TYPE_OZO_PERSON_CERTIFICATE
        ]
        self.assertEqual(after, [])

    def test_ozo_renew_validation(self) -> None:
        ozo_person_service.save(
            first_name="Petr",
            last_name="OZO",
            exam_date=date(2024, 1, 1),
            certificate_number="X",
        )
        with self.assertRaises(OzoPersonValidationError):
            ozo_person_service.renew(
                first_name="Petr",
                last_name="OZO",
                exam_date=date(2024, 1, 1),
                certificate_number="Y",
            )

    def test_ozo_dialog_has_renew_action(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            exam_date=date(2021, 5, 10),
            certificate_number="12345",
        )
        dialog = OzoPersonDialog()
        self.assertEqual(dialog.renew_btn.text(), ACTION_RENEW_CERTIFICATE)
        self.assertTrue(dialog.renew_btn.isEnabled())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
