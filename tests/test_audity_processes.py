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
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_AUDITY,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_PRILEZITOST,
        FINDING_STATUS_OTEVRENE,
    )
    from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from moduly.audity.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
        AUDIT_FINDING_TYPE_NESHODA,
        AUDIT_FINDING_TYPE_PKZ,
        FINDING_CREATE_FROM_CONTROL_POINT_LABEL,
        KNOWLEDGE_EDITOR_BUTTON_LABEL,
        TAB_DOCUMENTACE,
        TAB_TEREN,
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
        process = audit_knowledge_service.get_process_by_id("urazy_mimo_udalosti")
        assert process is not None
        criterion = audit_knowledge_service.get_criterion(
            "urazy_mimo_udalosti",
            "evidence_hlaseni_urazu",
        )
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

        self.assertEqual(dialog.tabs.count(), 8)
        self.assertEqual(dialog.tabs.tabText(2), TAB_DOCUMENTACE)
        self.assertEqual(dialog.tabs.tabText(3), TAB_TEREN)
        self.assertEqual(dialog.tabs.tabText(4), "Historie pracoviště")
        self.assertEqual(dialog.tabs.tabText(5), "Zjištění")
        self.assertEqual(dialog.tabs.tabText(6), "Úkoly")
        self.assertEqual(dialog.tabs.tabText(7), "Závěr")

    def test_tree_shows_seed_process(self) -> None:
        from moduly.audity.ui.audit_knowledge_tree_widget import AuditKnowledgeTreeWidget

        tree = AuditKnowledgeTreeWidget()
        tree.reload_tree()

        labels = [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]
        self.assertIn("Řízení pracovních úrazů a mimořádných událostí", labels)

    def test_select_criterion_shows_question(self) -> None:
        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        audit = self._create_audit_with_team()
        widget = AuditProcessesWidget()
        widget.set_audit_id(audit.id)
        widget.knowledge_tree.select_node("urazy_mimo_udalosti", "evidence_hlaseni_urazu")

        self.assertEqual(widget._current_process_id, "urazy_mimo_udalosti")
        self.assertEqual(widget._current_criterion_id, "evidence_hlaseni_urazu")
        self.assertEqual(widget.content_stack.currentIndex(), widget._PAGE_KNOWLEDGE)

        criterion_widget = widget.knowledge_widget.criterion_widget
        expected_ids = {
            "vsechny_urazy_evidovany",
            "urazy_klasifikovany",
            "ohlasovaci_povinnosti",
            "vedouci_znaji_postup",
            "uplnost_evidence_overovana",
        }
        self.assertTrue(expected_ids.issubset(criterion_widget._control_point_frames))

    def test_switching_criterion_resets_scroll_to_top(self) -> None:
        from moduly.audity.ui.audit_knowledge_criterion_widget import AuditKnowledgeCriterionWidget

        widget = AuditKnowledgeCriterionWidget()
        with patch.object(widget, "scroll_to_top") as mock_scroll:
            widget.set_criterion({"id": "sekce", "nazev": "Sekce"})
            mock_scroll.assert_called_once()

        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        processes = AuditProcessesWidget()
        with patch.object(
            processes.knowledge_widget.criterion_widget,
            "scroll_to_top",
        ) as mock_scroll:
            processes.knowledge_tree.select_node("urazy_mimo_udalosti", "evidence_hlaseni_urazu")
            mock_scroll.assert_called()

    def _finding_create_buttons(self, criterion_widget):
        from PySide6.QtWidgets import QPushButton

        return [
            button
            for button in criterion_widget.findChildren(QPushButton)
            if button.text() == FINDING_CREATE_FROM_CONTROL_POINT_LABEL
        ]

    def _open_criterion_with_result(self, audit, result: str, note: str = ""):
        context = ControlPointContext(
            area_id="urazy_mimo_udalosti",
            area_label="Řízení pracovních úrazů a mimořádných událostí",
            section_id="evidence_hlaseni_urazu",
            section_label="Evidence a hlášení pracovních úrazů",
            control_point_id="vsechny_urazy_evidovany",
            control_point_label="Všechny pracovní úrazy jsou evidovány.",
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            context,
            result=result,
            note=note,
        )

        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        widget = AuditProcessesWidget()
        widget.set_audit_id(audit.id)
        widget.knowledge_tree.select_node("urazy_mimo_udalosti", "evidence_hlaseni_urazu")
        return widget, context

    @patch("moduly.audity.ui.audit_knowledge_criterion_widget.FindingDialog")
    def test_recommendation_result_opens_finding_dialog_with_pkz_type(
        self, mock_finding_dialog
    ) -> None:
        audit = self._create_audit_with_team()
        widget, context = self._open_criterion_with_result(
            audit,
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            note="Doplnit evidence chybějících záznamů",
        )

        criterion_widget = widget.knowledge_widget.criterion_widget
        create_buttons = self._finding_create_buttons(criterion_widget)
        self.assertEqual(len(create_buttons), 1)

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 1
        mock_dialog.get_data.return_value = {
            "finding_type": FINDING_TYPE_PRILEZITOST,
            "reference_label": context.control_point_label,
            "description": "Doplnit evidence chybějících záznamů",
            "recommended_action": "Doplnit evidence chybějících záznamů",
            "responsible_person_id": None,
            "responsible_person_name": "",
            "due_date": None,
            "status": FINDING_STATUS_OTEVRENE,
            "resolution_note": "",
        }
        mock_finding_dialog.return_value = mock_dialog

        create_buttons[0].click()

        mock_finding_dialog.assert_called_once()
        _, kwargs = mock_finding_dialog.call_args
        self.assertEqual(kwargs["default_finding_type"], AUDIT_FINDING_TYPE_PKZ)
        mock_dialog.recommended_action_edit.setPlainText.assert_called_once_with(
            "Doplnit evidence chybějících záznamů"
        )

        finding = audit_service.finding_for_control_point(
            audit.id,
            process_label=context.area_label,
            criterion_label=context.section_label,
            question_id=context.control_point_id,
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.finding_type, FINDING_TYPE_PRILEZITOST)
        self.assertIsNone(finding.task_id)

    @patch("moduly.audity.ui.audit_knowledge_criterion_widget.FindingDialog")
    def test_noncompliance_result_opens_finding_dialog_with_neshoda_type(
        self, mock_finding_dialog
    ) -> None:
        audit = self._create_audit_with_team()
        widget, context = self._open_criterion_with_result(
            audit,
            CONTROL_RESULT_NEVYHOVUJE,
        )

        criterion_widget = widget.knowledge_widget.criterion_widget
        create_buttons = self._finding_create_buttons(criterion_widget)
        self.assertEqual(len(create_buttons), 1)

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 1
        mock_dialog.get_data.return_value = {
            "finding_type": FINDING_TYPE_NESHODA,
            "reference_label": context.control_point_label,
            "description": "Neshoda u kontrolního bodu",
            "recommended_action": "",
            "responsible_person_id": None,
            "responsible_person_name": "",
            "due_date": None,
            "status": FINDING_STATUS_OTEVRENE,
            "resolution_note": "",
        }
        mock_finding_dialog.return_value = mock_dialog

        create_buttons[0].click()

        mock_finding_dialog.assert_called_once()
        _, kwargs = mock_finding_dialog.call_args
        self.assertEqual(kwargs["default_finding_type"], AUDIT_FINDING_TYPE_NESHODA)

        finding = audit_service.finding_for_control_point(
            audit.id,
            process_label=context.area_label,
            criterion_label=context.section_label,
            question_id=context.control_point_id,
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.finding_type, FINDING_TYPE_NESHODA)

    def test_select_process_shows_guide_overview(self) -> None:
        from PySide6.QtWidgets import QLabel
        from moduly.audity.constants import (
            GUIDE_LABEL_AREAS,
            GUIDE_LABEL_UCEL,
            METHODOLOGY_PANEL_TITLE,
        )
        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        widget = AuditProcessesWidget()
        widget.knowledge_tree.select_node("urazy_mimo_udalosti")

        self.assertEqual(widget.content_stack.currentIndex(), widget._PAGE_OVERVIEW)
        tree_labels = {label.text() for label in widget.tree_panel.findChildren(QLabel)}
        self.assertNotIn(GUIDE_LABEL_UCEL, tree_labels)

        center_texts = {label.text() for label in widget.overview_widget.findChildren(QLabel)}
        self.assertIn(GUIDE_LABEL_UCEL, center_texts)
        self.assertIn(GUIDE_LABEL_AREAS, center_texts)

        right_texts = {label.text() for label in widget.methodology_panel.findChildren(QLabel)}
        self.assertIn(METHODOLOGY_PANEL_TITLE, right_texts)

    def test_planovani_process_shows_dual_standard_methodology(self) -> None:
        from PySide6.QtWidgets import QLabel
        from moduly.audity.constants import (
            GUIDE_LABEL_NORM_REQUIREMENTS,
            GUIDE_LABEL_OBJECTIVE_EVIDENCE,
            GUIDE_LABEL_RECOMMENDED_INTERVIEWS,
            PROCESS_TERM_QUESTION,
        )
        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        widget = AuditProcessesWidget()
        widget.knowledge_tree.select_node("planovani_bozp")

        right_texts = {label.text() for label in widget.methodology_panel.findChildren(QLabel)}
        self.assertIn(GUIDE_LABEL_NORM_REQUIREMENTS, right_texts)
        self.assertIn("ISO 9001", " ".join(right_texts))
        self.assertIn("ISO 45001", " ".join(right_texts))

        widget.knowledge_tree.select_node("planovani_bozp", "cile_politika")

        criterion_widget = widget.knowledge_widget.criterion_widget
        center_labels = {label.text() for label in criterion_widget.findChildren(QLabel)}
        self.assertIn(PROCESS_TERM_QUESTION, center_labels)
        self.assertIn(
            "Organizace stanovuje měřitelné cíle systému řízení.",
            center_labels,
        )
        self.assertIn("Při plánování jsou zohledněna rizika i příležitosti.", center_labels)

        right_labels = {label.text() for label in widget.methodology_panel.findChildren(QLabel)}
        self.assertIn(GUIDE_LABEL_OBJECTIVE_EVIDENCE, right_labels)
        self.assertIn(GUIDE_LABEL_RECOMMENDED_INTERVIEWS, right_labels)
        self.assertIn(GUIDE_LABEL_NORM_REQUIREMENTS, right_labels)
        self.assertIn("ISO 9001", " ".join(right_labels))
        self.assertIn("ISO 45001", " ".join(right_labels))

        expected_ids = {
            "meritelne_cile",
            "rizika_prilezitosti",
            "odpovednosti_zdroje",
            "vyhodnocovani_cilu",
            "rizeni_zmen_planovani",
            "prezkoumavani_vedenim",
            "politika_schvalena",
        }
        self.assertTrue(expected_ids.issubset(criterion_widget._control_point_frames))

    def test_planned_program_process_id_resolves_in_catalog(self) -> None:
        process = audit_knowledge_service.get_process_by_id("planovani_bozp")
        assert process is not None
        self.assertTrue(process.has_knowledge_file)
        knowledge = audit_knowledge_service.load_process_knowledge(process)
        assert knowledge is not None
        criterion = audit_knowledge_service.get_criterion("planovani_bozp", "cile_politika")
        assert criterion is not None
        self.assertGreaterEqual(len(audit_knowledge_service.get_audit_questions(criterion)), 6)

    def test_criterion_work_center_and_methodology_right(self) -> None:
        from PySide6.QtWidgets import QLabel
        from moduly.audity.constants import (
            GUIDE_LABEL_OBJECTIVE_EVIDENCE,
            GUIDE_LABEL_TYPICAL_NONCONFORMITIES,
            PROCESS_TERM_QUESTION,
        )
        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        widget = AuditProcessesWidget()
        widget.knowledge_tree.select_node("urazy_mimo_udalosti", "evidence_hlaseni_urazu")

        center_widget = widget.knowledge_widget.criterion_widget
        center_labels = {label.text() for label in center_widget.findChildren(QLabel)}
        self.assertIn(PROCESS_TERM_QUESTION, center_labels)
        self.assertNotIn(GUIDE_LABEL_OBJECTIVE_EVIDENCE, center_labels)
        self.assertNotIn(GUIDE_LABEL_TYPICAL_NONCONFORMITIES, center_labels)
        self.assertIn(
            "Všechny pracovní úrazy jsou evidovány.",
            center_labels,
        )

        right_labels = {label.text() for label in widget.methodology_panel.findChildren(QLabel)}
        self.assertIn(GUIDE_LABEL_OBJECTIVE_EVIDENCE, right_labels)
        self.assertIn(GUIDE_LABEL_TYPICAL_NONCONFORMITIES, right_labels)
        self.assertIn("Historie", right_labels)
        self.assertNotIn("Vyberte položku ve stromu vlevo.", right_labels)

    def test_methodology_panel_no_tree_hint_between_sections(self) -> None:
        from PySide6.QtWidgets import QLabel
        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        widget = AuditProcessesWidget()
        widget.knowledge_tree.select_node("urazy_mimo_udalosti", "evidence_hlaseni_urazu")

        labels = [label.text() for label in widget.methodology_panel.findChildren(QLabel)]
        self.assertNotIn("Vyberte položku ve stromu vlevo.", labels)

        section_titles = [
            "Doporučené rozhovory / role",
            "Možné pozorování v provozu",
        ]
        indices = [labels.index(title) for title in section_titles if title in labels]
        if len(indices) == 2:
            between = labels[indices[0] + 1 : indices[1]]
            self.assertNotIn("Vyberte položku ve stromu vlevo.", between)
            self.assertNotIn("Vyberte auditní tvrzení vlevo.", between)

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
            "description": "Pracovní úrazy nejsou řádně evidovány.",
            "recommended_action": "Zavést jednotný postup evidence.",
            "responsible_person_id": None,
            "responsible_person_name": "",
            "due_date": None,
            "status": FINDING_STATUS_OTEVRENE,
            "resolution_note": "",
        }
        mock_dialog_cls.return_value = mock_dialog

        from moduly.audity.ui.audit_knowledge_criterion_widget import AuditKnowledgeCriterionWidget
        from moduly.audity.ui.audit_methodology_panel_widget import AuditMethodologyPanelWidget

        methodology_panel = AuditMethodologyPanelWidget()
        widget = AuditKnowledgeCriterionWidget(methodology_panel=methodology_panel)
        widget.set_audit_id(audit.id)
        criterion = audit_knowledge_service.get_criterion(
            "urazy_mimo_udalosti",
            "evidence_hlaseni_urazu",
        )
        assert criterion is not None
        widget.set_criterion(
            criterion,
            area_id="urazy_mimo_udalosti",
            area_label="Řízení pracovních úrazů a mimořádných událostí",
            section_label="Evidence a hlášení pracovních úrazů",
        )

        question = audit_knowledge_service.get_audit_questions(criterion)[0]
        widget._create_finding(question)

        findings = finding_service.get_for_entity(ENTITY_AUDITY, audit.id)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.entity_type, ENTITY_AUDITY)
        self.assertEqual(finding.entity_id, audit.id)
        self.assertEqual(
            finding.source_area_label,
            "Řízení pracovních úrazů a mimořádných událostí",
        )
        self.assertEqual(finding.source_section_label, "Evidence a hlášení pracovních úrazů")
        self.assertEqual(finding.source_control_point_id, "vsechny_urazy_evidovany")
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
            "description": "Pracovní úrazy nejsou řádně evidovány.",
            "recommended_action": "Zavést jednotný postup evidence.",
            "responsible_person_id": None,
            "responsible_person_name": "",
            "due_date": None,
            "status": FINDING_STATUS_OTEVRENE,
            "resolution_note": "",
        }
        mock_dialog_cls.return_value = mock_dialog

        from moduly.audity.ui.audit_dialog import AuditDialog

        dialog = AuditDialog(audit=audit)
        criterion = audit_knowledge_service.get_criterion(
            "urazy_mimo_udalosti",
            "evidence_hlaseni_urazu",
        )
        assert criterion is not None
        dialog.processes_widget.knowledge_widget.criterion_widget.set_criterion(
            criterion,
            area_id="urazy_mimo_udalosti",
            area_label="Řízení pracovních úrazů a mimořádných událostí",
            section_label="Evidence a hlášení pracovních úrazů",
        )

        question = audit_knowledge_service.get_audit_questions(criterion)[0]
        dialog.processes_widget.knowledge_widget.criterion_widget._create_finding(question)

        dialog.findings_widget.refresh()
        self.assertEqual(dialog.findings_widget.table.rowCount(), 1)
        self.assertEqual(
            dialog.findings_widget.table.item(0, 7).text(),
            "Pracovní úrazy nejsou řádně evidovány.",
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
        self.assertEqual(
            combo_labels,
            {"Neshoda", "Příležitost ke zlepšování", "Pozorování"},
        )
        self.assertNotIn("Zjištění", combo_labels)
        self.assertEqual(dialog.type_combo.currentData(), FINDING_TYPE_NESHODA)
        self.assertEqual(dialog.type_combo.currentText(), "Neshoda")
        self.assertEqual(finding_type_label(FINDING_TYPE_NESHODA), "Neshoda")
        self.assertEqual(
            FINDING_TYPE_LABELS[FINDING_TYPE_PRILEZITOST],
            "Příležitost ke zlepšování",
        )
        self.assertEqual(FINDING_TYPE_LABELS[FINDING_TYPE_POZOROVANI], "Pozorování")
        self.assertNotEqual(FINDING_TYPE_ZJISTENI, dialog.type_combo.currentData())

    def test_processes_tab_has_knowledge_editor_button(self) -> None:
        from moduly.audity.ui.audit_dialog import AuditDialog
        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        audit = self._create_audit_with_team()
        dialog = AuditDialog(audit=audit)

        widget = dialog.processes_widget
        self.assertIsInstance(widget, AuditProcessesWidget)
        self.assertEqual(widget.edit_knowledge_btn.text(), KNOWLEDGE_EDITOR_BUTTON_LABEL)

    @patch("moduly.audity.ui.audit_processes_widget.exec_maximized", return_value=0)
    def test_knowledge_editor_button_opens_dialog(self, mock_exec) -> None:
        from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog
        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        widget = AuditProcessesWidget()
        widget.edit_knowledge_btn.click()

        mock_exec.assert_called_once()
        dialog = mock_exec.call_args.args[0]
        self.assertIsInstance(dialog, AudityKnowledgeEditorDialog)

    @patch("moduly.audity.ui.audit_processes_widget.exec_maximized", return_value=0)
    def test_knowledge_editor_button_passes_current_context(self, mock_exec) -> None:
        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        widget = AuditProcessesWidget()
        widget.knowledge_tree.select_node("urazy_mimo_udalosti", "evidence_hlaseni_urazu")
        widget.edit_knowledge_btn.click()

        dialog = mock_exec.call_args.args[0]
        self.assertEqual(dialog._initial_process_id, "urazy_mimo_udalosti")
        self.assertEqual(dialog._initial_criterion_id, "evidence_hlaseni_urazu")

    @patch("moduly.audity.ui.audit_processes_widget.exec_maximized", return_value=0)
    def test_knowledge_editor_refresh_preserves_control_results(self, mock_exec) -> None:
        from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

        audit = self._create_audit_with_team()
        context = self._question_context()
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            context,
            result=CONTROL_RESULT_VYHOVUJE,
            note="Zachovat po editoru",
        )

        widget = AuditProcessesWidget()
        widget.set_audit_id(audit.id)
        widget.knowledge_tree.select_node("urazy_mimo_udalosti", "evidence_hlaseni_urazu")
        widget._open_knowledge_editor()

        mock_exec.assert_called_once()
        self.assertEqual(
            control_result_service.current_result(ENTITY_AUDITY, audit.id, context),
            CONTROL_RESULT_VYHOVUJE,
        )
        reloaded = control_result_service.get_for_control_point(
            ENTITY_AUDITY,
            audit.id,
            context,
        )
        assert reloaded is not None
        self.assertEqual(reloaded.note, "Zachovat po editoru")
        self.assertEqual(widget._current_criterion_id, "evidence_hlaseni_urazu")

    def test_dialog_filters_processes_from_program_visit_links(self) -> None:
        from datetime import date

        from moduly.audity.constants import DEFAULT_AUDIT_PROGRAM_STANDARDS
        from moduly.audity.sluzby.audit_program_service import audit_program_service
        from moduly.audity.ui.audit_dialog import AuditDialog

        from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service

        audit_knowledge_service.ensure_catalogs()
        process_ids = [process.id for process in audit_knowledge_service.get_processes()[:2]]
        self.assertEqual(len(process_ids), 2)

        workplace = settings_service.save_workplace(name="Filtr provoz")
        program = audit_program_service.create_program(
            name="Program filtrace",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            audit_interval_months=6,
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=workplace.id,
            planned_year=2026,
            planned_month=4,
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id=process_ids[0],
            process_name="Proces 1",
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id=process_ids[1],
            process_name="Proces 2",
        )
        audit = audit_program_service.create_audit_from_visit(visit.id)

        dialog = AuditDialog(audit=audit)

        self.assertEqual(
            dialog.processes_widget._planned_process_ids,
            set(process_ids),
        )
        self.assertEqual(dialog.processes_widget.knowledge_tree.topLevelItemCount(), 2)


if __name__ == "__main__":
    unittest.main()
