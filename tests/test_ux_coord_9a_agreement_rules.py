"""UX-COORD-9a – dohoda a společná pravidla BOZP."""

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

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-9a-"))
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
        AGREEMENT_FIXED_PART_ORDER,
        AGREEMENT_PART_FINAL,
        AGREEMENT_PART_PPE,
        AGREEMENT_PART_WORK_INTENT,
        AGREEMENT_PART_WORKPLACE_HANDOVER,
        AGREEMENT_SECTION_TITLE,
        COMMON_RULES_SECTION_TITLE,
        TAB_MEASURES,
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
        build_coordination_agreement_parts,
        coordination_protocol_builder,
        flatten_protocol_measure_bullets,
        protocol_agreement_part_titles,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
        PROTOCOL_ODT_CHAPTER_TITLES,
        coordination_protocol_odt_renderer,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
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


class UxCoord9aAgreementRulesTestCase(unittest.TestCase):
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

    def test_columns_and_tab_rename(self) -> None:
        columns = _table_columns("bozp_coordinations")
        for name in (
            "work_intent_information_text",
            "ppe_text",
            "workplace_handover_text",
            "final_provisions_text",
        ):
            self.assertIn(name, columns)

        self.assertEqual(TAB_MEASURES, "Dohoda a pravidla BOZP")
        dialog = BozpCoordinationDialog(None)
        labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertIn("Dohoda a pravidla BOZP", labels)
        self.assertNotIn("Organizační opatření", labels)
        dialog.close()

        self.assertIn(AGREEMENT_SECTION_TITLE, PROTOCOL_ODT_CHAPTER_TITLES)
        self.assertIn(COMMON_RULES_SECTION_TITLE, PROTOCOL_ODT_CHAPTER_TITLES)
        self.assertNotIn("Organizační opatření", PROTOCOL_ODT_CHAPTER_TITLES)

    def test_four_texts_persist_and_reload(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9a persist",
            meeting_date=date.today(),
        )
        updated = bozp_coordination_service.update_coordination(
            coordination.id,
            meeting_date=coordination.meeting_date,
            place=coordination.place,
            subject=coordination.subject,
            note=coordination.note or "",
            work_intent_information_text="Text záměru prací",
            ppe_text="Text OOPP",
            workplace_handover_text="Text předání",
            final_provisions_text="Text závěru",
        )
        assert updated is not None
        reloaded = bozp_coordination_service.get_by_id(coordination.id)
        assert reloaded is not None
        self.assertEqual(reloaded.work_intent_information_text, "Text záměru prací")
        self.assertEqual(reloaded.ppe_text, "Text OOPP")
        self.assertEqual(reloaded.workplace_handover_text, "Text předání")
        self.assertEqual(reloaded.final_provisions_text, "Text závěru")

        dialog = BozpCoordinationDialog(None, coordination=reloaded)
        tab = dialog.measures_tab
        self.assertEqual(
            tab.work_intent_information_text.toPlainText(),
            "Text záměru prací",
        )
        self.assertEqual(tab.ppe_text.toPlainText(), "Text OOPP")
        self.assertEqual(
            tab.workplace_handover_text.toPlainText(),
            "Text předání",
        )
        self.assertEqual(tab.final_provisions_text.toPlainText(), "Text závěru")
        dialog.close()

    def test_measures_table_still_works(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9a measures",
            meeting_date=date.today(),
        )
        _deactivate_template_measures(coordination.id)
        created = coordination_measure_service.add(
            coordination.id,
            title="Krátký název",
            description="Text opatření",
        )
        self.assertTrue(created.active)
        listed = coordination_measure_service.list_for_coordination(
            coordination.id,
            include_inactive=False,
        )
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].title, "Krátký název")

        dialog = BozpCoordinationDialog(None, coordination=coordination)
        self.assertFalse(dialog.measures_tab.table.isHidden())
        # Tabulka zobrazuje i neaktivní výchozí pravidla.
        self.assertGreaterEqual(dialog.measures_tab.table.rowCount(), 1)
        dialog.close()

    def test_empty_fixed_part_omitted_filled_printed(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9a empty",
            meeting_date=date.today(),
            work_intent_information_text="",
            ppe_text="Používat OOPP.",
            workplace_handover_text="",
            final_provisions_text="",
        )
        result = coordination_protocol_builder.build(coordination.id)
        titles = protocol_agreement_part_titles(result.protocol_data)
        self.assertNotIn(AGREEMENT_PART_WORK_INTENT, titles)
        self.assertIn(AGREEMENT_PART_PPE, titles)
        self.assertNotIn(AGREEMENT_PART_WORKPLACE_HANDOVER, titles)
        self.assertNotIn(AGREEMENT_PART_FINAL, titles)

        parts = build_coordination_agreement_parts(result.protocol_data)
        ppe = next(item for item in parts if item["title"] == AGREEMENT_PART_PPE)
        self.assertEqual(ppe["lines"], ["Používat OOPP."])

        target = _TMP / "empty-parts.odt"
        coordination_protocol_odt_renderer.render_from_result(target, result)
        content = _odt_content(target)
        self.assertIn(AGREEMENT_PART_PPE, content)
        self.assertIn("Používat OOPP.", content)
        self.assertNotIn(AGREEMENT_PART_WORK_INTENT, content)
        self.assertNotIn(AGREEMENT_PART_FINAL, content)

    def test_active_rules_as_bullets_inactive_hidden(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9a rules",
            meeting_date=date.today(),
        )
        _deactivate_template_measures(coordination.id)
        active = coordination_measure_service.add(
            coordination.id,
            title="Aktivní",
            description="Aktivní text",
        )
        inactive = coordination_measure_service.add(
            coordination.id,
            title="Neaktivní",
            description="Neaktivní text",
        )
        coordination_measure_service.deactivate(inactive.id)

        result = coordination_protocol_builder.build(coordination.id)
        bullets = flatten_protocol_measure_bullets(
            result.protocol_data["measures_by_category"]
        )
        self.assertEqual(bullets, ["• Aktivní text"])
        self.assertEqual(result.summary.active_measures, 1)
        self.assertIs(active.id, active.id)

        target = _TMP / "rules.odt"
        coordination_protocol_odt_renderer.render_from_result(target, result)
        content = _odt_content(target)
        self.assertIn(COMMON_RULES_SECTION_TITLE, content)
        self.assertIn("• Aktivní text", content)
        self.assertNotIn("Neaktivní text", content)

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
            if group.title() == COMMON_RULES_SECTION_TITLE:
                for label in group.findChildren(QLabel):
                    section_texts.append(label.text())
        joined = "\n".join(section_texts)
        self.assertIn("• Aktivní text", joined)
        self.assertNotIn("Neaktivní text", joined)
        dialog.close()

    def test_eight_parts_order_stable(self) -> None:
        self.assertEqual(len(AGREEMENT_FIXED_PART_ORDER), 8)
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9a order",
            meeting_date=date.today(),
            work_intent_information_text="Záměr",
            ppe_text="OOPP",
            workplace_handover_text="Předání",
            final_provisions_text="Závěr",
        )
        result = coordination_protocol_builder.build(coordination.id)
        data = result.protocol_data
        # Doplníme skládané části, aby všech 8 bylo přítomno.
        data = dict(data)
        data["coordinator"] = {
            "full_name": "Jan Koordinátor",
            "role": "koordinátor BOZP",
            "employer_name": "Hlavní firma s.r.o.",
            "phone": "",
            "email": "",
        }
        data["contacts"] = [
            {
                "custom_name": "Ohlašovna",
                "contact_type_label": "Mimořádná událost",
                "phone": "+420",
                "email": "",
            }
        ]
        data["emergency_procedures"] = {
            "emergency_reporting": "Hlásit",
            "accident_reporting": "",
            "fire_reporting": "",
            "evacuation_instructions": "",
        }
        data["risk_handovers"] = [
            {
                "employer": {"display_name": "Dodavatel"},
                "handover_status_label": "Předáno",
            }
        ]
        titles = protocol_agreement_part_titles(data)
        self.assertEqual(titles, list(AGREEMENT_FIXED_PART_ORDER))


if __name__ == "__main__":
    unittest.main()
