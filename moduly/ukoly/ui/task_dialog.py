from datetime import date, timedelta
from collections.abc import Callable
from typing import Any

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import (
    ENTITY_ACCIDENT,
    ENTITY_AUDITY,
    ENTITY_MU_INVESTIGATION,
    ENTITY_STATE_SUPERVISION,
)
from core.navigation.source_navigator import (
    ACCIDENT_OPEN_ADMINISTRATION,
    ACCIDENT_OPEN_RECORD,
    source_navigator,
)
from core.shared.sluzby.finding_task_service import finding_task_service
from core.shared.task_source_display import task_source_label, task_type_label
from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.dialog_utils import configure_resizable_form_dialog, wrap_in_scroll_area
from core.widgets.editor_dialog_controller import (
    EDITOR_CLOSE_LABEL,
    EDITOR_SAVE_LABEL,
    configure_editor_close_button,
    configure_editor_save_button,
    confirm_unsaved_editor_close,
)
from core.widgets.task_finding_source_panel import TaskFindingSourcePanel
from moduly.kniha_urazu.sluzby.accident_reporting_task_service import (
    is_accident_reporting_task_title,
)
from moduly.ukoly.constants import TASK_TYPE_INVESTIGATION_ACTION
from moduly.ukoly.sluzby.task_service import task_service
from core.widgets.date_edit import DateEdit
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector
from core.widgets.workplace_selector import WorkplaceSelector

_SAVE_CLOSE_LABEL = "Uložit a zavřít"
_ATTACHMENTS_INFO = "Přílohy lze přidat až po prvním uložení opatření."

TASK_EDITOR_TITLE = "Úkol"
TASK_EDITOR_TITLE_FINDING = "Nápravné opatření"
TASK_EDITOR_TITLE_INVESTIGATION = "Vyšetřovací úkon"


def resolve_task_editor_window_title(
    *,
    window_title: str | None = None,
    is_investigation_action: bool = False,
    has_finding: bool = False,
) -> str:
    """Titul okna editoru: běžný úkol vs. kontext finding / vyšetřovací úkon."""
    explicit = (window_title or "").strip()
    if explicit:
        return explicit
    if is_investigation_action:
        return TASK_EDITOR_TITLE_INVESTIGATION
    if has_finding:
        return TASK_EDITOR_TITLE_FINDING
    return TASK_EDITOR_TITLE


