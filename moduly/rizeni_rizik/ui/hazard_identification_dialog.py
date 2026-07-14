from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QTabWidget, QVBoxLayout, QWidget

from core.ai_oponentni.constants import AI_PEER_REVIEW_TAB_TITLE
from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewWidget
from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import (
    DIALOG_WINDOW_TITLE,
    HAZARD_IDENTIFICATION_TABS,
    TAB_BASICS,
    TAB_EVENTS,
    TAB_HAZARDS,
    TAB_INVENTORY,
    TAB_RISK_ASSESSMENT,
    is_identification_events_read_only,
    is_identification_hazards_read_only,
    is_identification_inventory_read_only,
    is_identification_risk_assessment_read_only,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
    hazard_identification_peer_review_provider,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    HazardIdentificationError,
    hazard_identification_service,
)
from moduly.rizeni_rizik.ui.hazard_events_widget import HazardEventsWidget
from moduly.rizeni_rizik.ui.hazard_identification_basics_widget import (
    HazardIdentificationBasicsWidget,
)
from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget
from moduly.rizeni_rizik.ui.hazard_risk_assessments_widget import HazardRiskAssessmentsWidget
from moduly.rizeni_rizik.ui.identified_hazards_widget import IdentifiedHazardsWidget


class HazardIdentificationDialog(QDialog):
    def __init__(self, parent=None, identification=None):
        super().__init__(parent)

        self.identification = identification

        self.setWindowTitle(DIALOG_WINDOW_TITLE)
        self.resize(960, 680)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.basics_widget = HazardIdentificationBasicsWidget()
        self.risk_assessments_widget = HazardRiskAssessmentsWidget()
        self.events_widget = HazardEventsWidget(on_assessment_saved=self._on_assessment_saved)
        self.hazards_widget = IdentifiedHazardsWidget(on_event_saved=self._on_event_saved)
        self.inventory_widget = HazardInventoryWidget(on_hazard_saved=self._on_hazard_saved)
        self.ai_peer_review_widget = AiPeerReviewWidget(
            provider=hazard_identification_peer_review_provider,
            show_responsible_person_option=True,
            on_proposals_applied=self._on_peer_review_applied,
        )
        self.tabs.addTab(self.basics_widget, TAB_BASICS)
        self.tabs.addTab(self.inventory_widget, TAB_INVENTORY)
        self.tabs.addTab(self.hazards_widget, TAB_HAZARDS)
        self.tabs.addTab(self.events_widget, TAB_EVENTS)
        self.tabs.addTab(self.risk_assessments_widget, TAB_RISK_ASSESSMENT)
        self.tabs.addTab(self.ai_peer_review_widget, AI_PEER_REVIEW_TAB_TITLE)

        for tab_label in HAZARD_IDENTIFICATION_TABS[6:]:
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
        self._sync_inventory_context()
        self._sync_hazards_context()
        self._sync_events_context()
        self._sync_risk_assessment_context()
        self._sync_ai_peer_review_context()
        self._update_inventory_tab_enabled()
        self._update_hazards_tab_enabled()
        self._update_events_tab_enabled()
        self._update_risk_assessment_tab_enabled()
        self._update_ai_peer_review_tab_enabled()

    def _update_inventory_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(1, self.identification is not None)

    def _update_hazards_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(2, self.identification is not None)

    def _update_events_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(3, self.identification is not None)

    def _update_risk_assessment_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(4, self.identification is not None)

    def _update_ai_peer_review_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(5, self.identification is not None)

    def _sync_inventory_context(self) -> None:
        identification_id = self.identification.id if self.identification is not None else None
        status = self.identification.status if self.identification is not None else ""
        self.inventory_widget.set_identification(
            identification_id,
            read_only=is_identification_inventory_read_only(status),
        )

    def _sync_hazards_context(self) -> None:
        identification_id = self.identification.id if self.identification is not None else None
        status = self.identification.status if self.identification is not None else ""
        self.hazards_widget.set_identification(
            identification_id,
            read_only=is_identification_hazards_read_only(status),
        )

    def _sync_events_context(self) -> None:
        identification_id = self.identification.id if self.identification is not None else None
        status = self.identification.status if self.identification is not None else ""
        self.events_widget.set_identification(
            identification_id,
            read_only=is_identification_events_read_only(status),
        )

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

    def _on_hazard_saved(self) -> None:
        self.hazards_widget.refresh()

    def _on_event_saved(self) -> None:
        self.events_widget.refresh()
        self.hazards_widget.refresh()

    def _on_assessment_saved(self) -> None:
        self.risk_assessments_widget.refresh()
        self.events_widget.refresh()

    def _on_peer_review_applied(self) -> None:
        self.inventory_widget.refresh()
        self.hazards_widget.refresh()
        self.events_widget.refresh()
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

        self._update_inventory_tab_enabled()
        self._update_hazards_tab_enabled()
        self._update_events_tab_enabled()
        self._update_risk_assessment_tab_enabled()
        self._update_ai_peer_review_tab_enabled()
        self._sync_inventory_context()
        self._sync_hazards_context()
        self._sync_events_context()
        self._sync_risk_assessment_context()
        self._sync_ai_peer_review_context()
        self.basics_widget.load_identification(self.identification)
        QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Základní údaje byly uloženy.")

    def get_data(self) -> dict:
        return self.basics_widget.get_data()
