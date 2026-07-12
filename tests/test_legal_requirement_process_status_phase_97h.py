"""Fáze 97h – Stav procesu: právní požadavky."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.pravni_pozadavky.constants import (
        COMPLIANCE_CASTECNE_SPLNENO,
        COMPLIANCE_NENI_RELEVANTNI,
        COMPLIANCE_NESPLNENO,
        COMPLIANCE_SPLNENO,
        COMPLIANCE_STATUS_LABELS,
    )
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
    from moduly.pravni_pozadavky.sluzby.legal_requirement_process_status_service import (
        PROCESS_STATUS_NO_LEGAL_REQUIREMENTS,
        PROCESS_STATUS_UNEVALUATED_LABEL,
        legal_requirement_process_status_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.ui.legal_requirement_process_status_widget import (
        LegalRequirementProcessStatusWidget,
    )


class LegalRequirementProcessStatusPhase97hTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

        self._parent = legal_requirement_service.create_requirement(
            title="Kořenový proces",
            process_code="P-020",
        )

    def _create_child(
        self,
        *,
        title: str,
        process_code: str,
        compliance_status: str,
        active: bool = True,
    ):
        child = legal_requirement_service.create_requirement(
            title=title,
            process_code=process_code,
            parent_requirement_id=self._parent.id,
            compliance_status=compliance_status,
            active=active,
        )
        if compliance_status == "":
            with get_session() as session:
                row = session.get(LegalRequirement, child.id)
                assert row is not None
                row.compliance_status = ""
                session.commit()
            reloaded = legal_requirement_service.get_by_id(child.id)
            assert reloaded is not None
            return reloaded
        return child

    def test_no_children_shows_empty_message(self) -> None:
        status = legal_requirement_process_status_service.get_legal_requirements_status(
            self._parent.id,
        )
        self.assertEqual(status.requirement_count, 0)
        self.assertEqual(status.empty_message, PROCESS_STATUS_NO_LEGAL_REQUIREMENTS)

        widget = LegalRequirementProcessStatusWidget(self._parent.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Právní požadavky", labels)
        self.assertIn(PROCESS_STATUS_NO_LEGAL_REQUIREMENTS, labels)

    def test_counts_active_children_by_compliance_status(self) -> None:
        self._create_child(
            title="Splněný",
            process_code="P-020.1",
            compliance_status=COMPLIANCE_SPLNENO,
        )
        self._create_child(
            title="Částečný",
            process_code="P-020.2",
            compliance_status=COMPLIANCE_CASTECNE_SPLNENO,
        )
        self._create_child(
            title="Nesplněný",
            process_code="P-020.3",
            compliance_status=COMPLIANCE_NESPLNENO,
        )
        self._create_child(
            title="Nerelevantní",
            process_code="P-020.4",
            compliance_status=COMPLIANCE_NENI_RELEVANTNI,
        )
        self._create_child(
            title="Bez vyhodnocení",
            process_code="P-020.5",
            compliance_status="",
        )
        self._create_child(
            title="Neaktivní",
            process_code="P-020.6",
            compliance_status=COMPLIANCE_SPLNENO,
            active=False,
        )

        status = legal_requirement_process_status_service.get_legal_requirements_status(
            self._parent.id,
        )

        self.assertIsNone(status.empty_message)
        self.assertEqual(status.requirement_count, 5)
        by_code = {item.result_code: item for item in status.status_counts}
        self.assertEqual(by_code[COMPLIANCE_SPLNENO].count, 1)
        self.assertEqual(by_code[COMPLIANCE_CASTECNE_SPLNENO].count, 1)
        self.assertEqual(by_code[COMPLIANCE_NESPLNENO].count, 1)
        self.assertEqual(by_code[COMPLIANCE_NENI_RELEVANTNI].count, 1)
        self.assertEqual(by_code[""].count, 1)
        self.assertEqual(by_code[""].result_label, PROCESS_STATUS_UNEVALUATED_LABEL)
        self.assertEqual(
            by_code[COMPLIANCE_SPLNENO].result_label,
            COMPLIANCE_STATUS_LABELS[COMPLIANCE_SPLNENO],
        )

        widget = LegalRequirementProcessStatusWidget(self._parent.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Celkem: 5", labels)
        self.assertIn(f"• {COMPLIANCE_STATUS_LABELS[COMPLIANCE_SPLNENO]}: 1", labels)
        self.assertIn(f"• {PROCESS_STATUS_UNEVALUATED_LABEL}: 1", labels)

    def test_unevaluated_only_shows_summary_without_error(self) -> None:
        for index in range(1, 4):
            self._create_child(
                title=f"Požadavek {index}",
                process_code=f"P-020.{index}",
                compliance_status="",
            )

        status = legal_requirement_process_status_service.get_legal_requirements_status(
            self._parent.id,
        )
        self.assertIsNone(status.empty_message)
        self.assertEqual(status.requirement_count, 3)
        by_code = {item.result_code: item.count for item in status.status_counts}
        self.assertEqual(by_code[""], 3)

        widget = LegalRequirementProcessStatusWidget(self._parent.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Celkem: 3", labels)
        self.assertIn(f"• {PROCESS_STATUS_UNEVALUATED_LABEL}: 3", labels)
        self.assertNotIn(PROCESS_STATUS_NO_LEGAL_REQUIREMENTS, labels)

    def test_each_child_counted_once(self) -> None:
        child = self._create_child(
            title="Jeden požadavek",
            process_code="P-020.1",
            compliance_status=COMPLIANCE_SPLNENO,
        )
        # Více právních podkladů nesmí násobit počet požadavků.
        self.assertEqual(child.parent_requirement_id, self._parent.id)

        status = legal_requirement_process_status_service.get_legal_requirements_status(
            self._parent.id,
        )
        self.assertEqual(status.requirement_count, 1)

    def test_all_sections_remain_visible(self) -> None:
        widget = LegalRequirementProcessStatusWidget(self._parent.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Audity", labels)
        self.assertIn("Prověrky", labels)
        self.assertIn("Právní požadavky", labels)


if __name__ == "__main__":
    unittest.main()
