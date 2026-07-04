import html
import json
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path

from core.export import open_export_file

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.services.attachment_service import attachment_service
from core.services.storage_service import storage_service
from core.shared.constants import ENTITY_MU_INVESTIGATION
from core.widgets.attachment_widget import AttachmentWidget


_WITNESS_FORMS = (
    ("Prot-Vyjadreni-Postizeny.odt", "Vyjádření dotčené osoby k mimořádné události"),
    ("Prot-Vyjadreni-Svedek.odt", "Vyjádření svědka k mimořádné události"),
    ("CL-Vypovedi.odt", "Postup vedení výpovědí dotčené osoby a svědků"),
    ("Prot-Vypoved.odt", "Výpověď dotčené osoby / svědka k mimořádné události"),
)


class MuSvedciWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._saved_data: dict = {}
        self._investigation_id: int | None = None
        self._number_slug = "bez-cisla"
        self._event_number = ""

        self._init_widgets()
        self._build_ui()

    def set_context(
        self,
        investigation_id: int | None,
        *,
        event_number: str = "",
    ) -> None:
        self._investigation_id = investigation_id
        self._event_number = event_number.strip()
        self._number_slug = (
            str(self._event_number).replace("/", "-").replace("\\", "-").strip() or "bez-cisla"
        )
        self.event_number_label.setText(self._event_number)

        if hasattr(self, "svedci_attachment_widget"):
            self.svedci_attachment_widget.set_entity(ENTITY_MU_INVESTIGATION, investigation_id)

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
            "pocet_svedku": self.pocet_svedku.value(),
            "svedci": [w.text().strip() for w in self.svedek_widgets],
            "svedci_oddeleni": self.svedci_oddeleni.isChecked(),
            "vyjadreni_obsahuje_udaje": self.vyjadreni_obsahuje_udaje.isChecked(),
            "vyjadreni_vracena": self.vyjadreni_vracena.isChecked(),
            "rozhovor_po_vyjadreni": self.rozhovor_po_vyjadreni.isChecked(),
            "obsah": self.svedci_obsah.toPlainText().strip(),
        }

    def _init_widgets(self) -> None:
        saved = self._saved_data

        self.pocet_svedku = QSpinBox()
        self.pocet_svedku.setRange(0, 20)
        self.pocet_svedku.setValue(int(saved.get("pocet_svedku") or 0))
        self.svedci_form: QFormLayout | None = None
        self.svedek_widgets: list[QLineEdit] = []

        self.svedci_oddeleni = QCheckBox("Oddělit svědky a předat formulář k písemnému vyjádření")
        self.vyjadreni_obsahuje_udaje = QCheckBox("Vyjádření obsahují datum, čas, jméno a podpis")
        self.vyjadreni_vracena = QCheckBox(
            "Vráceny formuláře s vyjádřením od všech svědků (včetně dotčené osoby)"
        )
        self.rozhovor_po_vyjadreni = QCheckBox(
            "Doplňující rozhovor byl veden až po prvotním písemném vyjádření"
        )
        self.svedci_oddeleni.setChecked(bool(saved.get("svedci_oddeleni", False)))
        self.vyjadreni_obsahuje_udaje.setChecked(bool(saved.get("vyjadreni_obsahuje_udaje", False)))
        self.vyjadreni_vracena.setChecked(bool(saved.get("vyjadreni_vracena", False)))
        self.rozhovor_po_vyjadreni.setChecked(bool(saved.get("rozhovor_po_vyjadreni", False)))

        self.svedci_obsah = QTextEdit()
        self.svedci_obsah.setPlaceholderText(
            "Vyjádření svědků, rozdělení svědků, vlastní písemná vyjádření..."
        )
        self.svedci_obsah.setMinimumHeight(220)
        self.svedci_obsah.setPlainText(saved.get("obsah", ""))

    def _apply_saved_data(self) -> None:
        saved = self._saved_data
        self.pocet_svedku.setValue(int(saved.get("pocet_svedku") or 0))
        self._refresh_svedci_rows()
        self.svedci_oddeleni.setChecked(bool(saved.get("svedci_oddeleni", False)))
        self.vyjadreni_obsahuje_udaje.setChecked(bool(saved.get("vyjadreni_obsahuje_udaje", False)))
        self.vyjadreni_vracena.setChecked(bool(saved.get("vyjadreni_vracena", False)))
        self.rozhovor_po_vyjadreni.setChecked(bool(saved.get("rozhovor_po_vyjadreni", False)))
        self.svedci_obsah.setPlainText(saved.get("obsah", ""))

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        info = QLabel(
            "Zde evidujte svědky, jejich vyjádření a související formuláře. "
            "Otevřete editovatelné ODT formuláře pro výpovědi a vyjádření. "
            "Při otevření formuláře se vytvoří kopie a automaticky se doplní číslo události."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        zaklad_group = QGroupBox("Základní údaje")
        zaklad_form = QFormLayout(zaklad_group)
        self.event_number_label = QLabel("")
        zaklad_form.addRow("Číslo události:", self.event_number_label)
        layout.addWidget(zaklad_group)

        svedci_group = QGroupBox("1. Svědci a prvotní vyjádření")
        svedci_outer = QVBoxLayout(svedci_group)
        svedci_form = QFormLayout()
        svedci_form.addRow("Počet zjištěných svědků:", self.pocet_svedku)
        self.svedci_form = svedci_form
        self._refresh_svedci_rows()
        self.pocet_svedku.valueChanged.connect(self._refresh_svedci_rows)
        svedci_outer.addLayout(svedci_form)
        svedci_outer.addWidget(self.svedci_oddeleni)
        svedci_outer.addWidget(self.vyjadreni_obsahuje_udaje)
        svedci_outer.addWidget(self.vyjadreni_vracena)
        svedci_outer.addWidget(self.rozhovor_po_vyjadreni)
        layout.addWidget(svedci_group)

        zaznam_group = QGroupBox("2. Vyjádření a poznámky")
        zaznam_layout = QVBoxLayout(zaznam_group)
        zaznam_layout.addWidget(self.svedci_obsah)
        layout.addWidget(zaznam_group)

        formulare_group = QGroupBox("3. Formuláře")
        formulare_layout = QVBoxLayout(formulare_group)
        for filename, title in _WITNESS_FORMS:
            btn = QPushButton(title)
            btn.setMinimumHeight(36)
            btn.clicked.connect(
                lambda checked=False, f=filename, t=title: self._open_form(f, t)
            )
            formulare_layout.addWidget(btn)
        layout.addWidget(formulare_group)

        prilohy_group = QGroupBox("4. Přílohy")
        prilohy_layout = QVBoxLayout(prilohy_group)
        prilohy_info = QLabel(
            "Zde přiložte podepsaná vyjádření svědků, výpovědi, skeny formulářů "
            "nebo další soubory související se svědectvím."
        )
        prilohy_info.setWordWrap(True)
        prilohy_layout.addWidget(prilohy_info)
        self.svedci_attachment_widget = AttachmentWidget(
            entity_type=ENTITY_MU_INVESTIGATION,
            entity_id=None,
        )
        prilohy_layout.addWidget(self.svedci_attachment_widget)
        layout.addWidget(prilohy_group)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _refresh_svedci_rows(self) -> None:
        if self.svedci_form is None:
            return
        existing = [w.text() for w in self.svedek_widgets]
        saved = self._saved_data.get("svedci", []) or []
        while len(self.svedek_widgets) > 0:
            row = self.svedci_form.rowCount() - 1
            self.svedci_form.removeRow(row)
            self.svedek_widgets.pop()
        for idx in range(self.pocet_svedku.value()):
            value = existing[idx] if idx < len(existing) else (saved[idx] if idx < len(saved) else "")
            edit = QLineEdit(value)
            self.svedek_widgets.append(edit)
            self.svedci_form.addRow(f"Svědek {idx + 1}:", edit)

    def _form_templates_dir(self) -> Path:
        storage_service.ensure_structure()
        user_dir = storage_service.templates_dir / "setreni"
        if user_dir.exists():
            return user_dir
        return storage_service.bundled_templates_dir() / "setreni"

    def _form_output_filename(self, title: str, suffix: str = ".odt") -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"Formular-{self._slug(title)}-{self._number_slug}_{stamp}{suffix}"

    def _prepare_odt_form_copy(self, template_path: Path, output_path: Path) -> None:
        event_number = self._event_number
        escaped_number = html.escape(str(event_number), quote=False)

        with zipfile.ZipFile(template_path, "r") as zin, zipfile.ZipFile(output_path, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "content.xml":
                    xml = data.decode("utf-8")
                    xml = xml.replace("${cislo_urazu}", escaped_number)
                    xml = xml.replace(
                        "Číslo pracovního úrazu    ${cislo_urazu}",
                        f"Číslo události    {escaped_number}",
                    )
                    xml = xml.replace("Číslo pracovního úrazu", "Číslo události")
                    if "Číslo úrazu:" in xml:
                        xml = xml.replace("Číslo úrazu:", f"Číslo události: {escaped_number}", 1)
                    data = xml.encode("utf-8")
                zout.writestr(item, data)

    def _open_form(self, template_filename: str, title: str) -> None:
        if self._investigation_id is None:
            QMessageBox.information(
                self,
                "Formuláře",
                "Formulář lze vytvořit až po uložení vyšetřování.",
            )
            return

        template_path = self._form_templates_dir() / template_filename
        if not template_path.exists():
            QMessageBox.warning(self, "Formuláře", f"Šablona nebyla nalezena:\n{template_path}")
            return

        tmp_dir = storage_service.exports_dir / "docasne_formulare"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / self._form_output_filename(title)
        self._prepare_odt_form_copy(template_path, tmp_path)

        attachment = attachment_service.add_file_as(
            ENTITY_MU_INVESTIGATION,
            self._investigation_id,
            str(tmp_path),
            tmp_path.name,
        )
        final_path = attachment_service.resolve_path(attachment) if attachment is not None else tmp_path

        open_export_file(final_path, parent=self, title="Formuláře")

    def _slug(self, text: str) -> str:
        text = text.replace(":", "").strip()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        parts = []
        capitalize_next = True
        for ch in text:
            if ch.isalnum():
                parts.append(ch.upper() if capitalize_next else ch)
                capitalize_next = False
            else:
                capitalize_next = True
        return "".join(parts) or "Formular"
