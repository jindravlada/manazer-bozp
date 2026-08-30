"""Dialog průběhu dlouhé operace — pouze zobrazení, bez doménové práce.

Zobrazí se až po nastavitelné prodlevě (výchozí 300 ms). Skončí-li operace
dřív, dialog se neukáže a po dokončení neblikne.

Zavření a Escape:

- zrušitelná fáze → ``request_cancel`` (vlákno se neukončuje násilně),
- atomická fáze → zavření se odmítne, tlačítko Zrušit je neaktivní.

Nepoužívá ``exec()``: zpožděné zobrazení je neslučitelné s okamžitým
modálním ``exec()``. Modalita je ``WindowModal`` vůči rodiči.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from core.widgets.long_operation_runner import LongOperationRunner

DEFAULT_DELAY_MS = 300


class LongOperationDialog(QDialog):
    """Parent-modální průběh napojený na ``LongOperationRunner``."""

    presented = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str,
        runner: LongOperationRunner,
        delay_ms: int = DEFAULT_DELAY_MS,
        allow_cancel: bool = True,
    ) -> None:
        super().__init__(parent)
        self._runner = runner
        self._delay_ms = max(0, int(delay_ms))
        self._allow_cancel = bool(allow_cancel)
        self._settled = False
        self._presented = False
        self._atomic = False
        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._present)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(
            self,
            width=520,
            height=200,
            min_width=420,
            min_height=160,
        )

        layout = QVBoxLayout(self)
        self._phase_label = QLabel("Připravuji…")
        self._phase_label.setWordWrap(True)
        layout.addWidget(self._phase_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._count_label = QLabel("")
        self._count_label.setWordWrap(True)
        layout.addWidget(self._count_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self._cancel_btn = QPushButton("Zrušit")
        self._cancel_btn.setVisible(self._allow_cancel)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        buttons.addWidget(self._cancel_btn)
        layout.addLayout(buttons)

        runner.started.connect(self._on_started)
        runner.phase_changed.connect(self._on_phase_changed)
        runner.progress_changed.connect(self._on_progress_changed)
        runner.succeeded.connect(self._on_settled)
        runner.cancelled.connect(self._on_settled)
        runner.failed.connect(self._on_settled)
        runner.finished.connect(self._on_settled)

        if runner.is_running():
            self._on_started()

    def delay_ms(self) -> int:
        return self._delay_ms

    def was_presented(self) -> bool:
        """True, pokud se dialog skutečně ukázal (pro testy i diagnostiku)."""
        return self._presented

    def _on_started(self) -> None:
        self._settled = False
        self._presented = False
        self._atomic = False
        self._phase_label.setText("Připravuji…")
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setValue(0)
        self._count_label.setText("")
        self._update_cancel_enabled()
        self._show_timer.stop()
        self._show_timer.start(self._delay_ms)

    def _present(self) -> None:
        if self._settled or self._presented:
            return
        if not self._runner.is_running():
            return
        self._presented = True
        self.show()
        self.presented.emit()

    def _on_phase_changed(self, text: str, indeterminate: bool, atomic: bool) -> None:
        if self._settled:
            return
        self._phase_label.setText(text)
        self._atomic = bool(atomic)
        if indeterminate:
            self._progress_bar.setRange(0, 0)
            self._count_label.setText("")
        self._update_cancel_enabled()

    def _on_progress_changed(self, current: int, total: int) -> None:
        if self._settled:
            return
        if total <= 0:
            self._progress_bar.setRange(0, 0)
            self._count_label.setText("")
            return
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(min(max(current, 0), total))
        self._count_label.setText(f"{current} / {total}")

    def _update_cancel_enabled(self) -> None:
        can_cancel = (
            self._allow_cancel
            and not self._atomic
            and self._runner.is_running()
            and not self._settled
        )
        self._cancel_btn.setEnabled(can_cancel)

    def _on_cancel_clicked(self) -> None:
        if self._atomic or not self._allow_cancel:
            return
        self._cancel_btn.setEnabled(False)
        self._runner.request_cancel()

    def _on_settled(self, *_args) -> None:
        self._settle()

    def _settle(self) -> None:
        self._settled = True
        self._atomic = False
        self._show_timer.stop()
        self._cancel_btn.setEnabled(False)
        if self._presented and self.isVisible():
            self.hide()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._settled:
            event.accept()
            return
        if self._atomic:
            event.ignore()
            return
        if self._allow_cancel and self._runner.is_running():
            self._runner.request_cancel()
            event.ignore()
            return
        event.ignore()

    def reject(self) -> None:
        if self._settled:
            super().reject()
            return
        if self._atomic:
            return
        if self._allow_cancel and self._runner.is_running():
            self._runner.request_cancel()
            return

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
