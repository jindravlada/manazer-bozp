"""UX-COORD-4a – zobrazení organizačních opatření v náhledu a ODT."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QGroupBox, QLabel
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-4a-"))
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
        MEASURE_CATEGORY_COMMUNICATION,
        MEASURE_CATEGORY_LABELS,
        MEASURE_CATEGORY_PERSON_MOVEMENT,
        MEASURE_CATEGORY_VEHICLE_MOVEMENT,
        MEASURE_CATEGORY_WORK_ORGANIZATION,
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
        protocol_measure_display_text,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
        coordination_protocol_odt_renderer,
    )
    from moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog import (
        CoordinationProtocolPreviewDialog,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _deactivate_template_measures(coordination_id: int) -> None:
    for item in coordination_measure_service.list_for_coordination(coordination_id):
        if item.template_code:
            coordination_measure_service.deactivate(item.id)


class UxCoord4aMeasuresDisplayTestCase(unittest.TestCase):
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

    def test_display_text_prefers_description(self) -> None:
        self.assertEqual(
            protocol_measure_display_text(
                {
                    "title": "Organizační zajištění",
                    "description": (
                        "Organizační zajištění prací zajistí vedoucí zaměstnanec."
                    ),
                }
            ),
            "Organizační zajištění prací zajistí vedoucí zaměstnanec.",
        )

    def test_display_text_falls_back_to_title(self) -> None:
        self.assertEqual(
            protocol_measure_display_text(
                {"title": "Parkování vozidel", "description": ""}
            ),
            "Parkování vozidel",
        )
        self.assertEqual(
            protocol_measure_display_text({"title": "Parkování vozidel"}),
            "Parkování vozidel",
        )

    def test_flatten_omits_category_labels(self) -> None:
        groups = [
            {
                "category": MEASURE_CATEGORY_WORK_ORGANIZATION,
                "category_label": MEASURE_CATEGORY_LABELS[
                    MEASURE_CATEGORY_WORK_ORGANIZATION
                ],
                "measures": [
                    {
                        "title": "Organizační zajištění",
                        "description": "Organizační zajištění prací zajistí vedoucí.",
                        "sort_order": 0,
                    }
                ],
            },
            {
                "category": MEASURE_CATEGORY_VEHICLE_MOVEMENT,
                "category_label": MEASURE_CATEGORY_LABELS[
                    MEASURE_CATEGORY_VEHICLE_MOVEMENT
                ],
                "measures": [
                    {
                        "title": "Parkování vozidel",
                        "description": "Vozidla lze parkovat pouze na určených místech.",
                        "sort_order": 0,
                    }
                ],
            },
        ]
        lines = flatten_protocol_measure_bullets(groups)
        self.assertEqual(
            lines,
            [
                "• Organizační zajištění prací zajistí vedoucí.",
                "• Vozidla lze parkovat pouze na určených místech.",
            ],
        )
        joined = "\n".join(lines)
        self.assertNotIn("Organizace práce", joined)
        self.assertNotIn("Pohyb vozidel", joined)
        self.assertNotIn(":", joined)

    def test_order_by_category_then_sort_order(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-4a pořadí",
            meeting_date=date.today(),
        )
        _deactivate_template_measures(coordination.id)
        # Person movement je v MEASURE_CATEGORIES před communication.
        later_cat = coordination_measure_service.add(
            coordination.id,
            title="Komunikace A",
            description="Text komunikace A",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        earlier_cat = coordination_measure_service.add(
            coordination.id,
            title="Pohyb B",
            description="",
            category=MEASURE_CATEGORY_PERSON_MOVEMENT,
        )
        with get_session() as session:
            first = session.get(CoordinationMeasure, earlier_cat.id)
            second = session.get(CoordinationMeasure, later_cat.id)
            assert first is not None and second is not None
            first.sort_order = 20
            second.sort_order = 10
            # druhé opatření ve stejné kategorii movement – nižší sort_order první
            third = CoordinationMeasure(
                coordination_id=coordination.id,
                title="Pohyb A",
                description="Text pohybu A",
                category=MEASURE_CATEGORY_PERSON_MOVEMENT,
                sort_order=5,
                active=True,
            )
            session.add(third)
            session.commit()

        result = coordination_protocol_builder.build(coordination.id)
        lines = flatten_protocol_measure_bullets(
            result.protocol_data["measures_by_category"]
        )
        self.assertEqual(
            lines,
            [
                "• Text pohybu A",
                "• Pohyb B",
                "• Text komunikace A",
            ],
        )

    def test_inactive_measures_excluded(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-4a neaktivní",
            meeting_date=date.today(),
        )
        _deactivate_template_measures(coordination.id)
        active = coordination_measure_service.add(
            coordination.id,
            title="Aktivní",
            description="Popis aktivního",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        inactive = coordination_measure_service.add(
            coordination.id,
            title="Neaktivní",
            description="Popis neaktivního",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        coordination_measure_service.deactivate(inactive.id)

        result = coordination_protocol_builder.build(coordination.id)
        lines = flatten_protocol_measure_bullets(
            result.protocol_data["measures_by_category"]
        )
        self.assertEqual(lines, ["• Popis aktivního"])
        self.assertEqual(result.summary.active_measures, 1)
        self.assertIs(active.id, active.id)

    def test_preview_and_odt_hide_categories(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-4a UI",
            meeting_date=date.today(),
        )
        coordination_measure_service.add(
            coordination.id,
            title="Organizační zajištění",
            description="Organizační zajištění prací zajistí vedoucí zaměstnanec.",
            category=MEASURE_CATEGORY_WORK_ORGANIZATION,
        )
        coordination_measure_service.add(
            coordination.id,
            title="Parkování vozidel",
            description="",
            category=MEASURE_CATEGORY_VEHICLE_MOVEMENT,
        )

        result = coordination_protocol_builder.build(coordination.id)
        with patch(
            "moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog."
            "coordination_protocol_builder.build",
            return_value=result,
        ):
            dialog = CoordinationProtocolPreviewDialog(
                None,
                coordination_id=coordination.id,
            )
        section_texts = []
        for group in dialog.findChildren(QGroupBox):
            if group.title() == "Společná pravidla BOZP":
                for label in group.findChildren(QLabel):
                    section_texts.append(label.text())
        joined = "\n".join(section_texts)
        self.assertIn(
            "• Organizační zajištění prací zajistí vedoucí zaměstnanec.",
            joined,
        )
        self.assertIn("• Parkování vozidel", joined)
        self.assertNotIn("Organizace práce", joined)
        self.assertNotIn("Pohyb vozidel", joined)
        dialog.close()

        target = _TMP / "measures.odt"
        coordination_protocol_odt_renderer.render_from_result(target, result)
        content = _odt_content(target)
        self.assertIn(
            "Organizační zajištění prací zajistí vedoucí zaměstnanec.",
            content,
        )
        self.assertIn("Parkování vozidel", content)
        self.assertNotIn("Organizace práce", content)
        self.assertNotIn("Pohyb vozidel", content)
        # Kategorie jako nadpis „…:“ se v ODT nesmí objevit.
        for label in MEASURE_CATEGORY_LABELS.values():
            self.assertNotIn(f"{label}:", content)


if __name__ == "__main__":
    unittest.main()
