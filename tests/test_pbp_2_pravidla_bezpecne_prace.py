"""PBP-2: sběr platných pravidel z Registru rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="pbp-2-"))
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
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
        hazard_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
        hazard_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        PravidloBezpecnePrace,
        pravidla_bezpecne_prace_service,
    )
    from moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog import (
        PravidlaBezpecnePraceDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class PravidlaBezpecnePracePhasePbp2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.group_a = ensure_exposed_group("PBP2 skupina A")
        self.group_b = ensure_exposed_group("PBP2 skupina B")
        self.person = person_service.create_person(first_name="PBP", last_name="Tester")

        self.operation = settings_service.save_workplace(
            name="PBP2 provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="PBP2 pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.part = settings_service.save_workplace(
            name="PBP2 část",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )
        self.other_workplace = settings_service.save_workplace(
            name="PBP2 jiné pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )

    def _create_chain(
        self,
        *,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        group_id: int,
        event_name: str,
        existing: list[str] | None = None,
        required: list[str] | None = None,
        existing_inactive: list[str] | None = None,
    ):
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
            responsible_person_id=self.person.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name=f"Položka {event_name}",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name=event_name,
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_id=group_id,
            severity=RISK_SEVERITY_MODERATE,
        )
        measures = []
        for description in existing or []:
            measures.append(
                hazard_existing_measure_service.create_measure(
                    hazard_identification_id=identification.id,
                    hazard_risk_assessment_id=assessment.id,
                    description=description,
                )
            )
        for description in existing_inactive or []:
            measure = hazard_existing_measure_service.create_measure(
                hazard_identification_id=identification.id,
                hazard_risk_assessment_id=assessment.id,
                description=description,
            )
            hazard_existing_measure_service.deactivate_measure(measure.id)
        for description in required or []:
            hazard_required_measure_service.create_measure(
                hazard_identification_id=identification.id,
                hazard_risk_assessment_id=assessment.id,
                description=description,
            )
        return identification, assessment, measures

    def test_only_valid_existing_measures(self) -> None:
        self._create_chain(
            workplace_id=self.workplace.id,
            group_id=self.group_a.id,
            event_name="Událost platná",
            existing=["Používej ochranné brýle"],
            required=["Navržená zábrana"],
            existing_inactive=["Zrušené opatření"],
        )

        result = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

        self.assertEqual([item.text for item in result], ["Používej ochranné brýle"])
        self.assertIsInstance(result[0], PravidloBezpecnePrace)
        self.assertIsInstance(result[0].measure_id, int)

    def test_filter_by_endangered_group(self) -> None:
        self._create_chain(
            workplace_id=self.workplace.id,
            group_id=self.group_a.id,
            event_name="Pro A",
            existing=["Pravidlo skupiny A"],
        )
        self._create_chain(
            workplace_id=self.workplace.id,
            group_id=self.group_b.id,
            event_name="Pro B",
            existing=["Pravidlo skupiny B"],
        )

        result = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

        self.assertEqual([item.text for item in result], ["Pravidlo skupiny A"])

    def test_scope_operation_workplace_and_part(self) -> None:
        self._create_chain(
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
            group_id=self.group_a.id,
            event_name="Část",
            existing=["Pravidlo z části"],
        )
        self._create_chain(
            workplace_id=self.workplace.id,
            group_id=self.group_a.id,
            event_name="Pracoviště",
            existing=["Pravidlo z pracoviště"],
        )
        self._create_chain(
            workplace_id=self.other_workplace.id,
            group_id=self.group_a.id,
            event_name="Jiné",
            existing=["Pravidlo z jiného pracoviště"],
        )

        only_part = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
        )
        self.assertEqual([item.text for item in only_part], ["Pravidlo z části"])

        workplace_scope = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual(
            [item.text for item in workplace_scope],
            ["Pravidlo z části", "Pravidlo z pracoviště"],
        )

        operation_scope = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
        )
        self.assertEqual(
            [item.text for item in operation_scope],
            [
                "Pravidlo z části",
                "Pravidlo z jiného pracoviště",
                "Pravidlo z pracoviště",
            ],
        )

    def test_dedupe_preserves_first_wording(self) -> None:
        # Unikátnost popisu platí v rámci jednoho posouzení — duplicity napříč identifikacemi.
        self._create_chain(
            workplace_id=self.workplace.id,
            group_id=self.group_a.id,
            event_name="Duplikát 1",
            existing=["  Používej   helmu  "],
        )
        self._create_chain(
            workplace_id=self.workplace.id,
            group_id=self.group_a.id,
            event_name="Duplikát 2",
            existing=["používej helmu"],
        )
        self._create_chain(
            workplace_id=self.workplace.id,
            group_id=self.group_a.id,
            event_name="Duplikát 3",
            existing=["POUŽÍVEJ HELMU", "Jiná ochrana"],
        )

        result = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

        texts = [item.text for item in result]
        self.assertEqual(len(texts), 2)
        self.assertIn("Jiná ochrana", texts)
        helm_variants = [t for t in texts if "helmu" in t.casefold()]
        self.assertEqual(len(helm_variants), 1)
        self.assertEqual(helm_variants[0], "Používej   helmu")

    def test_stable_case_insensitive_sort(self) -> None:
        self._create_chain(
            workplace_id=self.workplace.id,
            group_id=self.group_a.id,
            event_name="Řazení",
            existing=["červená helma", "Bílá helma", "alfabeticky první"],
        )

        result = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

        texts = [item.text for item in result]
        self.assertEqual(
            texts,
            sorted(texts, key=lambda value: value.casefold()),
        )
        self.assertEqual(texts[0].casefold(), "alfabeticky první")

    def test_empty_result(self) -> None:
        result = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual(result, [])

    def test_dialog_shows_count_and_empty_info(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        dialog.endangered_group.set_group_id(self.group_a.id)
        dialog.operation.setCurrentIndex(dialog.operation.findData(self.operation.id))

        with (
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.pravidla_bezpecne_prace_service.generate",
                return_value=[],
            ),
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.QMessageBox.information"
            ) as info,
        ):
            dialog._generate()
            info.assert_called_once()
            self.assertIn("žádná platná", info.call_args.args[2])

        sample = [PravidloBezpecnePrace(text="Pravidlo", measure_id=1)]
        with (
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.pravidla_bezpecne_prace_service.generate",
                return_value=sample,
            ),
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.QMessageBox.information"
            ) as info,
        ):
            accepted = dialog._generate()
            info.assert_called_once()
            self.assertIn("Nalezeno pravidel: 1", info.call_args.args[2])
            self.assertEqual(dialog.last_result, sample)


if __name__ == "__main__":
    unittest.main()
