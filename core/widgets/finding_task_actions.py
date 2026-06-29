from PySide6.QtWidgets import QDialog, QMessageBox, QPushButton

from core.shared.sluzby.finding_task_service import finding_task_service
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog


class FindingTaskActions:
    _ACTION_LABELS = {
        "create": "Vytvořit úkol",
        "open": "Otevřít úkol",
    }

    def __init__(self, parent, get_finding_id, on_changed):
        self._parent = parent
        self._get_finding_id = get_finding_id
        self._on_changed = on_changed
        self._action = "hidden"

        self.button = QPushButton()
        self.button.clicked.connect(self._handle_click)

    def update_state(self) -> None:
        finding_id = self._get_finding_id()
        self._action = finding_task_service.get_task_action(finding_id)

        if self._action == "hidden":
            self.button.setVisible(False)
            self.button.setEnabled(False)
            return

        self.button.setVisible(True)
        self.button.setEnabled(True)
        self.button.setText(self._ACTION_LABELS[self._action])

    def _handle_click(self) -> None:
        finding_id = self._get_finding_id()
        if finding_id is None:
            return

        if self._action == "create":
            self._create_task(finding_id)
        elif self._action == "open":
            self._open_task(finding_id)

    def _create_task(self, finding_id: int) -> None:
        try:
            finding_task_service.create_task_from_finding(finding_id)
        except ValueError as exc:
            QMessageBox.warning(self._parent, "Úkol", str(exc))
            return

        self._on_changed()

    def _open_task(self, finding_id: int) -> None:
        from core.shared.sluzby.finding_service import finding_service

        finding = finding_service.get_by_id(finding_id)
        task = finding_task_service.get_linked_task(finding)
        if task is None:
            QMessageBox.warning(self._parent, "Úkol", "Propojený úkol nebyl nalezen.")
            self._on_changed()
            return

        dialog = TaskDialog(self._parent, task=task)
        if dialog.exec() == QDialog.Accepted:
            task_service.update_task(task.id, **dialog.get_data())
            self._on_changed()
