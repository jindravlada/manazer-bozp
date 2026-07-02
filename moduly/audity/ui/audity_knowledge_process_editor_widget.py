"""Editační formulář metadat řídicího procesu v editoru metodiky auditora."""

from PySide6.QtCore import Signal
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from moduly.audity.constants import (
    GUIDE_LABEL_EXPECTED_OUTPUT,
    GUIDE_LABEL_UCEL,
    GUIDE_LABEL_WHY_IMPORTANT,
)


class AudityKnowledgeProcessEditorWidget(QWidget):
    """Formulář metadat vybraného řídicího procesu."""

    add_section_requested = Signal()
    content_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._process_id = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        toolbar = QHBoxLayout()
        self._add_section_btn = QPushButton("+ Přidat oblast ověření")
        self._add_section_btn.clicked.connect(self.add_section_requested.emit)
        self._add_section_btn.setEnabled(False)
        toolbar.addWidget(self._add_section_btn)
        toolbar.addStretch()
        root.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_content = QWidget()
        form = QFormLayout(scroll_content)
        form.setSpacing(10)

        self._id_label = QLabel()
        self._nazev_edit = QLineEdit()
        self._popis_edit = QTextEdit()
        self._popis_edit.setMinimumHeight(80)
        self._ucel_edit = QTextEdit()
        self._ucel_edit.setMinimumHeight(90)
        self._proc_je_dulezity_edit = QTextEdit()
        self._proc_je_dulezity_edit.setMinimumHeight(90)
        self._ocekavany_vystup_edit = QTextEdit()
        self._ocekavany_vystup_edit.setMinimumHeight(90)
        self._poradi_spin = QSpinBox()
        self._poradi_spin.setRange(0, 99999)
        self._poradi_spin.setSingleStep(10)
        self._aktivni_check = QCheckBox("Proces je aktivní")

        form.addRow("Identifikátor:", self._id_label)
        form.addRow("Název procesu:", self._nazev_edit)
        form.addRow("Popis:", self._popis_edit)
        form.addRow(f"{GUIDE_LABEL_UCEL}:", self._ucel_edit)
        form.addRow(f"{GUIDE_LABEL_WHY_IMPORTANT}:", self._proc_je_dulezity_edit)
        form.addRow(f"{GUIDE_LABEL_EXPECTED_OUTPUT}:", self._ocekavany_vystup_edit)
        form.addRow("Pořadí:", self._poradi_spin)
        form.addRow("", self._aktivni_check)

        scroll.setWidget(scroll_content)
        root.addWidget(scroll, stretch=1)

        for widget in (
            self._nazev_edit,
            self._popis_edit,
            self._ucel_edit,
            self._proc_je_dulezity_edit,
            self._ocekavany_vystup_edit,
        ):
            widget.textChanged.connect(lambda *_args: self.content_modified.emit())
        self._poradi_spin.valueChanged.connect(lambda *_args: self.content_modified.emit())
        self._aktivni_check.toggled.connect(lambda *_args: self.content_modified.emit())

    @property
    def process_id(self) -> str:
        return self._process_id

    def has_process(self) -> bool:
        return bool(self._process_id)

    def load_process(self, *, process_id: str, metadata: dict) -> None:
        self._process_id = process_id
        self._id_label.setText(process_id)
        self._add_section_btn.setEnabled(True)
        self._nazev_edit.setText(str(metadata.get("nazev") or ""))
        self._popis_edit.setPlainText(str(metadata.get("popis") or ""))
        self._ucel_edit.setPlainText(str(metadata.get("ucel_procesu") or ""))
        self._proc_je_dulezity_edit.setPlainText(str(metadata.get("proc_je_dulezity") or ""))
        self._ocekavany_vystup_edit.setPlainText(str(metadata.get("ocekavany_vystup") or ""))
        self._poradi_spin.setValue(int(metadata.get("poradi") or 0))
        self._aktivni_check.setChecked(bool(metadata.get("aktivni", True)))

    def clear_process(self) -> None:
        self._process_id = ""
        self._id_label.clear()
        self._add_section_btn.setEnabled(False)
        self._nazev_edit.clear()
        self._popis_edit.clear()
        self._ucel_edit.clear()
        self._proc_je_dulezity_edit.clear()
        self._ocekavany_vystup_edit.clear()
        self._poradi_spin.setValue(0)
        self._aktivni_check.setChecked(True)

    def process_metadata(self) -> dict:
        return {
            "nazev": self._nazev_edit.text().strip(),
            "popis": self._popis_edit.toPlainText().strip(),
            "ucel_procesu": self._ucel_edit.toPlainText().strip(),
            "proc_je_dulezity": self._proc_je_dulezity_edit.toPlainText().strip(),
            "ocekavany_vystup": self._ocekavany_vystup_edit.toPlainText().strip(),
            "poradi": self._poradi_spin.value(),
            "aktivni": self._aktivni_check.isChecked(),
        }
