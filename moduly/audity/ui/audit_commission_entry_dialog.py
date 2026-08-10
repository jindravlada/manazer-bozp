from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.person_selector import PersonSelector
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.audity.constants import (
    COMMISSION_DEFAULT_ROLE_INVITED,
    COMMISSION_DEFAULT_ROLE_MEMBER,
)


class AuditCommissionEntryDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        entry_type: str,
        entry: dict | None = None,
    ):
        super().__init__(parent)

        self.entry_type = entry_type
        titles = {
            "member": "Auditor",
            "invited": "Přizvaná osoba",
        }
        self.setWindowTitle(titles.get(entry_type, "Osoba auditního týmu"))
        self.resize(520, 260)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.thp_selector = ThpWorkerSelector(include_empty=True)
        self.person_selector = PersonSelector(include_inactive=False, allow_add_new=True)
        self.role_edit = QLineEdit()
        self.note_edit = QLineEdit()

        if entry_type == "member":
            form.addRow("THP pracovník:", self.thp_selector)
            self.role_edit.setText(COMMISSION_DEFAULT_ROLE_MEMBER)
        else:
            form.addRow("Osoba:", self.person_selector)
            self.role_edit.setText(COMMISSION_DEFAULT_ROLE_INVITED)

        form.addRow("Role:", self.role_edit)
        form.addRow("Poznámka:", self.note_edit)
        layout.addLayout(form)

        is_new = entry is None
        buttons = create_save_cancel_box(self, is_new=is_new)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=is_new,
            title=self.windowTitle(),
        )
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()

        self.thp_selector.setVisible(entry_type == "member")
        self.person_selector.setVisible(entry_type == "invited")

        if entry is not None:
            if entry_type == "member" and entry.get("thp_worker_id") is not None:
                self.thp_selector.set_person_id(entry["thp_worker_id"])
            elif entry_type == "invited" and entry.get("person_id") is not None:
                self.person_selector.set_person_id(entry["person_id"])
            if entry.get("role_text"):
                self.role_edit.setText(entry["role_text"])
            if entry.get("note_text"):
                self.note_edit.setText(entry["note_text"])

        self._editor.capture_baseline()

    def get_data(self) -> dict:
        role_text = self.role_edit.text().strip() or None
        note_text = self.note_edit.text().strip() or None

        if self.entry_type == "member":
            worker = self.thp_selector.current_person()
            worker_id = self.thp_selector.current_person_id()
            display_name = worker.display_name if worker else self.thp_selector.currentText().strip()
            return {
                "thp_worker_id": worker_id,
                "person_id": None,
                "display_name": display_name,
                "role_text": role_text,
                "note_text": note_text,
            }

        person = self.person_selector.current_person()
        person_id = self.person_selector.current_person_id()
        display_name = person.display_name if person else self.person_selector.display_text()
        return {
            "thp_worker_id": None,
            "person_id": person_id,
            "display_name": display_name,
            "role_text": role_text,
            "note_text": note_text,
        }
