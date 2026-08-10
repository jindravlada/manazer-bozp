"""AUDIT-FIELD-OFFICE-2: Dokumentace / Terén v Auditech."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="audit-field-office-2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QLabel, QPushButton

    from core.shared.verification_type import (
        VERIFICATION_TYPE_DOCUMENTATION,
        VERIFICATION_TYPE_TERRAIN,
        normalize_verification_type,
    )
    from moduly.audity.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
        MOVE_TO_DOCUMENTATION_LABEL,
        MOVE_TO_TERRAIN_LABEL,
        TAB_DOCUMENTACE,
        TAB_TEREN,
    )
    from moduly.audity.repository.audit_verification_override_repository import (
        AuditVerificationOverrideRepository,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_verification_service import audit_verification_service
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.sluzby.inspection_verification_service import (
        inspection_verification_service,
    )


_PROCESS_ID = "urazy_mimo_udalosti"
_SECTION_ID = "evidence_hlaseni_urazu"


class AuditFieldOffice2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

        suffix = uuid.uuid4().hex[:6]
        self.leader_id = settings_service.save_worker(
            first_name="Jan", last_name=f"Novák-{suffix}"
        ).id
        self.workplace_rep_id = settings_service.save_worker(
            first_name="Eva", last_name=f"Králová-{suffix}"
        ).id
        self.union_id = person_service.create_person(
            first_name="Lucie", last_name=f"Horáková-{suffix}"
        ).id

    def _create_audit(self):
        audit = audit_service.create_audit(title="Test auditu FO-2")
        audit_commission_service.save_members(
            audit.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": self.leader_id,
                    "display_name": "Leader",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": self.workplace_rep_id,
                    "display_name": "Workplace",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": self.union_id,
                    "display_name": "Union",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        return audit

    def _criterion(self) -> dict:
        criterion = audit_knowledge_service.get_criterion(
            _PROCESS_ID,
            _SECTION_ID,
            ensure=False,
        )
        assert criterion is not None
        return criterion

    def _assertions(self) -> list[dict]:
        return audit_knowledge_service.get_audit_questions(self._criterion())

    def _titles(self, widget: AuditProcessesWidget) -> list[str]:
        host = widget.knowledge_widget.criterion_widget._content_host
        return [
            label.text()
            for label in host.findChildren(QLabel)
            if label.objectName() == "ControlPointTitle"
        ]

    def test_legacy_assertion_without_type_defaults_to_documentation(self) -> None:
        raw = {"id": "legacy", "text": "Legacy tvrzení", "aktivni": True, "poradi": 10}
        normalized = audit_knowledge_service.normalize_auditni_tvrzeni([raw])
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["verification_type"], VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(
            audit_knowledge_service.get_verification_type(raw),
            VERIFICATION_TYPE_DOCUMENTATION,
        )

    def test_methodology_documentation_and_terrain(self) -> None:
        docs = audit_knowledge_service.normalize_auditni_tvrzeni(
            [{"id": "a", "text": "A", "verification_type": "dokumentace"}]
        )
        terrain = audit_knowledge_service.normalize_auditni_tvrzeni(
            [{"id": "b", "text": "B", "verification_type": "teren"}]
        )
        self.assertEqual(docs[0]["verification_type"], VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(terrain[0]["verification_type"], VERIFICATION_TYPE_TERRAIN)

    def test_shared_normalize_used_by_proverky(self) -> None:
        self.assertEqual(
            normalize_verification_type("Terén"),
            VERIFICATION_TYPE_TERRAIN,
        )
        self.assertEqual(
            inspection_verification_service.normalize_verification_type("documentation"),
            VERIFICATION_TYPE_DOCUMENTATION,
        )
        self.assertEqual(
            audit_verification_service.normalize_verification_type("field"),
            VERIFICATION_TYPE_TERRAIN,
        )

    def test_filter_documentation_and_terrain_views(self) -> None:
        assertions = self._assertions()
        self.assertGreaterEqual(len(assertions), 2)
        first_id = str(assertions[0]["id"])
        second_id = str(assertions[1]["id"])

        # Dočasně nastav metodiku: první dokumentace, druhé terén (jen v paměti filtru).
        docs_item = dict(assertions[0], verification_type=VERIFICATION_TYPE_DOCUMENTATION)
        terrain_item = dict(assertions[1], verification_type=VERIFICATION_TYPE_TERRAIN)

        audit = self._create_audit()
        docs_filtered = audit_verification_service.filter_assertions(
            [docs_item, terrain_item],
            audit_id=audit.id,
            area_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
        )
        terrain_filtered = audit_verification_service.filter_assertions(
            [docs_item, terrain_item],
            audit_id=audit.id,
            area_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        self.assertEqual([item["id"] for item in docs_filtered], [first_id])
        self.assertEqual([item["id"] for item in terrain_filtered], [second_id])

    def test_override_moves_without_changing_methodology(self) -> None:
        assertions = self._assertions()
        item = dict(assertions[0], verification_type=VERIFICATION_TYPE_DOCUMENTATION)
        cp_id = str(item["id"])
        audit = self._create_audit()

        effective = audit_verification_service.set_override(
            audit.id,
            area_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            control_point_id=cp_id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
            item=item,
        )
        self.assertEqual(effective, VERIFICATION_TYPE_TERRAIN)
        self.assertEqual(
            audit_verification_service.effective_verification_type(
                audit.id,
                area_id=_PROCESS_ID,
                section_id=_SECTION_ID,
                control_point_id=cp_id,
                item=item,
            ),
            VERIFICATION_TYPE_TERRAIN,
        )
        self.assertEqual(
            audit_verification_service.methodology_verification_type(item),
            VERIFICATION_TYPE_DOCUMENTATION,
        )

        effective_back = audit_verification_service.set_override(
            audit.id,
            area_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            control_point_id=cp_id,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            item=item,
        )
        self.assertEqual(effective_back, VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(
            audit_verification_service.overrides_map(audit.id).get(
                (_PROCESS_ID, _SECTION_ID, cp_id)
            ),
            None,
        )

    def test_override_reload_and_no_duplicates(self) -> None:
        assertions = self._assertions()
        item = dict(assertions[0], verification_type=VERIFICATION_TYPE_DOCUMENTATION)
        cp_id = str(item["id"])
        audit = self._create_audit()
        repo = AuditVerificationOverrideRepository()

        audit_verification_service.set_override(
            audit.id,
            area_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            control_point_id=cp_id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
            item=item,
        )
        audit_verification_service.set_override(
            audit.id,
            area_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            control_point_id=cp_id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
            item=item,
        )
        rows = repo.list_for_audit(audit.id)
        matching = [
            row
            for row in rows
            if row.source_area_id == _PROCESS_ID
            and row.source_section_id == _SECTION_ID
            and row.source_control_point_id == cp_id
        ]
        self.assertEqual(len(matching), 1)

        reloaded = audit_verification_service.effective_verification_type(
            audit.id,
            area_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            control_point_id=cp_id,
            item=item,
        )
        self.assertEqual(reloaded, VERIFICATION_TYPE_TERRAIN)

    def test_dialog_tabs_and_move_refreshes_views(self) -> None:
        assertions = self._assertions()
        item = assertions[0]
        cp_id = str(item["id"])
        label = str(item.get("nazev") or item.get("text") or "")
        audit = self._create_audit()

        dialog = AuditDialog(audit=audit)
        dialog.show()
        QApplication.processEvents()
        self.assertEqual(dialog.tabs.tabText(2), TAB_DOCUMENTACE)
        self.assertEqual(dialog.tabs.tabText(3), TAB_TEREN)

        docs = dialog.processes_widget
        terrain = dialog.terrain_widget
        docs.set_audit_id(audit.id)
        terrain.set_audit_id(audit.id)
        docs.knowledge_tree.select_node(_PROCESS_ID, _SECTION_ID)
        terrain.knowledge_tree.select_node(_PROCESS_ID, _SECTION_ID)
        QApplication.processEvents()

        docs_criterion = docs.knowledge_widget.criterion_widget
        terrain_criterion = terrain.knowledge_widget.criterion_widget
        self.assertIsNotNone(docs_criterion._current_section)
        docs_ids = {
            str(row.get("id"))
            for row in docs_criterion._filtered_questions(docs_criterion._current_section)
        }
        terrain_ids = {
            str(row.get("id"))
            for row in terrain_criterion._filtered_questions(
                terrain_criterion._current_section
            )
        }
        self.assertIn(cp_id, docs_ids)
        self.assertNotIn(cp_id, terrain_ids)
        self.assertIn(label, self._titles(docs))

        audit_verification_service.set_override(
            audit.id,
            area_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            control_point_id=cp_id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
            item=item,
        )
        dialog._on_verification_type_changed()
        QApplication.processEvents()

        docs_ids = {
            str(row.get("id"))
            for row in docs_criterion._filtered_questions(docs_criterion._current_section)
        }
        terrain_ids = {
            str(row.get("id"))
            for row in terrain_criterion._filtered_questions(
                terrain_criterion._current_section
            )
        }
        self.assertNotIn(cp_id, docs_ids)
        self.assertIn(cp_id, terrain_ids)
        self.assertIn(label, self._titles(terrain))
        self.assertTrue(
            any(
                btn.text() == MOVE_TO_DOCUMENTATION_LABEL
                for btn in terrain_criterion._content_host.findChildren(QPushButton)
            )
        )
        dialog.close()

    def test_seed_missing_verification_type_filled_without_overwrite(self) -> None:
        user_section = {
            "id": "s1",
            "auditni_tvrzeni": [
                {"id": "a1", "text": "A", "verification_type": VERIFICATION_TYPE_TERRAIN},
                {"id": "a2", "text": "B"},
            ],
        }
        seed_section = {
            "id": "s1",
            "auditni_tvrzeni": [
                {"id": "a1", "text": "A", "verification_type": VERIFICATION_TYPE_DOCUMENTATION},
                {"id": "a2", "text": "B", "verification_type": VERIFICATION_TYPE_TERRAIN},
            ],
        }
        changed = audit_knowledge_service._merge_assertion_verification_type_from_seed(
            user_section,
            seed_section,
            full_sync=False,
        )
        self.assertTrue(changed)
        self.assertEqual(
            user_section["auditni_tvrzeni"][0]["verification_type"],
            VERIFICATION_TYPE_TERRAIN,
        )
        self.assertEqual(
            user_section["auditni_tvrzeni"][1]["verification_type"],
            VERIFICATION_TYPE_TERRAIN,
        )


if __name__ == "__main__":
    unittest.main()
