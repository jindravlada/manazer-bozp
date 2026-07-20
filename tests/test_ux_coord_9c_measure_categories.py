"""UX-COORD-9c – úprava kategorií společných pravidel BOZP."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-9c-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import (
        MEASURE_CATEGORIES_SELECTABLE,
        MEASURE_CATEGORY_EMERGENCIES,
        MEASURE_CATEGORY_LABELS,
        MEASURE_CATEGORY_PPE,
        MEASURE_CATEGORY_WORK_ORGANIZATION,
        MEASURE_CATEGORY_WORKPLACE_HANDOVER,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_measure_service import (
        coordination_measure_service,
    )
    from moduly.koordinace_bozp.ui.coordination_measure_dialog import (
        CoordinationMeasureDialog,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class UxCoord9cMeasureCategoriesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationContact))
            session.execute(delete(CoordinationEmployerActivity))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()
        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha 1",
            nace="",
            abbreviation="",
        )

    def test_new_measure_hides_deprecated_categories(self) -> None:
        dialog = CoordinationMeasureDialog(None)
        available = dialog.available_category_ids()
        labels = [
            dialog.category.itemText(index)
            for index in range(dialog.category.count())
        ]
        self.assertEqual(tuple(available), MEASURE_CATEGORIES_SELECTABLE)
        self.assertNotIn(MEASURE_CATEGORY_PPE, available)
        self.assertNotIn(MEASURE_CATEGORY_EMERGENCIES, available)
        self.assertNotIn(MEASURE_CATEGORY_WORKPLACE_HANDOVER, available)
        self.assertNotIn(MEASURE_CATEGORY_LABELS[MEASURE_CATEGORY_PPE], labels)
        self.assertNotIn(
            MEASURE_CATEGORY_LABELS[MEASURE_CATEGORY_EMERGENCIES],
            labels,
        )
        self.assertNotIn(
            MEASURE_CATEGORY_LABELS[MEASURE_CATEGORY_WORKPLACE_HANDOVER],
            labels,
        )
        self.assertIn(
            MEASURE_CATEGORY_LABELS[MEASURE_CATEGORY_WORK_ORGANIZATION],
            labels,
        )
        dialog.close()

    def test_legacy_measure_keeps_category_on_edit(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9c legacy",
            meeting_date=date.today(),
        )
        for category, title in (
            (MEASURE_CATEGORY_PPE, "OOPP legacy"),
            (MEASURE_CATEGORY_EMERGENCIES, "MU legacy"),
            (MEASURE_CATEGORY_WORKPLACE_HANDOVER, "Předání legacy"),
        ):
            measure = coordination_measure_service.add(
                coordination.id,
                title=title,
                description="Původní text",
                category=category,
            )
            dialog = CoordinationMeasureDialog(None, measure=measure)
            available = dialog.available_category_ids()
            self.assertIn(category, available)
            self.assertEqual(dialog.category.currentData(), category)
            self.assertEqual(dialog.title.text(), title)

            # Uložení bez změny kategorie.
            data = dialog.get_data()
            self.assertEqual(data["category"], category)
            updated = coordination_measure_service.update(
                measure.id,
                title=data["title"],
                description=data["description"] + " upraveno",
                category=data["category"],
            )
            assert updated is not None
            self.assertEqual(updated.category, category)
            self.assertEqual(updated.description, "Původní text upraveno")
            dialog.close()


if __name__ == "__main__":
    unittest.main()
