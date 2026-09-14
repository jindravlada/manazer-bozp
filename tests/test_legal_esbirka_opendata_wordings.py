import json
import unittest
from datetime import date
from unittest.mock import patch

from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
    ESBIRKA_OPENDATA_BASE_URL,
    legal_document_esbirka_opendata_client,
)

_ACT_URL = f"{ESBIRKA_OPENDATA_BASE_URL}/2006/262"
_ELI_2026 = "eli/cz/sb/2006/262/2026-01-01"
_ELI_2027 = "eli/cz/sb/2006/262/2027-01-01"
_ELI_2015 = "eli/cz/sb/2006/262/2015-11-25"
_ON_DATE = date(2026, 9, 14)


def _payload(**overrides):
    data = {
        "@id": "esel-esb/eli/cz/sb/2006/262",
        "má-poslední-znění": f"esel-esb/{_ELI_2027}",
        "má-vyhlášené-znění": "esel-esb/eli/cz/sb/2006/262/0000-00-00",
        "má-znění": [
            f"esel-esb/{_ELI_2015}",
            "esel-esb/eli/cz/sb/2006/262/0000-00-00",
            f"esel-esb/{_ELI_2026}",
            f"esel-esb/{_ELI_2027}",
        ],
    }
    data.update(overrides)
    return data


class LegalESbirkaOpenDataWordingsTestCase(unittest.TestCase):
    def test_a_extracts_dated_wordings_and_skips_proclaimed(self) -> None:
        wordings = legal_document_esbirka_opendata_client.extract_temporal_wordings(
            _payload(),
            source_url=_ACT_URL,
        )
        elis = [item.source_eli for item in wordings]
        self.assertEqual(elis, [_ELI_2015, _ELI_2026, _ELI_2027])
        self.assertTrue(all(item.effective_from is not None for item in wordings))
        self.assertEqual(wordings[1].effective_from, date(2026, 1, 1))
        self.assertEqual(wordings[1].source_url, _ACT_URL)

    def test_b_in_force_is_not_future_last_wording(self) -> None:
        wordings = legal_document_esbirka_opendata_client.extract_temporal_wordings(
            _payload(),
            source_url=_ACT_URL,
        )
        latest = legal_document_esbirka_opendata_client.extract_latest_wording(
            _payload(),
            source_url=_ACT_URL,
        )
        in_force = legal_document_esbirka_opendata_client.select_in_force_wording(
            wordings,
            _ON_DATE,
        )
        future = legal_document_esbirka_opendata_client.select_future_wordings(
            wordings,
            _ON_DATE,
        )
        assert in_force is not None
        self.assertEqual(in_force.source_eli, _ELI_2026)
        self.assertEqual(latest.last_wording_eli, _ELI_2027)
        self.assertNotEqual(in_force.source_eli, latest.last_wording_eli)
        self.assertEqual([item.source_eli for item in future], [_ELI_2027])

    def test_c_accepts_prefixed_keys_and_id_objects(self) -> None:
        payload = {
            "@id": "esel-esb/eli/cz/sb/2006/262",
            "l-sgov-dat-sbirka-pojem:má-znění": [
                {"@id": f"https://opendata.eselpoint.gov.cz/esel-esb/{_ELI_2026}"},
                {"@id": f"https://opendata.eselpoint.gov.cz/esel-esb/{_ELI_2027}"},
            ],
        }
        wordings = legal_document_esbirka_opendata_client.extract_temporal_wordings(
            payload,
            source_url=_ACT_URL,
        )
        self.assertEqual(
            [item.source_eli for item in wordings],
            [_ELI_2026, _ELI_2027],
        )

    def test_d_falls_back_to_last_wording_when_list_missing(self) -> None:
        payload = {
            "@id": "esel-esb/eli/cz/sb/2006/262",
            "má-poslední-znění": f"esel-esb/{_ELI_2026}",
        }
        wordings = legal_document_esbirka_opendata_client.extract_temporal_wordings(
            payload,
            source_url=_ACT_URL,
        )
        self.assertEqual([item.source_eli for item in wordings], [_ELI_2026])

    def test_e_rejects_payload_without_dated_wordings(self) -> None:
        with self.assertRaisesRegex(ValueError, "Neočekávaný formát"):
            legal_document_esbirka_opendata_client.extract_temporal_wordings(
                {"@id": "esel-esb/eli/cz/sb/2006/262"},
                source_url=_ACT_URL,
            )

    def test_f_deduplicates_and_ignores_last_wording_key_as_list(self) -> None:
        payload = _payload(
            **{
                "má-znění": [
                    f"esel-esb/{_ELI_2026}",
                    f"esel-esb/{_ELI_2026}",
                ],
                "má-poslední-znění": [
                    f"esel-esb/{_ELI_2027}",
                ],
            }
        )
        wordings = legal_document_esbirka_opendata_client.extract_temporal_wordings(
            payload,
            source_url=_ACT_URL,
        )
        self.assertEqual([item.source_eli for item in wordings], [_ELI_2026])

    def test_g_fetch_temporal_wordings_uses_act_metadata_url(self) -> None:
        body = json.dumps(_payload()).encode("utf-8")
        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
            return_value=type(
                "R",
                (),
                {"status_code": 200, "body": body, "final_url": _ACT_URL},
            )(),
        ) as get_mock:
            wordings = legal_document_esbirka_opendata_client.fetch_temporal_wordings(
                year=2006,
                number="262",
            )
        get_mock.assert_called_once()
        kwargs = get_mock.call_args
        self.assertEqual(kwargs.args[0], _ACT_URL)
        self.assertEqual(
            set(kwargs.kwargs["allowed_hosts"]),
            {"opendata.eselpoint.gov.cz"},
        )
        self.assertEqual(
            [item.source_eli for item in wordings],
            [_ELI_2015, _ELI_2026, _ELI_2027],
        )

    def test_h_no_in_force_wording_before_first_dated_eli(self) -> None:
        wordings = legal_document_esbirka_opendata_client.extract_temporal_wordings(
            _payload(),
            source_url=_ACT_URL,
        )
        self.assertIsNone(
            legal_document_esbirka_opendata_client.select_in_force_wording(
                wordings,
                date(2015, 11, 24),
            )
        )


if __name__ == "__main__":
    unittest.main()
