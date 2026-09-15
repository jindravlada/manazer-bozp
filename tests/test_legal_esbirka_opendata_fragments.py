import json
import unittest
from datetime import date
from unittest.mock import patch

from core.http_safe import SafeHttpsError
from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
    ESBIRKA_OPENDATA_ALLOWED_HOSTS,
    ESBIRKA_OPENDATA_HOST,
    ESBIRKA_OPENDATA_MAX_RESPONSE_BYTES,
    ESBIRKA_OPENDATA_WORDING_MAX_RESPONSE_BYTES,
    legal_document_esbirka_opendata_client,
)

_ELI_262 = "eli/cz/sb/2006/262/2026-01-01"
_ELI_361 = "eli/cz/sb/2007/361/2026-09-01"
_WORDING_URL_262 = f"https://{ESBIRKA_OPENDATA_HOST}/esel-esb/{_ELI_262}"
_ON_DATE = date(2026, 9, 14)

_FRAG_PAR = f"esel-esb/{_ELI_262}/dokument/norma/cast_4/hlava_2/dil_1/par_84"
_FRAG_ODST = f"esel-esb/{_ELI_262}/dokument/norma/cast_1/hlava_4/par_16/odst_4"
_FRAG_PISM = f"esel-esb/{_ELI_262}/dokument/norma/cast_13/hlava_14/par_334a/odst_1/pism_a"
_FRAG_BOD = f"esel-esb/{_ELI_262}/dokument/norma/cast_14/hlava_2/par_395/bod_14"
_FRAG_PRILOHA = f"esel-esb/{_ELI_262}/dokument/prilohy/priloha_0"
_FRAG_DOKUMENT = f"esel-esb/{_ELI_262}/dokument"
_FRAG_361_PISM = f"esel-esb/{_ELI_361}/dokument/norma/cast_3/hlava_1/par_41/odst_2/pism_a"
_FRAG_361_PRILOHA = f"esel-esb/{_ELI_361}/dokument/prilohy/priloha_5/cast_B/bod_2:2/pism_a"


def _wording_payload(*, eli: str = _ELI_262, fragments: list | None = None, **overrides):
    data = {
        "@id": f"esel-esb/{eli}",
        "@type": "l-sgov-dat-sbirka-pojem:znění-právního-aktu",
        "má-fragment-znění": fragments
        if fragments is not None
        else [
            _FRAG_DOKUMENT,
            _FRAG_PAR,
            _FRAG_ODST,
            _FRAG_PISM,
            _FRAG_BOD,
            _FRAG_PRILOHA,
        ],
        "má-typ-znění-právního-aktu": "esel-esb/cis-esb-typ-znění/položka/KONSOL",
        "účinnost-znění-od": eli.rsplit("/", 1)[-1],
        "účinnost-znění-do": "2026-12-31",
    }
    data.update(overrides)
    return data


def _by_kind(document, kind: str):
    return [item for item in document.fragments if item.section_kind == kind]


