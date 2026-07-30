import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.services.attachment_service import attachment_service
from core.shared.constants import ENTITY_MU_INVESTIGATION
from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector

# MU-UX-5 / MU-UX-7 – jednotné popisky a šířky sloupců opakovaných seznamů.
_ACTION_WIDTH = 90
_ROW_HEIGHT = 34

_OOPP_HEADERS = (
    "Název OOPP",
    "Datum vydání",
    "Datum ukončení používání",
    "Poznámka",
    "Akce",
)
_OOPP_STRETCHES = (3, 2, 2, 3)

_SKOLENI_HEADERS = (
    "Název školení",
    "Datum školení",
    "Úspěšně absolvováno",
    "Poznámka",
    "Akce",
)
_SKOLENI_STRETCHES = (3, 2, 2, 3)

_ZKOUSKY_HEADERS = (
    "Název zkoušky / odborné způsobilosti",
    "Platnost od",
    "Platnost do",
    "Poznámka",
    "Akce",
)
_ZKOUSKY_STRETCHES = (3, 2, 2, 3)

_KONTROLA_HEADERS = (
    "Datum",
    "Kontroloval",
    "Výsledek",
    "Akce",
)
_KONTROLA_STRETCHES = (2, 3, 3)

TAB_PREDPISY = 0
TAB_ODBORNA = 1
TAB_OOPP = 2
TAB_DALSI = 3

_TAB_TITLES = (
    "Předpisy a kontroly",
    "Odborná způsobilost",
    "OOPP",
    "Další skutečnosti",
)

_FIELD_TO_TAB: dict[str, int] = {
    "dodrz_pracovni_doba": TAB_PREDPISY,
    "dodrz_prescasy": TAB_PREDPISY,
    "dodrz_prescasy_detail": TAB_PREDPISY,
    "dodrz_predpisy_cinnost": TAB_PREDPISY,
    "dodrz_kontrola_predpisu_rows": TAB_PREDPISY,
    "dodrz_kontroly_reviz_zavady": TAB_PREDPISY,
    "dodrz_poruseni_predpisu": TAB_PREDPISY,
    "dodrz_skoleni_rows": TAB_ODBORNA,
    "dodrz_zkousky_rows": TAB_ODBORNA,
    "dodrz_lekar_typ": TAB_ODBORNA,
    "dodrz_lekar_datum": TAB_ODBORNA,
    "dodrz_lekar_platnost": TAB_ODBORNA,
    "dodrz_kvalifikace_splnuje": TAB_ODBORNA,
    "dodrz_kvalifikace_poznamka": TAB_ODBORNA,
    "dodrz_oopp_rows": TAB_OOPP,
    "dodrz_oopp_pouzity": TAB_OOPP,
    "dodrz_stav_oopp": TAB_OOPP,
    "dodrz_vyjadreni_oopp": TAB_OOPP,
    "dodrz_kontrola_oopp_rows": TAB_OOPP,
    "dodrz_ostatni_1": TAB_DALSI,
    "dodrz_ostatni_2": TAB_DALSI,
    "dodrz_priloha": TAB_DALSI,
}


class MuDodrzovaniAttachmentWidget(AttachmentWidget):
    """Přílohy s názvoslovím stejným jako ve Šetření úrazu / ostatních MU záložkách."""

    def __init__(self, parent=None):
        super().__init__(entity_type=ENTITY_MU_INVESTIGATION, entity_id=None, parent=parent)
        self._number_slug = "bez-cisla"

    def set_number_slug(self, slug: str) -> None:
        self._number_slug = slug or "bez-cisla"

    def add_attachment(self) -> None:
        if not self.entity_type or not self.entity_id:
            QMessageBox.information(
                self,
                "Přílohy",
                "Přílohy lze přidat až po uložení záznamu.",
            )
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Vyberte přílohy k dodržování předpisů",
            "",
            "Dokumenty a obrázky (*.pdf *.jpg *.jpeg *.png *.odt *.docx);;Všechny soubory (*.*)",
        )
        if not files:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for file_path in files:
            source = Path(file_path)
            new_name = f"DodrzovaniPredpisu-{self._number_slug}_{timestamp}-{source.name}"
            attachment_service.add_file_as(
                self.entity_type,
                self.entity_id,
                str(source),
                new_name,
            )

        self.reload()


class MuDodrzovaniPredpisuWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._saved_data: dict = {}
        self._investigation_id: int | None = None
        self._number_slug = "bez-cisla"
        self._tab_scroll_positions: dict[int, int] = {}
        self._active_scroll_tab = 0
        self._list_meta: dict[QVBoxLayout, dict] = {}

        self._init_widgets()
        self._build_ui()

    def set_context(
        self,
        investigation_id: int | None,
        *,
        event_number: str = "",
    ) -> None:
        self._investigation_id = investigation_id
        number = event_number.strip()
        self._number_slug = str(number).replace("/", "-").replace("\\", "-").strip() or "bez-cisla"
        if hasattr(self, "dodrzovani_attachment_widget"):
            self.dodrzovani_attachment_widget.set_number_slug(self._number_slug)
            self.dodrzovani_attachment_widget.set_entity(ENTITY_MU_INVESTIGATION, investigation_id)

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
            "dodrz_pracovni_doba": self._radio_choice_value(self.dodrz_pracovni_doba),
            "dodrz_prescasy": self._radio_choice_value(self.dodrz_prescasy),
            "dodrz_prescasy_detail": self.dodrz_prescasy_detail.toPlainText().strip(),
            "dodrz_predpisy_cinnost": self.dodrz_predpisy_cinnost.toPlainText().strip(),
            "dodrz_oopp_rows": [
                {
                    "typ": row["typ"].text().strip(),
                    "datum": self._date_to_json(row["datum"]),
                    "platnost": row["platnost"].text().strip(),
                    "poznamka": row["poznamka"].text().strip(),
                }
                for row in self.dodrz_oopp_rows
            ],
            "dodrz_skoleni_rows": [
                {
                    "typ": row["typ"].text().strip(),
                    "datum": self._date_to_json(row["datum"]),
                    "osnova": self._radio_choice_value(row["osnova"]),
                    "poznamka": row["poznamka"].text().strip(),
                }
                for row in self.dodrz_skoleni_rows
            ],
            "dodrz_lekar_typ": self.dodrz_lekar_typ.currentText().strip(),
            "dodrz_lekar_datum": self._date_to_json(self.dodrz_lekar_datum),
            "dodrz_lekar_platnost": self._date_to_json(self.dodrz_lekar_platnost),
            "dodrz_kvalifikace_splnuje": self._radio_choice_value(self.dodrz_kvalifikace_splnuje),
            "dodrz_kvalifikace_poznamka": self.dodrz_kvalifikace_poznamka.toPlainText().strip(),
            "dodrz_kontroly_reviz_zavady": self.dodrz_kontroly_reviz_zavady.toPlainText().strip(),
            "dodrz_zkousky_rows": [
                {
                    "typ": row["typ"].text().strip(),
                    "datum": self._date_to_json(row["datum"]),
                    "platnost": self._date_to_json(row["platnost"]),
                    "poznamka": row["poznamka"].text().strip(),
                }
                for row in self.dodrz_zkousky_rows
            ],
            "dodrz_ostatni_1": self.dodrz_ostatni_1.toPlainText().strip(),
            "dodrz_oopp_pouzity": self._radio_choice_value(self.dodrz_oopp_pouzity),
            "dodrz_stav_oopp": self.dodrz_stav_oopp.toPlainText().strip(),
            "dodrz_vyjadreni_oopp": self.dodrz_vyjadreni_oopp.toPlainText().strip(),
            "dodrz_kontrola_oopp_rows": [
                {
                    "datum": self._date_to_json(row["datum"]),
                    "kontroloval": self._widget_text(row["kontroloval"]),
                    "vysledek": row["vysledek"].text().strip(),
                }
                for row in self.dodrz_kontrola_oopp_rows
            ],
            "dodrz_kontrola_predpisu_rows": [
                {
                    "datum": self._date_to_json(row["datum"]),
                    "kontroloval": self._widget_text(row["kontroloval"]),
                    "vysledek": row["vysledek"].text().strip(),
                }
                for row in self.dodrz_kontrola_predpisu_rows
            ],
            "dodrz_poruseni_predpisu": self.dodrz_poruseni_predpisu.toPlainText().strip(),
            "dodrz_ostatni_2": self.dodrz_ostatni_2.toPlainText().strip(),
            "dodrz_priloha": "",
        }

    def focus_field(self, field_name: str | None) -> QWidget | None:
        """Přepne vnitřní podzáložku a zaměří pole (Kontrola spisu)."""
        if not field_name:
            return None
        tab_index = _FIELD_TO_TAB.get(field_name)
        if tab_index is not None:
            self.inner_tabs.setCurrentIndex(tab_index)
        widget = self.resolve_field_widget(field_name)
        if widget is not None:
            try:
                widget.setFocus(Qt.FocusReason.OtherFocusReason)
                self._ensure_widget_visible(widget)
            except Exception:
                pass
        return widget

    def resolve_field_widget(self, field_name: str) -> QWidget | None:
        mapping = {
            "dodrz_pracovni_doba": self.dodrz_pracovni_doba,
            "dodrz_prescasy": self.dodrz_prescasy,
            "dodrz_prescasy_detail": self.dodrz_prescasy_detail,
            "dodrz_predpisy_cinnost": self.dodrz_predpisy_cinnost,
            "dodrz_kontrola_predpisu_rows": (
                self.dodrz_kontrola_predpisu_rows[0]["datum"]
                if self.dodrz_kontrola_predpisu_rows
                else None
            ),
            "dodrz_kontroly_reviz_zavady": self.dodrz_kontroly_reviz_zavady,
            "dodrz_poruseni_predpisu": self.dodrz_poruseni_predpisu,
            "dodrz_skoleni_rows": (
                self.dodrz_skoleni_rows[0]["typ"] if self.dodrz_skoleni_rows else None
            ),
            "dodrz_zkousky_rows": (
                self.dodrz_zkousky_rows[0]["typ"] if self.dodrz_zkousky_rows else None
            ),
            "dodrz_lekar_typ": self.dodrz_lekar_typ,
            "dodrz_lekar_datum": self.dodrz_lekar_datum,
            "dodrz_lekar_platnost": self.dodrz_lekar_platnost,
            "dodrz_kvalifikace_splnuje": self.dodrz_kvalifikace_splnuje,
            "dodrz_kvalifikace_poznamka": self.dodrz_kvalifikace_poznamka,
            "dodrz_oopp_rows": self.dodrz_oopp_rows[0]["typ"] if self.dodrz_oopp_rows else None,
            "dodrz_oopp_pouzity": self.dodrz_oopp_pouzity,
            "dodrz_stav_oopp": self.dodrz_stav_oopp,
            "dodrz_vyjadreni_oopp": self.dodrz_vyjadreni_oopp,
            "dodrz_kontrola_oopp_rows": (
                self.dodrz_kontrola_oopp_rows[0]["datum"]
                if self.dodrz_kontrola_oopp_rows
                else None
            ),
            "dodrz_ostatni_1": self.dodrz_ostatni_1,
            "dodrz_ostatni_2": self.dodrz_ostatni_2,
            "dodrz_priloha": getattr(self, "dodrzovani_attachment_widget", None),
        }
        return mapping.get(field_name)

    def _ensure_widget_visible(self, widget: QWidget) -> None:
        scroll = self._scroll_for_tab(self.inner_tabs.currentIndex())
        if scroll is None:
            return
        QTimer.singleShot(0, lambda: scroll.ensureWidgetVisible(widget, 24, 24))

    def _init_widgets(self) -> None:
        saved = self._saved_data

        self.dodrz_pracovni_doba = self._radio_choice(["Dle grafu", "Mimo graf"])
        self._set_radio_choice(self.dodrz_pracovni_doba, saved.get("dodrz_pracovni_doba", ""))
        self.dodrz_prescasy = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.dodrz_prescasy, saved.get("dodrz_prescasy", ""))
        self.dodrz_prescasy_detail = QTextEdit()
        self.dodrz_prescasy_detail.setPlainText(saved.get("dodrz_prescasy_detail", ""))
        self._configure_text_edit(self.dodrz_prescasy_detail, lines=3)

        self.dodrz_predpisy_cinnost = QTextEdit()
        self.dodrz_predpisy_cinnost.setPlainText(saved.get("dodrz_predpisy_cinnost", ""))
        self._configure_text_edit(self.dodrz_predpisy_cinnost, lines=5)

        self.dodrz_oopp_rows = []
        for data in saved.get("dodrz_oopp_rows") or [{}]:
            self.dodrz_oopp_rows.append(self._make_oopp_row(data))

        self.dodrz_skoleni_rows = []
        for data in saved.get("dodrz_skoleni_rows") or [{}]:
            self.dodrz_skoleni_rows.append(self._make_skoleni_row(data))

        self.dodrz_lekar_typ = QComboBox()
        self.dodrz_lekar_typ.addItems(["Periodická", "Vstupní", "Mimořádná", "Výstupní", "Následná"])
        if saved.get("dodrz_lekar_typ"):
            self.dodrz_lekar_typ.setCurrentText(saved.get("dodrz_lekar_typ"))

        self.dodrz_lekar_datum = self._new_date_edit()
        self.dodrz_lekar_platnost = self._new_date_edit()
        if saved.get("dodrz_lekar_datum"):
            self._set_date_widget(self.dodrz_lekar_datum, saved.get("dodrz_lekar_datum"))
        if saved.get("dodrz_lekar_platnost"):
            self._set_date_widget(self.dodrz_lekar_platnost, saved.get("dodrz_lekar_platnost"))

        self.dodrz_kvalifikace_splnuje = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.dodrz_kvalifikace_splnuje, saved.get("dodrz_kvalifikace_splnuje", ""))
        self.dodrz_kvalifikace_poznamka = QTextEdit()
        self.dodrz_kvalifikace_poznamka.setPlainText(saved.get("dodrz_kvalifikace_poznamka", ""))
        self._configure_text_edit(self.dodrz_kvalifikace_poznamka, lines=4)

        self.dodrz_kontroly_reviz_zavady = QTextEdit()
        self.dodrz_kontroly_reviz_zavady.setPlainText(saved.get("dodrz_kontroly_reviz_zavady", ""))
        self._configure_text_edit(self.dodrz_kontroly_reviz_zavady, lines=5)

        self.dodrz_zkousky_rows = []
        for data in saved.get("dodrz_zkousky_rows") or [{}]:
            self.dodrz_zkousky_rows.append(self._make_zkouska_row(data))

        self.dodrz_ostatni_1 = QTextEdit()
        self.dodrz_ostatni_1.setPlainText(saved.get("dodrz_ostatni_1", ""))
        self._configure_text_edit(self.dodrz_ostatni_1, lines=5)
        self.dodrz_oopp_pouzity = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.dodrz_oopp_pouzity, saved.get("dodrz_oopp_pouzity", ""))
        self.dodrz_stav_oopp = QTextEdit()
        self.dodrz_stav_oopp.setPlainText(saved.get("dodrz_stav_oopp", ""))
        self._configure_text_edit(self.dodrz_stav_oopp, lines=4)
        self.dodrz_vyjadreni_oopp = QTextEdit()
        self.dodrz_vyjadreni_oopp.setPlainText(saved.get("dodrz_vyjadreni_oopp", ""))
        self._configure_text_edit(self.dodrz_vyjadreni_oopp, lines=6)

        self.dodrz_kontrola_oopp_rows = self._make_kontrola_rows(saved.get("dodrz_kontrola_oopp_rows"))
        self.dodrz_kontrola_predpisu_rows = self._make_kontrola_rows(saved.get("dodrz_kontrola_predpisu_rows"))

        self.dodrz_poruseni_predpisu = QTextEdit()
        self.dodrz_poruseni_predpisu.setPlainText(saved.get("dodrz_poruseni_predpisu", ""))
        self._configure_text_edit(self.dodrz_poruseni_predpisu, lines=5)
        self.dodrz_ostatni_2 = QTextEdit()
        self.dodrz_ostatni_2.setPlainText(saved.get("dodrz_ostatni_2", ""))
        self._configure_text_edit(self.dodrz_ostatni_2, lines=5)

    def _apply_saved_data(self) -> None:
        saved = self._saved_data

        self._set_radio_choice(self.dodrz_pracovni_doba, saved.get("dodrz_pracovni_doba", ""))
        self._set_radio_choice(self.dodrz_prescasy, saved.get("dodrz_prescasy", ""))
        self.dodrz_prescasy_detail.setPlainText(saved.get("dodrz_prescasy_detail", ""))
        self.dodrz_prescasy_detail.setVisible(self._radio_choice_value(self.dodrz_prescasy) == "ANO")

        self.dodrz_predpisy_cinnost.setPlainText(saved.get("dodrz_predpisy_cinnost", ""))

        self.dodrz_oopp_rows = []
        for data in saved.get("dodrz_oopp_rows") or [{}]:
            self.dodrz_oopp_rows.append(self._make_oopp_row(data))
        self._rebuild_dynamic_rows(self.dodrz_oopp_rows_layout, self.dodrz_oopp_rows)

        self.dodrz_skoleni_rows = []
        for data in saved.get("dodrz_skoleni_rows") or [{}]:
            self.dodrz_skoleni_rows.append(self._make_skoleni_row(data))
        self._rebuild_dynamic_rows(self.dodrz_skoleni_rows_layout, self.dodrz_skoleni_rows)

        if saved.get("dodrz_lekar_typ"):
            self.dodrz_lekar_typ.setCurrentText(saved.get("dodrz_lekar_typ"))
        self._set_date_widget(self.dodrz_lekar_datum, saved.get("dodrz_lekar_datum"))
        self._set_date_widget(self.dodrz_lekar_platnost, saved.get("dodrz_lekar_platnost"))

        self._set_radio_choice(self.dodrz_kvalifikace_splnuje, saved.get("dodrz_kvalifikace_splnuje", ""))
        self.dodrz_kvalifikace_poznamka.setPlainText(saved.get("dodrz_kvalifikace_poznamka", ""))
        self.dodrz_kontroly_reviz_zavady.setPlainText(saved.get("dodrz_kontroly_reviz_zavady", ""))

        self.dodrz_zkousky_rows = []
        for data in saved.get("dodrz_zkousky_rows") or [{}]:
            self.dodrz_zkousky_rows.append(self._make_zkouska_row(data))
        self._rebuild_dynamic_rows(self.dodrz_zkousky_rows_layout, self.dodrz_zkousky_rows)

        self.dodrz_ostatni_1.setPlainText(saved.get("dodrz_ostatni_1", ""))
        self._set_radio_choice(self.dodrz_oopp_pouzity, saved.get("dodrz_oopp_pouzity", ""))
        self.dodrz_stav_oopp.setPlainText(saved.get("dodrz_stav_oopp", ""))
        self.dodrz_vyjadreni_oopp.setPlainText(saved.get("dodrz_vyjadreni_oopp", ""))

        self.dodrz_kontrola_oopp_rows = self._make_kontrola_rows(saved.get("dodrz_kontrola_oopp_rows"))
        self._rebuild_dynamic_rows(self.dodrz_kontrola_oopp_rows_layout, self.dodrz_kontrola_oopp_rows)

        self.dodrz_kontrola_predpisu_rows = self._make_kontrola_rows(saved.get("dodrz_kontrola_predpisu_rows"))
        self._rebuild_dynamic_rows(
            self.dodrz_kontrola_predpisu_rows_layout,
            self.dodrz_kontrola_predpisu_rows,
        )

        self.dodrz_poruseni_predpisu.setPlainText(saved.get("dodrz_poruseni_predpisu", ""))
        self.dodrz_ostatni_2.setPlainText(saved.get("dodrz_ostatni_2", ""))

    def _build_ui(self) -> None:
        """MU-UX-7 – vnitřní pracovní podzáložky."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.inner_tabs = QTabWidget()
        self.inner_tabs.setObjectName("muDodrzInnerTabs")
        self._tab_scrolls: list[QScrollArea] = []

        builders = (
            self._build_tab_predpisy_a_kontroly,
            self._build_tab_odborna_zpusobilost,
            self._build_tab_oopp,
            self._build_tab_dalsi_skutecnosti,
        )
        for title, builder in zip(_TAB_TITLES, builders, strict=True):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            content = builder()
            scroll.setWidget(content)
            self._tab_scrolls.append(scroll)
            self.inner_tabs.addTab(scroll, title)

        self.inner_tabs.currentChanged.connect(self._on_inner_tab_changed)
        outer.addWidget(self.inner_tabs)

    def _on_inner_tab_changed(self, index: int) -> None:
        prev = self._active_scroll_tab
        if 0 <= prev < len(self._tab_scrolls):
            self._tab_scroll_positions[prev] = self._tab_scrolls[prev].verticalScrollBar().value()
        self._active_scroll_tab = index
        if 0 <= index < len(self._tab_scrolls):
            value = self._tab_scroll_positions.get(index, 0)
            scroll = self._tab_scrolls[index]

            def restore() -> None:
                scroll.verticalScrollBar().setValue(value)

            QTimer.singleShot(0, restore)

    def _scroll_for_tab(self, index: int) -> QScrollArea | None:
        if 0 <= index < len(self._tab_scrolls):
            return self._tab_scrolls[index]
        return None

    def _tab_page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 16)
        layout.setSpacing(12)
        return page, layout

    def _make_group(self, title: str) -> tuple[QGroupBox, QVBoxLayout]:
        box = QGroupBox(title)
        box.setFlat(True)
        body = QVBoxLayout(box)
        body.setContentsMargins(8, 10, 8, 8)
        body.setSpacing(8)
        return box, body

    def _build_tab_predpisy_a_kontroly(self) -> QWidget:
        page, layout = self._tab_page()

        pracovni, body = self._make_group("Pracovní doba")
        form = QFormLayout()
        form.setSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Dodržování pracovní doby:", self.dodrz_pracovni_doba)
        form.addRow("Přesčasy:", self.dodrz_prescasy)
        form.addRow("Detail přesčasové práce:", self.dodrz_prescasy_detail)
        body.addLayout(form)
        self._connect_prescasy_detail_visibility()
        layout.addWidget(pracovni)

        predpisy, body = self._make_group("Předpisy pro činnost")
        self.dodrz_predpisy_cinnost.setPlaceholderText(
            "Jaké předpisy platily pro činnost při události…"
        )
        body.addWidget(self.dodrz_predpisy_cinnost)
        layout.addWidget(predpisy)

        kpred, body = self._make_group("Kontrola dodržování předpisů")
        self.dodrz_kontrola_predpisu_layout, self.dodrz_kontrola_predpisu_rows_layout = (
            self._create_dynamic_list(
                body,
                self.dodrz_kontrola_predpisu_rows,
                _KONTROLA_HEADERS,
                _KONTROLA_STRETCHES,
                self._kontrola_row_widgets,
                "Přidat kontrolu",
                self.add_dodrz_kontrola_predpisu_row,
                list_kind="kontrola_predpisu",
            )
        )
        layout.addWidget(kpred)

        kontroly, body = self._make_group("Kontroly, revize a zjevné závady")
        self.dodrz_kontroly_reviz_zavady.setPlaceholderText(
            "Závěry kontrol a revizí, zjevné závady…"
        )
        body.addWidget(self.dodrz_kontroly_reviz_zavady)
        layout.addWidget(kontroly)

        poruseni, body = self._make_group("Porušení předpisů")
        self.dodrz_poruseni_predpisu.setPlaceholderText("Zjištěná porušení předpisů…")
        body.addWidget(self.dodrz_poruseni_predpisu)
        layout.addWidget(poruseni)

        layout.addStretch(1)
        return page

    def _build_tab_odborna_zpusobilost(self) -> QWidget:
        page, layout = self._tab_page()

        skoleni, body = self._make_group("Školení")
        self.dodrz_skoleni_layout, self.dodrz_skoleni_rows_layout = self._create_dynamic_list(
            body,
            self.dodrz_skoleni_rows,
            _SKOLENI_HEADERS,
            _SKOLENI_STRETCHES,
            self._skoleni_row_widgets,
            "Přidat školení",
            self.add_dodrz_skoleni_row,
            list_kind="skoleni",
        )
        layout.addWidget(skoleni)

        zkousky, body = self._make_group("Zkoušky a odborná způsobilost")
        self.dodrz_zkousky_layout, self.dodrz_zkousky_rows_layout = self._create_dynamic_list(
            body,
            self.dodrz_zkousky_rows,
            _ZKOUSKY_HEADERS,
            _ZKOUSKY_STRETCHES,
            self._zkouska_row_widgets,
            "Přidat zkoušku",
            self.add_dodrz_zkouska_row,
            list_kind="zkousky",
        )
        layout.addWidget(zkousky)

        lekar, body = self._make_group("Lékařská prohlídka")
        form = QFormLayout()
        form.setSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Typ prohlídky:", self.dodrz_lekar_typ)
        form.addRow("Datum prohlídky:", self.dodrz_lekar_datum)
        form.addRow("Platnost do:", self.dodrz_lekar_platnost)
        body.addLayout(form)
        layout.addWidget(lekar)

        kval, body = self._make_group("Kvalifikace k pracovní činnosti")
        form = QFormLayout()
        form.setSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Splňuje kvalifikaci:", self.dodrz_kvalifikace_splnuje)
        form.addRow("Poznámka:", self.dodrz_kvalifikace_poznamka)
        body.addLayout(form)
        layout.addWidget(kval)

        layout.addStretch(1)
        return page

    def _build_tab_oopp(self) -> QWidget:
        page, layout = self._tab_page()

        oopp, body = self._make_group("Přidělené OOPP")
        self.dodrz_oopp_layout, self.dodrz_oopp_rows_layout = self._create_dynamic_list(
            body,
            self.dodrz_oopp_rows,
            _OOPP_HEADERS,
            _OOPP_STRETCHES,
            self._oopp_row_widgets,
            "Přidat OOPP",
            self.add_dodrz_oopp_row,
            list_kind="oopp",
        )
        layout.addWidget(oopp)

        pouzivani, body = self._make_group("Používání OOPP při události")
        form = QFormLayout()
        form.setSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("OOPP byly použity:", self.dodrz_oopp_pouzity)
        body.addLayout(form)
        layout.addWidget(pouzivani)

        stav, body = self._make_group("Stav OOPP")
        self.dodrz_stav_oopp.setPlaceholderText("Stav OOPP v době události…")
        body.addWidget(self.dodrz_stav_oopp)
        layout.addWidget(stav)

        vyj, body = self._make_group("Vyjádření zaměstnance")
        body.addWidget(QLabel("Vyjádření / stanovisko:"))
        self.dodrz_vyjadreni_oopp.setPlaceholderText(
            "Co k používání OOPP uvedl zaměstnanec…"
        )
        body.addWidget(self.dodrz_vyjadreni_oopp)
        layout.addWidget(vyj)

        koopp, body = self._make_group("Kontrola OOPP")
        self.dodrz_kontrola_oopp_layout, self.dodrz_kontrola_oopp_rows_layout = (
            self._create_dynamic_list(
                body,
                self.dodrz_kontrola_oopp_rows,
                _KONTROLA_HEADERS,
                _KONTROLA_STRETCHES,
                self._kontrola_row_widgets,
                "Přidat kontrolu",
                self.add_dodrz_kontrola_oopp_row,
                list_kind="kontrola_oopp",
            )
        )
        layout.addWidget(koopp)

        layout.addStretch(1)
        return page

    def _build_tab_dalsi_skutecnosti(self) -> QWidget:
        page, layout = self._tab_page()

        z1, body = self._make_group("Záznamy k předpisům a kontrolám")
        body.addWidget(self.dodrz_ostatni_1)
        layout.addWidget(z1)

        z2, body = self._make_group("Záznamy k dotčené osobě a OOPP")
        body.addWidget(self.dodrz_ostatni_2)
        layout.addWidget(z2)

        prilohy, body = self._make_group("Přílohy k dodržování předpisů")
        hint = QLabel(
            "Zde přiložte sken nebo dokument vztahující se k této části šetření. "
            "Přílohy lze přidat až po uložení vyšetřování."
        )
        hint.setWordWrap(True)
        body.addWidget(hint)
        self.dodrzovani_attachment_widget = MuDodrzovaniAttachmentWidget()
        body.addWidget(self.dodrzovani_attachment_widget)
        layout.addWidget(prilohy)

        layout.addStretch(1)
        return page

    def _create_dynamic_list(
        self,
        parent_layout: QVBoxLayout,
        rows: list[dict],
        headers: tuple[str, ...],
        stretches: tuple[int, ...],
        widgets_fn,
        add_label: str,
        add_slot,
        *,
        list_kind: str,
    ) -> tuple[QVBoxLayout, QVBoxLayout]:
        """Kompaktní editor: hlavička (samostatný widget) + řádky + Přidat."""
        host = QWidget()
        host.setObjectName(f"muDodrzList_{list_kind}")
        host.setProperty("muDodrzList", True)
        outer = QVBoxLayout(host)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        header = self._make_header_widget(headers, stretches)
        header.setObjectName(f"muDodrzListHeader_{list_kind}")
        outer.addWidget(header)

        rows_host = QWidget()
        rows_host.setObjectName(f"muDodrzListRows_{list_kind}")
        rows_layout = QVBoxLayout(rows_host)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(4)
        outer.addWidget(rows_host)

        btn = QPushButton(add_label)
        btn.clicked.connect(add_slot)
        outer.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft)

        parent_layout.addWidget(host)

        self._list_meta[rows_layout] = {
            "kind": list_kind,
            "stretches": stretches,
            "widgets_fn": widgets_fn,
            "outer": outer,
            "header": header,
        }
        self._rebuild_dynamic_rows(rows_layout, rows)
        return outer, rows_layout

    def _make_header_widget(
        self,
        headers: tuple[str, ...],
        stretches: tuple[int, ...],
    ) -> QWidget:
        widget = QWidget()
        widget.setProperty("muDodrzListHeader", True)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(8)
        data_headers = headers[:-1] if headers and headers[-1] == "Akce" else headers
        for text, stretch in zip(data_headers, stretches, strict=True):
            label = QLabel(text)
            label.setWordWrap(True)
            font = label.font()
            font.setBold(True)
            label.setFont(font)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            layout.addWidget(label, stretch)
        action = QLabel("Akce" if headers and headers[-1] == "Akce" else "")
        font = action.font()
        font.setBold(True)
        action.setFont(font)
        action.setFixedWidth(_ACTION_WIDTH)
        action.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(action, 0)
        return widget

    def _make_row_widget(
        self,
        widgets: list,
        stretches: tuple[int, ...],
        rows: list[dict],
        index: int,
        rows_layout: QVBoxLayout,
    ) -> QWidget:
        row_widget = QWidget()
        row_widget.setProperty("muDodrzListRow", True)
        layout = QHBoxLayout(row_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for widget, stretch in zip(widgets, stretches, strict=True):
            self._style_row_field(widget)
            layout.addWidget(widget, stretch)
        remove_btn = QPushButton("Odebrat")
        remove_btn.setFixedWidth(_ACTION_WIDTH)
        remove_btn.setFixedHeight(_ROW_HEIGHT)
        remove_btn.clicked.connect(
            lambda _checked=False, i=index, r=rows, lay=rows_layout: self._remove_dynamic_row(
                r, i, lay
            )
        )
        layout.addWidget(remove_btn, 0)
        return row_widget

    def _style_row_field(self, widget: QWidget) -> None:
        if isinstance(widget, NullableDateEdit):
            widget.setMinimumWidth(140)
            widget.setMinimumHeight(_ROW_HEIGHT)
            widget.setMaximumHeight(_ROW_HEIGHT)
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        elif isinstance(widget, QLineEdit):
            widget.setMinimumHeight(_ROW_HEIGHT)
            widget.setMaximumHeight(_ROW_HEIGHT)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        elif isinstance(widget, ThpWorkerSelector):
            widget.setMinimumHeight(_ROW_HEIGHT)
            widget.setMaximumHeight(_ROW_HEIGHT)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            widget.setMinimumHeight(_ROW_HEIGHT)
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _oopp_row_widgets(self, row: dict) -> list:
        return [row["typ"], row["datum"], row["platnost"], row["poznamka"]]

    def _skoleni_row_widgets(self, row: dict) -> list:
        return [row["typ"], row["datum"], row["osnova"], row["poznamka"]]

    def _zkouska_row_widgets(self, row: dict) -> list:
        return [row["typ"], row["datum"], row["platnost"], row["poznamka"]]

    def _kontrola_row_widgets(self, row: dict) -> list:
        return [row["datum"], row["kontroloval"], row["vysledek"]]

    def _remove_dynamic_row(
        self,
        rows: list[dict],
        index: int,
        layout: QVBoxLayout,
    ) -> None:
        if len(rows) <= 1 or index < 0 or index >= len(rows):
            return
        rows.pop(index)
        self._rebuild_dynamic_rows(layout, rows)

    def add_dodrz_oopp_row(self) -> None:
        self.dodrz_oopp_rows.append(self._make_oopp_row())
        self._rebuild_dynamic_rows(self.dodrz_oopp_rows_layout, self.dodrz_oopp_rows)

    def add_dodrz_skoleni_row(self) -> None:
        self.dodrz_skoleni_rows.append(self._make_skoleni_row())
        self._rebuild_dynamic_rows(self.dodrz_skoleni_rows_layout, self.dodrz_skoleni_rows)

    def add_dodrz_zkouska_row(self) -> None:
        self.dodrz_zkousky_rows.append(self._make_zkouska_row())
        self._rebuild_dynamic_rows(self.dodrz_zkousky_rows_layout, self.dodrz_zkousky_rows)

    def add_dodrz_kontrola_predpisu_row(self) -> None:
        self.dodrz_kontrola_predpisu_rows.extend(self._make_kontrola_rows([{}]))
        self._rebuild_dynamic_rows(
            self.dodrz_kontrola_predpisu_rows_layout,
            self.dodrz_kontrola_predpisu_rows,
        )

    def add_dodrz_kontrola_oopp_row(self) -> None:
        self.dodrz_kontrola_oopp_rows.extend(self._make_kontrola_rows([{}]))
        self._rebuild_dynamic_rows(
            self.dodrz_kontrola_oopp_rows_layout,
            self.dodrz_kontrola_oopp_rows,
        )

    def _rebuild_dynamic_rows(self, layout: QVBoxLayout, rows: list[dict]) -> None:
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            nested = item.layout()
            if nested is not None:
                self._clear_layout(nested)

        meta = self._list_meta.get(layout) or {}
        stretches = meta.get("stretches") or self._stretches_for_layout(layout)
        widgets_fn = meta.get("widgets_fn") or self._widgets_fn_for_layout(layout)
        for index, row in enumerate(rows):
            layout.addWidget(
                self._make_row_widget(widgets_fn(row), stretches, rows, index, layout)
            )

    def _stretches_for_layout(self, layout) -> tuple[int, ...]:
        if layout is getattr(self, "dodrz_oopp_rows_layout", None):
            return _OOPP_STRETCHES
        if layout is getattr(self, "dodrz_skoleni_rows_layout", None):
            return _SKOLENI_STRETCHES
        if layout is getattr(self, "dodrz_zkousky_rows_layout", None):
            return _ZKOUSKY_STRETCHES
        return _KONTROLA_STRETCHES

    def _widgets_fn_for_layout(self, layout):
        if layout is getattr(self, "dodrz_skoleni_rows_layout", None):
            return self._skoleni_row_widgets
        if layout is getattr(self, "dodrz_zkousky_rows_layout", None):
            return self._zkouska_row_widgets
        if layout is getattr(self, "dodrz_oopp_rows_layout", None):
            return self._oopp_row_widgets
        return self._kontrola_row_widgets

    def _clear_layout(self, layout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
            nested = child.layout()
            if nested is not None:
                self._clear_layout(nested)

    def _make_kontrola_rows(self, saved_rows) -> list[dict]:
        rows = []
        for data in saved_rows or [{}]:
            data = data or {}
            row = {
                "datum": self._new_date_edit(),
                "kontroloval": self._new_thp_selector(data.get("kontroloval", "")),
                "vysledek": QLineEdit(data.get("vysledek", "")),
            }
            row["vysledek"].setPlaceholderText("Výsledek")
            if data.get("datum"):
                self._set_date_widget(row["datum"], data.get("datum"))
            rows.append(row)
        return rows

    def _make_oopp_row(self, data=None) -> dict:
        data = data or {}
        row = {
            "typ": QLineEdit(data.get("typ", "")),
            "datum": self._new_date_edit(),
            "platnost": QLineEdit(data.get("platnost", "")),
            "poznamka": QLineEdit(data.get("poznamka", "")),
        }
        row["typ"].setPlaceholderText("Název OOPP")
        row["platnost"].setPlaceholderText("Datum ukončení používání")
        row["poznamka"].setPlaceholderText("Poznámka")
        if data.get("datum"):
            self._set_date_widget(row["datum"], data.get("datum"))
        return row

    def _make_skoleni_row(self, data=None) -> dict:
        data = data or {}
        row = {
            "typ": QLineEdit(data.get("typ", "")),
            "datum": self._new_date_edit(),
            "osnova": self._radio_choice(["ANO", "NE"], compact=True),
            "poznamka": QLineEdit(data.get("poznamka", "")),
        }
        row["typ"].setPlaceholderText("Název školení")
        row["poznamka"].setPlaceholderText("Poznámka")
        row["osnova"].setToolTip("Úspěšně absolvováno")
        if data.get("datum"):
            self._set_date_widget(row["datum"], data.get("datum"))
        self._set_radio_choice(row["osnova"], data.get("osnova", ""))
        return row

    def _make_zkouska_row(self, data=None) -> dict:
        data = data or {}
        row = {
            "typ": QLineEdit(data.get("typ", "")),
            "datum": self._new_date_edit(),
            "platnost": self._new_date_edit(),
            "poznamka": QLineEdit(data.get("poznamka", "")),
        }
        row["typ"].setPlaceholderText("Název zkoušky / odborné způsobilosti")
        row["poznamka"].setPlaceholderText("Poznámka")
        if data.get("datum"):
            self._set_date_widget(row["datum"], data.get("datum"))
        if data.get("platnost"):
            self._set_date_widget(row["platnost"], data.get("platnost"))
        return row

    def _new_thp_selector(self, value: str = "") -> ThpWorkerSelector:
        selector = ThpWorkerSelector()
        selector.setEditable(True)
        if value:
            index = selector.findText(value)
            if index >= 0:
                selector.setCurrentIndex(index)
            else:
                selector.setEditText(value)
        return selector

    def _connect_prescasy_detail_visibility(self) -> None:
        def refresh() -> None:
            self.dodrz_prescasy_detail.setVisible(
                self._radio_choice_value(self.dodrz_prescasy) == "ANO"
            )

        for button in self.dodrz_prescasy.findChildren(QRadioButton):
            button.toggled.connect(refresh)
        refresh()

    def _configure_text_edit(self, widget: QTextEdit, *, lines: int) -> None:
        line_px = 22
        height = max(lines * line_px, 48)
        widget.setMinimumHeight(height)
        widget.setMaximumHeight(height + line_px * 4)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def _widget_text(self, widget) -> str:
        if hasattr(widget, "currentText"):
            return widget.currentText().strip()
        if hasattr(widget, "text"):
            return widget.text().strip()
        return ""

    def _new_date_edit(self, placeholder: str = "např. 05.06.1982") -> NullableDateEdit:
        widget = NullableDateEdit()
        if hasattr(widget, "setPlaceholderText"):
            widget.setPlaceholderText(placeholder)
        return widget

    def _radio_choice(self, labels: list[str], *, compact: bool = False) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for text in labels:
            layout.addWidget(QRadioButton(text))
        if not compact:
            layout.addStretch()
        else:
            layout.addStretch(0)
            box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
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

    def _date_value(self, widget):
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
            if hasattr(widget, "clear_date"):
                widget.clear_date()
            return
        if isinstance(value, str) and hasattr(widget, "set_date_iso"):
            widget.set_date_iso(value)
        elif hasattr(widget, "set_date_value"):
            widget.set_date_value(value)
