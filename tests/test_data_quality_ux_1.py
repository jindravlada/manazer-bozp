"""DATA-QUALITY-UX-1: otevření nalezených podobných položek."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.sluzby.similarity_checked_pair_service import (
        SIMILARITY_ENTITY_AUDIT_ASSERTION,
        SIMILARITY_ENTITY_LEGAL_REQUIREMENT,
        SIMILARITY_ENTITY_MEASURE,
        SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
        SIMILARITY_ENTITY_RISK,
    )
    from core.shared.sluzby.similarity_domain_analysis import SimilarityAnalysisPair
    from core.shared.sluzby.similarity_item_collectors import SimilarityItem
    from core.shared.sluzby.similarity_item_opener import (
        SimilarityItemOpenError,
        open_similarity_item,
        resolve_item_identity,
    )
    from core.ui.similarity_analysis_dialog import SimilarityAnalysisDialog


def _item(entity_type: str, composite_id: str, text: str = "text") -> SimilarityItem:
    return SimilarityItem(
        entity_type=entity_type,
        composite_id=composite_id,
        text=text,
        location_label="Umístění",
    )


def _pair(left: SimilarityItem, right: SimilarityItem) -> SimilarityAnalysisPair:
    return SimilarityAnalysisPair(
        score=0.92,
        match_type="very_similar",
        match_label="Velmi podobné",
        left=left,
        right=right,
        pair_entity_type=f"cross:{left.entity_type}:{right.entity_type}",
    )


class DataQualityUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_resolve_strips_cross_domain_prefix(self) -> None:
        item = _item(
            SIMILARITY_ENTITY_AUDIT_ASSERTION,
            f"{SIMILARITY_ENTITY_AUDIT_ASSERTION}::proc::crit::asrt",
        )
        entity_type, composite_id = resolve_item_identity(item)
        self.assertEqual(entity_type, SIMILARITY_ENTITY_AUDIT_ASSERTION)
        self.assertEqual(composite_id, "proc::crit::asrt")

    def test_open_proverky_builds_editor(self) -> None:
        item = _item(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            "area::sekce::bod1",
        )
        with (
            patch(
                "moduly.proverky.ui.proverky_knowledge_editor_dialog.ProverkyKnowledgeEditorDialog"
            ) as dialog_cls,
            patch(
                "core.shared.sluzby.similarity_item_opener.exec_maximized",
                return_value=0,
            ) as exec_mock,
        ):
            dialog_cls.return_value = MagicMock()
            open_similarity_item(None, item)
        dialog_cls.assert_called_once()
        kwargs = dialog_cls.call_args.kwargs
        self.assertEqual(kwargs["area_id"], "area")
        self.assertEqual(kwargs["section_id"], "sekce")
        self.assertEqual(kwargs["control_point_id"], "bod1")
        exec_mock.assert_called_once()

    def test_open_audit_builds_editor(self) -> None:
        item = _item(
            SIMILARITY_ENTITY_AUDIT_ASSERTION,
            f"{SIMILARITY_ENTITY_AUDIT_ASSERTION}::proc-1::krit-2::tvrzeni-3",
        )
        with (
            patch(
                "moduly.audity.ui.audity_knowledge_editor_dialog.AudityKnowledgeEditorDialog"
            ) as dialog_cls,
            patch(
                "core.shared.sluzby.similarity_item_opener.exec_maximized",
                return_value=0,
            ),
        ):
            dialog_cls.return_value = MagicMock()
            open_similarity_item(None, item)
        kwargs = dialog_cls.call_args.kwargs
        self.assertEqual(kwargs["process_id"], "proc-1")
        self.assertEqual(kwargs["criterion_id"], "krit-2")

    def test_open_legal_loads_requirement(self) -> None:
        item = _item(SIMILARITY_ENTITY_LEGAL_REQUIREMENT, "42")
        requirement = MagicMock()
        with (
            patch(
                "moduly.pravni_pozadavky.sluzby.legal_requirement_service.legal_requirement_service.get_by_id",
                return_value=requirement,
            ),
            patch(
                "moduly.pravni_pozadavky.ui.legal_requirement_dialog.LegalRequirementDialog"
            ) as dialog_cls,
            patch(
                "core.shared.sluzby.similarity_item_opener.exec_maximized",
                return_value=0,
            ),
        ):
            dialog_cls.return_value = MagicMock()
            open_similarity_item(None, item)
        dialog_cls.assert_called_once()
        self.assertIs(dialog_cls.call_args.kwargs["requirement"], requirement)

    def test_open_measure_required(self) -> None:
        item = _item(SIMILARITY_ENTITY_MEASURE, "required:17")
        measure = MagicMock()
        measure.hazard_risk_assessment_id = 9
        with (
            patch(
                "moduly.rizeni_rizik.sluzby.hazard_required_measure_service.hazard_required_measure_service.get_by_id",
                return_value=measure,
            ),
            patch(
                "core.shared.sluzby.similarity_item_opener._identification_id_for_assessment",
                return_value=3,
            ),
            patch(
                "moduly.rizeni_rizik.ui.hazard_required_measure_dialog.HazardRequiredMeasureDialog"
            ) as dialog_cls,
            patch(
                "core.shared.sluzby.similarity_item_opener.exec_maximized",
                return_value=0,
            ),
        ):
            dialog_cls.return_value = MagicMock()
            open_similarity_item(None, item)
        kwargs = dialog_cls.call_args.kwargs
        self.assertEqual(kwargs["hazard_identification_id"], 3)
        self.assertEqual(kwargs["hazard_risk_assessment_id"], 9)
        self.assertIs(kwargs["measure"], measure)

    def test_open_risk_builds_event_dialog(self) -> None:
        item = _item(SIMILARITY_ENTITY_RISK, "11")
        event = MagicMock()
        event.inventory_item_id = 5
        with (
            patch(
                "moduly.rizeni_rizik.sluzby.hazard_event_service.hazard_event_service.get_by_id",
                return_value=event,
            ),
            patch(
                "core.shared.sluzby.similarity_item_opener._identification_id_for_event",
                return_value=2,
            ),
            patch(
                "moduly.rizeni_rizik.ui.hazard_event_dialog.HazardEventDialog"
            ) as dialog_cls,
            patch(
                "core.shared.sluzby.similarity_item_opener.exec_maximized",
                return_value=0,
            ),
        ):
            dialog_cls.return_value = MagicMock()
            open_similarity_item(None, item)
        kwargs = dialog_cls.call_args.kwargs
        self.assertEqual(kwargs["hazard_identification_id"], 2)
        self.assertIs(kwargs["event"], event)

    def test_unknown_entity_raises_concrete_message(self) -> None:
        item = _item("neznama_oblast", "x")
        with self.assertRaises(SimilarityItemOpenError) as ctx:
            open_similarity_item(None, item)
        self.assertNotIn("dalším sprintu", str(ctx.exception))
        self.assertIn("editor", str(ctx.exception).casefold())

    def test_dialog_open_first_second_both_cross_domain(self) -> None:
        left = _item(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            f"{SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT}::a::s::i1",
            "Prověrka",
        )
        right = _item(
            SIMILARITY_ENTITY_AUDIT_ASSERTION,
            f"{SIMILARITY_ENTITY_AUDIT_ASSERTION}::p::c::t",
            "Audit",
        )
        dialog = SimilarityAnalysisDialog()
        dialog._pairs = [_pair(left, right)]
        dialog._show_results()
        dialog._results_table.selectRow(0)

        opened: list[str] = []

        def fake_open(_parent, item):
            opened.append(item.entity_type)

        with patch(
            "core.ui.similarity_analysis_dialog.open_similarity_item",
            side_effect=fake_open,
        ):
            dialog._open_selected("first")
            dialog._open_selected("second")
            dialog._open_selected("both")
        self.assertEqual(
            opened,
            [
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                SIMILARITY_ENTITY_AUDIT_ASSERTION,
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                SIMILARITY_ENTITY_AUDIT_ASSERTION,
            ],
        )
        dialog.close()

    def test_dialog_open_audit_then_proverky(self) -> None:
        left = _item(
            SIMILARITY_ENTITY_AUDIT_ASSERTION,
            f"{SIMILARITY_ENTITY_AUDIT_ASSERTION}::p::c::t",
        )
        right = _item(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            f"{SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT}::a::s::i1",
        )
        dialog = SimilarityAnalysisDialog()
        dialog._pairs = [_pair(left, right)]
        dialog._show_results()
        dialog._results_table.selectRow(0)
        opened: list[str] = []

        def fake_open(_parent, item):
            opened.append(item.entity_type)

        with patch(
            "core.ui.similarity_analysis_dialog.open_similarity_item",
            side_effect=fake_open,
        ):
            dialog._open_selected("both")
        self.assertEqual(
            opened,
            [
                SIMILARITY_ENTITY_AUDIT_ASSERTION,
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            ],
        )
        dialog.close()

    def test_dialog_no_placeholder_sprint_message(self) -> None:
        item = _item(SIMILARITY_ENTITY_AUDIT_ASSERTION, "p::c::t")
        dialog = SimilarityAnalysisDialog()
        with (
            patch(
                "core.ui.similarity_analysis_dialog.open_similarity_item",
                side_effect=SimilarityItemOpenError("Konkrétní důvod."),
            ),
            patch.object(QMessageBox, "warning") as warn,
            patch.object(QMessageBox, "information") as info,
        ):
            dialog._open_similarity_item(item)
        warn.assert_called_once()
        self.assertIn("Konkrétní důvod.", warn.call_args.args[2])
        info.assert_not_called()
        dialog.close()


if __name__ == "__main__":
    unittest.main()
