"""Editor mimořádné auditní otázky (AUDIT-EXTRAORDINARY-1)."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.editor_dialog_controller import (
    EDITOR_CLOSE_LABEL,
    EDITOR_SAVE_LABEL,
    configure_editor_close_button,
    configure_editor_save_button,
    confirm_unsaved_editor_close,
)
from moduly.audity.constants import (
    CONTROL_POINT_SEVERITY_OPTIONS,
    EXTRAORDINARY_NON_AUDITABLE_TARGET_LABEL,
    EXTRAORDINARY_QUESTION_EDITOR_TITLE_EDIT,
    EXTRAORDINARY_QUESTION_EDITOR_TITLE_NEW,
    EXTRAORDINARY_TARGET_STATUS_CANCELLED,
    EXTRAORDINARY_TARGET_STATUS_LABELS,
    EXTRAORDINARY_TARGET_STATUS_PENDING,
)
from moduly.audity.sluzby.audit_auditable_workplace_service import (
    is_auditable_workplace_id,
)
from moduly.audity.sluzby.audit_extraordinary_question_service import (
    AuditExtraordinaryError,
    audit_extraordinary_question_service,
    is_target_locked,
)
from moduly.nastaveni.sluzby.settings_service import settings_service


class ExtraordinaryQuestionEditorDialog(QDialog):
    """Nová / úprava mimořádné otázky s odloženým uložením."""

    def __init__(self, parent=None, *, question_id: int | None = None):
        super().__init__(parent)
        self._question_id = question_id
        self._closing = False
        self._baseline: dict | None = None
        self._existing_targets: dict[int, str] = {}
        self._text_locked = False

        self.setWindowTitle(
            EXTRAORDINARY_QUESTION_EDITOR_TITLE_EDIT
            if question_id
            else EXTRAORDINARY_QUESTION_EDITOR_TITLE_NEW
        )
        self.resize(720, 560)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.question_text = QTextEdit()
        self.question_text.setAcceptRichText(False)
        self.question_text.setMinimumHeight(90)
        form.addRow("Otázka:", self.question_text)

        self.process_combo = QComboBox()
        self._load_process_choices()
        form.addRow("Proces:", self.process_combo)

        self.severity_combo = QComboBox()
        self.severity_combo.addItem("— vyberte závažnost —", None)
        for value, label in CONTROL_POINT_SEVERITY_OPTIONS:
            self.severity_combo.addItem(label, value)
        form.addRow("Závažnost:", self.severity_combo)

        self.assigned_by = QLineEdit()
        self.assigned_by.setPlaceholderText("Zadal / zdroj")
        form.addRow("Zadal / zdroj:", self.assigned_by)

        self.assigned_on = QDateEdit()
        self.assigned_on.setCalendarPopup(True)
        self.assigned_on.setDate(date.today())
        form.addRow("Datum zadání:", self.assigned_on)

        self.note = QTextEdit()
        self.note.setAcceptRichText(False)
        self.note.setMinimumHeight(60)
        form.addRow("Poznámka:", self.note)
        layout.addLayout(form)

        layout.addWidget(QLabel("Cílové provozy:"))
        mode_row = QHBoxLayout()
        self.mode_all = QRadioButton("Všechny provozy")
        self.mode_selected = QRadioButton("Vybrané provozy")
        self.mode_selected.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self.mode_all)
        self._mode_group.addButton(self.mode_selected)
        mode_row.addWidget(self.mode_all)
        mode_row.addWidget(self.mode_selected)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        self.workplace_list = QListWidget()
        self.workplace_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        layout.addWidget(self.workplace_list, 1)

        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self._save_btn = QPushButton()
        configure_editor_save_button(self._save_btn)
        self._save_btn.setText(EDITOR_SAVE_LABEL)
        self._save_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._save_close_btn = QPushButton("Uložit a zavřít")
        self._save_close_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._close_btn = QPushButton()
        configure_editor_close_button(self._close_btn, is_new=question_id is None)
        self._close_btn.setText(EDITOR_CLOSE_LABEL)
        self._close_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        footer.addWidget(self._save_btn)
        footer.addWidget(self._save_close_btn)
        footer.addWidget(self._close_btn)
        layout.addLayout(footer)

        self._save_btn.clicked.connect(self._save_keep_open)
        self._save_close_btn.clicked.connect(self._save_and_close)
        self._close_btn.clicked.connect(self._request_close)
        self.mode_all.toggled.connect(self._on_mode_changed)

        self._load_workplaces()
        self._load_question()
        self._capture_baseline()

    def _load_process_choices(self) -> None:
        self.process_combo.blockSignals(True)
        self.process_combo.clear()
        for process_id, label in audit_extraordinary_question_service.list_process_choices():
            self.process_combo.addItem(label, process_id)
        self.process_combo.blockSignals(False)

    def _load_workplaces(self) -> None:
        self._choices = audit_extraordinary_question_service.list_selectable_workplaces()
        self.workplace_list.clear()
        listed_ids: set[int] = set()
        for choice in self._choices:
            item = QListWidgetItem(choice.display_name)
            item.setData(Qt.ItemDataRole.UserRole, choice.workplace_id)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(Qt.CheckState.Unchecked)
            self.workplace_list.addItem(item)
            listed_ids.add(int(choice.workplace_id))

        # Historické neauditovatelné cíle zachovat ve výběru (bez nabídky jako nový cíl).
        for workplace_id, status in self._existing_targets.items():
            if int(workplace_id) in listed_ids:
                continue
            workplace = settings_service.get_workplace_by_id(int(workplace_id))
            name = (
                str(workplace.name).strip()
                if workplace is not None and str(workplace.name or "").strip()
                else f"#{workplace_id}"
            )
            item = QListWidgetItem(
                f"{name} — {EXTRAORDINARY_NON_AUDITABLE_TARGET_LABEL}"
            )
            item.setData(Qt.ItemDataRole.UserRole, int(workplace_id))
            item.setData(Qt.ItemDataRole.UserRole + 1, False)  # is_auditable
            flags = (
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setFlags(flags)
            if status == EXTRAORDINARY_TARGET_STATUS_CANCELLED:
                item.setCheckState(Qt.CheckState.Unchecked)
                # Cancelled neauditovatelný cíl nelze obnovit zaškrtnutím.
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            else:
                item.setCheckState(Qt.CheckState.Checked)
            self.workplace_list.addItem(item)

    def _load_question(self) -> None:
        if self._question_id is None:
            return
        question, targets = audit_extraordinary_question_service.get_question(
            self._question_id
        )
        self.question_text.setPlainText(question.question_text or "")
        self.assigned_by.setText(question.assigned_by or "")
        if question.assigned_on is not None:
            self.assigned_on.setDate(question.assigned_on)
        self.note.setPlainText(question.note or "")
        severity = str(getattr(question, "severity", None) or "").strip()
        severity_index = self.severity_combo.findData(severity or None)
        if severity and severity_index < 0:
            # Historická/neznámá hodnota — zobrazit, dokud uživatel nevybere platnou.
            self.severity_combo.addItem(severity, severity)
            severity_index = self.severity_combo.findData(severity)
        self.severity_combo.setCurrentIndex(max(severity_index, 0))
        process_id = getattr(question, "process_id", None)
        process_index = self.process_combo.findData(process_id)
        if process_id and process_index < 0:
            name = str(getattr(question, "process_name", "") or "").strip() or str(process_id)
            self.process_combo.addItem(name, process_id)
            process_index = self.process_combo.findData(process_id)
        self.process_combo.setCurrentIndex(max(process_index, 0))
        self._existing_targets = {
            int(item.workplace_id): str(item.status or "") for item in targets
        }
        self._text_locked = any(
            is_target_locked(status) for status in self._existing_targets.values()
        )
        if self._text_locked:
            self.question_text.setReadOnly(True)
            self._hint.setText(
                "Text otázky je zamčený (cíle Přiřazeno/Ověřeno). "
                "Lze přidávat nové provozy a spravovat pending/cancelled cíle."
            )
        self.mode_selected.setChecked(True)
        # Znovu sestavit seznam včetně historických neauditovatelných cílů.
        self._load_workplaces()
        for row in range(self.workplace_list.count()):
            item = self.workplace_list.item(row)
            wid = int(item.data(Qt.ItemDataRole.UserRole))
            status = self._existing_targets.get(wid)
            if status is None:
                item.setCheckState(Qt.CheckState.Unchecked)
                continue
            label = EXTRAORDINARY_TARGET_STATUS_LABELS.get(status, status)
            base = item.text().split(" — ")[0]
            if not is_auditable_workplace_id(wid):
                item.setText(
                    f"{base} — {EXTRAORDINARY_NON_AUDITABLE_TARGET_LABEL} — {label}"
                )
            else:
                item.setText(f"{base} — {label}")
            if status == EXTRAORDINARY_TARGET_STATUS_CANCELLED:
                item.setCheckState(Qt.CheckState.Unchecked)
                if not is_auditable_workplace_id(wid):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            else:
                item.setCheckState(Qt.CheckState.Checked)
            if is_target_locked(status):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

    def _on_mode_changed(self) -> None:
        selected = self.mode_selected.isChecked()
        self.workplace_list.setEnabled(selected)
        if self.mode_all.isChecked() and self._question_id is None:
            for row in range(self.workplace_list.count()):
                item = self.workplace_list.item(row)
                if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    item.setCheckState(Qt.CheckState.Checked)

    def _selected_workplace_ids(self) -> list[int]:
        if self.mode_all.isChecked() and self._question_id is None:
            return [choice.workplace_id for choice in self._choices]
        ids: list[int] = []
        for row in range(self.workplace_list.count()):
            item = self.workplace_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return ids

    def _snapshot(self) -> dict:
        return {
            "question_text": self.question_text.toPlainText().strip(),
            "assigned_by": self.assigned_by.text().strip(),
            "assigned_on": self.assigned_on.date().toPython(),
            "note": self.note.toPlainText().strip(),
            "severity": self.severity_combo.currentData(),
            "process_id": self.process_combo.currentData(),
            "all_mode": self.mode_all.isChecked(),
            "workplace_ids": self._selected_workplace_ids(),
        }

    def _capture_baseline(self) -> None:
        self._baseline = deepcopy(self._snapshot())

    def _is_dirty(self) -> bool:
        return self._baseline != self._snapshot()

    def _persist(self) -> bool:
        data = self._snapshot()
        try:
            if self._question_id is None:
                created = audit_extraordinary_question_service.create_question(
                    question_text=data["question_text"],
                    assigned_by=data["assigned_by"],
                    assigned_on=data["assigned_on"],
                    note=data["note"],
                    severity=data["severity"],
                    process_id=data["process_id"],
                    workplace_ids=data["workplace_ids"],
                    all_workplaces=bool(data["all_mode"]),
                )
                self._question_id = created.id
                self.setWindowTitle(EXTRAORDINARY_QUESTION_EDITOR_TITLE_EDIT)
                configure_editor_close_button(self._close_btn, is_new=False)
            else:
                current_ids = set(data["workplace_ids"])
                existing = dict(self._existing_targets)
                add_ids = [wid for wid in current_ids if wid not in existing]
                restore_ids = [
                    wid
                    for wid in current_ids
                    if existing.get(wid) == EXTRAORDINARY_TARGET_STATUS_CANCELLED
                ]
                cancel_ids = [
                    wid
                    for wid, status in existing.items()
                    if wid not in current_ids
                    and status == EXTRAORDINARY_TARGET_STATUS_PENDING
                ]
                for wid, status in existing.items():
                    if is_target_locked(status) and wid not in current_ids:
                        raise AuditExtraordinaryError(
                            "Cíl Přiřazeno/Ověřeno nelze odškrtnout."
                        )
                audit_extraordinary_question_service.update_question(
                    self._question_id,
                    question_text=data["question_text"],
                    assigned_by=data["assigned_by"],
                    assigned_on=data["assigned_on"],
                    note=data["note"],
                    severity=data["severity"],
                    process_id=data["process_id"],
                    add_workplace_ids=add_ids,
                    cancel_workplace_ids=cancel_ids,
                    restore_workplace_ids=restore_ids,
                )
            # Reload targets after save
            _q, targets = audit_extraordinary_question_service.get_question(
                self._question_id
            )
            self._existing_targets = {
                int(item.workplace_id): str(item.status or "") for item in targets
            }
            self._load_workplaces()
            self._load_question()
            self._capture_baseline()
            return True
        except AuditExtraordinaryError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return False
        except Exception as exc:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                f"Uložení se nezdařilo.\n\n{exc}",
            )
            return False

    def _save_keep_open(self) -> None:
        self._persist()

    def _save_and_close(self) -> None:
        if self._persist():
            self._done_accept()

    def _done_accept(self) -> None:
        self._closing = True
        QDialog.accept(self)

    def _done_reject(self) -> None:
        self._closing = True
        QDialog.reject(self)

    def _request_close(self) -> None:
        if self._confirm_close():
            self._done_reject()

    def _confirm_close(self) -> bool:
        if self._closing or not self._is_dirty():
            return True
        decision = confirm_unsaved_editor_close(self, title=self.windowTitle())
        if decision == "cancel":
            return False
        if decision == "save":
            if not self._persist():
                return False
            self._done_accept()
            return False
        return True

    def reject(self) -> None:
        if self._closing:
            QDialog.reject(self)
            return
        if self._confirm_close():
            self._done_reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing or self._confirm_close():
            event.accept()
            return
        event.ignore()

    @property
    def question_id(self) -> int | None:
        return self._question_id
