from collections.abc import Callable
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import ENTITY_ACCIDENT
from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.editor_dialog_controller import (
    EDITOR_CLOSE_LABEL,
    EditorDialogController,
    _safe_disconnect,
    configure_editor_close_button,
    configure_editor_save_button,
    set_editor_save_enabled,
)
from core.widgets.dialog_utils import (
    configure_form_tab_navigation,
    create_save_cancel_box,
    configure_resizable_form_dialog,
    wrap_in_scroll_area,
)

from core.widgets.date_edit import DateEdit
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.kniha_urazu.sluzby.accident_service import accident_service
from moduly.kniha_urazu.sluzby.accident_dpn_care import (
    dpn_care_return_from_saved_data,
)
from moduly.kniha_urazu.sluzby.accident_dpn_responsibility import (
    dpn_employer_responsibility_from_saved_data,
)
from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    ACCIDENT_DATE_FUTURE_MESSAGE,
    DPN_END_BEFORE_START_MESSAGE,
    DPN_END_IN_FUTURE_MESSAGE,
    DPN_KIND_MISMATCH_BLOCK_MESSAGE,
    DPN_START_BEFORE_ACCIDENT_MESSAGE,
    RECORD_DATE_BEFORE_ACCIDENT_MESSAGE,
    dpn_calendar_days,
    dpn_record_update_overview_from_saved_data,
    is_accident_date_in_future,
    is_dpn_end_before_start,
    is_dpn_end_in_future,
    is_dpn_kind_mismatch,
    is_dpn_start_before_accident,
    is_record_date_before_accident,
)
from moduly.kniha_urazu.sluzby.breath_alcohol import (
    EXTREME_BREATH_ALCOHOL_CONFIRM_MESSAGE,
    EXTREME_BREATH_ALCOHOL_CONFIRM_TITLE,
    is_extreme_breath_alcohol,
)
from moduly.kniha_urazu.ui.tabs.tab_dalsi import TabDalsiUdaje
from moduly.kniha_urazu.ui.tabs.tab_po_ukonceni_dpn import (
    TAB_PO_UKONCENI_DPN,
    TabPoUkonceniDpn,
)
from moduly.kniha_urazu.ui.tabs.tab_pracoviste import TabPracoviste
from moduly.kniha_urazu.ui.tabs.tab_svedci import TabSvedci
from moduly.kniha_urazu.ui.tabs.tab_uraz import TabUraz
from moduly.kniha_urazu.ui.tabs.tab_zamestnanec import TabZamestnanec
from moduly.kniha_urazu.ui.tabs.tab_zapisovatel_zamestnavatel import TabZapisovatelZamestnavatel


ACCIDENT_DATE_CHANGE_TITLE = "Změnit datum úrazu?"
ACCIDENT_DATE_CHANGE_MESSAGE = (
    "Změna data úrazu může ovlivnit zákonné lhůty, oznámení a navazující evidenci. "
    "Opravdu chcete uložit nové datum úrazu?"
)
ACCIDENT_DATE_CHANGE_CONFIRM_LABEL = "Změnit datum úrazu"
ACCIDENT_DATE_CHANGE_CANCEL_LABEL = "Zrušit"
UNSAVED_CHANGES_PROMPT = (
    "V záznamu pracovního úrazu jsou neuložené změny. Chcete je uložit?"
)
UNSAVED_DISCARD_LABEL = "Zahodit změny"
SAVE_CONFIRMATION_TITLE = "Pracovní úraz"
SAVE_CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."
_SAVE_CLOSE_LABEL = "Uložit a zavřít"


def _exec_message_box(box: QMessageBox) -> int:
    return box.exec()


