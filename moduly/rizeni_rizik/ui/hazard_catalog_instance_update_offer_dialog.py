from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from moduly.rizeni_rizik.constants_library import (
    CATALOG_UPDATE_OFFER_REVISION_INSTANCE,
    CATALOG_UPDATE_OFFER_REVISION_MASTER,
    CATALOG_UPDATE_OFFER_CHOICE_KEEP,
    CATALOG_UPDATE_OFFER_CHOICE_SHOW_DIFF,
    CATALOG_UPDATE_OFFER_CHOICE_UPDATE,
    CATALOG_UPDATE_OFFER_DIALOG_TITLE,
    CATALOG_UPDATE_OFFER_INTRO,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_update_service import (
    CatalogInstanceUpdateOffer,
)

CATALOG_UPDATE_CHOICE_UPDATE = "update"
CATALOG_UPDATE_CHOICE_SHOW_DIFF = "show_diff"
CATALOG_UPDATE_CHOICE_KEEP = "keep"


class HazardCatalogInstanceUpdateOfferDialog(QDialog):
    def __init__(self, parent=None, *, offer: CatalogInstanceUpdateOffer):
        super().__init__(parent)
        self.offer = offer
        self.selected_choice = CATALOG_UPDATE_CHOICE_KEEP

        self.setWindowTitle(CATALOG_UPDATE_OFFER_DIALOG_TITLE)
        self.resize(460, 320)

        layout = QVBoxLayout(self)

        intro = QLabel(CATALOG_UPDATE_OFFER_INTRO)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        version_label = QLabel(
            f"{offer.template_name}\n\n"
            f"{CATALOG_UPDATE_OFFER_REVISION_INSTANCE.format(revision=offer.source_template_version)}\n\n"
            f"↓\n\n"
            f"{CATALOG_UPDATE_OFFER_REVISION_MASTER.format(revision=offer.master_version)}"
        )
        version_label.setWordWrap(True)
        layout.addWidget(version_label)

        self.choice_group = QButtonGroup(self)
        self.update_radio = QRadioButton(CATALOG_UPDATE_OFFER_CHOICE_UPDATE)
        self.show_diff_radio = QRadioButton(CATALOG_UPDATE_OFFER_CHOICE_SHOW_DIFF)
        self.keep_radio = QRadioButton(CATALOG_UPDATE_OFFER_CHOICE_KEEP)
        self.keep_radio.setChecked(True)

        for button in (self.update_radio, self.show_diff_radio, self.keep_radio):
            self.choice_group.addButton(button)
            layout.addWidget(button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def accept(self) -> None:
        if self.update_radio.isChecked():
            self.selected_choice = CATALOG_UPDATE_CHOICE_UPDATE
        elif self.show_diff_radio.isChecked():
            self.selected_choice = CATALOG_UPDATE_CHOICE_SHOW_DIFF
        else:
            self.selected_choice = CATALOG_UPDATE_CHOICE_KEEP
        super().accept()
