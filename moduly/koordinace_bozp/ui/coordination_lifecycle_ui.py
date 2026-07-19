"""Sdílené UI přechodů životního cyklu koordinace (UX-COORD-6b)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QMessageBox, QWidget

from moduly.koordinace_bozp.constants import DIALOG_WINDOW_TITLE
from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
    CoordinationLifecycleBlocked,
    CoordinationLifecycleError,
    CoordinationLifecycleNeedsConfirmation,
    LifecycleAction,
    coordination_lifecycle_service,
    lifecycle_confirm_message,
)


def run_lifecycle_transition(
    parent: QWidget,
    coordination_id: int,
    action: LifecycleAction,
    *,
    before_transition: Callable[[], bool] | None = None,
) -> BozpCoordination | None:
    """Provede přechod s potvrzením uživatele a validací builderem.

    Returns:
        Aktualizovaná koordinace, nebo None při zrušení / chybě.
    """
    answer = QMessageBox.question(
        parent,
        DIALOG_WINDOW_TITLE,
        lifecycle_confirm_message(action.action_id),
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if answer != QMessageBox.Yes:
        return None

    if before_transition is not None and not before_transition():
        return None

    confirm_warnings = False
    confirm_sensitive = False
    while True:
        try:
            return coordination_lifecycle_service.transition(
                coordination_id,
                action.target_status,
                confirm_warnings=confirm_warnings,
                confirm_sensitive=confirm_sensitive,
            )
        except CoordinationLifecycleBlocked as error:
            QMessageBox.warning(parent, DIALOG_WINDOW_TITLE, str(error))
            return None
        except CoordinationLifecycleNeedsConfirmation as error:
            answer = QMessageBox.question(
                parent,
                DIALOG_WINDOW_TITLE,
                str(error),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return None
            if error.sensitive:
                confirm_sensitive = True
            else:
                confirm_warnings = True
        except CoordinationLifecycleError as error:
            QMessageBox.warning(parent, DIALOG_WINDOW_TITLE, str(error))
            return None
