from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns
from moduly.rizeni_rizik.constants import format_event_display_name
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_CONTENT_INTRO_TEXT,
    HAZARD_LIBRARY_CONTENT_READ_ONLY_MESSAGE,
    HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
    HAZARD_LIBRARY_LEGAL_LINK_DIALOG_TITLE,
    HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ACTIVE,
    HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ID,
    HAZARD_LIBRARY_TEMPLATE_EVENT_COL_NAME,
    HAZARD_LIBRARY_TEMPLATE_EVENT_COLUMN_COUNT,
    HAZARD_LIBRARY_TEMPLATE_EVENT_TABLE_HEADERS,
    HAZARD_LIBRARY_TEMPLATE_EVENTS_SECTION_TITLE,
    HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ACTIVE,
    HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ID,
    HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_NOTE,
    HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_REQUIREMENT,
    HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COLUMN_COUNT,
    HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_TABLE_HEADERS,
    HAZARD_LIBRARY_TEMPLATE_LEGAL_LINKS_SECTION_TITLE,
    HAZARD_LIBRARY_TEMPLATE_SELECT_EVENT,
    HAZARD_LIBRARY_TEMPLATE_SELECT_LEGAL_LINK,
)
from moduly.pravni_pozadavky.constants import (
    legal_document_catalog_link_label,
    legal_requirement_merged_target_label,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.rizeni_rizik.sluzby.hazard_library_template_legal_link_service import (
    HazardLibraryTemplateLegalLinkError,
    hazard_library_template_legal_link_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    HazardLibraryTemplateEventError,
    hazard_library_template_event_service,
)
from moduly.rizeni_rizik.ui.hazard_library_template_assessments_dialog import (
    HazardLibraryTemplateAssessmentsDialog,
)
from moduly.rizeni_rizik.ui.hazard_library_template_event_dialog import (
    HazardLibraryTemplateEventDialog,
)
from moduly.rizeni_rizik.ui.hazard_library_template_legal_link_dialog import (
    HazardLibraryTemplateLegalLinkDialog,
)


class HazardLibraryTemplateContentWidget(QWidget):
    content_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._template_id: int | None = None
        self._read_only = False
        self._selected_event_id: int | None = None
        self._selected_legal_link_id: int | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(HAZARD_LIBRARY_CONTENT_INTRO_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(QLabel(HAZARD_LIBRARY_TEMPLATE_EVENTS_SECTION_TITLE))

        self.toolbar = QHBoxLayout()
        self.add_event_btn = QPushButton("Přidat událost")
        self.edit_event_btn = QPushButton("Upravit")
        self.assessments_btn = QPushButton("Posouzení a opatření")
        self.activate_event_btn = QPushButton("Aktivovat")
        self.deactivate_event_btn = QPushButton("Deaktivovat")
        self.toolbar.addWidget(self.add_event_btn)
        self.toolbar.addWidget(self.edit_event_btn)
        self.toolbar.addWidget(self.assessments_btn)
        self.toolbar.addWidget(self.activate_event_btn)
        self.toolbar.addWidget(self.deactivate_event_btn)
        self.toolbar.addStretch()
        layout.addLayout(self.toolbar)

        self.events_table = QTableWidget()
        self.events_table.setColumnCount(HAZARD_LIBRARY_TEMPLATE_EVENT_COLUMN_COUNT)
        self.events_table.setHorizontalHeaderLabels(HAZARD_LIBRARY_TEMPLATE_EVENT_TABLE_HEADERS)
        self.events_table.setColumnHidden(HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ID, True)
        self.events_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.events_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.events_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.events_table.setAlternatingRowColors(True)
        configure_table_columns(self.events_table, "hazard_library_template_events")
        layout.addWidget(self.events_table, 1)

        layout.addWidget(QLabel(HAZARD_LIBRARY_TEMPLATE_LEGAL_LINKS_SECTION_TITLE))
        legal_toolbar = QHBoxLayout()
        self.add_legal_link_btn = QPushButton("Přidat")
        self.edit_legal_link_btn = QPushButton("Upravit")
        self.activate_legal_link_btn = QPushButton("Aktivovat")
        self.deactivate_legal_link_btn = QPushButton("Deaktivovat")
        legal_toolbar.addWidget(self.add_legal_link_btn)
        legal_toolbar.addWidget(self.edit_legal_link_btn)
        legal_toolbar.addWidget(self.activate_legal_link_btn)
        legal_toolbar.addWidget(self.deactivate_legal_link_btn)
        legal_toolbar.addStretch()
        layout.addLayout(legal_toolbar)

        self.legal_links_table = QTableWidget()
        self.legal_links_table.setColumnCount(HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COLUMN_COUNT)
        self.legal_links_table.setHorizontalHeaderLabels(
            HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_TABLE_HEADERS,
        )
        self.legal_links_table.setColumnHidden(HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ID, True)
        self.legal_links_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.legal_links_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.legal_links_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.legal_links_table.setAlternatingRowColors(True)
        configure_table_columns(self.legal_links_table, "hazard_library_template_legal_links")
        layout.addWidget(self.legal_links_table)

        self.add_event_btn.clicked.connect(self.add_event)
        self.edit_event_btn.clicked.connect(self.edit_selected_event)
        self.assessments_btn.clicked.connect(self.open_assessments_for_selected_event)
        self.activate_event_btn.clicked.connect(self.activate_selected_event)
        self.deactivate_event_btn.clicked.connect(self.deactivate_selected_event)
        self.events_table.itemSelectionChanged.connect(self._on_event_selection_changed)
        self.events_table.doubleClicked.connect(self.edit_selected_event)
        self.add_legal_link_btn.clicked.connect(self.add_legal_link)
        self.edit_legal_link_btn.clicked.connect(self.edit_selected_legal_link)
        self.activate_legal_link_btn.clicked.connect(self.activate_selected_legal_link)
        self.deactivate_legal_link_btn.clicked.connect(self.deactivate_selected_legal_link)
        self.legal_links_table.itemSelectionChanged.connect(self._on_legal_link_selection_changed)
        self.legal_links_table.doubleClicked.connect(self.edit_selected_legal_link)

        self.set_template(None, read_only=False)

    def set_template(
        self,
        template_id: int | None,
        *,
        read_only: bool,
    ) -> None:
        self._template_id = template_id
        self._read_only = read_only
        self._selected_event_id = None
        self._selected_legal_link_id = None
        self._update_actions_enabled()
        self.refresh()

    def refresh(self) -> None:
        self._load_events_table()
        self._load_legal_links_table()

    def add_legal_link(self) -> None:
        if not self._ensure_editable():
            return
        dialog = HazardLibraryTemplateLegalLinkDialog(
            self,
            template_id=self._template_id,
        )
        if dialog.exec():
            self._notify_content_changed()
            self.refresh()

    def edit_selected_legal_link(self) -> None:
        link = self._selected_legal_link()
        if link is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_LEGAL_LINK_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_LEGAL_LINK,
            )
            return
        dialog = HazardLibraryTemplateLegalLinkDialog(
            self,
            template_id=self._template_id,
            link=link,
            read_only=self._read_only,
        )
        if dialog.exec():
            self._notify_content_changed()
            self.refresh()

    def activate_selected_legal_link(self) -> None:
        if not self._ensure_editable():
            return
        link = self._selected_legal_link()
        if link is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_LEGAL_LINK_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_LEGAL_LINK,
            )
            return
        if link.active:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_LEGAL_LINK_DIALOG_TITLE,
                "Právní vazba je již aktivní.",
            )
            return
        try:
            hazard_library_template_legal_link_service.activate_link(link.id)
        except HazardLibraryTemplateLegalLinkError as error:
            QMessageBox.warning(self, HAZARD_LIBRARY_LEGAL_LINK_DIALOG_TITLE, str(error))
            return
        self._notify_content_changed()
        self.refresh()

    def deactivate_selected_legal_link(self) -> None:
        if not self._ensure_editable():
            return
        link = self._selected_legal_link()
        if link is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_LEGAL_LINK_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_LEGAL_LINK,
            )
            return
        if not link.active:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_LEGAL_LINK_DIALOG_TITLE,
                "Právní vazba je již neaktivní.",
            )
            return
        hazard_library_template_legal_link_service.deactivate_link(link.id)
        self._notify_content_changed()
        self.refresh()

    def add_event(self) -> None:
        if not self._ensure_editable():
            return
        dialog = HazardLibraryTemplateEventDialog(
            self,
            template_id=self._template_id,
        )
        if dialog.exec():
            self._notify_content_changed()
            self.refresh()

    def edit_selected_event(self) -> None:
        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_EVENT,
            )
            return
        dialog = HazardLibraryTemplateEventDialog(
            self,
            template_id=self._template_id,
            event=event,
            read_only=self._read_only,
        )
        if dialog.exec():
            self._notify_content_changed()
            self.refresh()

    def open_assessments_for_selected_event(self) -> None:
        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_EVENT,
            )
            return
        dialog = HazardLibraryTemplateAssessmentsDialog(
            self,
            template_id=self._template_id,
            template_event_id=event.id,
            event_name=event.name,
            read_only=self._read_only,
            on_content_changed=self._notify_content_changed,
        )
        dialog.exec()
        self.refresh()

    def activate_selected_event(self) -> None:
        if not self._ensure_editable():
            return
        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_EVENT,
            )
            return
        if event.active:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                "Nežádoucí událost je již aktivní.",
            )
            return
        try:
            hazard_library_template_event_service.activate_event(event.id)
        except HazardLibraryTemplateEventError as error:
            QMessageBox.warning(self, HAZARD_LIBRARY_EVENT_DIALOG_TITLE, str(error))
            return
        self._notify_content_changed()
        self.refresh()

    def deactivate_selected_event(self) -> None:
        if not self._ensure_editable():
            return
        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_EVENT,
            )
            return
        if not event.active:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                "Nežádoucí událost je již neaktivní.",
            )
            return
        hazard_library_template_event_service.deactivate_event(event.id)
        self._notify_content_changed()
        self.refresh()

    def _notify_content_changed(self) -> None:
        self.content_changed.emit()

    def _ensure_editable(self) -> bool:
        if self._template_id is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                "Nejprve uložte základní údaje zdroje rizika.",
            )
            return False
        if self._read_only:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                HAZARD_LIBRARY_CONTENT_READ_ONLY_MESSAGE,
            )
            return False
        return True

    def _set_event_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self.add_event_btn,
            self.edit_event_btn,
            self.assessments_btn,
            self.activate_event_btn,
            self.deactivate_event_btn,
        ):
            button.setEnabled(enabled)

    def _load_events_table(self) -> None:
        self.events_table.blockSignals(True)
        self.events_table.setRowCount(0)

        if self._template_id is None:
            self.events_table.blockSignals(False)
            self._update_actions_enabled()
            return

        assessment_counts = hazard_library_template_assessment_service.count_active_by_events(
            self._template_id
        )
        events = hazard_library_template_event_service.get_for_template(
            self._template_id,
            include_inactive=True,
        )
        self.events_table.setRowCount(len(events))
        selected_row = -1
        for row_index, event in enumerate(events):
            self.events_table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ID,
                QTableWidgetItem(str(event.id)),
            )
            display_name = format_event_display_name(
                event.name,
                assessment_count=assessment_counts.get(event.id, 0),
            )
            self.events_table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_EVENT_COL_NAME,
                QTableWidgetItem(display_name),
            )
            self.events_table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ACTIVE,
                QTableWidgetItem("Ano" if event.active else "Ne"),
            )
            if self._selected_event_id == event.id:
                selected_row = row_index

        configure_table_columns(self.events_table, "hazard_library_template_events")
        if selected_row >= 0:
            self.events_table.selectRow(selected_row)
        else:
            self._selected_event_id = None
        self.events_table.blockSignals(False)
        self._update_actions_enabled()

    def _update_actions_enabled(self) -> None:
        has_template = self._template_id is not None
        has_event = self._selected_event_id is not None
        editable = not self._read_only and has_template

        if self._read_only:
            self.add_event_btn.setEnabled(False)
            self.edit_event_btn.setEnabled(has_template and has_event)
            self.activate_event_btn.setEnabled(False)
            self.deactivate_event_btn.setEnabled(False)
            self.assessments_btn.setEnabled(has_template and has_event)
            return

        self.add_event_btn.setEnabled(editable)
        self.edit_event_btn.setEnabled(has_template and has_event)
        self.activate_event_btn.setEnabled(editable and has_event)
        self.deactivate_event_btn.setEnabled(editable and has_event)
        self.assessments_btn.setEnabled(has_template and has_event)

        has_legal_link = self._selected_legal_link_id is not None
        if self._read_only:
            self.add_legal_link_btn.setEnabled(False)
            self.edit_legal_link_btn.setEnabled(has_template and has_legal_link)
            self.activate_legal_link_btn.setEnabled(False)
            self.deactivate_legal_link_btn.setEnabled(False)
            return

        self.add_legal_link_btn.setEnabled(editable)
        self.edit_legal_link_btn.setEnabled(has_template and has_legal_link)
        self.activate_legal_link_btn.setEnabled(editable and has_legal_link)
        self.deactivate_legal_link_btn.setEnabled(editable and has_legal_link)

    def _on_event_selection_changed(self) -> None:
        event = self._selected_event()
        self._selected_event_id = event.id if event is not None else None
        self._update_actions_enabled()

    def _selected_event(self):
        selected = self.events_table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.events_table.item(selected[0].row(), HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ID)
        if id_item is None:
            return None
        return hazard_library_template_event_service.get_by_id(int(id_item.text()))

    def _on_legal_link_selection_changed(self) -> None:
        link = self._selected_legal_link()
        self._selected_legal_link_id = link.id if link is not None else None
        self._update_actions_enabled()

    def _selected_legal_link(self):
        selected = self.legal_links_table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.legal_links_table.item(
            selected[0].row(),
            HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ID,
        )
        if id_item is None:
            return None
        return hazard_library_template_legal_link_service.get_by_id(int(id_item.text()))

    def _load_legal_links_table(self) -> None:
        self.legal_links_table.blockSignals(True)
        self.legal_links_table.setRowCount(0)

        if self._template_id is None:
            self.legal_links_table.blockSignals(False)
            self._update_actions_enabled()
            return

        links = hazard_library_template_legal_link_service.get_for_template(
            self._template_id,
            include_inactive=True,
        )
        self.legal_links_table.setRowCount(len(links))
        selected_row = -1
        for row_index, link in enumerate(links):
            label = "—"
            if link.legal_document_id is not None:
                document = legal_document_service.get_by_id(link.legal_document_id)
                if document is not None:
                    label = legal_document_catalog_link_label(document)
            elif link.legal_requirement_id is not None:
                requirement = legal_requirement_service.get_by_id(link.legal_requirement_id)
                if requirement is not None:
                    label = legal_requirement_merged_target_label(requirement)
            self.legal_links_table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ID,
                QTableWidgetItem(str(link.id)),
            )
            self.legal_links_table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_REQUIREMENT,
                QTableWidgetItem(label),
            )
            self.legal_links_table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_NOTE,
                QTableWidgetItem(link.note or ""),
            )
            self.legal_links_table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ACTIVE,
                QTableWidgetItem("Ano" if link.active else "Ne"),
            )
            if self._selected_legal_link_id == link.id:
                selected_row = row_index

        configure_table_columns(self.legal_links_table, "hazard_library_template_legal_links")
        if selected_row >= 0:
            self.legal_links_table.selectRow(selected_row)
        else:
            self._selected_legal_link_id = None
        self.legal_links_table.blockSignals(False)
        self._update_actions_enabled()
