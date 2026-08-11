from PySide6.QtWidgets import QMessageBox, QPushButton

from core.shared.sluzby.finding_task_service import finding_task_service
from moduly.ukoly.ui.task_dialog import TaskDialog


class FindingTaskActions:
    _ACTION_LABELS = {
        "create": "Vytvořit úkol",
        "open": "Otevřít úkol",
    }

    def __init__(self, parent, get_finding_id, on_changed, *, deferred_edits=None):
        self._parent = parent
        self._get_finding_id = get_finding_id
        self._on_changed = on_changed
        self._deferred_edits = deferred_edits
        self._action = "hidden"

        self.button = QPushButton()
        self.button.clicked.connect(self._handle_click)

    def set_deferred_edits(self, deferred_edits) -> None:
        self._deferred_edits = deferred_edits
        self.update_state()

    def update_state(self) -> None:
        finding_id = self._get_finding_id()
        if self._deferred_edits is not None:
            self._action = self._deferred_edits.get_task_action(finding_id)
        else:
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
        if self._deferred_edits is not None:
            try:
                task = self._deferred_edits.stage_task_from_finding(finding_id)
            except ValueError as exc:
                QMessageBox.warning(self._parent, "Úkol", str(exc))
                return
            self._on_changed()
            dialog = TaskDialog(
                self._parent,
                task=task,
                persist_handler=self._deferred_persist,
            )
            dialog.exec()
            self._on_changed()
            return

        try:
            task = finding_task_service.create_task_from_finding(finding_id)
        except ValueError as exc:
            QMessageBox.warning(self._parent, "Úkol", str(exc))
            return

        self._on_changed()

        dialog = TaskDialog(self._parent, task=task)
        dialog.exec()
        self._on_changed()

    def _open_task(self, finding_id: int) -> None:
        if self._deferred_edits is not None:
            finding = self._deferred_edits.get_finding(finding_id)
            task_id = getattr(finding, "task_id", None) if finding is not None else None
            task = self._deferred_edits.get_task(int(task_id)) if task_id else None
            if task is None:
                QMessageBox.warning(self._parent, "Úkol", "Propojený úkol nebyl nalezen.")
                self._on_changed()
                return
            dialog = TaskDialog(
                self._parent,
                task=task,
                persist_handler=self._deferred_persist,
            )
            dialog.exec()
            self._on_changed()
            return

        from core.shared.sluzby.finding_service import finding_service

        finding = finding_service.get_by_id(finding_id)
        task = finding_task_service.get_linked_task(finding)
        if task is None:
            QMessageBox.warning(self._parent, "Úkol", "Propojený úkol nebyl nalezen.")
            self._on_changed()
            return

        dialog = TaskDialog(self._parent, task=task)
        dialog.exec()
        self._on_changed()

    def _deferred_persist(self, task, data: dict):
        assert self._deferred_edits is not None
        if task is None or getattr(task, "id", None) is None:
            return False
        return self._deferred_edits.stage_task_update(int(task.id), data)
