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

    from moduly.pravni_pozadavky.constants import (
        CHANGE_NEW,
        CHECK_RUN_COMPLETED,
        CHECK_RUN_IN_PROGRESS,
        CHECK_RUN_NEW,
        DOCUMENT_TYPE_ZAKON,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_run_export_context_service import (
        legal_check_run_export_context_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import (
        CheckRunCancelledError,
        legal_check_run_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service


class LegalCheckRunServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument

        with get_session() as session:
            session.execute(delete(LegalChange))
            session.execute(delete(LegalCheckRun))
            session.execute(delete(LegalDocument))
            session.commit()

    def _create_document(self):
        return legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
        )

    def _create_run(self, **kwargs):
        defaults = {
            "title": "Kontrola Q2 2024",
            "period_from": date(2024, 4, 1),
            "period_to": date(2024, 6, 30),
            "checked_by": "Jan Novák",
        }
        defaults.update(kwargs)
        return legal_check_run_service.create(**defaults)

    def _create_change(self, document, **kwargs):
        defaults = {
            "legal_document_id": document.id,
            "change_type": CHANGE_NEW,
            "title": "Změna k posouzení",
        }
        defaults.update(kwargs)
        return legal_change_service.create(**defaults)

    def test_create_check_run(self) -> None:
        run = self._create_run()

        self.assertIsNotNone(run.id)
        self.assertEqual(run.title, "Kontrola Q2 2024")
        self.assertEqual(run.status, CHECK_RUN_NEW)
        self.assertTrue(run.active)

    def test_update_check_run(self) -> None:
        run = self._create_run()
        updated = legal_check_run_service.update(
            run.id,
            title="Upravená kontrola",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 3, 31),
            checked_by="Marie Svobodová",
            status=CHECK_RUN_NEW,
            active=True,
        )

        assert updated is not None
        self.assertEqual(updated.title, "Upravená kontrola")
        self.assertEqual(updated.checked_by, "Marie Svobodová")

    def test_deactivate_and_restore_check_run(self) -> None:
        run = self._create_run()

        deactivated = legal_check_run_service.deactivate(run.id)
        assert deactivated is not None
        self.assertFalse(deactivated.active)

        active_only = legal_check_run_service.list_all()
        self.assertEqual(active_only, [])

        restored = legal_check_run_service.restore(run.id)
        assert restored is not None
        self.assertTrue(restored.active)

    def test_start_run(self) -> None:
        run = self._create_run()

        started = legal_check_run_service.start_run(run.id)
        assert started is not None
        self.assertEqual(started.status, CHECK_RUN_IN_PROGRESS)
        self.assertIsNotNone(started.checked_at)

    def test_complete_run(self) -> None:
        run = self._create_run()
        legal_check_run_service.start_run(run.id)

        completed = legal_check_run_service.complete_run(run.id)
        assert completed is not None
        self.assertEqual(completed.status, CHECK_RUN_COMPLETED)

    def test_assign_change_to_check_run(self) -> None:
        document = self._create_document()
        run = self._create_run()
        change = self._create_change(
            document,
            legal_check_run_id=run.id,
            title="Změna v kontrole",
        )

        self.assertEqual(change.legal_check_run_id, run.id)
        changes = legal_change_service.list_by_check_run(run.id)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].id, change.id)

    def test_export_includes_changes(self) -> None:
        document = self._create_document()
        run = self._create_run(title="Export kontroly")
        self._create_change(
            document,
            legal_check_run_id=run.id,
            title="První změna",
            evaluated=True,
        )
        self._create_change(
            document,
            legal_check_run_id=run.id,
            title="Druhá změna",
            evaluated=False,
        )

        context = legal_check_run_export_context_service.build_for_run(run.id)
        assert context is not None
        row = context.rows[0]
        self.assertEqual(row.title, "Export kontroly")
        self.assertEqual(row.changes_count, 2)
        self.assertEqual(len(row.changes), 2)
        self.assertEqual(
            {item.title for item in row.changes},
            {"První změna", "Druhá změna"},
        )

    def test_export_counts_evaluated_and_unevaluated_changes(self) -> None:
        document = self._create_document()
        run = self._create_run()
        self._create_change(document, legal_check_run_id=run.id, evaluated=True)
        self._create_change(document, legal_check_run_id=run.id, evaluated=True)
        self._create_change(document, legal_check_run_id=run.id, evaluated=False)

        context = legal_check_run_export_context_service.build_for_run(run.id)
        assert context is not None
        row = context.rows[0]
        self.assertEqual(row.changes_count, 3)
        self.assertEqual(row.evaluated_count, 2)
        self.assertEqual(row.unevaluated_count, 1)

    def test_get_last_completed_run(self) -> None:
        older = self._create_run(title="Starší kontrola")
        legal_check_run_service.complete_run(older.id)
        newer = self._create_run(
            title="Novější kontrola",
            period_from=date(2024, 7, 1),
            period_to=date(2024, 9, 30),
        )
        legal_check_run_service.complete_run(newer.id)

        last_completed = legal_check_run_service.get_last_completed_run()
        assert last_completed is not None
        self.assertEqual(last_completed.id, newer.id)

    def test_get_run_completion_date_uses_checked_at(self) -> None:
        run = self._create_run()
        completed = legal_check_run_service.complete_run(run.id)
        assert completed is not None
        assert completed.checked_at is not None

        completion_date = legal_check_run_service.get_run_completion_date(completed)
        self.assertEqual(completion_date, completed.checked_at.date())

    def test_run_automatic_check_creates_completed_run(self) -> None:
        self._create_document()
        legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákon o BOZP",
            number="309/2006 Sb.",
            year=2006,
        )

        result = legal_check_run_service.run_automatic_check(
            period_from=date(2024, 1, 1),
            period_to=date(2024, 6, 30),
        )

        self.assertEqual(result.run.status, CHECK_RUN_COMPLETED)
        self.assertEqual(result.run.period_from, date(2024, 1, 1))
        self.assertEqual(result.run.period_to, date(2024, 6, 30))
        self.assertIsNotNone(result.run.checked_at)
        self.assertEqual(result.documents_checked_count, 2)
        self.assertEqual(result.changes_count, 0)

    def test_run_automatic_check_defaults_period_to_today(self) -> None:
        result = legal_check_run_service.run_automatic_check(
            period_from=date.today(),
        )

        self.assertEqual(result.run.period_to, date.today())
        self.assertEqual(result.changes_count, 0)

    def test_run_automatic_check_reports_progress(self) -> None:
        document = self._create_document()
        status_messages: list[str] = []
        progress_calls: list[tuple[int, int, str]] = []

        result = legal_check_run_service.run_automatic_check(
            period_from=date(2024, 1, 1),
            on_status=status_messages.append,
            on_progress=lambda current, total, label: progress_calls.append(
                (current, total, label),
            ),
        )

        self.assertEqual(status_messages[0], "Připravuji kontrolu…")
        self.assertEqual(progress_calls, [(1, 1, document.short_title or document.title)])
        self.assertEqual(result.documents_checked_count, 1)

    def test_run_automatic_check_cancelled_does_not_create_run(self) -> None:
        self._create_document()

        with self.assertRaises(CheckRunCancelledError):
            legal_check_run_service.run_automatic_check(
                period_from=date(2024, 1, 1),
                is_cancelled=lambda: True,
            )

        self.assertEqual(legal_check_run_service.list_all(include_inactive=True), [])


if __name__ == "__main__":
    unittest.main()
