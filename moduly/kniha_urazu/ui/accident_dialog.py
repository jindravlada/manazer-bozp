from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box, configure_resizable_form_dialog, wrap_in_scroll_area

from core.widgets.date_edit import DateEdit
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.kniha_urazu.ui.tabs.tab_dalsi import TabDalsiUdaje
from moduly.kniha_urazu.ui.tabs.tab_pracoviste import TabPracoviste
from moduly.kniha_urazu.ui.tabs.tab_svedci import TabSvedci
from moduly.kniha_urazu.ui.tabs.tab_uraz import TabUraz
from moduly.kniha_urazu.ui.tabs.tab_zamestnanec import TabZamestnanec
from moduly.kniha_urazu.ui.tabs.tab_zapisovatel_zamestnavatel import TabZapisovatelZamestnavatel


class AccidentDialog(QDialog):
    def __init__(self, parent=None, accident=None):
        super().__init__(parent)

        self.accident = accident
        self.setWindowTitle("Pracovní úraz")
        configure_resizable_form_dialog(self, width=860, height=680, min_width=640, min_height=480)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tab_podatel_widget = TabZapisovatelZamestnavatel()
        self.tab_zamestnanec_widget = TabZamestnanec()
        self.tab_uraz_widget = TabUraz()
        self.tab_pracoviste_widget = TabPracoviste()
        self.tab_dalsi_widget = TabDalsiUdaje()
        self.tab_svedci_widget = TabSvedci()

        self.tabs.addTab(wrap_in_scroll_area(self.tab_podatel_widget), "Zapisovatel / zaměstnavatel")
        self.tabs.addTab(wrap_in_scroll_area(self.tab_zamestnanec_widget), "Zaměstnanec")
        self.tabs.addTab(wrap_in_scroll_area(self.tab_uraz_widget), "Údaje o úrazu")
        self.tabs.addTab(wrap_in_scroll_area(self.tab_pracoviste_widget), "Pracoviště")
        self.tabs.addTab(wrap_in_scroll_area(self.tab_dalsi_widget), "Další údaje")
        self.tabs.addTab(wrap_in_scroll_area(self.tab_svedci_widget), "Svědci / podpisy")

        layout.addWidget(self.tabs, 1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._connect_logic()

        if accident is not None:
            self._load(accident)

        self._refresh_logic()

    def accept(self):
        validations = [
            ("Zapisovatel / zaměstnavatel", self.tab_podatel_widget),
            ("Zaměstnanec", self.tab_zamestnanec_widget),
        ]

        if hasattr(self, "tab_uraz_widget"):
            validations.append(("Údaje o úrazu", self.tab_uraz_widget))

        if hasattr(self, "tab_pracoviste_widget"):
            validations.append(("Pracoviště", self.tab_pracoviste_widget))

        if hasattr(self, "tab_dalsi_widget"):
            validations.append(("Další údaje", self.tab_dalsi_widget))

        if hasattr(self, "tab_svedci_widget"):
            validations.append(("Svědci / podpisy", self.tab_svedci_widget))

        for tab_name, widget in validations:
            if not hasattr(widget, "validate"):
                continue

            errors = widget.validate()

            if errors:
                self.tabs.setCurrentWidget(widget)

                if hasattr(widget, "focus_first_error"):
                    widget.focus_first_error()

                msg = (
                    f"Nejsou vyplněny všechny povinné údaje na záložce {tab_name}:\n\n"
                    + "\n".join(f"• {item}" for item in errors)
                )

                QMessageBox.warning(
                    self,
                    "Nelze uložit pracovní úraz",
                    msg,
                )
                return

        super().accept()

    def exec(self):
        self.showMaximized()
        return super().exec()

    def _line(self):
        return QLineEdit()

    def _text(self, height=90):
        widget = QTextEdit()
        widget.setFixedHeight(height)
        return widget

    def _combo(self, values):
        widget = QComboBox()
        widget.setEditable(True)
        widget.addItems(values)
        return widget

    def _tab_uraz(self):
        tab = QWidget()
        form = QFormLayout(tab)

        self.druh_urazu = self._combo(["", "Smrtelný", "Závažný", "Ostatní", "Bez pracovní neschopnosti"])
        self.podezreni_trestny_cin = self._combo(["", "ANO", "NE"])
        self.accident_date = DateEdit()
        self.accident_time = self._line()
        self.accident_time.setPlaceholderText("HH:MM")
        self.druh_zraneni = self._text(70)
        self.zranena_cast_tela = self._text(70)
        self.hromadny_uraz = self._combo(["", "ANO", "NE"])
        self.celkovy_pocet_zranenych = QSpinBox()
        self.celkovy_pocet_zranenych.setMinimum(1)
        self.celkovy_pocet_zranenych.setMaximum(999)
        self.cinnost_pri_urazu = self._line()
        self.misto_urazu = self._text(70)
        self.popis_urazoveho_deje = self._text(140)
        self.druh_a_rozsah_zraneni = self._text(70)

        for label, widget in [
            ("Druh úrazu:", self.druh_urazu),
            ("Podezření na trestný čin:", self.podezreni_trestny_cin),
            ("Datum úrazu:", self.accident_date),
            ("Čas úrazu:", self.accident_time),
            ("Druh zranění:", self.druh_zraneni),
            ("Zraněná část těla:", self.zranena_cast_tela),
            ("Hromadný úraz:", self.hromadny_uraz),
            ("Počet zraněných osob celkem:", self.celkovy_pocet_zranenych),
            ("Činnost, při které k PÚ došlo:", self.cinnost_pri_urazu),
            ("Místo úrazu:", self.misto_urazu),
            ("Popis úrazového děje, místa, příčin a okolností:", self.popis_urazoveho_deje),
            ("Druh a rozsah zranění – upřesnění:", self.druh_a_rozsah_zraneni),
        ]:
            form.addRow(label, widget)

        return tab

    def _tab_pracoviste(self):
        tab = QWidget()
        form = QFormLayout(tab)

        self.workplace = WorkplaceSelector()
        self.pracoviste = self._line()
        self.charakteristika_pracoviste = self._text(70)
        self.zdroj_urazu = self._text(70)
        self.pricina_urazu = self._text(70)
        self.uraz_pracoviste_zamestnavatele = self._combo(["", "ANO", "NE"])
        self.subjekt_registrovan = self._combo(["", "ANO", "NE"])
        self.ico_subjektu = self._line()
        self.adresa_sidla_subjektu = self._text(60)
        self.ekonomicka_cinnost_subjektu = self._line()
        self.ekonomicka_cinnost_pracoviste = self._line()
        self.adresa_pracoviste = self._text(60)
        self.okres_pracoviste = self._line()
        self.popis_pracoviste = self._text(80)

        for label, widget in [
            ("Pracoviště z nastavení:", self.workplace),
            ("Pracoviště:", self.pracoviste),
            ("Charakteristika pracoviště:", self.charakteristika_pracoviste),
            ("Zdroj pracovního úrazu:", self.zdroj_urazu),
            ("Příčina pracovního úrazu:", self.pricina_urazu),
            ("Úraz na pracovišti zaměstnavatele:", self.uraz_pracoviste_zamestnavatele),
            ("Subjekt je registrován (má IČO):", self.subjekt_registrovan),
            ("IČO zaměstnavatele/subjektu:", self.ico_subjektu),
            ("Adresa sídla:", self.adresa_sidla_subjektu),
            ("Ekonomická činnost:", self.ekonomicka_cinnost_subjektu),
            ("Ekonomická činnost pracoviště:", self.ekonomicka_cinnost_pracoviste),
            ("Adresa pracoviště:", self.adresa_pracoviste),
            ("Okres pracoviště:", self.okres_pracoviste),
            ("Popis pracoviště:", self.popis_pracoviste),
        ]:
            form.addRow(label, widget)

        return tab

    def _tab_dalsi(self):
        tab = QWidget()
        form = QFormLayout(tab)

        self.kontrola_alkohol = self._combo(["", "ANO", "NE"])
        self.kontrola_alkohol_duvod_neprovedeni = self._text(60)
        self.vysledek_kontroly_alkohol = self._combo(["", "Negativní", "Pozitivní"])
        self.mnozstvi_alkohol = self._line()
        self.kontrola_navykove_latky = self._combo(["", "ANO", "NE"])
        self.kontrola_navykove_latky_duvod_neprovedeni = self._text(60)
        self.vysledek_kontroly_navykove_latky = self._combo(["", "Negativní", "Pozitivní"])
        self.navykove_latky_popis = self._text(60)
        self.porusene_predpisy = self._text(90)
        self.opatreni = self._text(90)

        for label, widget in [
            ("Kontrola přítomnosti alkoholu:", self.kontrola_alkohol),
            ("Důvod neprovedení kontroly alkoholu:", self.kontrola_alkohol_duvod_neprovedeni),
            ("Výsledek kontroly alkoholu:", self.vysledek_kontroly_alkohol),
            ("Množství v promile (‰):", self.mnozstvi_alkohol),
            ("Kontrola návykových látek:", self.kontrola_navykove_latky),
            ("Důvod neprovedení kontroly NL:", self.kontrola_navykove_latky_duvod_neprovedeni),
            ("Výsledek kontroly NL:", self.vysledek_kontroly_navykove_latky),
            ("Zjištěné návykové látky:", self.navykove_latky_popis),
            ("Předpisy, které byly porušeny a kým:", self.porusene_predpisy),
            ("Přijatá opatření k zabránění opakování úrazu:", self.opatreni),
        ]:
            form.addRow(label, widget)

        return tab

    def _tab_svedci(self):
        tab = QWidget()
        form = QFormLayout(tab)

        self.svedci = self._text(80)
        self.vyjadreni_svedku = self._text(90)
        self.vyjadreni_oo = self._text(70)
        self.zapsal_jmeno = self._line()
        self.zapsal_pracovni_zarazeni = self._line()
        self.poznamka = self._text(90)

        for label, widget in [
            ("Jména svědků úrazu:", self.svedci),
            ("Vyjádření svědků a postiženého zaměstnance:", self.vyjadreni_svedku),
            ("Vyjádření zástupce OO:", self.vyjadreni_oo),
            ("Vedoucí zaměstnanec postiženého:", self.zapsal_jmeno),
            ("Pracovní zařazení vedoucího zaměstnance:", self.zapsal_pracovni_zarazeni),
            ("Interní poznámka:", self.poznamka),
        ]:
            form.addRow(label, widget)

        return tab

    def _connect_logic(self):
        pass

    def _workplace_changed(self):
        pass

    def _refresh_logic(self):
        pass

    def _load(self, accident):
        self.tab_podatel_widget.load_data(accident)
        self.tab_zamestnanec_widget.load_data(accident)
        self.tab_uraz_widget.load_data(accident)
        self.tab_pracoviste_widget.load_data(accident)
        self.tab_dalsi_widget.load_data(accident)
        self.tab_svedci_widget.load_data(accident)

        for name in self._field_names():
            if not hasattr(self, name) or not hasattr(accident, name):
                continue
            self._set_widget_value(getattr(self, name), getattr(accident, name))


    def _field_names(self):
        return [

        ]

    def _set_widget_value(self, widget, value):
        if isinstance(widget, QLineEdit):
            widget.setText(str(value or ""))
        elif isinstance(widget, QTextEdit):
            widget.setPlainText(str(value or ""))
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(str(value or ""))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value or 1))
        elif isinstance(widget, NullableDateEdit):
            widget.set_date_value(value)
        elif isinstance(widget, DateEdit) and value:
            widget.set_date_iso(value.isoformat())

    def _get_widget_value(self, widget):
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, NullableDateEdit):
            return widget.get_date()
        if isinstance(widget, DateEdit):
            qdate = widget.date()
            return date(qdate.year(), qdate.month(), qdate.day())
        return None

    def get_data(self):
        data = self.tab_podatel_widget.get_data()
        data.update(self.tab_zamestnanec_widget.get_data())
        data.update(self.tab_uraz_widget.get_data())
        data.update(self.tab_pracoviste_widget.get_data())
        data.update(self.tab_dalsi_widget.get_data())
        data.update(self.tab_svedci_widget.get_data())
        data.update({name: self._get_widget_value(getattr(self, name)) for name in self._field_names() if hasattr(self, name)})
        return data
