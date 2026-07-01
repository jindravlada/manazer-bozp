import importlib
import tempfile
import unittest
from datetime import date
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

    from moduly.audity.constants import (
        AUDIT_STATUS_DOKONCENO,
        AUDIT_STATUS_PLANOVANO,
        AUDIT_STATUS_PROBIHA,
        COMMISSION_RECORD_LEADER,
        DEFAULT_AUDIT_TYPE,
    )
    from moduly.audity.modely.audit_commission_member import AuditCommissionMember
    from moduly.audity.repository.audit_commission_repository import AuditCommissionRepository
    from moduly.audity.sluzby.audit_service import audit_service


class AudityAuditTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def test_create_and_reload_audit(self) -> None:
        audit = audit_service.create_audit(title="Test auditu")
        loaded = audit_service.get_by_id(audit.id)

        assert loaded is not None
        self.assertEqual(loaded.title, "Test auditu")
        self.assertTrue(loaded.number)

    def test_default_status_is_planovano(self) -> None:
        audit = audit_service.create_audit()

        self.assertEqual(audit.status, AUDIT_STATUS_PLANOVANO)

    def test_number_generation(self) -> None:
        audit = audit_service.create_audit(year=2026)

        self.assertEqual(audit.number, f"{audit.id}/2026")

    def test_status_lifecycle_derivation(self) -> None:
        planned = audit_service.create_audit()
        self.assertEqual(planned.status, AUDIT_STATUS_PLANOVANO)

        in_progress = audit_service.create_audit(started_at=date(2026, 3, 10))
        self.assertEqual(in_progress.status, AUDIT_STATUS_PROBIHA)

        finished = audit_service.create_audit(
            started_at=date(2026, 3, 10),
            finished_at=date(2026, 3, 12),
        )
        self.assertEqual(finished.status, AUDIT_STATUS_DOKONCENO)

    def test_default_audit_type(self) -> None:
        audit = audit_service.create_audit()

        self.assertEqual(audit.audit_type, DEFAULT_AUDIT_TYPE)

    def test_create_and_reload_commission_member(self) -> None:
        audit = audit_service.create_audit()
        repository = AuditCommissionRepository()
        member = repository.add(
            AuditCommissionMember(
                audit_id=audit.id,
                record_type=COMMISSION_RECORD_LEADER,
                display_name="Jan Novák",
                thp_worker_id=1,
            )
        )

        loaded = repository.get_for_audit(audit.id)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].id, member.id)
        self.assertEqual(loaded[0].display_name, "Jan Novák")


if __name__ == "__main__":
    unittest.main()
