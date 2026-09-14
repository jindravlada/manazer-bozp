import importlib
import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_LIVE_DB = Path(
    os.environ.get(
        "LEGAL_OPENDATA_LIVE_DB",
        "/home/test/.local/share/manazer-bozp/databaze/manager_bozp.db",
    )
)
_RUN_LIVE = os.environ.get("RUN_LEGAL_OPENDATA_LIVE_COPY") == "1"
_TMP = Path(tempfile.mkdtemp(prefix="legal-opendata-live-copy-"))

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

    from core.database.session import dispose_database_engine, reconfigure_database_engine
    from core.services.storage_service import storage_service
    from moduly.pravni_pozadavky.sluzby.legal_change_impacted_process_service import (
        legal_change_impacted_process_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_section_service import (
        legal_change_section_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_version_adoption_service import (
        legal_version_adoption_service,
    )


@unittest.skipUnless(_RUN_LIVE and _LIVE_DB.is_file(), "Živá kopie ostrých dat není zapnutá.")
class LegalCheckOpenDataLiveCopyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        dest = storage_service.database_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dispose_database_engine()
        shutil.copy2(_LIVE_DB, dest)
        reconfigure_database_engine(force=True)
        initialize_database()

    def test_check_on_copy_of_live_data(self) -> None:
        documents_before = {
            item.id: legal_document_service.get_by_id(item.id)
            for item in legal_document_service.list_all(include_inactive=False)
        }
        current_before = {
            document_id: legal_document_version_service.get_current_version(document_id)
            for document_id in documents_before
        }
        checksums_before = {
            document_id: None if version is None else version.checksum
            for document_id, version in current_before.items()
        }

        result = legal_check_run_service.run_automatic_check(
            period_from=date.today(),
            period_to=date.today(),
        )

        changes = legal_change_service.list_by_check_run(result.run.id, include_inactive=False)
        labels = []
        for change in changes:
            document = legal_document_service.get_by_id(change.legal_document_id)
            title = ""
            if document is not None:
                title = (
                    (document.short_title or "").strip()
                    or (document.title or "").strip()
                    or f"{document.number}/{document.year}"
                )
            labels.append(title)

        print("LIVE_COPY_CHANGES_COUNT", result.changes_count)
        print("LIVE_COPY_FAILED_COUNT", result.failed_count)
        print("LIVE_COPY_CHECKED", result.documents_checked_count)
        print("LIVE_COPY_DOCUMENTS", ",".join(labels) if labels else "-")
        print("LIVE_COPY_RUN_STATUS", result.run.status)
        from moduly.pravni_pozadavky.constants import (
            CHANGE_SECTION_ADDED,
            CHANGE_SECTION_MODIFIED,
            CHANGE_SECTION_REMOVED,
        )
        for change in changes:
            document = legal_document_service.get_by_id(change.legal_document_id)
            diff = legal_change_section_service.list_sections_for_change(change.id)
            added = sum(1 for item in diff if item.change_type == CHANGE_SECTION_ADDED)
            removed = sum(1 for item in diff if item.change_type == CHANGE_SECTION_REMOVED)
            modified = sum(1 for item in diff if item.change_type == CHANGE_SECTION_MODIFIED)
            number = ""
            if document is not None:
                number = f"{document.number}/{document.year}"
            print(f"LIVE_COPY_DIFF {number} +{added} -{removed} ~{modified}")

        self.assertGreater(result.documents_checked_count, 0)
        self.assertEqual(len(changes), result.changes_count)

        for document_id, version_before in current_before.items():
            if version_before is None:
                continue
            current = legal_document_version_service.get_current_version(document_id)
            assert current is not None
            self.assertEqual(current.id, version_before.id)

        if not changes:
            return

        sample = changes[0]
        self.assertIsNotNone(sample.new_legal_document_version_id)
        pending = legal_document_version_service.get_by_id(sample.new_legal_document_version_id)
        assert pending is not None
        self.assertTrue(pending.pending_adoption)
        from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service

        self.assertTrue(legal_section_service.list_by_version(pending.id))
        diff = legal_change_section_service.list_sections_for_change(sample.id)
        self.assertTrue(diff)
        impacts = legal_change_impacted_process_service.list_processes_for_change(sample.id)
        print("LIVE_COPY_SAMPLE_DIFF", len(diff))
        print("LIVE_COPY_SAMPLE_IMPACTS", len(impacts))
        print("LIVE_COPY_SAMPLE_ADOPT_OK", legal_version_adoption_service.can_adopt(sample))

        adopted = legal_version_adoption_service.adopt_detected_version(sample.id)
        current_after = legal_document_version_service.get_current_version(sample.legal_document_id)
        assert current_after is not None
        self.assertEqual(current_after.id, adopted.adopted_version.id)
        self.assertFalse(current_after.pending_adoption)
        self.assertNotEqual(
            current_after.id,
            current_before[sample.legal_document_id].id if current_before[sample.legal_document_id] else None,
        )
        still_same_checksums = [
            document_id
            for document_id, checksum in checksums_before.items()
            if document_id != sample.legal_document_id
            and legal_document_version_service.get_current_version(document_id) is not None
            and legal_document_version_service.get_current_version(document_id).id
            == (current_before[document_id].id if current_before[document_id] else None)
        ]
        self.assertTrue(still_same_checksums)
        print("LIVE_COPY_ADOPT_CURRENT_ID", current_after.id)


if __name__ == "__main__":
    unittest.main()
