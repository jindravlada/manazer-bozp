from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from moduly.pravni_pozadavky.sluzby.legal_change_impacted_process_service import (
    ImpactedControlProcess,
)


class LegalChangeImpactedProcessesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addStretch()

    def load_processes(self, processes: list[ImpactedControlProcess]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not processes:
            self._layout.addStretch()
            return

        for index, process in enumerate(processes):
            if index > 0:
                spacer = QLabel("")
                spacer.setFixedHeight(8)
                self._layout.addWidget(spacer)

            title = QLabel(process.display_title)
            title_font = QFont(title.font())
            title_font.setBold(True)
            title.setFont(title_font)
            self._layout.addWidget(title)

            sources_heading = QLabel("Právní podklady:")
            self._layout.addWidget(sources_heading)

            if process.legal_sources:
                for source in process.legal_sources:
                    label = QLabel(source.display_label)
                    if source.is_changed:
                        font = QFont(label.font())
                        font.setBold(True)
                        label.setFont(font)
                    self._layout.addWidget(label)
            else:
                empty_label = QLabel("—")
                self._layout.addWidget(empty_label)

        self._layout.addStretch()
