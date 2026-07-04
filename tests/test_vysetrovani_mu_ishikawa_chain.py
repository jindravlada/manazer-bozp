import json
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QMessageBox

from moduly.vysetrovani_mu.constants import (
    ISHIKAWA_CATEGORIES,
    ISHIKAWA_LEVEL_BEZPROSTREDNI,
    ISHIKAWA_STATUS_HYPOTEZA,
)
from moduly.vysetrovani_mu.ui.ishikawa_cause_chain import (
    cause_factor_display,
    chain_cause_label,
)
from moduly.vysetrovani_mu.ui.mu_ishikawa_widget import MuIshikawaWidget


class VysetrovaniMuIshikawaChainTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.widget = MuIshikawaWidget()

    def test_chain_button_exists_in_toolbar(self) -> None:
        self.assertIsNotNone(self.widget.chain_btn)
        self.assertEqual(self.widget.chain_btn.text(), "Řetězec příčin")

    def test_show_chain_dialog_without_causes_shows_information(self) -> None:
        with patch.object(QMessageBox, "information") as mock_info:
            self.widget.show_chain_dialog()

        mock_info.assert_called_once()
        self.assertEqual(mock_info.call_args[0][2], "Nejsou zadány žádné příčiny.")

    def test_show_chain_dialog_with_causes_opens_dialog(self) -> None:
        self.widget._causes = [
            {
                "id": "cause-1",
                "category": ISHIKAWA_CATEGORIES[0],
                "factor": "Únava",
                "factors": ["Únava"],
                "custom_factor": "",
                "description": "Operátor byl unavený",
                "evidence": "",
                "status": ISHIKAWA_STATUS_HYPOTEZA,
                "cause_level": ISHIKAWA_LEVEL_BEZPROSTREDNI,
                "triggered_by_cause_id": "",
                "note": "",
            }
        ]

        with (
            patch(
                "moduly.vysetrovani_mu.ui.mu_ishikawa_widget.MuIshikawaChainDialog"
            ) as mock_dialog_cls,
            patch(
                "moduly.vysetrovani_mu.ui.mu_ishikawa_widget.exec_maximized"
            ) as mock_exec,
        ):
            mock_dialog = MagicMock()
            mock_dialog_cls.return_value = mock_dialog
            self.widget.show_chain_dialog()

        mock_dialog_cls.assert_called_once_with(
            self.widget,
            causes=list(self.widget._causes),
        )
        mock_exec.assert_called_once_with(mock_dialog)

    def test_add_cause_passes_existing_causes_to_dialog(self) -> None:
        existing = {
            "id": "parent-1",
            "category": ISHIKAWA_CATEGORIES[0],
            "factor": "Hluk",
            "factors": ["Hluk"],
            "custom_factor": "",
            "description": "Vysoký hluk",
            "evidence": "",
            "status": ISHIKAWA_STATUS_HYPOTEZA,
            "cause_level": ISHIKAWA_LEVEL_BEZPROSTREDNI,
            "triggered_by_cause_id": "",
            "note": "",
        }
        self.widget._investigation_id = 1
        self.widget._causes = [existing]

        with (
            patch(
                "moduly.vysetrovani_mu.ui.mu_ishikawa_widget.MuIshikawaCauseDialog"
            ) as mock_dialog_cls,
            patch(
                "moduly.vysetrovani_mu.ui.mu_ishikawa_widget.exec_maximized",
                return_value=False,
            ),
        ):
            self.widget.add_cause()

        mock_dialog_cls.assert_called_once_with(
            self.widget,
            title="Přidat příčinu",
            other_causes=[existing],
        )

    def test_edit_cause_passes_other_causes_excluding_current(self) -> None:
        first = {
            "id": "cause-1",
            "category": ISHIKAWA_CATEGORIES[0],
            "factor": "Hluk",
            "factors": ["Hluk"],
            "custom_factor": "",
            "description": "Vysoký hluk",
            "evidence": "",
            "status": ISHIKAWA_STATUS_HYPOTEZA,
            "cause_level": ISHIKAWA_LEVEL_BEZPROSTREDNI,
            "triggered_by_cause_id": "",
            "note": "",
        }
        second = {
            "id": "cause-2",
            "category": ISHIKAWA_CATEGORIES[1],
            "factor": "Únava",
            "factors": ["Únava"],
            "custom_factor": "",
            "description": "Operátor byl unavený",
            "evidence": "",
            "status": ISHIKAWA_STATUS_HYPOTEZA,
            "cause_level": ISHIKAWA_LEVEL_BEZPROSTREDNI,
            "triggered_by_cause_id": "cause-1",
            "note": "",
        }
        self.widget._investigation_id = 1
        self.widget._causes = [first, second]
        self.widget._refresh_table()
        self.widget.table.selectRow(1)

        with (
            patch(
                "moduly.vysetrovani_mu.ui.mu_ishikawa_widget.MuIshikawaCauseDialog"
            ) as mock_dialog_cls,
            patch(
                "moduly.vysetrovani_mu.ui.mu_ishikawa_widget.exec_maximized",
                return_value=False,
            ),
        ):
            self.widget.edit_cause()

        mock_dialog_cls.assert_called_once_with(
            self.widget,
            cause=second,
            title="Upravit příčinu",
            other_causes=[first],
        )

    def test_triggered_by_cause_id_persists_through_json_roundtrip(self) -> None:
        raw = {
            "causes": [
                {
                    "id": "parent",
                    "category": ISHIKAWA_CATEGORIES[0],
                    "factor": "Hluk",
                    "description": "Vysoký hluk",
                    "status": ISHIKAWA_STATUS_HYPOTEZA,
                    "cause_level": ISHIKAWA_LEVEL_BEZPROSTREDNI,
                },
                {
                    "id": "child",
                    "category": ISHIKAWA_CATEGORIES[1],
                    "factors": ["Únava"],
                    "description": "Operátor byl unavený",
                    "status": ISHIKAWA_STATUS_HYPOTEZA,
                    "cause_level": ISHIKAWA_LEVEL_BEZPROSTREDNI,
                    "triggered_by_cause_id": "parent",
                },
            ]
        }

        self.widget.load_json(json.dumps(raw, ensure_ascii=False))
        exported = json.loads(self.widget.get_json())

        self.assertEqual(exported["causes"][1]["triggered_by_cause_id"], "parent")
        self.assertEqual(exported["causes"][1]["factor"], "Únava")
        self.assertEqual(exported["causes"][1]["factors"], ["Únava"])

    def test_cause_factor_display_reads_factor_and_factors(self) -> None:
        self.assertEqual(
            cause_factor_display({"factor": "Hluk"}),
            "Hluk",
        )
        self.assertEqual(
            cause_factor_display({"factors": ["Únava", "Hluk"]}),
            "Únava",
        )
        self.assertEqual(
            chain_cause_label({"factors": ["Únava"], "description": "Popis"}),
            "Únava",
        )

    def test_chain_dialog_pdf_imports_are_available(self) -> None:
        from moduly.vysetrovani_mu.ui.ishikawa_cause_chain_layout import (
            CauseChainGraphLayoutEngine,
        )
        from moduly.vysetrovani_mu.ui.ishikawa_cause_chain_model import (
            build_cause_chain_graph_model,
        )
        from moduly.vysetrovani_mu.ui.ishikawa_cause_chain_pdf_export import (
            export_cause_chain_graph_to_pdf,
        )
        from moduly.vysetrovani_mu.ui.mu_ishikawa_chain_dialog import MuIshikawaChainDialog

        self.assertTrue(callable(build_cause_chain_graph_model))
        self.assertTrue(callable(CauseChainGraphLayoutEngine))
        self.assertTrue(callable(export_cause_chain_graph_to_pdf))
        self.assertTrue(callable(MuIshikawaChainDialog))


if __name__ == "__main__":
    unittest.main()
