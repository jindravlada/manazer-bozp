"""Fullscreen obrazovka elektronické písemné části.

Uzamčení se týká okna Manažera, ne operačního systému. Escape, zavření
okna ani menu Manažera test neukončí. Vývojové opuštění není autorizace
administrátora a zapíná se jen proměnnou prostředí.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from moduly.testy.constants import (
    WRITTEN_FINISHED_TEXT,
    WRITTEN_NEXT,
    WRITTEN_PREVIOUS,
    WRITTEN_SUBMIT,
    WRITTEN_SUBMIT_CONFIRM,
    WRITTEN_SUBMIT_INCOMPLETE,
)
from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service
from moduly.testy.sluzby.written_exam_service import (
    WrittenExamClock,
    WrittenExamClosed,
    format_remaining_label,
    remaining_written_seconds,
    step_question_index,
    written_exam_dev_exit_enabled,
    written_exam_service,
)

_QUESTION_IMAGE_MAX = (720, 400)
_ANSWER_IMAGE_MAX = (360, 220)


class _BoundedScroll(QScrollArea):
    """Obsah otázky se roluje, patička s navigací zůstane na místě."""

    def minimumSizeHint(self) -> QSize:
        return QSize(160, 80)

    def sizeHint(self) -> QSize:
        return QSize(640, 360)


def fit_pixmap(pixmap: QPixmap, max_width: int, max_height: int) -> QPixmap:
    if pixmap.isNull():
        return pixmap
    if pixmap.width() <= max_width and pixmap.height() <= max_height:
        return pixmap
    return pixmap.scaled(
        max_width,
        max_height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class WrittenExamWindow(QDialog):
    def __init__(self, exam_id: int, parent=None, *, clock=None):
        super().__init__(parent)
        self.exam_id = int(exam_id)
        self.clock = clock or WrittenExamClock()
        self._host = parent.window() if parent is not None else None
        self._close_allowed = False
        self._phase = "running"
        self._index = 0
        self._screen = written_exam_service.screen(self.exam_id)
        self._nav_buttons: list[QPushButton] = []
        self._answer_group = QButtonGroup(self)
        self._answer_group.setExclusive(True)

        self.setObjectName("written-exam-window")
        self.setWindowTitle(self._screen.test_name)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setMinimumSize(960, 640)

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._on_tick)
        self._build()
        self._rebuild_navigation()
        self._show_question(0)
        if self._screen.finished:
            self._show_finished()
        elif self._phase == "running":
            self._timer.start()

    def enter_testing_mode(self) -> None:
        self._lock_host(True)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowFullScreen)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def show_at(self, width: int, height: int) -> None:
        self.resize(width, height)
        self.show()
        QApplication.processEvents()

    def release_testing_lock(self) -> None:
        """Interní cesta pro vývoj a testy. Není zabezpečení administrátora."""
        self._close_allowed = True
        if self._timer.isActive():
            self._timer.stop()
        self._lock_host(False)
        self.close()

    def submit_test(self) -> None:
        if self._phase != "running":
            return
        now = self.clock.now()
        if self._deadline_reached(now):
            return
        if written_exam_service.unanswered_count(self.exam_id):
            text = WRITTEN_SUBMIT_INCOMPLETE
        else:
            text = WRITTEN_SUBMIT_CONFIRM
        answer = QMessageBox.question(
            self,
            WRITTEN_SUBMIT,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._commit_finish(now)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)

    def event(self, event: QEvent) -> bool:  # noqa: N802
        if (
            event.type() == QEvent.Type.ShortcutOverride
            and isinstance(event, QKeyEvent)
            and event.key() == Qt.Key.Key_Escape
        ):
            event.accept()
            return True
        return super().event(event)

    def reject(self) -> None:  # noqa: N802
        return

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._close_allowed:
            event.ignore()
            return
        event.accept()
        self.hide()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        self._running = QWidget()
        running = QVBoxLayout(self._running)
        running.setContentsMargins(0, 0, 0, 0)
        running.setSpacing(8)

        header = QWidget()
        header.setObjectName("written-exam-header")
        header.setFixedHeight(72)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel(self._screen.test_name)
        self.title_label.setObjectName("written-exam-title")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        self.employee_label = QLabel(self._screen.employee_display_name)
        self.employee_label.setObjectName("written-exam-employee")
        self.employee_label.setWordWrap(True)
        self.employee_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.employee_label.setStyleSheet("font-size: 16px;")
        self.remaining_label = QLabel("Zbývá: 00:00")
        self.remaining_label.setObjectName("written-exam-remaining")
        self.remaining_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.remaining_label.setStyleSheet(
            "font-size: 22px; font-weight: 700; font-family: monospace;"
        )
        self.remaining_label.setMinimumWidth(180)
        header_layout.addWidget(self.title_label, 1)
        header_layout.addWidget(self.employee_label, 1)
        header_layout.addWidget(self.remaining_label)
        running.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(12)
        self._nav_scroll = _BoundedScroll()
        self._nav_scroll.setWidgetResizable(True)
        self._nav_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._nav_scroll.setFixedWidth(104)
        self._nav_scroll.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        self._nav_host = QWidget()
        self._nav_layout = QVBoxLayout(self._nav_host)
        self._nav_layout.setContentsMargins(0, 0, 0, 0)
        self._nav_layout.setSpacing(6)
        self._nav_scroll.setWidget(self._nav_host)
        self._nav_host.setStyleSheet(
            """
            QPushButton[current="true"] {
                background-color: #1d4ed8;
                color: white;
                font-weight: 700;
            }
            QPushButton[answered="true"][current="false"] {
                background-color: #dcfce7;
                color: #14532d;
                font-weight: 700;
            }
            QPushButton[answered="false"][current="false"] {
                background-color: #f5f5f4;
                color: #44403c;
            }
            """
        )

        self._question_scroll = _BoundedScroll()
        self._question_scroll.setWidgetResizable(True)
        self._question_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._question_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        body.addWidget(self._nav_scroll)
        body.addWidget(self._question_scroll, 1)
        running.addLayout(body, 1)

        footer = QWidget()
        footer.setObjectName("written-exam-footer")
        footer.setFixedHeight(64)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        self.prev_button = QPushButton(WRITTEN_PREVIOUS)
        self.prev_button.setObjectName("written-exam-prev")
        self.next_button = QPushButton(WRITTEN_NEXT)
        self.next_button.setObjectName("written-exam-next")
        self.submit_button = QPushButton(WRITTEN_SUBMIT)
        self.submit_button.setObjectName("written-exam-submit")
        for button in (self.prev_button, self.next_button, self.submit_button):
            button.setAutoDefault(False)
            button.setDefault(False)
            button.setMinimumHeight(44)
        self.prev_button.setMinimumWidth(120)
        self.next_button.setMinimumWidth(120)
        self.submit_button.setMinimumWidth(180)
        self.submit_button.setStyleSheet(
            "QPushButton { background: #b45309; color: white; font-weight: 700;"
            " padding: 8px 16px; font-size: 16px; }"
        )
        self.prev_button.clicked.connect(self._go_previous)
        self.next_button.clicked.connect(self._go_next)
        self.submit_button.clicked.connect(self.submit_test)
        footer_layout.addWidget(self.prev_button)
        footer_layout.addWidget(self.next_button)
        footer_layout.addStretch()
        footer_layout.addWidget(self.submit_button)
        running.addWidget(footer)

        self._finished = QLabel(WRITTEN_FINISHED_TEXT)
        self._finished.setObjectName("written-exam-finished")
        self._finished.setWordWrap(True)
        self._finished.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._finished.setStyleSheet("font-size: 28px; font-weight: 600;")
        finished_page = QWidget()
        finished_layout = QVBoxLayout(finished_page)
        finished_layout.addStretch()
        finished_layout.addWidget(self._finished)
        finished_layout.addStretch()

        self._stack = QStackedWidget()
        self._stack.addWidget(self._running)
        self._stack.addWidget(finished_page)
        root.addWidget(self._stack, 1)

        if written_exam_dev_exit_enabled():
            dev_exit = QPushButton("Vývojové opuštění")
            dev_exit.setObjectName("written-exam-dev-exit")
            dev_exit.setAutoDefault(False)
            dev_exit.setDefault(False)
            dev_exit.clicked.connect(self.release_testing_lock)
            root.addWidget(dev_exit, alignment=Qt.AlignmentFlag.AlignRight)

        self._refresh_remaining(self.clock.now())

    def _rebuild_navigation(self) -> None:
        while self._nav_layout.count():
            item = self._nav_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._nav_buttons = []
        for index, question in enumerate(self._screen.questions):
            button = QPushButton(str(question.position))
            button.setObjectName(f"written-exam-nav-{question.position}")
            button.setMinimumHeight(40)
            button.setAutoDefault(False)
            button.setDefault(False)
            button.clicked.connect(
                lambda _checked=False, target=index: self._jump(target)
            )
            self._nav_layout.addWidget(button)
            self._nav_buttons.append(button)
        self._nav_layout.addStretch()
        self._paint_navigation()

    def _paint_navigation(self) -> None:
        for index, question in enumerate(self._screen.questions):
            button = self._nav_buttons[index]
            button.setProperty(
                "answered",
                "true" if question.selected_exam_answer_id is not None else "false",
            )
            button.setProperty("current", "true" if index == self._index else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        count = len(self._screen.questions)
        self.prev_button.setEnabled(self._index > 0)
        self.next_button.setEnabled(count > 0 and self._index < count - 1)

    def _show_question(self, index: int) -> None:
        count = len(self._screen.questions)
        self._index = step_question_index(index, count, 0)
        if count == 0:
            return
        question = self._screen.questions[self._index]
        host = QWidget()
        host.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum,
        )
        layout = QVBoxLayout(host)
        layout.setContentsMargins(8, 4, 8, 8)
        heading = QLabel(f"Otázka {question.position}")
        heading.setObjectName("written-exam-question-heading")
        heading.setStyleSheet("font-size: 14px; color: #57534e;")
        text = QLabel(question.text)
        text.setObjectName("written-exam-question-text")
        text.setWordWrap(True)
        text.setStyleSheet("font-size: 18px;")
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(heading)
        layout.addWidget(text)
        picture = self._image_label(
            question.image_stored_path,
            _QUESTION_IMAGE_MAX,
            "written-exam-question-image",
        )
        if picture is not None:
            layout.addWidget(picture)

        for button in self._answer_group.buttons():
            self._answer_group.removeButton(button)

        for option in question.options:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 8, 0, 8)
            radio = QRadioButton(option.letter)
            radio.setObjectName(f"written-exam-answer-{option.letter}")
            radio.setProperty("examAnswerId", option.exam_answer_id)
            radio.setMinimumHeight(36)
            radio.setAutoExclusive(True)
            self._answer_group.addButton(radio)
            radio.toggled.connect(
                lambda checked, qid=question.exam_question_id, aid=option.exam_answer_id: (
                    self._on_answer(checked, qid, aid)
                )
            )
            row_layout.addWidget(radio, alignment=Qt.AlignmentFlag.AlignTop)
            detail = QVBoxLayout()
            if option.text.strip():
                caption = QLabel(option.text)
                caption.setWordWrap(True)
                caption.setObjectName(f"written-exam-answer-text-{option.letter}")
                caption.setStyleSheet("font-size: 16px;")
                detail.addWidget(caption)
            image = self._image_label(
                option.image_stored_path,
                _ANSWER_IMAGE_MAX,
                f"written-exam-answer-image-{option.letter}",
            )
            if image is not None:
                detail.addWidget(image)
            row_layout.addLayout(detail, 1)
            layout.addWidget(row)
            if question.selected_exam_answer_id == option.exam_answer_id:
                radio.blockSignals(True)
                radio.setChecked(True)
                radio.blockSignals(False)

        layout.addStretch()
        previous = self._question_scroll.takeWidget()
        self._question_scroll.setWidget(host)
        if previous is not None:
            previous.deleteLater()
        self._paint_navigation()

    def _image_label(
        self,
        relative_path: str,
        max_size: tuple[int, int],
        object_name: str,
    ) -> QLabel | None:
        path = test_exam_service.resolve_snapshot_image(relative_path)
        if path is None:
            return None
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        label = QLabel()
        label.setObjectName(object_name)
        label.setProperty("snapshotPath", relative_path)
        label.setPixmap(fit_pixmap(pixmap, max_size[0], max_size[1]))
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        return label

    def _jump(self, index: int) -> None:
        if self._phase != "running":
            return
        if self._deadline_reached(self.clock.now()):
            return
        self._screen = written_exam_service.screen(self.exam_id)
        self._show_question(index)

    def _go_previous(self) -> None:
        self._jump(step_question_index(self._index, len(self._screen.questions), -1))

    def _go_next(self) -> None:
        self._jump(step_question_index(self._index, len(self._screen.questions), 1))

    def _on_answer(self, checked: bool, exam_question_id: int, exam_answer_id: int) -> None:
        if not checked or self._phase != "running":
            return
        now = self.clock.now()
        try:
            written_exam_service.save_choice(
                self.exam_id,
                exam_question_id,
                exam_answer_id,
                now=now,
            )
        except WrittenExamClosed:
            self._show_finished()
            return
        except TestExamError as error:
            QMessageBox.warning(self, self._screen.test_name, str(error))
            self._screen = written_exam_service.screen(self.exam_id)
            self._show_question(self._index)
            return
        self._screen = written_exam_service.screen(self.exam_id)
        self._paint_navigation()

    def _on_tick(self) -> None:
        if self._phase != "running":
            return
        self._deadline_reached(self.clock.now())

    def _deadline_reached(self, now) -> bool:
        screen = self._screen
        if screen.started_at is None:
            return False
        self._refresh_remaining(now)
        left = remaining_written_seconds(
            screen.started_at,
            screen.duration_seconds,
            now,
        )
        if left > 0:
            return False
        reason = written_exam_service.sync_deadline(self.exam_id, now=now)
        if reason:
            self._show_finished()
            return True
        return False

    def _refresh_remaining(self, now) -> None:
        screen = self._screen
        if screen.started_at is None:
            self.remaining_label.setText(format_remaining_label(0))
            return
        left = remaining_written_seconds(
            screen.started_at,
            screen.duration_seconds,
            now,
        )
        self.remaining_label.setText(format_remaining_label(left))

    def _commit_finish(self, now) -> None:
        try:
            written_exam_service.submit(self.exam_id, now=now)
        except WrittenExamClosed:
            pass
        except TestExamError as error:
            QMessageBox.warning(self, self._screen.test_name, str(error))
            return
        self._show_finished()

    def _show_finished(self) -> None:
        self._phase = "finished"
        if self._timer.isActive():
            self._timer.stop()
        self._screen = written_exam_service.screen(self.exam_id)
        self._stack.setCurrentIndex(1)

    def _lock_host(self, locked: bool) -> None:
        host = self._host
        if host is None or host is self:
            return
        lock = getattr(host, "set_electronic_exam_lock", None)
        if callable(lock):
            lock(locked)
