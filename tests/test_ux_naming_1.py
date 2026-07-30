"""UX-NAMING-1 – sjednocení názvosloví (UI texty)."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from core.widgets.control_result_photo_widget import PHOTO_VIEW_LABEL
from moduly.audity.constants import (
    AUDIT_PROGRAM_STATUS_APPROVED,
    AUDIT_PROGRAM_STATUS_CLOSED,
    AUDIT_PROGRAM_STATUS_DRAFT,
    AUDIT_PROGRAM_STATUS_LABELS,
)
from moduly.koordinace_bozp.constants import (
    TAB_EMPLOYERS,
    TAB_PARTICIPANTS,
    TAB_RISK_SUBMISSIONS,
)
from moduly.proverky.ui.generate_inspections_dialog import GenerateInspectionsDialog
from moduly.rizeni_rizik.constants import (
    HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
    HAZARD_IDENTIFICATION_STATUS_COMPLETED,
    HAZARD_IDENTIFICATION_STATUS_DRAFT,
    HAZARD_IDENTIFICATION_STATUS_IN_PROGRESS,
    HAZARD_IDENTIFICATION_STATUS_LABELS,
    RISK_ASSESSMENT_STATUS_COMPLETED,
    RISK_ASSESSMENT_STATUS_DRAFT,
    RISK_ASSESSMENT_STATUS_LABELS,
    RISK_MEASURE_REVIEW_STATUS_COMPLETED,
    RISK_MEASURE_REVIEW_STATUS_DRAFT,
    RISK_MEASURE_REVIEW_STATUS_LABELS,
    TAB_AI_PEER_REVIEW,
    TAB_INVENTORY,
    TAB_RISK_ASSESSMENT,
)
from moduly.vysetrovani_mu.ui.mu_dodrzovani_predpisu_widget import MuDodrzovaniPredpisuWidget


class UxNaming1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_risk_status_labels_canonical(self) -> None:
        self.assertEqual(
            HAZARD_IDENTIFICATION_STATUS_LABELS[HAZARD_IDENTIFICATION_STATUS_DRAFT],
            "Rozpracováno",
        )
        self.assertEqual(
            HAZARD_IDENTIFICATION_STATUS_LABELS[HAZARD_IDENTIFICATION_STATUS_IN_PROGRESS],
            "Probíhá",
        )
        self.assertEqual(
            HAZARD_IDENTIFICATION_STATUS_LABELS[HAZARD_IDENTIFICATION_STATUS_COMPLETED],
            "Uzavřeno",
        )
        self.assertEqual(
            HAZARD_IDENTIFICATION_STATUS_LABELS[HAZARD_IDENTIFICATION_STATUS_ARCHIVED],
            "Archivováno",
        )
        self.assertEqual(
            RISK_ASSESSMENT_STATUS_LABELS[RISK_ASSESSMENT_STATUS_DRAFT],
            "Rozpracováno",
        )
        self.assertEqual(
            RISK_ASSESSMENT_STATUS_LABELS[RISK_ASSESSMENT_STATUS_COMPLETED],
            "Uzavřeno",
        )
        self.assertEqual(
            RISK_MEASURE_REVIEW_STATUS_LABELS[RISK_MEASURE_REVIEW_STATUS_DRAFT],
            "Rozpracováno",
        )
        self.assertEqual(
            RISK_MEASURE_REVIEW_STATUS_LABELS[RISK_MEASURE_REVIEW_STATUS_COMPLETED],
            "Uzavřeno",
        )

    def test_audit_program_status_labels_canonical(self) -> None:
        self.assertEqual(AUDIT_PROGRAM_STATUS_LABELS[AUDIT_PROGRAM_STATUS_DRAFT], "Rozpracováno")
        self.assertEqual(AUDIT_PROGRAM_STATUS_LABELS[AUDIT_PROGRAM_STATUS_APPROVED], "Schváleno")
        self.assertEqual(AUDIT_PROGRAM_STATUS_LABELS[AUDIT_PROGRAM_STATUS_CLOSED], "Uzavřeno")

    def test_short_tab_names(self) -> None:
        self.assertEqual(TAB_EMPLOYERS, "Zaměstnavatelé")
        self.assertEqual(TAB_PARTICIPANTS, "Účastníci")
        self.assertEqual(TAB_RISK_SUBMISSIONS, "Předání rizik")
        self.assertEqual(TAB_INVENTORY, "Zdroje rizik")
        self.assertEqual(TAB_RISK_ASSESSMENT, "Posouzení rizik")
        self.assertEqual(TAB_AI_PEER_REVIEW, "Oponentura AI")

    def test_generate_inspections_uses_proverky(self) -> None:
        dialog = GenerateInspectionsDialog()
        try:
            self.assertEqual(dialog.windowTitle(), "Generovat prověrky")
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_photo_preview_label_is_nahled(self) -> None:
        self.assertIn("Náhled", PHOTO_VIEW_LABEL)
        self.assertNotIn("Zobrazit", PHOTO_VIEW_LABEL)

    def test_mu_group_titles_are_nouns(self) -> None:
        widget = MuDodrzovaniPredpisuWidget()
        try:
            from PySide6.QtWidgets import QGroupBox

            titles = {g.title() for g in widget.findChildren(QGroupBox)}
            self.assertIn("Platné předpisy", titles)
            self.assertIn("Revize a zjevné závady", titles)
            self.assertIn("Porušení předpisů", titles)
            self.assertIn("Kvalifikace", titles)
            self.assertNotIn("Vyber", " ".join(titles))
        finally:
            widget.close()
            widget.deleteLater()

    def test_mu_lists_use_odebrat(self) -> None:
        widget = MuDodrzovaniPredpisuWidget()
        try:
            labels = {btn.text() for btn in widget.findChildren(QPushButton)}
            self.assertIn("Odebrat", labels)
            self.assertNotIn("Odstranit", labels)
            self.assertIn("Přidat OOPP", labels)
        finally:
            widget.close()
            widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
