"""PROVERKY-DIALOG-DEFER-1: Neukládat nezapisuje změny v editoru prověrky."""

from __future__ import annotations

import importlib
import os
import unittest
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(__file__).resolve().parents[1] / ".test-tmp" / "proverky-defer-1"
_TMP.mkdir(parents=True, exist_ok=True)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.shared.constants import (
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.modely.finding import Finding
    from core.shared.sluzby.finding_service import finding_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.proverky.modely.bozp_inspection import BozpInspection
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog


def _read_finding_description(finding_id: int) -> str:
    with get_session() as session:
        row = session.get(Finding, finding_id)
        assert row is not None
        value = row.description or ""
        session.expunge(row)
        return value


def _read_silne(inspection_id: int) -> str:
    with get_session() as session:
        row = session.get(BozpInspection, inspection_id)
        assert row is not None
        value = row.silne_stranky or ""
        session.expunge(row)
        return value


class ProverkyDialogDefer1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)
        suffix = uuid.uuid4().hex[:6]
        self.leader_id = settings_service.save_worker(
            first_name="Jan", last_name=f"L-{suffix}"
        ).id
        self.workplace_rep_id = settings_service.save_worker(
            first_name="Eva", last_name=f"W-{suffix}"
        ).id
        self.union_id = person_service.create_person(
            first_name="Lucie", last_name=f"U-{suffix}"
        ).id

    def _create_inspection(self, *, silne: str = "OK") -> BozpInspection:
        inspection = bozp_inspection_service.create_inspection(
            inspection_date=date(2026, 1, 1),
            silne_stranky=silne,
        )
        bozp_inspection_commission_service.save_members(
            inspection.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": self.leader_id,
                    "display_name": "L",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": self.workplace_rep_id,
                    "display_name": "W",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": self.union_id,
                    "display_name": "U",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        reloaded = bozp_inspection_service.get_by_id(inspection.id)
        assert reloaded is not None
        return reloaded

    def _fill_commission(self, dialog: BozpInspectionDialog) -> None:
        dialog.commission_widget.leader_selector.set_person_id(self.leader_id)
        dialog.commission_widget.workplace_selector.set_person_id(self.workplace_rep_id)
        dialog.commission_widget.union_selector.set_person_id(self.union_id)

    def test_finding_discard_keeps_original(self) -> None:
        original = "PŮVODNÍ POPIS"
        inspection = self._create_inspection()
        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description=original,
            status=FINDING_STATUS_OTEVRENE,
        )
        dialog = BozpInspectionDialog(inspection=inspection)
        self._fill_commission(dialog)
        dialog._capture_baseline()

        fake = SimpleNamespace(
            exec=lambda: True,
            get_data=lambda: {
                "finding_type": FINDING_TYPE_ZJISTENI,
                "reference_label": "",
                "description": "ZMĚNĚNÝ POPIS",
                "recommended_action": "",
                "responsible_person_id": None,
                "responsible_person_name": "",
                "due_date": None,
                "status": FINDING_STATUS_OTEVRENE,
                "resolution_note": "",
            },
        )
        with patch(
            "moduly.proverky.ui.bozp_inspection_findings_widget.FindingDialog",
            return_value=fake,
        ):
            dialog.findings_widget.table.selectRow(0)
            dialog.findings_widget.edit_finding()

        self.assertTrue(dialog._is_dirty())
        self.assertEqual(_read_finding_description(finding.id), original)

        with patch(
            "moduly.proverky.ui.bozp_inspection_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            with patch.object(
                finding_service, "update", wraps=finding_service.update
            ) as spy:
                dialog._request_close()
                spy.assert_not_called()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertEqual(_read_finding_description(finding.id), original)

    def test_save_writes_finding_and_conclusion(self) -> None:
        inspection = self._create_inspection(silne="PŘED")
        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="PŘED",
            status=FINDING_STATUS_OTEVRENE,
        )
        dialog = BozpInspectionDialog(inspection=inspection)
        self._fill_commission(dialog)
        dialog._capture_baseline()
        dialog.conclusion_widget.silne_stranky_edit.setPlainText("PO ULOŽENÍ")
        dialog._deferred.stage_finding_update(
            finding.id,
            {
                "finding_type": FINDING_TYPE_ZJISTENI,
                "reference_label": "",
                "description": "PO ULOŽENÍ",
                "recommended_action": "",
                "responsible_person_id": None,
                "responsible_person_name": "",
                "due_date": None,
                "status": FINDING_STATUS_OTEVRENE,
                "resolution_note": "",
            },
        )
        self.assertTrue(dialog._persist())
        self.assertEqual(_read_silne(inspection.id), "PO ULOŽENÍ")
        self.assertEqual(_read_finding_description(finding.id), "PO ULOŽENÍ")


if __name__ == "__main__":
    unittest.main()