class TaskDialog(QDialog):
    """Editor úkolu / opatření se stay-open ukládáním (AGENDA-TASK-UX-6)."""

    def __init__(
        self,
        parent=None,
        task=None,
        *,
        create_kwargs: dict | None = None,
        create_factory: Callable[[dict], Any] | None = None,
        persist_handler: Callable[[Any | None, dict], Any] | None = None,
        window_title: str | None = None,
        fixed_priority: str | None = None,
        source_finding: Any | None = None,
    ):
        super().__init__(parent)

        self.task = task
        self._create_kwargs = dict(create_kwargs or {})
        self._create_factory = create_factory
        self._persist_handler = persist_handler
        self._fixed_priority = str(fixed_priority or "").strip() or None
        self._baseline: object | None = None
        self._closing = False
        self._attachments_info_label: QLabel | None = None
        self._finding = finding_task_service.get_finding_for_task(task) if task is not None else None
        # U odloženého úkolu (temp id < 0) načíst finding ze source_record_id.
        if self._finding is None and task is not None and getattr(task, "id", 0) and int(task.id) < 0:
            source_id = getattr(task, "source_record_id", None)
            if source_id:
                from core.shared.sluzby.finding_service import finding_service

                self._finding = finding_service.get_by_id(int(source_id))
        if self._finding is None and source_finding is not None:
            self._finding = source_finding
        self._is_investigation_action = (
            task is not None
            and getattr(task, "task_type", "") == TASK_TYPE_INVESTIGATION_ACTION
        )

        self.setWindowTitle(
            resolve_task_editor_window_title(
                window_title=window_title,
                is_investigation_action=self._is_investigation_action,
                has_finding=self._finding is not None,
            )
        )
        configure_resizable_form_dialog(self, width=720, height=640, min_width=520, min_height=420)

        main_layout = QVBoxLayout(self)

        if self._finding is not None:
            self.source_panel = TaskFindingSourcePanel()
            source_task = task
            if source_task is None:
                from types import SimpleNamespace

                from core.shared.constants import ENTITY_FINDING

                source_task = SimpleNamespace(
                    source_module=ENTITY_FINDING,
                    source_record_id=self._finding.id,
                )
            self.source_panel.set_content(
                task_source_label(source_task),
                self._finding.description,
            )
            if self._should_show_source_open_button():
                self.source_panel.open_button.clicked.connect(self._open_source_record)
            else:
                self.source_panel.open_button.setVisible(False)
            main_layout.addWidget(self.source_panel)
        elif (
            task is not None
            and task.source_module == ENTITY_MU_INVESTIGATION
            and task.source_record_id
        ):
            self.source_panel = TaskFindingSourcePanel()
            self.source_panel.set_content(
                task_source_label(task),
                (task.description or "").strip(),
            )
            if source_navigator.can_open(ENTITY_MU_INVESTIGATION, task.source_record_id):
                self.source_panel.open_button.clicked.connect(self._open_mu_investigation)
            else:
                self.source_panel.open_button.setVisible(False)
            main_layout.addWidget(self.source_panel)
        elif (
            task is not None
            and task.source_module == ENTITY_ACCIDENT
            and task.source_record_id
        ):
            self.source_panel = TaskFindingSourcePanel()
            self.source_panel.set_content(
                task_source_label(task),
                (task.description or "").strip(),
            )
            if source_navigator.can_open(ENTITY_ACCIDENT, task.source_record_id):
                self.source_panel.open_button.clicked.connect(self._open_accident_source)
            else:
                self.source_panel.open_button.setVisible(False)
            main_layout.addWidget(self.source_panel)

        tab_title = "Úkon" if self._is_investigation_action else "Opatření"
        self.tabs = QTabWidget()
        self.tabs.addTab(wrap_in_scroll_area(self._main_tab()), tab_title)
        self.tabs.addTab(wrap_in_scroll_area(self._attachments_tab()), "Přílohy")

        main_layout.addWidget(self.tabs, 1)
        main_layout.addLayout(self._build_footer())

        self.completed_checkbox.stateChanged.connect(self._completed_changed)
        self.requires_verification_checkbox.stateChanged.connect(self._verification_changed)
        self.canceled_checkbox.stateChanged.connect(self._refresh_status)
        self.checked_date_edit.dateChanged.connect(self._refresh_status)
        self.checked_by_selector.currentIndexChanged.connect(self._refresh_status)

        if task is not None:
            self.title_edit.setPlainText(task.title)
            self.priority_combo.setCurrentText(task.priority)
            if task.due_date:
                self.due_date_edit.set_date_iso(task.due_date.isoformat())
            self.remind_from_edit.set_date_value(getattr(task, "remind_from", None))
            self.person_selector.set_person_id(task.responsible_person_id)
            self.workplace_selector.set_workplace_id(task.workplace_id)

            self.completed_checkbox.setChecked(task.completed)
            self.completed_date_edit.set_date_value(task.completed_date)
            self.requires_verification_checkbox.setChecked(task.requires_verification)
            self.check_due_date_edit.set_date_value(task.check_due_date)
            self.checked_date_edit.set_date_value(task.checked_date)
            self.checked_by_selector.set_person_id(task.checked_by_id)
            self.canceled_checkbox.setChecked(task.canceled)
            note_text = task.note or ""
            if self._is_investigation_action and not note_text.strip():
                note_text = task.description or ""
            self.note_edit.setPlainText(note_text)

        self._verification_changed()
        self._refresh_status()
        self._apply_fixed_priority()
        self._capture_baseline()

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addStretch(1)

        self._save_btn = QPushButton()
        configure_editor_save_button(self._save_btn)
        self._save_btn.setText(EDITOR_SAVE_LABEL)

        self._save_close_btn = QPushButton(_SAVE_CLOSE_LABEL)
        configure_editor_save_button(self._save_close_btn)
        self._save_close_btn.setText(_SAVE_CLOSE_LABEL)

        self._close_btn = QPushButton()
        configure_editor_close_button(self._close_btn, is_new=False)
        self._close_btn.setText(EDITOR_CLOSE_LABEL)

        for button in (self._save_btn, self._save_close_btn, self._close_btn):
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._save_btn.clicked.connect(self._save_keep_open)
        self._save_close_btn.clicked.connect(self._save_and_close)
        self._close_btn.clicked.connect(self._request_close)

        footer.addWidget(self._save_btn)
        footer.addWidget(self._save_close_btn)
        footer.addWidget(self._close_btn)
        return footer

    def _apply_fixed_priority(self) -> None:
        if not self._fixed_priority:
            return
        self.priority_combo.setCurrentText(self._fixed_priority)
        self.priority_combo.setEnabled(False)

    def _capture_baseline(self) -> None:
        self._baseline = self.get_data()

    def _is_dirty(self) -> bool:
        return self.get_data() != self._baseline

    def _save_keep_open(self) -> None:
        self._persist()

    def _save_and_close(self) -> None:
        if self._persist():
            self._closing = True
            self.accept()

    def _persist(self) -> bool:
        data = self.get_data()
        if not data["title"]:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Zadejte text opatření / úkolu.",
            )
            return False

        remind_error = task_service.validate_remind_from(
            data.get("remind_from"),
            data.get("due_date"),
        )
        if remind_error:
            QMessageBox.warning(self, self.windowTitle(), remind_error)
            return False

        if self._persist_handler is not None:
            result = self._persist_handler(self.task, data)
            if result is False:
                return False
            if result is not None and result is not True:
                self.task = result
            self._capture_baseline()
            return True

        if self.task is None:
            if self._create_factory is not None:
                self.task = self._create_factory(data)
                if self.task is None:
                    return False
                # Factory často nepropisuje remind_from — doplnit bez přepsání ostatních polí.
                if getattr(self.task, "remind_from", None) != data.get("remind_from"):
                    task_service.update_task(
                        task_id=self.task.id,
                        title=self.task.title,
                        description=self.task.description or "",
                        priority=self.task.priority or "Normální",
                        due_date=self.task.due_date,
                        remind_from=data.get("remind_from"),
                        responsible_person_id=self.task.responsible_person_id,
                        workplace_id=self.task.workplace_id,
                        completed=bool(self.task.completed),
                        completed_date=self.task.completed_date,
                        requires_verification=bool(self.task.requires_verification),
                        check_due_date=self.task.check_due_date,
                        checked_date=self.task.checked_date,
                        checked_by_id=self.task.checked_by_id,
                        canceled=bool(self.task.canceled),
                        note=self.task.note or "",
                    )
                    refreshed = task_service.get_task_by_id(self.task.id)
                    if refreshed is not None:
                        self.task = refreshed
            else:
                self.task = task_service.create_task(**data, **self._create_kwargs)
            if self.task is None:
                return False
            self._activate_attachments(self.task.id)
        else:
            task_service.update_task(task_id=self.task.id, **data)
            refreshed = task_service.get_task_by_id(self.task.id)
            if refreshed is not None:
                self.task = refreshed

        self._capture_baseline()
        return True

    def _activate_attachments(self, task_id: int) -> None:
        self.attachment_widget.set_entity("task", task_id)
        if self._attachments_info_label is not None:
            self._attachments_info_label.setVisible(False)

    def _request_close(self) -> None:
        if self._confirm_close():
            self._closing = True
            self.reject()

    def _confirm_close(self) -> bool:
        if self._closing or not self._is_dirty():
            return True
        decision = confirm_unsaved_editor_close(self, title=self.windowTitle())
        if decision == "cancel":
            return False
        if decision == "save":
            if not self._persist():
                return False
            self._closing = True
            self.accept()
            return False
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_close():
            self._closing = True
            event.accept()
        else:
            event.ignore()

    def reject(self) -> None:
        if self._confirm_close():
            self._closing = True
            super().reject()

    def _should_show_source_open_button(self) -> bool:
        if self._finding is None:
            return False
        if not source_navigator.can_open(self._finding.entity_type, self._finding.entity_id):
            return False
        if self._finding.entity_type in {
            ENTITY_AUDITY,
            ENTITY_STATE_SUPERVISION,
        } and self._is_opened_from_modal_parent():
            return False
        return True

    def _is_opened_from_modal_parent(self) -> bool:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QDialog):
                return True
            parent = parent.parentWidget()
        return False

    def _open_source_record(self) -> None:
        if self._finding is None:
            return

        if not source_navigator.open(self._finding.entity_type, self._finding.entity_id):
            QMessageBox.warning(
                self,
                "Navigace",
                "Zdrojový záznam se nepodařilo otevřít.",
            )

    def _open_mu_investigation(self) -> None:
        if self.task is None or self.task.source_record_id is None:
            return

        if not source_navigator.open(ENTITY_MU_INVESTIGATION, self.task.source_record_id):
            QMessageBox.warning(
                self,
                "Navigace",
                "Vyšetřování se nepodařilo otevřít.",
            )

    def _open_accident_source(self) -> None:
        if self.task is None or self.task.source_record_id is None:
            return

        target = ACCIDENT_OPEN_RECORD
        if is_accident_reporting_task_title(self.task.title or ""):
            target = ACCIDENT_OPEN_ADMINISTRATION

        if not source_navigator.open(
            ENTITY_ACCIDENT,
            self.task.source_record_id,
            accident_target=target,
        ):
            QMessageBox.warning(
                self,
                "Navigace",
                "Pracovní úraz se nepodařilo otevřít.",
            )

    def _main_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.title_edit = QTextEdit()
        self.title_edit.setPlaceholderText("Popište stanovené opatření / úkol.")
        self.title_edit.setFixedHeight(95)

        self.person_selector = ThpWorkerSelector()

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Nízká", "Normální", "Vysoká", "Kritická"])
        self.priority_combo.setCurrentText("Normální")

        self.due_date_edit = DateEdit()

        self.remind_from_edit = NullableDateEdit()
        _remind_hint = (
            "Od tohoto data se úkol zobrazí na Pracovní ploše\nv části Připomínky."
        )
        self.remind_from_edit.setToolTip(_remind_hint)
        self.remind_from_hint = QLabel(_remind_hint)
        self.remind_from_hint.setWordWrap(True)
        self.remind_from_hint.setStyleSheet("color: #666;")

        self.completed_checkbox = QCheckBox("Opatření splněno")
        self.completed_date_edit = NullableDateEdit()

        self.workplace_selector = WorkplaceSelector()

        self.requires_verification_checkbox = QCheckBox("Vyžaduje kontrolu účinnosti opatření")

        self.check_due_date_edit = NullableDateEdit()
        self.checked_date_edit = NullableDateEdit()
        self.checked_by_selector = ThpWorkerSelector()

        self.canceled_checkbox = QCheckBox("Opatření zrušeno / netrvá")

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("Poznámka, zjištěné závady nebo výsledek kontroly.")

        self.status_label = QLabel("Aktivní")
        self.type_label = QLabel(task_type_label(self.task) if self.task is not None else "Nápravné opatření")

        layout.addRow("Typ:", self.type_label)
        layout.addRow("Opatření:", self.title_edit)
        layout.addRow("Odpovídá:", self.person_selector)
        layout.addRow("Priorita:", self.priority_combo)
        layout.addRow("Termín splnění:", self.due_date_edit)
        layout.addRow("Připomenout od:", self.remind_from_edit)
        layout.addRow("", self.remind_from_hint)
        layout.addRow("Splnění:", self.completed_checkbox)
        layout.addRow("Splněno dne:", self.completed_date_edit)
        layout.addRow("Pracoviště:", self.workplace_selector)
        layout.addRow("Kontrolovat:", self.requires_verification_checkbox)
        layout.addRow("Kontrola do:", self.check_due_date_edit)
        layout.addRow("Datum kontroly:", self.checked_date_edit)
        layout.addRow("Kontroloval:", self.checked_by_selector)
        layout.addRow("Zrušeno:", self.canceled_checkbox)
        layout.addRow("Stav:", self.status_label)
        layout.addRow("Poznámka / zjištěné závady:", self.note_edit)

        return tab

    def _attachments_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        entity_id = self.task.id if self.task is not None else None
        if entity_id is not None and int(entity_id) < 0:
            entity_id = None
        self.attachment_widget = AttachmentWidget("task", entity_id)

        if entity_id is None:
            self._attachments_info_label = QLabel(_ATTACHMENTS_INFO)
            layout.addWidget(self._attachments_info_label)

        layout.addWidget(self.attachment_widget)
        return tab

    def _completed_changed(self):
        if self.completed_checkbox.isChecked():
            if not self.completed_date_edit.has_date():
                today = date.today()
                self.completed_date_edit.set_date_value(today)

            if self.requires_verification_checkbox.isChecked() and not self.check_due_date_edit.has_date():
                completed_date = self.completed_date_edit.get_date() or date.today()
                self.check_due_date_edit.set_date_value(completed_date + timedelta(days=15))
        else:
            self.completed_date_edit.clear_date()
            self.check_due_date_edit.clear_date()
            self.checked_date_edit.clear_date()
            self.checked_by_selector.set_person_id(None)

        self._refresh_status()

    def _verification_changed(self):
        enabled = self.requires_verification_checkbox.isChecked()

        self.check_due_date_edit.setEnabled(enabled)
        self.checked_date_edit.setEnabled(enabled)
        self.checked_by_selector.setEnabled(enabled)

        if not enabled:
            self.check_due_date_edit.clear_date()
            self.checked_date_edit.clear_date()
            self.checked_by_selector.set_person_id(None)
        elif self.completed_checkbox.isChecked() and not self.check_due_date_edit.has_date():
            completed_date = self.completed_date_edit.get_date() or date.today()
            self.check_due_date_edit.set_date_value(completed_date + timedelta(days=15))

        self._refresh_status()

    def _refresh_status(self):
        if self.canceled_checkbox.isChecked():
            self.status_label.setText("Zrušeno")
        elif self.completed_checkbox.isChecked():
            if not self.requires_verification_checkbox.isChecked():
                self.status_label.setText("Ukončeno")
            elif self.checked_date_edit.has_date():
                self.status_label.setText("Ukončeno")
            else:
                self.status_label.setText("Splněno - čeká na kontrolu")
        else:
            self.status_label.setText("Aktivní")

    def get_data(self) -> dict:
        qdate = self.due_date_edit.date()
        due_date = date(qdate.year(), qdate.month(), qdate.day())

        requires_verification = self.requires_verification_checkbox.isChecked()

        data = {
            "title": self.title_edit.toPlainText().strip(),
            "description": "",
            "priority": self.priority_combo.currentText(),
            "due_date": due_date,
            "remind_from": self.remind_from_edit.get_date(),
            "responsible_person_id": self.person_selector.current_person_id(),
            "workplace_id": self.workplace_selector.current_workplace_id(),
            "completed": self.completed_checkbox.isChecked(),
            "completed_date": self.completed_date_edit.get_date() if self.completed_checkbox.isChecked() else None,
            "requires_verification": requires_verification,
            "check_due_date": self.check_due_date_edit.get_date() if requires_verification else None,
            "checked_date": self.checked_date_edit.get_date() if requires_verification else None,
            "checked_by_id": self.checked_by_selector.current_person_id() if requires_verification else None,
            "canceled": self.canceled_checkbox.isChecked(),
            "note": self.note_edit.toPlainText().strip(),
        }
        if self._fixed_priority:
            data["priority"] = self._fixed_priority
        return data
