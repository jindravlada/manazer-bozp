import importlib
import sys
import unittest


class LegalSectionTreeImportPhase90aTestCase(unittest.TestCase):
    def test_legal_section_tree_module_imports_without_error(self) -> None:
        module_name = "moduly.pravni_pozadavky.ui.legal_section_tree"
        sys.modules.pop(module_name, None)

        module = importlib.import_module(module_name)

        self.assertTrue(hasattr(module, "LegalSectionTree"))
        self.assertTrue(callable(module.LegalSectionTree))
        self.assertTrue(hasattr(module, "load_version_sections_into_tree"))


if __name__ == "__main__":
    unittest.main()