def _normalize_snapshot(value):
    """Stejná normalizace, jakou při uložení dělá ``get_data`` (ořez textu, vnořené struktury)."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return {key: _normalize_snapshot(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_snapshot(item) for item in value]
    return value


class _AccidentEditorController(EditorDialogController):
    """Stejná lišta jako u MU a událostí; Uložit zůstává dostupné i na čistém formuláři.

    Skrytý dialog (testy před ``show``) se zavírá bez dotazu, stejně jako dřív.
    """

    def request_close(self) -> bool:
        dialog = self._dialog
        if getattr(dialog, "_closing", False):
            return True
        if dialog is not None and not dialog.isVisible():
            return True
        return super().request_close()

    def eventFilter(self, watched, event):  # noqa: N802
        dialog = getattr(self, "_dialog", None)
        if dialog is not None and getattr(dialog, "_closing", False):
            self._closing = True
            return False
        return super().eventFilter(watched, event)

    def _refresh_save_enabled(self) -> None:
        set_editor_save_enabled(self._buttons, True)
        if self.save_button is not None:
            self.save_button.setEnabled(True)
        for button in self._extra_save_buttons:
            button.setEnabled(True)


class AccidentDialog(QDialog):
    def __init__(self, parent=None, accident=None, focus_tab=None, *, on_persist=None):
        super().__init__(parent)

        self.accident = accident
        self._on_persist: Callable[[dict], object] | None = on_persist
        self._baseline: dict | None = None
        self._closing = False
        self._baseline_after_show = False
        self._was_saved = False
        self._editor: _AccidentEditorController | None = None
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
        self.tab_po_ukonceni_dpn_widget = TabPoUkonceniDpn()
        self.tab_attachments_widget = AttachmentWidget(
            entity_type=ENTITY_ACCIDENT,
            entity_id=accident.id if accident is not None else None,
        )

        self.tabs.addTab(wrap_in_scroll_area(self.tab_podatel_widget), "Zapisovatel")
        self.tabs.addTab(wrap_in_scroll_area(self.tab_zamestnanec_widget), "Zaměstnanec")
        self.tabs.addTab(wrap_in_scroll_area(self.tab_uraz_widget), "Údaje o úrazu")
        self.tabs.addTab(wrap_in_scroll_area(self.tab_pracoviste_widget), "Pracoviště")
        self.tabs.addTab(wrap_in_scroll_area(self.tab_dalsi_widget), "Další údaje")
        self.tabs.addTab(wrap_in_scroll_area(self.tab_attachments_widget), "Přílohy")
        self.tabs.addTab(wrap_in_scroll_area(self.tab_svedci_widget), "Svědci")
        self.tabs.addTab(wrap_in_scroll_area(self.tab_po_ukonceni_dpn_widget), TAB_PO_UKONCENI_DPN)

        layout.addWidget(self.tabs, 1)

        buttons = create_save_cancel_box(self, is_new=accident is None)
        self._editor = _AccidentEditorController(
            self,
            buttons,
            is_new=accident is None,
            title=self.windowTitle(),
            on_save=self._persist,
            unsaved_text=UNSAVED_CHANGES_PROMPT,
            discard_label=UNSAVED_DISCARD_LABEL,
        )
        if self._editor.save_button is not None:
            _safe_disconnect(
                self._editor.save_button.clicked,
                self._editor._handle_save_clicked,
            )
            self._editor.save_button.clicked.connect(self._save_keep_open)
        configure_editor_close_button(self._editor.close_button, is_new=False)
        if self._editor.close_button is not None:
            self._editor.close_button.setText(EDITOR_CLOSE_LABEL)
        layout.addLayout(self._build_footer())
        buttons.hide()
        for button in (
            self._editor.save_button,
            self._save_close_btn,
            self._editor.close_button,
        ):
            if button is not None:
                button.setVisible(True)
        self._editor.set_snapshot_provider(self._snapshot)

        self._connect_logic()

        if accident is not None:
            self._load(accident)

        self._refresh_logic()
        configure_form_tab_navigation(self)
        self._apply_focus_tab(focus_tab)
        self._capture_baseline()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # Widgety (číselníky, zaměstnavatel ze nastavení) se mohou dopočítat až při zobrazení.
        if not self._baseline_after_show:
            self._baseline_after_show = True
            self._capture_baseline()

    @property
    def was_saved(self) -> bool:
        return self._was_saved

    def _build_footer(self) -> QHBoxLayout:
        """Vpravo Uložit | Uložit a zavřít | Zavřít."""
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addStretch(1)

        assert self._editor is not None
        self._save_close_btn = QPushButton(_SAVE_CLOSE_LABEL)
        configure_editor_save_button(self._save_close_btn)
        self._save_close_btn.setText(_SAVE_CLOSE_LABEL)
        self._save_close_btn.clicked.connect(self._save_and_close)
        self._editor.bind_extra_save_button(self._save_close_btn)

        ordered = [
            self._editor.save_button,
            self._save_close_btn,
            self._editor.close_button,
        ]
        for button in ordered:
            if button is None:
                continue
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.setAutoDefault(False)
            button.setDefault(False)
            footer.addWidget(button)
        return footer

    def _snapshot(self):
        return _normalize_snapshot(self.get_data())

    def _capture_baseline(self) -> None:
        self._baseline = self._snapshot()
        if self._editor is not None:
            self._editor.capture_baseline()

    def _is_dirty(self) -> bool:
        return self._snapshot() != self._baseline

    def _show_save_confirmation(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(SAVE_CONFIRMATION_TITLE)
        box.setText(SAVE_CONFIRMATION_TEXT)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        ok_button = box.button(QMessageBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("OK")
        _exec_message_box(box)

    def _save_keep_open(self) -> None:
        """Uloží změny, potvrdí úspěch a editor nechá otevřený."""
        confirm = self._is_dirty() or getattr(self.accident, "id", None) is None
        assert self._editor is not None
        if not self._editor._run_save():
            return
        if confirm:
            self._show_save_confirmation()

    def _save_and_close(self) -> None:
        if self._closing or (self._editor is not None and self._editor._closing):
            self._closing = True
            if self._editor is not None:
                self._editor._closing = True
            QDialog.accept(self)
            return
        assert self._editor is not None
        if not self._editor._run_save():
            return
        self._closing = True
        self._editor._closing = True
        QDialog.accept(self)

    def _persist(self) -> bool:
        """Společný zápis pro Uložit, Uložit a zavřít i Uložit v dotazu při zavření."""
        has_id = getattr(self.accident, "id", None) is not None
        if has_id and not self._is_dirty():
            return True

        if not self._validate_tabs():
            return False
        if not self._validate_date_rules():
            return False
        if not self._confirm_extreme_breath_alcohol():
            return False
        if not self._confirm_injury_date_change():
            return False

        if self._on_persist is not None:
            try:
                result = self._on_persist(self.get_data())
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Nelze uložit pracovní úraz",
                    "Pracovní úraz se nepodařilo uložit.\n\n" + str(exc),
                )
                return False
            if result is None or result is False:
                QMessageBox.warning(
                    self,
                    "Nelze uložit pracovní úraz",
                    "Pracovní úraz se nepodařilo uložit.",
                )
                return False
            if result is not True:
                self._adopt_saved(result)
            elif has_id:
                self._was_saved = True

        self._finish_saved_form()
        return True

    def _adopt_saved(self, saved) -> None:
        """Po prvním vytvoření další Uložit aktualizuje stejný záznam."""
        self.accident = saved
        accident_id = getattr(saved, "id", None)
        if not accident_id:
            return
        self.tab_attachments_widget.set_entity(ENTITY_ACCIDENT, int(accident_id))
        self._was_saved = True

        def update(data: dict, accident_id: int = int(accident_id)) -> bool:
            return accident_service.update_accident(accident_id, **data) is not None

        self._on_persist = update

    def _finish_saved_form(self) -> None:
        self.tab_uraz_widget.commit_injury_date_baseline()
        self._capture_baseline()

    def _validate_tabs(self) -> bool:
        validations = [
            ("Zapisovatel", self.tab_podatel_widget),
            ("Zaměstnanec", self.tab_zamestnanec_widget),
        ]

        if hasattr(self, "tab_uraz_widget"):
            validations.append(("Údaje o úrazu", self.tab_uraz_widget))

        if hasattr(self, "tab_pracoviste_widget"):
            validations.append(("Pracoviště", self.tab_pracoviste_widget))

        if hasattr(self, "tab_dalsi_widget"):
            validations.append(("Další údaje", self.tab_dalsi_widget))

        if hasattr(self, "tab_svedci_widget"):
            validations.append(("Svědci", self.tab_svedci_widget))

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
                return False
        return True

    def _apply_focus_tab(self, focus_tab: str | None) -> None:
        title = (focus_tab or "").strip()
        if not title:
            return
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                self.tabs.setCurrentIndex(index)
                return

    def accept(self) -> None:
        """Uložit a zavřít. Při chybě validace nebo zápisu editor zůstane otevřený."""
        self._save_and_close()

    def _confirm_extreme_breath_alcohol(self) -> bool:
        value = self.tab_dalsi_widget.get_data().get("mnozstvi_alkohol", "")
        if not is_extreme_breath_alcohol(value):
            return True

        self._focus_tab_containing(self.tab_dalsi_widget)
        self.tab_dalsi_widget.mnozstvi_alkohol.setFocus()

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(EXTREME_BREATH_ALCOHOL_CONFIRM_TITLE)
        box.setText(EXTREME_BREATH_ALCOHOL_CONFIRM_MESSAGE)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        yes_button = box.button(QMessageBox.StandardButton.Yes)
        no_button = box.button(QMessageBox.StandardButton.No)
        if yes_button is not None:
            yes_button.setText("Ano")
        if no_button is not None:
            no_button.setText("Ne")
        return box.exec() == QMessageBox.StandardButton.Yes

    def _confirm_injury_date_change(self) -> bool:
        if self.accident is None or getattr(self.accident, "id", None) is None:
            return True
        if not self.tab_uraz_widget.injury_date_changed_from_baseline():
            return True

        box = QMessageBox(self)
        box.setWindowModality(Qt.WindowModality.WindowModal)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(ACCIDENT_DATE_CHANGE_TITLE)
        box.setText(ACCIDENT_DATE_CHANGE_MESSAGE)
        confirm_btn = box.addButton(
            ACCIDENT_DATE_CHANGE_CONFIRM_LABEL,
            QMessageBox.ButtonRole.ActionRole,
        )
        cancel_btn = box.addButton(
            ACCIDENT_DATE_CHANGE_CANCEL_LABEL,
            QMessageBox.ButtonRole.ActionRole,
        )
        box.setDefaultButton(cancel_btn)
        box.setEscapeButton(cancel_btn)
        box.exec()
        return box.clickedButton() is confirm_btn

    def _validate_date_rules(self) -> bool:
        accident_date = self.tab_uraz_widget.get_accident_date()
        if is_accident_date_in_future(accident_date):
            self._focus_tab_containing(self.tab_uraz_widget)
            self.tab_uraz_widget.accident_date.setFocus()
            QMessageBox.warning(
                self,
                "Nelze uložit pracovní úraz",
                ACCIDENT_DATE_FUTURE_MESSAGE,
            )
            return False

        datum_zapisu = self.tab_podatel_widget.datum_zapisu.get_date()
        if is_record_date_before_accident(datum_zapisu, accident_date):
            self._focus_tab_containing(self.tab_podatel_widget)
            self.tab_podatel_widget.datum_zapisu.setFocus()
            QMessageBox.warning(
                self,
                "Nelze uložit pracovní úraz",
                RECORD_DATE_BEFORE_ACCIDENT_MESSAGE,
            )
            return False

        if not self._validate_dpn_rules(accident_date):
            return False

        return True

    def _validate_dpn_rules(self, accident_date: date | None) -> bool:
        dpn_od = self.tab_uraz_widget.dpn_od.get_date()
        dpn_do = self.tab_uraz_widget.dpn_do.get_date()

        if is_dpn_start_before_accident(dpn_od, accident_date):
            self._focus_tab_containing(self.tab_uraz_widget)
            self.tab_uraz_widget.dpn_od.setFocus()
            QMessageBox.warning(
                self,
                "Nelze uložit pracovní úraz",
                DPN_START_BEFORE_ACCIDENT_MESSAGE,
            )
            return False

        if is_dpn_end_before_start(dpn_od, dpn_do):
            self._focus_tab_containing(self.tab_uraz_widget)
            self.tab_uraz_widget.dpn_do.setFocus()
            QMessageBox.warning(
                self,
                "Nelze uložit pracovní úraz",
                DPN_END_BEFORE_START_MESSAGE,
            )
            return False

        if is_dpn_end_in_future(dpn_do):
            self._focus_tab_containing(self.tab_uraz_widget)
            self.tab_uraz_widget.dpn_do.setFocus()
            QMessageBox.warning(
                self,
                "Nelze uložit pracovní úraz",
                DPN_END_IN_FUTURE_MESSAGE,
            )
            return False

        days = dpn_calendar_days(dpn_od, dpn_do)
        druh_urazu = self.tab_uraz_widget.druh_urazu.value()
        if is_dpn_kind_mismatch(druh_urazu, days):
            self._focus_tab_containing(self.tab_uraz_widget)
            QMessageBox.warning(
                self,
                "Nelze uložit pracovní úraz",
                DPN_KIND_MISMATCH_BLOCK_MESSAGE,
            )
            return False

        return True

    def _focus_tab_containing(self, inner_widget: QWidget) -> None:
        current = inner_widget
        while current is not None:
            index = self.tabs.indexOf(current)
            if index >= 0:
                self.tabs.setCurrentIndex(index)
                return
            current = current.parentWidget()

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
        self.tab_uraz_widget.druh_urazu.currentTextChanged.connect(self._refresh_dpn_kind_warning)
        self.tab_uraz_widget.dpn_od.dateChanged.connect(self._refresh_dpn_kind_warning)
        self.tab_uraz_widget.dpn_do.dateChanged.connect(self._refresh_dpn_kind_warning)
        self.tab_uraz_widget.dpn_od.dateChanged.connect(self._refresh_po_ukonceni_dpn)
        self.tab_uraz_widget.dpn_do.dateChanged.connect(self._refresh_po_ukonceni_dpn)

    def _workplace_changed(self):
        pass

    def _refresh_logic(self):
        self._refresh_dpn_kind_warning()
        self._refresh_po_ukonceni_dpn()
        self.tab_uraz_widget.refresh_date_and_kind_hints()

    def _refresh_dpn_kind_warning(self, *_args) -> None:
        self.tab_uraz_widget.refresh_dpn_kind_warning(
            self.tab_uraz_widget.druh_urazu.value()
        )

    def _refresh_po_ukonceni_dpn(self, *_args) -> None:
        self.tab_po_ukonceni_dpn_widget.set_from_dpn_range(
            self.tab_uraz_widget.dpn_od.get_date(),
            self.tab_uraz_widget.dpn_do.get_date(),
        )

    def _load(self, accident):
        self.tab_podatel_widget.load_data(accident)
        self.tab_zamestnanec_widget.load_data(accident)
        self.tab_uraz_widget.load_data(accident)
        self.tab_pracoviste_widget.load_data(accident)
        self.tab_dalsi_widget.load_data(accident)
        self.tab_svedci_widget.load_data(accident)
        self._load_dpn_record_update(accident)

        for name in self._field_names():
            if not hasattr(self, name) or not hasattr(accident, name):
                continue
            self._set_widget_value(getattr(self, name), getattr(accident, name))

        self._refresh_dpn_kind_warning()
        self._refresh_po_ukonceni_dpn()
        self.tab_uraz_widget.refresh_date_and_kind_hints()

    def _load_dpn_record_update(self, accident) -> None:
        if accident is None or getattr(accident, "id", None) is None:
            self.tab_po_ukonceni_dpn_widget.load_dpn_record_update(None)
            self.tab_po_ukonceni_dpn_widget.load_dpn_care_return(None)
            self.tab_po_ukonceni_dpn_widget.load_dpn_employer_responsibility(None)
            return
        import json

        from moduly.kniha_urazu.sluzby.investigation_service import investigation_service

        investigation = investigation_service.get_or_create(accident.id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        try:
            saved = json.loads(raw) if str(raw).strip() else {}
        except Exception:
            saved = {}
        if not isinstance(saved, dict):
            saved = {}
        self.tab_po_ukonceni_dpn_widget.load_dpn_record_update(
            dpn_record_update_overview_from_saved_data(accident, saved)
        )
        self.tab_po_ukonceni_dpn_widget.load_dpn_care_return(
            dpn_care_return_from_saved_data(saved)
        )
        self.tab_po_ukonceni_dpn_widget.load_dpn_employer_responsibility(
            dpn_employer_responsibility_from_saved_data(saved)
        )

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
        data["dpn_care_return"] = self.tab_po_ukonceni_dpn_widget.get_dpn_care_return()
        data["dpn_record_update"] = self.tab_po_ukonceni_dpn_widget.get_dpn_record_update()
        data["dpn_employer_responsibility"] = (
            self.tab_po_ukonceni_dpn_widget.get_dpn_employer_responsibility()
        )
        return data
