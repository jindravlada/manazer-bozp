import json
import unicodedata
import uuid
from datetime import date, datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.services.attachment_service import attachment_service
from core.shared.constants import ENTITY_MU_INVESTIGATION
from moduly.vysetrovani_mu.sluzby.mu_chronologie_events import build_system_chronologie_events
from moduly.vysetrovani_mu.ui.mu_chronologie_entry_dialog import MuChronologieEntryDialog


class MuCasovaOsaWidget(QWidget):
    """Časová osa vyšetřování MU.

    JSON struktura (casova_osa_json):
    - cas_synchronizace: data sekce synchronizace zařízení (1:1 ze Šetření úrazu)
    - chronologie: ručně zadané události (source=manual)
    - system_events: rezervováno; systémové události se počítají živě při zobrazení
    """

    _CHRONOLOGIE_COLUMNS = ("Datum", "Čas", "Typ události", "Popis", "Zdroj")

    def __init__(self, parent=None):
        super().__init__(parent)

        self._saved_data: dict = {}
        self._investigation_id: int | None = None
        self._started_at: date | None = None
        self._source_type: str = ""
        self._source_id: int | None = None
        self._oznameni_datum: date | None = None
        self._oznameni_cas: str = ""
        self._number_slug = "bez-cisla"
        self._chronologie_entries: list[dict] = []
        self._display_entries: list[dict] = []

        self._init_cas_synchronizace_widgets()
        self._build_ui()

    def set_context(
        self,
        investigation_id: int | None,
        *,
        event_number: str = "",
        started_at: date | None = None,
        source_type: str = "",
        source_id: int | None = None,
        oznameni_datum: date | None = None,
        oznameni_cas: str = "",
    ) -> None:
        self._investigation_id = investigation_id
        self._started_at = started_at
        self._source_type = source_type or ""
        self._source_id = source_id
        self._oznameni_datum = oznameni_datum
        self._oznameni_cas = (oznameni_cas or "").strip()
        number = event_number.strip()
        self._number_slug = str(number).replace("/", "-").replace("\\", "-").strip() or "bez-cisla"
        self._refresh_chronologie_table()

    def set_started_at(self, started_at: date | None) -> None:
        self._started_at = started_at
        self._refresh_chronologie_table()

    def set_oznameni_context(
        self,
        *,
        oznameni_datum: date | None = None,
        oznameni_cas: str = "",
    ) -> None:
        self._oznameni_datum = oznameni_datum
        self._oznameni_cas = (oznameni_cas or "").strip()
        self._refresh_chronologie_table()

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
            "cas_synchronizace": self._cas_synchronizace_data(),
            "chronologie": list(self._chronologie_entries),
            "system_events": self._saved_data.get("system_events", []) or [],
        }

    def _cas_synchronizace_data(self) -> dict:
        return {
            "caszarizeni_fotodokumentace": self._radio_choice_value(self.caszarizeni_fotodokumentace),
            "caszarizeni_reference_source": self.caszarizeni_reference_source.currentText().strip(),
            "caszarizeni_srovnani_cas": self.caszarizeni_srovnani_cas.text().strip(),
            "caszarizeni_visible_rows": getattr(self, "caszarizeni_visible_rows", 1),
            "caszarizeni_rows": [
                {
                    "zarizeni": getattr(self, f"caszarizeni_{i}_zarizeni").text().strip(),
                    "cas_zarizeni": getattr(self, f"caszarizeni_{i}_cas_zarizeni").text().strip(),
                    "cas_mobil": getattr(self, f"caszarizeni_{i}_cas_mobil").text().strip(),
                    "rozdil": getattr(self, f"caszarizeni_{i}_rozdil").text().strip(),
                    "srovnany_cas": getattr(self, f"caszarizeni_{i}_srovnany_cas").text().strip(),
                    "foto": getattr(self, f"caszarizeni_{i}_foto").text().strip(),
                }
                for i in range(1, 11)
            ],
        }

    def _init_cas_synchronizace_widgets(self) -> None:
        saved = self._saved_data.get("cas_synchronizace", {}) or {}

        self.caszarizeni_fotodokumentace = self._radio_choice(["Pořízena", "Nepořízena"])
        self._set_radio_choice(self.caszarizeni_fotodokumentace, saved.get("caszarizeni_fotodokumentace", ""))
        self.caszarizeni_reference_source = QComboBox()
        self.caszarizeni_reference_source.addItem("Mobil / referenční čas v řádcích")
        self._saved_caszarizeni_reference_source = saved.get("caszarizeni_reference_source", "")
        self.caszarizeni_srovnani_cas = QLineEdit()
        self.caszarizeni_srovnani_cas.setPlaceholderText("např. 14:35")
        self.caszarizeni_srovnani_cas.setText(saved.get("caszarizeni_srovnani_cas", ""))
        self.caszarizeni_rows: list[list[QWidget]] = []
        cas_rows = saved.get("caszarizeni_rows", []) or []
        for i in range(1, 11):
            data = cas_rows[i - 1] if i <= len(cas_rows) else {}
            setattr(self, f"caszarizeni_{i}_zarizeni", QLineEdit(data.get("zarizeni", "")))
            setattr(self, f"caszarizeni_{i}_cas_zarizeni", QLineEdit(data.get("cas_zarizeni", "")))
            setattr(self, f"caszarizeni_{i}_cas_mobil", QLineEdit(data.get("cas_mobil", "")))
            setattr(self, f"caszarizeni_{i}_rozdil", QLineEdit(data.get("rozdil", "")))
            setattr(self, f"caszarizeni_{i}_srovnany_cas", QLineEdit(data.get("srovnany_cas", "")))
            setattr(self, f"caszarizeni_{i}_foto", QLineEdit(data.get("foto", "")))
            getattr(self, f"caszarizeni_{i}_rozdil").setReadOnly(True)
            getattr(self, f"caszarizeni_{i}_srovnany_cas").setReadOnly(True)
            getattr(self, f"caszarizeni_{i}_foto").setReadOnly(True)

        if self._saved_caszarizeni_reference_source:
            self.caszarizeni_reference_source.addItem(self._saved_caszarizeni_reference_source)
            self.caszarizeni_reference_source.setCurrentText(self._saved_caszarizeni_reference_source)

    def _apply_saved_data(self) -> None:
        saved = self._saved_data
        cas_saved = saved.get("cas_synchronizace", {}) or {}

        self._set_radio_choice(
            self.caszarizeni_fotodokumentace,
            cas_saved.get("caszarizeni_fotodokumentace", ""),
        )
        ref_source = cas_saved.get("caszarizeni_reference_source", "")
        if ref_source:
            if self.caszarizeni_reference_source.findText(ref_source) < 0:
                self.caszarizeni_reference_source.addItem(ref_source)
            self.caszarizeni_reference_source.setCurrentText(ref_source)
        self.caszarizeni_srovnani_cas.setText(cas_saved.get("caszarizeni_srovnani_cas", ""))

        cas_rows = cas_saved.get("caszarizeni_rows", []) or []
        for i in range(1, 11):
            data = cas_rows[i - 1] if i <= len(cas_rows) else {}
            getattr(self, f"caszarizeni_{i}_zarizeni").setText(data.get("zarizeni", ""))
            getattr(self, f"caszarizeni_{i}_cas_zarizeni").setText(data.get("cas_zarizeni", ""))
            getattr(self, f"caszarizeni_{i}_cas_mobil").setText(data.get("cas_mobil", ""))
            getattr(self, f"caszarizeni_{i}_rozdil").setText(data.get("rozdil", ""))
            getattr(self, f"caszarizeni_{i}_srovnany_cas").setText(data.get("srovnany_cas", ""))
            getattr(self, f"caszarizeni_{i}_foto").setText(data.get("foto", ""))

        if hasattr(self, "caszarizeni_rows") and self.caszarizeni_rows:
            saved_visible = int(cas_saved.get("caszarizeni_visible_rows", 1) or 1)
            self.caszarizeni_visible_rows = max(1, min(saved_visible, len(self.caszarizeni_rows)))
            for idx, widgets in enumerate(self.caszarizeni_rows, start=1):
                visible = idx <= self.caszarizeni_visible_rows
                for widget in widgets:
                    widget.setVisible(visible)

        self._chronologie_entries = self._normalize_chronologie(saved.get("chronologie", []) or [])
        self._refresh_chronologie_table()
        self._recalculate_caszarizeni()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        layout.addWidget(self._build_cas_synchronizace_group())
        layout.addWidget(self._build_chronologie_group())
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _build_cas_synchronizace_group(self) -> QGroupBox:
        cas_group = QGroupBox("Časová synchronizace zařízení")
        cas_layout = QVBoxLayout(cas_group)
        cas_info = QLabel(
            "Zadejte zařízení, jeho zobrazený čas a referenční čas. "
            "Rozdíl se dopočítá automaticky jako čas zařízení vůči referenci. "
            "Jako základ srovnání lze použít mobil nebo libovolné zadané zařízení."
        )
        cas_info.setWordWrap(True)
        cas_layout.addWidget(cas_info)
        cas_form = QFormLayout()
        cas_form.addRow("Fotodokumentace časů zařízení:", self.caszarizeni_fotodokumentace)
        cas_form.addRow("Srovnávat podle:", self.caszarizeni_reference_source)
        cas_form.addRow("Srovnání časové osy – referenční čas:", self.caszarizeni_srovnani_cas)
        cas_layout.addLayout(cas_form)
        cas_layout.addWidget(
            QLabel(
                "<b>Zařízení | Čas zařízení na fotce | Referenční čas na fotce | "
                "Rozdíl | Čas zařízení ve srovnávaném čase | Fotografie času zařízení</b>"
            )
        )

        rows = []
        for i in range(1, 11):
            row_layout = QHBoxLayout()
            zarizeni = getattr(self, f"caszarizeni_{i}_zarizeni")
            cas_zarizeni = getattr(self, f"caszarizeni_{i}_cas_zarizeni")
            cas_mobil = getattr(self, f"caszarizeni_{i}_cas_mobil")
            rozdil = getattr(self, f"caszarizeni_{i}_rozdil")
            srovnany = getattr(self, f"caszarizeni_{i}_srovnany_cas")
            foto = getattr(self, f"caszarizeni_{i}_foto")
            zarizeni.setPlaceholderText("např. kamera / lokomotiva")
            cas_zarizeni.setPlaceholderText("čas zařízení")
            cas_mobil.setPlaceholderText("referenční čas")
            rozdil.setPlaceholderText("rozdíl")
            srovnany.setPlaceholderText("přepočet")
            foto.setPlaceholderText("příloha")
            btn = QPushButton("Přiložit fotografii")
            btn.clicked.connect(lambda checked=False, row=i: self.add_caszarizeni_photo(row))
            for widget in (zarizeni, cas_zarizeni, cas_mobil, rozdil, srovnany, foto, btn):
                row_layout.addWidget(widget)
            cas_layout.addLayout(row_layout)
            rows.append([zarizeni, cas_zarizeni, cas_mobil, rozdil, srovnany, foto, btn])

        btn_add = QPushButton("Přidat zařízení")
        btn_add.clicked.connect(self.add_caszarizeni_row)
        cas_layout.addWidget(btn_add)
        self._register_caszarizeni_rows(rows)
        self._connect_caszarizeni_calculation()
        return cas_group

    def _build_chronologie_group(self) -> QGroupBox:
        group = QGroupBox("Chronologie událostí")
        layout = QVBoxLayout(group)

        info = QLabel(
            "Chronologie spojuje ručně zadané milníky se systémovými událostmi "
            "odvozenými ze spisu a zdrojového záznamu. Systémové záznamy nelze upravit."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        toolbar = QHBoxLayout()
        self.chronologie_add_btn = QPushButton("Přidat")
        self.chronologie_edit_btn = QPushButton("Upravit")
        self.chronologie_delete_btn = QPushButton("Odebrat")
        toolbar.addWidget(self.chronologie_add_btn)
        toolbar.addWidget(self.chronologie_edit_btn)
        toolbar.addWidget(self.chronologie_delete_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.chronologie_table = QTableWidget(0, len(self._CHRONOLOGIE_COLUMNS))
        self.chronologie_table.setHorizontalHeaderLabels(list(self._CHRONOLOGIE_COLUMNS))
        self.chronologie_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.chronologie_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.chronologie_table.setSelectionMode(QTableWidget.SingleSelection)
        self.chronologie_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.chronologie_table.doubleClicked.connect(self._edit_chronologie_entry)
        self.chronologie_table.selectionModel().selectionChanged.connect(
            self._update_chronologie_toolbar_state
        )
        layout.addWidget(self.chronologie_table)

        self.chronologie_add_btn.clicked.connect(self._add_chronologie_entry)
        self.chronologie_edit_btn.clicked.connect(self._edit_chronologie_entry)
        self.chronologie_delete_btn.clicked.connect(self._delete_chronologie_entry)
        return group

    def _register_caszarizeni_rows(self, rows: list[list[QWidget]]) -> None:
        self.caszarizeni_rows = rows
        saved = self._saved_data.get("cas_synchronizace", {}) or {}
        saved_visible = int(saved.get("caszarizeni_visible_rows", 1) or 1)
        self.caszarizeni_visible_rows = max(1, min(saved_visible, len(rows)))
        for idx, widgets in enumerate(rows, start=1):
            visible = idx <= self.caszarizeni_visible_rows
            for widget in widgets:
                widget.setVisible(visible)

    def add_caszarizeni_row(self) -> None:
        current = getattr(self, "caszarizeni_visible_rows", 1)
        if current >= len(self.caszarizeni_rows):
            return
        self.caszarizeni_visible_rows = current + 1
        for widget in self.caszarizeni_rows[self.caszarizeni_visible_rows - 1]:
            widget.setVisible(True)

    def add_caszarizeni_photo(self, row: int) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte fotografii času zařízení",
            "",
            "Obrázky (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;Všechny soubory (*)",
        )
        if not file_path:
            return

        source = Path(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        device_name = getattr(self, f"caszarizeni_{row}_zarizeni").text().strip() or f"Zarizeni{row}"
        new_name = (
            f"Foto-CasZarizeni-{self._slug(device_name)}-{self._number_slug}_{timestamp}{source.suffix.lower()}"
        )
        attachment = None
        if self._investigation_id is not None:
            attachment = attachment_service.add_file_as(
                ENTITY_MU_INVESTIGATION,
                self._investigation_id,
                str(source),
                new_name,
            )
        final_name = attachment.filename if attachment is not None else new_name
        getattr(self, f"caszarizeni_{row}_foto").setText(final_name)

    def _connect_caszarizeni_calculation(self) -> None:
        self.caszarizeni_srovnani_cas.textChanged.connect(self._recalculate_caszarizeni)
        self.caszarizeni_reference_source.currentTextChanged.connect(self._recalculate_caszarizeni)
        for i in range(1, 11):
            getattr(self, f"caszarizeni_{i}_zarizeni").textChanged.connect(
                self._refresh_caszarizeni_reference_choices
            )
            getattr(self, f"caszarizeni_{i}_cas_zarizeni").textChanged.connect(self._recalculate_caszarizeni)
            getattr(self, f"caszarizeni_{i}_cas_mobil").textChanged.connect(self._recalculate_caszarizeni)
        self._refresh_caszarizeni_reference_choices()

    def _recalculate_caszarizeni(self) -> None:
        srovnani = self._parse_time_minutes(self.caszarizeni_srovnani_cas.text())
        ref_row = self._caszarizeni_reference_row()
        if srovnani is None:
            base_ref_time = None
        elif ref_row is None:
            base_ref_time = srovnani
        else:
            ref_offset = self._caszarizeni_row_offset(ref_row)
            base_ref_time = None if ref_offset is None else srovnani - ref_offset

        for i in range(1, 11):
            offset = self._caszarizeni_row_offset(i)
            getattr(self, f"caszarizeni_{i}_rozdil").setText(self._format_time_delta(offset))
            if base_ref_time is None or offset is None:
                getattr(self, f"caszarizeni_{i}_srovnany_cas").setText("")
            else:
                getattr(self, f"caszarizeni_{i}_srovnany_cas").setText(
                    self._format_time_minutes(base_ref_time + offset)
                )

    def _refresh_caszarizeni_reference_choices(self) -> None:
        current = self.caszarizeni_reference_source.currentText().strip()
        self.caszarizeni_reference_source.blockSignals(True)
        self.caszarizeni_reference_source.clear()
        self.caszarizeni_reference_source.addItem("Mobil / referenční čas v řádcích")
        for i in range(1, 11):
            name = getattr(self, f"caszarizeni_{i}_zarizeni").text().strip()
            if name:
                self.caszarizeni_reference_source.addItem(name)
        idx = self.caszarizeni_reference_source.findText(current)
        self.caszarizeni_reference_source.setCurrentIndex(idx if idx >= 0 else 0)
        self.caszarizeni_reference_source.blockSignals(False)
        self._recalculate_caszarizeni()

    def _caszarizeni_row_offset(self, row: int) -> int | None:
        cas_zarizeni = self._parse_time_minutes(getattr(self, f"caszarizeni_{row}_cas_zarizeni").text())
        cas_ref = self._parse_time_minutes(getattr(self, f"caszarizeni_{row}_cas_mobil").text())
        if cas_zarizeni is None or cas_ref is None:
            return None
        return cas_zarizeni - cas_ref

    def _caszarizeni_reference_row(self) -> int | None:
        value = self.caszarizeni_reference_source.currentText().strip()
        if not value or value.startswith("Mobil"):
            return None
        for i in range(1, 11):
            name = getattr(self, f"caszarizeni_{i}_zarizeni").text().strip()
            if name and value == name:
                return i
        return None

    def _add_chronologie_entry(self) -> None:
        dialog = MuChronologieEntryDialog(
            self,
            title="Přidat událost",
            default_date=self._started_at,
        )
        if not dialog.exec():
            return
        entry = dialog.get_entry()
        entry["id"] = str(uuid.uuid4())
        entry["source"] = "manual"
        self._chronologie_entries.append(entry)
        self._sort_chronologie_entries()
        self._refresh_chronologie_table()

    def _edit_chronologie_entry(self) -> None:
        entry = self._selected_display_entry()
        if entry is None:
            return
        if entry.get("source") == "system":
            QMessageBox.information(
                self,
                "Chronologie událostí",
                "Systémovou událost nelze upravit.",
            )
            return
        manual_index = self._manual_entry_index(entry.get("id"))
        if manual_index is None:
            return
        entry = self._chronologie_entries[manual_index]
        dialog = MuChronologieEntryDialog(self, entry=entry, title="Upravit událost")
        if not dialog.exec():
            return
        updated = dialog.get_entry()
        updated["id"] = entry.get("id") or str(uuid.uuid4())
        updated["source"] = "manual"
        self._chronologie_entries[manual_index] = updated
        self._sort_chronologie_entries()
        self._refresh_chronologie_table()

    def _delete_chronologie_entry(self) -> None:
        entry = self._selected_display_entry()
        if entry is None:
            return
        if entry.get("source") == "system":
            QMessageBox.information(
                self,
                "Chronologie událostí",
                "Systémovou událost nelze odebrat.",
            )
            return
        manual_index = self._manual_entry_index(entry.get("id"))
        if manual_index is None:
            return
        self._chronologie_entries.pop(manual_index)
        self._refresh_chronologie_table()

    def _selected_chronologie_row(self) -> int | None:
        selected = self.chronologie_table.selectionModel().selectedRows()
        if not selected:
            return None
        return selected[0].row()

    def _selected_display_entry(self) -> dict | None:
        row = self._selected_chronologie_row()
        if row is None or row >= len(self._display_entries):
            return None
        return self._display_entries[row]

    def _manual_entry_index(self, entry_id: str | None) -> int | None:
        if not entry_id:
            return None
        for index, entry in enumerate(self._chronologie_entries):
            if entry.get("id") == entry_id:
                return index
        return None

    def _update_chronologie_toolbar_state(self) -> None:
        entry = self._selected_display_entry()
        is_system = entry is not None and entry.get("source") == "system"
        self.chronologie_edit_btn.setEnabled(not is_system)
        self.chronologie_delete_btn.setEnabled(not is_system)

    def _system_chronologie_events(self) -> list[dict]:
        return build_system_chronologie_events(
            started_at=self._started_at,
            source_type=self._source_type,
            source_id=self._source_id,
            oznameni_datum=self._oznameni_datum,
            oznameni_cas=self._oznameni_cas,
        )

    def _merged_chronologie_entries(self) -> list[dict]:
        merged = self._system_chronologie_events() + list(self._chronologie_entries)
        return self._sort_chronologie_entries_list(merged)

    def _normalize_chronologie(self, entries: list[dict]) -> list[dict]:
        normalized = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("source") == "system":
                continue
            normalized.append(
                {
                    "id": entry.get("id") or str(uuid.uuid4()),
                    "datum": (entry.get("datum") or "").strip(),
                    "cas": (entry.get("cas") or "").strip(),
                    "typ": (entry.get("typ") or "").strip(),
                    "popis": (entry.get("popis") or "").strip(),
                    "source": "manual",
                }
            )
        return self._sort_chronologie_entries_list(normalized)

    def _sort_chronologie_entries(self) -> None:
        self._chronologie_entries = self._sort_chronologie_entries_list(self._chronologie_entries)

    def _sort_chronologie_entries_list(self, entries: list[dict]) -> list[dict]:
        return sorted(entries, key=self._chronologie_sort_key)

    def _chronologie_sort_key(self, entry: dict) -> tuple:
        date_key = entry.get("datum") or "9999-12-31"
        time_key = self._parse_time_minutes(entry.get("cas")) or 24 * 3600
        return (date_key, time_key, entry.get("typ") or "", entry.get("id") or "")

    def _refresh_chronologie_table(self) -> None:
        self._display_entries = self._merged_chronologie_entries()
        self.chronologie_table.setRowCount(len(self._display_entries))
        for row, entry in enumerate(self._display_entries):
            is_system = entry.get("source") == "system"
            values = (
                self._format_chronologie_date(entry.get("datum")),
                entry.get("cas") or "",
                entry.get("typ") or "",
                entry.get("popis") or "",
                "Systém" if is_system else "Ruční",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if is_system:
                    item.setToolTip("Systémová událost odvozená ze spisu nebo zdrojového záznamu.")
                self.chronologie_table.setItem(row, column, item)
        self._update_chronologie_toolbar_state()

    def _format_chronologie_date(self, raw_date: str) -> str:
        raw_date = (raw_date or "").strip()
        if not raw_date:
            return ""
        try:
            return datetime.fromisoformat(raw_date).strftime("%d.%m.%Y")
        except ValueError:
            return raw_date

    def _radio_choice(self, labels: list[str]) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        for text in labels:
            layout.addWidget(QRadioButton(text))
        layout.addStretch()
        return box

    def _radio_choice_value(self, box: QWidget) -> str:
        for child in box.findChildren(QRadioButton):
            if child.isChecked():
                return child.text()
        return ""

    def _set_radio_choice(self, box: QWidget, value: str) -> None:
        if not value:
            return
        for child in box.findChildren(QRadioButton):
            if child.text() == value:
                child.setChecked(True)
                return

    def _parse_time_minutes(self, text: str) -> int | None:
        text = (text or "").strip()
        if not text:
            return None
        text = text.replace(".", ":")
        parts = text.split(":")
        try:
            if len(parts) == 1:
                h = int(parts[0])
                m = 0
                s = 0
            else:
                h = int(parts[0])
                m = int(parts[1])
                s = int(parts[2]) if len(parts) > 2 else 0
            if h < 0 or h > 23 or m < 0 or m > 59 or s < 0 or s > 59:
                return None
            return h * 3600 + m * 60 + s
        except Exception:
            return None

    def _format_time_minutes(self, seconds: int) -> str:
        if seconds is None:
            return ""
        seconds = seconds % (24 * 3600)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _format_time_delta(self, seconds: int | None) -> str:
        if seconds is None:
            return ""
        sign = "+" if seconds >= 0 else "-"
        seconds = abs(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{sign}{h:02d}:{m:02d}:{s:02d}"

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
        return "".join(parts) or "Foto"
