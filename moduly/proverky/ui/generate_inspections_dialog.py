from datetime import date

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.proverky.sluzby.bozp_inspection_generation_service import (
    bozp_inspection_generation_service,
)


class GenerateInspectionsDialog(QDialog):
    def __init__(self, parent=None, *, year: int | None = None):
        super().__init__(parent)

        self.setWindowTitle("Generovat prověrky")
        self.resize(420, 180)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Automaticky založí roční prověrky BOZP pro aktivní provozy, "
            "které pro vybraný rok ještě nemají záznam. Měsíce se rozloží rovnoměrně."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(year or date.today().year)
        form.addRow("Rok:", self.year_spin)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Generovat")
        buttons.accepted.connect(self._generate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _generate(self) -> None:
        year = self.year_spin.value()
        result = bozp_inspection_generation_service.generate_for_year(year)

        if not result.created and result.skipped_existing:
            QMessageBox.information(
                self,
                "Generovat prověrky",
                f"Pro rok {year} už existují prověrky u všech aktivních provozů.\n"
                "Stávající záznamy nebyly změněny.",
            )
            return

        if not result.created:
            QMessageBox.information(
                self,
                "Generovat prověrky",
                "Nejsou k dispozici žádné aktivní provozy pro generování.",
            )
            return

        QMessageBox.information(
            self,
            "Generovat prověrky",
            f"Bylo vytvořeno {len(result.created)} prověrek pro rok {year}.\n"
            f"Přeskočeno provozů, které už plán mají: {result.skipped_existing}.",
        )
        self.accept()
