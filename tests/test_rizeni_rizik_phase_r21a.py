"""R21a – zjednodušení editoru Identifikace rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
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

    from core.ai_oponentni.constants import AI_PEER_REVIEW_TAB_TITLE
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_IDENTIFICATION_VISIBLE_TABS,
        TAB_AI_PEER_REVIEW,
        TAB_HISTORY,
        TAB_MEASURES,
        TAB_PUBLICATION,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import (
        HazardIdentificationDialog,
    )


class PhaseR21aTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

        operation = settings_service.save_workplace(
            name="Provoz R21a",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Pracoviště R21a",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        cls.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )

    def test_visible_tabs_only(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        labels = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertEqual(labels, list(HAZARD_IDENTIFICATION_VISIBLE_TABS))
        for hidden in (
            TAB_AI_PEER_REVIEW,
            AI_PEER_REVIEW_TAB_TITLE,
            TAB_MEASURES,
            TAB_PUBLICATION,
            TAB_HISTORY,
        ):
            self.assertNotIn(hidden, labels)
        self.assertFalse(hasattr(dialog, "ai_peer_review_widget"))


if __name__ == "__main__":
    unittest.main()
