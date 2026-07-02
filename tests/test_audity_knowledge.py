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
