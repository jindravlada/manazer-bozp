import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service


class AudityKnowledgeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_load_processes(self) -> None:
        processes = audit_knowledge_service.get_processes()

        self.assertGreaterEqual(len(processes), 1)
        process_ids = {process.id for process in processes}
        self.assertIn("urazy_mimo_udalosti", process_ids)

    def test_load_process_detail(self) -> None:
        process = audit_knowledge_service.get_process_by_id("urazy_mimo_udalosti")

        assert process is not None
        self.assertEqual(process.nazev, "Řízení pracovních úrazů a mimořádných událostí")
        self.assertTrue(process.ucel_procesu)
        self.assertTrue(process.has_knowledge_file)

        knowledge = audit_knowledge_service.load_process_knowledge(process)
        assert knowledge is not None
        self.assertEqual(knowledge["id"], "urazy_mimo_udalosti")
        self.assertIn("včas oznámeny", knowledge["ucel_procesu"])

    def test_process_contains_criteria(self) -> None:
        process = audit_knowledge_service.get_process_by_id("urazy_mimo_udalosti")
        assert process is not None

        knowledge = audit_knowledge_service.load_process_knowledge(process)
        assert knowledge is not None

        criteria = audit_knowledge_service.get_active_criteria(knowledge)
        self.assertGreaterEqual(len(criteria), 1)
        self.assertEqual(criteria[0]["id"], "evidence_hlaseni_urazu")

    def test_criterion_contains_audit_questions(self) -> None:
        criterion = audit_knowledge_service.get_criterion(
            "urazy_mimo_udalosti",
            "evidence_hlaseni_urazu",
        )

        assert criterion is not None
        questions = audit_knowledge_service.get_audit_questions(criterion)
        self.assertEqual(len(questions), 5)
        self.assertEqual(questions[0]["id"], "vsechny_urazy_evidovany")
        self.assertEqual(questions[0]["text"], "Všechny pracovní úrazy jsou evidovány.")
        self.assertEqual(questions[0]["nazev"], "Všechny pracovní úrazy jsou evidovány.")

    def test_question_stable_key(self) -> None:
        stable_key = audit_knowledge_service.question_stable_key(
            "urazy_mimo_udalosti",
            "evidence_hlaseni_urazu",
            "vsechny_urazy_evidovany",
        )

        self.assertEqual(
            stable_key,
            "urazy_mimo_udalosti/evidence_hlaseni_urazu/vsechny_urazy_evidovany",
        )

    def test_migrates_auditni_tvrzeni_from_seed_for_legacy_user_catalog(self) -> None:
        from core.services.editable_catalog_service import editable_catalog_service

        bundled_path = editable_catalog_service.bundled_path("audity/urazy_mimo_udalosti.json")
        seed_data = audit_knowledge_service._load_json(bundled_path)
        user_data = audit_knowledge_service._load_json(bundled_path)

        section = next(
            item
            for item in user_data.get("sekce") or []
            if item.get("id") == "evidence_hlaseni_urazu"
        )
        section.pop("auditni_tvrzeni", None)
        section["navodne_otazky"] = [
            {
                "id": "evidence_klasifikace_ohlasovani",
                "nazev": "Jak organizace zajišťuje, že jsou všechny pracovní úrazy řádně evidovány, správně klasifikovány a jsou splněny všechny zákonné ohlašovací povinnosti?",
                "popis": "Organizace má zavedený a uplatňovaný postup pro hlášení, evidenci, klasifikaci a plnění ohlašovacích povinností u pracovních úrazů.",
                "poradi": 10,
                "aktivni": True,
                "zavaznost": "vysoka",
            }
        ]

        self.assertTrue(
            audit_knowledge_service._merge_knowledge_from_seed(user_data, seed_data)
        )

        migrated_section = next(
            item
            for item in user_data.get("sekce") or []
            if item.get("id") == "evidence_hlaseni_urazu"
        )
        self.assertEqual(len(migrated_section.get("auditni_tvrzeni") or []), 5)
        self.assertEqual(migrated_section.get("navodne_otazky"), [])

        questions = audit_knowledge_service.get_audit_questions(migrated_section)
        self.assertEqual(len(questions), 5)
        self.assertEqual(questions[0]["id"], "vsechny_urazy_evidovany")

    def test_merge_adds_new_sections_from_seed(self) -> None:
        from core.services.editable_catalog_service import editable_catalog_service

        bundled_path = editable_catalog_service.bundled_path("audity/urazy_mimo_udalosti.json")
        seed_data = audit_knowledge_service._load_json(bundled_path)
        user_data = audit_knowledge_service._load_json(bundled_path)

        user_data["verze"] = 4
        user_data["sekce"] = [
            section
            for section in user_data.get("sekce") or []
            if section.get("id") == "evidence_hlaseni_urazu"
        ]

        self.assertTrue(
            audit_knowledge_service._merge_knowledge_from_seed(user_data, seed_data)
        )

        section_ids = {section.get("id") for section in user_data.get("sekce") or []}
        self.assertIn("evidence_hlaseni_urazu", section_ids)
        self.assertIn("vysetrovani_urazu", section_ids)
        self.assertIn("mimoradne_udalosti", section_ids)
        self.assertEqual(len(user_data["sekce"]), len(seed_data["sekce"]))
        self.assertEqual(user_data["verze"], seed_data["verze"])

    def test_merge_adds_new_list_items_without_overwriting_user_edits(self) -> None:
        seed_section = {
            "id": "evidence_hlaseni_urazu",
            "auditni_tvrzeni": [
                {
                    "id": "vsechny_urazy_evidovany",
                    "text": "Seed text",
                    "popis": "Seed popis",
                    "poradi": 10,
                    "aktivni": True,
                    "zavaznost": "vysoka",
                },
                {
                    "id": "nova_tvrzeni",
                    "text": "Nové tvrzení ze seed dat.",
                    "popis": "Popis nového tvrzení.",
                    "poradi": 60,
                    "aktivni": True,
                    "zavaznost": "stredni",
                },
            ],
            "objektivni_dukazy": [
                {
                    "id": "dukaz_kniha_urazu",
                    "nazev": "Seed kniha",
                    "poradi": 10,
                    "aktivni": True,
                },
                {
                    "id": "dukaz_novy",
                    "nazev": "Nový důkaz",
                    "poradi": 60,
                    "aktivni": True,
                },
            ],
        }
        user_section = {
            "id": "evidence_hlaseni_urazu",
            "auditni_tvrzeni": [
                {
                    "id": "vsechny_urazy_evidovany",
                    "text": "Uživatelsky upravený text.",
                    "popis": "Uživatelský popis.",
                    "poradi": 10,
                    "aktivni": True,
                    "zavaznost": "vysoka",
                }
            ],
            "objektivni_dukazy": [
                {
                    "id": "dukaz_kniha_urazu",
                    "nazev": "Uživatelská kniha úrazů",
                    "poradi": 10,
                    "aktivni": True,
                }
            ],
        }

        self.assertTrue(
            audit_knowledge_service._merge_section_fields_from_seed(
                user_section,
                seed_section,
                full_severity_sync=False,
            )
        )

        assertions = {item["id"]: item for item in user_section["auditni_tvrzeni"]}
        self.assertEqual(
            assertions["vsechny_urazy_evidovany"]["text"],
            "Uživatelsky upravený text.",
        )
        self.assertIn("nova_tvrzeni", assertions)

        dukazy = {item["id"]: item for item in user_section["objektivni_dukazy"]}
        self.assertEqual(dukazy["dukaz_kniha_urazu"]["nazev"], "Uživatelská kniha úrazů")
        self.assertIn("dukaz_novy", dukazy)

    def test_auditni_tvrzeni_fallback_to_navodne_otazky(self) -> None:
        criterion = {
            "navodne_otazky": [
                {
                    "id": "legacy_question",
                    "nazev": "Stará otázka",
                    "aktivni": True,
                }
            ]
        }
        questions = audit_knowledge_service.get_audit_questions(criterion)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["id"], "legacy_question")


if __name__ == "__main__":
    unittest.main()
