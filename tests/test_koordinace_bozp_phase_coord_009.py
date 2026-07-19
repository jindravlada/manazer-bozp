"""Fáze COORD-009 – organizační opatření."""

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

_TMP = Path(tempfile.mkdtemp(prefix="coord-009-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import (
        DEFAULT_COORDINATION_MEASURES,
        MEASURE_CATEGORY_COMMUNICATION,
        MEASURE_CATEGORY_EMERGENCIES,
        MEASURE_CATEGORY_LABELS,
        MEASURE_CATEGORY_WORK_ORGANIZATION,
        TAB_MEASURES,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
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
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
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
        CoordinationMeasureError,
        coordination_measure_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service


class KoordinaceBozpPhaseCoord009TestCase(unittest.TestCase):
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
            address="Praha",
            nace="",
        )

    def _create_coordination(self, **kwargs):
        return bozp_coordination_service.create_coordination(
            subject="COORD-009",
            meeting_date=date.today(),
            **kwargs,
        )

    def test_model_table(self) -> None:
        columns = _table_columns("coordination_measures")
        for name in (
            "id",
            "coordination_id",
            "title",
            "description",
            "category",
            "sort_order",
            "active",
        ):
            self.assertIn(name, columns)

    def test_create_measure(self) -> None:
        coordination = self._create_coordination()
        measure = coordination_measure_service.add(
            coordination.id,
            title="Dodržovat pokyny koordinátora BOZP.",
            description="Platí pro všechny dodavatele.",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        self.assertEqual(measure.title, "Dodržovat pokyny koordinátora BOZP.")
        self.assertEqual(measure.category, MEASURE_CATEGORY_COMMUNICATION)
        self.assertTrue(measure.active)
        self.assertEqual(measure.sort_order, 1)

    def test_change_sort_order(self) -> None:
        coordination = self._create_coordination()
        first = coordination_measure_service.add(
            coordination.id,
            title="První",
            category=MEASURE_CATEGORY_WORK_ORGANIZATION,
        )
        second = coordination_measure_service.add(
            coordination.id,
            title="Druhé",
            category=MEASURE_CATEGORY_WORK_ORGANIZATION,
        )
        third = coordination_measure_service.add(
            coordination.id,
            title="Třetí",
            category=MEASURE_CATEGORY_WORK_ORGANIZATION,
        )
        self.assertTrue(coordination_measure_service.move_up(second.id))
        titles = [
            item.title
            for item in coordination_measure_service.list_for_coordination(
                coordination.id
            )
        ]
        self.assertEqual(titles, ["Druhé", "První", "Třetí"])
        self.assertTrue(coordination_measure_service.move_down(first.id))
        titles = [
            item.title
            for item in coordination_measure_service.list_for_coordination(
                coordination.id
            )
        ]
        self.assertEqual(titles, ["Druhé", "Třetí", "První"])
        # okraj: už nelze nahoru / dolů
        self.assertFalse(coordination_measure_service.move_up(second.id))
        self.assertFalse(coordination_measure_service.move_down(first.id))
        self.assertEqual(third.id, third.id)

    def test_change_category(self) -> None:
        coordination = self._create_coordination()
        measure = coordination_measure_service.add(
            coordination.id,
            title="Oznámit událost",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        updated = coordination_measure_service.update(
            measure.id,
            title="Oznámit událost",
            description="ihned",
            category=MEASURE_CATEGORY_EMERGENCIES,
        )
        self.assertEqual(updated.category, MEASURE_CATEGORY_EMERGENCIES)
        self.assertEqual(
            coordination_measure_service.category_label(updated.category),
            MEASURE_CATEGORY_LABELS[MEASURE_CATEGORY_EMERGENCIES],
        )
        with self.assertRaises(CoordinationMeasureError):
            coordination_measure_service.update(
                measure.id,
                title="x",
                category="neplatna",
            )

    def test_deactivate(self) -> None:
        coordination = self._create_coordination()
        measure = coordination_measure_service.add(
            coordination.id,
            title="Únikové cesty",
            category=MEASURE_CATEGORY_WORK_ORGANIZATION,
        )
        self.assertTrue(coordination_measure_service.deactivate(measure.id))
        reloaded = coordination_measure_service.get_by_id(measure.id)
        self.assertFalse(reloaded.active)
        self.assertTrue(coordination_measure_service.activate(measure.id))
        self.assertTrue(coordination_measure_service.get_by_id(measure.id).active)

    def test_insert_default_template(self) -> None:
        coordination = self._create_coordination(insert_default_measures=True)
        items = coordination_measure_service.list_for_coordination(coordination.id)
        self.assertEqual(len(items), len(DEFAULT_COORDINATION_MEASURES))
        self.assertEqual(
            [item.title for item in items],
            [title for _category, title in DEFAULT_COORDINATION_MEASURES],
        )
        self.assertEqual(
            [item.sort_order for item in items],
            list(range(1, len(items) + 1)),
        )

    def test_edit_inserted_measures(self) -> None:
        coordination = self._create_coordination(insert_default_measures=True)
        items = coordination_measure_service.list_for_coordination(coordination.id)
        first = items[0]
        updated = coordination_measure_service.update(
            first.id,
            title="Upravený pokyn koordinátora.",
            description="Doplněný popis",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        self.assertEqual(updated.title, "Upravený pokyn koordinátora.")
        self.assertEqual(updated.description, "Doplněný popis")
        # ostatní zůstávají
        titles = [
            item.title
            for item in coordination_measure_service.list_for_coordination(
                coordination.id
            )
        ]
        self.assertEqual(len(titles), len(DEFAULT_COORDINATION_MEASURES))
        self.assertIn("Upravený pokyn koordinátora.", titles)

    def test_order_preserved_after_save(self) -> None:
        coordination = self._create_coordination(insert_default_measures=True)
        items = coordination_measure_service.list_for_coordination(coordination.id)
        # přesun posledního nahoru a znovu načtení
        last = items[-1]
        coordination_measure_service.move_up(last.id)
        reloaded = coordination_measure_service.list_for_coordination(coordination.id)
        self.assertEqual(reloaded[-2].id, last.id)
        self.assertEqual(
            [item.sort_order for item in reloaded],
            list(range(1, len(reloaded) + 1)),
        )

    def test_ui_tab_and_create_checkbox(self) -> None:
        create_dialog = BozpCoordinationDialog(None)
        self.assertFalse(create_dialog.insert_default_measures.isHidden())
        self.assertTrue(create_dialog.insert_default_measures.isChecked())
        self.assertIn("insert_default_measures", create_dialog.get_data())

        coordination = self._create_coordination()
        edit_dialog = BozpCoordinationDialog(None, coordination=coordination)
        labels = [edit_dialog.tabs.tabText(i) for i in range(edit_dialog.tabs.count())]
        self.assertIn(TAB_MEASURES, labels)
        self.assertTrue(edit_dialog.insert_default_measures.isHidden())
        self.assertNotIn("insert_default_measures", edit_dialog.get_data())
        self.assertFalse(edit_dialog.measures_tab.content.isHidden())


if __name__ == "__main__":
    unittest.main()
