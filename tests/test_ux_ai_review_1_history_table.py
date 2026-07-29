"""UX-AI-REVIEW-1: čitelnost tabulky historie AI oponentur."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView

_TMP = Path(tempfile.mkdtemp(prefix="ux-ai-review-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.ai_oponentni.constants import (
        AI_PEER_REVIEW_COL_ACCEPTED,
        AI_PEER_REVIEW_COL_EXPORT_DATE,
        AI_PEER_REVIEW_COL_FILENAME,
        AI_PEER_REVIEW_COL_LOADED,
        AI_PEER_REVIEW_COL_MODEL,
        AI_PEER_REVIEW_COL_PENDING,
        AI_PEER_REVIEW_COL_REJECTED,
        AI_PEER_REVIEW_COL_RESPONSE_DATE,
        AI_PEER_REVIEW_COL_UNASSIGNED,
    )
    from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewWidget


class _ProviderStub:
    source_type = "test_source"
    uses_proposal_packages = False

    @staticmethod
    def can_export(_source_id) -> bool:
        return True


class UxAiReview1HistoryTableTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _widget(self) -> AiPeerReviewWidget:
        return AiPeerReviewWidget(provider=_ProviderStub())

    def test_history_table_row_and_header_heights(self) -> None:
        widget = self._widget()
        self.assertEqual(widget.table.verticalHeader().defaultSectionSize(), 29)
        self.assertEqual(widget.table.verticalHeader().minimumSectionSize(), 29)
        self.assertEqual(widget.table.horizontalHeader().height(), 32)
        self.assertGreater(widget.table.horizontalHeader().height(), 29)

    def test_history_table_numeric_columns_are_centered(self) -> None:
        widget = self._widget()
        widget._source_id = 1
        rows = [
            SimpleNamespace(
                id=7,
                exported_at=None,
                response_loaded_at=None,
                ai_model="gpt",
                loaded_proposals_count=12,
                pending_proposals_count=4,
                accepted_count=6,
                rejected_count=1,
                unassigned_count=1,
                export_file_path="/tmp/export_01.zip",
            )
        ]

        from datetime import datetime

        rows[0].exported_at = datetime(2026, 8, 12, 9, 30)

        with patch(
            "core.ai_oponentni.ui.ai_peer_review_widget.ai_peer_review_service.get_for_source",
            return_value=rows,
        ):
            widget._load_table()

        expected = int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        for column in (
            AI_PEER_REVIEW_COL_LOADED,
            AI_PEER_REVIEW_COL_PENDING,
            AI_PEER_REVIEW_COL_ACCEPTED,
            AI_PEER_REVIEW_COL_REJECTED,
            AI_PEER_REVIEW_COL_UNASSIGNED,
        ):
            self.assertEqual(widget.table.item(0, column).textAlignment(), expected)

        self.assertNotEqual(
            widget.table.item(0, AI_PEER_REVIEW_COL_EXPORT_DATE).textAlignment(),
            expected,
        )
        self.assertNotEqual(
            widget.table.item(0, AI_PEER_REVIEW_COL_FILENAME).textAlignment(),
            expected,
        )

    def test_history_table_file_column_stretches_and_others_stay_fixed(self) -> None:
        widget = self._widget()
        header = widget.table.horizontalHeader()

        self.assertEqual(
            header.sectionResizeMode(AI_PEER_REVIEW_COL_FILENAME),
            QHeaderView.ResizeMode.Stretch,
        )
        for column in (
            AI_PEER_REVIEW_COL_EXPORT_DATE,
            AI_PEER_REVIEW_COL_RESPONSE_DATE,
            AI_PEER_REVIEW_COL_MODEL,
            AI_PEER_REVIEW_COL_LOADED,
            AI_PEER_REVIEW_COL_PENDING,
            AI_PEER_REVIEW_COL_ACCEPTED,
            AI_PEER_REVIEW_COL_REJECTED,
            AI_PEER_REVIEW_COL_UNASSIGNED,
        ):
            self.assertEqual(
                header.sectionResizeMode(column),
                QHeaderView.ResizeMode.Fixed,
            )

        self.assertGreaterEqual(widget.table.columnWidth(AI_PEER_REVIEW_COL_EXPORT_DATE), 132)
        self.assertGreaterEqual(widget.table.columnWidth(AI_PEER_REVIEW_COL_MODEL), 128)


if __name__ == "__main__":
    unittest.main()
