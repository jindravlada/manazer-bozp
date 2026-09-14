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

    from core.http_safe import SafeHttpsError
    from moduly.pravni_pozadavky.constants import (
        DOCUMENT_TYPE_ZAKON,
        SECTION_ATTACHMENT,
        SECTION_HEAD,
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        SECTION_PART,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
        ESBIRKA_OPENDATA_ALLOWED_HOSTS,
        ESBIRKA_OPENDATA_HOST,
        ESBIRKA_OPENDATA_SPARQL_URL,
        ESbirkaOpenDataFragmentContent,
        legal_document_esbirka_opendata_client,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_tree import (
        legal_document_esbirka_opendata_tree_builder,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.sluzby.legal_section_structure_compare_service import (
        legal_section_structure_compare_service,
    )


_ELI = "eli/cz/sb/2006/262/2026-01-01"
_ON_DATE = date(2026, 9, 14)
_BASE = f"esel-esb/{_ELI}/dokument"


def _payload(iris: list[str]):
    return {
        "@id": f"esel-esb/{_ELI}",
        "má-fragment-znění": iris,
        "účinnost-znění-od": "2026-01-01",
    }


def _content(suffix: str, html: str, fragment_type: str) -> ESbirkaOpenDataFragmentContent:
    eli = f"{_ELI}/{suffix}" if not suffix.startswith("eli/") else suffix
    return ESbirkaOpenDataFragmentContent(
        fragment_eli=eli,
        fragment_type=fragment_type,
        html=html,
        text=html,
    )


def _wording(iris: list[str]):
    return legal_document_esbirka_opendata_client.extract_wording_fragments(
        _payload(iris),
        source_eli=_ELI,
        source_url=f"https://{ESBIRKA_OPENDATA_HOST}/esel-esb/{_ELI}",
    )


def _sparql_json(rows: list[dict]) -> bytes:
    bindings = []
    for row in rows:
        binding = {}
        for key, value in row.items():
            binding[key] = {"type": "literal" if key != "frag" else "uri", "value": value}
        bindings.append(binding)
    return json.dumps({"results": {"bindings": bindings}}).encode("utf-8")


class LegalESbirkaOpenDataTreeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

    def test_a_builds_rpp_tree_with_text_and_identity_keys(self) -> None:
        iris = [
            f"{_BASE}/norma/cast_1",
            f"{_BASE}/norma/cast_1/frag_1",
            f"{_BASE}/norma/cast_1/hlava_1",
            f"{_BASE}/norma/cast_1/hlava_1/frag_2",
            f"{_BASE}/norma/cast_1/hlava_1/par_1",
            f"{_BASE}/norma/cast_1/hlava_1/par_1/frag_3",
            f"{_BASE}/norma/cast_1/hlava_1/par_1/pism_a",
            f"{_BASE}/norma/cast_1/hlava_1/par_101",
            f"{_BASE}/norma/cast_1/hlava_1/par_101/odst_1",
            f"{_BASE}/prilohy/priloha_1",
            f"{_BASE}/prilohy/priloha_1/frag_9",
        ]
        wording = _wording(iris)
        contents = [
            _content("dokument/norma/cast_1", "<var>ČÁST PRVNÍ</var>", "Cast"),
            _content("dokument/norma/cast_1/frag_1", "VŠEOBECNÁ USTANOVENÍ", "Nadpis_pod"),
            _content("dokument/norma/cast_1/hlava_1", "<var>HLAVA I</var>", "Hlava"),
            _content("dokument/norma/cast_1/hlava_1/frag_2", "PŘEDMĚT ÚPRAVY", "Nadpis_pod"),
            _content("dokument/norma/cast_1/hlava_1/par_1", "<var>§ 1</var>", "Paragraf"),
            _content("dokument/norma/cast_1/hlava_1/par_1/frag_3", "Tento zákon", "Odstavec_Dc"),
            _content(
                "dokument/norma/cast_1/hlava_1/par_1/pism_a",
                "<var>a)</var> upravuje právní vztahy",
                "Pismeno_Lb",
            ),
            _content("dokument/norma/cast_1/hlava_1/par_101", "<var>§ 101</var>", "Paragraf"),
            _content(
                "dokument/norma/cast_1/hlava_1/par_101/odst_1",
                "(1) Zaměstnavatel je povinen zajistit bezpečnost",
                "Odstavec_Dc",
            ),
            _content("dokument/prilohy/priloha_1", "<var>Příloha č. 1</var>", "Hlavicka_priloha"),
            _content("dokument/prilohy/priloha_1/frag_9", "Charakteristiky platových tříd", "Odstavec_Dc"),
        ]
        parsed = legal_document_esbirka_opendata_tree_builder.build_parsed_sections(
            wording,
            contents,
        )
        by_type = {}
        for section in parsed:
            by_type.setdefault(section.section_type, []).append(section)

        part = by_type[SECTION_PART][0]
        self.assertEqual(part.section_number, "PRVNÍ")
        self.assertEqual(part.text, "VŠEOBECNÁ USTANOVENÍ")

        head = by_type[SECTION_HEAD][0]
        self.assertEqual(head.section_number, "I")
        self.assertEqual(head.parent_sort_order, part.sort_order)

        par1 = next(item for item in by_type[SECTION_PARAGRAPH] if item.paragraph == "1")
        self.assertEqual(par1.title, "Tento zákon")
        self.assertEqual(par1.parent_sort_order, head.sort_order)

        letter = by_type[SECTION_LETTER][0]
        self.assertEqual(letter.item_letter, "a")
        self.assertEqual(letter.text, "upravuje právní vztahy")
        self.assertEqual(letter.parent_sort_order, par1.sort_order)

        odst = by_type[SECTION_SUBSECTION][0]
        self.assertEqual(odst.section_number, "1")
        self.assertIn("bezpečnost", odst.text)

        attachment = by_type[SECTION_ATTACHMENT][0]
        self.assertEqual(attachment.section_number, "1")
        self.assertIn("Charakteristiky", attachment.text)

        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262",
            year=2006,
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Test",
        )
        stored = legal_section_service.create_tree_from_parsed(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            parsed_sections=parsed,
        )
        keys = {
            legal_section_structure_compare_service.section_identity_key(
                section,
                sections_by_id={item.id: item for item in stored},
            )
            for section in stored
        }
        self.assertIn("cast:PRVNÍ", keys)
        self.assertIn("cast:PRVNÍ/hlava:I/§:1", keys)
        self.assertIn("cast:PRVNÍ/hlava:I/§:1/pism:a", keys)
        self.assertIn("cast:PRVNÍ/hlava:I/§:101/odst:1", keys)

        compared = legal_section_structure_compare_service.compare_version_sections(
            old_sections=stored,
            new_sections=stored,
        )
        self.assertFalse(compared.has_changes)

    def test_b_empty_or_unrelated_contents_are_not_a_valid_tree(self) -> None:
        wording = _wording([f"{_BASE}/norma/cast_1", f"{_BASE}/norma/cast_1/par_1"])
        with self.assertRaisesRegex(ValueError, "Neočekávaný formát"):
            legal_document_esbirka_opendata_tree_builder.build_parsed_sections(wording, [])
        with self.assertRaisesRegex(ValueError, "Neočekávaný formát"):
            legal_document_esbirka_opendata_tree_builder.build_parsed_sections(
                wording,
                [_content("dokument/norma/cast_9/par_999", "cizí", "Paragraf")],
            )

    def test_c_sparql_fetch_uses_official_endpoint_once(self) -> None:
        body = _sparql_json(
            [
                {
                    "frag": f"https://{ESBIRKA_OPENDATA_HOST}/esel-esb/{_ELI}/dokument/norma/par_1",
                    "text": "<var>§ 1</var>",
                    "typ": "https://opendata.eselpoint.gov.cz/esel-esb/cis-esb-typ-fragmentu/položka/Paragraf",
                }
            ]
        )
        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
            return_value=type(
                "R",
                (),
                {
                    "status_code": 200,
                    "body": body,
                    "final_url": ESBIRKA_OPENDATA_SPARQL_URL,
                },
            )(),
        ) as get_mock:
            contents = legal_document_esbirka_opendata_client.fetch_wording_fragment_contents(
                _ELI,
            )
        get_mock.assert_called_once()
        url = get_mock.call_args.args[0]
        self.assertTrue(url.startswith(ESBIRKA_OPENDATA_SPARQL_URL))
        self.assertEqual(
            set(get_mock.call_args.kwargs["allowed_hosts"]),
            set(ESBIRKA_OPENDATA_ALLOWED_HOSTS),
        )
        self.assertEqual(contents[0].fragment_type, "Paragraf")
        self.assertIn("§ 1", contents[0].html)

    def test_d_sparql_network_error_is_failed(self) -> None:
        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
            side_effect=SafeHttpsError("Služba není dostupná.", kind="network"),
        ):
            with self.assertRaisesRegex(ValueError, "Internet není dostupný"):
                legal_document_esbirka_opendata_client.fetch_wording_fragment_contents(_ELI)

    def test_e_live_262_and_361_build_text_trees(self) -> None:
        try:
            labour = legal_document_esbirka_opendata_tree_builder.fetch_in_force_parsed_sections(
                year=2006,
                number="262",
                on_date=_ON_DATE,
            )
            driving = legal_document_esbirka_opendata_tree_builder.fetch_in_force_parsed_sections(
                year=2007,
                number="361",
                on_date=_ON_DATE,
            )
        except ValueError as exc:
            message = str(exc)
            if "Internet" in message or "dostupn" in message:
                self.skipTest(message)
            raise

        labour_types = {section.section_type: 0 for section in labour}
        for section in labour:
            labour_types[section.section_type] = labour_types.get(section.section_type, 0) + 1
        self.assertGreaterEqual(labour_types.get(SECTION_PART, 0), 10)
        self.assertGreaterEqual(labour_types.get(SECTION_PARAGRAPH, 0), 400)
        par101 = next(item for item in labour if item.paragraph == "101")
        odst101 = next(
            item
            for item in labour
            if item.section_type == SECTION_SUBSECTION
            and item.parent_sort_order == par101.sort_order
            and item.section_number == "1"
        )
        self.assertIn("bezpečnost", odst101.text.casefold())
        self.assertTrue(any((item.text or item.title) and "§" not in (item.text or "") for item in labour))

        driving_types: dict[str, int] = {}
        for section in driving:
            driving_types[section.section_type] = driving_types.get(section.section_type, 0) + 1
        self.assertGreaterEqual(driving_types.get(SECTION_PART, 0), 3)
        self.assertGreaterEqual(driving_types.get(SECTION_PARAGRAPH, 0), 50)
        par10 = next(item for item in driving if item.paragraph == "10")
        self.assertTrue((par10.title or par10.text).strip())
        self.assertTrue(
            any(item.section_type == SECTION_ATTACHMENT and (item.text or item.title) for item in driving)
        )


if __name__ == "__main__":
    unittest.main()
