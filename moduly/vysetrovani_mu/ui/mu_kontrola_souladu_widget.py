import json

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_STANOVISKO_MU = "Jedná se o mimořádnou událost"
_STANOVISKO_NEMU = "Nejedná se o mimořádnou událost"
_STANOVISKO_NELZE = "Nelze zatím uzavřít"

_PODKLADY = (
    ("vypoved_postizeneho", "Výpověď dotčené osoby"),
    ("vypovedi_svedku", "Výpovědi svědků"),
    ("fotodokumentace", "Fotodokumentace"),
    ("stav_mista", "Stav místa"),
    ("kamerove_zaznamy", "Kamerové záznamy"),
    ("casove_udaje", "Časové údaje"),
    ("lekarska_zprava", "Lékařská zpráva"),
    ("pracovni_postup", "Pracovní postup"),
    ("oopp", "OOPP"),
    ("skoleni", "Školení"),
    ("evidence_prace", "Evidence práce / docházka"),
)

_NESROVNALOSTI = (
    ("cas", "V čase události"),
    ("misto", "V místě události"),
    ("mechanismus", "V mechanismu události"),
    ("vypovedi", "Ve výpovědích"),
    ("zraneni_popis", "Mezi zraněním a popisem události"),
    ("jine", "Jiné"),
)


class MuKontrolaSouladuWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._saved_data: dict = {}
        self.soulad_podklady: dict[str, QCheckBox] = {}
        self.soulad_nesrovnalosti: dict[str, QCheckBox] = {}

        self._init_widgets()
        self._build_ui()

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
            "soulad_podklady": {key: cb.isChecked() for key, cb in self.soulad_podklady.items()},
            "soulad_nesrovnalosti": {key: cb.isChecked() for key, cb in self.soulad_nesrovnalosti.items()},
            "soulad_popis_nesrovnalosti": self.soulad_popis_nesrovnalosti.toPlainText().strip(),
            "soulad_vyhodnoceni": self.soulad_vyhodnoceni.toPlainText().strip(),
            "soulad_vzniklo_poskozeni": self._radio_choice_value(self.soulad_vzniklo_poskozeni),
            "soulad_pri_plneni": self._radio_choice_value(self.soulad_pri_plneni),
            "soulad_nahle_pusobeni": self._radio_choice_value(self.soulad_nahle_pusobeni),
            "soulad_mimo_praci": self._radio_choice_value(self.soulad_mimo_praci),
            "soulad_stanovisko_bozp": self.soulad_stanovisko_bozp.currentText().strip(),
            "soulad_oduvodneni": self.soulad_oduvodneni.toPlainText().strip(),
        }

    def _init_widgets(self) -> None:
        saved = self._saved_data

        self.soulad_podklady = {}
        for key, label in _PODKLADY:
            cb = QCheckBox(label)
            podklady_saved = saved.get("soulad_podklady", {}) or {}
            cb.setChecked(bool(podklady_saved.get(key, saved.get(f"soulad_podklad_{key}", False))))
            self.soulad_podklady[key] = cb

        self.soulad_nesrovnalosti = {}
        for key, label in _NESROVNALOSTI:
            cb = QCheckBox(label)
            nesrovnalosti_saved = saved.get("soulad_nesrovnalosti", {}) or {}
            cb.setChecked(bool(nesrovnalosti_saved.get(key, saved.get(f"soulad_nesrovnalost_{key}", False))))
            self.soulad_nesrovnalosti[key] = cb

        self.soulad_popis_nesrovnalosti = QTextEdit()
        self.soulad_popis_nesrovnalosti.setPlainText(saved.get("soulad_popis_nesrovnalosti", ""))
        self.soulad_vyhodnoceni = QTextEdit()
        self.soulad_vyhodnoceni.setPlainText(saved.get("soulad_vyhodnoceni", ""))

        self.soulad_vzniklo_poskozeni = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.soulad_vzniklo_poskozeni, saved.get("soulad_vzniklo_poskozeni", ""))
        self.soulad_pri_plneni = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.soulad_pri_plneni, saved.get("soulad_pri_plneni", ""))
        self.soulad_nahle_pusobeni = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.soulad_nahle_pusobeni, saved.get("soulad_nahle_pusobeni", ""))
        self.soulad_mimo_praci = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.soulad_mimo_praci, saved.get("soulad_mimo_praci", ""))

        self.soulad_stanovisko_bozp = QComboBox()
        self.soulad_stanovisko_bozp.addItems([_STANOVISKO_MU, _STANOVISKO_NEMU, _STANOVISKO_NELZE])
        self.soulad_stanovisko_bozp.setCurrentText(
            self._normalize_stanovisko(saved.get("soulad_stanovisko_bozp", _STANOVISKO_NELZE))
        )

        self.soulad_oduvodneni = QTextEdit()
        self.soulad_oduvodneni.setPlainText(saved.get("soulad_oduvodneni", ""))

    def _apply_saved_data(self) -> None:
        saved = self._saved_data
        podklady_saved = saved.get("soulad_podklady", {}) or {}
        for key, cb in self.soulad_podklady.items():
            cb.setChecked(bool(podklady_saved.get(key, saved.get(f"soulad_podklad_{key}", False))))

        nesrovnalosti_saved = saved.get("soulad_nesrovnalosti", {}) or {}
        for key, cb in self.soulad_nesrovnalosti.items():
            cb.setChecked(bool(nesrovnalosti_saved.get(key, saved.get(f"soulad_nesrovnalost_{key}", False))))

        self.soulad_popis_nesrovnalosti.setPlainText(saved.get("soulad_popis_nesrovnalosti", ""))
        self.soulad_vyhodnoceni.setPlainText(saved.get("soulad_vyhodnoceni", ""))

        self._set_radio_choice(self.soulad_vzniklo_poskozeni, saved.get("soulad_vzniklo_poskozeni", ""))
        self._set_radio_choice(self.soulad_pri_plneni, saved.get("soulad_pri_plneni", ""))
        self._set_radio_choice(self.soulad_nahle_pusobeni, saved.get("soulad_nahle_pusobeni", ""))
        self._set_radio_choice(self.soulad_mimo_praci, saved.get("soulad_mimo_praci", ""))

        self.soulad_stanovisko_bozp.setCurrentText(
            self._normalize_stanovisko(saved.get("soulad_stanovisko_bozp", _STANOVISKO_NELZE))
        )
        self._refresh_stanovisko_bozp()

        self.soulad_oduvodneni.setPlainText(saved.get("soulad_oduvodneni", ""))

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        layout.addWidget(QLabel("<b>Kontrola souladu důkazů a posouzení mimořádné události</b>"))
        layout.addWidget(QLabel("Kontrola souladu důkazů"))

        podklady = QGroupBox("Porovnané podklady")
        pf = QVBoxLayout(podklady)
        for key, _label in _PODKLADY:
            pf.addWidget(self.soulad_podklady[key])
        layout.addWidget(podklady)

        nesrovnalosti = QGroupBox("Zjištěné nesrovnalosti")
        nf = QVBoxLayout(nesrovnalosti)
        for key, _label in _NESROVNALOSTI:
            nf.addWidget(self.soulad_nesrovnalosti[key])
        layout.addWidget(nesrovnalosti)

        popis = QGroupBox("Popis zjištěných nesrovnalostí")
        popis_f = QFormLayout(popis)
        self._add_textedit_row(popis_f, "", self.soulad_popis_nesrovnalosti, 180)
        layout.addWidget(popis)

        vyhodnoceni = QGroupBox("Vyhodnocení souladu důkazů")
        vyhodnoceni_f = QFormLayout(vyhodnoceni)
        self._add_textedit_row(vyhodnoceni_f, "", self.soulad_vyhodnoceni, 180)
        layout.addWidget(vyhodnoceni)

        posouzeni = QGroupBox("Posouzení mimořádné události")
        form = QFormLayout(posouzeni)
        form.addRow("Vzniklo poškození zdraví:", self.soulad_vzniklo_poskozeni)
        form.addRow("Došlo k němu při plnění pracovních úkolů nebo v přímé souvislosti:", self.soulad_pri_plneni)
        form.addRow("Šlo o náhlé, krátkodobé a zevní působení:", self.soulad_nahle_pusobeni)
        form.addRow("Jedná se o událost mimo práci nebo cestu do/z práce:", self.soulad_mimo_praci)
        form.addRow("Stanovisko specialisty BOZP:", self.soulad_stanovisko_bozp)
        self._add_textedit_row(form, "Odůvodnění stanoviska:", self.soulad_oduvodneni, 180)
        layout.addWidget(posouzeni)

        self._connect_stanovisko_bozp_refresh()

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _connect_stanovisko_bozp_refresh(self) -> None:
        for skupina in (
            self.soulad_vzniklo_poskozeni,
            self.soulad_pri_plneni,
            self.soulad_nahle_pusobeni,
            self.soulad_mimo_praci,
        ):
            for button in skupina.findChildren(QRadioButton):
                button.toggled.connect(self._refresh_stanovisko_bozp)
        self._refresh_stanovisko_bozp()

    def _refresh_stanovisko_bozp(self) -> None:
        hodnoty = [
            self._radio_choice_value(self.soulad_vzniklo_poskozeni),
            self._radio_choice_value(self.soulad_pri_plneni),
            self._radio_choice_value(self.soulad_nahle_pusobeni),
            self._radio_choice_value(self.soulad_mimo_praci),
        ]
        if any(not hodnota for hodnota in hodnoty):
            self.soulad_stanovisko_bozp.setCurrentText(_STANOVISKO_NELZE)
        elif hodnoty == ["ANO", "ANO", "ANO", "NE"]:
            self.soulad_stanovisko_bozp.setCurrentText(_STANOVISKO_MU)
        else:
            self.soulad_stanovisko_bozp.setCurrentText(_STANOVISKO_NEMU)

    def _normalize_stanovisko(self, value: str) -> str:
        value = (value or "").strip()
        legacy_map = {
            "Jedná se o pracovní úraz": _STANOVISKO_MU,
            "Nejedná se o pracovní úraz": _STANOVISKO_NEMU,
        }
        if value in legacy_map:
            return legacy_map[value]
        if value in (_STANOVISKO_MU, _STANOVISKO_NEMU, _STANOVISKO_NELZE):
            return value
        return _STANOVISKO_NELZE

    def _add_textedit_row(self, form, label, widget, height=160) -> None:
        widget.setMinimumHeight(height)
        form.addRow(label, widget)

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
