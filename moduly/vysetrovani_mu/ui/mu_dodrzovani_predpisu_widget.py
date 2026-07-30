import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.services.attachment_service import attachment_service
from core.shared.constants import ENTITY_MU_INVESTIGATION
from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector

# MU-UX-5 – jednotné popisky a šířky sloupců opakovaných seznamů.
_OOPP_HEADERS = (
    "Název OOPP",
    "Datum vydání",
    "Datum ukončení používání",
    "Poznámka",
)
_OOPP_STRETCHES = (3, 2, 2, 3)

_SKOLENI_HEADERS = (
    "Název školení",
    "Datum školení",
    "Úspěšně absolvováno",
    "Poznámka",
)
_SKOLENI_STRETCHES = (3, 2, 2, 3)

_ZKOUSKY_HEADERS = (
    "Název zkoušky / odborné způsobilosti",
    "Platnost od",
    "Platnost do",
    "Poznámka",
)
_ZKOUSKY_STRETCHES = (3, 2, 2, 3)

_KONTROLA_HEADERS = (
    "Datum",
    "Kontroloval",
    "Výsledek",
)
_KONTROLA_STRETCHES = (2, 3, 3)


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

    def _init_widgets(self) -> None:
        saved = self._saved_data

        self.dodrz_pracovni_doba = self._radio_choice(["Dle grafu", "Mimo graf"])
        self._set_radio_choice(self.dodrz_pracovni_doba, saved.get("dodrz_pracovni_doba", ""))
        self.dodrz_prescasy = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.dodrz_prescasy, saved.get("dodrz_prescasy", ""))
        self.dodrz_prescasy_detail = QTextEdit()
        self.dodrz_prescasy_detail.setPlainText(saved.get("dodrz_prescasy_detail", ""))
        self.dodrz_prescasy_detail.setMinimumHeight(90)

        self.dodrz_predpisy_cinnost = QTextEdit()
        self.dodrz_predpisy_cinnost.setPlainText(saved.get("dodrz_predpisy_cinnost", ""))

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
        self.dodrz_kontroly_reviz_zavady = QTextEdit()
        self.dodrz_kontroly_reviz_zavady.setPlainText(saved.get("dodrz_kontroly_reviz_zavady", ""))

        self.dodrz_zkousky_rows = []
        for data in saved.get("dodrz_zkousky_rows") or [{}]:
            self.dodrz_zkousky_rows.append(self._make_zkouska_row(data))

        self.dodrz_ostatni_1 = QTextEdit()
        self.dodrz_ostatni_1.setPlainText(saved.get("dodrz_ostatni_1", ""))
        self.dodrz_oopp_pouzity = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.dodrz_oopp_pouzity, saved.get("dodrz_oopp_pouzity", ""))
        self.dodrz_stav_oopp = QTextEdit()
        self.dodrz_stav_oopp.setPlainText(saved.get("dodrz_stav_oopp", ""))
        self.dodrz_vyjadreni_oopp = QTextEdit()
        self.dodrz_vyjadreni_oopp.setPlainText(saved.get("dodrz_vyjadreni_oopp", ""))

        self.dodrz_kontrola_oopp_rows = self._make_kontrola_rows(saved.get("dodrz_kontrola_oopp_rows"))
        self.dodrz_kontrola_predpisu_rows = self._make_kontrola_rows(saved.get("dodrz_kontrola_predpisu_rows"))

        self.dodrz_poruseni_predpisu = QTextEdit()
        self.dodrz_poruseni_predpisu.setPlainText(saved.get("dodrz_poruseni_predpisu", ""))
        self.dodrz_ostatni_2 = QTextEdit()
        self.dodrz_ostatni_2.setPlainText(saved.get("dodrz_ostatni_2", ""))

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
        self._rebuild_dynamic_rows(self.dodrz_oopp_layout, self.dodrz_oopp_rows)

        self.dodrz_skoleni_rows = []
        for data in saved.get("dodrz_skoleni_rows") or [{}]:
            self.dodrz_skoleni_rows.append(self._make_skoleni_row(data))
        self._rebuild_dynamic_rows(self.dodrz_skoleni_layout, self.dodrz_skoleni_rows)

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
        self._rebuild_dynamic_rows(self.dodrz_zkousky_layout, self.dodrz_zkousky_rows)

        self.dodrz_ostatni_1.setPlainText(saved.get("dodrz_ostatni_1", ""))
        self._set_radio_choice(self.dodrz_oopp_pouzity, saved.get("dodrz_oopp_pouzity", ""))
        self.dodrz_stav_oopp.setPlainText(saved.get("dodrz_stav_oopp", ""))
        self.dodrz_vyjadreni_oopp.setPlainText(saved.get("dodrz_vyjadreni_oopp", ""))

        self.dodrz_kontrola_oopp_rows = self._make_kontrola_rows(saved.get("dodrz_kontrola_oopp_rows"))
        self._rebuild_kontrola_rows(self.dodrz_kontrola_oopp_layout, self.dodrz_kontrola_oopp_rows)

        self.dodrz_kontrola_predpisu_rows = self._make_kontrola_rows(saved.get("dodrz_kontrola_predpisu_rows"))
        self._rebuild_kontrola_rows(self.dodrz_kontrola_predpisu_layout, self.dodrz_kontrola_predpisu_rows)

        self.dodrz_poruseni_predpisu.setPlainText(saved.get("dodrz_poruseni_predpisu", ""))
        self.dodrz_ostatni_2.setPlainText(saved.get("dodrz_ostatni_2", ""))

    def _build_ui(self) -> None:
        """MU-UX-6 – čtyři logické bloky podle postupu vyšetřovatele."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 24)
        layout.setSpacing(28)

        layout.addWidget(self._build_block_predpisy_a_kontroly())
        layout.addWidget(self._build_block_odborna_zpusobilost())
        layout.addWidget(self._build_block_oopp())
        layout.addWidget(self._build_block_dalsi_skutecnosti())

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _build_block_predpisy_a_kontroly(self) -> QWidget:
        block, body = self._make_section_block("Předpisy a kontroly")

        pracovni = self._make_subsection("Pracovní doba")
        form = QFormLayout(pracovni)
        form.setSpacing(10)
        form.setContentsMargins(0, 8, 0, 0)
        form.addRow("Dodržování pracovní doby:", self.dodrz_pracovni_doba)
        form.addRow("Přesčasy:", self.dodrz_prescasy)
        form.addRow("Detail přesčasové práce:", self.dodrz_prescasy_detail)
        self._connect_prescasy_detail_visibility()
        body.addWidget(pracovni)

        predpisy = self._make_subsection(
            "Předpisy pro činnost, při které došlo k mimořádné události"
        )
        pf = QVBoxLayout(predpisy)
        pf.setContentsMargins(0, 8, 0, 0)
        self.dodrz_predpisy_cinnost.setMinimumHeight(120)
        self.dodrz_predpisy_cinnost.setPlaceholderText(
            "Jaké předpisy platily pro činnost při události…"
        )
        pf.addWidget(self.dodrz_predpisy_cinnost)
        body.addWidget(predpisy)

        kpred = self._make_subsection("Kontrola dodržování předpisů a pracovních postupů")
        kpf = QVBoxLayout(kpred)
        kpf.setContentsMargins(0, 8, 0, 0)
        kpf.setSpacing(8)
        self.dodrz_kontrola_predpisu_layout = kpf
        kpf.addLayout(
            self._column_header_row(_KONTROLA_HEADERS, _KONTROLA_STRETCHES, with_remove=False)
        )
        for row in self.dodrz_kontrola_predpisu_rows:
            kpf.addLayout(
                self._row_widgets_layout(
                    [row["datum"], row["kontroloval"], row["vysledek"]],
                    _KONTROLA_STRETCHES,
                )
            )
        body.addWidget(kpred)

        kontroly = self._make_subsection(
            "Kontroly a revize zařízení / zjevné závady na pracovišti"
        )
        krf = QVBoxLayout(kontroly)
        krf.setContentsMargins(0, 8, 0, 0)
        self.dodrz_kontroly_reviz_zavady.setMinimumHeight(100)
        self.dodrz_kontroly_reviz_zavady.setPlaceholderText(
            "Závěry kontrol a revizí, zjevné závady…"
        )
        krf.addWidget(self.dodrz_kontroly_reviz_zavady)
        body.addWidget(kontroly)

        poruseni = self._make_subsection("Porušení předpisů")
        prf = QVBoxLayout(poruseni)
        prf.setContentsMargins(0, 8, 0, 0)
        self.dodrz_poruseni_predpisu.setMinimumHeight(100)
        self.dodrz_poruseni_predpisu.setPlaceholderText(
            "Zjištěná porušení předpisů…"
        )
        prf.addWidget(self.dodrz_poruseni_predpisu)
        body.addWidget(poruseni)

        return block

    def _build_block_odborna_zpusobilost(self) -> QWidget:
        block, body = self._make_section_block("Odborná způsobilost")

        skoleni = self._make_subsection(
            "Školení související s mimořádnou událostí a školení o BOZP"
        )
        sf = QVBoxLayout(skoleni)
        sf.setContentsMargins(0, 8, 0, 0)
        sf.setSpacing(8)
        self.dodrz_skoleni_layout = sf
        self._populate_dynamic_list(
            sf,
            self.dodrz_skoleni_rows,
            _SKOLENI_HEADERS,
            _SKOLENI_STRETCHES,
            self._skoleni_row_widgets,
            "Přidat školení",
            self.add_dodrz_skoleni_row,
        )
        body.addWidget(skoleni)

        zkousky = self._make_subsection("Zkoušky z předpisů a odborná způsobilost")
        zf = QVBoxLayout(zkousky)
        zf.setContentsMargins(0, 8, 0, 0)
        zf.setSpacing(8)
        self.dodrz_zkousky_layout = zf
        self._populate_dynamic_list(
            zf,
            self.dodrz_zkousky_rows,
            _ZKOUSKY_HEADERS,
            _ZKOUSKY_STRETCHES,
            self._zkouska_row_widgets,
            "Přidat zkoušku",
            self.add_dodrz_zkouska_row,
        )
        body.addWidget(zkousky)

        lekar = self._make_subsection("Lékařská prohlídka")
        lf = QFormLayout(lekar)
        lf.setContentsMargins(0, 8, 0, 0)
        lf.setSpacing(10)
        lf.addRow("Typ prohlídky:", self.dodrz_lekar_typ)
        lf.addRow("Datum prohlídky:", self.dodrz_lekar_datum)
        lf.addRow("Platnost do:", self.dodrz_lekar_platnost)
        body.addWidget(lekar)

        kval = self._make_subsection("Kvalifikace k pracovní činnosti")
        kf = QFormLayout(kval)
        kf.setContentsMargins(0, 8, 0, 0)
        kf.setSpacing(10)
        kf.addRow("Splňuje kvalifikaci:", self.dodrz_kvalifikace_splnuje)
        self.dodrz_kvalifikace_poznamka.setMinimumHeight(90)
        kf.addRow("Poznámka:", self.dodrz_kvalifikace_poznamka)
        body.addWidget(kval)

        return block

    def _build_block_oopp(self) -> QWidget:
        block, body = self._make_section_block("Osobní ochranné pracovní prostředky")

        oopp = self._make_subsection("Přidělené OOPP")
        of = QVBoxLayout(oopp)
        of.setContentsMargins(0, 8, 0, 0)
        of.setSpacing(8)
        self.dodrz_oopp_layout = of
        self._populate_dynamic_list(
            of,
            self.dodrz_oopp_rows,
            _OOPP_HEADERS,
            _OOPP_STRETCHES,
            self._oopp_row_widgets,
            "Přidat OOPP",
            self.add_dodrz_oopp_row,
        )
        body.addWidget(oopp)

        pouzivani = self._make_subsection("Používání OOPP při události")
        puf = QFormLayout(pouzivani)
        puf.setContentsMargins(0, 8, 0, 0)
        puf.setSpacing(10)
        puf.addRow("OOPP byly použity:", self.dodrz_oopp_pouzity)
        body.addWidget(pouzivani)

        # MU-UX-6 bod 7 – vyjádření bezprostředně pod používáním OOPP.
        vyj = self._make_subsection("Vyjádření zaměstnance k používání OOPP")
        vyf = QVBoxLayout(vyj)
        vyf.setContentsMargins(0, 8, 0, 0)
        vyf.setSpacing(6)
        vyf.addWidget(QLabel("Vyjádření / stanovisko:"))
        self.dodrz_vyjadreni_oopp.setMinimumHeight(100)
        self.dodrz_vyjadreni_oopp.setPlaceholderText(
            "Co k používání OOPP uvedl zaměstnanec…"
        )
        vyf.addWidget(self.dodrz_vyjadreni_oopp)
        body.addWidget(vyj)

        stav = self._make_subsection("Stav OOPP")
        stf = QVBoxLayout(stav)
        stf.setContentsMargins(0, 8, 0, 0)
        self.dodrz_stav_oopp.setMinimumHeight(90)
        self.dodrz_stav_oopp.setPlaceholderText("Stav OOPP v době události…")
        stf.addWidget(self.dodrz_stav_oopp)
        body.addWidget(stav)

        koopp = self._make_subsection("Kontrola používání OOPP dle ZP")
        kof = QVBoxLayout(koopp)
        kof.setContentsMargins(0, 8, 0, 0)
        kof.setSpacing(8)
        self.dodrz_kontrola_oopp_layout = kof
        kof.addLayout(
            self._column_header_row(_KONTROLA_HEADERS, _KONTROLA_STRETCHES, with_remove=False)
        )
        for row in self.dodrz_kontrola_oopp_rows:
            kof.addLayout(
                self._row_widgets_layout(
                    [row["datum"], row["kontroloval"], row["vysledek"]],
                    _KONTROLA_STRETCHES,
                )
            )
        body.addWidget(koopp)

        return block

    def _build_block_dalsi_skutecnosti(self) -> QWidget:
        block, body = self._make_section_block("Další skutečnosti")

        ostatni = self._make_subsection("Ostatní záznamy")
        of = QVBoxLayout(ostatni)
        of.setContentsMargins(0, 8, 0, 0)
        of.setSpacing(12)
        of.addWidget(QLabel("Záznamy k předpisům a kontrolám:"))
        self.dodrz_ostatni_1.setMinimumHeight(90)
        of.addWidget(self.dodrz_ostatni_1)
        of.addWidget(QLabel("Záznamy k dotčené osobě a OOPP:"))
        self.dodrz_ostatni_2.setMinimumHeight(90)
        of.addWidget(self.dodrz_ostatni_2)
        body.addWidget(ostatni)

        prilohy = self._make_subsection("Přílohy k dodržování předpisů")
        pl = QVBoxLayout(prilohy)
        pl.setContentsMargins(0, 8, 0, 0)
        pl.setSpacing(8)
        hint = QLabel(
            "Zde přiložte sken nebo dokument vztahující se k této části šetření. "
            "Přílohy lze přidat až po uložení vyšetřování."
        )
        hint.setWordWrap(True)
        pl.addWidget(hint)
        self.dodrzovani_attachment_widget = MuDodrzovaniAttachmentWidget()
        pl.addWidget(self.dodrzovani_attachment_widget)
        body.addWidget(prilohy)

        return block

    def _make_section_block(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        block = QFrame()
        block.setObjectName("muDodrzSection")
        block.setFrameShape(QFrame.Shape.NoFrame)
        outer = QVBoxLayout(block)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("muDodrzSectionTitle")
        font = title_label.font()
        font.setBold(True)
        font.setPointSize(max(font.pointSize() + 3, 13))
        title_label.setFont(font)
        outer.addWidget(title_label)

        body = QVBoxLayout()
        body.setContentsMargins(4, 0, 0, 0)
        body.setSpacing(18)
        outer.addLayout(body)
        return block, body

    def _make_subsection(self, title: str) -> QWidget:
        box = QGroupBox(title)
        box.setFlat(True)
        box.setAlignment(Qt.AlignmentFlag.AlignLeft)
        return box

    def _populate_dynamic_list(
        self,
        layout: QVBoxLayout,
        rows: list[dict],
        headers: tuple[str, ...],
        stretches: tuple[int, ...],
        widgets_fn,
        add_label: str,
        add_slot,
    ) -> None:
        layout.addLayout(self._column_header_row(headers, stretches, with_remove=True))
        for index, row in enumerate(rows):
            layout.addLayout(
                self._dynamic_row_layout(widgets_fn(row), stretches, rows, index, layout)
            )
        btn = QPushButton(add_label)
        btn.clicked.connect(add_slot)
        layout.addWidget(btn)

    def _oopp_row_widgets(self, row: dict) -> list:
        return [row["typ"], row["datum"], row["platnost"], row["poznamka"]]

    def _skoleni_row_widgets(self, row: dict) -> list:
        return [row["typ"], row["datum"], row["osnova"], row["poznamka"]]

    def _zkouska_row_widgets(self, row: dict) -> list:
        return [row["typ"], row["datum"], row["platnost"], row["poznamka"]]

    def _dynamic_row_layout(
        self,
        widgets: list,
        stretches: tuple[int, ...],
        rows: list[dict],
        index: int,
        parent_layout: QVBoxLayout,
    ) -> QHBoxLayout:
        row_layout = self._row_widgets_layout(widgets, stretches)
        remove_btn = QPushButton("Odebrat")
        remove_btn.setFixedWidth(90)
        remove_btn.clicked.connect(
            lambda _checked=False, i=index, r=rows, lay=parent_layout: self._remove_dynamic_row(
                r, i, lay
            )
        )
        row_layout.addWidget(remove_btn, 0)
        return row_layout

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
        row = self._make_oopp_row()
        self.dodrz_oopp_rows.append(row)
        self._rebuild_dynamic_rows(self.dodrz_oopp_layout, self.dodrz_oopp_rows)

    def add_dodrz_skoleni_row(self) -> None:
        row = self._make_skoleni_row()
        self.dodrz_skoleni_rows.append(row)
        self._rebuild_dynamic_rows(self.dodrz_skoleni_layout, self.dodrz_skoleni_rows)

    def add_dodrz_zkouska_row(self) -> None:
        row = self._make_zkouska_row()
        self.dodrz_zkousky_rows.append(row)
        self._rebuild_dynamic_rows(self.dodrz_zkousky_layout, self.dodrz_zkousky_rows)

    def _make_kontrola_rows(self, saved_rows) -> list[dict]:
        rows = []
        for data in saved_rows or [{}]:
            data = data or {}
            row = {
                "datum": self._new_date_edit(),
                "kontroloval": self._new_thp_selector(data.get("kontroloval", "")),
                "vysledek": QLineEdit(data.get("vysledek", "")),
            }
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
            "osnova": self._radio_choice(["ANO", "NE"]),
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
            self.dodrz_prescasy_detail.setVisible(self._radio_choice_value(self.dodrz_prescasy) == "ANO")

        for button in self.dodrz_prescasy.findChildren(QRadioButton):
            button.toggled.connect(refresh)
        refresh()

    def _rebuild_dynamic_rows(self, layout, rows: list[dict]) -> None:
        if layout is None:
            return
        # Zachovat hlavičku (index 0) a tlačítko Přidat (poslední).
        while layout.count() > 2:
            item = layout.takeAt(1)
            if item.layout() is not None:
                self._clear_layout(item.layout())
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        stretches = self._stretches_for_layout(layout)
        widgets_fn = self._widgets_fn_for_layout(layout)
        for index, row in enumerate(rows):
            layout.insertLayout(
                layout.count() - 1,
                self._dynamic_row_layout(
                    widgets_fn(row),
                    stretches,
                    rows,
                    index,
                    layout,
                ),
            )

    def _rebuild_kontrola_rows(self, layout, rows: list[dict]) -> None:
        if layout is None:
            return
        while layout.count() > 1:
            item = layout.takeAt(1)
            if item.layout() is not None:
                self._clear_layout(item.layout())
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for row in rows:
            layout.addLayout(
                self._row_widgets_layout(
                    [row["datum"], row["kontroloval"], row["vysledek"]],
                    _KONTROLA_STRETCHES,
                )
            )

    def _stretches_for_layout(self, layout) -> tuple[int, ...]:
        if layout is getattr(self, "dodrz_oopp_layout", None):
            return _OOPP_STRETCHES
        if layout is getattr(self, "dodrz_skoleni_layout", None):
            return _SKOLENI_STRETCHES
        if layout is getattr(self, "dodrz_zkousky_layout", None):
            return _ZKOUSKY_STRETCHES
        return _OOPP_STRETCHES

    def _widgets_fn_for_layout(self, layout):
        if layout is getattr(self, "dodrz_skoleni_layout", None):
            return self._skoleni_row_widgets
        if layout is getattr(self, "dodrz_zkousky_layout", None):
            return self._zkouska_row_widgets
        return self._oopp_row_widgets

    def _row_widgets_for_row(self, row: dict) -> list:
        if "osnova" in row:
            return self._skoleni_row_widgets(row)
        if isinstance(row.get("platnost"), NullableDateEdit):
            return self._zkouska_row_widgets(row)
        return self._oopp_row_widgets(row)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
            nested = child.layout()
            if nested is not None:
                self._clear_layout(nested)

    def _column_header_row(
        self,
        headers: tuple[str, ...],
        stretches: tuple[int, ...],
        *,
        with_remove: bool = True,
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 4)
        row.setSpacing(8)
        for text, stretch in zip(headers, stretches, strict=True):
            label = QLabel(text)
            label.setWordWrap(True)
            font = label.font()
            font.setBold(True)
            label.setFont(font)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            row.addWidget(label, stretch)
        if with_remove:
            spacer = QLabel("")
            spacer.setFixedWidth(90)
            row.addWidget(spacer, 0)
        return row

    def _row_widgets_layout(
        self,
        widgets,
        stretches: tuple[int, ...] | None = None,
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        weights = stretches or tuple(1 for _ in widgets)
        for widget, stretch in zip(widgets, weights, strict=True):
            if isinstance(widget, NullableDateEdit):
                widget.setMinimumWidth(150)
                widget.setMinimumHeight(34)
                widget.setSizePolicy(
                    QSizePolicy.Policy.Preferred,
                    QSizePolicy.Policy.Fixed,
                )
            elif isinstance(widget, QLineEdit):
                widget.setMinimumHeight(34)
                widget.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed,
                )
            row.addWidget(widget, stretch)
        return row

    def _add_textedit_row(self, form, label, widget, height=160) -> None:
        widget.setMinimumHeight(height)
        form.addRow(label, widget)

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
