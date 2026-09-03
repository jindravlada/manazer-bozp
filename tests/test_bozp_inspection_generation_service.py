import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_OPERATION,
)
from moduly.proverky.modely.bozp_inspection import BozpInspection
from moduly.proverky.sluzby.bozp_inspection_generation_service import (
    BozpInspectionGenerationService,
)


def _operation(**fields):
    payload = {
        "id": 1,
        "name": "Provoz A",
        "item_type": WORKPLACE_ITEM_TYPE_OPERATION,
        "active": True,
        "preferred_months_json": "[3,4,5]",
    }
    payload.update(fields)
    return SimpleNamespace(**payload)


class BozpInspectionGenerationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = BozpInspectionGenerationService()

    def test_generate_skips_existing_operations(self) -> None:
        workplaces = [
            _operation(id=1, name="Provoz A", preferred_months_json="[3,4,5]"),
            _operation(id=2, name="Provoz B", preferred_months_json="[9,10,11]"),
        ]
        created_inspection = BozpInspection(
            id=10,
            year=2026,
            planned_month=4,
            workplace_id=2,
            workplace_name="Provoz B",
            title="Prověrka BOZP – Provoz B",
            number="1/2026",
        )

        with patch(
            "moduly.proverky.sluzby.bozp_inspection_generation_service.settings_service.get_workplaces",
            return_value=workplaces,
        ):
            with patch.object(
                self.service,
                "_operations_with_inspection_for_year",
                return_value={1},
            ):
                with patch.object(
                    self.service,
                    "_month_usage_for_year",
                    return_value={(2026, 3): 1},
                ):
                    with patch(
                        "moduly.proverky.sluzby.bozp_inspection_generation_service.bozp_inspection_service.create_inspection",
                        return_value=created_inspection,
                    ) as mock_create:
                        result = self.service.generate_for_year(2026)

        self.assertEqual(result.skipped_existing, 1)
        self.assertEqual(len(result.created), 1)
        self.assertEqual(result.created[0].workplace_id, 2)
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs["workplace_id"], 2)

    def test_generate_uses_balanced_months_for_multiple_operations(self) -> None:
        workplaces = [
            _operation(id=11, name="Provoz C", preferred_months_json="[3,4,5,9,10,11]"),
            _operation(id=12, name="Provoz D", preferred_months_json="[3,4,5,9,10,11]"),
        ]

        def _create(**fields):
            return BozpInspection(id=fields["workplace_id"], **fields)

        with patch(
            "moduly.proverky.sluzby.bozp_inspection_generation_service.settings_service.get_workplaces",
            return_value=workplaces,
        ):
            with patch.object(self.service, "_operations_with_inspection_for_year", return_value=set()):
                with patch.object(self.service, "_month_usage_for_year", return_value={}):
                    with patch(
                        "moduly.proverky.sluzby.bozp_inspection_generation_service.bozp_inspection_service.create_inspection",
                        side_effect=_create,
                    ):
                        result = self.service.generate_for_year(date.today().year)

        months = {inspection.planned_month for inspection in result.created}
        self.assertEqual(len(result.created), 2)
        self.assertEqual(len(months), 2)


if __name__ == "__main__":
    unittest.main()
