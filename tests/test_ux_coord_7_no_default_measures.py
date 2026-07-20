"""UX-COORD-7 – zrušení velké výchozí sady organizačních opatření.

UX-COORD-9d doplňuje malou pevnou sadu společných pravidel; tento test ověřuje,
že se neobnovila stará obecná sada a že dialog nemá checkbox pro výchozí opatření.
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-7-"))
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
        DEFAULT_COMMON_BOZP_RULE_CODES,
        DEFAULT_COMMON_BOZP_RULES,
        MEASURE_CATEGORY_COMMUNICATION,
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
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog


class UxCoord7NoDefaultMeasuresTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationContact))
            session.execute(delete(CoordinationEmployerActivity))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()

    def test_new_coordination_gets_only_small_common_rules_set(self) -> None:
        created = bozp_coordination_service.create_coordination(
            subject="Bez velké výchozí sady",
            meeting_date=date(2026, 7, 19),
            place="Místnost",
        )
        measures = coordination_measure_service.list_for_coordination(created.id)
        self.assertEqual(len(measures), len(DEFAULT_COMMON_BOZP_RULES))
        self.assertEqual(
            sorted(item.template_code for item in measures),
            sorted(DEFAULT_COMMON_BOZP_RULE_CODES),
        )

    def test_create_dialog_has_no_default_checkbox(self) -> None:
        dialog = BozpCoordinationDialog(None)
        self.assertFalse(hasattr(dialog, "insert_default_measures"))
        self.assertNotIn("insert_default_measures", dialog.get_data())
        dialog.close()

    def test_create_inserts_exactly_default_common_rules(self) -> None:
        before = 0
        with get_session() as session:
            before = session.query(CoordinationMeasure).count()
        bozp_coordination_service.create_coordination(
            subject="Kontrola automatiky",
            meeting_date=date.today(),
            place="Areál",
        )
        with get_session() as session:
            after = session.query(CoordinationMeasure).count()
        self.assertEqual(after, before + len(DEFAULT_COMMON_BOZP_RULES))

    def test_existing_measures_unchanged(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="Existující opatření",
            meeting_date=date.today(),
            place="Areál",
        )
        measure = coordination_measure_service.add(
            coordination.id,
            title="Ruční opatření",
            category=MEASURE_CATEGORY_COMMUNICATION,
            description="Zůstane beze změny",
        )
        other = bozp_coordination_service.create_coordination(
            subject="Jiná koordinace",
            meeting_date=date.today(),
            place="Areál",
        )
        reloaded = coordination_measure_service.get_by_id(measure.id)
        assert reloaded is not None
        self.assertEqual(reloaded.title, "Ruční opatření")
        self.assertEqual(reloaded.description, "Zůstane beze změny")
        other_measures = coordination_measure_service.list_for_coordination(other.id)
        self.assertEqual(len(other_measures), len(DEFAULT_COMMON_BOZP_RULES))
        self.assertEqual(
            len(coordination_measure_service.list_for_coordination(coordination.id)),
            len(DEFAULT_COMMON_BOZP_RULES) + 1,
        )


if __name__ == "__main__":
    unittest.main()
