from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QTabWidget, QVBoxLayout, QWidget

from core.ai_oponentni.constants import AI_PEER_REVIEW_TAB_TITLE
from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewWidget
from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import (
    DIALOG_WINDOW_TITLE,
    HAZARD_IDENTIFICATION_TABS,
    TAB_BASICS,
    TAB_INVENTORY,
    TAB_PHOTOS,
    TAB_RISK_ASSESSMENT,
    is_identification_inventory_read_only,
    is_identification_photos_read_only,
    is_identification_risk_assessment_read_only,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
    hazard_identification_peer_review_provider,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    HazardIdentificationError,
    hazard_identification_service,
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
        self.ai_peer_review_widget = AiPeerReviewWidget(
            provider=hazard_identification_peer_review_provider,
            on_proposals_applied=self._on_peer_review_applied,
            allow_new_exports=False,
        )
        self.tabs.addTab(self.basics_widget, TAB_BASICS)
        self.tabs.addTab(self.photos_widget, TAB_PHOTOS)
        self.tabs.addTab(self.inventory_widget, TAB_INVENTORY)
        self.tabs.addTab(self.risk_assessments_widget, TAB_RISK_ASSESSMENT)
        self.tabs.addTab(self.ai_peer_review_widget, AI_PEER_REVIEW_TAB_TITLE)

        for tab_label in HAZARD_IDENTIFICATION_TABS[5:]:
            placeholder = QWidget()
            placeholder_layout = QVBoxLayout(placeholder)
            placeholder_layout.addWidget(QLabel("Obsah bude doplněn v další fázi."))
            placeholder_layout.addStretch()
            index = self.tabs.addTab(placeholder, tab_label)
            self.tabs.setTabEnabled(index, False)

        layout.addWidget(self.tabs)

        buttons = create_save_cancel_box(self)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.clicked.connect(self._save_basics)
        if cancel_button is not None:
            cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self.basics_widget.load_identification(identification)
        self._sync_photos_context()
        self._sync_inventory_context()
        self._sync_risk_assessment_context()
        self._sync_ai_peer_review_context()
        self._update_photos_tab_enabled()
        self._update_inventory_tab_enabled()
        self._update_risk_assessment_tab_enabled()
        self._update_ai_peer_review_tab_enabled()

    def _update_photos_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(1, self.identification is not None)

    def _update_inventory_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(2, self.identification is not None)

    def _update_risk_assessment_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(3, self.identification is not None)

    def _update_ai_peer_review_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(4, self.identification is not None)

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

    def _handle_open_library_template(self, template_id: int) -> None:
        self.accept()
        if self._on_open_library_template is not None:
            self._on_open_library_template(template_id)

    def _sync_risk_assessment_context(self) -> None:
        identification_id = self.identification.id if self.identification is not None else None
        status = self.identification.status if self.identification is not None else ""
        self.risk_assessments_widget.set_identification(
            identification_id,
            read_only=is_identification_risk_assessment_read_only(status),
        )

    def _sync_ai_peer_review_context(self) -> None:
        identification_id = self.identification.id if self.identification is not None else None
        self.ai_peer_review_widget.set_source(identification_id)

    def _on_event_saved(self) -> None:
        self.risk_assessments_widget.refresh()

    def _on_peer_review_applied(self) -> None:
        self.inventory_widget.refresh()
        self.risk_assessments_widget.refresh()

    def _save_basics(self) -> None:
        data = self.basics_widget.get_data()
        try:
            if self.identification is None:
                self.identification = hazard_identification_service.create_identification(**data)
            else:
                updated = hazard_identification_service.update_identification(
                    self.identification.id,
                    **data,
                )
                if updated is not None:
                    self.identification = updated
        except HazardIdentificationError as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            self.tabs.setCurrentWidget(self.basics_widget)
            return

        self._update_photos_tab_enabled()
        self._update_inventory_tab_enabled()
        self._update_risk_assessment_tab_enabled()
        self._update_ai_peer_review_tab_enabled()
        self._sync_photos_context()
        self._sync_inventory_context()
        self._sync_risk_assessment_context()
        self._sync_ai_peer_review_context()
        self.basics_widget.load_identification(self.identification)
        QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Základní údaje byly uloženy.")

    def get_data(self) -> dict:
        return self.basics_widget.get_data()
