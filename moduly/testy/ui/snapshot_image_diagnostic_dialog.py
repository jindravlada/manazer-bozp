"""Diagnostika obrázků, kvůli kterým se elektronická zkouška nespustila."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from moduly.testy.constants import MODULE_NAME
from moduly.testy.sluzby.test_exam_service import (
    SnapshotImageProblem,
    format_snapshot_image_report,
)

_INTRO = (
    "Elektronickou zkoušku nelze zahájit.\n"
    "Časový limit nebyl spuštěn a výsledek zkoušky nebyl vytvořen."
)


class SnapshotImageDiagnosticDialog(QDialog):
    def __init__(
        self,
        problems: list[SnapshotImageProblem] | tuple[SnapshotImageProblem, ...],
        parent=None,
    ):
        super().__init__(parent)
        self._problems = tuple(problems)
        self.setObjectName("snapshot-image-diagnostic")
        self.setWindowTitle(MODULE_NAME)
        self.setMinimumWidth(640)

        intro = QLabel(_INTRO)
        intro.setObjectName("snapshot-image-diagnostic-intro")
        intro.setWordWrap(True)

        self._text = QPlainTextEdit()
        self._text.setObjectName("snapshot-image-diagnostic-text")
        self._text.setReadOnly(True)
        self._text.setMinimumHeight(220)

        self._full_path = QCheckBox("Zobrazit úplnou cestu")
        self._full_path.setObjectName("snapshot-image-diagnostic-full-path")
        self._full_path.toggled.connect(self._refresh)

        copy = QPushButton("Zkopírovat podrobnosti")
        copy.setObjectName("snapshot-image-diagnostic-copy")
        copy.setAutoDefault(False)
        copy.clicked.connect(self.copy_details)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(self._full_path)
        row.addStretch(1)
        row.addWidget(copy)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self._text, 1)
        layout.addLayout(row)
        layout.addWidget(buttons)
        self._refresh()

    def report_text(self, *, include_full_paths: bool) -> str:
        return format_snapshot_image_report(
            self._problems,
            include_full_paths=include_full_paths,
        )

    def detailed_text(self) -> str:
        return f"{_INTRO}\n\n{self.report_text(include_full_paths=True)}"

    def copy_details(self) -> None:
        QApplication.clipboard().setText(self.detailed_text())

    def _refresh(self) -> None:
        self._text.setPlainText(
            self.report_text(include_full_paths=self._full_path.isChecked())
        )
