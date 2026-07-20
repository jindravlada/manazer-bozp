"""UX-COORD-9d – výchozí společná pravidla BOZP."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete, text

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-9d-"))
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
        DEFAULT_COMMON_BOZP_RULE_CODES,
        DEFAULT_COMMON_BOZP_RULES,
        DEFAULT_COMMON_RULE_FOLLOW_COORDINATOR,
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
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        coordination_protocol_builder,
        flatten_protocol_measure_bullets,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class UxCoord9dDefaultCommonRulesTestCase(unittest.TestCase):
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
        )

    def test_template_code_column_exists(self) -> None:
        self.assertIn("template_code", _table_columns("coordination_measures"))

    def test_new_coordination_gets_exactly_one_default_set(self) -> None:
        created = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9d sada",
            meeting_date=date.today(),
        )
        measures = coordination_measure_service.list_for_coordination(created.id)
        self.assertEqual(len(measures), len(DEFAULT_COMMON_BOZP_RULES))
        codes = [item.template_code for item in measures]
        self.assertEqual(sorted(codes), sorted(DEFAULT_COMMON_BOZP_RULE_CODES))
        by_code = {item.template_code: item for item in measures}
        for spec in DEFAULT_COMMON_BOZP_RULES:
            item = by_code[spec["template_code"]]
            self.assertEqual(item.title, spec["title"])
            self.assertEqual(item.description, spec["description"])
            self.assertEqual(item.category, spec["category"])
            self.assertTrue(item.active)

    def test_repeated_ensure_does_not_duplicate(self) -> None:
        created = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9d duplicity",
            meeting_date=date.today(),
        )
        again = coordination_measure_service.ensure_default_common_rules(created.id)
        self.assertEqual(again, [])
        measures = coordination_measure_service.list_for_coordination(created.id)
        self.assertEqual(len(measures), len(DEFAULT_COMMON_BOZP_RULES))
        updated = bozp_coordination_service.update_coordination(
            created.id,
            meeting_date=created.meeting_date,
            place=created.place or "",
            subject=created.subject,
            note="uložení znovu",
        )
        assert updated is not None
        measures_after = coordination_measure_service.list_for_coordination(created.id)
        self.assertEqual(len(measures_after), len(DEFAULT_COMMON_BOZP_RULES))

    def test_old_coordination_not_backfilled(self) -> None:
        with get_session() as session:
            session.execute(
                text(
                    """
                    INSERT INTO bozp_coordinations (
                        coordination_number, meeting_date, place, subject,
                        status, note, active, created_at, updated_at
                    ) VALUES (
                        'LEGACY-9d', :meeting_date, '', 'Stará koordinace',
                        'draft', '', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"meeting_date": date.today().isoformat()},
            )
            session.commit()
            legacy_id = session.execute(
                text(
                    "SELECT id FROM bozp_coordinations "
                    "WHERE coordination_number = 'LEGACY-9d'"
                )
            ).scalar_one()

        measures = coordination_measure_service.list_for_coordination(legacy_id)
        self.assertEqual(measures, [])
        # Otevření / update nesmí doplnit výchozí sadu.
        bozp_coordination_service.update_coordination(
            legacy_id,
            meeting_date=date.today(),
            place="",
            subject="Stará koordinace",
            note="",
            valid_from=date.today(),
            valid_to=date.today(),
        )
        self.assertEqual(
            coordination_measure_service.list_for_coordination(legacy_id),
            [],
        )

    def test_default_rules_editable_and_deactivatable(self) -> None:
        created = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9d edit",
            meeting_date=date.today(),
        )
        follow = next(
            item
            for item in coordination_measure_service.list_for_coordination(created.id)
            if item.template_code == DEFAULT_COMMON_RULE_FOLLOW_COORDINATOR
        )
        updated = coordination_measure_service.update(
            follow.id,
            title="Upravený pokyn.",
            description="Upravený text.",
            category=follow.category,
        )
        assert updated is not None
        self.assertEqual(updated.title, "Upravený pokyn.")
        self.assertEqual(updated.template_code, DEFAULT_COMMON_RULE_FOLLOW_COORDINATOR)

        self.assertTrue(coordination_measure_service.deactivate(follow.id))
        reloaded = coordination_measure_service.get_by_id(follow.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

        result = coordination_protocol_builder.build(created.id)
        bullets = flatten_protocol_measure_bullets(
            result.protocol_data["measures_by_category"]
        )
        self.assertNotIn("• Upravený text.", bullets)
        self.assertEqual(
            result.summary.active_measures,
            len(DEFAULT_COMMON_BOZP_RULES) - 1,
        )


if __name__ == "__main__":
    unittest.main()
