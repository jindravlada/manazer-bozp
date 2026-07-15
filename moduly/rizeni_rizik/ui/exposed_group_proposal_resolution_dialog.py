from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.ai_oponentni.types import AiProposal
from core.widgets.dialog_utils import create_save_cancel_box
from moduly.nastaveni.sluzby.exposed_group_service import (
    ExposedGroupError,
    ExposedGroupMatchKind,
    exposed_group_service,
)
from moduly.nastaveni.ui.exposed_groups_management_dialog import ExposedGroupsManagementDialog


def is_exposed_group_proposal(proposal: AiProposal) -> bool:
    area = (proposal.area or "").casefold()
    needles = ("ohrožen", "ohrozen", "osob", "skupin", "rizik", "posouzen")
    return any(needle in area for needle in needles)


class ExposedGroupProposalResolutionDialog(QDialog):
    """Rozhodnutí uživatele o napojení AI návrhu na číselník ohrožených skupin."""

    def __init__(self, parent=None, *, proposal: AiProposal):
        super().__init__(parent)
        self.proposal = proposal
        self.resolved_group_id: int | None = None
        self.user_rejected = False

        match = exposed_group_service.classify_name(proposal.name)
        self.setWindowTitle("Ohrožená skupina – návrh AI")
        self.resize(560, 320)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Navržený název: {proposal.name}"))
        if proposal.reasoning:
            reasoning = QLabel(proposal.reasoning)
            reasoning.setWordWrap(True)
            layout.addWidget(reasoning)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.group_combo = QComboBox()
        self.group_combo.setVisible(False)
        form = QFormLayout()
        form.addRow("Vybrat skupinu:", self.group_combo)
        layout.addLayout(form)

        manage_btn = QPushButton("Spravovat číselník…")
        manage_btn.clicked.connect(self._open_management)
        layout.addWidget(manage_btn)

        self._match = match
        self._configure_for_match()

        buttons = create_save_cancel_box(self)
        accept_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if accept_button is not None:
            accept_button.setText("Potvrdit")
        reject_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if reject_button is not None:
            reject_button.setText("Zamítnout návrh")
        buttons.accepted.connect(self._accept_resolution)
        buttons.rejected.connect(self._reject_proposal)
        layout.addWidget(buttons)

        self._action_buttons = QHBoxLayout()
        self.use_button = QPushButton("Použít shodu")
        self.activate_button = QPushButton("Aktivovat a použít")
        self.create_button = QPushButton("Vytvořit novou a použít")
        self.pick_button = QPushButton("Vybrat jinou skupinu")
        self.use_button.clicked.connect(self._use_active_match)
        self.activate_button.clicked.connect(self._activate_and_use)
        self.create_button.clicked.connect(self._create_and_use)
        self.pick_button.clicked.connect(self._show_picker)
        for button in (
            self.use_button,
            self.activate_button,
            self.create_button,
            self.pick_button,
        ):
            self._action_buttons.addWidget(button)
        layout.addLayout(self._action_buttons)

    def _configure_for_match(self) -> None:
        for button in (
            self.use_button,
            self.activate_button,
            self.create_button,
            self.pick_button,
        ):
            button.setVisible(False)

        if self._match.kind == ExposedGroupMatchKind.ACTIVE:
            group = self._match.groups[0]
            self.info_label.setText(
                f"Nalezena aktivní shoda v číselníku: „{group.name}“."
            )
            self.use_button.setVisible(True)
            self.pick_button.setVisible(True)
            self.resolved_group_id = group.id
            return

        if self._match.kind == ExposedGroupMatchKind.INACTIVE:
            group = self._match.groups[0]
            self.info_label.setText(
                f"Nalezena neaktivní shoda v číselníku: „{group.name}“."
            )
            self.activate_button.setVisible(True)
            self.pick_button.setVisible(True)
            self.resolved_group_id = group.id
            return

        if self._match.kind == ExposedGroupMatchKind.AMBIGUOUS:
            names = ", ".join(group.name for group in self._match.groups)
            self.info_label.setText(
                f"Nalezeno více shod v číselníku ({names}). Vyberte správnou skupinu."
            )
            self._populate_group_combo(include_inactive=True)
            self.group_combo.setVisible(True)
            self.pick_button.setVisible(True)
            self.create_button.setVisible(True)
            return

        self.info_label.setText("V číselníku nebyla nalezena odpovídající skupina.")
        self.create_button.setVisible(True)
        self.pick_button.setVisible(True)

    def _populate_group_combo(self, *, include_inactive: bool) -> None:
        current_id = self.resolved_group_id
        self.group_combo.clear()
        for group in exposed_group_service.get_all(include_inactive=include_inactive):
            label = group.name
            if not group.active:
                label = f"{label} (neaktivní)"
            self.group_combo.addItem(label, group.id)
        if current_id is not None:
            index = self.group_combo.findData(current_id)
            if index >= 0:
                self.group_combo.setCurrentIndex(index)

    def _open_management(self) -> None:
        dialog = ExposedGroupsManagementDialog(self)
        dialog.exec()
        self._populate_group_combo(include_inactive=True)

    def _show_picker(self) -> None:
        self._populate_group_combo(include_inactive=True)
        self.group_combo.setVisible(True)

    def _use_active_match(self) -> None:
        if self.resolved_group_id is None:
            return
        self.accept()

    def _activate_and_use(self) -> None:
        if self.resolved_group_id is None:
            return
        try:
            exposed_group_service.activate(self.resolved_group_id)
        except ExposedGroupError as error:
            QMessageBox.warning(self, "Ohrožená skupina", str(error))
            return
        self.accept()

    def _create_and_use(self) -> None:
        reply = QMessageBox.question(
            self,
            "Ohrožená skupina",
            f"Vytvořit novou položku číselníku „{self.proposal.name.strip()}“ a použít ji?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            group = exposed_group_service.create_group(name=self.proposal.name)
        except ExposedGroupError as error:
            QMessageBox.warning(self, "Ohrožená skupina", str(error))
            return
        self.resolved_group_id = group.id
        self.accept()

    def _accept_resolution(self) -> None:
        if self.group_combo.isVisible() and self.group_combo.currentData() is not None:
            self.resolved_group_id = self.group_combo.currentData()
        if self.resolved_group_id is None:
            QMessageBox.warning(self, "Ohrožená skupina", "Vyberte nebo vytvořte skupinu.")
            return
        self.accept()

    def _reject_proposal(self) -> None:
        self.user_rejected = True
        self.reject()


def resolve_exposed_group_proposals(
    parent,
    proposals: list[AiProposal],
) -> tuple[list[AiProposal], list[AiProposal]]:
    """Doplní exposed_group_id u návrhů ohrožených skupin; nerozhodnuté jdou mezi zamítnuté."""
    resolved: list[AiProposal] = []
    rejected: list[AiProposal] = []
    for proposal in proposals:
        if not is_exposed_group_proposal(proposal):
            resolved.append(proposal)
            continue
        dialog = ExposedGroupProposalResolutionDialog(parent, proposal=proposal)
        if dialog.exec() and dialog.resolved_group_id is not None:
            resolved.append(
                AiProposal(
                    area=proposal.area,
                    name=proposal.name,
                    reasoning=proposal.reasoning,
                    parent_export_id=proposal.parent_export_id,
                    proposal_id=proposal.proposal_id,
                    exposed_group_id=dialog.resolved_group_id,
                )
            )
        else:
            rejected.append(proposal)
    return resolved, rejected
