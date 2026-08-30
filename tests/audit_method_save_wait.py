"""Čekání na asynchronní uložení editoru auditní metodiky (bez sleep)."""

from __future__ import annotations

from PySide6.QtCore import QEventLoop, QTimer


def wait_for_audit_method_save(dialog, *, timeout_ms: int = 15000) -> None:
    """Počká na dokončení ``_start_save`` včetně GUI epilogu a cleanupu runneru."""
    if not getattr(dialog, "_save_busy", False):
        return

    loop = QEventLoop()
    runner = getattr(dialog, "_save_runner", None)

    def _quit() -> None:
        if loop.isRunning():
            loop.quit()

    if runner is not None:
        runner.finished.connect(lambda: QTimer.singleShot(0, _quit))
    poll = QTimer()
    poll.timeout.connect(lambda: None if dialog._save_busy else _quit())
    poll.start(15)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(_quit)
    timeout.start(timeout_ms)
    loop.exec()
    poll.stop()
    timeout.stop()
    if getattr(dialog, "_save_busy", False):
        raise AssertionError("Ukládání auditní metodiky neskončilo včas.")
