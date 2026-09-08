import importlib
import tempfile
import unittest
from contextlib import contextmanager
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

    from core.services.app_runtime_service import mark_application_started

    mark_application_started()

    from moduly.pravni_pozadavky.constants import (
        CHECK_RUN_CANCELLED,
        CHECK_RUN_COMPLETED,
        CHECK_RUN_ERROR,
        CHECK_RUN_IN_PROGRESS,
        DOCUMENT_TYPE_NARIZENI_VLADY,
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
        legal_document_esbirka_client,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_novelization_service import (
        legal_check_novelization_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.sluzby.legal_version_adoption_service import (
        legal_version_adoption_service,
    )


class LegalCheckInterruptedRunTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
        from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalChangeSection))
            session.execute(delete(LegalChange))
            session.execute(delete(LegalCheckRun))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

        self.fixture_html = (
            Path(__file__).resolve().parent / "data" / "sample_esbirka_390_2021.html"
        ).read_text(encoding="utf-8")
        self.remote_version = legal_document_esbirka_client.extract_version_info(
            self.fixture_html,
            year=2021,
            number="390",
        )

    def _old_checksum(self) -> str:
        return legal_document_esbirka_client.build_version_checksum(
            slice_id="111111",
            text_checksum="old-checksum",
        )

    def _create_document(self, *, number: str, year: int, title: str, document_type: str):
        document = legal_document_service.create(
            document_type=document_type,
            title=title,
            number=number,
            year=year,
            short_title=title,
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum=self._old_checksum(),
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            title="§ 1",
            text="Původní znění",
            sort_order=1,
        )
        return document, version

    def _create_restored_pair(self):
        zp, zp_version = self._create_document(
            number="262/2006 Sb.",
            year=2006,
            title="Zákoník práce",
            document_type=DOCUMENT_TYPE_ZAKON,
        )
        nv, nv_version = self._create_document(
            number="361/2007 Sb.",
            year=2007,
            title="NV 361/2007",
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
        )
        return zp, zp_version, nv, nv_version

    def _seed_completed_history(self) -> None:
        legal_check_run_service.create(
            title="Historická kontrola",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
            status=CHECK_RUN_COMPLETED,
            documents_checked_count=2,
            changes_found_count=0,
        )

    @contextmanager
    def _patched_esbirka(self):
        with (
            patch.object(
                legal_document_esbirka_client,
                "fetch_version_info",
                return_value=self.remote_version,
            ),
            patch.object(
                legal_document_esbirka_client,
                "fetch_full_text_html",
                return_value=self.fixture_html,
            ),
            patch.object(
                legal_document_esbirka_client,
                "extract_version_info",
                return_value=self.remote_version,
            ),
        ):
            yield

    def _cancel_after_first_processed(self, target):
        processed = {"n": 0}
        original = target

        def wrapped(*args, **kwargs):
            result = original(*args, **kwargs)
            processed["n"] += 1
            return result

        def is_cancelled() -> bool:
            return processed["n"] >= 1

        return wrapped, is_cancelled, processed

    def test_completed_check_is_not_reported_again(self) -> None:
        zp, zp_version, _nv, _nv_version = self._create_restored_pair()
        self._seed_completed_history()

        with self._patched_esbirka():
            first = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )
            second = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 3, 1),
                period_to=date(2024, 3, 31),
            )

        self.assertEqual(first.changes_count, 2)
        self.assertEqual(second.changes_count, 0)
        self.assertEqual(len(legal_change_service.list_by_document(zp.id)), 1)
        self.assertEqual(
            len(legal_document_version_service.list_by_document(zp.id, include_inactive=True)),
            2,
        )
        used = legal_document_version_service.get_by_id(zp_version.id)
        assert used is not None
        self.assertEqual(used.checksum, self._old_checksum())

    def test_cancelled_check_is_reported_by_next_completed_run(self) -> None:
        zp, zp_version, nv, nv_version = self._create_restored_pair()
        self._seed_completed_history()
        wrapped, is_cancelled, processed = self._cancel_after_first_processed(
            legal_check_novelization_service.check_document,
        )

        with self._patched_esbirka(), patch.object(
            legal_check_novelization_service,
            "check_document",
            side_effect=wrapped,
        ):
            cancelled = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
                is_cancelled=is_cancelled,
            )

        self.assertEqual(cancelled.run.status, CHECK_RUN_CANCELLED)
        self.assertEqual(processed["n"], 1)
        self.assertEqual(len(legal_change_service.list_all()), 1)
        used_zp = legal_document_version_service.get_by_id(zp_version.id)
        used_nv = legal_document_version_service.get_by_id(nv_version.id)
        assert used_zp is not None and used_nv is not None
        self.assertEqual(used_zp.checksum, self._old_checksum())
        self.assertEqual(used_nv.checksum, self._old_checksum())

        legal_check_run_service.deactivate(cancelled.run.id)

        with self._patched_esbirka():
            retry = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 3, 1),
                period_to=date(2024, 3, 31),
            )

        self.assertEqual(retry.changes_count, 2)
        self.assertEqual(retry.run.status, CHECK_RUN_COMPLETED)
        zp_changes = legal_change_service.list_by_document(zp.id)
        nv_changes = legal_change_service.list_by_document(nv.id)
        self.assertEqual(len(zp_changes), 1)
        self.assertEqual(len(nv_changes), 1)
        self.assertEqual(
            len(legal_document_version_service.list_by_document(zp.id, include_inactive=True)),
            2,
        )
        self.assertEqual(
            len(legal_document_version_service.list_by_document(nv.id, include_inactive=True)),
            2,
        )
        self.assertTrue(
            legal_document_version_service.get_by_id(
                zp_changes[0].new_legal_document_version_id,
            ).pending_adoption,
        )

    def test_exception_after_processed_document_does_not_lose_change(self) -> None:
        zp, _zp_version, nv, _nv_version = self._create_restored_pair()
        self._seed_completed_history()
        original = legal_check_novelization_service.check_document
        calls = {"n": 0}

        def wrapped(*args, **kwargs):
            calls["n"] += 1
            result = original(*args, **kwargs)
            if calls["n"] >= 1:
                raise RuntimeError("simulovaná chyba po zpracování předpisu")
            return result

        with self._patched_esbirka(), patch.object(
            legal_check_novelization_service,
            "check_document",
            side_effect=wrapped,
        ):
            with self.assertRaisesRegex(RuntimeError, "simulovaná chyba"):
                legal_check_run_service.run_automatic_check(
                    period_from=date(2024, 2, 1),
                    period_to=date(2024, 2, 28),
                )

        failed_runs = [
            item
            for item in legal_check_run_service.list_all(include_inactive=True)
            if item.status == CHECK_RUN_ERROR
        ]
        self.assertEqual(len(failed_runs), 1)
        self.assertEqual(len(legal_change_service.list_all()), 1)

        with self._patched_esbirka():
            retry = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 3, 1),
                period_to=date(2024, 3, 31),
            )

        self.assertEqual(retry.changes_count, 2)
        self.assertEqual(len(legal_change_service.list_by_document(zp.id)), 1)
        self.assertEqual(len(legal_change_service.list_by_document(nv.id)), 1)

    def test_unfinished_in_progress_run_does_not_swallow_change(self) -> None:
        zp, _zp_version, nv, _nv_version = self._create_restored_pair()
        self._seed_completed_history()
        hanging = legal_check_run_service._begin_automatic_check(
            date(2024, 2, 1),
            date(2024, 2, 28),
        )
        self.assertEqual(hanging.status, CHECK_RUN_IN_PROGRESS)
        with self._patched_esbirka():
            created = legal_check_novelization_service.check_document(
                zp,
                check_run_id=hanging.id,
            )
        assert created is not None
        self.assertEqual(legal_check_run_service.get_by_id(hanging.id).status, CHECK_RUN_IN_PROGRESS)

        with self._patched_esbirka():
            retry = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 3, 1),
                period_to=date(2024, 3, 31),
            )

        self.assertEqual(retry.changes_count, 2)
        self.assertEqual(len(legal_change_service.list_by_document(zp.id)), 1)
        self.assertEqual(len(legal_change_service.list_by_document(nv.id)), 1)
        self.assertEqual(
            legal_change_service.list_by_document(zp.id)[0].legal_check_run_id,
            retry.run.id,
        )

    def test_adopted_wording_is_not_reported_again(self) -> None:
        zp, _zp_version, _nv, _nv_version = self._create_restored_pair()
        self._seed_completed_history()

        with self._patched_esbirka():
            first = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )
        self.assertEqual(first.changes_count, 2)
        for change in legal_change_service.list_all():
            legal_version_adoption_service.adopt_detected_version(change.id)

        with self._patched_esbirka():
            second = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 3, 1),
                period_to=date(2024, 3, 31),
            )

        self.assertEqual(second.changes_count, 0)
        current = legal_document_version_service.get_current_version(zp.id)
        assert current is not None
        self.assertFalse(current.pending_adoption)

    def test_evaluated_without_adoption_is_not_a_substitute_for_wording_status(self) -> None:
        zp, zp_version, _nv, _nv_version = self._create_restored_pair()
        self._seed_completed_history()

        with self._patched_esbirka():
            first = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )
        self.assertEqual(first.changes_count, 2)
        zp_change = legal_change_service.list_by_document(zp.id)[0]
        legal_change_service.mark_evaluated(zp_change.id, evaluated_by="Jan Novák")

        with self._patched_esbirka():
            second = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 3, 1),
                period_to=date(2024, 3, 31),
            )

        self.assertEqual(second.changes_count, 0)
        updated = legal_change_service.get_by_id(zp_change.id)
        assert updated is not None
        self.assertTrue(updated.evaluated)
        current = legal_document_version_service.get_current_version(zp.id)
        assert current is not None
        self.assertEqual(current.id, zp_version.id)
        detected = legal_document_version_service.get_by_id(updated.new_legal_document_version_id)
        assert detected is not None
        self.assertTrue(detected.pending_adoption)

    def test_cancelled_first_check_does_not_confirm_reference_checksum(self) -> None:
        zp, zp_version, nv, nv_version = self._create_restored_pair()
        wrapped, is_cancelled, processed = self._cancel_after_first_processed(
            legal_check_novelization_service.initialize_reference_state,
        )

        with self._patched_esbirka(), patch.object(
            legal_check_novelization_service,
            "initialize_reference_state",
            side_effect=wrapped,
        ):
            cancelled = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
                is_cancelled=is_cancelled,
            )

        self.assertEqual(cancelled.run.status, CHECK_RUN_CANCELLED)
        self.assertEqual(processed["n"], 1)
        self.assertEqual(legal_document_version_service.get_by_id(zp_version.id).checksum, self._old_checksum())
        self.assertEqual(legal_document_version_service.get_by_id(nv_version.id).checksum, self._old_checksum())

        with self._patched_esbirka():
            completed = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 3, 1),
                period_to=date(2024, 3, 31),
            )

        self.assertTrue(completed.is_first_check)
        self.assertEqual(completed.changes_count, 0)
        remote_checksum = legal_document_esbirka_client.build_version_checksum(
            slice_id=self.remote_version.slice_id,
            text_checksum=self.remote_version.text_checksum,
        )
        self.assertEqual(legal_document_version_service.get_by_id(zp_version.id).checksum, remote_checksum)
        self.assertEqual(legal_document_version_service.get_by_id(nv_version.id).checksum, remote_checksum)


if __name__ == "__main__":
    unittest.main()
