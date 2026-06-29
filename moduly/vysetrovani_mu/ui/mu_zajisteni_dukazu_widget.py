import json
import unicodedata
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.services.attachment_service import attachment_service
from core.shared.constants import ENTITY_MU_INVESTIGATION
from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.vysetrovani_mu.sluzby.mu_source_context import MuSourceContext


class MuZajisteniDukazuWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._saved_data: dict = {}
        self._investigation_id: int | None = None
        self._number_slug = "bez-cisla"
        self._event_number = ""
        self._loaded_from_record = False
        self._dukazy_cas_fotek_manual = False
        self._dukazy_syncing_cas_fotek = False

        self._init_widgets()
        self._build_ui()

    def set_context(
        self,
        investigation_id: int | None,
        *,
        event_number: str = "",
        context: MuSourceContext | None = None,
    ) -> None:
        self._investigation_id = investigation_id
        self._event_number = event_number.strip()
        number = self._event_number or self._number_slug
        self._number_slug = str(number).replace("/", "-").replace("\\", "-").strip() or "bez-cisla"
        self.event_number_label.setText(self._event_number)

        if hasattr(self, "dukazy_attachment_widget"):
            self.dukazy_attachment_widget.set_entity(ENTITY_MU_INVESTIGATION, investigation_id)

        if self._loaded_from_record or context is None:
            return

        if context.default_oznameni_datum and self.dukazy_datum.get_date() is None:
            self.dukazy_datum.set_date_value(context.default_oznameni_datum)
        if context.default_oznameni_cas and not self.dukazy_cas.text().strip():
            self.dukazy_cas.setText(context.default_oznameni_cas)
        if context.default_oznameni_komu and not self.dukazy_provedl.currentText().strip():
            provedl = context.default_oznameni_komu
            index = self.dukazy_provedl.findText(provedl)
            if index >= 0:
                self.dukazy_provedl.setCurrentIndex(index)
            else:
                self.dukazy_provedl.setEditText(provedl)
        if context.default_oznameni_datum and self.dukazy_datum_fotek.get_date() is None:
            self.dukazy_datum_fotek.set_date_value(context.default_oznameni_datum)
        if context.default_oznameni_cas and not self.dukazy_cas_fotek.text().strip():
            self.dukazy_cas_fotek.setText(context.default_oznameni_cas)

    def load_json(self, raw_json: str) -> None:
        self._loaded_from_record = True
        try:
            self._saved_data = json.loads(raw_json or "{}")
        except Exception:
            self._saved_data = {}
        self._apply_saved_data()

    def get_json(self) -> str:
        return json.dumps(self.get_data(), ensure_ascii=False)

    def get_data(self) -> dict:
        return {
            "datum": self._date_to_json(self.dukazy_datum),
            "cas": self.dukazy_cas.text().strip(),
            "provedl": self.dukazy_provedl.currentText().strip(),
            "presne_misto": self.dukazy_presne_misto_text.toPlainText().strip(),
            "stav_povrchu": self.dukazy_stav_povrchu_text.toPlainText().strip(),
            "osvetleni_viditelnost": self.dukazy_osvetleni_viditelnost_text.toPlainText().strip(),
            "pocasi_podminky": self.dukazy_pocasi_podminky_text.toPlainText().strip(),
            "prekazky_znaceni_okoli": self.dukazy_prekazky_znaceni_okoli_text.toPlainText().strip(),
            "stav_zarizeni_nastroju_oopp": self.dukazy_stav_zarizeni_nastroju_oopp_text.toPlainText().strip(),
            "chemikalie_skvrny": self.dukazy_chemikalie_skvrny_text.toPlainText().strip(),
            "sirsi_okoli": self.dukazy_sirsi_okoli_text.toPlainText().strip(),
            "fotky": dict(self.dukazy_photo_paths),
            "nacrt_porizen": self.dukazy_nacrt_porizen.isChecked(),
            "datum_fotek": self._date_to_json(self.dukazy_datum_fotek),
            "cas_fotek": self.dukazy_cas_fotek.text().strip(),
            "kamerovy_zaznam": self._radio_choice_value(self.dukazy_kamerovy_zaznam_ano_ne),
            "dochazka_datum": self._date_to_json(self.dukazy_dochazka_datum),
            "dochazka_cas": self.dukazy_dochazka_cas.text().strip(),
            "pracovni_postup": self._radio_choice_value(self.dukazy_pracovni_postup_ano_ne),
            "provozni_dokumentace": self.dukazy_provozni_dokumentace_text.toPlainText().strip(),
            "provozni_zaznamy": self.dukazy_provozni_zaznamy_text.toPlainText().strip(),
            "poznamka": self.dukazy_poznamka.toPlainText().strip(),
        }

    def _init_widgets(self) -> None:
        saved = self._saved_data

        self.dukazy_datum = self._new_date_edit()
        if saved.get("datum"):
            self._set_date_widget(self.dukazy_datum, saved.get("datum"))

        self.dukazy_cas = QLineEdit()
        self.dukazy_cas.setPlaceholderText("např. 14:35")
        if saved.get("cas"):
            self.dukazy_cas.setText(saved.get("cas"))

        self.dukazy_provedl = ThpWorkerSelector()
        self.dukazy_provedl.setEditable(True)
        provedl = saved.get("provedl") or ""
        if provedl:
            index = self.dukazy_provedl.findText(provedl)
            if index >= 0:
                self.dukazy_provedl.setCurrentIndex(index)
            else:
                self.dukazy_provedl.setEditText(provedl)

        self.dukazy_presne_misto_text = QTextEdit()
        self.dukazy_stav_povrchu_text = QTextEdit()
        self.dukazy_osvetleni_viditelnost_text = QTextEdit()
        self.dukazy_pocasi_podminky_text = QTextEdit()
        self.dukazy_prekazky_znaceni_okoli_text = QTextEdit()
        self.dukazy_stav_zarizeni_nastroju_oopp_text = QTextEdit()
        self.dukazy_chemikalie_skvrny_text = QTextEdit()
        self.dukazy_sirsi_okoli_text = QTextEdit()
        for key, widget in {
            "presne_misto": self.dukazy_presne_misto_text,
            "stav_povrchu": self.dukazy_stav_povrchu_text,
            "osvetleni_viditelnost": self.dukazy_osvetleni_viditelnost_text,
            "pocasi_podminky": self.dukazy_pocasi_podminky_text,
            "prekazky_znaceni_okoli": self.dukazy_prekazky_znaceni_okoli_text,
            "stav_zarizeni_nastroju_oopp": self.dukazy_stav_zarizeni_nastroju_oopp_text,
            "chemikalie_skvrny": self.dukazy_chemikalie_skvrny_text,
            "sirsi_okoli": self.dukazy_sirsi_okoli_text,
        }.items():
            widget.setPlainText(saved.get(key, ""))

        self.dukazy_photo_statuses: dict[str, QLabel] = {}
        self.dukazy_photo_paths = dict(saved.get("fotky", {}) or {})

        self.dukazy_nacrt_porizen = QCheckBox(
            "Náčrt místa: rozměry, vzdálenosti, výšky, úhly, umístění a poloha důležitých předmětů"
        )
        self.dukazy_nacrt_porizen.setChecked(bool(saved.get("nacrt_porizen", False)))
        self.dukazy_datum_fotek = self._new_date_edit()
        if saved.get("datum_fotek"):
            self._set_date_widget(self.dukazy_datum_fotek, saved.get("datum_fotek"))
        self.dukazy_cas_fotek = QLineEdit()
        self.dukazy_cas_fotek.setPlaceholderText("čas pořízení fotek / videa")
        if saved.get("cas_fotek"):
            self.dukazy_cas_fotek.setText(saved.get("cas_fotek"))

        if saved.get("cas_fotek"):
            self._dukazy_cas_fotek_manual = saved.get("cas_fotek") != self.dukazy_cas.text()
        self.dukazy_cas.textChanged.connect(self._sync_dukazy_cas_fotek_from_provedeni)
        self.dukazy_cas_fotek.textChanged.connect(self._on_dukazy_cas_fotek_user_edit)

        self.dukazy_kamerovy_zaznam_ano_ne = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.dukazy_kamerovy_zaznam_ano_ne, saved.get("kamerovy_zaznam", ""))
        self.dukazy_dochazka_datum = self._new_date_edit()
        if saved.get("dochazka_datum"):
            self._set_date_widget(self.dukazy_dochazka_datum, saved.get("dochazka_datum"))
        self.dukazy_dochazka_cas = QLineEdit()
        self.dukazy_dochazka_cas.setPlaceholderText("např. 06:00")
        self.dukazy_dochazka_cas.setText(saved.get("dochazka_cas", ""))
        self.dukazy_pracovni_postup_ano_ne = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.dukazy_pracovni_postup_ano_ne, saved.get("pracovni_postup", ""))
        self.dukazy_provozni_dokumentace_text = QTextEdit()
        self.dukazy_provozni_dokumentace_text.setPlainText(saved.get("provozni_dokumentace", ""))
        self.dukazy_provozni_zaznamy_text = QTextEdit()
        self.dukazy_provozni_zaznamy_text.setPlainText(saved.get("provozni_zaznamy", ""))
        self.dukazy_poznamka = QTextEdit()
        self.dukazy_poznamka.setPlainText(saved.get("poznamka", ""))

    def _apply_saved_data(self) -> None:
        saved = self._saved_data
        if saved.get("datum"):
            self._set_date_widget(self.dukazy_datum, saved.get("datum"))
        self.dukazy_cas.setText(saved.get("cas", ""))
        provedl = saved.get("provedl") or ""
        if provedl:
            index = self.dukazy_provedl.findText(provedl)
            if index >= 0:
                self.dukazy_provedl.setCurrentIndex(index)
            else:
                self.dukazy_provedl.setEditText(provedl)
        for key, widget in {
            "presne_misto": self.dukazy_presne_misto_text,
            "stav_povrchu": self.dukazy_stav_povrchu_text,
            "osvetleni_viditelnost": self.dukazy_osvetleni_viditelnost_text,
            "pocasi_podminky": self.dukazy_pocasi_podminky_text,
            "prekazky_znaceni_okoli": self.dukazy_prekazky_znaceni_okoli_text,
            "stav_zarizeni_nastroju_oopp": self.dukazy_stav_zarizeni_nastroju_oopp_text,
            "chemikalie_skvrny": self.dukazy_chemikalie_skvrny_text,
            "sirsi_okoli": self.dukazy_sirsi_okoli_text,
        }.items():
            widget.setPlainText(saved.get(key, ""))
        self.dukazy_photo_paths = dict(saved.get("fotky", {}) or {})
        for key, status in self.dukazy_photo_statuses.items():
            saved_name = self.dukazy_photo_paths.get(key, "")
            status.setText(f"Přiloženo: {saved_name}" if saved_name else "Nepřiloženo")
        self.dukazy_nacrt_porizen.setChecked(bool(saved.get("nacrt_porizen", False)))
        if saved.get("datum_fotek"):
            self._set_date_widget(self.dukazy_datum_fotek, saved.get("datum_fotek"))
        self.dukazy_cas_fotek.setText(saved.get("cas_fotek", ""))
        self._set_radio_choice(self.dukazy_kamerovy_zaznam_ano_ne, saved.get("kamerovy_zaznam", ""))
        if saved.get("dochazka_datum"):
            self._set_date_widget(self.dukazy_dochazka_datum, saved.get("dochazka_datum"))
        self.dukazy_dochazka_cas.setText(saved.get("dochazka_cas", ""))
        self._set_radio_choice(self.dukazy_pracovni_postup_ano_ne, saved.get("pracovni_postup", ""))
        self.dukazy_provozni_dokumentace_text.setPlainText(saved.get("provozni_dokumentace", ""))
        self.dukazy_provozni_zaznamy_text.setPlainText(saved.get("provozni_zaznamy", ""))
        self.dukazy_poznamka.setPlainText(saved.get("poznamka", ""))

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        intro = QLabel(
            "<b>Cíl:</b> zajistit svědky, místo události, fotodokumentaci a potřebné dokumenty tak, "
            "aby nedošlo ke znehodnocení důkazů nebo sladění výpovědí a mohlo dojít "
            "k řádnému vyšetření okolností a příčin vzniku mimořádné události."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        zaklad_group = QGroupBox("Základní údaje")
        zaklad_form = QFormLayout(zaklad_group)
        self.event_number_label = QLabel("")
        zaklad_form.addRow("Číslo události:", self.event_number_label)
        zaklad_form.addRow("Datum provedení:", self.dukazy_datum)
        zaklad_form.addRow("Čas provedení:", self.dukazy_cas)
        zaklad_form.addRow("Provedl:", self.dukazy_provedl)
        layout.addWidget(zaklad_group)

        misto_group = QGroupBox("2. Popis místa události")
        misto_form = QFormLayout(misto_group)
        for widget in (
            self.dukazy_presne_misto_text,
            self.dukazy_stav_povrchu_text,
            self.dukazy_osvetleni_viditelnost_text,
            self.dukazy_pocasi_podminky_text,
            self.dukazy_prekazky_znaceni_okoli_text,
            self.dukazy_stav_zarizeni_nastroju_oopp_text,
            self.dukazy_chemikalie_skvrny_text,
            self.dukazy_sirsi_okoli_text,
        ):
            widget.setMinimumHeight(150)
        misto_form.addRow("Přesné místo události:", self.dukazy_presne_misto_text)
        misto_form.addRow("Stav povrchu / podlahy:", self.dukazy_stav_povrchu_text)
        misto_form.addRow("Osvětlení a viditelnost:", self.dukazy_osvetleni_viditelnost_text)
        misto_form.addRow("Počasí nebo vnitřní podmínky:", self.dukazy_pocasi_podminky_text)
        misto_form.addRow("Překážky, značení, širší okolí:", self.dukazy_prekazky_znaceni_okoli_text)
        misto_form.addRow("Stav zařízení, nástrojů a OOPP:", self.dukazy_stav_zarizeni_nastroju_oopp_text)
        misto_form.addRow("Chemikálie, skvrny, nečistoty:", self.dukazy_chemikalie_skvrny_text)
        misto_form.addRow("Širší okolí události:", self.dukazy_sirsi_okoli_text)
        layout.addWidget(misto_group)

        foto_group = QGroupBox("3. Fotodokumentace, video a náčrt")
        foto_layout = QVBoxLayout(foto_group)
        foto_info = QLabel(
            "U každé položky vložte odpovídající fotografii. Po vložení se položka automaticky označí jako splněná "
            "a fotka se uloží do příloh vyšetřování s jednotným názvem."
        )
        foto_info.setWordWrap(True)
        foto_layout.addWidget(foto_info)
        foto_form_buttons = QFormLayout()
        for label in (
            "Celkový pohled na místo:",
            "Přístupová trasa:",
            "Směr pohybu dotčené osoby:",
            "Detail místa události:",
            "Detail možné příčiny:",
            "Použité zařízení / nástroj:",
            "OOPP, zejména obuv u pádů:",
            "Značení nebo jeho absence:",
        ):
            self._photo_row(foto_form_buttons, label)
        foto_layout.addLayout(foto_form_buttons)
        foto_layout.addWidget(self.dukazy_nacrt_porizen)
        foto_form = QFormLayout()
        foto_form.addRow("Datum pořízení fotek / videa:", self.dukazy_datum_fotek)
        foto_form.addRow("Čas pořízení fotek / videa:", self.dukazy_cas_fotek)
        foto_layout.addLayout(foto_form)
        layout.addWidget(foto_group)

        dokumenty_group = QGroupBox("4. Dokumenty a další důkazy")
        dokumenty_form = QFormLayout(dokumenty_group)
        self.dukazy_provozni_dokumentace_text.setMinimumHeight(160)
        self.dukazy_provozni_zaznamy_text.setMinimumHeight(160)
        dokumenty_form.addRow("Kamerový záznam mohl zachytit průběh události:", self.dukazy_kamerovy_zaznam_ano_ne)
        dokumenty_form.addRow("Datum nástupu na směnu:", self.dukazy_dochazka_datum)
        dokumenty_form.addRow("Čas nástupu na směnu:", self.dukazy_dochazka_cas)
        dokumenty_form.addRow("Byl vydán pracovní postup / příkaz k práci:", self.dukazy_pracovni_postup_ano_ne)
        dokumenty_form.addRow("Provozní dokumentace, údržba, kniha závad/oprav:", self.dukazy_provozni_dokumentace_text)
        dokumenty_form.addRow("Další provozní záznamy:", self.dukazy_provozni_zaznamy_text)
        layout.addWidget(dokumenty_group)

        poznamky_group = QGroupBox("5. Poznámky, nákresy apod.")
        poznamky_layout = QVBoxLayout(poznamky_group)
        self.dukazy_poznamka.setMinimumHeight(180)
        poznamky_layout.addWidget(self.dukazy_poznamka)
        layout.addWidget(poznamky_group)

        prilohy_group = QGroupBox("6. Přílohy zajištění důkazů")
        prilohy_layout = QVBoxLayout(prilohy_group)
        prilohy_info = QLabel(
            "Zde přiložte podepsaný ručně vyplněný formulář, sken zajištění důkazů, "
            "fotodokumentaci nebo další důkazní soubory. Přílohy se ukládají do uživatelského "
            "adresáře aplikace v .local a jsou připravené pro pozdější migraci spolu s databází."
        )
        prilohy_info.setWordWrap(True)
        prilohy_layout.addWidget(prilohy_info)
        self.dukazy_attachment_widget = AttachmentWidget(
            entity_type=ENTITY_MU_INVESTIGATION,
            entity_id=None,
        )
        prilohy_layout.addWidget(self.dukazy_attachment_widget)
        layout.addWidget(prilohy_group)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _photo_row(self, form_layout: QFormLayout, label: str) -> None:
        row = QHBoxLayout()
        btn = QPushButton("Vložit fotku")
        status = QLabel("Nepřiloženo")
        photo_keys = {
            "Celkový pohled na místo:": "CelkovyPohled",
            "Přístupová trasa:": "PristupovaTrasa",
            "Směr pohybu dotčené osoby:": "SmerPohybu",
            "Detail místa události:": "DetailMista",
            "Detail možné příčiny:": "DetailMoznePriciny",
            "Použité zařízení / nástroj:": "ZarizeniNastroj",
            "OOPP, zejména obuv u pádů:": "OOPP",
            "Značení nebo jeho absence:": "Znaceni",
        }
        key = photo_keys.get(label, self._slug(label))
        saved_name = self.dukazy_photo_paths.get(key, "")
        if saved_name:
            status.setText(f"Přiloženo: {saved_name}")
        self.dukazy_photo_statuses[key] = status
        btn.clicked.connect(lambda checked=False, st=status, item_key=key: self._select_photo(st, item_key))
        row.addWidget(btn)
        row.addWidget(status)
        row.addStretch()
        form_layout.addRow(label, row)

    def _select_photo(self, status_label: QLabel, item_key: str) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte fotografii",
            "",
            "Obrázky (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;Všechny soubory (*)",
        )
        if not file_path:
            return

        source = Path(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"Foto-{item_key}-{self._number_slug}_{timestamp}{source.suffix.lower()}"
        attachment = None
        if self._investigation_id is not None:
            attachment = attachment_service.add_file_as(
                ENTITY_MU_INVESTIGATION,
                self._investigation_id,
                str(source),
                new_name,
            )
        final_name = attachment.filename if attachment is not None else new_name
        self.dukazy_photo_paths[item_key] = final_name
        status_label.setText(f"Přiloženo: {final_name}")

    def _sync_dukazy_cas_fotek_from_provedeni(self, text: str) -> None:
        if self._dukazy_cas_fotek_manual:
            return
        self._dukazy_syncing_cas_fotek = True
        self.dukazy_cas_fotek.setText(text)
        self._dukazy_syncing_cas_fotek = False

    def _on_dukazy_cas_fotek_user_edit(self, _text: str) -> None:
        if self._dukazy_syncing_cas_fotek:
            return
        self._dukazy_cas_fotek_manual = True

    def _new_date_edit(self, placeholder: str = "např. 05.06.1982") -> NullableDateEdit:
        widget = NullableDateEdit()
        if hasattr(widget, "setPlaceholderText"):
            widget.setPlaceholderText(placeholder)
        return widget

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

    def _date_value(self, widget) -> object | None:
        if hasattr(widget, "get_date"):
            return widget.get_date()
        return None

    def _date_to_json(self, widget) -> str:
        value = self._date_value(widget)
        if value is None:
            return ""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    def _set_date_widget(self, widget, value) -> None:
        if not value:
            return
        if isinstance(value, str) and hasattr(widget, "set_date_iso"):
            widget.set_date_iso(value)
        elif hasattr(widget, "set_date_value"):
            widget.set_date_value(value)

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
