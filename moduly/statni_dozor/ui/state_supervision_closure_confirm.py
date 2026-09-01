"""Potvrzení uzavření kontroly s nevyřešenými zjištěními nebo úkoly."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from core.widgets.editor_dialog_controller import (
    EDITOR_CANCEL_LABEL,
    configure_editor_close_button,
)
from moduly.statni_dozor.constants import (
    ACTION_CONFIRM_CLOSE_SUPERVISION,
    CLOSURE_WARNING_ACTIVE_TASKS,
    CLOSURE_WARNING_FOOTER,
    CLOSURE_WARNING_INTRO,
    CLOSURE_WARNING_MISSING_TASKS,
    CLOSURE_WARNING_OPEN_FINDINGS,
    MODULE_NAME,
)
from moduly.statni_dozor.sluzby.state_supervision_closure_readiness import (
    StateSupervisionClosureReadiness,
)


def format_closure_warning_text(readiness: StateSupervisionClosureReadiness) -> str:
    lines = [CLOSURE_WARNING_INTRO]
    rows = (
        (readiness.open_findings_count, CLOSURE_WARNING_OPEN_FINDINGS),
        (readiness.active_tasks_count, CLOSURE_WARNING_ACTIVE_TASKS),
        (readiness.missing_tasks_count, CLOSURE_WARNING_MISSING_TASKS),
    )
    for count, label in rows:
        if count:
            lines.append(f"– {label}: {count}")
    lines.append("")
    lines.append(CLOSURE_WARNING_FOOTER)
    return "\n".join(lines)


def confirm_supervision_closure(
    parent: QWidget | None,
    readiness: StateSupervisionClosureReadiness,
) -> bool:
    """True = uživatel chce kontrolu přesto uzavřít. Zrušit / Escape = False."""
    box = QMessageBox(parent)
    box.setWindowTitle(MODULE_NAME)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText(format_closure_warning_text(readiness))
    close_btn = box.addButton(
        ACTION_CONFIRM_CLOSE_SUPERVISION,
        QMessageBox.ButtonRole.ActionRole,
    )
    cancel_btn = box.addButton(
        EDITOR_CANCEL_LABEL,
        QMessageBox.ButtonRole.ActionRole,
    )
    configure_editor_close_button(cancel_btn, is_new=True)
    box.setDefaultButton(cancel_btn)
    box.setEscapeButton(cancel_btn)
    box.exec()
    return box.clickedButton() is close_btn
