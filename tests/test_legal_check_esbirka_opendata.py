import importlib
import json
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

    from core.services.app_runtime_service import mark_application_started

    mark_application_started()

    from core.http_safe import SafeHttpsError
    from moduly.pravni_pozadavky.constants import (
        CHANGE_NOVELIZATION,
        CHECK_RUN_COMPLETED,
        CHECK_RUN_ERROR,
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
        ESBIRKA_ALLOWED_HOSTS,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
        ESBIRKA_OPENDATA_ALLOWED_HOSTS,
        ESBIRKA_OPENDATA_BASE_URL,
        ESbirkaOpenDataWording,
        legal_document_esbirka_opendata_client,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_tree import (
        legal_document_esbirka_opendata_tree_builder,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_number import (
        normalize_legal_act_number_and_year,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_novelization_service import (
        NOVELIZATION_CHANGED,
        NOVELIZATION_FAILED,
        NOVELIZATION_UNCHANGED,
        legal_check_novelization_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import (
        format_automatic_check_user_message,
        legal_check_run_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from tests.legal_opendata_check_fakes import (
        fake_in_force_tree,
        parsed_sections_from_version,
        patch_no_future_wordings,
    )

class _FakeRawResponse:
    def __init__(self, *, status: int = 200, headers: dict | None = None):
        self.status_code = status
        self.headers = headers or {}

    def iter_content(self, chunk_size=8192):
        return iter(())

    def close(self) -> None:
        return None


def _request_sequence(responses: list[_FakeRawResponse]):
    queue = list(responses)

    def _request(method, url, **kwargs):
        if not queue:
            raise AssertionError(f"Neočekávaný request na {url}")
        return queue.pop(0)

    return _request


_ELI_A = "eli/cz/sb/2006/262/2026-01-01"
_ELI_B = "eli/cz/sb/2006/262/2027-01-01"
_ACT_URL = f"{ESBIRKA_OPENDATA_BASE_URL}/2006/262"


def _wording(eli: str = _ELI_B) -> ESbirkaOpenDataWording:
    return ESbirkaOpenDataWording(
        last_wording_eli=eli,
        source_url=_ACT_URL,
        effective_from=date.fromisoformat(eli.rsplit("/", 1)[-1]),
        version_label=f"e-Sbírka {eli}",
    )


def _eli_checksum(eli: str = _ELI_B) -> str:
    return legal_document_esbirka_opendata_client.build_version_checksum(eli)


class LegalCheckESbirkaOpenDataTestCase(unittest.TestCase):
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
        no_futures = patch_no_future_wordings()
        no_futures.start()
        self.addCleanup(no_futures.stop)

    def _create_document(
        self,
        *,
        number: str = "262",
        year: int = 2006,
        checksum: str = "",
        short_title: str = "ZP",
    ):
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number=number,
            year=year,
            short_title=short_title,
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum=checksum,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            section_number="1",
            title="§ 1",
            text="Původní znění",
            sort_order=1,
        )
        return document, version

    def _patch_in_force(self, eli: str, *, change_text: str | None = None):
        def _fetch(*, year, number, on_date):
            version = legal_document_version_service.get_current_version(
                self._document_id_for(year, number),
            )
            sections = parsed_sections_from_version(version.id) if version is not None else []
            if change_text is not None and sections:
                sections[0].text = change_text
            return fake_in_force_tree(eli, sections)

        return patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            side_effect=_fetch,
        )

    def _document_id_for(self, year, number) -> int:
        from moduly.pravni_pozadavky.import_export.legal_document_number import (
            normalize_legal_act_number_and_year,
        )

        want_number, want_year = normalize_legal_act_number_and_year(number, year)
        for item in legal_document_service.list_all(include_inactive=False):
            got_number, got_year = normalize_legal_act_number_and_year(
                item.number or "",
                item.year if item.year is not None else want_year,
            )
            if got_number == want_number and got_year == want_year:
                return item.id
        raise AssertionError(f"Předpis {number}/{year} nebyl nalezen.")

    def _seed_completed_run(self) -> None:
        legal_check_run_service.create(
            title="Historická kontrola",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
            status=CHECK_RUN_COMPLETED,
            documents_checked_count=1,
            changes_found_count=0,
        )

    def test_a_build_url_for_262_2006(self) -> None:
        self.assertEqual(
            legal_document_esbirka_opendata_client.build_url(year=2006, number="262"),
            _ACT_URL,
        )

    def test_b_normalizes_compound_number(self) -> None:
        self.assertEqual(
            normalize_legal_act_number_and_year("262/2006 Sb.", 2006),
            ("262", 2006),
        )
        self.assertEqual(
            legal_document_esbirka_opendata_client.build_url(
                year=2006,
                number="262/2006 Sb.",
            ),
            _ACT_URL,
        )

    def test_c_rejects_inconsistent_year_before_http(self) -> None:
        with patch("core.http_safe.requests.request") as request_mock:
            with self.assertRaisesRegex(ValueError, "neshodují"):
                legal_document_esbirka_opendata_client.fetch_latest_wording(
                    year=2006,
                    number="262/2005",
                )
        request_mock.assert_not_called()

    def test_d_extracts_last_wording_eli_from_jsonld(self) -> None:
        payload = {
            "@id": "esel-esb/eli/cz/sb/2006/262",
            "má-poslední-znění": "esel-esb/eli/cz/sb/2006/262/2027-01-01",
        }
        wording = legal_document_esbirka_opendata_client.extract_latest_wording(
            payload,
            source_url=_ACT_URL,
        )
        self.assertEqual(wording.last_wording_eli, _ELI_B)
        self.assertEqual(wording.effective_from, date(2027, 1, 1))
        self.assertEqual(
            legal_document_esbirka_opendata_client.build_version_checksum(
                wording.last_wording_eli,
            ),
            f"esbirka-eli:{_ELI_B}",
        )

    def test_e_same_eli_is_unchanged(self) -> None:
        document, version = self._create_document(checksum=_eli_checksum(_ELI_B))
        run = legal_check_run_service._begin_automatic_check(date(2024, 2, 1), date(2024, 2, 28))
        with self._patch_in_force(_ELI_B):
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(result.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(result.change)
        self.assertEqual(legal_change_service.list_by_check_run(run.id), [])
        self.assertEqual(
            legal_document_version_service.get_by_id(version.id).checksum,
            _eli_checksum(_ELI_B),
        )

    def test_f_different_eli_creates_novelization(self) -> None:
        document, version = self._create_document(checksum=_eli_checksum(_ELI_A))
        run = legal_check_run_service._begin_automatic_check(date(2024, 2, 1), date(2024, 2, 28))
        with self._patch_in_force(_ELI_B, change_text="Nové znění Open Data"):
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(result.status, NOVELIZATION_CHANGED)
        assert result.change is not None
        self.assertEqual(result.change.change_type, CHANGE_NOVELIZATION)
        self.assertEqual(result.change.title, "Předpis byl novelizován.")
        self.assertEqual(result.change.legal_document_version_id, version.id)
        self.assertIsNotNone(result.change.new_legal_document_version_id)
        updated = legal_document_version_service.get_by_id(version.id)
        assert updated is not None
        self.assertEqual(updated.checksum, _eli_checksum(_ELI_A))

    def test_g_legacy_checksum_is_rebaselined_without_false_change(self) -> None:
        document, version = self._create_document(
            checksum="esbirka:356121:old-text-hash",
        )
        self._seed_completed_run()
        with self._patch_in_force(_ELI_B):
            result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )
        self.assertEqual(result.changes_count, 0)
        self.assertEqual(result.failed_count, 0)
        self.assertEqual(result.run.status, CHECK_RUN_COMPLETED)
        self.assertEqual(legal_change_service.list_by_document(document.id), [])
        updated = legal_document_version_service.get_by_id(version.id)
        assert updated is not None
        self.assertEqual(updated.checksum, _eli_checksum(_ELI_B))
        self.assertEqual(updated.source_eli, _ELI_B)

    def test_h_second_eli_check_with_same_value_is_unchanged(self) -> None:
        document, version = self._create_document(
            checksum="esbirka:111111:old-hash",
        )
        self._seed_completed_run()
        with self._patch_in_force(_ELI_B):
            first = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )
            second = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 3, 1),
                period_to=date(2024, 3, 31),
            )
        self.assertEqual(first.changes_count, 0)
        self.assertEqual(second.changes_count, 0)
        self.assertEqual(legal_change_service.list_by_document(document.id), [])
        self.assertEqual(
            legal_document_version_service.get_by_id(version.id).checksum,
            _eli_checksum(_ELI_B),
        )

    def test_i_eli_change_after_baseline_is_detected(self) -> None:
        document, version = self._create_document(checksum=_eli_checksum(_ELI_A))
        self._seed_completed_run()
        with self._patch_in_force(_ELI_A):
            first = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )
        with self._patch_in_force(_ELI_B, change_text="Nové znění Open Data"):
            second = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 3, 1),
                period_to=date(2024, 3, 31),
            )
        self.assertEqual(first.changes_count, 0)
        self.assertEqual(second.changes_count, 1)
        changes = legal_change_service.list_by_document(document.id)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].title, "Předpis byl novelizován.")
        self.assertIsNotNone(changes[0].new_legal_document_version_id)
        self.assertEqual(
            legal_document_version_service.get_by_id(version.id).checksum,
            _eli_checksum(_ELI_A),
        )

    def test_j_safe_https_error_is_failed_not_unchanged(self) -> None:
        document, _version = self._create_document(checksum=_eli_checksum(_ELI_A))
        run = legal_check_run_service._begin_automatic_check(date(2024, 2, 1), date(2024, 2, 28))
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            side_effect=SafeHttpsError("Neplatná adresa služby.", kind="invalid_url"),
        ):
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(result.status, NOVELIZATION_FAILED)
        self.assertIsNone(result.change)
        self.assertEqual(legal_change_service.list_by_check_run(run.id), [])

    def test_k_http_timeout_limit_and_invalid_json_are_failed(self) -> None:
        document, _version = self._create_document(checksum=_eli_checksum(_ELI_A))
        run = legal_check_run_service._begin_automatic_check(date(2024, 2, 1), date(2024, 2, 28))
        cases = [
            ValueError("Vypršel časový limit spojení."),
            ValueError("Odpověď je příliš velká."),
            ValueError("Neočekávaný formát odpovědi."),
        ]
        for error in cases:
            with self.subTest(error=str(error)):
                with patch.object(
                    legal_document_esbirka_opendata_tree_builder,
                    "fetch_in_force_tree",
                    side_effect=error,
                ):
                    result = legal_check_novelization_service.check_document(
                        document,
                        check_run_id=run.id,
                    )
                self.assertEqual(result.status, NOVELIZATION_FAILED)
                self.assertEqual(result.error, str(error))
        invalid = json.dumps({"@id": "esel-esb/eli/cz/sb/2006/262"}).encode("utf-8")
        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
            return_value=type(
                "R",
                (),
                {"status_code": 200, "body": invalid, "final_url": _ACT_URL},
            )(),
        ):
            with self.assertRaisesRegex(ValueError, "Neočekávaný formát"):
                legal_document_esbirka_opendata_client.fetch_latest_wording(
                    year=2006,
                    number="262",
                )

    def test_l_partial_failure_is_not_full_success(self) -> None:
        ok_document, _ok_version = self._create_document(
            number="262",
            checksum=_eli_checksum(_ELI_A),
        )
        failed_document, _failed_version = self._create_document(
            number="390",
            year=2021,
            checksum=_eli_checksum("eli/cz/sb/2021/390/2021-01-01"),
            short_title="NV 390/2021",
        )
        self._seed_completed_run()

        def _fetch(*, year, number, on_date):
            if str(number) == "262" and int(year) == 2006:
                version = legal_document_version_service.get_current_version(ok_document.id)
                sections = parsed_sections_from_version(version.id) if version is not None else []
                return fake_in_force_tree(_ELI_A, sections)
            raise ValueError("Internet není dostupný.")

        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            side_effect=_fetch,
        ):
            result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )
        self.assertEqual(result.run.status, CHECK_RUN_COMPLETED)
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.documents_checked_count, 1)
        self.assertEqual(result.documents_total_count, 2)
        self.assertIn("Nepodařilo se ověřit", result.run.note or "")
        self.assertIn(failed_document.short_title, result.run.note or "")
        message = format_automatic_check_user_message(result)
        self.assertIn("nepodařilo dokončit úplně", message)
        self.assertNotEqual(message.split("\n", 1)[0], "Kontrola změn dokončena.")

    def test_m_all_failed_marks_check_run_error(self) -> None:
        self._create_document(checksum=_eli_checksum(_ELI_A))
        self._seed_completed_run()
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            side_effect=ValueError("Internet není dostupný."),
        ):
            result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )
        self.assertEqual(result.run.status, CHECK_RUN_ERROR)
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.documents_checked_count, 0)
        message = format_automatic_check_user_message(result)
        self.assertTrue(
            message.startswith("Kontrolu právních předpisů se nepodařilo provést.")
        )
        self.assertIn("Nepodařilo se ověřit", message)
        self.assertIn("Internet není dostupný.", message)

    def test_n_redirect_outside_allowlist_is_rejected(self) -> None:
        from core.http_safe import safe_https_get

        redirect = _FakeRawResponse(
            status=301,
            headers={"Location": "https://www.zakonyprolidi.cz/cs/2006-262"},
        )
        with self.assertRaises(SafeHttpsError) as context:
            safe_https_get(
                _ACT_URL,
                allowed_hosts=ESBIRKA_OPENDATA_ALLOWED_HOSTS,
                timeout=10,
                max_bytes=1024,
                request=_request_sequence([redirect]),
            )
        self.assertEqual(str(context.exception), "Neplatná adresa služby.")

    def test_o_zakonyprolidi_is_not_on_allowlist(self) -> None:
        self.assertNotIn("www.zakonyprolidi.cz", ESBIRKA_OPENDATA_ALLOWED_HOSTS)
        self.assertNotIn("zakonyprolidi.cz", ESBIRKA_OPENDATA_ALLOWED_HOSTS)
        self.assertNotIn("www.zakonyprolidi.cz", ESBIRKA_ALLOWED_HOSTS)
        self.assertEqual(
            ESBIRKA_OPENDATA_ALLOWED_HOSTS,
            frozenset({"opendata.eselpoint.gov.cz"}),
        )

    def test_compound_number_on_document_is_accepted(self) -> None:
        document, version = self._create_document(
            number="262/2006 Sb.",
            year=2006,
            checksum=_eli_checksum(_ELI_B),
        )
        run = legal_check_run_service._begin_automatic_check(date(2024, 2, 1), date(2024, 2, 28))
        with self._patch_in_force(_ELI_B) as fetch_mock:
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(result.status, NOVELIZATION_UNCHANGED)
        fetch_mock.assert_called_once()
        self.assertEqual(fetch_mock.call_args.kwargs["year"], 2006)
        self.assertEqual(fetch_mock.call_args.kwargs["number"], "262/2006 Sb.")


if __name__ == "__main__":
    unittest.main()
