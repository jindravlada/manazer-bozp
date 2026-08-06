"""Dialog ohlášení pracovního úrazu odborové organizaci."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.services.storage_service import storage_service
from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_close_box,
)
from moduly.kniha_urazu.sluzby.union_notice_service import (
    ACTION_PDF,
    ACTION_PREVIEW,
    ACTION_PRINT,
    DOCUMENT_SUBTITLE,
    DOCUMENT_TITLE,
    RELATION_AGREEMENT,
    RELATION_EMPLOYMENT,
    RELATION_OTHER,
    RELATION_OUTSIDE,
    RELATION_SERVICE,
    UnionNoticeData,
    union_notice_service,
)

RELATION_CHOICES = (
    "",
    RELATION_EMPLOYMENT,
    RELATION_SERVICE,
    RELATION_AGREEMENT,
    RELATION_OUTSIDE,
    RELATION_OTHER,
)

GENDER_CHOICES = ("", "Muž", "Žena")
YES_NO_CHOICES = ("", "Ano", "Ne")


class UnionNoticeMissingDialog(QDialog):
    def __init__(self, parent, missing_required: list, not_relevant: list):
        super().__init__(parent)
        self.setWindowTitle("Chybějící náležitosti ohlášení")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(520, 420)
        self.choice = "back"

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Před finálním výstupem zkontrolujte náležitosti podle "
                "přílohy č. 2 k nařízení vlády č. 322/2025 Sb."
            )
        )

        if missing_required:
            layout.addWidget(QLabel("<b>Chybí povinný údaj:</b>"))
            for item in missing_required:
                layout.addWidget(QLabel(f"• [{item.section}] {item.label}"))

        if not_relevant:
            layout.addWidget(QLabel("<b>Údaj není pro daný úraz relevantní:</b>"))
            for item in not_relevant:
                layout.addWidget(QLabel(f"• [{item.section}] {item.label}"))

        if not missing_required:
            layout.addWidget(QLabel("Všechny povinné náležitosti jsou vyplněny."))

        buttons = QDialogButtonBox(self)
        back_btn = QPushButton("Vrátit se k doplnění")
        draft_btn = QPushButton("Pracovní náhled")
        final_btn = QPushButton("Pokračovat k finálnímu výstupu")
        final_btn.setEnabled(not missing_required)
        buttons.addButton(back_btn, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.addButton(draft_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(final_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        back_btn.clicked.connect(self._back)
        draft_btn.clicked.connect(self._draft)
        final_btn.clicked.connect(self._final)
        layout.addWidget(buttons)

    def _back(self) -> None:
        self.choice = "back"
        self.reject()

    def _draft(self) -> None:
        self.choice = "draft"
        self.accept()

    def _final(self) -> None:
        self.choice = "final"
        self.accept()


class UnionNoticePreviewDialog(QDialog):
    def __init__(self, parent, html: str, *, title: str = "Náhled ohlášení"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(self, width=780, height=700, min_width=520, min_height=400)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(html)
        layout.addWidget(browser, 1)
        buttons = create_close_box(self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class UnionNoticeDialog(QDialog):
    """Formulář ohlášení + Náhled / Tisk / Uložit jako PDF."""

    def __init__(self, parent=None, *, accident):
        super().__init__(parent)
        self.accident = accident
        self._original_snapshot = None
        self.setWindowTitle(f"{DOCUMENT_TITLE} – {DOCUMENT_SUBTITLE}")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(self, width=860, height=720, min_width=640, min_height=480)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Údaje jsou předvyplněny ze záznamu úrazu. Úpravy v tomto dialogu "
            "jsou jednorázové a neukládají se do karty úrazu ani zaměstnance."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_employer(), "I. Zaměstnavatel")
        self.tabs.addTab(self._tab_employee(), "II. Zaměstnanec")
        self.tabs.addTab(self._tab_place(), "III–VI. Místo a práce")
        self.tabs.addTab(self._tab_injury(), "VII–VIII. Úraz")
        self.tabs.addTab(self._tab_notifier(), "IX. Oznamující")
        layout.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        self.preview_btn = QPushButton("Náhled")
        self.print_btn = QPushButton("Tisk")
        self.pdf_btn = QPushButton("Uložit jako PDF")
        self.close_btn = QPushButton("Zavřít")
        footer.addWidget(self.preview_btn)
        footer.addWidget(self.print_btn)
        footer.addWidget(self.pdf_btn)
        footer.addStretch()
        footer.addWidget(self.close_btn)
        layout.addLayout(footer)

        self.preview_btn.clicked.connect(lambda: self._run_output("preview"))
        self.print_btn.clicked.connect(lambda: self._run_output("print"))
        self.pdf_btn.clicked.connect(lambda: self._run_output("pdf"))
        self.close_btn.clicked.connect(self.reject)

        data = union_notice_service.build_from_accident(accident)
        self._load_data(data)
        self._original_snapshot = self.get_data()

    def _line(self) -> QLineEdit:
        return QLineEdit()

    def _text(self, height: int = 90) -> QTextEdit:
        edit = QTextEdit()
        edit.setAcceptRichText(False)
        edit.setMinimumHeight(height)
        return edit

    def _combo(self, items: tuple[str, ...]) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(False)
        combo.addItems(list(items))
        return combo

    def _tab_employer(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.employer_name = self._line()
        self.employer_ico = self._line()
        self.employer_birth_date = self._line()
        self.employer_birth_date.setPlaceholderText("Jen pokud nemá IČO")
        self.employer_address = self._text(70)
        form.addRow("Jméno:", self.employer_name)
        form.addRow("IČO:", self.employer_ico)
        form.addRow("Datum narození (bez IČO):", self.employer_birth_date)
        form.addRow("Adresa sídla / místa pobytu:", self.employer_address)
        return self._scroll(page)

    def _tab_employee(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.employee_name = self._line()
        self.employee_birth_date = self._line()
        self.employee_gender = self._combo(GENDER_CHOICES)
        self.employee_citizenship = self._line()
        self.employee_residence = self._text(70)
        self.employee_delivery_address = self._text(60)
        self.employee_relation = self._combo(RELATION_CHOICES)
        self.employee_relation_start = self._line()
        form.addRow("Jméno:", self.employee_name)
        form.addRow("Datum narození:", self.employee_birth_date)
        form.addRow("Pohlaví:", self.employee_gender)
        form.addRow("Státní občanství:", self.employee_citizenship)
        form.addRow("Adresa místa pobytu:", self.employee_residence)
        form.addRow("Doručovací adresa (pokud odlišná):", self.employee_delivery_address)
        form.addRow("Vztah k zaměstnavateli:", self.employee_relation)
        form.addRow("Den vzniku právního vztahu:", self.employee_relation_start)
        return self._scroll(page)

    def _tab_place(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.accident_place_address = self._text(70)
        self.workplace_characteristic = self._text(70)
        self.activity = self._line()
        self.cz_isco = self._line()
        form.addRow("Adresa místa úrazu:", self.accident_place_address)
        form.addRow("Charakteristika pracoviště:", self.workplace_characteristic)
        form.addRow("Činnost při úrazu:", self.activity)
        form.addRow("CZ-ISCO:", self.cz_isco)
        return self._scroll(page)

    def _tab_injury(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.accident_date = self._line()
        self.accident_time = self._line()
        self.death_date = self._line()
        self.injury_type = self._line()
        self.body_part = self._line()
        self.injured_count = self._line()
        self.mass_accident = self._combo(YES_NO_CHOICES)
        self.description = self._text(110)
        self.cause = self._text(70)
        self.source = self._text(70)
        form.addRow("Datum úrazu:", self.accident_date)
        form.addRow("Čas úrazu:", self.accident_time)
        form.addRow("Datum úmrtí:", self.death_date)
        form.addRow("Druh zranění:", self.injury_type)
        form.addRow("Zraněná část těla:", self.body_part)
        form.addRow("Počet zraněných osob:", self.injured_count)
        form.addRow("Hromadný pracovní úraz:", self.mass_accident)
        form.addRow("Popis:", self.description)
        form.addRow("Příčina:", self.cause)
        form.addRow("Zdroj:", self.source)
        return self._scroll(page)

    def _tab_notifier(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.notifier_name = self._line()
        self.notifier_phone = self._line()
        self.notifier_email = self._line()
        self.notifier_position = self._line()
        form.addRow("Jméno:", self.notifier_name)
        form.addRow("Telefon:", self.notifier_phone)
        form.addRow("E-mail:", self.notifier_email)
        form.addRow("Pracovní zařazení:", self.notifier_position)
        return self._scroll(page)

    def _scroll(self, page: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    def _set_combo(self, combo: QComboBox, value: str) -> None:
        text = (value or "").strip()
        index = combo.findText(text)
        if index < 0 and text:
            combo.addItem(text)
            index = combo.findText(text)
        combo.setCurrentIndex(max(index, 0))

    def _load_data(self, data: UnionNoticeData) -> None:
        self.employer_name.setText(data.employer_name)
        self.employer_ico.setText(data.employer_ico)
        self.employer_birth_date.setText(data.employer_birth_date)
        self.employer_address.setPlainText(data.employer_address)
        self.employee_name.setText(data.employee_name)
        self.employee_birth_date.setText(data.employee_birth_date)
        self._set_combo(self.employee_gender, data.employee_gender)
        self.employee_citizenship.setText(data.employee_citizenship)
        self.employee_residence.setPlainText(data.employee_residence)
        self.employee_delivery_address.setPlainText(data.employee_delivery_address)
        self._set_combo(self.employee_relation, data.employee_relation)
        self.employee_relation_start.setText(data.employee_relation_start)
        self.accident_place_address.setPlainText(data.accident_place_address)
        self.workplace_characteristic.setPlainText(data.workplace_characteristic)
        self.activity.setText(data.activity)
        self.cz_isco.setText(data.cz_isco)
        self.accident_date.setText(data.accident_date)
        self.accident_time.setText(data.accident_time)
        self.death_date.setText(data.death_date)
        self.death_date.setEnabled(bool(data.is_fatal))
        self.injury_type.setText(data.injury_type)
        self.body_part.setText(data.body_part)
        self.injured_count.setText(data.injured_count)
        self._set_combo(self.mass_accident, data.mass_accident)
        self.description.setPlainText(data.description)
        self.cause.setPlainText(data.cause)
        self.source.setPlainText(data.source)
        self.notifier_name.setText(data.notifier_name)
        self.notifier_phone.setText(data.notifier_phone)
        self.notifier_email.setText(data.notifier_email)
        self.notifier_position.setText(data.notifier_position)
        self._is_fatal = bool(data.is_fatal)
        self._accident_id = int(data.accident_id)

    def get_data(self) -> UnionNoticeData:
        return UnionNoticeData(
            accident_id=self._accident_id,
            employer_name=self.employer_name.text().strip(),
            employer_ico=self.employer_ico.text().strip(),
            employer_birth_date=self.employer_birth_date.text().strip(),
            employer_address=self.employer_address.toPlainText().strip(),
            employee_name=self.employee_name.text().strip(),
            employee_birth_date=self.employee_birth_date.text().strip(),
            employee_gender=self.employee_gender.currentText().strip(),
            employee_citizenship=self.employee_citizenship.text().strip(),
            employee_residence=self.employee_residence.toPlainText().strip(),
            employee_delivery_address=self.employee_delivery_address.toPlainText().strip(),
            employee_relation=self.employee_relation.currentText().strip(),
            employee_relation_start=self.employee_relation_start.text().strip(),
            accident_place_address=self.accident_place_address.toPlainText().strip(),
            workplace_characteristic=self.workplace_characteristic.toPlainText().strip(),
            activity=self.activity.text().strip(),
            cz_isco=self.cz_isco.text().strip(),
            accident_date=self.accident_date.text().strip(),
            accident_time=self.accident_time.text().strip(),
            death_date=self.death_date.text().strip(),
            injury_type=self.injury_type.text().strip(),
            body_part=self.body_part.text().strip(),
            injured_count=self.injured_count.text().strip(),
            mass_accident=self.mass_accident.currentText().strip(),
            is_fatal=bool(self._is_fatal),
            description=self.description.toPlainText().strip(),
            cause=self.cause.toPlainText().strip(),
            source=self.source.toPlainText().strip(),
            notifier_name=self.notifier_name.text().strip(),
            notifier_phone=self.notifier_phone.text().strip(),
            notifier_email=self.notifier_email.text().strip(),
            notifier_position=self.notifier_position.text().strip(),
        )

    def _run_output(self, mode: str) -> None:
        data = self.get_data()
        missing = union_notice_service.validate(data)
        required = [item for item in missing if item.kind == "required"]
        not_relevant = [item for item in missing if item.kind == "not_relevant"]

        if mode == "preview":
            # Náhled vždy dovolí pracovní výstup; při chybách označí [CHYBÍ].
            draft = bool(required)
            if required:
                checklist = UnionNoticeMissingDialog(self, required, not_relevant)
                if checklist.exec() != QDialog.DialogCode.Accepted:
                    return
                if checklist.choice == "back":
                    return
                draft = checklist.choice != "final" or bool(required)
                if checklist.choice == "final" and required:
                    draft = True
            html = union_notice_service.build_html(data, draft=draft)
            UnionNoticePreviewDialog(self, html).exec()
            union_notice_service.record_history(
                self._accident_id,
                action=ACTION_PREVIEW,
                notifier_name=data.notifier_name,
            )
            return

        # Tisk / PDF – finální jen bez chybějících povinných.
        checklist = UnionNoticeMissingDialog(self, required, not_relevant)
        if checklist.exec() != QDialog.DialogCode.Accepted:
            return
        if checklist.choice == "back":
            return
        if checklist.choice == "draft":
            html = union_notice_service.build_html(data, draft=True)
            UnionNoticePreviewDialog(
                self, html, title="Pracovní náhled ohlášení"
            ).exec()
            union_notice_service.record_history(
                self._accident_id,
                action=ACTION_PREVIEW,
                notifier_name=data.notifier_name,
            )
            return

        if required:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Finální výstup nelze vytvořit, dokud chybí povinné údaje.",
            )
            return

        html = union_notice_service.build_html(data, draft=False)
        if mode == "print":
            self._print_html(html)
            union_notice_service.record_history(
                self._accident_id,
                action=ACTION_PRINT,
                notifier_name=data.notifier_name,
            )
        elif mode == "pdf":
            path = self._save_pdf(html, data)
            if path is not None:
                union_notice_service.record_history(
                    self._accident_id,
                    action=ACTION_PDF,
                    notifier_name=data.notifier_name,
                )

    def _print_html(self, html: str) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        document = QTextDocument()
        document.setHtml(html)
        document.print_(printer)

    def _save_pdf(self, html: str, data: UnionNoticeData) -> Path | None:
        storage_service.ensure_structure()
        default_name = f"OhlaseniOO-{self._accident_id}.pdf"
        default_dir = storage_service.export_file("ohlaseni", default_name).parent
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Uložit ohlášení jako PDF",
            str(default_dir / default_name),
            "PDF (*.pdf)",
        )
        if not path_str:
            return None
        path = Path(path_str)
        if path.suffix.lower() != ".pdf":
            path = path.with_suffix(".pdf")
        try:
            union_notice_service.write_pdf(html, path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                f"PDF se nepodařilo uložit.\n\n{exc}",
            )
            return None
        QMessageBox.information(self, self.windowTitle(), f"PDF uloženo:\n{path}")
        return path