class LegalESbirkaOpenDataFragmentsTestCase(unittest.TestCase):
    def test_a_builds_wording_url_from_eli(self) -> None:
        self.assertEqual(
            legal_document_esbirka_opendata_client.build_wording_url(_ELI_262),
            _WORDING_URL_262,
        )

    def test_b_rejects_invalid_eli_before_http(self) -> None:
        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
        ) as get_mock:
            with self.assertRaisesRegex(ValueError, "Neočekávaný formát"):
                legal_document_esbirka_opendata_client.fetch_wording_fragments("not-an-eli")
        get_mock.assert_not_called()

    def test_c_extracts_hierarchy_from_real_262_iris(self) -> None:
        document = legal_document_esbirka_opendata_client.extract_wording_fragments(
            _wording_payload(),
            source_eli=_ELI_262,
            source_url=_WORDING_URL_262,
        )
        self.assertEqual(document.source_eli, _ELI_262)
        self.assertEqual(document.effective_from, date(2026, 1, 1))
        self.assertEqual(document.effective_to, date(2026, 12, 31))
        self.assertEqual(document.wording_type, "KONSOL")
        self.assertEqual(len(document.fragments), 6)

        paragraf = _by_kind(document, "par")[0]
        self.assertEqual(paragraf.section_number, "84")
        self.assertEqual(paragraf.document_part, "norma")
        self.assertEqual(
            paragraf.path_segments,
            ("norma", "cast_4", "hlava_2", "dil_1", "par_84"),
        )
        self.assertEqual(paragraf.parent_path, "norma/cast_4/hlava_2/dil_1")

        odstavec = _by_kind(document, "odst")[0]
        self.assertEqual(odstavec.section_number, "4")
        self.assertEqual(odstavec.parent_path.endswith("par_16"), True)

        pismeno = _by_kind(document, "pism")[0]
        self.assertEqual(pismeno.section_number, "a")

        bod = _by_kind(document, "bod")[0]
        self.assertEqual(bod.section_number, "14")

        priloha = _by_kind(document, "priloha")[0]
        self.assertEqual(priloha.document_part, "prilohy")
        self.assertEqual(priloha.section_number, "0")

        dokument = _by_kind(document, "dokument")[0]
        self.assertEqual(dokument.fragment_eli, f"{_ELI_262}/dokument")
        self.assertTrue(dokument.source_url.startswith(f"https://{ESBIRKA_OPENDATA_HOST}/"))

    def test_d_extracts_361_letter_and_attachment_paths(self) -> None:
        payload = _wording_payload(
            eli=_ELI_361,
            fragments=[_FRAG_361_PISM, _FRAG_361_PRILOHA],
            **{"účinnost-znění-do": None},
        )
        del payload["účinnost-znění-do"]
        document = legal_document_esbirka_opendata_client.extract_wording_fragments(
            payload,
            source_eli=_ELI_361,
            source_url=f"https://{ESBIRKA_OPENDATA_HOST}/esel-esb/{_ELI_361}",
        )
        pismeno = _by_kind(document, "pism")[0]
        self.assertEqual(pismeno.section_number, "a")
        self.assertIn("par_41", pismeno.path_segments)
        priloha_letter = document.fragments[1]
        self.assertEqual(priloha_letter.section_kind, "pism")
        self.assertEqual(priloha_letter.document_part, "prilohy")
        self.assertEqual(priloha_letter.path_segments[-2], "bod_2:2")
        self.assertEqual(document.effective_from, date(2026, 9, 1))
        self.assertIsNone(document.effective_to)

    def test_e_skips_invalid_foreign_and_off_allowlist_iris(self) -> None:
        payload = _wording_payload(
            fragments=[
                _FRAG_PAR,
                "https://www.zakonyprolidi.cz/cs/2006-262",
                "esel-esb/eli/cz/sb/2007/361/2026-09-01/dokument/norma/par_1",
                "not-an-iri",
                {"@id": f"https://{ESBIRKA_OPENDATA_HOST}/esel-esb/{_ELI_262}/dokument/norma/cast_1/par_1"},
                _FRAG_PAR,
            ]
        )
        document = legal_document_esbirka_opendata_client.extract_wording_fragments(
            payload,
            source_eli=_ELI_262,
            source_url=_WORDING_URL_262,
        )
        self.assertEqual(
            [item.fragment_eli for item in document.fragments],
            [
                f"{_ELI_262}/dokument/norma/cast_4/hlava_2/dil_1/par_84",
                f"{_ELI_262}/dokument/norma/cast_1/par_1",
            ],
        )
        self.assertEqual(document.fragments[0].list_index, 0)
        self.assertEqual(document.fragments[1].list_index, 4)

    def test_f_empty_fragment_list_is_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Seznam fragmentů je prázdný"):
            legal_document_esbirka_opendata_client.extract_wording_fragments(
                _wording_payload(fragments=[]),
                source_eli=_ELI_262,
                source_url=_WORDING_URL_262,
            )

    def test_g_missing_fragment_metadata_is_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Neočekávaný formát"):
            legal_document_esbirka_opendata_client.extract_wording_fragments(
                {"@id": f"esel-esb/{_ELI_262}"},
                source_eli=_ELI_262,
                source_url=_WORDING_URL_262,
            )

    def test_h_all_invalid_iris_are_incomplete_response(self) -> None:
        with self.assertRaisesRegex(ValueError, "Neočekávaný formát"):
            legal_document_esbirka_opendata_client.extract_wording_fragments(
                _wording_payload(fragments=["https://www.zakonyprolidi.cz/cs/2006-262"]),
                source_eli=_ELI_262,
                source_url=_WORDING_URL_262,
            )

    def test_i_fetch_uses_wording_url_allowlist_and_larger_limit(self) -> None:
        body = json.dumps(_wording_payload()).encode("utf-8")
        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
            return_value=type(
                "R",
                (),
                {"status_code": 200, "body": body, "final_url": _WORDING_URL_262},
            )(),
        ) as get_mock:
            document = legal_document_esbirka_opendata_client.fetch_wording_fragments(
                _ELI_262,
            )
        get_mock.assert_called_once()
        self.assertEqual(get_mock.call_args.args[0], _WORDING_URL_262)
        self.assertEqual(
            set(get_mock.call_args.kwargs["allowed_hosts"]),
            set(ESBIRKA_OPENDATA_ALLOWED_HOSTS),
        )
        self.assertEqual(
            get_mock.call_args.kwargs["max_bytes"],
            ESBIRKA_OPENDATA_WORDING_MAX_RESPONSE_BYTES,
        )
        self.assertGreater(
            ESBIRKA_OPENDATA_WORDING_MAX_RESPONSE_BYTES,
            ESBIRKA_OPENDATA_MAX_RESPONSE_BYTES,
        )
        self.assertGreater(ESBIRKA_OPENDATA_WORDING_MAX_RESPONSE_BYTES, 272_354)
        self.assertEqual(len(document.fragments), 6)

    def test_j_network_timeout_too_large_and_invalid_json_fail(self) -> None:
        cases = [
            (SafeHttpsError("Služba není dostupná.", kind="network"), r"kind=network.*endpoint=wording"),
            (SafeHttpsError("Vypršel časový limit spojení.", kind="timeout"), r"kind=timeout.*endpoint=wording"),
            (SafeHttpsError("Odpověď je příliš velká.", kind="too_large"), r"kind=too_large.*endpoint=wording"),
            (SafeHttpsError("Neplatná adresa služby.", kind="invalid_url"), r"kind=invalid_url.*endpoint=wording"),
        ]
        for error, message in cases:
            with self.subTest(kind=error.kind):
                with patch(
                    "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
                    side_effect=error,
                ):
                    with self.assertRaisesRegex(ValueError, message):
                        legal_document_esbirka_opendata_client.fetch_wording_fragments(
                            _ELI_262,
                        )
        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
            return_value=type(
                "R",
                (),
                {
                    "status_code": 200,
                    "body": b"{",
                    "final_url": _WORDING_URL_262,
                },
            )(),
        ):
            with self.assertRaisesRegex(ValueError, "Neočekávaný formát"):
                legal_document_esbirka_opendata_client.fetch_wording_fragments(_ELI_262)

    def test_k_http_404_is_not_found(self) -> None:
        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
            return_value=type(
                "R",
                (),
                {"status_code": 404, "body": b"", "final_url": _WORDING_URL_262},
            )(),
        ):
            with self.assertRaisesRegex(ValueError, "Předpis nenalezen"):
                legal_document_esbirka_opendata_client.fetch_wording_fragments(_ELI_262)

    def test_l_prefixed_keys_and_id_objects(self) -> None:
        payload = {
            "@id": f"esel-esb/{_ELI_262}",
            "l-sgov-dat-sbirka-pojem:má-fragment-znění": [
                {"@id": f"https://{ESBIRKA_OPENDATA_HOST}/esel-esb/{_ELI_262}/dokument/norma/par_1"},
            ],
            "l-sgov-dat-sbirka-pojem:účinnost-znění-od": "2026-01-01",
        }
        document = legal_document_esbirka_opendata_client.extract_wording_fragments(
            payload,
            source_eli=_ELI_262,
            source_url=_WORDING_URL_262,
        )
        self.assertEqual(document.fragments[0].section_kind, "par")
        self.assertEqual(document.fragments[0].section_number, "1")
        self.assertEqual(document.effective_from, date(2026, 1, 1))

    def test_m_live_in_force_262_and_361_have_reconstructable_structure(self) -> None:
        try:
            labour = legal_document_esbirka_opendata_client.fetch_in_force_wording_fragments(
                year=2006,
                number="262",
                on_date=_ON_DATE,
            )
            driving = legal_document_esbirka_opendata_client.fetch_in_force_wording_fragments(
                year=2007,
                number="361",
                on_date=_ON_DATE,
            )
        except ValueError as exc:
            message = str(exc)
            if "kind=network" in message or "kind=timeout" in message or "kind=http_status" in message:
                self.skipTest(message)
            if "Internet" in message or "dostupn" in message:
                self.skipTest(message)
            raise

        self.assertEqual(labour.source_eli, _ELI_262)
        self.assertGreaterEqual(len(labour.fragments), 2500)
        self.assertTrue(_by_kind(labour, "par"))
        self.assertTrue(_by_kind(labour, "odst"))
        self.assertTrue(_by_kind(labour, "pism"))
        self.assertTrue(_by_kind(labour, "priloha"))
        self.assertTrue(all(item.fragment_eli.startswith(_ELI_262) for item in labour.fragments))
        self.assertTrue(
            all(item.source_url.startswith(f"https://{ESBIRKA_OPENDATA_HOST}/") for item in labour.fragments)
        )

        self.assertEqual(driving.source_eli, _ELI_361)
        self.assertGreaterEqual(len(driving.fragments), 1000)
        self.assertTrue(_by_kind(driving, "par"))
        self.assertTrue(_by_kind(driving, "pism"))
        self.assertTrue(_by_kind(driving, "priloha"))
        self.assertTrue(all(item.fragment_eli.startswith(_ELI_361) for item in driving.fragments))


if __name__ == "__main__":
    unittest.main()
