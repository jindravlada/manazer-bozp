import importlib
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        ENTITY_AUDITY,
        FINDING_TYPE_NESHODA,
        FINDING_STATUS_OTEVRENE,
    )
    from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from moduly.audity.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
        TAB_AUDITOVANE_PROCESY,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class AudityProcessesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

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

    def _create_audit_with_team(self):
        audit = audit_service.create_audit(title="Test auditu")
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

    def _question_context(self):
        process = audit_knowledge_service.get_process_by_id("planovani_bozp")
        assert process is not None
        criterion = audit_knowledge_service.get_criterion("planovani_bozp", "cile_politika")
        assert criterion is not None
        questions = audit_knowledge_service.get_audit_questions(criterion)
        assert questions
        question = questions[0]
        return ControlPointContext(
            area_id=process.id,
            area_label=process.nazev,
            section_id=criterion["id"],
            section_label=criterion["nazev"],
            control_point_id=question["id"],
            control_point_label=question["nazev"],
        )

    def test_dialog_has_processes_tab_third(self) -> None:
        from moduly.audity.ui.audit_dialog import AuditDialog

        audit = self._create_audit_with_team()
        dialog = AuditDialog(audit=audit)

        self.assertEqual(dialog.tabs.count(), 6)
        self.assertEqual(dialog.tabs.tabText(2), TAB_AUDITOVANE_PROCESY)
        self.assertEqual(dialog.tabs.tabText(3), "Zjištění")
        self.assertEqual(dialog.tabs.tabText(4), "Úkoly")
        self.assertEqual(dialog.tabs.tabText(5), "Závěr")

    def test_tree_shows_seed_process(self) -> None:
        from moduly.audity.ui.audit_knowledge_tree_widget import AuditKnowledgeTreeWidget

        tree = AuditKnowledgeTreeWidget()
        tree.reload_tree()

        labels = [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]
        self.assertIn("Řízení plánování systému BOZP", labels)

    def test_select_criterion_shows_question(self) -> None:
        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        audit = self._create_audit_with_team()
        widget = AuditProcessesWidget()
        widget.set_audit_id(audit.id)
        widget.knowledge_tree.select_node("planovani_bozp", "cile_politika")

        self.assertEqual(widget._current_process_id, "planovani_bozp")
        self.assertEqual(widget._current_criterion_id, "cile_politika")
        self.assertEqual(widget.content_stack.currentIndex(), widget._PAGE_KNOWLEDGE)

        criterion_widget = widget.knowledge_widget.criterion_widget
        self.assertIn("politika_promitnuti", criterion_widget._control_point_frames)

    def test_select_process_shows_guide_overview(self) -> None:
        from PySide6.QtWidgets import QLabel
        from moduly.audity.constants import (
            GUIDE_BLOCK_EVALUATE,
            GUIDE_BLOCK_UNDERSTAND,
            GUIDE_BLOCK_VERIFY,
        )
        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        widget = AuditProcessesWidget()
        widget.knowledge_tree.select_node("planovani_bozp")

        self.assertEqual(widget.content_stack.currentIndex(), widget._PAGE_OVERVIEW)
        overview_text = widget.overview_widget._content_host.findChildren(QLabel)
        texts = {label.text() for label in overview_text}
        self.assertIn(GUIDE_BLOCK_UNDERSTAND, texts)
        self.assertIn(GUIDE_BLOCK_VERIFY, texts)
        self.assertIn(GUIDE_BLOCK_EVALUATE, texts)

    def test_criterion_shows_guide_blocks_and_seed_content(self) -> None:
        from PySide6.QtWidgets import QLabel
        from moduly.audity.constants import (
            GUIDE_BLOCK_EVALUATE,
            GUIDE_BLOCK_UNDERSTAND,
            GUIDE_BLOCK_VERIFY,
            GUIDE_LABEL_OBJECTIVE_EVIDENCE,
            GUIDE_LABEL_TYPICAL_NONCONFORMITIES,
            GUIDE_LABEL_VERIFICATION_GOAL,
        )
        from moduly.audity.ui.audit_knowledge_criterion_widget import AuditKnowledgeCriterionWidget

        criterion = audit_knowledge_service.get_criterion("planovani_bozp", "cile_politika")
        assert criterion is not None

        widget = AuditKnowledgeCriterionWidget()
        widget.set_criterion(
            criterion,
            area_id="planovani_bozp",
            area_label="Řízení plánování systému BOZP",
            section_label="Politika, cíle a plánování",
        )

        labels = {label.text() for label in widget.findChildren(QLabel)}
        self.assertIn(GUIDE_BLOCK_UNDERSTAND, labels)
        self.assertIn(GUIDE_BLOCK_VERIFY, labels)
        self.assertIn(GUIDE_BLOCK_EVALUATE, labels)
        self.assertIn(GUIDE_LABEL_VERIFICATION_GOAL, labels)
        self.assertIn(GUIDE_LABEL_OBJECTIVE_EVIDENCE, labels)
        self.assertIn(GUIDE_LABEL_TYPICAL_NONCONFORMITIES, labels)
        self.assertIn(
            "Jak organizace zajišťuje, že politika BOZP a cíle BOZP jsou promítnuty do skutečného řízení práce?",
            labels,
        )

    def test_control_result_persists_after_reopen(self) -> None:
        audit = self._create_audit_with_team()
        context = self._question_context()

        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            context,
            result=CONTROL_RESULT_VYHOVUJE,
            note="Vyhovuje podle dokumentace",
        )

        reloaded = control_result_service.get_for_control_point(
            ENTITY_AUDITY,
            audit.id,
            context,
        )
        assert reloaded is not None
        self.assertEqual(reloaded.result, CONTROL_RESULT_VYHOVUJE)
        self.assertEqual(reloaded.note, "Vyhovuje podle dokumentace")
        self.assertEqual(reloaded.entity_type, ENTITY_AUDITY)

        current = control_result_service.current_result(ENTITY_AUDITY, audit.id, context)
        self.assertEqual(current, CONTROL_RESULT_VYHOVUJE)

    @patch("moduly.audity.ui.audit_knowledge_criterion_widget.FindingDialog")
    def test_create_finding_for_noncompliance(self, mock_dialog_cls) -> None:
        audit = self._create_audit_with_team()
        context = self._question_context()
        stable_key = audit_knowledge_service.question_stable_key(
            context.area_id,
            context.section_id,
            context.control_point_id,
        )

        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            context,
            result=CONTROL_RESULT_NEVYHOVUJE,
        )

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = True
        mock_dialog.get_data.return_value = {
            "finding_type": FINDING_TYPE_NESHODA,
            "reference_label": stable_key,
            "description": "Politika BOZP chybí.",
            "recommended_action": "Schválit politiku.",
            "responsible_person_id": None,
            "responsible_person_name": "",
            "due_date": None,
            "status": FINDING_STATUS_OTEVRENE,
            "resolution_note": "",
        }
        mock_dialog_cls.return_value = mock_dialog

        from moduly.audity.ui.audit_knowledge_criterion_widget import AuditKnowledgeCriterionWidget

        widget = AuditKnowledgeCriterionWidget()
        widget.set_audit_id(audit.id)
        criterion = audit_knowledge_service.get_criterion("planovani_bozp", "cile_politika")
        assert criterion is not None
        widget.set_criterion(
            criterion,
            area_id="planovani_bozp",
            area_label="Řízení plánování systému BOZP",
            section_label="Politika, cíle a plánování",
        )

        question = audit_knowledge_service.get_audit_questions(criterion)[0]
        widget._create_finding(question)

        findings = finding_service.get_for_entity(ENTITY_AUDITY, audit.id)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.entity_type, ENTITY_AUDITY)
        self.assertEqual(finding.entity_id, audit.id)
        self.assertEqual(finding.source_area_label, "Řízení plánování systému BOZP")
        self.assertEqual(finding.source_section_label, "Politika, cíle a plánování")
        self.assertEqual(finding.source_control_point_id, "politika_promitnuti")
        self.assertEqual(finding.reference_label, stable_key)

    @patch("moduly.audity.ui.audit_knowledge_criterion_widget.FindingDialog")
    def test_finding_from_question_appears_on_findings_tab(self, mock_dialog_cls) -> None:
        audit = self._create_audit_with_team()
        context = self._question_context()
        stable_key = audit_knowledge_service.question_stable_key(
            context.area_id,
            context.section_id,
            context.control_point_id,
        )

        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            context,
            result=CONTROL_RESULT_NEVYHOVUJE,
        )

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = True
        mock_dialog.get_data.return_value = {
            "finding_type": FINDING_TYPE_NESHODA,
            "reference_label": stable_key,
            "description": "Politika BOZP chybí.",
            "recommended_action": "Schválit politiku.",
            "responsible_person_id": None,
            "responsible_person_name": "",
            "due_date": None,
            "status": FINDING_STATUS_OTEVRENE,
            "resolution_note": "",
        }
        mock_dialog_cls.return_value = mock_dialog

        from moduly.audity.ui.audit_dialog import AuditDialog

        dialog = AuditDialog(audit=audit)
        criterion = audit_knowledge_service.get_criterion("planovani_bozp", "cile_politika")
        assert criterion is not None
        dialog.processes_widget.knowledge_widget.criterion_widget.set_criterion(
            criterion,
            area_id="planovani_bozp",
            area_label="Řízení plánování systému BOZP",
            section_label="Politika, cíle a plánování",
        )

        question = audit_knowledge_service.get_audit_questions(criterion)[0]
        dialog.processes_widget.knowledge_widget.criterion_widget._create_finding(question)

        dialog.findings_widget.refresh()
        self.assertEqual(dialog.findings_widget.table.rowCount(), 1)
        self.assertEqual(
            dialog.findings_widget.table.item(0, 7).text(),
            "Politika BOZP chybí.",
        )

    def test_finding_dialog_includes_audit_finding_type_labels(self) -> None:
        from core.shared.constants import (
            FINDING_TYPE_NESHODA,
            FINDING_TYPE_POZOROVANI,
            FINDING_TYPE_PRILEZITOST,
            FINDING_TYPE_ZJISTENI,
            VALID_FINDING_TYPES,
        )
        from core.shared.finding_display import FINDING_TYPE_LABELS, finding_type_label
        from core.widgets.finding_dialog import FindingDialog
        from moduly.audity.constants import (
            AUDIT_FINDING_TYPE_NESHODA,
            AUDIT_FINDING_TYPE_LABELS,
            AUDIT_FINDING_TYPES,
        )

        for finding_type in VALID_FINDING_TYPES:
            self.assertIn(finding_type, FINDING_TYPE_LABELS)

        for finding_type, label in AUDIT_FINDING_TYPE_LABELS.items():
            self.assertEqual(FINDING_TYPE_LABELS[finding_type], label)
            self.assertEqual(finding_type_label(finding_type), label)

        dialog = FindingDialog(
            title="Zjištění auditu",
            allowed_finding_types=AUDIT_FINDING_TYPES,
            default_finding_type=AUDIT_FINDING_TYPE_NESHODA,
        )
        combo_labels = {
            dialog.type_combo.itemText(index)
            for index in range(dialog.type_combo.count())
        }
        self.assertEqual(combo_labels, {"Neshoda", "PKZ", "Pozorování"})
        self.assertNotIn("Zjištění", combo_labels)
        self.assertEqual(dialog.type_combo.currentData(), FINDING_TYPE_NESHODA)
        self.assertEqual(dialog.type_combo.currentText(), "Neshoda")
        self.assertEqual(finding_type_label(FINDING_TYPE_NESHODA), "Neshoda")
        self.assertEqual(FINDING_TYPE_LABELS[FINDING_TYPE_PRILEZITOST], "PKZ")
        self.assertEqual(FINDING_TYPE_LABELS[FINDING_TYPE_POZOROVANI], "Pozorování")
        self.assertNotEqual(FINDING_TYPE_ZJISTENI, dialog.type_combo.currentData())


if __name__ == "__main__":
    unittest.main()
