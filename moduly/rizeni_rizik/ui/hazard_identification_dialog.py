from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import (
    DIALOG_WINDOW_TITLE,
    HAZARD_IDENTIFICATION_CANCEL_CONFIRM,
    HAZARD_IDENTIFICATION_SAVE_SUCCESS,
    HAZARD_IDENTIFICATION_UNSAVED_DISCARD,
    HAZARD_IDENTIFICATION_UNSAVED_PROMPT,
    HAZARD_IDENTIFICATION_UNSAVED_SAVE,
    HAZARD_IDENTIFICATION_UNSAVED_STAY,
    TAB_BASICS,
    TAB_INVENTORY,
    TAB_PHOTOS,
    TAB_RISK_ASSESSMENT,
    is_identification_inventory_read_only,
    is_identification_photos_read_only,
    is_identification_risk_assessment_read_only,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    HazardIdentificationError,
    hazard_identification_service,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_working_copy import (
    HazardIdentificationWorkingCopy,
)
from moduly.rizeni_rizik.ui.hazard_identification_basics_widget import (
    HazardIdentificationBasicsWidget,
)
from moduly.rizeni_rizik.ui.hazard_identification_photos_widget import (
    HazardIdentificationPhotosWidget,
)
from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget
from moduly.rizeni_rizik.ui.hazard_risk_assessments_widget import HazardRiskAssessmentsWidget


class HazardIdentificationDialog(QDialog):
    def __init__(self, parent=None, identification=None, on_open_library_template=None):
        super().__init__(parent)

        self.identification = identification
        self._on_open_library_template = on_open_library_template
        self._identification_store: HazardIdentificationWorkingCopy | None = None
        self._basics_dirty = False
        self._loaded_basics: dict | None = None
        self._closing = False

        self.setWindowTitle(DIALOG_WINDOW_TITLE)
        self.resize(960, 680)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.basics_widget = HazardIdentificationBasicsWidget()
        self.photos_widget = HazardIdentificationPhotosWidget()
        self.risk_assessments_widget = HazardRiskAssessmentsWidget()
        self.inventory_widget = HazardInventoryWidget(
            on_event_saved=self._on_event_saved,
            on_open_library_template=self._handle_open_library_template,
        )
        # R21a: jen HAZARD_IDENTIFICATION_VISIBLE_TABS (AI / Opatření / Publikace / Historie skryté).
        self.basics_tab_index = self.tabs.addTab(self.basics_widget, TAB_BASICS)
        self.photos_tab_index = self.tabs.addTab(self.photos_widget, TAB_PHOTOS)
        self.inventory_tab_index = self.tabs.addTab(self.inventory_widget, TAB_INVENTORY)
        self.risk_assessment_tab_index = self.tabs.addTab(
            self.risk_assessments_widget,
            TAB_RISK_ASSESSMENT,
        )

        layout.addWidget(self.tabs)

        self.buttons = create_save_cancel_box(self)
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if self.save_button is not None:
            self.save_button.clicked.connect(self._save_all)
        if cancel_button is not None:
            cancel_button.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self.buttons)

        self._connect_basics_change_signals()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.basics_widget.load_identification(identification)
        self._capture_loaded_basics()
        if identification is not None:
            self._identification_store = HazardIdentificationWorkingCopy.load(identification.id)

        self._sync_photos_context()
        self._sync_inventory_context()
        self._sync_risk_assessment_context()
        self._update_photos_tab_enabled()
        self._update_inventory_tab_enabled()
        self._update_risk_assessment_tab_enabled()
        self._update_save_enabled()
        self._update_window_title()

    @property
    def _content_store(self):
        """Kompatibilita pro find_identification_working_copy."""
        return self._identification_store

    @_content_store.setter
    def _content_store(self, value) -> None:
        self._identification_store = value

    def _update_window_title(self) -> None:
        if (
            self.identification is not None
            and (self.identification.identification_number or "").strip()
        ):
            self.setWindowTitle(
                f"{DIALOG_WINDOW_TITLE} — {self.identification.identification_number}",
            )
        else:
            self.setWindowTitle(DIALOG_WINDOW_TITLE)

    def _connect_basics_change_signals(self) -> None:
        self.basics_widget.operation.currentIndexChanged.connect(self._on_basics_edited)
        self.basics_widget.workplace.currentIndexChanged.connect(self._on_basics_edited)
        self.basics_widget.workplace_part.currentIndexChanged.connect(self._on_basics_edited)
        self.basics_widget.responsible_person.currentIndexChanged.connect(self._on_basics_edited)
        self.basics_widget.started_at.dateChanged.connect(self._on_basics_edited)
        self.basics_widget.status.currentIndexChanged.connect(self._on_basics_edited)
        self.basics_widget.note.textChanged.connect(self._on_basics_edited)

    def _capture_loaded_basics(self) -> None:
        self._loaded_basics = self.get_data()
        self._basics_dirty = False

    def get_data(self) -> dict:
        return self.basics_widget.get_data()

    def is_dirty(self) -> bool:
        store_dirty = (
            self._identification_store is not None and self._identification_store.is_dirty
        )
        basics_changed = (
            self._loaded_basics is not None and self.get_data() != self._loaded_basics
        )
        return self._basics_dirty or store_dirty or basics_changed

    def _on_basics_edited(self, *_args) -> None:
        self._basics_dirty = True
        self._update_save_enabled()

    def _update_save_enabled(self) -> None:
        if self.save_button is not None:
            self.save_button.setEnabled(self.is_dirty() or self.identification is None)

    def _update_photos_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(self.photos_tab_index, self.identification is not None)

    def _update_inventory_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(self.inventory_tab_index, self.identification is not None)

    def _update_risk_assessment_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(
            self.risk_assessment_tab_index,
            self.identification is not None,
        )

    def _sync_photos_context(self) -> None:
        identification_id = self.identification.id if self.identification is not None else None
        status = self.identification.status if self.identification is not None else ""
        self.photos_widget.set_identification(
            identification_id,
            read_only=is_identification_photos_read_only(status),
        )

    def _sync_inventory_context(self) -> None:
        identification_id = self.identification.id if self.identification is not None else None
        status = self.identification.status if self.identification is not None else ""
        self.inventory_widget.set_identification(
            identification_id,
            read_only=is_identification_inventory_read_only(status),
            identification_status=status,
        )

    def _sync_risk_assessment_context(self) -> None:
        identification_id = self.identification.id if self.identification is not None else None
        status = self.identification.status if self.identification is not None else ""
        self.risk_assessments_widget.set_identification(
            identification_id,
            read_only=is_identification_risk_assessment_read_only(status),
        )

    def _refresh_child_widgets(self) -> None:
        self.photos_widget.refresh()
        self.inventory_widget.refresh()
        self.risk_assessments_widget.refresh()

    def _handle_open_library_template(self, template_id: int) -> None:
        if self.is_dirty():
            decision = self._prompt_unsaved_close()
            if decision == "stay":
                return
            if decision == "save":
                if not self._save_all():
                    return
            else:
                return
        self._discard_working_copy()
        self._closing = True
        super().accept()
        if self._on_open_library_template is not None:
            self._on_open_library_template(template_id)

    def _on_event_saved(self) -> None:
        self.risk_assessments_widget.refresh()
        self._update_save_enabled()

    def _on_tab_changed(self, index: int) -> None:
        if index == self.photos_tab_index and self.identification is not None:
            self.photos_widget.refresh()
        if index == self.inventory_tab_index and self.identification is not None:
            self.inventory_widget.refresh()
        if index == self.risk_assessment_tab_index and self.identification is not None:
            self.risk_assessments_widget.refresh()
        self._update_save_enabled()

    def _save_all(self) -> bool:
        data = self.get_data()
        try:
            if self.identification is None:
                self.identification = hazard_identification_service.create_identification(**data)
                self._identification_store = HazardIdentificationWorkingCopy.load(
                    self.identification.id,
                )
            else:
                if self._identification_store is None:
                    self._identification_store = HazardIdentificationWorkingCopy.load(
                        self.identification.id,
                    )
                self.identification = self._identification_store.commit(basics=data)
        except HazardIdentificationError as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            self.tabs.setCurrentIndex(self.basics_tab_index)
            return False
        except ValueError as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            return False

        self.basics_widget.load_identification(self.identification)
        self._capture_loaded_basics()
        self._update_window_title()
        self._update_photos_tab_enabled()
        self._update_inventory_tab_enabled()
        self._update_risk_assessment_tab_enabled()
        self._sync_photos_context()
        self._sync_inventory_context()
        self._sync_risk_assessment_context()
        self._refresh_child_widgets()
        self._update_save_enabled()
        QMessageBox.information(self, DIALOG_WINDOW_TITLE, HAZARD_IDENTIFICATION_SAVE_SUCCESS)
        return True

    def _discard_working_copy(self) -> None:
        if self.identification is not None:
            self._identification_store = HazardIdentificationWorkingCopy.load(
                self.identification.id,
            )
            reloaded = hazard_identification_service.get_by_id(self.identification.id)
            if reloaded is not None:
                self.identification = reloaded
                self.basics_widget.load_identification(reloaded)
        else:
            self._identification_store = None
            self.basics_widget.load_identification(None)
        self._capture_loaded_basics()
        self._sync_photos_context()
        self._sync_inventory_context()
        self._sync_risk_assessment_context()
        self._refresh_child_widgets()

    def _on_cancel_clicked(self) -> None:
        if self.is_dirty():
            answer = QMessageBox.question(
                self,
                DIALOG_WINDOW_TITLE,
                HAZARD_IDENTIFICATION_CANCEL_CONFIRM,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._discard_working_copy()
        self._closing = True
        self.reject()

    def _prompt_unsaved_close(self) -> str:
        message = QMessageBox(self)
        message.setWindowTitle(DIALOG_WINDOW_TITLE)
        message.setText(HAZARD_IDENTIFICATION_UNSAVED_PROMPT)
        message.setIcon(QMessageBox.Icon.Question)
        save_btn = message.addButton(
            HAZARD_IDENTIFICATION_UNSAVED_SAVE,
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard_btn = message.addButton(
            HAZARD_IDENTIFICATION_UNSAVED_DISCARD,
            QMessageBox.ButtonRole.DestructiveRole,
        )
        stay_btn = message.addButton(
            HAZARD_IDENTIFICATION_UNSAVED_STAY,
            QMessageBox.ButtonRole.RejectRole,
        )
        message.setDefaultButton(stay_btn)
        message.exec()
        clicked = message.clickedButton()
        if clicked is save_btn:
            return "save"
        if clicked is discard_btn:
            return "discard"
        return "stay"

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing or not self.is_dirty():
            self._discard_working_copy()
            super().closeEvent(event)
            return
        decision = self._prompt_unsaved_close()
        if decision == "stay":
            event.ignore()
            return
        if decision == "save":
            if not self._save_all():
                event.ignore()
                return
        self._discard_working_copy()
        self._closing = True
        super().closeEvent(event)

    def reject(self) -> None:
        if self._closing:
            super().reject()
            return
        if self.is_dirty():
            decision = self._prompt_unsaved_close()
            if decision == "stay":
                return
            if decision == "save":
                if not self._save_all():
                    return
            self._discard_working_copy()
        self._closing = True
        super().reject()
