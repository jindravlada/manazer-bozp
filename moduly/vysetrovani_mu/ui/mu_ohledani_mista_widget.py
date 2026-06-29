import json
from datetime import datetime
from pathlib import Path

import subprocess

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.services.attachment_service import attachment_service
from core.shared.constants import ENTITY_MU_INVESTIGATION
from core.widgets.thp_worker_selector import ThpWorkerSelector
from core.widgets.workplace_selector import WorkplaceSelector


class MuOhledaniMistaWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._investigation_id: int | None = None
        self._number_slug = "bez-cisla"
        self._saved_data: dict = {}

        self._init_ohledani_mista_widgets()
        self._build_ui()

    def set_context(
        self,
        investigation_id: int | None,
        *,
        event_number: str = "",
        accident_number: str = "",
        investigation_number: str = "",
    ) -> None:
        self._investigation_id = investigation_id
        number = event_number.strip() or accident_number.strip() or investigation_number.strip()
        self.accident_number_label.setText(number)
        self._number_slug = str(number).replace("/", "-").replace("\\", "-").strip() or "bez-cisla"

    def load_json(self, raw_json: str) -> None:
        try:
            self._saved_data = json.loads(raw_json or "{}")
        except Exception:
            self._saved_data = {}
        self._apply_saved_data()

    def get_json(self) -> str:
        return json.dumps(self.get_data(), ensure_ascii=False)

    def get_data(self) -> dict:
        return {
            "ohledani_zapsal": self.ohledani_zapsal.currentText().strip() if hasattr(self.ohledani_zapsal, "currentText") else "",
            "ohledani_provoz": self.ohledani_provoz.currentText().strip() if hasattr(self.ohledani_provoz, "currentText") else self.ohledani_provoz.text().strip(),
            "ohledani_provedli": self.ohledani_provedli.toPlainText().strip(),
            "ohledani_zahajeni": self.ohledani_zahajeni.text().strip(),
            "ohledani_ukonceni": self.ohledani_ukonceni.text().strip(),
            "ohledani_popis_mista": self.ohledani_popis_mista.toPlainText().strip(),
            "ohledani_priloha": self.ohledani_priloha.text().strip(),
        }

    def _init_ohledani_mista_widgets(self):
        saved = self._saved_data

        self.ohledani_zapsal = ThpWorkerSelector()
        self.ohledani_zapsal.setEditable(True)
        if saved.get("ohledani_zapsal"):
            self.ohledani_zapsal.setCurrentText(saved.get("ohledani_zapsal", ""))

        self.ohledani_provoz = WorkplaceSelector()
        self.ohledani_provoz.setEditable(True)
        if saved.get("ohledani_provoz"):
            self.ohledani_provoz.setCurrentText(saved.get("ohledani_provoz", ""))
        self.ohledani_provedli = QTextEdit()
        self.ohledani_provedli.setPlainText(saved.get("ohledani_provedli", ""))
        self.ohledani_zahajeni = QLineEdit(saved.get("ohledani_zahajeni", ""))
        self.ohledani_ukonceni = QLineEdit(saved.get("ohledani_ukonceni", ""))
        self.ohledani_popis_mista = QTextEdit()
        self.ohledani_popis_mista.setPlainText(saved.get("ohledani_popis_mista", ""))
        self.ohledani_priloha = QLineEdit(saved.get("ohledani_priloha", ""))
        self.ohledani_priloha.setReadOnly(True)

    def _apply_saved_data(self) -> None:
        saved = self._saved_data
        if saved.get("ohledani_zapsal"):
            self.ohledani_zapsal.setCurrentText(saved.get("ohledani_zapsal", ""))
        if saved.get("ohledani_provoz"):
            self.ohledani_provoz.setCurrentText(saved.get("ohledani_provoz", ""))
        self.ohledani_provedli.setPlainText(saved.get("ohledani_provedli", ""))
        self.ohledani_zahajeni.setText(saved.get("ohledani_zahajeni", ""))
        self.ohledani_ukonceni.setText(saved.get("ohledani_ukonceni", ""))
        self.ohledani_popis_mista.setPlainText(saved.get("ohledani_popis_mista", ""))
        self.ohledani_priloha.setText(saved.get("ohledani_priloha", ""))

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        zaklad = QGroupBox("Protokol o ohledání místa události")
        form = QFormLayout(zaklad)
        self.accident_number_label = QLabel("")
        form.addRow("Číslo události:", self.accident_number_label)
        form.addRow("Záznam provedl:", self.ohledani_zapsal)
        form.addRow("Provoz:", self.ohledani_provoz)
        self.ohledani_provedli.setMinimumHeight(170)
        form.addRow("Ohledání místa provedli:", self.ohledani_provedli)
        form.addRow("Čas ohledání - zahájení:", self.ohledani_zahajeni)
        form.addRow("Čas ohledání - ukončení:", self.ohledani_ukonceni)
        layout.addWidget(zaklad)

        vysl = QGroupBox("Výsledek ohledání")
        vf = QFormLayout(vysl)
        self.ohledani_popis_mista.setMinimumHeight(220)
        vf.addRow("Podrobný popis místa:", self.ohledani_popis_mista)
        btn = QPushButton("Přiložit podepsaný protokol o ohledání místa")
        btn.clicked.connect(self.add_ohledani_attachment)
        open_btn = QPushButton("Otevřít")
        open_btn.clicked.connect(self.open_ohledani_attachment)
        row = QHBoxLayout()
        row.addWidget(btn)
        row.addWidget(open_btn)
        row.addWidget(self.ohledani_priloha)
        vf.addRow("", row)
        layout.addWidget(vysl)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def add_ohledani_attachment(self):
        if self._investigation_id is None:
            QMessageBox.information(
                self,
                "Příloha",
                "Protokol lze přiložit až po uložení vyšetřování.",
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte podepsaný protokol o ohledání místa",
            "",
            "Dokumenty a obrázky (*.pdf *.jpg *.jpeg *.png *.odt *.docx);;Všechny soubory (*)",
        )
        if not file_path:
            return

        source = Path(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"Ohledani-{self._number_slug}_{timestamp}{source.suffix.lower()}"
        attachment = attachment_service.add_file_as(
            ENTITY_MU_INVESTIGATION,
            self._investigation_id,
            str(source),
            new_name,
        )
        if attachment is None:
            QMessageBox.warning(self, "Příloha", "Protokol se nepodařilo uložit.")
            return
        self.ohledani_priloha.setText(attachment.filename)

    def open_ohledani_attachment(self) -> None:
        filename = self.ohledani_priloha.text().strip()
        if not filename:
            QMessageBox.information(self, "Příloha", "Není přiložen žádný protokol.")
            return
        if self._investigation_id is None:
            QMessageBox.information(
                self,
                "Příloha",
                "Protokol lze otevřít až po uložení vyšetřování.",
            )
            return

        attachments = attachment_service.get_for_entity(
            ENTITY_MU_INVESTIGATION,
            self._investigation_id,
        )
        attachment = next((item for item in attachments if item.filename == filename), None)
        if attachment is None:
            QMessageBox.warning(self, "Příloha", "Soubor protokolu nebyl nalezen.")
            return

        path = attachment_service.resolve_path(attachment)
        if not path.exists():
            QMessageBox.warning(self, "Příloha", "Soubor protokolu nebyl nalezen.")
            return

        try:
            subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            QMessageBox.warning(self, "Příloha", f"Protokol se nepodařilo otevřít.\n\n{exc}")
